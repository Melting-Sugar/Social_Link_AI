from app.core.config import get_settings
from app.integrations.stt.amivoice import AmiVoiceProvider
from app.integrations.stt.azure_speech import AzureSpeechProvider
from app.integrations.stt.base import STTProvider


def get_stt_provider() -> STTProvider:
    """§6: vendor selection is a config switch, never a call-site branch.
    確定事項25-28 — AmiVoiceが既定（ESAS感情分析を1回の呼び出しで兼ねる）。
    Azureは実装を残したまま非アクティブ化（§12.3参照）。"""
    match get_settings().stt_provider:
        case "azure":
            return AzureSpeechProvider()
        case _:
            return AmiVoiceProvider()
