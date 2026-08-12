import asyncio
import time
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.integrations.stt.base import STTProvider, STTResult, STTSegment

_SUBMIT_URL = "https://acp-api-async.amivoice.com/v1/recognitions"
_POLL_URL = "https://acp-api-async.amivoice.com/v1/recognitions/{session_id}"
_ENGINE = "-a-general"  # contracted plan: 会話_汎用 (確定事項25)

_POLL_INTERVAL_SECONDS = 2.0
# Generous: single-request latency tracks ~1x realtime (確定事項26), but
# queueing under concurrent load can add well over a minute (確定事項28,
# still unconfirmed with AmiVoice support) — timeout errs on the side of
# not killing a request that's merely queued.
_POLL_TIMEOUT_SECONDS = 600.0


class AmiVoiceProvider(STTProvider):
    """§12.3 確定事項25-28 — ESAS感情分析はAmiVoice自身の音声認識リクエスト
    にしか付けられない（単体では呼べない）ため、STTとプロソディを1回のAPI
    呼び出しで兼ねる。sentimentAnalysisの結果は生レスポンスのまま
    STTResult.raw_vendor_response に格納し、AnalysisServiceが話者ラベルの
    時間範囲と突き合わせて集計する。§3.3が前提としていた「話者ごとに音声
    クリップを切り出し個別のプロソディベンダーへ送る」設計は、AmiVoiceの
    場合そのステップ自体が不要になる。

    診断対象は自分/相手の2名（§12.1）のみのため、diarizationMinSpeaker/
    MaxSpeakerは2に固定。

    §8: 生音声は保存しない方針だが、AmiVoiceの非同期HTTPは既定でログ
    （音声データ＋認識結果）を保存する仕様（公式ドキュメント確認済み）。
    loggingOptOut=Trueを明示しないとベンダー側に残ってしまうため必須。
    """

    def __init__(self) -> None:
        self._api_key = get_settings().amivoice_api_key

    async def transcribe(self, audio_path: str) -> STTResult:
        async with httpx.AsyncClient(timeout=60.0) as client:
            session_id = await self._submit(client, audio_path)
            data = await self._poll_until_done(client, session_id)

        return STTResult(
            segments=_group_tokens_into_segments(data),
            full_transcript=data.get("text", ""),
            raw_vendor_response=data,
        )

    async def _submit(self, client: httpx.AsyncClient, audio_path: str) -> str:
        audio_bytes = await asyncio.to_thread(Path(audio_path).read_bytes)
        response = await client.post(
            _SUBMIT_URL,
            data={
                "u": self._api_key,
                "d": (
                    f"grammarFileNames={_ENGINE} speakerDiarization=True "
                    "diarizationMinSpeaker=2 diarizationMaxSpeaker=2 sentimentAnalysis=True "
                    "loggingOptOut=True"
                ),
            },
            files={"a": audio_bytes},
        )
        response.raise_for_status()
        payload = response.json()
        session_id = payload.get("sessionid")
        if not session_id:
            raise RuntimeError(f"AmiVoice submission failed: {payload}")
        return session_id

    async def _poll_until_done(self, client: httpx.AsyncClient, session_id: str) -> dict:
        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = _POLL_URL.format(session_id=session_id)

        while True:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            status = data.get("status")

            if status == "completed":
                return data
            if status == "error":
                raise RuntimeError(f"AmiVoice recognition failed: {data.get('message') or data}")
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"AmiVoice recognition timed out after {_POLL_TIMEOUT_SECONDS}s "
                    f"(session {session_id}, last status={status!r})"
                )
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)


def extract_prosody_scores(raw_response: dict, segments: list[STTSegment]) -> dict[str, float]:
    """§12.3 確定事項25 — AmiVoiceのsentiment_analysisは元の音声全体の
    タイムラインに沿ったセグメント配列で返るため、話者ごとの発話区間
    （segments）と時間的に重なるものだけを抜き出し、パラメータごとに
    平均してProsodyResult.scoresと同じ形（dict[str, float]）に集約する。
    """
    sentiment_segments = raw_response.get("sentiment_analysis", {}).get("segments", [])
    if not sentiment_segments or not segments:
        return {}

    overlapping = [
        s
        for s in sentiment_segments
        if any(s["starttime"] < seg.end_ms and s["endtime"] > seg.start_ms for seg in segments)
    ]
    if not overlapping:
        return {}

    keys = [k for k in overlapping[0] if k not in ("starttime", "endtime")]
    return {key: sum(s[key] for s in overlapping) / len(overlapping) for key in keys}


def _group_tokens_into_segments(data: dict) -> list[STTSegment]:
    """AmiVoiceは単語(token)単位で話者ラベルを返す。STTSegmentは発話単位な
    ので、連続する同一ラベルのトークンを1セグメントにまとめて変換する。"""
    tokens = [
        token
        for segment in data.get("segments", [])
        for result in segment.get("results", [])
        for token in result.get("tokens", [])
    ]

    segments: list[STTSegment] = []
    label: str | None = None
    text = ""
    start_ms = 0
    end_ms = 0
    for token in tokens:
        token_label = token.get("label") or "unknown"
        if token_label != label:
            if label is not None:
                segments.append(STTSegment(label, text, start_ms, end_ms))
            label = token_label
            text = ""
            start_ms = token["starttime"]
        text += token["written"]
        end_ms = token["endtime"]
    if label is not None:
        segments.append(STTSegment(label, text, start_ms, end_ms))
    return segments
