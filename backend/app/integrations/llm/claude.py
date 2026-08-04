from dataclasses import dataclass

from anthropic import AsyncAnthropic

from app.core.config import get_settings

MODEL_SONNET_5 = "claude-sonnet-5"
MODEL_HAIKU_4_5 = "claude-haiku-4-5-20251001"


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
    ) -> ConversationReport:
        user_content = (
            f"場面: {scene}\n"
            f"文字起こし:\n{transcript}\n\n"
            f"プロソディ感情スコア: {prosody_scores if prosody_scores else '（利用不可）'}\n"
        )
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
        user_content = f"場面: {scene}\n発言案: {statement_text}\n"
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
