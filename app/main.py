from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.models.schemas import (
    ChatRequest, WorksheetRequest, BrandIdentityRequest, 
    CustomerProfileRequest, MarketingStrategyRequest,
    MasterContentGenerationRequest, PlatformVariantGenerationRequest,
    BatchGenerationRequest, ContentBriefsGenerationRequest
)
from app.services.chat import chat_event_generator
from app.services.worksheet import worksheet_event_generator
from app.services.brand import brand_identity_event_generator
from app.services.customer import customer_profile_event_generator
from app.services.strategy import marketing_strategy_event_generator
from app.services.master_content import master_content_event_generator
from app.services.variant_generator import platform_variants_event_generator
from app.services.batch_generator import batch_generate_event_stream
from app.services.content_briefs import content_briefs_event_generator

# Load environment variables
load_dotenv()

app = FastAPI(title="Marketing Agent API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_auth_token(raw_request: Request) -> str:
    """Extract bearer token from Authorization header."""
    auth = raw_request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return ""


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        chat_event_generator(request.message, request.thread_id),
        media_type="text/event-stream"
    )

@app.post("/generate-worksheet")
async def generate_worksheet(request: WorksheetRequest, raw_request: Request):
    auth_token = _extract_auth_token(raw_request)
    return StreamingResponse(
        worksheet_event_generator(
            brand_ids=request.brandIds,
            customer_ids=request.customerIds,
            language=request.language,
            auth_token=auth_token,
        ),
        media_type="text/event-stream"
    )

@app.post("/generate-brand-identity")
async def generate_brand_identity(request: BrandIdentityRequest, raw_request: Request):
    auth_token = _extract_auth_token(raw_request)
    return StreamingResponse(
        brand_identity_event_generator(
            worksheet_id=request.worksheetId,
            language=request.language,
            auth_token=auth_token,
        ),
        media_type="text/event-stream"
    )

@app.post("/generate-customer-profile")
async def generate_customer_profile(request: CustomerProfileRequest, raw_request: Request):
    auth_token = _extract_auth_token(raw_request)
    return StreamingResponse(
        customer_profile_event_generator(
            brand_identity_id=request.brandIdentityId,
            language=request.language,
            auth_token=auth_token,
        ),
        media_type="text/event-stream"
    )


@app.post("/generate-marketing-strategy")
async def generate_marketing_strategy(request: MarketingStrategyRequest, raw_request: Request):
    auth_token = _extract_auth_token(raw_request)
    return StreamingResponse(
        marketing_strategy_event_generator(
            worksheet_id=request.worksheetId,
            campaign_type=request.campaignType,
            product_id=request.productId,
            goal=request.goal,
            language=request.language,
            auth_token=auth_token,
        ),
        media_type="text/event-stream"
    )


@app.post("/generate-master-content")
async def generate_master_content(request: MasterContentGenerationRequest, raw_request: Request):
    auth_token = _extract_auth_token(raw_request)
    return StreamingResponse(
        master_content_event_generator(
            campaign_id=request.campaignId,
            workspace_id=request.workspaceId,
            language=request.languagePreference,
            auth_token=auth_token,
        ),
        media_type="text/event-stream"
    )


@app.post("/generate-platform-variants/{master_content_id}")
async def generate_platform_variants(master_content_id: str, request: PlatformVariantGenerationRequest, raw_request: Request):
    auth_token = _extract_auth_token(raw_request)
    return StreamingResponse(
        platform_variants_event_generator(
            master_content_id=master_content_id,
            platforms=request.platforms,
            workspace_id=request.workspaceId,
            language=request.languagePreference,
            auth_token=auth_token,
        ),
        media_type="text/event-stream"
    )


@app.post("/batch-generate-posts")
async def batch_generate_posts(request: BatchGenerationRequest, raw_request: Request):
    auth_token = _extract_auth_token(raw_request)
    return StreamingResponse(
        batch_generate_event_stream(
            campaign_id=request.campaignId,
            workspace_id=request.workspaceId,
            language=request.language,
            platforms=request.platforms,
            num_masters=request.numMasters,
            auth_token=auth_token,
        ),
        media_type="text/event-stream"
    )


@app.post("/generate-content-briefs")
async def generate_content_briefs(request: ContentBriefsGenerationRequest, raw_request: Request):
    auth_token = _extract_auth_token(raw_request)
    return StreamingResponse(
        content_briefs_event_generator(
            campaign_id=request.campaignId,
            workspace_id=request.workspaceId,
            language=request.language,
            angles_per_stage=request.anglesPerStage,
            auth_token=auth_token,
        ),
        media_type="text/event-stream"
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

