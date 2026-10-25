---
id: visual
title: Visual Guide (Diagrams)
weight: 0
---

# Visual guide

The architecture of the exam in pictures: where data flows, which components talk to each other, and what changes
between the options the exam asks you to choose from. Each diagram has the 2–3 facts that questions are usually built
on, and a link to the full notes. The diagrams use the **exam's (March 2026) names**, with today's names in brackets.

<div class="dg-legend"><span><i class="k-app"></i>users, apps, your agent</span><span><i class="k-data"></i>data: volumes, Delta tables, indexes</span><span><i class="k-model"></i>models &amp; endpoints</span><span><i class="k-tool"></i>tools, Genie, MCP, sub-agents</span><span><i class="k-gov"></i>guardrails, credentials, masking</span><span><i class="k-eval"></i>MLflow tracing &amp; evaluation</span></div>

On a phone, scroll a diagram sideways to see all of it.

---

## 1. The big picture

### 1.1 One application, six exam sections

[[diagram:lifecycle]]

- Sections 3 and 4 (develop, assemble and deploy) are **52%** of the exam.
- The loop matters: production failures become **evaluation data** for the next version ([§6.9](#/notes/d6)).

### 1.2 Which approach fits the requirement?

[[diagram:which-tool]]

- Structured data → **Genie**. Documents → **RAG / Knowledge Assistant**. Fields from documents → **Information Extraction**.
- No user waiting → **batch `ai_query()`**, never a real-time endpoint.
- Notes: [§1.6 Agent Bricks](#/notes/d1), [§4.6 batch inference](#/notes/d4).

---

## 2. Data preparation and retrieval (§2)

### 2.1 RAG ingestion pipeline

[[diagram:rag-ingest]]

- Order: **ingest → parse → clean → chunk → write Delta → enable CDF → Delta Sync index**.
- Clean and mask **before** chunking and embedding. Whatever reaches the index can be retrieved and leaked.
- Notes: [§2 pipeline and 2.4](#/notes/d2).

### 2.2 Chunking strategies

[[diagram:chunking]]

- Headings in the source → **structure-aware** chunking. Need precision *and* context → **parent-child**.
- To get fewer records, **increase chunk size and/or decrease overlap**. A smaller embedding dimension doesn't reduce the count.
- Notes: [§2.1](#/notes/d2), choose by evaluation in [§3.3](#/notes/d3).

### 2.3 Hybrid search and re-ranking

[[diagram:retrieval]]

- **Hybrid** helps with exact terms (SKUs, error codes, names). The **re-ranker** (cross-encoder) improves the order of the top results.
- Both add latency: if *latency is the critical metric*, they're the first things to turn off.
- Notes: [§2.7–2.8](#/notes/d2).

---

## 3. Agents and tools (§1, §3)

### 3.1 The tool-calling loop

[[diagram:agent-loop]]

- The LLM chooses tools by **name and description**, so write clear descriptions and typed parameters.
- **Knowledge tools before action tools.** Put confirmation and least privilege in front of anything with side effects.
- Notes: [§1.5](#/notes/d1).

### 3.2 Multi-agent supervisor

[[diagram:multi-agent]]

- Structured-data questions go to a **Genie space** sub-agent. Document questions go to a **Knowledge Assistant** or retriever.
- In code: `GenieAgent` in a LangGraph supervisor, logged with the `DatabricksGenieSpace` resource.
- Notes: [§3.13](#/notes/d3), [§1.6](#/notes/d1).

### 3.3 MCP server types

[[diagram:mcp]]

- **Managed** MCP for UC functions, Vector Search and Genie (zero maintenance). **External** through a UC connection with secrets. **Custom** as a Databricks App.
- Notes: [§4.10](#/notes/d4).

---

## 4. Assembling and deploying (§4)

### 4.1 The online RAG request

[[diagram:rag-query]]

- The agent endpoint **calls** the LLM endpoint. They're two different serving endpoints.
- Retrieval judges find the context through the **RETRIEVER span** in the trace.
- Notes: [§4.2, 4.5](#/notes/d4), tracing in [§6.3](#/notes/d6).

### 4.2 Vector Search index types

[[diagram:vs-index]]

- **Delta Sync** needs **Change Data Feed** and a primary key. Deletes in the table propagate to the index.
- **Direct Vector Access**: you `upsert()`/`delete()` yourself, with no automatic sync.
- Notes: [§4.4](#/notes/d4).

### 4.3 Configuring Vector Search

[[diagram:vs-config]]

- **Continuous sync only on Standard endpoints.** Storage-optimized = triggered sync, 1B+ vectors, a bit slower.
- Data updated nightly → **triggered** sync after the ETL job (cheapest).
- Notes: [§4.4 table](#/notes/d4).

### 4.4 From code to endpoint with MLflow

[[diagram:model-lifecycle]]

- Unity Catalog model names are **`catalog.schema.model`**, need a **signature**, and use **aliases** (not stages).
- `agents.deploy()` gives you the endpoint **plus** the Review App, inference tables and tracing.
- Notes: [§3.11](#/notes/d3), [§4.3](#/notes/d4), [§4.9 prompts](#/notes/d4).

### 4.5 How a deployed agent authenticates

[[diagram:endpoint-auth]]

- Default answer: **declare `resources=[...]`** when logging (automatic passthrough).
- "Each user must only see their own data" → **on-behalf-of-user**. Create user-scoped clients **inside `predict()`**.
- Notes: [§4.12](#/notes/d4).

### 4.6 Where GenAI assets live in Unity Catalog

[[diagram:uc-assets]]

- Same three-level namespace for files, tables, indexes, functions, models and prompts. Promote across **dev/prod catalogs**.
- Notes: [§4.3, 4.8](#/notes/d4).

---

## 5. Governance (§5)

### 5.1 Guardrails in layers

[[diagram:guardrails]]

- **Mask** when the app must keep working, and **block** when the request must stop.
- Indirect prompt injection arrives through **retrieved documents and tool outputs**, not the user's message.
- Notes: [§5.1–5.2](#/notes/d5), [§3.6](#/notes/d3).

---

## 6. Evaluation and monitoring (§6)

### 6.1 AI Gateway around your endpoints

[[diagram:gateway]]

- **Inference tables** = full request/response payloads. **Usage tracking** = token counts in `system.serving.endpoint_usage`.
- **Rate limits** per user, group, service principal or endpoint control both cost and abuse.
- Notes: [§6.7](#/notes/d6).

### 6.2 Evaluation and monitoring as one loop

[[diagram:eval-monitor]]

- Judges that need **ground truth**: `Correctness`, `RetrievalSufficiency`, `ToolCallCorrectness`. They only work offline.
- Production monitoring = **registered scorers** on a **sample** of live traces, plus user and SME feedback.
- Notes: [§6.3–6.6, 6.9](#/notes/d6), [§3.12](#/notes/d3).
