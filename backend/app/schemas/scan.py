from pydantic import BaseModel


class ScanResponse(BaseModel):
    added: int