# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 08: Batch inference with `ai_query()` + governance (masking, row filters)
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §4 Identify batch inference workloads and apply `ai_query()` appropriately
# MAGIC - §1 Select model tasks to accomplish a business requirement (AI Functions)
# MAGIC - §5 Use masking techniques as guard rails to meet a performance objective
# MAGIC - §5 Recommend an alternative for problematic text mitigation in a data source
# MAGIC
# MAGIC **Time:** ~30 min · **Runs on:** Free Edition (serverless SQL / notebook)

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
dbutils.widgets.text("llm_endpoint", "databricks-meta-llama-3-3-70b-instruct")
CATALOG, SCHEMA, LLM = (dbutils.widgets.get(k) for k in ["catalog", "schema", "llm_endpoint"])
T = f"{CATALOG}.{SCHEMA}.support_tickets"

spark.sql(f"""CREATE OR REPLACE TABLE {T} AS SELECT * FROM VALUES
 (1, 'EU', 'I was charged twice for order 88213. My card 4111 1111 1111 1111. Call me at +1 415 555 0100.'),
 (2, 'US', 'Package shows delivered but nothing arrived. Very disappointed!!'),
 (3, 'EU', 'The app crashes when I open settings on Android 15.'),
 (4, 'US', 'Can I change the shipping address for order 77120? Email me: bob@example.com'),
 (5, 'APAC','Your product is garbage and your support team is useless idiots.')
 AS t(ticket_id, region, body)""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: General-purpose `ai_query` with structured output
# MAGIC `ai_query(endpoint, request [, returnType, failOnError, modelParameters, responseFormat])`

# COMMAND ----------

display(spark.sql(f"""
SELECT ticket_id,
  ai_query('{LLM}',
    CONCAT('Classify this support ticket and rate urgency 1-5. Ticket: ', body),
    responseFormat => 'STRUCT<result:STRUCT<category:STRING, urgency:INT>>',
    modelParameters => named_struct('temperature', 0.0),
    failOnError => false
  ) AS out
FROM {T}"""))

# COMMAND ----------

# MAGIC %md
# MAGIC With `failOnError => false`, the result is a struct with `result` and `errorMessage` per row, so one bad row doesn't fail a 10M-row job.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Task-specific AI Functions (less prompt engineering)

# COMMAND ----------

display(spark.sql(f"""
SELECT ticket_id,
       ai_classify(body, ARRAY('billing', 'shipping', 'technical', 'other')) AS category,
       ai_analyze_sentiment(body)                                           AS sentiment,
       ai_extract(body, ARRAY('order_id', 'email'))                         AS extracted,
       ai_summarize(body, 10)                                               AS summary
FROM {T}"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Mask PII **before** the data feeds a GenAI app (mask early)
# MAGIC Masking keeps the text useful for downstream tasks (classification, RAG) and removes the sensitive values.

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE TABLE {T}_masked AS
SELECT ticket_id, region,
       ai_mask(body, ARRAY('person', 'email', 'phone', 'credit card number')) AS body
FROM {T}""")
display(spark.table(f"{T}_masked"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Mitigate problematic (toxic) text in a source
# MAGIC Options: **filter out**, **redact**, **rewrite** (with review), or **replace the source**. Here we flag and rewrite.

# COMMAND ----------

display(spark.sql(f"""
WITH flagged AS (
  SELECT *, ai_classify(body, ARRAY('toxic', 'not_toxic')) AS tox FROM {T}_masked)
SELECT ticket_id, tox,
  CASE WHEN tox = 'toxic'
       THEN ai_query('{LLM}', CONCAT('Rewrite this customer message politely, keeping the complaint facts: ', body))
       ELSE body END AS clean_body
FROM flagged"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Unity Catalog column masks & row filters (per-user governance)
# MAGIC Agents and Genie that query **on behalf of the user** automatically respect these.

# COMMAND ----------

spark.sql(f"""CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.mask_body(body STRING)
RETURN CASE WHEN is_account_group_member('support_leads') THEN body ELSE regexp_replace(body, '[0-9]', '#') END""")

spark.sql(f"""CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.region_filter(region STRING)
RETURN is_account_group_member('admins') OR region = 'US'""")

spark.sql(f"ALTER TABLE {T} ALTER COLUMN body SET MASK {CATALOG}.{SCHEMA}.mask_body")
spark.sql(f"ALTER TABLE {T} SET ROW FILTER {CATALOG}.{SCHEMA}.region_filter ON (region)")
display(spark.table(T))   # what you see depends on your group membership

# COMMAND ----------

# Cleanup governance objects so other labs aren't affected
spark.sql(f"ALTER TABLE {T} ALTER COLUMN body DROP MASK")
spark.sql(f"ALTER TABLE {T} DROP ROW FILTER")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Challenges
# MAGIC 1. Productionize Step 1 as a **Lakeflow Job** that runs nightly and appends results to a table. Why is this better than looping over rows against a real-time endpoint?
# MAGIC 2. Use `ai_parse_document` + `ai_extract` on a PDF invoice you upload (the Information Extraction pattern).
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Which argument returns typed fields? Which keeps the job alive on errors?
# MAGIC - Why mask PII before indexing instead of asking the LLM not to reveal it?
# MAGIC - Masking vs blocking: which keeps task completion high?
