from pydantic import BaseModel


class ScanResponse(BaseModel):
    added: int


class ScanStartResponse(BaseModel):
    started: bool
    reason: str
