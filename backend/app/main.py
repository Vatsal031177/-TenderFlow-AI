import json
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import init_db, get_db, SessionLocal
from app.db.models import Tender, QuoteLineItem
from app.seed import seed_catalog
from app.ai.orchestrator import orchestrator

app = FastAPI(title="TenderFlow AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        seed_catalog(db)
    finally:
        db.close()


class ProcessTenderRequest(BaseModel):
    title: str
    customer_name: str
    raw_text: str


class UpdateLineItemRequest(BaseModel):
    unit_price: float


class QuoteItemResponse(BaseModel):
    id: int
    position_no: str
    requested_description: str
    quantity: float
    unit: str
    matched_sku: Optional[str]
    matched_name: Optional[str]
    unit_price: float
    line_total: float
    margin_pct: float
    confidence: float
    retrieval_source: str
    graph_dependencies: List[dict]
    needs_review: bool


class TenderResponse(BaseModel):
    id: int
    title: str
    customer_name: str
    total_net: float
    estimated_margin_pct: float
    status: str
    guardrail_alerts: List[str]
    trace_id: Optional[str]
    items: List[QuoteItemResponse]


def serialize_tender(tender: Tender) -> TenderResponse:
    return TenderResponse(
        id=tender.id,
        title=tender.title,
        customer_name=tender.customer_name,
        total_net=tender.total_net,
        estimated_margin_pct=tender.estimated_margin_pct,
        status=tender.status,
        guardrail_alerts=json.loads(tender.guardrail_alerts or "[]"),
        trace_id=tender.trace_id,
        items=[
            QuoteItemResponse(
                id=i.id,
                position_no=i.position_no,
                requested_description=i.requested_description,
                quantity=i.quantity,
                unit=i.unit,
                matched_sku=i.matched_sku,
                matched_name=i.matched_name,
                unit_price=i.unit_price,
                line_total=i.line_total,
                margin_pct=i.margin_pct,
                confidence=i.confidence,
                retrieval_source=i.retrieval_source,
                graph_dependencies=json.loads(i.graph_dependencies or "[]"),
                needs_review=i.needs_review,
            )
            for i in tender.items
        ],
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/tenders", response_model=List[TenderResponse])
def list_tenders(db: Session = Depends(get_db)):
    tenders = db.query(Tender).order_by(Tender.created_at.desc()).all()
    return [serialize_tender(t) for t in tenders]


@app.post("/api/tenders/process", response_model=TenderResponse)
def process_tender(payload: ProcessTenderRequest, db: Session = Depends(get_db)):
    tender = orchestrator.process_tender(
        db=db,
        title=payload.title,
        customer_name=payload.customer_name,
        raw_text=payload.raw_text,
    )
    return serialize_tender(tender)


@app.patch("/api/tenders/{tender_id}/items/{item_id}", response_model=TenderResponse)
def update_line_item(
    tender_id: int,
    item_id: int,
    payload: UpdateLineItemRequest,
    db: Session = Depends(get_db),
):
    item = (
        db.query(QuoteLineItem)
        .filter(QuoteLineItem.id == item_id, QuoteLineItem.tender_id == tender_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found")

    item.unit_price = payload.unit_price
    item.line_total = round(item.quantity * payload.unit_price, 2)
    item.needs_review = False

    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    tender.total_net = round(sum(i.line_total for i in tender.items), 2)
    if not any(i.needs_review for i in tender.items):
        tender.status = "READY_TO_SEND"

    db.commit()
    db.refresh(tender)
    return serialize_tender(tender)
