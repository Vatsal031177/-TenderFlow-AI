
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
