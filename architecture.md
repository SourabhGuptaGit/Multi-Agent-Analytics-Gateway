# Multi-Agent Analytics Gateway (MAAG)
## Technical Architecture & System Design Documentation  
**Version:** 1.0  
**Document Type:** Enterprise Architecture Specification  
**Owner:** MAAG Engineering  
**Status:** Stable

---

# 1. Introduction

This document provides a formal architectural description of the **Multi-Agent Analytics Gateway (MAAG)** — an agent-driven analytics platform that converts **natural language queries into validated SQL**, executes them against a **DuckDB analytical engine**, and returns **accurate, structured insights**.

The system is built for:
- Analytical workloads  
- High-scale read operations on Parquet data lakes  
- Enterprise reliability  
- Component-level modularity  
- Extensible AI-driven governance  

This architecture document contains:

- System components  
- Data flow  
- Agent responsibilities  
- RAG subsystem design  
- FAISS metadata indexing  
- Orchestration logic  
- LLM integration  
- Scaling strategy for large datasets (50GB–100GB+)  
- Operational considerations  
- Deployment design patterns  

---

# 2. High-Level Architecture Overview

MAAG consists of five major subsystems:

1. **Ingestion & Data Processing Layer**  
2. **Metadata Extraction & Vector Index Layer (FAISS)**  
3. **Multi-Agent Orchestration Layer**  
4. **Execution Layer (DuckDB Engine)**  
5. **Serving Layer (FastAPI + Gradio UI)**

Each subsystem operates independently, enabling modular development and production-grade isolation.

---

# 3. System Architecture Diagram (ASCII)

```
                     +-----------------------------+
                     |      Gradio Frontend UI     |
                     +--------------+--------------+
                                    |
                                    v
                        HTTP: /api/ask | /api/sql
                                    |
                       +------------+-------------+
                       |      FastAPI Backend      |
                       +------------+-------------+
                                    |
                                    v
                      +-------------------------------+
                      |     Multi-Agent Orchestrator  |
                      +-------------------------------+
                        |       |           |         
     --------------------        |           ----------------------
     |                           |                                |
     v                           v                                v
+-----------+        +-----------------------+        +----------------------+
| Retrieval | -----> |    NL→SQL Agent       | -----> | SQL Validator Agent |
|  Agent    |        +-----------------------+        +----------------------+
+-----------+                                                 |
     |                                                       v
     |                                                +--------------+
     |                                                | SQL Executor |
     |                                                |   (DuckDB)   |
     |                                                +------+-------+
     |                                                       |
     |                                                       v
     |                                              +-----------------+
     |                                              | Response Agent  |
     |                                              +-----------------+
     |
     |
     v
+---------------------------------------------------------------+
|                     RAG Subsystem                             |
|   (FAISS Metadata Index + Schema Store + Embedding Models)    |
+---------------------------------------------------------------+
```

---

# 4. Component Breakdown

## 4.1 Ingestion Layer

**Responsibilities:**
- Load raw CSV files from `data/raw/`
- Clean & sanitize data (optional)
- Convert CSV → Parquet
- Register tables inside DuckDB
- Extract structural metadata (columns, datatypes, count)
- Serialize metadata as JSON
- Trigger FAISS index rebuild for metadata

**Key modules:**
- `ingestion.loader`
- `ingestion.converter`
- `db.metadata_store`
- `db.index_builder`
- `db.duckdb_client`

**Output:**
- Parquet files in `data/processed/`
- Metadata JSON in `data/metadata/`
- FAISS index in `data/metadata/faiss_index.bin`

---

## 4.2 Metadata Vector Index (FAISS)

MAAG does **not** embed raw data.  
Instead, it embeds **metadata descriptors**, ensuring:
- Lightweight storage  
- Fast search  
- Scalability to any dataset size

### Embedded Items:
- `table_name`
- `column_name`
- `datatype`
- `column_summary` (first rows or inferred stats)
- `semantic tags`

### Index Structure:
- Model dimension: 768 (MPNet)
- FAISS Index Type: FlatIP (can be upgraded)
- Mapping stored at: `faiss_index.bin.mapping.json`

### Query Workflow:
```
User Query → Embedding → FAISS → Top-K metadata hits → RAG context
```

---

## 4.3 Multi-Agent Orchestration Layer

The orchestrator coordinates all agents:

### Agents included:
1. **Retrieval Agent**  
2. **NL→SQL Agent**  
3. **SQL Validator Agent**  
4. **SQL Executor**  
5. **Response Agent**  
6. **Summarization Agent**

### High-level workflow:
```
1. RAG → contextual metadata
2. NL→SQL → draft SQL query
3. Validator → fix SQL, verify columns & tables
4. Executor → run query on DuckDB
5. Response Agent → human-friendly answer
```

### Design Principles:
- Each agent is stateless  
- Input/output contracts are strict  
- Failures cascade gracefully with safe fallback  
- LLM calls are centralized via `core.llm`  

---

## 4.4 Retrieval Agent

**Purpose:**  
Identify relevant tables/columns by performing vector search on metadata index.

**Input:**  
User query (NL)

**Output:**  
- Structured metadata  
- RAG prompt context  
- Ranked table/column relevance list

**Algorithm:**
1. Encode query using MPNet model  
2. Search FAISS for top-K metadata entries  
3. Consolidate into schema-centric structure  
4. Generate RAG-ready prompt

---

## 4.5 NL→SQL Agent

**Purpose:**  
Translate natural language → SQL.

**Input:**  
- User question  
- RAG metadata context

**Output:**  
- Draft SQL query  
- Schema structure for validator

**Prompts include:**
- Table names  
- Column names  
- Datatypes  
- Whether aggregation is required  
- RAG search results

**LLM Provider:**  
- OpenAI  
- Gemini  
- Ollama  
Configurable via `.env`.

---

## 4.6 SQL Validator Agent

**Purpose:**  
Ensure generated SQL is:
- Valid  
- Executable  
- Safe  
- Mapped to correct tables  

**Validations:**
- Table existence  
- Column existence  
- Alias normalization  
- Aggregation consistency  
- SELECT clause parsing  
- Forbidden keywords (DROP, INSERT, etc.)

**Output:**
- Valid SQL  
- List of fixes applied  
- Validation report  

---

## 4.7 SQL Executor (DuckDB)

**Purpose:**  
Execute validated SQL against DuckDB.

**Features:**
- Row-limit enforcement  
- Safe auto-LIMIT injection  
- Columnar vectorized execution  
- Direct Parquet access  
- Minimal memory footprint

**Advantages of DuckDB:**
- Scales to 100GB+ datasets  
- Zero external server required  
- Streaming-friendly  
- Supports complex analytical SQL

---

## 4.8 Response Agent

**Purpose:**  
Convert SQL + raw rows into:
- Natural language explanation  
- Markdown table  
- Summary text  

**Inputs:**
- User question  
- SQL generated  
- Rows returned  

**Output:**
- Final human-readable answer  

---

# 5. Detailed Sequence Flow

```
(1) User → MAAG API (/api/ask)
(2) RAG Retrieves contextual metadata
(3) NL→SQL Agent generates candidate SQL
(4) Validator Agent validates or auto-fixes SQL
(5) SQL Executor queries DuckDB
(6) Response Agent summarizes output
(7) API → Gradio returns final answer
```

---

# 6. RAG System Design

### Key Principles:
- Use metadata, not raw data
- Lightweight vector search
- Deterministic schema understanding
- Scalable to 500+ tables

### Context Construction:
Metadata hits → grouped into:
- Tables  
- Columns  
- Suggested constraints  
- Similar column names  
- Descriptive tags  

RAG Prompt Example:
```
Relevant Tables:
- international_sales (columns: sku, price, region)
- cloud_warehouse (columns: increff, shiprocket)

Recommended columns:
- international_sales.sku
```

---

# 7. LLM Integration Architecture

### Centralized LLM Wrapper (`core.llm`)
- Abstracts providers  
- Enforces max token safety  
- Supports:
  - ChatCompletion  
  - Gemini content generation  
  - Ollama local inference  

### Automatic model selection:
```
LLM_PROVIDER=openai | gemini | ollama
```

### Token Safety Logic:
- Pre-token estimation  
- Post-query row-size guard  
- Configurable override  

---

# 8. Database Architecture (DuckDB)

### Why DuckDB:
- In-process analytical engine
- Vectorized operations
- Ideal for columnar datasets
- No external services
- Instant Parquet reads

### Data Layout:
```
data/
  raw/        → original CSV files
  processed/  → Parquet tables
  metadata/   → schema JSON + FAISS index
  retail.duckdb → DB catalog
```

### Operational Behavior:
- Tables registered from Parquet  
- Lazy scanning enabled  
- Table caching optional  
- AP-level read-only mode supported  

---

# 9. Scaling Strategy (50GB–100GB+)

MAAG is designed for **big data scenarios**.

### 9.1 Storage Scaling
- Parquet partitioning
- Hive-style directory layout
- Predicate pushdown
- Statistics-based skipping

### 9.2 Compute Scaling
- DuckDB parallel query execution
- Columnar vectorization
- JVM-free Python integration

### 9.3 Metadata Scaling
- FAISS IVF-HNSW
- Product quantization (optional)
- Sharded index per schema
- Remote vector store option (Milvus, Pinecone)

### 9.4 Model Scaling
- Async batch LLM calls
- Local inference with Ollama
- GPU-backed inference for enterprise

### 9.5 API Scaling
- Horizontal scaling with Uvicorn/Gunicorn
- Reverse proxy (NGINX)
- Kubernetes deployment template

---

# 10. Reliability & Safety

### 10.1 Token Safety Guard
- Estimated token calculation  
- Hard-limit enforcement  
- Early request rejection  

### 10.2 Query Safety Guard
- No DDL/DML allowed  
- SELECT-only validator  
- LIMIT injection for large scans  

### 10.3 Runtime Safety
- Graceful agent fallback  
- Schema mismatch detection  
- Invalid SQL recovery  

---

# 11. Deployment Architecture

### Supported Deployment Targets:
- Docker  
- Docker Compose  
- AWS EC2  
- AWS ECS / Fargate  
- Azure Container Apps  
- Local machine development  

### Recommended Production Topology:
```
User
  |
Load Balancer (NGINX / ALB)
  |
FastAPI Containers — Horizontal scaling
  |
DuckDB (embedded) or DuckDB Server Mode
  |
S3/ADLS/GCS Parquet Storage
  |
Optional: External Vector DB (FAISS/Milvus/Pinecone)
```

---

# 12. Observability & Logging

### Logging Features:
- Structured logging
- File-based rotating logs
- Error-level and debug-level separation
- LLM token usage monitoring
- Agent lifecycle tracing

### Monitoring Stack (Optional):
- Prometheus exporters
- Grafana dashboards
- OpenTelemetry traces

---

# 13. Security Considerations

### Recommendations:
- API keys stored via environment variables
- No SQL write operations allowed
- Validate all user input
- Enable HTTPS at ingress level
- Use per-environment LLM API keys
- Enable rate limiting for public deployments

---

# 14. Future Enhancements

1. Multi-table join inference  
2. Natural language-to-dataset mapping  
3. Fine-grained access control  
4. Semantic relationship graph for tables  
5. Self-learning metadata enrichment  
6. On-the-fly schema drift detection  
7. Data quality and anomaly reporting  
8. Interactive dashboards (Streamlit/Gradio Pages)

---

# 15. Conclusion

This document outlines the complete technical architecture of the **Multi-Agent Analytics Gateway (MAAG)**.  
The system is engineered for:

- High scalability  
- Modular extensibility  
- Robust analytical performance  
- Enterprise reliability  
- LLM-driven intelligence  

MAAG provides a future-proof architecture capable of integrating additional agents, larger datasets, and hybrid cloud deployments—all while maintaining a clear separation of concerns and strong operational semantics.

---

# Appendix A — File Responsibilities

```
core/
  llm.py            → Unified LLM provider wrapper
  rag.py            → Metadata-based RAG context builder
  utils.py          → Logging, token checks, helper functions
  sql_executor.py   → Safe SQL execution with DuckDB
  
agents/
  controller.py     → Orchestrator for multi-agent pipeline
  nl_to_sql_agent.py → Natural language → SQL generator
  validation_agent.py → SQL correctness verification
  response_agent.py   → Final answer synthesis

db/
  index_builder.py  → FAISS index creation
  metadata_store.py → Metadata extraction into JSON
  duckdb_client.py  → DuckDB interface
```

---

# End of Document
