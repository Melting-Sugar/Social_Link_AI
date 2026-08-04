from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.statement_check import StatementCheckRequest, StatementCheckResponse
from app.services.statement_check_service import StatementCheckService

router = APIRouter(prefix="/api/statement-check", tags=["statement-check"])


@router.post("", response_model=StatementCheckResponse)
async def check_statement(
    payload: StatementCheckRequest, current_user: CurrentUser
) -> StatementCheckResponse:
    """B-①. §7③: audio-pipeline-independent, synchronous."""
    result = await StatementCheckService().check(
        statement_text=payload.statement_text,
        scene=payload.scene.value,
        relationship_context=payload.relationship_context,
    )
    return StatementCheckResponse(is_safe=result.is_safe, feedback=result.feedback)
