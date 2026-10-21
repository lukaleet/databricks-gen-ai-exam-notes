---
id: plan
title: Study Plan & Hands-on Checklist
weight: 0
---

# Study plan

Work backwards from your exam date in **2-week sprints** (adapted from the Databricks AI Prep Guide).

| Phase | Share of your time | What to do here |
|---|---|---|
| **Diagnose** | First 25% | Read the *Exam Overview & Naming Traps* page. Take one **practice quiz per section** (10 questions each) *before* reading the notes. Note your 2–3 weakest sections. |
| **Deep dive + build** | Middle 50% | Read the notes for weak sections, do the matching **labs**, run the **scenarios**, and drill **flashcards** daily (10 min). Retake section quizzes until you reach ≥ 85%. |
| **Simulate** | Final 25% | Take **timed mock exams** (45 questions / 90 min). Review every miss in **Review mistakes**, then re-read the matching notes section. Repeat with a new random mock. |

**Daily rhythm (≈60–90 min):** 10 min flashcards → 30–45 min notes or a lab → 15–20 min practice questions → 5 min logging weak spots.

**You're ready when** mock scores are consistently ≥ 80%, you can explain *why* each wrong option is wrong, and you've completed the hands-on checklist below.

## Hands-on checklist (do these in Databricks Free Edition)

Each item maps to exam objectives and to a lab in `labs/`.

| # | Task | Section | Lab |
|---|---|---|---|
| 1 | Call a Foundation Model API with the OpenAI client and force JSON output with `response_format` | §1, §3 | 01 |
| 2 | Parse, clean and chunk documents, then write chunks to a UC Delta table with CDF enabled | §2 | 02 |
| 3 | Create a Vector Search endpoint and a Delta Sync index (managed embeddings), then query it with filters and hybrid search | §2, §4 | 03 |
| 4 | Compute precision@k, recall@k and MRR for your retriever on a labeled query set | §2 | 03 |
| 5 | Write a `ResponsesAgent` RAG agent, trace it, log it with `resources`, and register it to UC with an alias | §3, §4 | 04 |
| 6 | Run `mlflow.genai.evaluate()` with built-in judges (with and without ground truth) plus a custom `@scorer` | §6 | 05 |
| 7 | Register two prompt versions, promote with aliases, then roll back | §4 | 06 |
| 8 | Create UC functions as tools and run a tool-calling agent. Call them through the managed MCP server | §1, §4 | 07 |
| 9 | Run batch inference with `ai_query()` (`responseFormat`, `failOnError`) and mask PII with `ai_mask()` | §4, §5 | 08 |
| 10 | Deploy with `agents.deploy()`, then query the endpoint, inspect inference and usage tables, and register monitoring scorers | §4, §6 | 09 |
| 11 | Build a pyfunc chain with pre- and post-processing and register it to UC | §4 | 10 |
| 12 | *(UI)* Build a Genie space over a table, ask 3 questions, and look at the generated SQL | §3 | n/a |
| 13 | *(UI, if available)* Try Agent Bricks Knowledge Assistant / Information Extraction on a few docs | §1 | n/a |
| 14 | *(UI)* Compare 2 models side by side in AI Playground on the same prompt | §3 | n/a |

## Using an AI chatbot as a tutor (from the Databricks AI Prep Guide)

1. **Prime it every session.** Upload the official exam guide and paste: *"Use only current Databricks product names and behaviours, ground everything in docs.databricks.com and Databricks Academy, cite doc URLs, and say so when you can't verify a claim."*
2. **Paste the naming-traps table** from the Exam Overview page at the start of every session.
3. **Per-section loop:** Orient → Diagnose (10 questions) → Deep dive on the objectives you missed (quote them verbatim) → Practice → Repair (explain your misconception, then give a new question on the same concept).
4. **Cross-check** important answers with a second AI or the docs. When they disagree, that's a signal to read the docs.
5. **Re-check the official exam guide** two weeks before your exam date.

## Official resources

- Exam page and guide: databricks.com → Learn → Certification → *Generative AI Engineer Associate*
- Databricks Academy (free self-paced courses): academy.databricks.com
- Docs: docs.databricks.com (Agent Bricks / agents, AI Search / Vector Search, MLflow 3 GenAI, Model Serving, Unity Gateway / AI Gateway)
- Free Edition: databricks.com/learn/free-edition
- Registration: webassessor.com/databricks
