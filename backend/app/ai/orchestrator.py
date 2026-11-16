import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Tender, QuoteLineItem
from app.ai.gateway import gateway
from app.ai.rag import rag_engine
from app.ai.observability import trace_step, generate_trace_id


class TenderOrchestrator:
    """
    Agentic quoting workflow:
    1. Extract structured BoQ positions from raw tender text
    2. Match against Hybrid (ES + pgvector) + Graph RAG knowledge base
    3. Apply pricing, margin, and Graph-dependency guardrails
    4. Persist structured quote for human-in-the-loop review
    """

    @trace_step(name="orchestrate_tender_workflow", run_type="chain")
    def process_tender(
        self, db: Session, title: str, customer_name: str, raw_text: str
    ) -> Tender:
        trace_id = generate_trace_id()
        extracted_positions = gateway.extract_boq_positions(raw_text)

        tender = Tender(
            title=title,
            customer_name=customer_name,
            raw_text=raw_text,
            trace_id=trace_id,
        )
        db.add(tender)
        db.flush()

        total_net = 0.0
        total_cost = 0.0
        matched_skus = set()
        alerts: List[str] = []
        line_items: List[QuoteLineItem] = []

        for pos in extracted_positions:
            match = rag_engine.match_item(db, pos["description"])
            catalog_item = match["item"]
            confidence = match["confidence"]
            graph_deps = match["graph_dependencies"]

            if catalog_item:
                matched_skus.add(catalog_item.sku)
                unit_price = catalog_item.list_price
                cost_price = catalog_item.cost_price
                margin_pct = round(((unit_price - cost_price) / unit_price) * 100, 2)
                matched_sku = catalog_item.sku
                matched_name = catalog_item.name
            else:
                unit_price = 0.0
                cost_price = 0.0
                margin_pct = 0.0
                matched_sku = None
                matched_name = "UNMATCHED - MANUAL QUOTE REQUIRED"

            qty = float(pos["quantity"])
            line_total = round(qty * unit_price, 2)
            total_net += line_total
            total_cost += round(qty * cost_price, 2)

            needs_review = (
                catalog_item is None
                or confidence < settings.confidence_review_threshold
                or margin_pct < settings.min_margin_percent
            )

            if catalog_item and margin_pct < settings.min_margin_percent:
                alerts.append(
                    f"Pos {pos['position_no']} ({matched_sku}): Margin {margin_pct}% is below guardrail ({settings.min_margin_percent}%)."
                )
            if confidence < settings.confidence_review_threshold:
                alerts.append(
                    f"Pos {pos['position_no']}: Low match confidence ({confidence:.2f}). Human verification required."
                )

            li = QuoteLineItem(
                tender_id=tender.id,
                position_no=str(pos["position_no"]),
                requested_description=pos["description"],
                quantity=qty,
                unit=pos["unit"],
                matched_sku=matched_sku,
                matched_name=matched_name,
                unit_price=unit_price,
                line_total=line_total,
                margin_pct=margin_pct,
                confidence=confidence,
                retrieval_source=match["source"],
                graph_dependencies=json.dumps(graph_deps),
                needs_review=needs_review,
            )
            line_items.append(li)
            db.add(li)

        # Graph RAG Cross-Check Guardrail: detect missing mandatory accessories
        for li in line_items:
            deps = json.loads(li.graph_dependencies)
            for dep in deps:
                if dep["relation"] in ("REQUIRES_ACCESSORY", "REQUIRES_SUBSTRUCTURE"):
                    if dep["target"] not in matched_skus:
                        alerts.append(
                            f"Graph RAG Alert for Pos {li.position_no}: Missing {dep['target']} ({dep['note']})."
                        )

        overall_margin = (
            round(((total_net - total_cost) / total_net) * 100, 2) if total_net > 0 else 0.0
        )

        tender.total_net = round(total_net, 2)
        tender.estimated_margin_pct = overall_margin
        tender.guardrail_alerts = json.dumps(alerts)
        tender.status = "NEEDS_REVIEW" if alerts or any(i.needs_review for i in line_items) else "READY_TO_SEND"

        db.commit()
        db.refresh(tender)
        return tender


orchestrator = TenderOrchestrator()
