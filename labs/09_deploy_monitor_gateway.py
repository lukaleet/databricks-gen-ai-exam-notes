# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 09: Deploy, query, govern & monitor an agent
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §4 Identify how to serve an LLM application (Agent Framework deployment)
# MAGIC - §4 Control access to resources from model serving endpoints
# MAGIC - §6 Use inference tables and Agent Monitoring to track a live LLM endpoint
# MAGIC - §6 Use AI Gateway (inference tables, usage tables, rate limiting)
# MAGIC - §6 Use Databricks features to control LLM costs
# MAGIC - §6 Incorporate SME feedback (Review App)
# MAGIC
# MAGIC **Time:** ~45 min (endpoint creation ~15 min) · **Prereq:** Lab 04 (registered model)
# MAGIC
# MAGIC > **Free Edition:** custom CPU serving endpoints are limited in number. Some gateway, system-table and monitoring features may not be available. If a step fails, read the code and the explanation. The exam tests the concepts.

# COMMAND ----------

# MAGIC %pip install -U -qqq "mlflow[databricks]>=3.1" databricks-agents databricks-sdk openai
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
MODEL_NAME = f"{CATALOG}.{SCHEMA}.hr_policy_agent"

import mlflow
from mlflow import MlflowClient
mlflow.set_registry_uri("databricks-uc")
version = MlflowClient().get_model_version_by_alias(MODEL_NAME, "champion").version
print(MODEL_NAME, "v", version)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Deploy with `agents.deploy()`
# MAGIC Creates: **Model Serving endpoint** + **Review App** + **inference tables / tracing** for monitoring. Resources declared at logging time get **automatic auth passthrough**.

# COMMAND ----------

from databricks import agents
deployment = agents.deploy(MODEL_NAME, version, scale_to_zero=True,
                           tags={"project": "hr-assistant", "env": "dev"})
ENDPOINT = deployment.endpoint_name
print("Endpoint:", ENDPOINT)
print("Review App:", deployment.review_app_url)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Query the endpoint (once it's READY)

# COMMAND ----------

from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
w.serving_endpoints.wait_get_serving_endpoint_not_updating(ENDPOINT)

client = w.serving_endpoints.get_open_ai_client()
resp = client.responses.create(model=ENDPOINT, input=[{"role": "user", "content": "How many PTO days can I carry over?"}])
print(resp.output_text if hasattr(resp, "output_text") else resp)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: AI Gateway: usage tracking, inference tables, rate limits, guardrails
# MAGIC (Also available in the UI: Serving → endpoint → **AI Gateway**. Since Aug 2026 this is part of **Unity Gateway**.)

# COMMAND ----------

from databricks.sdk.service.serving import (
    AiGatewayRateLimit, AiGatewayRateLimitKey, AiGatewayRateLimitRenewalPeriod,
    AiGatewayUsageTrackingConfig, AiGatewayInferenceTableConfig)

try:
    w.serving_endpoints.put_ai_gateway(
        name=ENDPOINT,
        usage_tracking_config=AiGatewayUsageTrackingConfig(enabled=True),
        inference_table_config=AiGatewayInferenceTableConfig(
            enabled=True, catalog_name=CATALOG, schema_name=SCHEMA, table_name_prefix="hr_agent"),
        rate_limits=[AiGatewayRateLimit(calls=20, key=AiGatewayRateLimitKey.USER,
                                        renewal_period=AiGatewayRateLimitRenewalPeriod.MINUTE)],
    )
    print("Gateway configured")
except Exception as e:
    print("Gateway config not available here (configure in UI or check edition):", e)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Analyze logs: inference table & usage system table

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Inference table: request/response payloads (name shown on the endpoint page; usually <prefix>_payload)
# MAGIC -- SELECT request_time, status_code, execution_duration_ms, request, response
# MAGIC -- FROM <catalog>.<schema>.hr_agent_payload ORDER BY request_time DESC LIMIT 20;
# MAGIC
# MAGIC -- Token usage per user/day (cost control, chargeback)
# MAGIC SELECT date_trunc('day', request_time) AS day, requester,
# MAGIC        sum(input_token_count) AS in_tokens, sum(output_token_count) AS out_tokens, count(*) AS requests
# MAGIC FROM system.serving.endpoint_usage
# MAGIC WHERE request_time > current_date() - INTERVAL 7 DAYS
# MAGIC GROUP BY ALL ORDER BY day DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Production monitoring ("Agent Monitoring") with registered scorers
# MAGIC Scorers run on a **sample** of live traces. Only judges that need **no ground truth** make sense here.

# COMMAND ----------

from mlflow.genai.scorers import Safety, RelevanceToQuery, RetrievalGroundedness, ScorerSamplingConfig

# Use the experiment that receives the endpoint's traces (agents.deploy links it to the logging experiment).
try:
    Safety().register(name="safety").start(sampling_config=ScorerSamplingConfig(sample_rate=1.0))
    RelevanceToQuery().register(name="relevance").start(sampling_config=ScorerSamplingConfig(sample_rate=0.2))
    RetrievalGroundedness().register(name="groundedness").start(sampling_config=ScorerSamplingConfig(sample_rate=0.2))
    print("Monitoring scorers started")
except Exception as e:
    print("Monitoring not available here:", e)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: SME feedback loop
# MAGIC 1. Share the **Review App** URL with HR experts. They chat and rate answers.
# MAGIC 2. Create a **labeling session** for poorly scored production traces:
# MAGIC ```python
# MAGIC import mlflow.genai.labeling as labeling
# MAGIC session = labeling.create_labeling_session(name="hr_week_42", assigned_users=["sme@company.com"],
# MAGIC                                            label_schemas=["expected_facts"])
# MAGIC session.add_traces(mlflow.search_traces(filter_string="...low groundedness..."))
# MAGIC ```
# MAGIC 3. Merge SME labels into the evaluation dataset (Lab 05, Step 7) → re-evaluate → promote the new version with an alias.
# MAGIC
# MAGIC ## Step 7: Access control recap
# MAGIC | Need | Mechanism |
# MAGIC |---|---|
# MAGIC | Agent → index/LLM/function | `resources=[...]` → **automatic auth passthrough** |
# MAGIC | Per-user data permissions | **On-behalf-of-user** (`UserAuthPolicy`, `ModelServingUserCredentials` in `predict`) |
# MAGIC | External API keys | env vars `{{secrets/scope/key}}` |
# MAGIC | Who can call the endpoint | Endpoint permission **CAN QUERY** |
# MAGIC | Abuse/cost | Gateway **rate limits** |
# MAGIC
# MAGIC 🧹 *Cleanup:* `w.serving_endpoints.delete(ENDPOINT)` when done (Free Edition endpoint limits).
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Which three things does `agents.deploy()` give you?
# MAGIC - Which table answers "which user consumed the most tokens last week?"
# MAGIC - Why sample expensive LLM judges at 5–20% in production?
