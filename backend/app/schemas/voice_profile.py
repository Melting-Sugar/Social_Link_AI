from pydantic import BaseModel


class VoiceProfileStatusResponse(BaseModel):
    registered: bool
