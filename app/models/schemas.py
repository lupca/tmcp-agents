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

class BrandIdentityRequest(BaseModel):
    worksheetId: str = Field(..., min_length=1)
    language: str = "Vietnamese"

class CustomerProfileRequest(BaseModel):
    brandIdentityId: str = Field(..., min_length=1)
    language: str = "Vietnamese"


class MarketingStrategyRequest(BaseModel):
    worksheetId: str = Field(..., min_length=1)
    brandIdentityId: str = Field(..., min_length=1)
    customerProfileId: str = Field(..., min_length=1)
    goal: str = ""
    language: str = "Vietnamese"


class MasterContentGenerationRequest(BaseModel):
    campaignId: str = Field(..., min_length=1, description="ID of the marketing campaign")
    languagePreference: str = "Vietnamese"
    workspaceId: str = Field(..., min_length=1, description="Workspace ID for context isolation")


class PlatformVariantGenerationRequest(BaseModel):
    platforms: list[str] = Field(..., min_items=1, description="List of platform codes (e.g., 'facebook', 'instagram', 'linkedin', 'twitter', 'tiktok', 'youtube', 'blog', 'email')")
    languagePreference: str = "Vietnamese"
    workspaceId: str = Field(..., min_length=1, description="Workspace ID for context isolation")
