# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 00: Setup (run once)
# MAGIC
# MAGIC Creates the catalog objects used by every other lab.
# MAGIC
# MAGIC **Works in:** Databricks Free Edition or any Unity Catalog workspace with serverless compute.
# MAGIC
# MAGIC | Setting | Default | Notes |
# MAGIC |---|---|---|
# MAGIC | `catalog` | `workspace` | Free Edition ships with a `workspace` catalog. Change it if you use another one. |
# MAGIC | `schema` | `genai_lab` | All lab tables, functions, models, prompts and indexes go here. |
# MAGIC | `llm_endpoint` | `databricks-meta-llama-3-3-70b-instruct` | Pick any chat model listed on the **Serving** page. |
# MAGIC | `embedding_endpoint` | `databricks-gte-large-en` | Pick any embedding model on the **Serving** page. |
# MAGIC
# MAGIC > Model names on Foundation Model APIs change over time. If an endpoint doesn't exist, open **Serving** in the left nav and copy an available name.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
dbutils.widgets.text("llm_endpoint", "databricks-meta-llama-3-3-70b-instruct")
dbutils.widgets.text("embedding_endpoint", "databricks-gte-large-en")

CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.raw_docs")
print(f"Ready: {CATALOG}.{SCHEMA} and volume /Volumes/{CATALOG}/{SCHEMA}/raw_docs")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Smoke test: can we call the LLM and the embedding model?

# COMMAND ----------

# MAGIC %pip install -U -qqq openai databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

from databricks.sdk import WorkspaceClient

LLM = dbutils.widgets.get("llm_endpoint")
EMB = dbutils.widgets.get("embedding_endpoint")

client = WorkspaceClient().serving_endpoints.get_open_ai_client()  # OpenAI-compatible client
r = client.chat.completions.create(model=LLM, messages=[{"role": "user", "content": "Say hi in 3 words."}])
print("LLM:", r.choices[0].message.content)

e = client.embeddings.create(model=EMB, input=["hello world"])
print("Embedding dims:", len(e.data[0].embedding))

# COMMAND ----------

# MAGIC %md
# MAGIC ✅ If both calls worked, continue with **Lab 01**.
# MAGIC
# MAGIC **Exam link:** Foundation Model APIs are *OpenAI-compatible*. That's why the `openai` client works against Databricks endpoints (Section 4: "serve an LLM application that leverages Foundation Model APIs").
