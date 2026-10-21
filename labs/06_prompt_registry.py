# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 06: Prompt Registry: versioning, aliases, promotion & rollback
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §4 Apply prompt version control and manage prompt lifecycle
# MAGIC - §4 Apply CI/CD best practices: promoting prompts across environments
# MAGIC
# MAGIC **Time:** ~20 min · **Runs on:** Free Edition

# COMMAND ----------

# MAGIC %pip install -U -qqq "mlflow[databricks]>=3.1" openai databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

import mlflow
dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
dbutils.widgets.text("llm_endpoint", "databricks-meta-llama-3-3-70b-instruct")
CATALOG, SCHEMA, LLM = (dbutils.widgets.get(k) for k in ["catalog", "schema", "llm_endpoint"])
PROMPT = f"{CATALOG}.{SCHEMA}.hr_system"          # prompts live in Unity Catalog

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Register v1 and v2 (versions are immutable)

# COMMAND ----------

v1 = mlflow.genai.register_prompt(
    name=PROMPT,
    template=("You are an HR assistant. Answer using only this context:\n{{context}}\n\n"
              "Question: {{question}}"),
    commit_message="v1: basic grounded prompt",
    tags={"team": "hr-ai"},
)
v2 = mlflow.genai.register_prompt(
    name=PROMPT,
    template=("You are an HR assistant. Answer ONLY from the context and cite the policy title in [brackets]. "
              "If the answer is missing, say \"I don't know based on current policies.\"\n\n"
              "Context:\n{{context}}\n\nQuestion: {{question}}"),
    commit_message="v2: citations + abstention",
)
print(v1.version, v2.version)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Aliases = environments
# MAGIC `staging` → validated → `production`. The application loads **by alias**, so promotion needs no redeploy.

# COMMAND ----------

mlflow.genai.set_prompt_alias(PROMPT, alias="production", version=v1.version)
mlflow.genai.set_prompt_alias(PROMPT, alias="staging", version=v2.version)

prod = mlflow.genai.load_prompt(f"prompts:/{PROMPT}@production")
print("PROD template (v%s):\n%s" % (prod.version, prod.template))
print("\nFormatted:\n", prod.format(context="[PTO Policy] New hires accrue 15 days.", question="How much PTO?"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: A quality gate before promotion (what CI would run)

# COMMAND ----------

from databricks.sdk import WorkspaceClient
client = WorkspaceClient().serving_endpoints.get_open_ai_client()

def run(prompt_uri, ctx, q):
    p = mlflow.genai.load_prompt(prompt_uri)
    r = client.chat.completions.create(model=LLM, temperature=0,
        messages=[{"role": "user", "content": p.format(context=ctx, question=q)}])
    return r.choices[0].message.content

tests = [
    ("[PTO Policy] New hires accrue 15 days per year.", "How many PTO days for new hires?", lambda o: "[" in o),
    ("[Travel Policy] Per diem is 60 USD domestic.", "What's the parental leave?", lambda o: "don't know" in o.lower()),
]
passed = all(check(run(f"prompts:/{PROMPT}@staging", c, q)) for c, q, check in tests)
print("Staging prompt passed:", passed)

if passed:
    mlflow.genai.set_prompt_alias(PROMPT, alias="production", version=v2.version)
    print("Promoted v2 → production")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Rollback = move the alias back

# COMMAND ----------

mlflow.genai.set_prompt_alias(PROMPT, alias="production", version=v1.version)
print("production now →", mlflow.genai.load_prompt(f"prompts:/{PROMPT}@production").version)

# Discover prompts (filter syntax for UC-backed prompts may vary by MLflow version)
try:
    for p in mlflow.genai.search_prompts(filter_string=f"catalog = '{CATALOG}' AND schema = '{SCHEMA}'"):
        print(p.name)
except Exception as e:
    print("search_prompts:", e)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Challenges
# MAGIC 1. In Lab 04's `agent.py`, replace the hard-coded system prompt with `load_prompt(...@production)`. Re-log the agent. Now promote v2 and confirm the agent changes **without** re-logging.
# MAGIC 2. Run `mlflow.genai.evaluate()` (Lab 05) once per prompt version and compare the runs.
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Why are prompt versions immutable but aliases mutable?
# MAGIC - Which answer fits an exam question asking for gated promotion with history and rollback? (Prompt Registry + aliases, not overwriting files or tables.)
# MAGIC - What template syntax does the registry use? (`{{variable}}`)
