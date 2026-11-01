---
id: today
title: "Today's Stack: What to Use When"
weight: 0
---

# Today's stack: what to use when

> **Read this page for real projects, not for exam answers.** The exam (March 2026 version) still tests Vector Search,
> AI Gateway, Genie spaces, Knowledge Assistant, Multi-Agent Supervisor and Agent Framework on Model Serving.
> This page maps those to what Databricks recommends **today** (checked against docs.databricks.com on
> **November 1, 2026**). Several pieces are still Beta, and that is marked where it applies.

[[diagram:today-stack]]

## The 30-second version

- **A business user wants answers from data or documents** → **Genie One** (chat), backed by **Genie Agents** that a data team curates.
- **A developer writes an agent in code** → **Agent Bricks CLI** (`agentbricks init → dev → deploy`). It runs on **Agent Runtime** with **DurableAgentServer**.
- **The agent needs models** → call them through **Unity Gateway** (one API for Databricks-hosted and external models).
- **The agent needs tools or data** → **MCP servers** (Databricks-provided, external or custom), **AI Search** for retrieval, **Databricks Sandbox** to run code it writes.
- **The agent needs to remember** → managed **agent sessions** (one conversation) and **agent memory** (across conversations), both on Lakebase.
- **A batch job over a table** → **AI Functions** (`ai_parse_document`, `ai_extract`, `ai_classify`, `ai_query`…). No agent needed.
- **Measure and improve quality** → **MLflow 3** (tracing, `mlflow.genai.evaluate()`, judges, monitoring, Prompt Registry). Mostly unchanged.
- **Govern and control cost** → **Unity Catalog** permissions, enforced by **Unity Gateway** (guardrails, rate limits, budgets, usage).
- **Run coding agents such as Claude Code or Codex under one governed setup** → **Omnigent** (Beta).

## Pick a path in four questions

1. **Is it a batch job over a table, with no conversation?** Use AI Functions in a scheduled job, and stop there.
2. **Do business users just need answers over governed data and documents?** Curate a **Genie Agent** and let them use **Genie One**. No code.
3. **Do you need custom logic, actions with side effects, several agents, or a specific framework?** Write it with the **Agent Bricks CLI**. It can still call Genie Agents as tools.
4. **Is the "agent" really a coding or knowledge-work assistant (Claude Code, Codex, Cursor) that a team should share and govern?** Use **Omnigent**, with **Databricks Sandbox** for execution and **Unity Gateway** for models.

---

## "I want to… → use…"

Each table has the same columns. **Today** is the current recommendation. **Not this** is the tempting older or wrong
choice. **On the exam** is the March 2026 name for the same job, the one to pick in an exam answer.

### Answer questions over data and documents (low-code)

| I want to… | Today | Not this | On the exam |
|---|---|---|---|
| Let business users ask data questions in plain language | **Genie One** | Building a custom chatbot | (closest: Genie space) |
| Give one domain trusted tables, metrics, sample queries and business rules | **Genie Agent** | A long system prompt with table docs | Genie space |
| Answer policy questions from documents, with citations | **Genie Agent** over the documents | Knowledge Assistant *(legacy)* | Knowledge Assistant |
| Offer one assistant over both tables and documents | **Genie Agent**. If several agents must be coordinated in code, use the **Agent Bricks CLI** | Supervisor Agent *(legacy)* | Multi-Agent Supervisor |
| Let another app or agent talk to a Genie Agent | **Genie Conversation API** (apps) or the **Genie One MCP server** (agents) | Copying Genie's SQL into prompts | Genie Conversation API / Genie MCP |

### Build and run your own agent (code-first)

| I want to… | Today | Not this | On the exam |
|---|---|---|---|
| Start a new agent project | `pip install databricks-agentbricks`, then `agentbricks init` (templates for LangGraph and the OpenAI Agents SDK) | Hand-writing a Model Serving deployment | Agent Framework + `ResponsesAgent` |
| Move an existing LangGraph / OpenAI Agents SDK agent | `agentbricks init --existing` (generates migration steps) | Rewriting it from scratch | Wrap in `ResponsesAgent`, log with MLflow |
| Run and test the agent locally | `agentbricks dev` | AI Playground for agent testing *(legacy for this)* | AI Playground |
| Deploy it | `agentbricks deploy` → **Agent Runtime** (managed compute on Databricks Apps) running **DurableAgentServer** | Model Serving for agents *(legacy)* | `agents.deploy()` to Model Serving |
| Keep long or interrupted runs alive | **DurableAgentServer** / **AgentKit** durable execution (crash recovery, background runs) | Retrying from the client | — |
| Call a deployed agent | The **invocation API** (`/api/invocations`) via CLI, REST or Python | — | Querying a serving endpoint |
| Give users a chat UI | The chat UI that comes with CLI projects, or a **Databricks App**, Slack or Teams | A static page with a token in it | Databricks Apps / Review App |
| Use a Genie Agent inside a custom agent | `agentbricks tools add genie-agent` | Querying its tables directly | `GenieAgent` / Genie MCP server |
| Let the agent run code it writes (e.g. analysis scripts) | **Databricks Sandbox** *(Beta)*, called as a tool | Running generated code on the agent's own compute | — |
| Write a cheap one-step LLM "agent" | **AI Functions** such as `ai_query` | A full agent deployment | `ai_query` |

### Coding agents and harnesses

| I want to… | Today | Notes |
|---|---|---|
| Define an agent once and switch between Claude Code, Codex, Cursor, Pi or your own harness | **Omnigent** *(Beta, open source)* | YAML definition; change one line to swap harness or model while tools, prompts, skills and policies stay the same |
| Govern what coding agents may do | **Omnigent** policies (built-in contextual policies, custom policies in CEL) | Custom Python policies aren't supported |
| Share one live agent session with teammates | **Omnigent** managed server on Databricks | Uses your workspace identity provider |
| Give coding agents governed model access and shared skills | **Unity Gateway** | Claude Code, Codex and others route their model calls through it |
| Get AI help while writing notebooks, pipelines and SQL | **Genie Code** (formerly Databricks Assistant) | For people, not for deploying agents |

### Models

| I want to… | Today | Not this | On the exam |
|---|---|---|---|
| Use frontier and open models behind one API, switchable without code changes | **Unity Gateway** (Foundation Model APIs, external providers, serving endpoints) | Hard-coded provider keys in code | AI Gateway + external model endpoints |
| Run an LLM over millions of rows | **AI Functions** (`ai_query` or a task-specific function) in one query | Looping over a real-time endpoint | `ai_query()` |
| Serve your own fine-tuned or custom model | **Model Serving** (still current for models) | — | Provisioned throughput / custom endpoint |
| Fall back to another model, split traffic, cap spend | **Unity Gateway** fallbacks, routing, rate limits, budgets | Client-side retry logic | AI Gateway fallbacks / traffic splitting |

### Retrieval

| I want to… | Today | Not this | On the exam |
|---|---|---|---|
| Semantic or hybrid search over chunks | **AI Search** (Delta Sync index, Databricks-computed embeddings) | A hand-rolled vector store | Vector Search |
| Keyword-only search | **AI Search** full-text: `query_type="FULL_TEXT"` or a full-text index *(both Beta)* | `LIKE` queries | — |
| Index over a billion vectors cheaply | Storage-optimized endpoint (≈250 ms extra latency) | Standard endpoint | Same |
| Retrieve from SQL or an agent | `vector_search()` in SQL, `ai_search()` *(Beta)*, or AI Search through MCP | Exporting chunks to the prompt | `vector_search()` / VS MCP |
| Write new code against it | Python package `databricks-ai-search` (`AISearchClient`). REST paths still say `/vector-search/` and are current | — | `databricks-vectorsearch` |

### Documents and extraction (batch)

| I want to… | Today | Not this | On the exam |
|---|---|---|---|
| Parse PDFs, Office files and scans | `ai_parse_document()` | Separate OCR and PDF libraries | `ai_parse_document` / pytesseract |
| Pull fields into a table | `ai_extract()`, or the **Information Extraction** UI built on it | Information Extraction *(legacy version)* | Information Extraction |
| Classify, mask PII, summarize, translate | `ai_classify`, `ai_mask`, `ai_summarize`, `ai_translate` | `ai_query` with a hand-written prompt | Same functions |
| Prepare documents for search | `ai_prep_search()` *(Beta)* | — | Manual chunking pipeline |

### Tools and MCP

The docs now call managed servers **Databricks-provided** and add external ones through the **MCPs UI**. The decision rule is unchanged.

| I want to… | Today | On the exam |
|---|---|---|
| Use Databricks data and tools without hosting anything | **Databricks-provided MCP servers**: Genie One MCP for natural-language data questions, Databricks SQL, and others | Managed MCP servers |
| Use a vendor's existing MCP server | **External MCP server**, registered with a UC connection | External MCP server |
| Turn your own REST API into tools | **Custom MCP server** from a Databricks Apps template | Custom MCP server on Databricks Apps |
| Expose governed business logic | **Unity Catalog functions** | UC functions as tools |

### Memory and state

| I want to… | Today | Not this | On the exam |
|---|---|---|---|
| Keep one conversation's history across turns | Managed **agent sessions** (Lakebase) | Re-sending the whole history from the client | LangGraph checkpointer on Lakebase |
| Remember facts across conversations | Managed **agent memory** *(Beta, Lakebase)* | Self-managed memory stores *(legacy)* | Lakebase store keyed by user |
| Store operational app data | **Lakebase** (Autoscaling is the current version) | Delta tables for per-request writes | Lakebase |

### Quality and observability (MLflow 3, mostly unchanged)

| I want to… | Use |
|---|---|
| See every step an agent took | **MLflow Tracing** |
| Test before a release | `mlflow.genai.evaluate()` with built-in judges, Guidelines, `make_judge()` judges and `@scorer` functions |
| Score live traffic | Register scorers and `.start()` them with a sampling rate |
| Collect expert feedback | Labeling sessions (queues of traces for review), plus the Review App for existing agents |
| Make a judge agree with your experts | Judge alignment (MemAlign) |
| Improve a prompt automatically | `optimize_prompts()` with GEPA *(seen in Databricks skill guides; check the official API before relying on it)* |
| Version and promote prompts | **Prompt Registry** with aliases |

### Governance and cost

| I want to… | Today | On the exam |
|---|---|---|
| Control who may use which model, MCP server, function or connection | **Unity Catalog** privileges (all are securables), enforced by **Unity Gateway** | Endpoint permissions + UC |
| Block PII, prompt injection and unsafe content | **Unity Gateway service policies** (guardrails); they can allow, deny or require approval | AI Gateway guardrails |
| Cap usage and spend | **Unity Gateway** rate limits and **budgets with hard spend caps** | AI Gateway rate limits |
| See payloads and who called what | **Inference tables** (payloads) and **usage tables** (who, what, when) | Inference tables + `system.serving.endpoint_usage` |
| Make a tool respect each user's data permissions | Run the tool as the **requesting user** instead of the app's service principal | On-behalf-of-user auth |

---

## Exam answer → today's answer

| If the exam answer is… | …the current docs would say |
|---|---|
| Knowledge Assistant | Genie Agent over the documents |
| Multi-Agent Supervisor | Genie Agent (low-code), or a multi-agent system built with the Agent Bricks CLI |
| Genie space | Genie Agent (users reach it through Genie One) |
| Agent Framework: `ResponsesAgent` + `agents.deploy()` to Model Serving | Agent Bricks CLI → DurableAgentServer → Agent Runtime |
| AI Playground to prototype an agent | `agentbricks dev` |
| Mosaic AI Vector Search | AI Search (same engine, same REST paths) |
| AI Gateway on a serving endpoint | Unity Gateway (governs models, MCP servers and skills centrally) |
| Information Extraction (Agent Bricks) | Information Extraction on `ai_extract` (the original version is legacy) |
| Lakebase checkpointer / self-managed memory | Managed agent sessions and agent memory |
| Databricks Assistant | Genie Code |
| Asset Bundles | Declarative Automation Bundles (same `databricks.yml`) |

## What has not changed

- **RAG fundamentals:** chunking, overlap, metadata filters, hybrid search, reranking, the same embedding model for queries and documents.
- **MLflow 3:** tracing, `mlflow.genai.evaluate()`, which judges need ground truth, `@scorer`, production monitoring, Prompt Registry aliases.
- **Unity Catalog models:** aliases instead of stages.
- **AI Functions** for batch work, including `failOnError` and `responseFormat` in `ai_query`.
- **The MCP decision rule:** Databricks-provided → external → custom.
- **Security ideas:** least privilege, user-scoped access, confirmation before side effects, guardrails on input and output.

## Status and sources

Checked **November 1, 2026**. Statuses change quickly, so check the linked page before you rely on one.

| Piece | Status | Source |
|---|---|---|
| Knowledge Assistant, Supervisor Agent, agents on Model Serving, legacy agent servers | Legacy | [Legacy agent offerings](https://docs.databricks.com/aws/en/agents/legacy/) |
| Agent Bricks CLI, Agent Runtime, DurableAgentServer | Current recommendation | [Agent Bricks FAQ](https://docs.databricks.com/aws/en/agents/concepts/faq), [Deploy agents](https://docs.databricks.com/aws/en/agents/deploy/) |
| Genie One, Genie Agents | Current. User usage is free through Jan 31, 2027 | [Genie](https://docs.databricks.com/en/genie/) |
| Omnigent | Beta | [Omnigent on Databricks](https://docs.databricks.com/aws/en/omnigent/) |
| Databricks Sandbox | Beta | [Sandbox quickstart](https://docs.databricks.com/aws/en/compute/serverless/sandbox-quickstart) |
| Agent memory and sessions | Beta | [Managed agent memory](https://docs.databricks.com/gcp/en/agents/agent-memory/managed-memory) |
| Unity Gateway | Current; some pages still label service policies Beta | [Unity Gateway](https://docs.databricks.com/aws/en/unity-gateway/), [AI governance](https://docs.databricks.com/aws/en/ai-gateway/ai-governance) |
| AI Search | Current; full-text search Beta | [AI Search](https://docs.databricks.com/aws/en/vector-search/vector-search) |
| AI Functions | Mostly GA; `ai_prep_search`, `ai_search` Beta | [AI Functions](https://docs.databricks.com/aws/en/large-language-models/ai-functions) |
| MCP servers | Current | [MCP on Databricks](https://docs.databricks.com/aws/en/generative-ai/mcp/) |
