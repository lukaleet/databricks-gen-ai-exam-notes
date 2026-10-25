---
id: d2
title: "Section 2: Data Preparation"
weight: 14
---

# Section 2: Data Preparation (14%)

> 🗺️ **Visual learner?** This section's architecture is drawn in the [Visual guide](#/notes/visual).

**Objectives**

1. Apply a chunking strategy for a given document structure and model constraints
2. Filter extraneous content in source documents that degrades quality of a RAG application
3. Choose the appropriate Python package to extract document content from provided source data and format
4. Define operations and sequence to write given chunked text into Delta Lake tables in Unity Catalog
5. Identify needed source documents that provide necessary knowledge and quality for a given RAG application
6. Use tools and metrics to evaluate retrieval performance
7. Design retrieval systems using advanced chunking strategies
8. Explain the role of re-ranking in the information retrieval process

---

## The RAG data pipeline (memorize the order)

```text
 Source files (UC Volume)            e.g. /Volumes/main/rag/raw_docs/*.pdf
        │  1. Ingest (Auto Loader / read_files, binaryFile)
        ▼
 Raw table (bronze)                  path, content (binary), modification_time
        │  2. Parse / extract text   (ai_parse_document, pypdf, unstructured, pytesseract...)
        ▼
 Parsed table (silver)               path, text, metadata (title, page, section)
        │  3. Clean / filter         (remove headers, footers, boilerplate, duplicates, PII)
        │  4. Chunk                  (fixed / recursive / structure-aware / semantic)
        ▼
 Chunks table (gold, Delta, UC)      chunk_id (PK), doc_path, chunk_text, metadata...
        │  5. Enable Change Data Feed on the table
        │  6. Create Vector Search index (Delta Sync) → embeddings computed & synced
        ▼
 Vector Search index  ──►  Retriever  ──►  (Re-ranker)  ──►  LLM
```

## 2.1 Chunking strategies

**Why chunk?** Embedding models and LLMs have **context limits**. Smaller, focused chunks also give more **precise retrieval**. Chunks that are too small lose context; chunks that are too large dilute relevance and waste tokens.

| Strategy | How | Good for | Watch out |
|---|---|---|---|
| **Fixed-size** (by tokens/characters) | Split every N tokens, with optional **overlap** | Simple, uniform text | Cuts sentences/ideas mid-way |
| **Recursive character splitting** | Try to split on `\n\n`, then `\n`, then `. `, then ` ` until size fits | Good default for prose | Still size-driven |
| **Sentence / paragraph-based** | Split on natural boundaries | Articles, FAQs | Paragraph sizes vary a lot |
| **Structure-aware (document-based)** | Split by headings/sections (Markdown, HTML `<h2>`, PDF layout), keep tables whole | Manuals, docs with headers, legal docs | Needs parsing that keeps structure |
| **Semantic chunking** | Split where embedding similarity between sentences drops (topic shift) | Long mixed-topic docs | More compute |
| **Parent-child / small-to-big** | Embed small chunks for precise matching, but return the larger **parent** section to the LLM | Precision + enough context | Extra storage/lookup |
| **Hierarchical / summary-augmented** | Store document/section summaries + chunks; retrieve at multiple levels | Large corpora, "big picture" questions | More preprocessing |
| **Metadata enrichment** | Add title, section header, date, product to each chunk (and/or prepend the header to the chunk text) | Filtering + better embedding context | Keep metadata accurate |

**Chunk size vs. overlap math (a classic exam question):**
- Number of chunks ≈ `doc_tokens / (chunk_size − overlap)`.
- **Fewer records** → **increase chunk size** and/or **decrease overlap**.
- **More precise retrieval** → smaller chunks (to a point). **More context per hit** → larger chunks or parent-child.
- The embedding model's **max context length must be ≥ chunk size**, or text gets truncated silently.
- An embedding model with **fewer dimensions doesn't reduce the number of records**. It only reduces the size of each vector.

**Choosing a chunk size:** start from the query style. Short factoid questions → smaller chunks (~200-500 tokens). Questions needing a whole procedure → larger or structure-aware chunks. Then **evaluate**: try multiple strategies and compare retrieval metrics (see 2.6). That's the "select chunking strategy based on model & retrieval evaluation" objective in Section 3.

## 2.2 Filtering extraneous content

Things that **degrade RAG quality** and should be removed or handled:

- Repeated **headers/footers**, page numbers, navigation menus, cookie banners, HTML boilerplate, ads
- **Table of contents**, indexes, legal disclaimers repeated on every page
- **Duplicate** or near-duplicate documents, and **outdated versions** of the same doc (keep the latest, or add version/date metadata and filter)
- OCR garbage, encoding artifacts, empty chunks, extremely short chunks
- Irrelevant documents (out of domain) and low-quality sources
- Sensitive data you shouldn't expose (PII), so mask or remove it (see Governance)

**How:** regex/rules in the parse step, HTML parsers that drop `<nav>`/`<footer>`, dedup by hash or similarity, a minimum chunk length filter, metadata filters at query time (e.g. `{"doc_status": "current"}`).

## 2.3 Picking the right Python package for extraction

| Source format | Package(s) | Notes |
|---|---|---|
| Digital (text-based) PDF | **`pypdf`** (PyPDF2 successor), **`pdfplumber`**, **PyMuPDF (`fitz`)** | `pdfplumber` is good at tables |
| **Scanned** PDF / images (.png, .jpg) | **`pytesseract`** (Tesseract OCR), `easyocr` | OCR needed. Least code for images = `pytesseract.image_to_string(Image.open(f))` |
| Mixed formats (pdf, docx, pptx, html, email) | **`unstructured`** | Partitions docs into elements (Title, NarrativeText, Table) |
| Word .docx | `python-docx` | |
| PowerPoint .pptx | `python-pptx` | |
| HTML / web pages | **`beautifulsoup4`**, `lxml` | Parsing HTML, removing boilerplate tags |
| Crawling websites | `scrapy`, `requests` | Crawling/scraping, not parsing files |
| Markdown | `markdown`, LangChain `MarkdownHeaderTextSplitter` | Splits by headers |
| Layout-aware PDF → Markdown | `docling`, `pymupdf4llm` | Keeps headings/tables for structure-aware chunking |

**Databricks-native option (least code, scalable, SQL):** `ai_parse_document()` (GA April 2026). It parses PDF, JPG/PNG, TIFF, DOC/DOCX, PPT/PPTX into structured elements (text, tables as HTML, figures with descriptions, titles), and handles OCR for scanned content.

```sql
SELECT path, ai_parse_document(content) AS parsed
FROM read_files('/Volumes/main/rag/raw_docs/', format => 'binaryFile');
```

**Chunking libraries:** LangChain text splitters (`RecursiveCharacterTextSplitter`, `TokenTextSplitter`, `MarkdownHeaderTextSplitter`, `HTMLHeaderTextSplitter`), LlamaIndex node parsers (`SentenceSplitter`, `SemanticSplitterNodeParser`, `HierarchicalNodeParser`), and `tiktoken` / HF tokenizers to count tokens.

## 2.4 Writing chunks to Delta tables in Unity Catalog

Correct sequence:

1. **Read** raw files from a **UC Volume** (`spark.read.format("binaryFile")` or Auto Loader `cloudFiles` for incremental ingestion).
2. **Parse** text (UDF / `ai_parse_document`).
3. **Chunk**, usually with a **pandas UDF** or `explode()` of an array of chunks so it scales on Spark.
4. **Add a unique primary key** per chunk (e.g. hash of path + chunk index) plus metadata columns.
5. **Write** as a **Delta table in Unity Catalog** (`catalog.schema.table`) with `saveAsTable` (append/merge for incremental updates).
6. **Enable Change Data Feed (CDF)**: `ALTER TABLE ... SET TBLPROPERTIES (delta.enableChangeDataFeed = true)`. A Delta Sync Vector Search index needs this.
7. **Create or sync** the Vector Search index on the table.

```python
from pyspark.sql import functions as F

chunks_df = (parsed_df
    .withColumn("chunk", F.explode(chunk_udf("text")))           # array<string> -> rows
    .withColumn("chunk_id", F.sha2(F.concat_ws("-", "path", "chunk"), 256))
    .select("chunk_id", "path", "chunk"))

(chunks_df.write.format("delta").mode("append")
    .option("delta.enableChangeDataFeed", "true")
    .saveAsTable("main.rag.doc_chunks"))
```

Gotchas: the Vector Search index needs a **primary key**. The column name `_id` is **reserved**. Use **MERGE** to upsert changed documents so the index syncs only the changes.

## 2.5 Choosing the right source documents

- The source must **actually contain** the knowledge the questions need. If a bot fails on a topic, first check whether the data covers it.
- Prefer **authoritative, current, de-duplicated** sources with clear ownership.
- Match data type to retrieval method: **unstructured policies/manuals → vector search**; **per-entity structured facts (order status, delivery date, balances) → tables / feature & online tables / SQL tools / Genie**; **real-time** → API tools.
- Check **licensing/usage rights** and **PII** before ingesting (Governance).
- Analyze **expected user questions** (logs, SMEs) to find gaps in coverage.

## 2.6 Evaluating retrieval performance

**Retrieval metrics** (need to know which docs are relevant, i.e. ground truth):

| Metric | Meaning |
|---|---|
| **Precision@k** | Of the top-k retrieved chunks, what fraction is relevant? (noise) |
| **Recall@k** | Of all relevant chunks, what fraction appears in the top-k? (coverage) |
| **Hit rate@k** | Did at least one relevant chunk appear in top-k? |
| **MRR** (mean reciprocal rank) | How high is the first relevant result? 1/rank averaged |
| **NDCG** | Ranking quality with graded relevance, rewards relevant items at the top |

**LLM-judge retrieval metrics in MLflow 3** (`mlflow.genai.scorers`):
- `RetrievalRelevance`: are the retrieved chunks relevant to the query? (**no ground truth**)
- `RetrievalGroundedness`: is the answer supported by the retrieved context? (**no ground truth**, detects hallucination)
- `RetrievalSufficiency`: does the retrieved context contain everything needed for the expected answer? (**requires ground truth** `expectations`)

These judges find the retrieved context through **MLflow traces**, using spans of type `RETRIEVER`. So instrument your retriever with `@mlflow.trace(span_type=SpanType.RETRIEVER)` or use autologging.

**How to tune retrieval:** change chunk size/overlap/strategy, embedding model, `num_results` (k), add hybrid search, add metadata filters, add a re-ranker. Then re-run the **same evaluation dataset** and compare.

## 2.7 Advanced retrieval design

- **Hybrid search**: combine vector (semantic) similarity with keyword (BM25) search, fused with Reciprocal Rank Fusion. Helps with exact terms (SKU codes, error codes, names). On Databricks: `query_type="HYBRID"`.
- **Metadata filtering**: restrict search to e.g. `{"product": "X", "year >=": 2024}`. Improves precision and enforces business rules.
- **Query rewriting / expansion**: LLM rewrites the user question (e.g. adds context from chat history, or generates multiple queries, or HyDE = hypothetical answer embedding).
- **Parent-child / small-to-big**, **hierarchical**, **summary indexes** (see 2.1).
- **Multi-vector**: embed summaries/questions per chunk.

## 2.8 Re-ranking

Retrieval is two-stage:

1. **First stage (recall)**: a fast ANN vector search returns top **N** candidates (e.g. 50). Bi-encoder embeddings are computed independently for query and docs.
2. **Second stage (precision)**: a **re-ranker** (usually a **cross-encoder** that reads query + document together) scores each candidate more accurately, and you keep the top **k** (e.g. 5) for the prompt.

**Why:** better relevance at the top → fewer, better chunks in the prompt → higher answer quality, less noise, fewer tokens.
**Cost:** extra **latency** and compute. If **latency is the critical metric**, re-ranking (and hybrid search) may be turned off. If **quality is critical**, turn it on.

Databricks Vector Search supports a built-in reranker:

```python
from databricks.vector_search.reranker import DatabricksReranker

results = index.similarity_search(
    query_text="How do I reset my device?",
    columns=["chunk_id", "chunk", "doc_title"],
    num_results=10,
    query_type="HYBRID",
    reranker=DatabricksReranker(columns_to_rerank=["chunk", "doc_title"]),
)
```

---

### Quick self-check
- 150M embeddings, limit 100M: which TWO knobs? (bigger chunks, less overlap)
- Scanned PNG invoices, least code: which package? (`pytesseract`, or `ai_parse_document` in SQL)
- What table property must be on for a Delta Sync index? (Change Data Feed)
- Which retrieval judge needs ground truth? (`RetrievalSufficiency`)
