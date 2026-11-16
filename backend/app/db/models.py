from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.db.session import Base


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(128), nullable=False)
    unit = Column(String(32), nullable=False)
    cost_price = Column(Float, nullable=False)
    list_price = Column(Float, nullable=False)
    din_standard = Column(String(128), nullable=True)
    description = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    customer_name = Column(String(255), nullable=False)
    raw_text = Column(Text, nullable=False)
    total_net = Column(Float, default=0.0)
    estimated_margin_pct = Column(Float, default=0.0)
    status = Column(String(64), default="NEEDS_REVIEW")
    guardrail_alerts = Column(Text, default="[]")
    trace_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("QuoteLineItem", back_populates="tender", cascade="all, delete-orphan")


class QuoteLineItem(Base):
    __tablename__ = "quote_line_items"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("tenders.id"), nullable=False)
    position_no = Column(String(32), nullable=False)
    requested_description = Column(Text, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(32), nullable=False)
    matched_sku = Column(String(64), nullable=True)
    matched_name = Column(String(255), nullable=True)
    unit_price = Column(Float, default=0.0)
    line_total = Column(Float, default=0.0)
    margin_pct = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    retrieval_source = Column(String(64), default="hybrid")
    graph_dependencies = Column(Text, default="[]")
    needs_review = Column(Boolean, default=False)

    tender = relationship("Tender", back_populates="items")
