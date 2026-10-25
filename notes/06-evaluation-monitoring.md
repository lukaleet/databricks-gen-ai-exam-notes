---
id: d6
title: "Section 6: Evaluation and Monitoring"
weight: 12
---

# Section 6: Evaluation and Monitoring (12%)

> 🗺️ **Visual learner?** This section's architecture is drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Select an LLM choice (size and architecture) based on a set of quantitative evaluation metrics
2. Select key metrics to monitor for a specific LLM deployment scenario
3. Evaluate agent performance using MLflow scoring and tracing
4. Use inference logging to assess deployed RAG application performance
5. Use Databricks features to control LLM costs
6. Use inference tables and Agent Monitoring to track a live LLM endpoint
7. Identify evaluation judges that require ground truth
8. Use AI Gateway (Inference Tables, Usage Tables, and rate limiting) to track an LLM or agent deployed via Agent Framework
9. Use Databricks custom Scorers for evaluating agents and LLMs
10. Incorporate SME feedback to improve agent performance

---

## 6.1 Choosing LLM size/architecture from metrics

Read a comparison table like an engineer:
- Find the models that **pass the quality threshold** (e.g. correctness ≥ 0.85, groundedness ≥ 0.9).
- Among those, pick the one with the best **latency/cost**. Usually that's the **smallest** passing model.
- **Mixture-of-Experts (MoE)** models activate only part of their parameters per token, so they give large-model quality with lower inference compute.
- **Reasoning models** score higher on multi-step tasks but cost more tokens and latency.
- Domain-specific **fine-tuned small models** can beat large general models on narrow tasks (classification, extraction).
- Watch for **trade-offs**: a model that is 1% better but 3× slower is wrong when latency is the constraint.

## 6.2 Key metrics to monitor in production

| Category | Metrics |
|---|---|
| **Quality** | LLM-judge scores on sampled traffic (safety, relevance, groundedness, guidelines), **user feedback** (thumbs up/down), resolution rate |
| **Retrieval** | Retrieval relevance, "no results" rate, number of chunks, similarity scores |
| **Operational** | **Latency** (p50/p95/p99, time-to-first-token), **throughput** (QPS), **error rate** (4xx/5xx), timeouts, rate-limit hits |
| **Cost / usage** | **Token counts** (input/output), requests per user, cost per request, DBUs |
| **Safety / governance** | Guardrail trigger rate (blocked/masked), PII detections, jailbreak attempts |
| **Drift** | Changes in input topics and distributions, and in output length or quality |

Pick per scenario: a **customer-facing chatbot** → latency, safety, user feedback, groundedness. A **batch summarizer** → throughput, cost, quality sample. An **internal RAG over policies** → groundedness, retrieval relevance, "I don't know" rate.

## 6.3 Evaluating agents with MLflow scoring and tracing

**MLflow Tracing** records each request as a **trace** made of **spans** (LLM calls, retriever, tools, parsers) with inputs, outputs, latency, token usage and errors.

```python
import mlflow
from mlflow.entities import SpanType

mlflow.langchain.autolog()            # or mlflow.openai.autolog(), etc.

@mlflow.trace(span_type=SpanType.RETRIEVER)
def retrieve(query: str): ...
```

**Evaluation harness, `mlflow.genai.evaluate()`:**

```python
import mlflow
from mlflow.genai.scorers import (Correctness, RelevanceToQuery, RetrievalGroundedness,
                                  RetrievalSufficiency, Safety, Guidelines)

eval_data = [
    {"inputs": {"question": "How many PTO days do new hires get?"},
     "expectations": {"expected_facts": ["15 days of PTO", "accrues monthly"]}},
    {"inputs": {"question": "Can I carry over unused PTO?"},
     "expectations": {"expected_response": "Up to 5 days can be carried over."}},
]

def predict_fn(question: str) -> str:          # keys of `inputs` become kwargs
    return my_agent(question)

results = mlflow.genai.evaluate(
    data=eval_data,
    predict_fn=predict_fn,
    scorers=[Correctness(), RelevanceToQuery(), RetrievalGroundedness(),
             RetrievalSufficiency(), Safety(),
             Guidelines(name="tone", guidelines="Answer politely and concisely.")],
)
```

- `data` can be a list of dicts, a DataFrame, an **MLflow evaluation dataset** (`mlflow.genai.datasets.create_dataset(uc_table_name=...)`), or **existing traces** (then no `predict_fn` is needed).
- Results show per-row assessments plus rationale in the MLflow UI. Compare runs to detect regressions.

## 6.4 Judges that require ground truth

| Scorer / judge | Measures | Needs ground truth (`expectations`)? |
|---|---|---|
| `RelevanceToQuery` | Does the response address the request? | **No** |
| `Safety` | Harmful/toxic content? | **No** |
| `RetrievalGroundedness` | Is the response supported by the retrieved context (no hallucination)? | **No** |
| `RetrievalRelevance` | Are the retrieved chunks relevant to the request? | **No** |
| `Guidelines` | Does it follow natural-language rules you define (global)? | **No** |
| `ToolCallEfficiency` | Redundant/unnecessary tool calls? | **No** |
| `Correctness` | Matches `expected_response` / `expected_facts`? | **Yes** |
| `RetrievalSufficiency` | Does retrieved context contain all facts needed for the expected answer? | **Yes** |
| `ToolCallCorrectness` | Were the right tools called (vs. expected)? | **Yes** |
| `ExpectationsGuidelines` | Per-example guidelines stored in `expectations` | Uses per-row `guidelines` in expectations (labels, not a reference answer) |

Multi-turn judges also exist: `ConversationCompleteness`, `UserFrustration`, `KnowledgeRetention`...

**Memory trick:** if the judge compares to **"the correct answer" or "what should have happened"**, it needs ground truth (*Correctness, Sufficiency, ToolCallCorrectness*). Only judges **without** ground truth can run on live production traffic.

## 6.5 Custom scorers

When built-ins don't cover your criteria:

**1. Code-based scorer (`@scorer`)**: deterministic checks (format, length, keywords, latency from the trace).

```python
from mlflow.genai.scorers import scorer
from mlflow.entities import Feedback

@scorer
def is_concise(outputs) -> bool:
    return len(str(outputs).split()) <= 120

@scorer
def cites_source(inputs, outputs, expectations, trace) -> Feedback:
    ok = "[source:" in str(outputs)
    return Feedback(value=ok, rationale="Has citation" if ok else "No citation found")
```
Available parameters: `inputs`, `outputs`, `expectations`, `trace`. Return a bool, number, string, `Feedback`, or a list of `Feedback`.

**2. LLM judge with natural-language criteria**: `Guidelines(name=..., guidelines=...)` for pass/fail rules, or a custom judge with **`make_judge()`** (`mlflow.genai.judges`) using templated instructions like `{{ inputs }}`, `{{ outputs }}`, `{{ expectations }}`, `{{ trace }}`.

```python
from mlflow.genai.judges import make_judge

empathy = make_judge(
    name="empathy",
    instructions="Evaluate if the response in {{ outputs }} shows empathy to the "
                 "customer's problem in {{ inputs }}. Answer 'yes' or 'no'.",
    model="databricks:/databricks-claude-sonnet-4-5",
)
```

**Production monitoring:** only **built-in judges** and **`@scorer` functions** (defined in a Databricks notebook) can be registered for production monitoring. Class-based `Scorer` subclasses can't.

## 6.6 Inference tables, Agent Monitoring, inference logging

**Inference tables** (an AI Gateway feature on serving endpoints) automatically log **requests and responses** (plus status, latency, request id, user, and for agents the **traces**) to a **Delta table in Unity Catalog**, e.g. `catalog.schema.<endpoint>_payload`.

Use them to:
- Inspect failures, latency and token usage per request
- Run **offline evaluation on real traffic** (sample rows → `mlflow.genai.evaluate()` with judges)
- Build **dashboards and alerts** (Databricks SQL)
- Feed bad examples into the evaluation dataset or Review App for labeling
- Assess **RAG performance**: check retrieved docs, groundedness, and questions with no good answer

**Agent Monitoring / production monitoring (MLflow 3):** register scorers against the experiment that receives the endpoint's traces. They automatically evaluate a **sample** of live traffic:

```python
from mlflow.genai.scorers import Safety, ScorerSamplingConfig

safety = Safety().register(name="safety")
safety = safety.start(sampling_config=ScorerSamplingConfig(sample_rate=0.5))
```

Results are attached as **feedback on each trace** and shown in monitoring dashboards. Use **high sample rates** for cheap code-based checks and **low rates** (5-20%) for expensive LLM judges.

## 6.7 AI Gateway: inference tables, usage tables, rate limits

AI Gateway (now part of **Unity Gateway**) features configured on serving endpoints (external models, Foundation Model APIs, custom models/agents):

| Feature | What it gives you |
|---|---|
| **Inference tables** | Full request/response payload logging to UC Delta tables |
| **Usage tracking** | Token and request usage in **system tables**: `system.serving.endpoint_usage` (per-request token counts, requester), joined with `system.serving.served_entities` |
| **Rate limiting** | QPM / TPM limits per **endpoint**, **user**, **user group**, or **service principal**. Controls cost and abuse |
| **Guardrails** | Safety filtering, PII detection (block/mask) on input/output |
| **Traffic splitting / fallbacks** | Route % of traffic between models (A/B). Fail over to another model on errors |

For an agent deployed with **Agent Framework** (`agents.deploy`), inference tables and tracing are enabled automatically. Track usage with the usage system table, and set rate limits on the endpoint.

## 6.8 Controlling LLM costs on Databricks

- Choose the **smallest model that meets quality**. Use small models for routing/classification.
- **Pay-per-token** for low or variable traffic. **Provisioned throughput** for steady high volume (predictable cost and performance). **Scale-to-zero** on custom endpoints for dev and low traffic.
- **Rate limits** (AI Gateway) per user/group/endpoint. **Budget policies / serverless usage policies** with tags for chargeback.
- Monitor **usage system tables** (`system.serving.endpoint_usage`, `system.billing.usage`).
- Reduce tokens: shorter prompts, fewer/better chunks (re-ranking), summarize history, cap `max_tokens`.
- **Batch with `ai_query()`** instead of row-by-row real-time calls.
- **Caching** of repeated requests or results where appropriate.
- Lower **sample rates** for LLM-judge monitoring.
- Triggered (not continuous) Vector Search sync when freshness allows. **Storage-optimized** endpoints for very large indexes.

## 6.9 Incorporating SME feedback

- **Review App**: SMEs chat with the agent or review **labeling sessions** of selected traces and give structured feedback (ratings, corrected answers, expected facts, guideline compliance).
- **Labeling sessions / label schemas** (`mlflow.genai.labeling`): define what SMEs label (e.g. "correctness: yes/no", "expected_facts").
- **Evaluation datasets**: SME-corrected answers become **ground truth** (`expectations`) for future `mlflow.genai.evaluate()` runs.
- **Judge alignment**: align an LLM judge to SME labels so it reproduces their judgment at scale (MLflow judge `.align()` with feedback data).
- **Agent Bricks**: SMEs give natural-language feedback and guidelines directly, and the agent is re-optimized.
- **Rater consistency**: define clear **rubrics**, **calibrate SMEs** on examples, then use the aligned judgments in `mlflow.genai.evaluate()`. Don't just average noisy scores, drop disagreements, or blindly trust an LLM judge.

**The improvement loop**

```text
Production traces ──► monitoring scorers + user feedback ──► find failures
      ▲                                                          │
      │                                                          ▼
 deploy new version ◄── evaluate (quality gate) ◄── SMEs label → evaluation dataset
                                                     fix prompt / retrieval / tools
```

---

### Quick self-check
- Which 3 judges need ground truth?
- Which system table holds per-request token usage?
- What's the difference between inference tables and production-monitoring scorers?
- SME ratings disagree wildly: what's the fix?
