# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 07: Tools: Unity Catalog functions, a tool-calling loop & managed MCP
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §1 Define and order tools that gather knowledge or take actions for multi-stage reasoning
# MAGIC - §4 Integrate managed, external, and custom MCP servers
# MAGIC - §3 Utilize MLflow and Agent Framework for developing agentic systems (tracing tool calls)
# MAGIC
# MAGIC **Time:** ~40 min · **Runs on:** Free Edition (managed MCP availability may vary)

# COMMAND ----------

# MAGIC %pip install -U -qqq "mlflow[databricks]>=3.1" openai databricks-sdk databricks-mcp
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
dbutils.widgets.text("llm_endpoint", "databricks-meta-llama-3-3-70b-instruct")
CATALOG, SCHEMA, LLM = (dbutils.widgets.get(k) for k in ["catalog", "schema", "llm_endpoint"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Data + governed tools as UC functions
# MAGIC UC functions are **governed** (permissions, lineage), **discoverable**, and **reusable** by any agent or framework.
# MAGIC The `COMMENT`s matter: the LLM picks tools by **name + description**.

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE {CATALOG}.{SCHEMA}.orders AS SELECT * FROM VALUES
  ('88213', 'alice@example.com', 'processing', DATE'2026-10-28', 120.00),
  ('77120', 'bob@example.com',   'shipped',    DATE'2026-10-23',  45.50),
  ('66001', 'alice@example.com', 'delivered',  DATE'2026-09-30',  15.99)
  AS t(order_id, email, status, expected_delivery, amount)""")

spark.sql(f"""CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_latest_order(customer_email STRING)
RETURNS STRING
COMMENT 'Returns the most recent order id for a customer email. Use this first when the user does not give an order id.'
RETURN (SELECT max_by(order_id, expected_delivery) FROM {CATALOG}.{SCHEMA}.orders WHERE email = customer_email)""")

spark.sql(f"""CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_order_status(order_id_in STRING)
RETURNS STRING
COMMENT 'Returns status and expected delivery date for a given order id.'
RETURN (SELECT concat('status=', status, '; expected_delivery=', cast(expected_delivery AS STRING))
        FROM {CATALOG}.{SCHEMA}.orders WHERE order_id = order_id_in)""")

display(spark.sql(f"SELECT {CATALOG}.{SCHEMA}.get_order_status({CATALOG}.{SCHEMA}.get_latest_order('alice@example.com')) AS s"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: A minimal tool-calling agent loop (ReAct style), traced with MLflow
# MAGIC The model decides the **order**: find the order (knowledge) → get its status (knowledge) → answer.

# COMMAND ----------

import json, mlflow
from mlflow.entities import SpanType
from databricks.sdk import WorkspaceClient

mlflow.openai.autolog()
client = WorkspaceClient().serving_endpoints.get_open_ai_client()

TOOLS = [
    {"type": "function", "function": {
        "name": "get_latest_order",
        "description": "Returns the most recent order id for a customer email. Use first if no order id is given.",
        "parameters": {"type": "object", "properties": {"customer_email": {"type": "string"}},
                       "required": ["customer_email"]}}},
    {"type": "function", "function": {
        "name": "get_order_status",
        "description": "Returns status and expected delivery date for an order id.",
        "parameters": {"type": "object", "properties": {"order_id_in": {"type": "string"}},
                       "required": ["order_id_in"]}}},
]

@mlflow.trace(span_type=SpanType.TOOL)
def call_uc_function(name: str, args: dict) -> str:
    arg_sql = ", ".join(f"'{str(v)}'" for v in args.values())   # demo only, use parameterized calls in production
    return str(spark.sql(f"SELECT {CATALOG}.{SCHEMA}.{name}({arg_sql}) AS r").first()["r"])

@mlflow.trace(span_type=SpanType.AGENT)
def run_agent(user_msg: str, max_steps: int = 5) -> str:
    messages = [{"role": "system", "content": "You are an order support agent. Use tools; never guess order data."},
                {"role": "user", "content": user_msg}]
    for _ in range(max_steps):
        msg = client.chat.completions.create(model=LLM, messages=messages, tools=TOOLS, temperature=0).choices[0].message
        if not msg.tool_calls:
            return msg.content
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            result = call_uc_function(tc.function.name, json.loads(tc.function.arguments))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "Stopped: too many steps"

print(run_agent("Hi, I'm alice@example.com, when will my latest order arrive?"))

# COMMAND ----------

# MAGIC %md
# MAGIC Open the trace: **AGENT → LLM → TOOL(get_latest_order) → LLM → TOOL(get_order_status) → LLM**. That's multi-stage reasoning with ordered tools.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: The same tools via the **managed MCP server for UC functions**
# MAGIC URL pattern: `https://<workspace-host>/api/2.0/mcp/functions/{catalog}/{schema}`. No server to run, governed by UC.
# MAGIC
# MAGIC | MCP type | Use when | How |
# MAGIC |---|---|---|
# MAGIC | **Managed** | UC functions, Vector Search, Genie: least maintenance | `/api/2.0/mcp/functions/...`, `/api/2.0/mcp/vector-search/...`, `/api/2.0/mcp/genie/{space_id}` |
# MAGIC | **External** | A vendor already offers an MCP server | UC **connection** + key in **Secrets** / managed OAuth → `/api/2.0/mcp/external/{connection}` |
# MAGIC | **Custom** | Proprietary API with no server | Build it, host as a **Databricks App** |

# COMMAND ----------

from databricks_mcp import DatabricksMCPClient

w = WorkspaceClient()
url = f"{w.config.host}/api/2.0/mcp/functions/{CATALOG}/{SCHEMA}"
try:
    mcp = DatabricksMCPClient(server_url=url, workspace_client=w)
    tools = mcp.list_tools()
    print([t.name for t in tools])
    res = mcp.call_tool(tools[0].name, {"customer_email": "bob@example.com"} if "latest" in tools[0].name
                        else {"order_id_in": "77120"})
    print(res.content)
except Exception as e:
    print("Managed MCP not available here:", e)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Logging an agent that uses these tools
# MAGIC Declare resources so the serving endpoint gets **automatic auth passthrough**:
# MAGIC ```python
# MAGIC from mlflow.models.resources import DatabricksFunction, DatabricksServingEndpoint, DatabricksSQLWarehouse
# MAGIC resources = [DatabricksServingEndpoint(endpoint_name=LLM),
# MAGIC              DatabricksFunction(function_name=f"{CATALOG}.{SCHEMA}.get_order_status"),
# MAGIC              DatabricksFunction(function_name=f"{CATALOG}.{SCHEMA}.get_latest_order")]
# MAGIC ```
# MAGIC
# MAGIC ## 🧪 Challenges
# MAGIC 1. Add an **action** tool `request_address_change(order_id, new_address)` (just log to a table). Add a guardrail: the agent must ask for confirmation first, and refuse if status is `shipped`.
# MAGIC 2. Make the tool descriptions vague ("does stuff with orders") and watch tool selection degrade.
# MAGIC 3. Evaluate the agent with `ToolCallCorrectness` (needs expected tool calls) and `ToolCallEfficiency` (no ground truth).
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Why gather knowledge before taking actions?
# MAGIC - Managed vs external vs custom MCP: which one for a vendor with an existing MCP server and an API key?
