# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 02: Parse, clean, chunk → Delta table in Unity Catalog
# MAGIC
# MAGIC **Exam objectives**
# MAGIC - §2 Apply a chunking strategy for a given document structure and model constraints
# MAGIC - §2 Filter extraneous content in source documents that degrades quality of a RAG application
# MAGIC - §2 Choose the appropriate Python package to extract document content
# MAGIC - §2 Define operations and sequence to write given chunked text into Delta Lake tables in Unity Catalog
# MAGIC
# MAGIC **Time:** ~45 min · **Runs on:** Free Edition · **Prereq:** Lab 00
# MAGIC
# MAGIC We generate a small synthetic HR policy corpus (Markdown with headers + boilerplate) so you don't need to upload anything.

# COMMAND ----------

# MAGIC %pip install -U -qqq langchain-text-splitters tiktoken
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "genai_lab")
CATALOG, SCHEMA = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")
VOL = f"/Volumes/{CATALOG}/{SCHEMA}/raw_docs"
CHUNKS_TABLE = f"{CATALOG}.{SCHEMA}.policy_chunks"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Create source documents in a UC Volume
# MAGIC Every doc has a repeated **header/footer** (boilerplate we'll filter) and Markdown headings (structure we'll use for chunking).

# COMMAND ----------

import os, textwrap

HEADER = "ACME Corp - INTERNAL - Page {p}\n"
FOOTER = "\n© ACME Corp. Confidential. Do not distribute. | hr-portal.acme.example\n"

docs = {
"pto_policy.md": """
# Paid Time Off (PTO) Policy
Effective: 2026-01-01. Department: HR.
## Eligibility
All full-time employees are eligible for PTO from their first day of employment.
## Accrual
New hires accrue 15 days of PTO per year, accrued monthly (1.25 days per month).
After 5 years of service, accrual increases to 20 days per year.
## Carry-over
Up to 5 unused PTO days can be carried over into the next calendar year. Carried-over days expire on March 31.
## Requesting PTO
Submit requests in the HR portal at least 2 weeks in advance for absences longer than 3 days.
""",
"travel_policy.md": """
# Business Travel Policy
Effective: 2026-03-01. Department: Finance.
## Booking
All flights must be booked through the corporate travel tool. Economy class is required for flights under 6 hours.
## Per diem
The meal per diem is 60 USD per day domestically and 80 USD per day internationally.
## Expense reports
Submit expense reports within 30 days of returning, with itemized receipts for any expense over 25 USD.
""",
"remote_work_policy.md": """
# Remote Work Policy
Effective: 2025-06-01. Department: HR.
## Eligibility
Employees may work remotely up to 3 days per week with manager approval.
## Equipment
The company provides a laptop and a one-time 500 USD home office stipend.
## Security
Use the corporate VPN on all networks. Never store customer data on personal devices.
""",
"pto_policy_2019_OLD.md": """
# Paid Time Off (PTO) Policy (2019, superseded)
## Accrual
New hires accrue 10 days of PTO per year.
""",
}

for name, body in docs.items():
    pages = [HEADER.format(p=i + 1) + part + FOOTER for i, part in enumerate(body.split("## Accrual"))]
    content = "## Accrual".join(pages)
    with open(f"{VOL}/{name}", "w") as f:
        f.write(textwrap.dedent(content))

display(dbutils.fs.ls(VOL))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Ingest raw files (bronze)
# MAGIC Real projects use **Auto Loader** (`cloudFiles`) for incremental ingestion. Here we use a batch read.
# MAGIC For PDFs, Office files and scans you would read `format("binaryFile")` and parse with `ai_parse_document()`, `pypdf`, `unstructured` or `pytesseract` (see the table in the Section 2 notes).

# COMMAND ----------

from pyspark.sql import functions as F

raw_df = (spark.read.format("text").option("wholetext", True).load(f"{VOL}/*.md")
          .withColumn("path", F.col("_metadata.file_path"))
          .withColumnRenamed("value", "raw_text"))
display(raw_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ### (Optional) Parsing PDFs/images with `ai_parse_document`
# MAGIC Upload a PDF or PNG to the volume, then run:
# MAGIC ```sql
# MAGIC SELECT path, ai_parse_document(content) AS parsed
# MAGIC FROM read_files('/Volumes/<catalog>/<schema>/raw_docs/', format => 'binaryFile', pathGlobFilter => '*.pdf');
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Clean (filter extraneous content) and drop superseded docs

# COMMAND ----------

import re

BOILERPLATE = [
    r"ACME Corp - INTERNAL - Page \d+",
    r"© ACME Corp\. Confidential\. Do not distribute\. \| hr-portal\.acme\.example",
]

@F.udf("string")
def clean_text(t):
    for pat in BOILERPLATE:
        t = re.sub(pat, "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()

clean_df = (raw_df
    .withColumn("text", clean_text("raw_text"))
    .withColumn("is_superseded", F.col("text").contains("superseded"))
    .filter(~F.col("is_superseded"))          # keep only current versions
    .withColumn("doc_title", F.regexp_extract("text", r"^# (.+)", 1))
    .withColumn("department", F.regexp_extract("text", r"Department: (\w+)", 1))
    .select("path", "doc_title", "department", "text"))
display(clean_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Chunk (structure-aware + size cap)
# MAGIC 1. Split by Markdown headers (keeps each policy section together).
# MAGIC 2. Cap size with a recursive splitter (in tokens) so chunks fit the embedding model's context window.
# MAGIC 3. Prepend the doc title and section to each chunk (metadata enrichment).

# COMMAND ----------

import pandas as pd
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import ArrayType, StructType, StructField, StringType

CHUNK_TOKENS, OVERLAP = 200, 20

chunk_schema = ArrayType(StructType([
    StructField("section", StringType()), StructField("chunk", StringType())]))

@pandas_udf(chunk_schema)
def chunk_markdown(texts: pd.Series) -> pd.Series:
    from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
    md = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "title"), ("##", "section")])
    rec = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base", chunk_size=CHUNK_TOKENS, chunk_overlap=OVERLAP)
    out = []
    for t in texts:
        rows = []
        for d in md.split_text(t):
            title, section = d.metadata.get("title", ""), d.metadata.get("section", "")
            for piece in rec.split_text(d.page_content):
                rows.append({"section": section, "chunk": f"{title} > {section}\n{piece}"})
        out.append(rows)
    return pd.Series(out)

chunks_df = (clean_df
    .withColumn("c", F.explode(chunk_markdown("text")))
    .select("path", "doc_title", "department",
            F.col("c.section").alias("section"), F.col("c.chunk").alias("chunk"))
    .filter(F.length("chunk") > 40)                                  # drop tiny/empty chunks
    .withColumn("chunk_id", F.sha2(F.concat_ws("|", "path", "section", "chunk"), 256)))
display(chunks_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Write to a Delta table in UC **with Change Data Feed**
# MAGIC Order matters: table with a **primary key** → **CDF enabled** → (Lab 03) Delta Sync index.

# COMMAND ----------

(chunks_df.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(CHUNKS_TABLE))

spark.sql(f"ALTER TABLE {CHUNKS_TABLE} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
spark.sql(f"ALTER TABLE {CHUNKS_TABLE} ALTER COLUMN chunk_id SET NOT NULL")
display(spark.sql(f"SHOW TBLPROPERTIES {CHUNKS_TABLE}").filter("key like '%ChangeDataFeed%'"))
print(spark.table(CHUNKS_TABLE).count(), "chunks")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Incremental updates with MERGE (how production pipelines do it)
# MAGIC When a document changes, upsert its chunks and delete the stale ones. CDF then propagates **only the changes** to the index on the next sync.

# COMMAND ----------

from delta.tables import DeltaTable

updated = chunks_df.filter("doc_title = 'Business Travel Policy'") \
    .withColumn("chunk", F.regexp_replace("chunk", "60 USD", "65 USD")) \
    .withColumn("chunk_id", F.sha2(F.concat_ws("|", "path", "section", "chunk"), 256))

tgt = DeltaTable.forName(spark, CHUNKS_TABLE)
(tgt.alias("t")
    .merge(updated.alias("s"), "t.chunk_id = s.chunk_id")
    .whenNotMatchedInsertAll()
    .execute())
# delete old chunks of the changed doc that are no longer present
old_ids = [r.chunk_id for r in updated.select("chunk_id").collect()]
spark.sql(f"""DELETE FROM {CHUNKS_TABLE}
              WHERE doc_title = 'Business Travel Policy'
              AND chunk_id NOT IN ({",".join(repr(i) for i in old_ids)})""")
display(spark.sql(f"SELECT section, chunk FROM {CHUNKS_TABLE} WHERE doc_title='Business Travel Policy'"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🧪 Challenges
# MAGIC 1. **Chunk-count math:** re-run Step 4 with `CHUNK_TOKENS=50, OVERLAP=25` and then `CHUNK_TOKENS=400, OVERLAP=0`. How does the chunk count change? Which knobs reduce the record count?
# MAGIC 2. Remove the `doc_title > section` prefix and see (in Lab 03) whether retrieval quality drops.
# MAGIC 3. Look at `SELECT * FROM table_changes('<catalog>.<schema>.policy_chunks', 0)` to see the CDF rows from your MERGE.
# MAGIC
# MAGIC ## ✅ Check yourself
# MAGIC - Which package would you use for scanned PNGs? For HTML pages? For a mixed DOCX/PPTX/PDF corpus?
# MAGIC - Why must the chunk size be ≤ the embedding model's max tokens?
# MAGIC - Why delete the 2019 policy instead of letting the LLM figure out which version is current?
