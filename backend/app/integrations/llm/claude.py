from dataclasses import dataclass

from anthropic import AsyncAnthropic

from app.core.config import get_settings

MODEL_SONNET_5 = "claude-sonnet-5"
MODEL_HAIKU_4_5 = "claude-haiku-4-5-20251001"

# Mirrors frontend/lib/conversation-api.ts's SCENE_LABELS — the LLM was
# previously getting the raw enum value (e.g. "workplace"), not the Japanese
# label a human would actually describe the scene as.
_SCENE_LABELS_JA = {
    "school_university": "学校・大学",
    "workplace": "職場",
    "first_meeting": "初対面",
    "friend": "友人との会話",
    "romantic": "恋愛・気になる人",
}

# §12.3確定事項26: AmiVoice ESASの正式パラメータ定義（日本語名・値域）を
# 公式APIから取得したもの。分析結果の解釈だけでなく、この一覧をLLMに渡す
# ためにも使う — 素のPython dictをそのまま渡すと、値域も日本語名も無い
# 英語変数名だけの数値の羅列になり、LLMが数値の大小を正しく解釈できない。
_PROSODY_PARAM_INFO: dict[str, tuple[str, float, float]] = {
    "energy": ("エネルギー", 0, 100),
    "stress": ("ストレス", 0, 100),
    "emo_cog": ("感情バランス論理", 1, 500),
    "concentration": ("集中", 0, 100),
    "anticipation": ("期待", 0, 100),
    "excitement": ("興奮", 0, 30),
    "hesitation": ("躊躇", 0, 30),
    "uncertainty": ("不確実", 0, 30),
    "intensive_thinking": ("思考", 0, 100),
    "imagination_activity": ("想像力", 0, 30),
    "embarrassment": ("困惑", 0, 30),
    "passionate": ("情熱", 0, 30),
    "brain_power": ("脳活動", 0, 100),
    "confidence": ("自信", 0, 30),
    "aggression": ("攻撃性・憤り", 0, 30),
    "atmosphere": ("雰囲気・会話傾向", -100, 100),
    "upset": ("動揺", 0, 30),
    "content": ("喜び", 0, 30),
    "dissatisfaction": ("不満", 0, 30),
    "extreme_emotion": ("極端な起伏", 0, 30),
}


def _format_prosody_scores(scores: dict[str, float]) -> str:
    if not scores:
        return "（利用不可）"
    lines = []
    for key, value in scores.items():
        name, lo, hi = _PROSODY_PARAM_INFO.get(key, (key, None, None))
        range_note = f"、値域{lo}〜{hi}" if lo is not None else ""
        lines.append(f"- {name}（{key}{range_note}）: {value:.1f}")
    return "\n" + "\n".join(lines)


@dataclass
class ConversationReport:
    """The slower half of the report (§11.6: "プロソディ解析やLLM統合が
    必要な項目は後から埋まる"). Topic is handled separately by
    extract_topic() with Haiku, since §11.6 groups transcription+topic as
    the fast-returning step and everything here needs the fuller Sonnet 5
    reasoning pass."""

    flow: str
    other_reaction: str
    relationship_distance: str
    suggestion_category: str
    suggestion_text: str


@dataclass
class StatementCheckResult:
    is_safe: bool
    feedback: str


@dataclass
class SummaryResult:
    summary_bullets: list[str]


# §11.11 出力文言の方針: baked directly into the system prompt so every
# report the model writes already uses hedged language for the fields
# where the pipeline's own inference can be wrong — not left as a
# find-and-replace on the model's output afterward.
_REPORT_SYSTEM_PROMPT = """\
あなたはASD等コミュニケーションに難がある方の対話を支援するアプリのバックエンドで、
会話分析を行うアシスタントです。1ラウンド分の会話の文字起こし（発言者は
user=アプリ利用者本人、other=会話の相手、と話者識別済み）と、可能であれば声の
トーンから推定した感情スコアを受け取り、構造化されたレポートを生成します。

出力は必ずsubmit_conversation_reportツールで返してください。各フィールドの方針：

- 場面（例：職場、初対面）ごとに、期待される言葉遣いや距離感の基準は異なります。
  例えば初対面や職場での硬さは通常の範囲内である一方、友人や恋愛の場面で同程度の
  硬さが続く場合は距離が縮まっていない兆候かもしれません。場面を踏まえた上で
  flow・other_reaction・relationship_distanceを解釈してください。
- プロソディ感情スコアが提供されている場合、各パラメータには値域が付記されています。
  値域に対する相対的な高さ・低さで判断してください（例：値域0〜30のパラメータが
  25なら高い、値域0〜100のパラメータが25なら中程度）。
- 直前のラウンドの分析結果が提供されている場合、それは参考情報であり今回の判定を
  上書きする根拠にはしないでください。relationship_distanceは前回の値に引きずられず、
  あくまで今回の文字起こし・プロソディから判断した上で、前回との変化があれば
  flowやother_reactionの記述の中で「前回よりも〜」のように触れてください。
- flow（会話の流れ）、other_reaction（相手の反応）: あなたの解釈が入る項目です。
  「〜になっています」のような言い切りではなく、「〜ように見えます」等、推定である
  ことが伝わる言い回しにしてください。誤った断定は、実際にはそうでない状況を
  「そうだ」と思い込ませ、支援どころか利用者の不安を増幅しかねません。
- relationship_distance: 5段階のうち最も近いものを選んでください
  （distant/no_change/warming_up/getting_closer/opening_up）。
- suggestion_category/suggestion_text（次に話すと良いこと）: 断定ではなく提案・
  助言として書いてください。
- プロソディの感情スコアが提供されていない場合は、文字起こしの内容のみから
  判断し、その旨さらに慎重な推定表現を使ってください。
"""

_TOPIC_SYSTEM_PROMPT = """\
1ラウンド分の会話の文字起こしから、話されている話題を一言で抽出してください。
これは文字起こしからの客観的な抽出なので、断定的な言い方で構いません。
出力は必ずsubmit_topicツールで返してください。
"""

_TOPIC_TOOL = {
    "name": "submit_topic",
    "description": "会話の話題を一言で提出する",
    "input_schema": {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"],
    },
}

_REPORT_TOOL = {
    "name": "submit_conversation_report",
    "description": "1ラウンド分の会話分析レポート（話題を除く）を提出する",
    "input_schema": {
        "type": "object",
        "properties": {
            "flow": {"type": "string"},
            "other_reaction": {"type": "string"},
            "relationship_distance": {
                "type": "string",
                "enum": ["distant", "no_change", "warming_up", "getting_closer", "opening_up"],
            },
            "suggestion_category": {
                "type": "string",
                "enum": [
                    "ask_question",
                    "show_empathy",
                    "talk_about_self",
                    "change_topic",
                    "just_listen",
                ],
            },
            "suggestion_text": {"type": "string"},
        },
        "required": [
            "flow",
            "other_reaction",
            "relationship_distance",
            "suggestion_category",
            "suggestion_text",
        ],
    },
}

_STATEMENT_CHECK_SYSTEM_PROMPT = """\
あなたはASD等コミュニケーションに難がある方向けの発言チェック機能のアシスタント
です。ユーザーがこれから言おうとしている発言案を、場面や相手との関係性を踏まえて
判定してください。「大丈夫」という判定が実際には誤っていた場合、そのまま相手に
言ってしまい対人関係に悪影響が出うるため、確信が持てない場合は安全側（言い換えを
提案する側）に倒してください。判定結果は断定ではなく助言として伝えてください。
出力は必ずsubmit_statement_checkツールで返してください。
"""

_STATEMENT_CHECK_TOOL = {
    "name": "submit_statement_check",
    "description": "発言案の判定結果を提出する",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_safe": {"type": "boolean"},
            "feedback": {
                "type": "string",
                "description": "判定理由と、is_safeがfalseの場合は言い換え案",
            },
        },
        "required": ["is_safe", "feedback"],
    },
}

_SUMMARY_SYSTEM_PROMPT = """\
あなたはASD等コミュニケーションに難がある方向けの会話振り返り機能のアシスタント
です。1回の利用（複数ラウンドの会話）全体について、各ラウンドの分析結果（話題・
会話の流れ・相手の反応・関係性の距離感・提案）と気分入力を受け取り、それらを
統合して「今日の会話のまとめ」「うまくいったポイント」「次回へのアドバイス」を
含む箇条書きの要約を生成してください。この要約もAIの解釈が入るため、断定的な
言い切りではなく推定・助言として書いてください（§11.11と同じ方針）。
出力は必ずsubmit_summaryツールで返してください。
"""

_SUMMARY_TOOL = {
    "name": "submit_summary",
    "description": "会話全体の振り返り箇条書きを提出する",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary_bullets": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary_bullets"],
    },
}


class ClaudeClient:
    """§4.1/§7 — the one fully-confirmed, non-PoC-gated vendor in the
    analysis pipeline. Never receives audio directly (§3.2): only STT text
    + prosody scores (when available) + scene/mood context."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def extract_topic(self, *, transcript: str) -> str:
        """§11.6: the fast-returning half of the report — cheap Haiku 4.5
        call so the frontend has something to show well before the full
        Sonnet 5 report finishes."""
        response = await self._client.messages.create(
            model=MODEL_HAIKU_4_5,
            max_tokens=128,
            system=_TOPIC_SYSTEM_PROMPT,
            tools=[_TOPIC_TOOL],
            tool_choice={"type": "tool", "name": "submit_topic"},
            messages=[{"role": "user", "content": f"文字起こし:\n{transcript}"}],
        )
        data = _extract_tool_input(response, "submit_topic")
        return data["topic"]

    async def generate_conversation_report(
        self,
        *,
        transcript: str,
        prosody_scores: dict[str, float],
        scene: str,
        mood_context: str | None = None,
        previous_round_context: str | None = None,
    ) -> ConversationReport:
        user_content = (
            f"場面: {_SCENE_LABELS_JA.get(scene, scene)}\n"
            f"文字起こし:\n{transcript}\n\n"
            f"プロソディ感情スコア: {_format_prosody_scores(prosody_scores)}\n"
        )
        if previous_round_context:
            user_content += f"\n直前のラウンドの分析結果（参考情報。今回の判定はこのラウンドの内容を優先すること）: {previous_round_context}\n"
        if mood_context:
            user_content += f"\n参考情報（気分・体調の入力履歴）: {mood_context}\n"

        response = await self._client.messages.create(
            model=MODEL_SONNET_5,
            max_tokens=1024,
            system=_REPORT_SYSTEM_PROMPT,
            tools=[_REPORT_TOOL],
            tool_choice={"type": "tool", "name": "submit_conversation_report"},
            messages=[{"role": "user", "content": user_content}],
        )
        data = _extract_tool_input(response, "submit_conversation_report")
        return ConversationReport(**data)

    async def check_statement(
        self, *, statement_text: str, scene: str, relationship_context: str | None = None
    ) -> StatementCheckResult:
        user_content = f"場面: {_SCENE_LABELS_JA.get(scene, scene)}\n発言案: {statement_text}\n"
        if relationship_context:
            user_content += f"関係性の参考情報: {relationship_context}\n"

        response = await self._client.messages.create(
            model=MODEL_SONNET_5,
            max_tokens=512,
            system=_STATEMENT_CHECK_SYSTEM_PROMPT,
            tools=[_STATEMENT_CHECK_TOOL],
            tool_choice={"type": "tool", "name": "submit_statement_check"},
            messages=[{"role": "user", "content": user_content}],
        )
        data = _extract_tool_input(response, "submit_statement_check")
        return StatementCheckResult(**data)

    async def generate_summary(
        self, *, round_reports: list[str], mood_context: str | None = None
    ) -> SummaryResult:
        """`round_reports` is each round's already-generated report text
        (topic/flow/reaction/relationship/suggestion) — NOT the raw
        transcript. Raw transcripts are never persisted past processing
        (§8), so a summary produced after the fact can only draw on what
        was actually kept: the per-round Recording fields."""
        user_content = "\n---\n".join(f"ラウンド{i + 1}:\n{t}" for i, t in enumerate(round_reports))
        if mood_context:
            user_content += f"\n\n参考情報（気分・体調の入力）: {mood_context}\n"

        response = await self._client.messages.create(
            model=MODEL_SONNET_5,
            max_tokens=1024,
            system=_SUMMARY_SYSTEM_PROMPT,
            tools=[_SUMMARY_TOOL],
            tool_choice={"type": "tool", "name": "submit_summary"},
            messages=[{"role": "user", "content": user_content}],
        )
        data = _extract_tool_input(response, "submit_summary")
        return SummaryResult(**data)


def _extract_tool_input(response, tool_name: str) -> dict:
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise RuntimeError(f"Claude response did not include the expected {tool_name!r} tool call")
