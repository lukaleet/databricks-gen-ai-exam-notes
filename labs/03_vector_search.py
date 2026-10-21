# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 03: Vector Search (AI Search) index, querying & retrieval evaluation
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §4 Create and query a Vector Search index
# MAGIC - §4 Explain the key concepts and components of Mosaic AI Vector Search
# MAGIC - §4 Configure vector search based on number of embeddings, update frequency, latency, and cost
# MAGIC - §2 Use tools and metrics to evaluate retrieval performance
# MAGIC - §2 Explain the role of re-ranking
# MAGIC
# MAGIC **Time:** ~45 min (index creation takes a few minutes) · **Prereq:** Lab 02
# MAGIC
# MAGIC > **Free Edition:** 1 AI Search endpoint (1 search unit) and **no Direct Vector Access**. Reuse a single endpoint for all labs.
# MAGIC >
# MAGIC > **Naming:** the exam says *Mosaic AI Vector Search*. Since June 2026 the docs call it **Databricks AI Search**. This lab uses the `databricks-vectorsearch` SDK (`VectorSearchClient`), which still works (with a deprecation warning). The new package is `databricks-ai-search`.

# COMMAND ----------

# MAGIC %pip install -U -qqq databricks-vectorsearch
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
dbutils.widgets.text("embedding_endpoint", "databricks-gte-large-en")
dbutils.widgets.text("vs_endpoint", "genai_lab_vs")

CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
EMB = dbutils.widgets.get("embedding_endpoint")
VS_ENDPOINT = dbutils.widgets.get("vs_endpoint")
SOURCE_TABLE = f"{CATALOG}.{SCHEMA}.policy_chunks"
INDEX_NAME = f"{CATALOG}.{SCHEMA}.policy_chunks_index"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create (or reuse) an endpoint
# MAGIC | | STANDARD | STORAGE_OPTIMIZED |
# MAGIC |---|---|---|
# MAGIC | Scale | ~320M vectors (768d) | 1B+ vectors |
# MAGIC | Latency | lowest | ~+250 ms |
# MAGIC | Sync | triggered **or continuous** | triggered only |
# MAGIC | Cost at scale | higher | lower |

# COMMAND ----------

import time
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient(disable_notice=True)

existing = [e["name"] for e in vsc.list_endpoints().get("endpoints", [])]
if VS_ENDPOINT not in existing:
    vsc.create_endpoint(name=VS_ENDPOINT, endpoint_type="STANDARD")

while vsc.get_endpoint(VS_ENDPOINT)["endpoint_status"]["state"] != "ONLINE":
    print("waiting for endpoint..."); time.sleep(30)
print("Endpoint online")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Create a Delta Sync index with managed embeddings
# MAGIC - `source_table_name`: needs **Change Data Feed** (Lab 02 enabled it)
# MAGIC - `primary_key`: unique id (the `_id` column name is reserved)
# MAGIC - `embedding_source_column` + `embedding_model_endpoint_name` = **managed embeddings**
# MAGIC - `pipeline_type="TRIGGERED"` = refresh when you call `sync()` (cheaper). `"CONTINUOUS"` = near real-time.

# COMMAND ----------

try:
    index = vsc.get_index(VS_ENDPOINT, INDEX_NAME)
    print("Index exists, syncing")
    index.sync()
except Exception:
    index = vsc.create_delta_sync_index(
        endpoint_name=VS_ENDPOINT,
        index_name=INDEX_NAME,
        source_table_name=SOURCE_TABLE,
        pipeline_type="TRIGGERED",
        primary_key="chunk_id",
        embedding_source_column="chunk",
        embedding_model_endpoint_name=EMB,
        columns_to_sync=["chunk_id", "chunk", "doc_title", "section", "department", "path"],
    )

while not index.describe().get("status", {}).get("ready", False):
    print("waiting for index...", index.describe().get("status", {}).get("detailed_state")); time.sleep(30)
print("Index ready")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Query: ANN, filters, hybrid

# COMMAND ----------

def show(res):
    cols = [c["name"] for c in res["manifest"]["columns"]]
    for row in res["result"]["data_array"]:
        d = dict(zip(cols, row))
        print(f'{d.get("score", 0):.3f} | {d["doc_title"]} > {d["section"]}')

q = "How many vacation days do new employees get?"
print("ANN:");     show(index.similarity_search(query_text=q, columns=["chunk_id", "doc_title", "section", "chunk"], num_results=3))
print("\nFILTER department=Finance:")
show(index.similarity_search(query_text=q, columns=["chunk_id", "doc_title", "section", "chunk"],
                             filters={"department": "Finance"}, num_results=3))
print("\nHYBRID (vector + BM25):")
show(index.similarity_search(query_text="per diem 80 USD", columns=["chunk_id", "doc_title", "section", "chunk"],
                             query_type="HYBRID", num_results=3))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Re-ranking (two-stage retrieval)
# MAGIC Retrieve more candidates (high recall), then rerank the top ones (high precision). This adds latency.

# COMMAND ----------

try:
    from databricks.vector_search.reranker import DatabricksReranker
    show(index.similarity_search(query_text=q, columns=["chunk_id", "doc_title", "section", "chunk"],
                                 num_results=3, query_type="HYBRID",
                                 reranker=DatabricksReranker(columns_to_rerank=["chunk", "doc_title"])))
except Exception as e:
    print("Reranker not available in this SDK/workspace:", e)

# COMMAND ----------

# MAGIC %md
# MAGIC ### SQL access
# MAGIC Run in a SQL cell: `SELECT * FROM vector_search(index => '<catalog>.<schema>.policy_chunks_index', query_text => 'PTO carry over', num_results => 3)`

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Evaluate retrieval (precision@k, recall@k, MRR)
# MAGIC A tiny labeled set: for each query, which `section`s are relevant (ground truth).

# COMMAND ----------

eval_set = [
    {"q": "How many PTO days does a new hire accrue?",          "relevant": {"Accrual"}},
    {"q": "Can I roll over unused vacation to next year?",       "relevant": {"Carry-over"}},
    {"q": "What is the daily meal allowance abroad?",            "relevant": {"Per diem"}},
    {"q": "Do I need a VPN when working from a cafe?",           "relevant": {"Security"}},
    {"q": "How much is the home office stipend?",                "relevant": {"Equipment"}},
]

def retrieve_sections(q, k, query_type="ANN"):
    res = index.similarity_search(query_text=q, columns=["section"], num_results=k, query_type=query_type)
    return [r[0] for r in res["result"]["data_array"]]

def metrics(k, query_type="ANN"):
    P, R, RR = [], [], []
    for ex in eval_set:
        got = retrieve_sections(ex["q"], k, query_type)
        rel = [g in ex["relevant"] for g in got]
        P.append(sum(rel) / k)
        R.append(len(set(got) & ex["relevant"]) / len(ex["relevant"]))
        RR.append(next((1 / (i + 1) for i, r in enumerate(rel) if r), 0))
    n = len(eval_set)
    return {"k": k, "type": query_type, "precision@k": round(sum(P) / n, 2),
            "recall@k": round(sum(R) / n, 2), "MRR": round(sum(RR) / n, 2)}

display(spark.createDataFrame([metrics(1), metrics(3), metrics(3, "HYBRID"), metrics(5)]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Updating the index (CI/CD pattern)
# MAGIC After the ingestion job MERGEs new chunks into the source table, call `index.sync()` for **triggered** indexes. A continuous index picks changes up automatically.

# COMMAND ----------

spark.sql(f"""INSERT INTO {SOURCE_TABLE} (chunk_id, path, doc_title, department, section, chunk)
VALUES (sha2('parental-leave', 256), 'manual', 'Parental Leave Policy', 'HR', 'Duration',
        'Parental Leave Policy > Duration\nEmployees receive 16 weeks of fully paid parental leave.')""")
index.sync()
time.sleep(60)
show(index.similarity_search(query_text="How long is parental leave?", columns=["chunk_id", "doc_title", "section"], num_results=2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Challenges
# MAGIC 1. Rebuild the chunks in Lab 02 with a different size/strategy, create a second index, and compare metrics. Pick the strategy with data (exam objective §3, "select chunking strategy based on model & retrieval evaluation").
# MAGIC 2. Sizing exercise: 150M chunks, 100 QPS, latency critical → which endpoint type? 2B chunks, weekly updates, cost-sensitive → which?
# MAGIC 3. Why can't you convert a self-managed-embedding index to managed embeddings later? (You'd create a new index.)
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Delta Sync vs Direct Vector Access: which needs CDF, and which needs manual upserts?
# MAGIC - When would you turn hybrid search and reranking **off**?
# MAGIC - Which retrieval metric rewards the first relevant result being at rank 1?
# MAGIC
# MAGIC 🧹 *Cleanup (optional, frees your Free Edition endpoint):* `vsc.delete_index(VS_ENDPOINT, INDEX_NAME)` / `vsc.delete_endpoint(VS_ENDPOINT)`. Labs 04, 05 and 09 reuse the index, so keep it until you're done.
