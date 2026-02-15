from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from schemas import ChatRequest, WorksheetRequest, BrandIdentityRequest, CustomerProfileRequest, MarketingStrategyRequest
from services import chat_event_generator
from worksheet_service import worksheet_event_generator
from brand_identity_service import brand_identity_event_generator
from customer_profile_service import customer_profile_event_generator
from marketing_strategy_service import marketing_strategy_event_generator

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

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    return StreamingResponse(
        chat_event_generator(request.message, request.thread_id),
        media_type="text/event-stream"
    )

@app.post("/generate-worksheet")
async def generate_worksheet(request: WorksheetRequest):
    return StreamingResponse(
        worksheet_event_generator(
            business_description=request.businessDescription,
            target_audience=request.targetAudience,
            pain_points=request.painPoints,
            usp=request.uniqueSellingProposition,
            language=request.language,
        ),
        media_type="text/event-stream"
    )

@app.post("/generate-brand-identity")
async def generate_brand_identity(request: BrandIdentityRequest):
    return StreamingResponse(
        brand_identity_event_generator(
            worksheet_id=request.worksheetId,
            language=request.language,
        ),
        media_type="text/event-stream"
    )

@app.post("/generate-customer-profile")
async def generate_customer_profile(request: CustomerProfileRequest):
    return StreamingResponse(
        customer_profile_event_generator(
            brand_identity_id=request.brandIdentityId,
            language=request.language,
        ),
        media_type="text/event-stream"
    )


@app.post("/generate-marketing-strategy")
async def generate_marketing_strategy(request: MarketingStrategyRequest):
    return StreamingResponse(
        marketing_strategy_event_generator(
            worksheet_id=request.worksheetId,
            brand_identity_id=request.brandIdentityId,
            customer_profile_id=request.customerProfileId,
            goal=request.goal,
            language=request.language,
        ),
        media_type="text/event-stream"
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

