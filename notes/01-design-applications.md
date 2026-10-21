---
id: d1
title: "Section 1: Design Applications"
weight: 14
---

# Section 1: Design Applications (14%)

**Objectives**

1. Design a prompt that elicits a specifically formatted response
2. Select model tasks to accomplish a given business requirement
3. Select chain components for a desired model input and output
4. Translate business use case goals into a description of the desired inputs and outputs for the AI pipeline
5. Define and order tools that gather knowledge or take actions for multi-stage reasoning
6. Determine how and when to use Agent Bricks (Knowledge Assistant, Multiagent Supervisor, Information Extraction) to solve problems

---

## 1.1 Prompts that produce a specific format

A prompt usually has these parts. Know their names, because the exam uses them:

| Part | Purpose | Example |
|---|---|---|
| **System prompt / instruction** | Role, rules, tone, constraints | "You are a support assistant for ACME. Answer only from the provided context." |
| **Context** | Retrieved documents, tool results, user profile | `Context: {{retrieved_chunks}}` |
| **Input / question** | The user's request | `Question: {{question}}` |
| **Output indicator / format spec** | Exactly what shape to return | "Return JSON with keys `sentiment` (positive\|negative\|neutral) and `reason`." |
| **Examples (few-shot)** | Show input → output pairs | 2-3 examples in the same format |

**Techniques that make the format reliable** (from most to least reliable):

1. **Structured outputs / JSON schema enforcement**: Databricks Foundation Model APIs support `response_format` with a JSON schema (OpenAI-compatible). In SQL, `ai_query(..., responseFormat => ...)`. This *constrains decoding* and is the strongest guarantee.
2. **Few-shot examples** showing the exact output format.
3. **Explicit format instructions + delimiters**: "Return only the JSON object. Do not include any explanation." Use delimiters (`###`, XML tags, triple quotes) to separate instructions from data.
4. **Post-processing / validation** in the chain: parse, validate (e.g. Pydantic), retry on failure.

Other prompt techniques you should recognize:

- **Zero-shot** (instructions only), **few-shot** (examples), **chain-of-thought** ("think step by step" or reasoning models), **role/persona prompting**, **prompt chaining** (output of one call → input of next).
- **Lower temperature** (e.g. 0-0.2) → more deterministic and better for extraction/formatting. Higher temperature → more creative.
- **Stop sequences and max_tokens** limit the response length and shape.
- Tell the model what to do when it can't answer: "If the answer is not in the context, say *I don't know*". This reduces hallucination.

```text
System: You are an assistant that classifies support tickets.
Return ONLY valid JSON matching: {"category": "billing|shipping|technical|other", "urgency": 1-5}

Example:
Ticket: "My card was charged twice for order 123"
{"category": "billing", "urgency": 4}

Ticket: """{{ticket_text}}"""
```

## 1.2 Selecting model tasks for a business requirement

Map the business need to an **NLP task category**, then pick models that are evaluated on that task.

| Business requirement | Task |
|---|---|
| Paragraph → one-sentence gist | **Summarization** |
| Route tickets to teams | **Text classification** (or zero-shot classification) |
| Pull names, dates, amounts from contracts | **Information / entity extraction (NER)** |
| Is a review positive or negative? | **Sentiment analysis** (classification) |
| Answer questions from company docs | **Question answering** + retrieval (**RAG**) |
| Find similar products/documents | **Embeddings + semantic similarity search** |
| Translate product descriptions | **Translation** (text2text generation) |
| Write marketing copy | **Text generation** |
| Turn a question into SQL | **Text-to-SQL** (e.g. Genie) |
| Read scanned invoices | **OCR / document parsing** → extraction |

Notes:
- **Decompose** complex requirements into tasks, e.g. "answer customer emails about orders" = classify intent → extract order id → look up order (tool) → generate reply.
- Prefer the **simplest model/task** that meets the requirement. A classifier or SQL function is cheaper than an LLM agent.
- On Databricks, many tasks have **AI Functions** for batch/SQL use: `ai_query`, `ai_summarize`, `ai_classify`, `ai_extract`, `ai_analyze_sentiment`, `ai_translate`, `ai_mask`, `ai_fix_grammar`, `ai_gen`, `ai_similarity`, `ai_parse_document`.

## 1.3 Chain components

A **chain** (or pipeline) is a sequence of components. Common components:

| Component | Role | Databricks / LangChain examples |
|---|---|---|
| Prompt template | Builds the model input from variables | MLflow Prompt Registry, `ChatPromptTemplate` |
| LLM / chat model | Generates output | Foundation Model APIs endpoint, `ChatDatabricks` |
| Embedding model | Text → vector | `databricks-gte-large-en`, `databricks-bge-large-en` |
| Retriever | Finds relevant chunks | Vector Search index, `VectorSearchRetrieverTool` |
| Re-ranker | Reorders retrieved results by relevance | Vector Search reranker, cross-encoder |
| Tools | Take actions / fetch data | Unity Catalog functions, MCP servers, Genie |
| Output parser | Converts raw text → structured output | `StrOutputParser`, JSON/Pydantic parsers |
| Memory / state | Keeps conversation or intermediate state | Lakebase (Postgres), checkpointers |
| Guardrails | Filter unsafe input/output | AI Gateway guardrails, custom checks |

**How to pick components:** start from the **desired input and output**.
- Input is free text and the answer must cite internal docs → you need a retriever plus an LLM with a prompt that asks for citations.
- Output must be JSON → structured output or an output parser.
- Answer depends on live per-customer data (order status) → a **tool** or **structured lookup** (SQL, feature/online table) instead of a vector store.
- Multi-turn chat → conversation history / memory.

## 1.4 Business goals → pipeline inputs/outputs

Before you design, write down:

1. **Users and channel**: who asks, and where (App, Slack, Teams, SQL, batch job)?
2. **Inputs**: what's in a request (free text, ids, files)? Which **key fields** must the user give (e.g. `account_id`, `transaction_id`)?
3. **Knowledge needed**: static docs (→ RAG), structured facts (→ tables/tools), real-time data (→ API/tool).
4. **Outputs**: format (text, JSON, SQL, a table row), length, citations, language.
5. **Constraints**: latency, cost, throughput (QPS), privacy/PII, licensing.
6. **Success metrics**: how quality is measured (correctness, groundedness, CSAT).

> Sample exam pattern: a chatbot answers billing questions well but fails on *expected delivery date*. Delivery dates are **structured, per-transaction facts**, so serve them from a table keyed on `transaction_id` (feature/online table, or a tool). Don't use a vector store of policies, and don't fine-tune.

**Batch vs. real-time:** if the requirement is "process all 2M support tickets nightly", it's a **batch** workload → `ai_query()` in SQL/Lakeflow jobs, not a real-time serving endpoint.

## 1.5 Tools and multi-stage reasoning (agents)

An **agent** is an LLM that decides which **tools** to call, in what order, until it can answer. This is the ReAct pattern: *Reason → Act (tool) → Observe → repeat*.

**Tool types**
- **Knowledge-gathering (read-only)**: vector search retriever, Genie (text-to-SQL), UC SQL function lookups, web search.
- **Action-taking (side effects)**: create a ticket, send an email, update a record. These need extra guardrails (confirmation, permissions, idempotency).

**On Databricks, tools usually are**
- **Unity Catalog functions** (SQL or Python): governed, discoverable, reusable across agents.
- **Agent code tools** (functions defined in the agent's code).
- **MCP servers**: managed (UC functions, Vector Search, Genie), external, or custom.

**Ordering tools**
- Put dependencies first: *identify the customer → fetch their orders → check shipment status → compose answer*.
- Gather knowledge **before** taking actions; **validate** before irreversible actions.
- Give each tool a **clear name, description, and typed parameters**. The LLM chooses tools by their descriptions.
- Keep the tool set **small and focused** per agent. If you have many domains, use a **multi-agent** design with a supervisor that routes to specialized agents.

```text
User: "Was my last order shipped and can I change the address?"
1. get_customer(email)              -> customer_id         (knowledge)
2. get_latest_order(customer_id)    -> order_id, status    (knowledge)
3. lookup_policy("address change")  -> policy chunk (RAG)  (knowledge)
4. if status == "processing": update_address(order_id, new_addr)  (action, after confirmation)
```

## 1.6 Agent Bricks: when to use which

**Agent Bricks** is Databricks' way to build agents for common tasks with little or no code. You describe the task and point at your data. Databricks then builds, evaluates and optimizes the agent, and deploys it to a serving endpoint.

| Agent Bricks type (exam name) | What it does | Use when | Inputs |
|---|---|---|---|
| **Knowledge Assistant** | Q&A chatbot over your documents, **with citations**. Uses an "instructed retriever" and improves with SME feedback and guidelines. | "Build a chatbot over our HR/policy/product PDFs quickly, with citations, minimal code" | UC volume files (pdf, docx, pptx, txt, md…), UC tables with text, or existing vector search indexes |
| **Multi-Agent Supervisor** (now "Supervisor Agent") | Coordinates several agents/tools and routes each request to the right one | "Combine a Genie space for sales data + a Knowledge Assistant for policies + a UC function" | Genie spaces, agent endpoints (incl. Knowledge Assistants), UC functions, MCP servers |
| **Information Extraction** | Turns unstructured docs into **structured fields** with a defined schema (built on `ai_extract`) | "Extract vendor, date, total from 50k invoices into a Delta table" | Documents/text in UC; you define a JSON schema |
| *(Custom LLM: summarization, classification, transformation)* | Domain-specific text transformation agent | Custom tasks with optimization | Example data |

**Decision rules**
- Q&A over unstructured docs, fast, low code → **Knowledge Assistant**.
- Several specialists (data + docs + actions) behind one interface → **Multi-Agent Supervisor**.
- Unstructured → structured fields at scale → **Information Extraction** (or `ai_extract` / `ai_query` with a response format in SQL).
- Natural-language questions over **structured tables** → **Genie space** (text-to-SQL). Use it on its own or as a sub-agent.
- Highly custom logic, special frameworks, fine-grained control over the chain → **custom agent** with Agent Framework (`ResponsesAgent`, LangGraph, OpenAI Agents SDK...).

**Feedback loop:** Agent Bricks agents improve when **SMEs label questions, give feedback and add guidelines**. Built-in evaluation creates a benchmark, and the agent is tuned against it.

> **Status (Oct 2026):** Knowledge Assistant and Supervisor Agent are now marked *legacy*. Genie Agents (no-code) or the Agent Bricks CLI (code-first) are recommended for new builds. The March 2026 exam still tests them under the names above.

---

### Quick self-check
- Can you name the 5 parts of a prompt and the strongest way to force JSON output?
- Given "summarize to one sentence", which task category?
- When is a Genie space the right sub-agent, and when is a vector index?
- Which Agent Bricks type turns PDFs into table rows?
