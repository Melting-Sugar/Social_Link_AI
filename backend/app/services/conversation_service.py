import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.claude import ClaudeClient
from app.models.conversation import Conversation
from app.models.enums import Scene
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.recording_repository import RecordingRepository


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._conversations = ConversationRepository(session)
        self._recordings = RecordingRepository(session)
        self._llm = ClaudeClient()

    async def create(self, *, user_id: uuid.UUID, scene: Scene) -> Conversation:
        return await self._conversations.create(
            user_id=user_id, scene=scene, started_at=datetime.now(UTC)
        )

    async def get_for_user(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        conversation = await self._conversations.get_by_id_for_user(conversation_id, user_id)
        if conversation is None:
            raise ValueError("会話が見つかりません。")
        return conversation

    async def end(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        conversation = await self.get_for_user(conversation_id, user_id)
        if conversation.ended_at is None:
            await self._conversations.mark_ended(conversation, datetime.now(UTC))
        return conversation

    async def generate_summary(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, *, mood_context: str | None = None
    ) -> list[str]:
        """A-⑤. §7④: built from each round's already-generated report
        fields, not raw transcripts (see claude.generate_summary). Also
        marks the conversation ended — reaching A-⑤ is the natural
        "conversation wrapped up" signal."""
        await self.end(conversation_id, user_id)
        recordings = await self._recordings.list_by_conversation(conversation_id)
        completed = [r for r in recordings if r.flow is not None]
        if not completed:
            raise ValueError("振り返りの元になる会話記録がまだありません。")

        round_reports = [
            f"話題: {r.topic}\n会話の流れ: {r.flow}\n相手の反応: {r.other_reaction}\n"
            f"関係性の距離感: {r.relationship_distance}\n次に話すと良いこと: {r.suggestion_text}"
            for r in completed
        ]
        result = await self._llm.generate_summary(round_reports=round_reports, mood_context=mood_context)
        return result.summary_bullets
