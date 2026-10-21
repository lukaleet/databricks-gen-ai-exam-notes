# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 01: Prompt engineering & structured output
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §1 Design a prompt that elicits a specifically formatted response
# MAGIC - §1 Select model tasks to accomplish a given business requirement
# MAGIC - §3 Create a prompt that adjusts an LLM's response from a baseline to a desired output
# MAGIC - §3 Augment a prompt with additional context from a user's input based on key fields, terms, and intents
# MAGIC
# MAGIC **Time:** ~30 min · **Runs on:** Free Edition

# COMMAND ----------

# MAGIC %pip install -U -qqq openai databricks-sdk pydantic
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("llm_endpoint", "databricks-meta-llama-3-3-70b-instruct")
LLM = dbutils.widgets.get("llm_endpoint")

from databricks.sdk import WorkspaceClient
client = WorkspaceClient().serving_endpoints.get_open_ai_client()

def chat(messages, **kw):
    r = client.chat.completions.create(model=LLM, messages=messages, **kw)
    return r.choices[0].message.content

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Baseline (zero-shot, no format spec)
# MAGIC Run it a few times. Notice how the format drifts.

# COMMAND ----------

ticket = "Hi, I was charged twice for order 88213 and I need this fixed today!!"
print(chat([{"role": "user", "content": f"Classify this support ticket: {ticket}"}]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: System prompt + explicit format + few-shot + low temperature

# COMMAND ----------

SYSTEM = """You classify customer support tickets.
Return ONLY a JSON object with keys:
  "category": one of "billing", "shipping", "technical", "other"
  "urgency": integer 1-5
  "order_id": string or null
Do not add any other text."""

few_shot = [
    {"role": "user", "content": 'Ticket: """My package says delivered but nothing arrived. Order 5512"""'},
    {"role": "assistant", "content": '{"category": "shipping", "urgency": 3, "order_id": "5512"}'},
]

out = chat([{"role": "system", "content": SYSTEM}, *few_shot,
            {"role": "user", "content": f'Ticket: """{ticket}"""'}],
           temperature=0.0)
print(out)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Strongest guarantee, structured outputs (JSON schema)
# MAGIC `response_format` constrains decoding to the schema. This is the best answer when an exam question asks for *guaranteed* parseable output.

# COMMAND ----------

import json

schema = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["billing", "shipping", "technical", "other"]},
        "urgency": {"type": "integer"},
        "order_id": {"type": ["string", "null"]},
    },
    "required": ["category", "urgency", "order_id"],
}

r = client.chat.completions.create(
    model=LLM,
    messages=[{"role": "system", "content": "Classify the support ticket."},
              {"role": "user", "content": ticket}],
    response_format={"type": "json_schema",
                     "json_schema": {"name": "ticket", "schema": schema, "strict": True}},
    temperature=0,
)
parsed = json.loads(r.choices[0].message.content)
parsed

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Baseline → desired output
# MAGIC Desired: **3 short bullet points for a non-technical customer, no jargon, friendly tone.**

# COMMAND ----------

question = "Why does my smart thermostat lose Wi-Fi connection every night?"
baseline = chat([{"role": "user", "content": question}])
print("BASELINE:\n", baseline[:1200])

desired_prompt = [
    {"role": "system", "content": (
        "You are a friendly support agent for non-technical customers. "
        "Answer in exactly 3 short bullet points, no jargon, max 15 words each. "
        "If you are unsure, suggest contacting support.")},
    {"role": "user", "content": question},
]
print("\nDESIRED:\n", chat(desired_prompt, temperature=0.2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Augment the prompt from key fields & intent
# MAGIC Pattern: **extract key fields → look up facts → inject them as context**.

# COMMAND ----------

# Fake "systems of record"
ORDERS = {"88213": {"status": "processing", "expected_delivery": "2026-10-28", "tier": "gold"}}

user_msg = "Where is my order 88213? I'm a gold member."

# 1) Extract key fields + intent (structured output again)
extract = client.chat.completions.create(
    model=LLM, temperature=0,
    messages=[{"role": "system", "content": "Extract fields from the user message."},
              {"role": "user", "content": user_msg}],
    response_format={"type": "json_schema", "json_schema": {"name": "x", "schema": {
        "type": "object",
        "properties": {"intent": {"type": "string", "enum": ["order_status", "refund", "other"]},
                       "order_id": {"type": ["string", "null"]}},
        "required": ["intent", "order_id"]}}},
)
fields = json.loads(extract.choices[0].message.content)
print(fields)

# 2) Look up structured facts, 3) Inject
facts = ORDERS.get(fields["order_id"] or "", {})
answer = chat([
    {"role": "system", "content": "Answer using ONLY the order facts. If facts are missing, say you can't find the order."},
    {"role": "user", "content": f"Order facts: {json.dumps(facts)}\n\nCustomer: {user_msg}"},
], temperature=0)
print(answer)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Challenges
# MAGIC 1. Change the task to **summarization**: turn a 5-sentence memo into a one-sentence gist (≤ 20 words). Which task category would you evaluate models on? *(Summarization)*
# MAGIC 2. Add a **guardrail instruction**: when the order isn't found, the bot must never invent a date. Test it with order `99999`.
# MAGIC 3. Use `ai_query` in SQL to classify 3 tickets with `responseFormat` (see Lab 08 for syntax).
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Which is stronger: few-shot examples or `response_format` JSON schema? Why?
# MAGIC - Why does low temperature help extraction tasks?
# MAGIC - Why look up delivery dates in a table instead of retrieving shipping-policy documents?
