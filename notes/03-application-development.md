---
id: d3
title: "Section 3: Application Development"
weight: 30
---

# Section 3: Application Development (30%)

**Objectives**

1. Select Langchain/similar tools for use in a Generative AI application
2. Qualitatively assess responses to identify common issues such as quality and safety
3. Select chunking strategy based on model & retrieval evaluation
4. Augment a prompt with additional context from a user's input based on key fields, terms, and intents
5. Create a prompt that adjusts an LLM's response from a baseline to a desired output
6. Implement LLM guardrails to prevent negative outcomes
7. Select the best LLM based on the attributes of the application to be developed
8. Select an embedding model context length based on source documents, expected queries, and optimization strategy
9. Select a model from a model hub or marketplace for a task based on model metadata/model cards
10. Select the best model for a given task based on common metrics generated in experiments
11. Utilize MLflow and Agent Framework for developing agentic systems
12. Compare the evaluation and monitoring phases of the Gen AI application life cycle
13. Enable multi-agent systems to leverage Genie Spaces or conversational API to retrieve data

---

## 3.1 Frameworks and libraries

| Tool | What it's for | Databricks integration |
|---|---|---|
| **LangChain** | Chains, prompt templates, retrievers, tools, output parsers (LCEL: `prompt \| llm \| parser`) | `databricks-langchain`: `ChatDatabricks`, `DatabricksEmbeddings`, `DatabricksVectorSearch`, `VectorSearchRetrieverTool`, `UCFunctionToolkit`, `GenieAgent` |
| **LangGraph** | Stateful, graph-based **agents** and multi-agent workflows (nodes, edges, state, checkpointers) | Wrap in `ResponsesAgent`. Checkpointer can persist to Lakebase. |
| **LlamaIndex** | Data/indexing-centric RAG: loaders, node parsers, query engines | `mlflow.llama_index` flavor |
| **OpenAI Agents SDK** / **OpenAI client** | Agents with tools; OpenAI-compatible API | Foundation Model APIs are **OpenAI-compatible**. Use the `openai` client with workspace base URL / `WorkspaceClient().serving_endpoints.get_open_ai_client()` |
| **DSPy** | Programmatic prompt optimization ("compile" prompts from metrics) | MLflow flavor |
| **Hugging Face Transformers** | Open models, tokenizers, pipelines | `mlflow.transformers` flavor |
| **MLflow** | Tracing, evaluation, prompt registry, model packaging/registry | Native (Databricks-managed MLflow) |
| **unitycatalog-ai** | Define/use UC functions as agent tools across frameworks | `DatabricksFunctionClient` |
| **databricks-mcp** | Connect agents to MCP servers | `DatabricksMCPClient` |

**Selection hints:** a simple prompt → LLM → parser chain needs only LangChain LCEL or plain Python. Branching/looping tool use and multi-agent need LangGraph or the OpenAI Agents SDK. Heavy document indexing needs LlamaIndex. Whatever you choose, **wrap it in MLflow `ResponsesAgent`** to deploy with Agent Framework.

## 3.2 Qualitatively assessing responses

Common issues to recognize when reviewing outputs:

| Issue | Symptom | Typical fix |
|---|---|---|
| **Hallucination / ungrounded** | Confident facts not in the context | Better retrieval, "answer only from context", groundedness checks |
| **Irrelevant answer** | Doesn't address the question | Better prompt, query rewriting, retrieval relevance |
| **Incomplete** | Misses parts of a multi-part question | Larger k, better chunking, decomposition |
| **Wrong format / too long** | Not JSON, rambles | Format instructions, structured outputs, max_tokens |
| **Toxic / unsafe / biased** | Harmful, offensive content | Safety guardrails, Safety judge |
| **PII leakage** | Exposes personal data | Masking, PII guardrails |
| **Off-topic / jailbreak success** | Answers things outside scope | System prompt scope, input guardrails |
| **Stale information** | Outdated facts | Refresh index, filter by date |
| **Inconsistent tone/persona** | Violates brand voice | System prompt, guidelines judge |

Tools: **AI Playground** (side-by-side model comparison), **MLflow trace UI** (see every step), **Review App** (SMEs label responses), and LLM judges (`Safety`, `RelevanceToQuery`, `Guidelines`).

## 3.3 Choosing chunking from evaluation

You don't guess chunk size, you **measure** it:
1. Build an **evaluation dataset** (questions + expected facts/answers).
2. Create indexes with several chunking strategies (e.g. 256/512/1024 tokens, recursive vs. header-based).
3. Run `mlflow.genai.evaluate()` with retrieval judges (`RetrievalRelevance`, `RetrievalSufficiency`, `RetrievalGroundedness`) plus `Correctness`.
4. Pick the strategy with the best scores **subject to** cost/latency constraints, and make sure the chunk size fits the **embedding model's context window**.

## 3.4 Augmenting prompts from user input (key fields, terms, intents)

- **Extract key fields** from the user input (e.g. `order_id`, product name, date range) with an LLM or regex, then use them to **look up structured data** or as **metadata filters** for retrieval.
- **Detect intent** (billing vs. shipping vs. technical) → route to the right prompt template, tool or sub-agent.
- **Expand terms**: synonyms, acronyms ("PTO" → "paid time off"), product codes → names.
- **Inject context**: user profile (role, region, language), conversation history summary, retrieved chunks, tool results.

```python
template = """You are a support assistant.
Customer tier: {{tier}} | Region: {{region}}
Relevant policy excerpts:
{{context}}
Question: {{question}}
Answer using only the excerpts. Cite the policy title."""
```

## 3.5 Adjusting a response from baseline to desired output

Iterate on the prompt and **compare against the baseline** with an evaluation set:
- Add **explicit instructions** (tone, length, audience: "explain to a non-technical customer in 3 bullet points").
- Add **few-shot examples** of the desired output.
- Specify **format** (sections, JSON, markdown table).
- Add **constraints** ("do not mention competitors", "if unsure, ask a clarifying question").
- Use **role/persona** and **step-by-step** reasoning for complex tasks.
- Tune **temperature/max_tokens**.
- Version each change in the **MLflow Prompt Registry** and evaluate each version.
- If prompting isn't enough → better context (RAG), then **fine-tuning** as a last resort (for style/format/domain language, *not* for frequently changing facts).

## 3.6 LLM guardrails

Guardrails are controls on the **input** and **output** of the model:

| Layer | Examples |
|---|---|
| **Input guardrails** | Detect prompt injection/jailbreaks, block off-topic requests, **PII detection & masking** before the LLM, input length limits, allow-lists of intents |
| **Output guardrails** | **Safety / toxicity filters**, PII masking in responses, groundedness checks, format validation, block disallowed topics |
| **System-level** | System prompt with scope rules, least-privilege tool permissions, human approval for actions, **rate limits**, monitoring |

On Databricks:
- **AI Gateway guardrails** on serving endpoints: **safety filtering** (blocks unsafe content) and **PII detection** (block or mask), applied to requests and/or responses. (Now part of Unity Gateway "service policies".)
- **Llama Guard** or another safety classifier as a separate model/step in the chain.
- **`ai_mask()`** to mask PII in data; **Unity Catalog column masks / row filters** for data access.
- **Custom guardrail code** in the agent (e.g. a classification step before retrieval).
- **Evaluation and monitoring** with `Safety` and `Guidelines` judges.

## 3.7 Selecting the best LLM

Attributes to weigh:

| Attribute | Consider |
|---|---|
| **Task fit / quality** | Benchmarks for the task (reasoning, coding, summarization), your own eval results |
| **Context window** | Must fit system prompt + retrieved context + history + output |
| **Latency / throughput** | Smaller models are faster. Time-to-first-token for chat UX. |
| **Cost** | Price per token; pay-per-token vs. provisioned throughput |
| **Size / architecture** | Small (7-8B) vs. large (70B+), dense vs. **mixture-of-experts**, reasoning models |
| **Capabilities** | Tool/function calling, structured outputs, multilingual, vision |
| **License & governance** | Commercial use allowed? Data residency? Open vs. proprietary |
| **Deployment** | Available as Foundation Model API? Need fine-tuning? |

**Rule of thumb:** choose the **smallest/cheapest model that meets the quality bar** on your evaluation set. Use larger or reasoning models for complex multi-step reasoning or agent planning, and small models for classification/extraction/routing.

**Model serving options on Databricks:**
- **Foundation Model APIs, pay-per-token**: shared endpoints (e.g. `databricks-meta-llama-3-3-70b-instruct`, `databricks-claude-*`, `databricks-gte-large-en`). Fast to start, good for development and moderate traffic.
- **Foundation Model APIs, provisioned throughput**: dedicated capacity, guaranteed performance, for production/high volume and fine-tuned models.
- **External models**: OpenAI, Anthropic, Google, Bedrock etc., governed through a Databricks endpoint (credentials in secrets).
- **Custom models**: your own MLflow model / agent on a serving endpoint.

## 3.8 Embedding model context length

- The embedding model's **max tokens must be ≥ your chunk size**. Otherwise the text is **truncated** and the meaning is lost.
- **Larger context length / larger dimension** = bigger model, more storage, more latency and cost. Only pay for it if chunks or queries need it.
- If **cost/latency > quality** and chunks are ≤512 tokens → pick the **smallest model with context ≥ 512** (e.g. 512-context, 384-dim).
- Queries and documents must use the **same embedding model**.
- Long documents? Either chunk to fit a smaller model, or use a long-context embedding model (fewer, larger chunks).
- **Embedding dimension** affects storage and search speed. Higher dimensions often bring better quality at higher cost.

Databricks-hosted embedding models: `databricks-gte-large-en` (8192-token context, 1024 dims), `databricks-bge-large-en` (512-token context, 1024 dims), and `databricks-qwen3-embedding-0-6b`. Check the current list in the Serving page, because the model list changes.

## 3.9 Choosing from a model hub / marketplace via model cards

A **model card** tells you: intended use and **task**, **license** (commercial use?), training data, **context length**, size/parameters, languages, benchmarks/eval results, limitations and biases, and hardware needs.

Where: **Databricks Marketplace**, Unity Catalog `system.ai` schema (Databricks-provided models), **Hugging Face Hub**.

Pick by matching the card to requirements: task + language + license + context length + size (latency/cost). A model with a non-commercial license can't be used for a commercial product, however well it scores.

## 3.10 Choosing the best model from experiment metrics

| Metric | Use for |
|---|---|
| **Perplexity** | Language-model fit (lower = better) |
| **BLEU** | Translation (n-gram precision vs. reference) |
| **ROUGE** (ROUGE-1/2/L) | **Summarization** (n-gram recall vs. reference) |
| **Exact match / F1** | QA / extraction |
| **Accuracy / precision / recall / F1** | Classification |
| **Toxicity** | Safety |
| **Latency, tokens/sec, cost per request** | Operational |
| **LLM-judge scores** (correctness, groundedness, relevance, guidelines) | Modern GenAI quality |

Compare runs in **MLflow experiments** (evaluation runs side-by-side). Choose the model that meets the quality threshold at the best cost/latency.

## 3.11 MLflow and Agent Framework for agentic systems

**Mosaic AI Agent Framework** = tools to **author, log, evaluate, deploy and monitor** agents on Databricks, built on **MLflow 3**.

**Author** with MLflow `ResponsesAgent` (the recommended interface, compatible with the OpenAI Responses schema). It works with any framework underneath.

```python
# agent.py  (models-from-code)
import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
from databricks.sdk import WorkspaceClient

class SimpleAgent(ResponsesAgent):
    def __init__(self):
        self.client = WorkspaceClient().serving_endpoints.get_open_ai_client()

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        messages = [{"role": m.role, "content": m.content} for m in request.input]
        resp = self.client.chat.completions.create(
            model="databricks-meta-llama-3-3-70b-instruct", messages=messages)
        text = resp.choices[0].message.content
        return ResponsesAgentResponse(
            output=[self.create_text_output_item(text=text, id="msg_1")])

mlflow.openai.autolog()          # tracing
mlflow.models.set_model(SimpleAgent())
```

**Lifecycle with MLflow**
1. **Trace**: `mlflow.<flavor>.autolog()` or `@mlflow.trace`. Traces record every step (LLM calls, retrieval, tools) with inputs, outputs, latency and tokens.
2. **Log**: `mlflow.pyfunc.log_model(name="agent", python_model="agent.py", resources=[...], input_example=...)` (*models-from-code*: you log the code file, not a pickled object).
3. **Evaluate**: `mlflow.genai.evaluate(data, predict_fn, scorers)`.
4. **Register** to Unity Catalog: `mlflow.set_registry_uri("databricks-uc")` + `mlflow.register_model(uri, "catalog.schema.agent")`.
5. **Deploy**: `from databricks import agents; agents.deploy("catalog.schema.agent", version)`. This creates a serving endpoint, the **Review App** for feedback, and enables **inference tables** / monitoring.
6. **Monitor**: production monitoring with registered scorers on live traces.

**Legacy interfaces:** `ChatAgent`, `ChatModel`, MLflow 2 `mlflow.evaluate(model_type="databricks-agent")`. These are still supported, but use `ResponsesAgent` and `mlflow.genai` for new work.

## 3.12 Evaluation vs. monitoring

| | **Evaluation** (offline, pre-production) | **Monitoring** (online, production) |
|---|---|---|
| When | During development, before release, in CI | After deployment, continuously |
| Data | Curated **evaluation dataset** (can include **ground truth**/expectations) | **Live traffic** (traces/inference tables), usually **no ground truth** |
| Goal | Compare versions, catch regressions, choose models/prompts/chunking | Detect drift, quality drops, safety issues, latency/cost problems |
| Tools | `mlflow.genai.evaluate()`, scorers/judges, evaluation datasets, Review App labeling | Registered scorers with sampling (`.register().start()`), inference tables, AI Gateway usage tracking, dashboards/alerts |
| Judges | Can use ground-truth judges (`Correctness`, `RetrievalSufficiency`) | Mostly judges **without ground truth** (`Safety`, `RelevanceToQuery`, `RetrievalGroundedness`, `Guidelines`) |

**They form a loop:** production traces with bad feedback get added to the **evaluation dataset**, which is used to test the next version.

## 3.13 Genie spaces and the conversational API in multi-agent systems

- A **Genie space** (now "Genie Agent") is a natural-language → **SQL** interface over curated Unity Catalog tables, with instructions, example SQL and trusted assets. Use it for questions over **structured data** ("What were Q3 sales by region?").
- Multi-agent systems can use Genie:
  - **Multi-Agent Supervisor (Agent Bricks)**: add the Genie space as a sub-agent (no code).
  - **Code**: `GenieAgent` from `databricks_langchain.genie` inside a LangGraph supervisor. Log it with resource `DatabricksGenieSpace(genie_space_id=...)`.
  - **Managed MCP server for Genie**: `https://<workspace>/api/2.0/mcp/genie/{genie_space_id}`.
  - **Genie Conversation API** (REST): `POST /api/2.0/genie/spaces/{space_id}/start-conversation`, then poll the message and fetch query results. Follow-ups use `.../conversations/{conversation_id}/messages`. Use it to embed Genie in apps, Slack and Teams.
- Permissions: the caller needs access to the Genie space, `CAN USE` on its SQL warehouse, and `SELECT` on the underlying UC tables.

```python
from databricks_langchain.genie import GenieAgent
genie = GenieAgent(genie_space_id="01ef...", genie_agent_name="sales_genie",
                   description="Answers questions about sales and revenue tables")
```

---

### Quick self-check
- Which judges need ground truth? Which can run in production monitoring?
- 512-token chunks, cost matters more than quality: which embedding model profile?
- What does `agents.deploy()` give you besides the endpoint?
- When is a Genie space better than a vector index?
