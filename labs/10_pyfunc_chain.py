# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 10: A pyfunc chain with pre- and post-processing
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §4 Code a chain using a pyfunc model with pre- and post-processing
# MAGIC - §4 Code a simple chain according to requirements
# MAGIC - §4 Register the model to Unity Catalog using MLflow (signature from input example)
# MAGIC
# MAGIC **Time:** ~20 min · **Runs on:** Free Edition
# MAGIC
# MAGIC **Requirements for the chain**
# MAGIC 1. Input: a DataFrame with a `question` column.
# MAGIC 2. Pre-processing: strip HTML, trim to 1,000 chars, reject empty input.
# MAGIC 3. LLM call with a fixed system prompt.
# MAGIC 4. Post-processing: mask emails and 16-digit card numbers, return a `answer` column.

# COMMAND ----------

# MAGIC %pip install -U -qqq "mlflow[databricks]>=3.1" openai databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
dbutils.widgets.text("llm_endpoint", "databricks-meta-llama-3-3-70b-instruct")
CATALOG, SCHEMA, LLM = (dbutils.widgets.get(k) for k in ["catalog", "schema", "llm_endpoint"])

# COMMAND ----------

import re, mlflow, pandas as pd
from mlflow.pyfunc import PythonModel
from mlflow.models.resources import DatabricksServingEndpoint

class SupportChain(PythonModel):
    SYSTEM = "You are a concise support assistant. Answer in at most 3 sentences."

    def load_context(self, context):
        # Runs ONCE at load time: put expensive setup here
        from databricks.sdk import WorkspaceClient
        self.client = WorkspaceClient().serving_endpoints.get_open_ai_client()
        self.llm = context.model_config.get("llm_endpoint")

    @staticmethod
    def _pre(q: str) -> str:
        q = re.sub(r"<[^>]+>", " ", q or "").strip()
        if not q:
            raise ValueError("Empty question")
        return q[:1000]

    @staticmethod
    def _post(a: str) -> str:
        a = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[EMAIL]", a)
        return re.sub(r"\b\d(?:[ -]?\d){15}\b", "[CARD]", a)

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        answers = []
        for q in model_input["question"]:
            r = self.client.chat.completions.create(
                model=self.llm, temperature=0,
                messages=[{"role": "system", "content": self.SYSTEM},
                          {"role": "user", "content": self._pre(q)}])
            answers.append(self._post(r.choices[0].message.content))
        return pd.DataFrame({"answer": answers})

# COMMAND ----------

# MAGIC %md
# MAGIC ## Unit-test the pre/post steps in isolation (CI best practice: test components)

# COMMAND ----------

assert SupportChain._pre("<p>Hello</p>") == "Hello"
assert SupportChain._post("mail me at a.b@c.com") == "mail me at [EMAIL]"
assert SupportChain._post("card 4111 1111 1111 1111 ok") == "card [CARD] ok"
print("component tests passed")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Log (signature inferred from input example), register to UC, load & predict

# COMMAND ----------

example = pd.DataFrame({"question": ["<b>How do I reset my password?</b>"]})

with mlflow.start_run(run_name="support_chain"):
    info = mlflow.pyfunc.log_model(
        name="chain",
        python_model=SupportChain(),
        model_config={"llm_endpoint": LLM},
        input_example=example,                       # → signature
        pip_requirements=["mlflow", "openai", "databricks-sdk", "pandas"],
        resources=[DatabricksServingEndpoint(endpoint_name=LLM)],
    )
print(info.signature)

mlflow.set_registry_uri("databricks-uc")
mv = mlflow.register_model(info.model_uri, f"{CATALOG}.{SCHEMA}.support_chain")

model = mlflow.pyfunc.load_model(f"models:/{CATALOG}.{SCHEMA}.support_chain/{mv.version}")
model.predict(pd.DataFrame({"question": ["My email is jane@x.com, how do I update my card 4111111111111111?"]}))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Challenges
# MAGIC 1. Rewrite the same chain in LangChain LCEL: `prompt | ChatDatabricks(endpoint=LLM) | StrOutputParser()`, then compare the code size.
# MAGIC 2. Use `mlflow.models.set_model` with a code file (models-from-code) instead of passing the object.
# MAGIC 3. Run batch inference on a Spark DataFrame: `mlflow.pyfunc.spark_udf(spark, model_uri)`.
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - What goes in `load_context` vs `predict`?
# MAGIC - Why did registration to UC succeed without writing a signature manually?
