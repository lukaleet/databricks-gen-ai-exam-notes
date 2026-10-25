---
id: d4
title: "Section 4: Assembling and Deploying Applications"
weight: 22
---

# Section 4: Assembling and Deploying Applications (22%)

> 🗺️ **Visual learner?** This section's architecture is drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Code a chain using a pyfunc model with pre- and post-processing
2. Control access to resources from model serving endpoints
3. Code a simple chain according to requirements
4. Choose the basic elements needed to create a RAG application: model flavor, embedding model, retriever, dependencies, input examples, model signature
5. Register the model to Unity Catalog using MLflow
6. Create and query a Vector Search index
7. Identify how to serve an LLM application that leverages Foundation Model APIs
8. Explain the key concepts and components of Mosaic AI Vector Search
9. Identify batch inference workloads and apply `ai_query()` appropriately
10. Configure vector search for a particular solution based on number of embeddings, update frequency, latency, and cost requirements
11. Configure a persistent datastore to store and retrieve intermediate memory or structured information
12. Apply CI/CD best practices such as updating a Vector Search index, promoting prompts across environments, and testing individual components of an agent
13. Integrate managed, external, and custom MCP servers based on a given application requirements
14. Apply prompt version control and manage prompt lifecycle
15. Develop an appropriate interactive user facing interface for an agent usage scenario (Apps, Slack, Teams, etc.)

---

## 4.1 A pyfunc chain with pre- and post-processing

`mlflow.pyfunc.PythonModel` is the generic, framework-agnostic way to package custom logic. Use it when you need **custom pre-processing** (clean or validate input, add context) and **post-processing** (parse or format output, mask PII) around a model call.

```python
import mlflow, re
from mlflow.pyfunc import PythonModel

class SupportChain(PythonModel):
    def load_context(self, context):
        # runs once when the model loads: create clients, load artifacts/config
        from databricks.sdk import WorkspaceClient
        self.client = WorkspaceClient().serving_endpoints.get_open_ai_client()

    def _preprocess(self, question: str) -> str:
        return question.strip()[:2000]                     # trim, limit length

    def _postprocess(self, text: str) -> str:
        return re.sub(r"\b\d{16}\b", "[CARD]", text)      # mask card numbers

    def predict(self, context, model_input, params=None):
        outputs = []
        for q in model_input["question"]:
            r = self.client.chat.completions.create(
                model="databricks-meta-llama-3-3-70b-instruct",
                messages=[{"role": "user", "content": self._preprocess(q)}])
            outputs.append(self._postprocess(r.choices[0].message.content))
        return outputs
```

Key points: `load_context()` runs **once** at load time (put expensive setup there). `predict(context, model_input, params)` handles each request. `model_input` is usually a pandas DataFrame.

## 4.2 Basic elements of a RAG application (when logging)

| Element | What / why |
|---|---|
| **Model flavor** | How MLflow packages it: `pyfunc` (custom / `ResponsesAgent`), `langchain`, `llama_index`, `openai`, `transformers` |
| **Embedding model** | Must be the **same** for indexing and querying (e.g. `databricks-gte-large-en`) |
| **Retriever** | Vector Search index + query settings (k, filters, hybrid, reranker) |
| **LLM** | Generation endpoint (Foundation Model API, external model) |
| **Prompt** | Template (ideally loaded from the Prompt Registry) |
| **Dependencies** | `pip_requirements` / `conda_env`, code files (`code_paths`), and **resources** (endpoints, indexes, functions it needs for auth) |
| **Input example** | Sample request, used to **infer the signature** and to validate the model before deployment |
| **Model signature** | Input/output **schema**. Required to register in Unity Catalog (inferred automatically for `ResponsesAgent`, or from `input_example`) |

```python
from mlflow.models.resources import (DatabricksServingEndpoint,
    DatabricksVectorSearchIndex, DatabricksFunction)

with mlflow.start_run():
    info = mlflow.pyfunc.log_model(
        name="rag_agent",
        python_model="agent.py",                       # models-from-code
        input_example={"input": [{"role": "user", "content": "What is the PTO policy?"}]},
        pip_requirements=["mlflow", "databricks-langchain", "databricks-vectorsearch"],
        resources=[
            DatabricksServingEndpoint(endpoint_name="databricks-meta-llama-3-3-70b-instruct"),
            DatabricksVectorSearchIndex(index_name="main.rag.doc_chunks_index"),
            DatabricksFunction(function_name="main.tools.get_order_status"),
        ],
    )
```

## 4.3 Register to Unity Catalog with MLflow

```python
mlflow.set_registry_uri("databricks-uc")                # default on recent MLflow versions
mv = mlflow.register_model(info.model_uri, "main.rag.hr_agent")   # 3-level name

from mlflow import MlflowClient
MlflowClient().set_registered_model_alias("main.rag.hr_agent", "champion", mv.version)
# load by alias: models:/main.rag.hr_agent@champion
```

- Name format: **`catalog.schema.model_name`**.
- UC needs a **signature**.
- Use **aliases** (`@champion`, `@challenger`), *not* stages. Stages are legacy Workspace Model Registry.
- Permissions: `USE CATALOG`, `USE SCHEMA`, `CREATE MODEL` on the schema; `EXECUTE` to load or serve.
- Lineage and governance come with Unity Catalog.

## 4.4 Mosaic AI Vector Search: concepts (now "Databricks AI Search")

| Concept | Details |
|---|---|
| **Vector Search endpoint** | The compute that serves indexes. Types: **Standard** and **Storage-optimized** |
| **Index** | Lives in Unity Catalog as `catalog.schema.index_name` |
| **Delta Sync Index** | Automatically syncs from a source **Delta table** (needs **Change Data Feed**). Two options: **managed embeddings** (Databricks computes embeddings from a text column using a model endpoint) or **self-managed embeddings** (table already has a vector column) |
| **Direct Vector Access Index** | You write/delete vectors yourself via REST/SDK (`upsert`, `delete`). No automatic sync |
| **Sync mode** | **Triggered** (you call `index.sync()` or schedule it; cheaper) or **Continuous** (near real-time; standard endpoints only; costs more because a pipeline keeps running) |
| **Algorithm** | HNSW approximate nearest neighbour (ANN); L2 distance |
| **Query types** | ANN (vector similarity, default), **HYBRID** (vector + BM25 keyword with reciprocal rank fusion), full-text |
| **Filters** | Metadata filters on columns, e.g. `{"department": "HR"}`, `{"year >=": 2024}` |
| **Reranker** | Optional second-stage reranking for better relevance (adds latency) |

### Standard vs. storage-optimized endpoints

| | **Standard** | **Storage-optimized** |
|---|---|---|
| Scale | ~**320M** vectors (768-dim) | **1B+** vectors |
| Query latency | **Lowest** (tens of ms); high QPS | Higher (~**+250 ms**) |
| Indexing speed | Normal | **10-20× faster** indexing |
| Cost at large scale | Higher | **Lower** cost per vector |
| Sync | Triggered **or continuous** | **Triggered only** |
| Direct Vector Access | Yes (limited size) | Limited |

**Configuration decisions**
- **Latency critical, high QPS, ≤ a few hundred million vectors** → **Standard**.
- **Huge corpus (hundreds of millions to billions), cost-sensitive, latency less critical** → **Storage-optimized**.
- **Data changes constantly and must be fresh within seconds** → Delta Sync with **continuous** sync (standard).
- **Data changes daily/weekly** → **triggered** sync after the ETL job (cheaper).
- **Embeddings come from your own pipeline/model** → self-managed embeddings (Delta Sync) or Direct Vector Access.
- **Accuracy matters and latency budget allows** → hybrid + reranker. **Latency critical** → keep them off and improve the embedding model instead (even fine-tune it).
- Too many vectors? Bigger chunks, less overlap, filter out irrelevant docs, dedupe.

### Create and query an index

```python
from databricks.vector_search.client import VectorSearchClient
vsc = VectorSearchClient()

vsc.create_endpoint(name="rag_endpoint", endpoint_type="STANDARD")   # or "STORAGE_OPTIMIZED"

index = vsc.create_delta_sync_index(
    endpoint_name="rag_endpoint",
    index_name="main.rag.doc_chunks_index",
    source_table_name="main.rag.doc_chunks",          # CDF enabled
    pipeline_type="TRIGGERED",                         # or "CONTINUOUS"
    primary_key="chunk_id",
    embedding_source_column="chunk",                   # managed embeddings
    embedding_model_endpoint_name="databricks-gte-large-en",
)

index.sync()                                           # triggered refresh (e.g. after ETL)

res = index.similarity_search(
    query_text="How many vacation days do new hires get?",
    columns=["chunk_id", "path", "chunk"],
    filters={"department": "HR"},
    num_results=5,
    query_type="HYBRID",
)
```

SQL alternative: `SELECT * FROM vector_search(index => 'main.rag.doc_chunks_index', query_text => '...', num_results => 5)`. A new `ai_search()` SQL function is also in Beta (Aug 2026).

> SDK note: since the June 2026 rename, the new Python package is `databricks-ai-search`. The legacy `databricks-vectorsearch` package (`VectorSearchClient`) still works with a deprecation warning, and it's the one the exam-era docs and courses use.

## 4.5 Serving LLM applications with Foundation Model APIs

- **Foundation Model APIs** give you hosted LLMs and embedding models behind serving endpoints:
  - **Pay-per-token**: ready-made endpoints (`databricks-...`). No setup; good for development, PoCs and moderate load.
  - **Provisioned throughput**: dedicated capacity for production SLAs, high throughput, **fine-tuned** or custom-weight models.
- **External models**: proxy third-party providers (OpenAI, Anthropic, Bedrock, Vertex) through a Databricks endpoint. The API key goes in **Databricks secrets**.
- APIs are **OpenAI-compatible** (chat completions, embeddings), so the `openai` client works:

```python
from databricks.sdk import WorkspaceClient
client = WorkspaceClient().serving_endpoints.get_open_ai_client()
client.chat.completions.create(model="databricks-meta-llama-3-3-70b-instruct",
                               messages=[{"role": "user", "content": "Hi"}])
```

- Your **agent/chain** is deployed as a **custom model** serving endpoint (via `agents.deploy()`), and it **calls** the Foundation Model API endpoint inside.
- The **AI Playground** lets you test and compare models before writing code, and can export code for an agent prototype.

## 4.6 Batch inference with `ai_query()`

Use **batch** when there's no user waiting: classify or summarize millions of rows, enrich tables nightly, back-fill embeddings, run offline evaluation.

```sql
SELECT ticket_id,
       ai_query('databricks-meta-llama-3-3-70b-instruct',
                CONCAT('Classify this ticket as billing, shipping or technical: ', body),
                failOnError => false) AS category
FROM main.support.tickets;
```

- `ai_query(endpoint, request [, returnType, failOnError, modelParameters, responseFormat])`
- `responseFormat` → **structured output** (JSON schema / STRUCT).
- `failOnError => false` returns errors per row instead of failing the whole query.
- `modelParameters => named_struct('temperature', 0.0, 'max_tokens', 100)`.
- Runs on SQL warehouses or job clusters, scales automatically, and works with Foundation Model APIs, external models and custom endpoints. Schedule it with **Lakeflow Jobs**.
- **Task-specific AI Functions** (`ai_classify`, `ai_extract`, `ai_summarize`, `ai_mask`...) are even simpler for common tasks.
- **Don't** use `ai_query` for interactive chat. **Do** use it for large table-scale transformations.

## 4.7 Persistent datastore for memory and structured state

| Need | Store |
|---|---|
| **Conversation / short-term memory** (thread state, checkpoints) for agents | **Lakebase** (managed Postgres): low-latency transactional reads/writes. E.g. a LangGraph checkpointer backed by Lakebase |
| **Long-term memory** (user preferences, facts learned) | Lakebase tables, or (2026+) **managed agent memory** (Beta) |
| **Low-latency lookups of structured features** (order status, delivery date) | **Online/feature tables** (feature serving) or Lakebase synced tables |
| **Analytics, logs, evaluation data, inference logs** | **Delta tables** in Unity Catalog |
| **Semantic recall over past content** | Vector Search index |

Delta tables are great for analytics, but **not** for many small, low-latency transactional reads/writes per chat turn. That's what Lakebase (OLTP) is for. Declare `DatabricksLakebase(...)` as a resource for automatic auth.

## 4.8 CI/CD for GenAI applications

- **Environments**: dev → staging → prod workspaces or catalogs (e.g. `dev.rag`, `prod.rag`).
- **Infrastructure as code**: **Databricks Asset Bundles** (now *Declarative Automation Bundles*) with `databricks.yml` to deploy jobs, pipelines, serving endpoints and apps per target.
- **Vector Search index updates**: the ingestion job updates the Delta table (MERGE), then a **triggered `index.sync()`** step runs (or continuous sync). Rebuild the index if you change the embedding model or chunking (new index + switch).
- **Prompt promotion**: prompts in the **MLflow Prompt Registry** (UC). Promote by moving **aliases** (`@staging` → tested → `@production`). Roll back by pointing the alias at an older version.
- **Model promotion**: UC model **aliases** (`@champion`/`@challenger`), deploy by alias.
- **Testing individual components**: unit-test tools/UC functions, the retriever (does it return expected docs?), prompt formatting and output parsers **separately**, then integration tests of the whole agent, then evaluation (`mlflow.genai.evaluate`) as a **quality gate** in CI.
- **Git folders** for source control. CI runner (GitHub Actions, Azure DevOps) calls the Databricks CLI or bundles.

## 4.9 Prompt version control and lifecycle (MLflow Prompt Registry)

```python
import mlflow

p = mlflow.genai.register_prompt(
    name="main.prompts.support_answer",            # stored in Unity Catalog
    template="Answer using only this context:\n{{context}}\n\nQuestion: {{question}}",
    commit_message="v1: initial grounded prompt",
)
mlflow.genai.set_prompt_alias("main.prompts.support_answer", alias="production", version=p.version)

prompt = mlflow.genai.load_prompt("prompts:/main.prompts.support_answer@production")
text = prompt.format(context=ctx, question=q)
```

- Versions are **immutable** and auto-incremented. Each has a **commit message**, like Git.
- **Aliases** are mutable pointers (`production`, `staging`) for promotion and **rollback** without code changes.
- Template variables use **`{{double_braces}}`**.
- URIs: `prompts:/name/<version>` or `prompts:/name@<alias>`.
- Prompts link to **traces and evaluation runs**, so you can see which prompt version produced which quality.
- Other APIs: `search_prompts`, `delete_prompt_alias`. Prompt optimization (e.g. GEPA-based `mlflow.genai.optimize_prompts`) can generate improved versions automatically.

## 4.10 MCP (Model Context Protocol) servers

**MCP** is an open standard that lets agents discover and call **tools, resources and prompts** exposed by servers.

| Type | What | When | How |
|---|---|---|---|
| **Managed MCP** | Databricks-hosted servers for **UC functions**, **Vector Search indexes**, **Genie spaces** (and more, e.g. DBSQL) | You want to use Databricks data/tools with **zero server maintenance**, governed by UC | URL like `https://<host>/api/2.0/mcp/functions/{catalog}/{schema}`, `/api/2.0/mcp/vector-search/{catalog}/{schema}`, `/api/2.0/mcp/genie/{space_id}` |
| **External MCP** | Third-party MCP servers (e.g. GitHub, web search vendors) | Use an existing external service | Register via a **Unity Catalog connection** (HTTP connection, with managed OAuth) and keep the **API key in Databricks Secrets**. Access through the Databricks proxy (`/api/2.0/mcp/external/{connection_name}`) |
| **Custom MCP** | Your own MCP server code | Proprietary logic/APIs that no managed or external server covers | Host it as a **Databricks App** (templates exist) |

**Choosing:** prefer **managed** (least maintenance) → **external** if a vendor already provides one → **custom** only if nothing else fits. Connect from code with `DatabricksMCPClient` (package `databricks-mcp`) or in the AI Playground / Multi-Agent Supervisor. Governance: UC permissions on the functions/indexes/connections. Since 2026 the gateway (Unity Gateway) can also govern MCP servers.

## 4.11 User-facing interfaces

| Interface | When |
|---|---|
| **Databricks Apps** | Custom web UI (Streamlit, Dash, Gradio, Flask, React, Node) hosted **inside Databricks**: SSO with corporate identity, no infrastructure. Chatbot UI templates exist. |
| **Review App** | For **SMEs/testers** to chat with an agent and give **feedback** during development (created by `agents.deploy`) |
| **AI Playground** | Prototype, compare models, test tools. Not for end users |
| **Slack / Microsoft Teams** | Users already work there. Bot calls the agent endpoint (or Genie via its API). Databricks Genie app for Slack (Preview, June 2026) |
| **Genie space UI** | Business users asking data questions |
| **REST API / SDK** | Integrate the endpoint into existing applications |

**Databricks Apps authorization**
- **App authorization**: every app has its own **service principal**. Credentials are injected as env vars (`DATABRICKS_CLIENT_ID/SECRET`). Use it for shared, non-user-specific actions.
- **User authorization (on-behalf-of-user)**: the app acts as the signed-in user. The user's token comes in the `x-forwarded-access-token` header, limited by declared **scopes**, and **UC row filters and column masks apply per user**.
- **Never** put PATs or API keys in browser JavaScript. Call endpoints from the **app backend**.

## 4.12 Controlling access to resources from serving endpoints

An agent on a serving endpoint must reach other resources (LLM endpoints, indexes, UC functions, Genie, tables, warehouses). Three methods:

1. **Automatic authentication passthrough** *(recommended)*: declare `resources=[...]` when logging. Databricks then creates a **short-lived service principal credential** with least-privilege access to exactly those resources. The deployer must have access to them.
   Classes in `mlflow.models.resources`: `DatabricksServingEndpoint`, `DatabricksVectorSearchIndex`, `DatabricksFunction`, `DatabricksGenieSpace`, `DatabricksSQLWarehouse`, `DatabricksTable`, `DatabricksUCConnection`, `DatabricksApp`, `DatabricksLakebase`.
2. **On-behalf-of-user (OBO) authentication**: the agent acts **as the end user** so UC permissions apply per user. Log with `auth_policy=AuthPolicy(system_auth_policy=..., user_auth_policy=UserAuthPolicy(api_scopes=[...]))`, and inside `predict()` use `ModelServingUserCredentials()` (from `databricks_ai_bridge`). Initialize user-scoped clients **inside predict**, not `__init__`.
3. **Manual authentication**: pass credentials as **environment variables referencing secrets**: `{{secrets/scope/key}}`, OAuth service principal (`DATABRICKS_CLIENT_ID/SECRET`) preferred over PAT. Use it for external services or resources that automatic passthrough doesn't support.

Also: **endpoint permissions** (`CAN QUERY`, `CAN MANAGE`, `CAN VIEW`) control who can call the endpoint itself. AI Gateway adds **rate limits** per user/group/service principal.

---

### Quick self-check
- Which index type requires CDF, and which needs manual upserts?
- 1B vectors, cost-sensitive, nightly updates: which endpoint type and sync mode?
- Three ways an agent endpoint authenticates to a Vector Search index?
- How do you roll back a prompt in production without redeploying code?
