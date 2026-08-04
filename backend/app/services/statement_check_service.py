from app.integrations.llm.claude import ClaudeClient, StatementCheckResult


class StatementCheckService:
    """§7③ / §11.11: independent of the audio pipeline entirely — plain
    synchronous text-in, text-out. §11.11 flags this as the highest-stakes
    spot for the "AI推定" framing policy, since a wrong "safe to say"
    verdict directly shapes what the user says next; the prompt (see
    integrations/llm/claude.py) already leans toward caution when unsure."""

    def __init__(self) -> None:
        self._llm = ClaudeClient()

    async def check(
        self, *, statement_text: str, scene: str, relationship_context: str | None
    ) -> StatementCheckResult:
        return await self._llm.check_statement(
            statement_text=statement_text, scene=scene, relationship_context=relationship_context
        )
