# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 05: Evaluate an agent with MLflow 3 (judges, custom scorers, SME data)
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §6 Evaluate agent performance using MLflow scoring and tracing
# MAGIC - §6 Identify evaluation judges that require ground truth
# MAGIC - §6 Use Databricks custom Scorers for evaluating agents and LLMs
# MAGIC - §6 Select an LLM choice based on quantitative evaluation metrics
# MAGIC - §3 Select chunking strategy / best model based on evaluation
# MAGIC
# MAGIC **Time:** ~45 min · **Prereq:** Lab 04 (`agent.py` and `agent_config.yaml` in this folder)

# COMMAND ----------

# MAGIC %pip install -U -qqq "mlflow[databricks]>=3.4" databricks-vectorsearch openai databricks-sdk
# MAGIC %restart_python

# COMMAND ----------

import mlflow, sys
sys.path.append(".")
from agent import AGENT
from mlflow.types.responses import ResponsesAgentRequest

def predict_fn(question: str) -> str:
    """Keys of each row's `inputs` dict become keyword args here."""
    r = AGENT.predict(ResponsesAgentRequest(input=[{"role": "user", "content": question}]))
    return r.model_dump()["output"][0]["content"][0]["text"]

predict_fn("How many PTO days do new hires get?")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Evaluation dataset (inputs + expectations = ground truth)

# COMMAND ----------

eval_data = [
    {"inputs": {"question": "How many PTO days do new hires accrue per year?"},
     "expectations": {"expected_facts": ["15 days per year", "accrued monthly"]}},
    {"inputs": {"question": "How many unused PTO days can I carry over?"},
     "expectations": {"expected_facts": ["up to 5 days", "expire on March 31"]}},
    {"inputs": {"question": "What is the international meal per diem?"},
     "expectations": {"expected_response": "The international meal per diem is 80 USD per day."}},
    {"inputs": {"question": "How many days per week can I work remotely?"},
     "expectations": {"expected_facts": ["up to 3 days per week", "manager approval"]}},
    {"inputs": {"question": "What is the company's stock ticker?"},           # not in corpus
     "expectations": {"expected_response": "I don't know based on current policies."}},
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Built-in judges, with and without ground truth
# MAGIC | Needs ground truth | No ground truth |
# MAGIC |---|---|
# MAGIC | `Correctness`, `RetrievalSufficiency`, `ToolCallCorrectness` | `RelevanceToQuery`, `Safety`, `RetrievalGroundedness`, `RetrievalRelevance`, `Guidelines` |

# COMMAND ----------

from mlflow.genai.scorers import (Correctness, RelevanceToQuery, RetrievalGroundedness,
                                  RetrievalRelevance, RetrievalSufficiency, Safety, Guidelines)

builtin = [
    Correctness(), RetrievalSufficiency(),                         # need expectations
    RelevanceToQuery(), Safety(), RetrievalGroundedness(), RetrievalRelevance(),
    Guidelines(name="cites_policy",
               guidelines="The response must cite a policy title in square brackets, unless it says it doesn't know."),
]

results = mlflow.genai.evaluate(data=eval_data, predict_fn=predict_fn, scorers=builtin)
results.metrics

# COMMAND ----------

# MAGIC %md
# MAGIC Open the **Evaluations** tab of the MLflow run linked above. Each row shows the trace, every judge's value and its **rationale**.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Custom code-based scorers (`@scorer`)
# MAGIC Cheap, deterministic checks. Parameters you can request: `inputs`, `outputs`, `expectations`, `trace`.

# COMMAND ----------

import re
from mlflow.genai.scorers import scorer
from mlflow.entities import Feedback

@scorer
def is_concise(outputs) -> bool:
    return len(str(outputs).split()) <= 80

@scorer
def has_citation(outputs) -> Feedback:
    ok = bool(re.search(r"\[[^\]]+\]", str(outputs))) or "don't know" in str(outputs).lower()
    return Feedback(value=ok, rationale="Citation or abstention present" if ok else "Missing [Policy] citation")

@scorer
def retrieval_latency_ok(trace) -> Feedback:
    spans = [s for s in trace.data.spans if s.span_type == "RETRIEVER"]
    if not spans:
        return Feedback(value=False, rationale="No RETRIEVER span found")
    ms = (spans[0].end_time_ns - spans[0].start_time_ns) / 1e6
    return Feedback(value=ms < 2000, rationale=f"Retriever took {ms:.0f} ms")

results2 = mlflow.genai.evaluate(data=eval_data, predict_fn=predict_fn,
                                 scorers=[is_concise, has_citation, retrieval_latency_ok])
results2.metrics

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Custom LLM judge with `make_judge` (subjective criteria)

# COMMAND ----------

from mlflow.genai.judges import make_judge

helpfulness = make_judge(
    name="employee_friendly",
    instructions=("Evaluate whether the answer in {{ outputs }} to the question in {{ inputs }} "
                  "is clear and actionable for an employee (tells them what to do next when relevant). "
                  "Answer 'yes' or 'no'."),
)
results3 = mlflow.genai.evaluate(data=eval_data, predict_fn=predict_fn, scorers=[helpfulness])
results3.metrics

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Compare configurations (model selection / chunking selection)
# MAGIC Re-run the same dataset with another LLM (or another index) and compare runs side by side in the MLflow UI.
# MAGIC Choose the **cheapest/fastest configuration that meets the quality bar**.

# COMMAND ----------

import yaml, importlib, agent as agent_mod

CANDIDATES = ["databricks-meta-llama-3-3-70b-instruct", "databricks-meta-llama-3-1-8b-instruct"]  # edit to models available to you
for llm in CANDIDATES:
    cfg = yaml.safe_load(open("agent_config.yaml")); cfg["llm_endpoint"] = llm
    yaml.safe_dump(cfg, open("agent_config.yaml", "w"))
    importlib.reload(agent_mod)
    def pf(question: str) -> str:
        r = agent_mod.AGENT.predict(ResponsesAgentRequest(input=[{"role": "user", "content": question}]))
        return r.model_dump()["output"][0]["content"][0]["text"]
    with mlflow.start_run(run_name=f"eval_{llm}"):
        res = mlflow.genai.evaluate(data=eval_data, predict_fn=pf,
                                    scorers=[Correctness(), RetrievalGroundedness(), is_concise])
        print(llm, {k: round(v, 2) for k, v in res.metrics.items() if k.endswith("/mean")})

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Evaluate existing traces (no re-run)
# MAGIC Production or Review App traces can be scored directly. Pass them as `data` and omit `predict_fn`.

# COMMAND ----------

traces = mlflow.search_traces(max_results=10)
mlflow.genai.evaluate(data=traces, scorers=[Safety(), RelevanceToQuery()]).metrics

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7 (optional): Persist the eval set as an MLflow Evaluation Dataset in UC
# MAGIC ```python
# MAGIC import mlflow.genai.datasets
# MAGIC ds = mlflow.genai.datasets.create_dataset(uc_table_name=f"{catalog}.{schema}.hr_eval_set")
# MAGIC ds.merge_records(eval_data)
# MAGIC mlflow.genai.evaluate(data=ds, predict_fn=predict_fn, scorers=[Correctness()])
# MAGIC ```
# MAGIC SME labels from the Review App can be merged into this dataset as new `expectations`.
# MAGIC
# MAGIC ## 🧪 Challenges
# MAGIC 1. Add a question whose answer needs **two** policies. Which judge flags the gap: `RetrievalSufficiency` or `RetrievalRelevance`?
# MAGIC 2. Write a `@scorer` that fails if the response contains an email address (a PII guard).
# MAGIC 3. Set `num_results` to 1 in `agent_config.yaml`, re-run, and explain which metrics move.
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Name the three judges that need ground truth.
# MAGIC - Why must the retriever be traced as a `RETRIEVER` span?
# MAGIC - Which scorer types can be registered for **production monitoring**? (built-in judges + `@scorer`, not class-based `Scorer`)
