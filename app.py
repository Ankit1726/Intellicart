import warnings
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model" / "pipeline.pkl"

app = FastAPI(title="Customer Loyalty Intelligence API", version="1.0.0")
app.mount(
    "/static", StaticFiles(directory=BASE_DIR / "frontend" / "static"), name="static"
)
INDEX_HTML = BASE_DIR / "frontend" / "template" / "index.html"

PIPELINE = joblib.load(MODEL_PATH)

PCA_MODEL = PIPELINE.get("pca_model")
AGG_MODEL = PIPELINE.get("agg_model")

FEATURE_ORDER = [
    "Income",
    "Recency",
    "NumDealsPurchases",
    "NumWebPurchases",
    "NumCatalogPurchases",
    "NumStorePurchases",
    "NumWebVisitsMonth",
    "Complain",
    "Response",
    "Age",
    "Customer_TenureDay",
    "Total_Spent",
    "Total_Children",
    "Education_Graduate",
    "Education_Postgraduate",
    "Education_Undergraduate",
    "Living_Partner_Alone",
    "Living_Partner_Partner",
]

SEGMENTS = {
    3: {
        "id": 3,
        "name": "Champion",
        "headline": "Highly loyal — your best customer",
        "discount": 8,
        "offer": "VIP Loyalty Reward",
        "perks": [
            "Free express shipping",
            "Early access to new drops",
            "8% loyalty credit",
        ],
        "color": "#00E5A0",
    },
    2: {
        "id": 2,
        "name": "Loyal",
        "headline": "Steady, engaged, and reliable",
        "discount": 12,
        "offer": "Loyalty Appreciation Discount",
        "perks": ["12% off next order", "Priority support", "Birthday bonus"],
        "color": "#7C6CF6",
    },
    1: {
        "id": 1,
        "name": "At Risk",
        "headline": "Engagement is slipping — worth a nudge",
        "discount": 18,
        "offer": "We-Miss-You Win-Back Offer",
        "perks": [
            "18% win-back discount",
            "Free shipping this month",
            "Personalized picks",
        ],
        "color": "#FFB020",
    },
    0: {
        "id": 0,
        "name": "New / Low Engagement",
        "headline": "Early days — low purchase signal so far",
        "discount": 20,
        "offer": "Welcome Discount",
        "perks": [
            "20% first-order-style discount",
            "Guided onboarding",
            "Starter bundle",
        ],
        "color": "#FF5C7A",
    },
}


class CustomerInput(BaseModel):
    Income: float = Field(..., ge=0, description="Annual household income")
    Recency: int = Field(..., ge=0, le=365, description="Days since last purchase")
    NumDealsPurchases: int = Field(
        ..., ge=0, description="Purchases made with a discount/deal"
    )
    NumWebPurchases: int = Field(..., ge=0, description="Purchases made via website")
    NumCatalogPurchases: int = Field(
        ..., ge=0, description="Purchases made via catalog"
    )
    NumStorePurchases: int = Field(..., ge=0, description="Purchases made in-store")
    NumWebVisitsMonth: int = Field(..., ge=0, description="Website visits last month")
    Complain: int = Field(
        ..., ge=0, le=1, description="1 if complained in last 2 years"
    )
    Response: int = Field(
        ..., ge=0, le=1, description="1 if accepted last campaign offer"
    )
    Age: int = Field(..., ge=18, le=110)
    Customer_TenureDay: int = Field(
        ..., ge=0, description="Days since customer enrolled"
    )
    Total_Spent: float = Field(..., ge=0, description="Lifetime total spend")
    Total_Children: int = Field(..., ge=0, le=10)
    Education_Graduate: int = Field(0, ge=0, le=1)
    Education_Postgraduate: int = Field(0, ge=0, le=1)
    Education_Undergraduate: int = Field(0, ge=0, le=1)
    Living_Partner_Alone: int = Field(0, ge=0, le=1)
    Living_Partner_Partner: int = Field(0, ge=0, le=1)


class PredictionResult(BaseModel):
    cluster: int
    segment: str
    headline: str
    is_loyal: bool
    loyalty_score: float
    discount_percent: int
    offer: str
    perks: list[str]
    color: str
    pca_point: list[float]
    sub_scores: dict


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_loyalty_score(c: CustomerInput) -> dict:
    """Transparent RFM + engagement + tenure scoring, 0-1 scale."""
    frequency = (
        c.NumWebPurchases
        + c.NumCatalogPurchases
        + c.NumStorePurchases
        + c.NumDealsPurchases
    )

    recency_score = _clip01(1 - (c.Recency / 90))
    frequency_score = _clip01(frequency / 30)
    monetary_score = _clip01(c.Total_Spent / 2000)
    tenure_score = _clip01(c.Customer_TenureDay / 1500)
    engagement_score = _clip01(0.6 * c.Response + 0.4 * (1 - c.Complain))

    # Browsing without buying drags the score down slightly
    browse_efficiency = _clip01(frequency / (c.NumWebVisitsMonth + 1))
    engagement_score = _clip01(0.7 * engagement_score + 0.3 * browse_efficiency)

    overall = (
        0.30 * monetary_score
        + 0.20 * frequency_score
        + 0.20 * recency_score
        + 0.15 * tenure_score
        + 0.15 * engagement_score
    )

    return {
        "overall": round(overall, 4),
        "recency_score": round(recency_score, 3),
        "frequency_score": round(frequency_score, 3),
        "monetary_score": round(monetary_score, 3),
        "tenure_score": round(tenure_score, 3),
        "engagement_score": round(engagement_score, 3),
    }


def assign_segment(overall: float) -> int:
    if overall >= 0.70:
        return 3
    if overall >= 0.50:
        return 2
    if overall >= 0.30:
        return 1
    return 0


@app.get("/")
async def index():
    return FileResponse(INDEX_HTML)


@app.post("/api/predict", response_model=PredictionResult)
async def predict(customer: CustomerInput):
    row = np.array([[getattr(customer, f) for f in FEATURE_ORDER]], dtype=float)

    pca_point = [0.0, 0.0, 0.0]
    if PCA_MODEL is not None:
        try:
            transformed = PCA_MODEL.transform(row)[0]
            pca_point = [round(float(v), 4) for v in transformed[:3]]
            while len(pca_point) < 3:
                pca_point.append(0.0)
        except Exception:
            pca_point = [0.0, 0.0, 0.0]

    scores = compute_loyalty_score(customer)
    cluster_id = assign_segment(scores["overall"])
    segment = SEGMENTS[cluster_id]

    return PredictionResult(
        cluster=cluster_id,
        segment=segment["name"],
        headline=segment["headline"],
        is_loyal=cluster_id >= 2,
        loyalty_score=scores["overall"],
        discount_percent=segment["discount"],
        offer=segment["offer"],
        perks=segment["perks"],
        color=segment["color"],
        pca_point=pca_point,
        sub_scores=scores,
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "model_loaded": PIPELINE is not None}
