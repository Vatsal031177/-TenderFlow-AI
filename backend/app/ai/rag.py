from typing import List, Dict, Any
import networkx as nx
from elasticsearch import Elasticsearch
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.db.models import CatalogItem
from app.ai.gateway import gateway
from app.ai.observability import trace_step

ES_INDEX = "construction_catalog"


class ConstructionKnowledgeGraph:
    """Graph RAG layer capturing DIN norms & mandatory material dependencies."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self._build_default_graph()

    def _build_default_graph(self):
        # Nodes: SKUs and Norms
        edges = [
            ("SKU-DRYWALL-FR60", "SKU-SEALANT-FIRESTOP", {"relation": "REQUIRES_ACCESSORY", "note": "Fire-rated partition requires intumescent firestop sealant per DIN 4102-4"}),
            ("SKU-DRYWALL-FR60", "SKU-PROFILE-CW75", {"relation": "REQUIRES_SUBSTRUCTURE", "note": "Requires galvanized CW75 stud profiles"}),
            ("SKU-DRYWALL-FR60", "NORM-DIN-4102", {"relation": "COMPLIES_WITH", "note": "Fire resistance class F90 / EI90"}),
            ("SKU-INSUL-MINWOOL-100", "SKU-VAPOR-BARRIER", {"relation": "REQUIRES_ACCESSORY", "note": "Mineral wool insulation requires vapor retarder foil per DIN 4108"}),
            ("SKU-CONCRETE-C30", "NORM-EN-206", {"relation": "COMPLIES_WITH", "note": "Exposure class XC4 concrete specification"}),
            ("SKU-CONCRETE-C30", "SKU-REBAR-B500B", {"relation": "OFTEN_PAIRED_WITH", "note": "Verify reinforcement steel B500B coverage"}),
        ]
        for u, v, attrs in edges:
            self.graph.add_edge(u, v, **attrs)

    def get_dependencies(self, sku: str) -> List[Dict[str, str]]:
        if sku not in self.graph:
            return []
        deps = []
        for _, target, data in self.graph.out_edges(sku, data=True):
            deps.append({
                "target": target,
                "relation": data.get("relation", "RELATED"),
                "note": data.get("note", ""),
            })
        return deps


class HybridGraphRAG:
    def __init__(self):
        self.es = Elasticsearch(settings.elasticsearch_url)
        self.kg = ConstructionKnowledgeGraph()

    def ensure_index(self):
        if not self.es.indices.exists(index=ES_INDEX):
            self.es.indices.create(
                index=ES_INDEX,
                mappings={
                    "properties": {
                        "sku": {"type": "keyword"},
                        "name": {"type": "text"},
                        "category": {"type": "keyword"},
                        "din_standard": {"type": "text"},
                        "description": {"type": "text"},
                    }
                },
            )

    def index_catalog_item(self, item: CatalogItem):
        self.ensure_index()
        self.es.index(
            index=ES_INDEX,
            id=item.sku,
            document={
                "sku": item.sku,
                "name": item.name,
                "category": item.category,
                "din_standard": item.din_standard or "",
                "description": item.description,
            },
        )

    @trace_step(name="hybrid_graph_rag_search", run_type="retriever")
    def match_item(self, db: Session, query_text: str) -> Dict[str, Any]:
        # 1. Lexical Search via Elasticsearch (BM25)
        es_scores: Dict[str, float] = {}
        try:
            res = self.es.search(
                index=ES_INDEX,
                size=5,
                query={
                    "multi_match": {
                        "query": query_text,
                        "fields": ["name^3", "din_standard^2", "description", "sku^3"],
                    }
                },
            )
            hits = res["hits"]["hits"]
            max_score = hits[0]["_score"] if hits else 1.0
            for h in hits:
                es_scores[h["_source"]["sku"]] = (h["_score"] / max_score) if max_score else 0.0
        except Exception:
            pass

        # 2. Vector Search via PostgreSQL pgvector
        vec = gateway.embed(query_text)
        vec_str = "[" + ",".join(str(x) for x in vec) + "]"
        rows = db.execute(
            text(
                """
                SELECT sku, 1 - (embedding <=> CAST(:vec AS vector)) AS cosine_sim
                FROM catalog_items
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT 5
                """
            ),
            {"vec": vec_str},
        ).fetchall()

        vec_scores: Dict[str, float] = {r[0]: max(0.0, float(r[1])) for r in rows}

        # 3. Reciprocal / Weighted Score Fusion
        candidate_skus = set(es_scores.keys()) | set(vec_scores.keys())
        if not candidate_skus:
            return {"item": None, "confidence": 0.0, "source": "none", "graph_dependencies": []}

        best_sku = None
        best_score = -1.0
        for sku in candidate_skus:
            fused = 0.55 * es_scores.get(sku, 0.0) + 0.45 * vec_scores.get(sku, 0.0)
            if fused > best_score:
                best_score = fused
                best_sku = sku

        matched_item = db.query(CatalogItem).filter(CatalogItem.sku == best_sku).first()
        graph_deps = self.kg.get_dependencies(best_sku) if best_sku else []

        source = "hybrid_es_pgvector"
        if best_sku in es_scores and best_sku not in vec_scores:
            source = "elasticsearch_bm25"
        elif best_sku in vec_scores and best_sku not in es_scores:
            source = "pgvector"

        return {
            "item": matched_item,
            "confidence": round(min(best_score, 0.99), 3),
            "source": source,
            "graph_dependencies": graph_deps,
        }


rag_engine = HybridGraphRAG()
