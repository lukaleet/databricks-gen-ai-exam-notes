---
id: d5
title: "Section 5: Governance"
weight: 8
---

# Section 5: Governance (8%)

> 🗺️ **Visual learner?** This section's architecture is drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Use masking techniques as guard rails to meet a performance objective
2. Select guardrail techniques to protect against malicious user inputs to a Gen AI application
3. Use legal/licensing requirements for data sources to avoid legal risk
4. Recommend an alternative for problematic text mitigation in a data source feeding a GenAI application

---

## 5.1 Masking as a guardrail

**Goal:** keep sensitive data (PII, PHI, secrets) out of prompts, indexes, logs and responses, **while the app still works** (the "performance objective").

| Technique | Where | Notes |
|---|---|---|
| **Mask/redact during data prep** | Before chunking/indexing | Sensitive values never reach the vector index or LLM. `ai_mask(text, array('person','email','phone'))`, regex, NER (Presidio, spaCy) |
| **Pseudonymization / tokenization** | Data prep | Replace with consistent tokens (`<CUSTOMER_17>`) so the text keeps its meaning and relationships. Can be reversed with a secure mapping if needed |
| **Unity Catalog column masks & row filters** | Tables queried by tools/Genie | Per-user dynamic masking. Agents running **on-behalf-of-user** automatically respect them |
| **AI Gateway PII guardrail** | Serving endpoint request/response | **Block** or **mask** PII detected in input or output |
| **Output post-processing** | Chain post-processing step | Regex/NER masking before returning to the user |
| **Inference table hygiene** | Logs | Payload logs may contain PII. Restrict access and mask downstream |

**Masking vs. blocking:** masking keeps the request flowing (better user experience / task completion) and removes the sensitive value. Blocking stops the request completely. If the objective is "keep answering while never exposing card numbers", choose **masking**.

**Masking early beats masking late:** removing PII before embedding means it can't be retrieved or leaked later, and it reduces compliance scope.

## 5.2 Guardrails against malicious user inputs

Threats:
- **Prompt injection** (direct): "Ignore previous instructions and..."
- **Indirect prompt injection**: malicious instructions hidden in retrieved documents, web pages or tool outputs
- **Jailbreaks**: role-play tricks to bypass safety
- **Data exfiltration**: tricking the agent into revealing system prompts, other users' data or secrets
- **Tool abuse**: making an action-taking agent do harmful things (delete, send, pay)
- **Denial of wallet**: flooding with huge/expensive requests

Defenses (layered, "defense in depth"):
- **Input validation and classification**: safety classifiers (e.g. **Llama Guard**), prompt-injection detectors, topic allow-lists, input **length limits**
- **AI Gateway guardrails**: safety filter + PII detection on requests
- **Strong system prompt** with clear scope, and separation of instructions from data (delimiters, "treat retrieved text as data, not instructions")
- **Least privilege**: tools/agents get only the permissions they need; **OBO auth** so users can only reach their own data; read-only tools where possible
- **Human-in-the-loop** confirmation for high-impact actions
- **Rate limiting** (AI Gateway: per user/group/endpoint QPM/TPM)
- **Output guardrails**: check responses for leaked secrets/PII and unsafe content
- **Monitoring and red-teaming**: `Safety` judge in production monitoring, review traces, adversarial test sets in evaluation

## 5.3 Legal and licensing requirements for data sources

- Check the **license and terms of use** of every data source and model:
  - Website **terms of service** may forbid scraping or commercial reuse
  - **Copyrighted** material (books, articles, paywalled content) needs permission
  - **Open dataset licenses**: CC BY (attribution), CC BY-NC (**non-commercial only**), CC BY-SA (share-alike), research-only licenses
  - **Model licenses**: some open-weight models restrict commercial use or user counts, or require attribution. Read the **model card**
- **Privacy regulations** (GDPR, CCPA, HIPAA): personal data needs a lawful basis, minimization, the right to be forgotten (be able to **delete** a person's data from tables **and** the vector index → Delta Sync propagates deletes)
- **Internal data classification**: confidential docs shouldn't be in a broadly accessible index. Use UC permissions and separate indexes per audience
- Prefer **licensed/first-party** data and **Databricks Marketplace** datasets with clear terms
- Keep **lineage and documentation** (UC lineage, tags) to prove where data came from

Exam pattern: "the team wants to use content X but its license prohibits commercial use" → **don't use it**. Find a properly licensed alternative, get permission, or use first-party data.

## 5.4 Alternatives for problematic text in a data source

When source data contains **toxic, biased, offensive, outdated, PII or copyrighted** text:

| Option | When |
|---|---|
| **Remove/filter** the problematic documents or passages | Content isn't needed for the use case |
| **Redact or mask** the problematic spans | The rest of the document is valuable |
| **Rewrite/sanitize** with an LLM (e.g. neutralize offensive language), with review | Content needed but wording is a problem |
| **Replace the source** with a curated, licensed or higher-quality one | The source is fundamentally unsuitable |
| **Tag with metadata + filter at retrieval** (e.g. `audience=internal`, `status=deprecated`) | Content OK for some users or contexts only |
| **Output-side guardrails** | Extra safety layer, *not* a substitute for cleaning the source |

**Principle:** fix it **at the source** (data prep) instead of relying only on the LLM to "ignore" bad content. Fine-tuning the model to avoid it is costly and unreliable compared to cleaning the data.

---

### Quick self-check
- PII must never reach the vector index: where do you mask?
- What's the difference between Safety guardrails and PII guardrails in AI Gateway?
- A dataset is CC BY-NC and your app is commercial: what do you do?
- Name three defenses against indirect prompt injection.
