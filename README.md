# TenderFlow AI — Agentic Construction Tendering & Quoting Workbench

An end-to-end AI-first quoting and Bill of Quantities (BoQ / *Leistungsverzeichnis*) processing platform built for construction inside-sales workflows.

It ingests unstructured tender text, extracts structured line items via an LLM Model Gateway, matches them against an internal product catalog using **3-way Hybrid + Graph RAG** (Elasticsearch BM25 + PostgreSQL `pgvector` + NetworkX knowledge graph), enforces deterministic pricing/compliance **guardrails**, and exposes a Next.js human-in-the-loop review workbench with **LangSmith** observability.

---

## Architecture

```mermaid
flowchart LR
    UI["Next.js 14 Workbench<br/>(TypeScript + Tailwind)"] -->|REST API| API["FastAPI Backend<br/>(Python 3.11)"]

    subgraph AI["Agentic Pipeline & Guardrails"]
        API --> Orch["Tender Orchestrator"]
        Orch --> GW["Model Gateway<br/>(OpenAI + Offline Fallback)"]
        Orch --> RAG["Hybrid + Graph RAG"]
        Orch --> Guard["Margin & Compliance<br/>Guardrails"]
        Orch -.->|"@traceable"| LS["LangSmith<br/>Observability"]
    end

    subgraph Data["Retrieval & Persistence"]
        RAG --> ES["Elasticsearch 8<br/>(BM25 Lexical / DIN Norms)"]
        RAG --> PGV["PostgreSQL + pgvector<br/>(Dense Vector Search)"]
        RAG --> KG["NetworkX Graph<br/>(Accessory & DIN Rules)"]
        Orch --> PG["PostgreSQL<br/>(Tenders & Quote Items)"]
    end

Key Engineering Decisions
Hybrid + Graph RAG (backend/app/ai/rag.py):
Elasticsearch (BM25) handles exact matches on construction SKU codes, DIN/EN norms (e.g., DIN 4102-4, C30/37 XC4), and technical terminology.
PostgreSQL pgvector handles semantic similarity when tender wording differs from internal catalog naming.
Weighted Score Fusion combines lexical (0.55) and semantic (0.45) signals.
Knowledge Graph (NetworkX) models material dependencies and compliance rules (e.g., SKU-DRYWALL-FR60 → REQUIRES_ACCESSORY → SKU-SEALANT-FIRESTOP & SKU-PROFILE-CW75).
Deterministic Guardrails (backend/app/ai/orchestrator.py):
Flags line items falling below MIN_MARGIN_PERCENT (default 18.0%).
Flags low-confidence matches below CONFIDENCE_REVIEW_THRESHOLD (default 0.75) for human-in-the-loop review.
Cross-checks matched SKUs against the Knowledge Graph to warn sales reps if mandatory accessories or substructures are missing from the tender.
Model Gateway with Offline Fallback (backend/app/ai/gateway.py):
Uses OpenAI (gpt-4o-mini + text-embedding-3-small) when OPENAI_API_KEY is configured.
Gracefully falls back to a deterministic regex BoQ parser and hashed 1536-dim embeddings when running offline without API keys—making local evaluation zero-friction.
Observability (backend/app/ai/observability.py):
Instrumented with LangSmith @traceable decorators across orchestration, RAG retrieval, and LLM gateway calls, storing a trace_id per tender.
Tech Stack
Frontend: TypeScript, Next.js 14 (App Router), React 18, Tailwind CSS
Backend: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0
Data & Search: PostgreSQL 16 (pgvector), Elasticsearch 8.13, NetworkX
AI & Observability: OpenAI SDK, LangSmith
Infrastructure: Docker Compose, Terraform (AWS VPC, RDS, OpenSearch, EKS), Kubernetes (Deployment + HPA)
Quick Start (Local)
1. Configure Environment
Bash
cp .env.example .env
(Optional) Add your OPENAI_API_KEY and LANGCHAIN_API_KEY to .env. If left blank, the app runs using the built-in deterministic fallback mode.
2. Boot the Stack
Bash
docker compose up --build
Once healthy, the backend automatically initializes the pgvector extension, creates tables, and seeds sample construction catalog items (backend/app/seed.py) into both PostgreSQL and Elasticsearch.
3. Access Services
Service	URL
Frontend Workbench	http://localhost:3000
Backend API Docs (Swagger)	http://localhost:8000/docs
Health Check	http://localhost:8000/health
Elasticsearch	http://localhost:9200
PostgreSQL	localhost:5432
Walkthrough: Testing the Pipeline
Open http://localhost:3000.
Keep or modify the pre-loaded sample Leistungsverzeichnis (BoQ):
Pos 1.1: Fire-rated drywall gypsum board F90 DIN 4102-4 12.5mm 240 m2
Pos 1.2: Rockwool mineral wool thermal insulation 100mm WLG 035 240 m2
Pos 2.1: Structural ready-mix concrete C30/37 XC4 for floor slab 85 m3
Click Generate AI Quote.
Inspect the generated quote:
Graph RAG Alerts automatically flag missing accessories (SKU-SEALANT-FIRESTOP, SKU-PROFILE-CW75, SKU-VAPOR-BARRIER) that were omitted from the customer's BoQ.
Margin & Confidence Guardrails highlight items requiring inside-sales review.
Click Adjust on any line item to override unit pricing in PostgreSQL and recalculate quote totals and status (NEEDS_REVIEW → READY_TO_SEND).
API Endpoints
Method	Endpoint	Description
GET	/health	Service health check
GET	/api/tenders	List processed tenders and quote line items
POST	/api/tenders/process	Run extraction, Hybrid+Graph RAG, and guardrails on raw BoQ text
PATCH	/api/tenders/{tender_id}/items/{item_id}	Adjust line item unit price and recalculate tender totals
Infrastructure & Deployment (infra/)
Terraform (infra/terraform/main.tf): Provisions AWS VPC, private subnets, RDS PostgreSQL 16, OpenSearch 2.13, and EKS cluster in eu-central-1 (Frankfurt).
Kubernetes (infra/k8s/deployment.yaml): Defines the backend Deployment with readiness probes on /health, resource limits, secret injection (tenderflow-secrets), and a HorizontalPodAutoscaler (2–10 replicas at 70% CPU utilization).
Bash
# Validate Terraform configuration
cd infra/terraform
terraform init
terraform validate
Project Structure
Text
tenderflow-ai/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI app & REST endpoints
│       ├── config.py            # Pydantic settings
│       ├── seed.py              # Sample construction SKU seeder
│       ├── db/
│       │   ├── session.py       # SQLAlchemy + pgvector setup
│       │   └── models.py        # CatalogItem, Tender, QuoteLineItem
│       └── ai/
│           ├── gateway.py       # LLM & embedding gateway + offline fallback
│           ├── rag.py           # Elasticsearch + pgvector + NetworkX Graph RAG
│           ├── orchestrator.py  # Agentic workflow & guardrails
│           └── observability.py # LangSmith @traceable integration
├── frontend/
│   ├── Dockerfile
│   └── src/app/
│       ├── layout.tsx
│       └── page.tsx             # Quote ingestion & review workbench
└── infra/
    ├── terraform/main.tf        # AWS EKS, RDS, OpenSearch IaC
    └── k8s/deployment.yaml      # K8s Deployment & HPA
