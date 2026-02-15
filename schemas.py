from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default_thread"

class ChatResponse(BaseModel):
    status: str

class WorksheetRequest(BaseModel):
    businessDescription: str = Field(..., min_length=20)
    targetAudience: str = Field(..., min_length=20)
    painPoints: str = Field(..., min_length=20)
    uniqueSellingProposition: str = Field(..., min_length=20)
    language: str = "Vietnamese"
