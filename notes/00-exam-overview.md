---
id: overview
title: Exam Overview & Naming Traps
weight: 0
---

# Exam overview

| Item | Detail |
|---|---|
| Exam | Databricks Certified **Generative AI Engineer Associate** |
| Version covered | Exam published **March 18, 2026** (guide updated March 18, 2026) |
| Scored questions | **45** multiple-choice and multiple-selection |
| Unscored questions | Up to 10 extra, not identified, time already included |
| Time | **90 minutes** (~2 min per question incl. unscored) |
| Delivery | Online proctored, no test aids |
| Fee / validity | USD 200 / 2 years (recertify by taking the current live exam) |
| Recommended experience | ~6 months hands-on with Databricks + the outline below |

> **Always re-check the official exam guide ~2 weeks before your exam date.** The guide on the certification page is the source of truth for the objectives.

## Section weights → approximate scored questions

| # | Section | Weight | ≈ Questions |
|---|---|---|---|
| 1 | Design Applications | 14% | 6 |
| 2 | Data Preparation | 14% | 6 |
| 3 | Application Development | **30%** | **14** |
| 4 | Assembling and Deploying Applications | **22%** | **10** |
| 5 | Governance | 8% | 4 |
| 6 | Evaluation and Monitoring | 12% | 5 |

Sections 3 + 4 are more than half of the exam. Spend most of your time on them, but don't skip
Governance: four questions can decide a pass.

## Recommended official training (from the exam guide)

- Instructor-led: *Generative AI Engineering with Databricks*
- Self-paced (Databricks Academy): *Building RAG Agents with Agent Bricks*, *Building Agentic Applications on Databricks*, *Agent Evaluation on Databricks*, *Deploying and Monitoring Agent Applications on Databricks*

## How exam questions are written

- Questions are **scenario-based**: "A Generative AI Engineer is building... Which approach...?"
- Look for the **constraint words**: *least amount of code*, *minimize maintenance*, *latency is most critical*, *cost over quality*, *must respect each user's permissions*, *preserve version history*. The right answer is the option that satisfies **every** stated constraint, and often the most "managed / native Databricks" one.
- Multiple-selection questions tell you how many to pick ("Which **TWO**..."). There is no partial credit to rely on.
- Distractors are often things that technically work but violate a constraint (e.g. embedding a token in a browser, fine-tuning to inject frequently changing facts, overwriting instead of versioning).

---

# Naming traps: exam names vs. current names (as of October 2026)

The exam was written in **March 2026**. Since then Databricks has renamed several products.
**The exam uses the March-2026 names**, but the documentation you read today uses the new
ones. Know both.

| Name used on the exam | Current name in docs (Oct 2026) | Notes |
|---|---|---|
| Mosaic AI Vector Search / Vector Search | **Databricks AI Search** | Renamed **June 1, 2026**. Same engine (HNSW ANN + L2), now also full-text-only indexes. SDK: legacy `databricks-vectorsearch` still works with a deprecation warning; new package `databricks-ai-search`. |
| AI Gateway (Mosaic AI Gateway) on serving endpoints | **Unity Gateway** (a.k.a. Unity AI Gateway); the old one is "legacy AI Gateway" | Unity Gateway GA **Aug 2026**. Governs models, MCP servers, agents and tools through Unity Catalog. Same core features: inference tables, usage tracking, rate limits, guardrails, fallbacks, traffic splitting. |
| Genie Spaces / Genie space | **Genie Agents** | Renamed **July 8, 2026**. The Genie *Conversation API* still exists. |
| Multiagent Supervisor / Multi-Agent Supervisor (Agent Bricks) | **Supervisor Agent** — now **legacy** | Marked legacy **Oct 12, 2026** together with Knowledge Assistant. Recommended now: Genie Agents (no-code) or Agent Bricks CLI (code-first). Still on the exam. |
| Knowledge Assistant (Agent Bricks) | Knowledge Assistant — now **legacy** | Same as above. Still on the exam. |
| Information Extraction (Agent Bricks) | Information Extraction (new UI version built on `ai_extract`); original version is "legacy" | |
| Databricks Assistant | **Genie Code** | Renamed March 2026. |
| Databricks Asset Bundles (DABs) | **Declarative Automation Bundles** | Renamed March 2026. Same `databricks.yml` concept for CI/CD. |
| Delta Sharing | **OpenSharing** | Renamed June 2026 (relevant for Marketplace / data sharing). |
| Mosaic AI Agent Framework + Model Serving deployment | Still documented; new code-first path = **Agent Bricks CLI → DurableAgentServer → Agent Runtime** | `ResponsesAgent` + `agents.deploy()` is what the exam tests. |
| MLflow `ChatAgent` / `ChatModel` | **`ResponsesAgent`** (recommended) | ChatAgent/ChatModel are legacy interfaces; still supported. |
| Agent Evaluation (`mlflow.evaluate(model_type="databricks-agent")`) | **MLflow 3 GenAI evaluation**: `mlflow.genai.evaluate()` with **scorers / LLM judges** | MLflow 2-style agent eval is legacy. The exam uses `mlflow.genai.evaluate()` wording. |
| Lakehouse Monitoring for agents | **Production monitoring** in MLflow 3 (registered scorers sampling live traces) — the exam calls it "Agent Monitoring" | |
| Workspace Model Registry | **Models in Unity Catalog** (`mlflow.set_registry_uri("databricks-uc")`, aliases instead of stages) | Stages (Staging/Production) are legacy; use **aliases** like `@champion`. |

**Exam strategy:** if you see an older name in an answer option, don't assume it's wrong for that
reason alone. The exam guide itself uses "Vector Search", "AI Gateway", "Genie Spaces" and "Multiagent Supervisor".
