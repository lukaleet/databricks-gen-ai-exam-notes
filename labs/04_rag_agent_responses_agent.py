# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 04: Build, trace, log & register a RAG agent (Agent Framework + MLflow)
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §3 Utilize MLflow and Agent Framework for developing agentic systems
# MAGIC - §4 Choose the basic elements needed to create a RAG application: flavor, embedding model, retriever, dependencies, input examples, signature
# MAGIC - §4 Register the model to Unity Catalog using MLflow
# MAGIC - §4 Control access to resources from model serving endpoints (resources → automatic auth passthrough)
# MAGIC - §4 Apply prompt version control (loads the prompt from the Prompt Registry if present)
# MAGIC
# MAGIC **Time:** ~45 min · **Prereq:** Lab 03 (index ready)

# COMMAND ----------

# MAGIC %pip install -U -qqq "mlflow[databricks]>=3.1" databricks-agents databricks-vectorsearch openai databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
dbutils.widgets.text("llm_endpoint", "databricks-meta-llama-3-3-70b-instruct")
dbutils.widgets.text("vs_endpoint", "genai_lab_vs")
dbutils.widgets.text("embedding_endpoint", "databricks-gte-large-en")

CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
LLM = dbutils.widgets.get("llm_endpoint")
VS_ENDPOINT = dbutils.widgets.get("vs_endpoint")
EMB = dbutils.widgets.get("embedding_endpoint")
INDEX_NAME = f"{CATALOG}.{SCHEMA}.policy_chunks_index"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.hr_policy_agent"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Write the agent as code (`agent.py`)
# MAGIC This is the **models-from-code** pattern: MLflow logs the *file*, which ends with `mlflow.models.set_model(AGENT)`.
# MAGIC Config is passed through `ModelConfig` so the same code runs in dev and prod.

# COMMAND ----------

import yaml

config = {"llm_endpoint": LLM, "vs_endpoint": VS_ENDPOINT, "index_name": INDEX_NAME, "num_results": 4}
with open("agent_config.yaml", "w") as f:
    yaml.safe_dump(config, f)

agent_code = r'''
import mlflow
from mlflow.entities import SpanType
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse
from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient

mlflow.openai.autolog()                                  # trace every LLM call
cfg = mlflow.models.ModelConfig(development_config="agent_config.yaml")

SYSTEM_PROMPT = """You are an HR policy assistant.
Answer ONLY from the context below. Cite the policy title in brackets, e.g. [PTO Policy].
If the answer is not in the context, say "I don't know based on current policies."

Context:
{context}"""

class HRPolicyAgent(ResponsesAgent):
    def __init__(self):
        self.llm = WorkspaceClient().serving_endpoints.get_open_ai_client()
        self.index = VectorSearchClient(disable_notice=True).get_index(
            cfg.get("vs_endpoint"), cfg.get("index_name"))

    @mlflow.trace(span_type=SpanType.RETRIEVER)          # lets retrieval judges find the context
    def retrieve(self, query: str):
        res = self.index.similarity_search(
            query_text=query, columns=["chunk_id", "doc_title", "chunk"],
            num_results=cfg.get("num_results"))
        return [{"page_content": r[2], "metadata": {"doc_uri": r[1], "chunk_id": r[0]}}
                for r in res["result"]["data_array"]]

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        messages = [{"role": m.role, "content": m.content} for m in request.input]
        question = messages[-1]["content"]
        docs = self.retrieve(question)
        context = "\n\n".join(f"[{d['metadata']['doc_uri']}]\n{d['page_content']}" for d in docs)
        resp = self.llm.chat.completions.create(
            model=cfg.get("llm_endpoint"), temperature=0,
            messages=[{"role": "system", "content": SYSTEM_PROMPT.format(context=context)}, *messages])
        return ResponsesAgentResponse(output=[
            self.create_text_output_item(text=resp.choices[0].message.content, id="msg_1")])

AGENT = HRPolicyAgent()
mlflow.models.set_model(AGENT)
'''
with open("agent.py", "w") as f:
    f.write(agent_code)
print("agent.py written")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Test locally and inspect the trace
# MAGIC Expand the trace UI under the cell output: you'll see the RETRIEVER span and the LLM span with tokens and latency.

# COMMAND ----------

import importlib, sys
sys.path.append(".")
import agent; importlib.reload(agent)
from mlflow.types.responses import ResponsesAgentRequest

resp = agent.AGENT.predict(ResponsesAgentRequest(input=[{"role": "user", "content": "How many PTO days can I carry over?"}]))
print(resp.model_dump()["output"][0]["content"][0]["text"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Log the agent with all the RAG "basic elements"
# MAGIC | Element | Here |
# MAGIC |---|---|
# MAGIC | Flavor | `pyfunc` (ResponsesAgent) |
# MAGIC | Code | `python_model="agent.py"` (models-from-code) + `model_config` |
# MAGIC | Dependencies | `pip_requirements` |
# MAGIC | Input example | sample request → signature (ResponsesAgent infers it) |
# MAGIC | Resources | LLM endpoint + vector index (+ embedding endpoint used by the index) → **automatic auth passthrough** |

# COMMAND ----------

import mlflow
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksVectorSearchIndex

with mlflow.start_run(run_name="hr_policy_agent"):
    info = mlflow.pyfunc.log_model(
        name="agent",
        python_model="agent.py",
        model_config="agent_config.yaml",
        input_example={"input": [{"role": "user", "content": "What is the meal per diem abroad?"}]},
        pip_requirements=["mlflow>=3.1", "databricks-vectorsearch", "databricks-sdk", "openai"],
        resources=[
            DatabricksServingEndpoint(endpoint_name=LLM),
            DatabricksServingEndpoint(endpoint_name=EMB),
            DatabricksVectorSearchIndex(index_name=INDEX_NAME),
        ],
    )
print(info.model_uri)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Validate the logged model before deploying
# MAGIC `mlflow.models.predict` runs the model in an isolated environment with the logged dependencies, which catches missing packages early.

# COMMAND ----------

mlflow.models.predict(
    model_uri=info.model_uri,
    input_data={"input": [{"role": "user", "content": "Do I need a VPN at home?"}]},
    env_manager="uv",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Register to Unity Catalog and set an alias

# COMMAND ----------

from mlflow import MlflowClient

mlflow.set_registry_uri("databricks-uc")
mv = mlflow.register_model(info.model_uri, MODEL_NAME)
MlflowClient().set_registered_model_alias(MODEL_NAME, "champion", mv.version)
print(f"Registered {MODEL_NAME} v{mv.version} as @champion")

# Load by alias (what a deployment or batch job would do)
loaded = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
print(loaded.predict({"input": [{"role": "user", "content": "How long is parental leave?"}]}))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6 (optional): Deploy → see Lab 09
# MAGIC ```python
# MAGIC from databricks import agents
# MAGIC agents.deploy(MODEL_NAME, mv.version, scale_to_zero=True)   # endpoint + Review App + inference tables
# MAGIC ```
# MAGIC
# MAGIC ## 🧪 Challenges
# MAGIC 1. Replace `SYSTEM_PROMPT` with `mlflow.genai.load_prompt("prompts:/<catalog>.<schema>.hr_system@production")` after Lab 06.
# MAGIC 2. Add a second tool (e.g. a UC function from Lab 07) and declare it as `DatabricksFunction(function_name=...)` in `resources`.
# MAGIC 3. Change `num_results` in `agent_config.yaml` without touching code. Why is config-driven code good for CI/CD?
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Why is `ResponsesAgent` preferred over `ChatAgent` / `ChatModel`?
# MAGIC - What breaks at serving time if you forget to declare the vector index in `resources`?
# MAGIC - Why can't you register to UC without a signature, and how did we get one here?
