import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.temp_storage import delete_temp_file, save_upload_and_normalize
from app.integrations.speaker_id.factory import get_speaker_id_provider
from app.models.voice_profile import VoiceProfile
from app.repositories.voice_profile_repository import VoiceProfileRepository


class VoiceEnrollmentService:
    """§11.3 / §12.3. Runs synchronously within the request — unlike the
    full recording pipeline, this is a single ~10-20s clip and one local
    embedding-extraction step, not a multi-vendor chain, so it doesn't
    need the Celery job treatment §11.5 gives recordings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._voice_profiles = VoiceProfileRepository(session)
        self._speaker_id = get_speaker_id_provider()

    async def register(self, *, user_id: uuid.UUID, raw_bytes: bytes, filename: str) -> VoiceProfile:
        wav_path = await save_upload_and_normalize(raw_bytes, original_filename=filename)
        try:
            embedding = await self._speaker_id.extract_embedding(wav_path)
        finally:
            # §8: raw audio is never kept around past processing, including
            # for voice enrollment.
            delete_temp_file(wav_path)
        return await self._voice_profiles.upsert(user_id=user_id, embedding=embedding)

    async def get_status(self, user_id: uuid.UUID) -> bool:
        return await self._voice_profiles.get_by_user_id(user_id) is not None

    async def delete(self, user_id: uuid.UUID) -> bool:
        profile = await self._voice_profiles.get_by_user_id(user_id)
        if profile is None:
            return False
        await self._voice_profiles.delete(profile)
        return True
