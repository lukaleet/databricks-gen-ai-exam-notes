"""Architecture diagrams for the Visual guide page, drawn as inline SVG.

Each diagram is a function returning a Diagram. Notes reference them with a line `[[diagram:<id>]]`,
which scripts/build.py replaces with the rendered <figure>. Colours come from CSS classes in
docs/assets/style.css (k-data, k-model, ...) so every diagram follows the light/dark theme.

Box kinds (the colour code, shown as a legend on the page):
  data  = Delta tables, volumes, indexes, Unity Catalog objects
  model = LLMs, embedding models, serving endpoints, registered models
  tool  = agent tools, Genie, MCP servers, sub-agents
  gov   = guardrails, credentials, permissions, masking
  eval  = MLflow tracing, evaluation, monitoring
  app   = users, apps, your agent code
  plain = everything else
"""
from html import escape

LABEL_PX, SUB_PX = 13, 11
CHAR_W = {"label": 0.62 * LABEL_PX, "sub": 0.56 * SUB_PX, "mono": 0.61 * SUB_PX}
warnings = []


class Diagram:
    def __init__(self, did, w, h, claim, caption):
        self.id, self.w, self.h, self.claim, self.caption = did, w, h, claim, caption
        self.els, self.boxes = [], {}

    # ---------- primitives ----------
    def box(self, key, x, y, w, h, label, sub=(), kind="plain", num=None, mono=False, accent=False, top=False):
        """A rounded box. `label` may contain '\n'. `sub` is a list of smaller lines (mono=True for code)."""
        self.boxes[key] = (x, y, w, h)
        labels = label.split("\n") if label else []
        sub = [sub] if isinstance(sub, str) else list(sub)
        cls = f"dg-box k-{kind}" + (" dg-hl" if accent else "")
        out = [f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>']
        block = len(labels) * 16 + len(sub) * 14
        ty = y + (16 if top else (h - block) / 2) + 12
        for line in labels:
            self._fit(key, line, "label", w)
            out.append(f'<text class="dg-label" x="{x + w / 2}" y="{ty:.1f}" text-anchor="middle">{escape(line)}</text>')
            ty += 16
        for line in sub:
            self._fit(key, line, "mono" if mono else "sub", w)
            out.append(f'<text class="dg-sub{" dg-mono" if mono else ""}" x="{x + w / 2}" y="{ty:.1f}" text-anchor="middle">{escape(line)}</text>')
            ty += 14
        if num is not None:
            out.append(f'<circle class="dg-num" cx="{x}" cy="{y}" r="10"/>'
                       f'<text class="dg-numt" x="{x}" y="{y + 4}" text-anchor="middle">{num}</text>')
        self.els.append("".join(out))
        return self

    def chip(self, x, y, w, text, kind="plain", h=20, mono=True):
        """A small pill (versions, aliases, strips). Not an arrow target."""
        self.els.append(f'<rect class="dg-box k-{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}"/>'
                        f'<text class="dg-sub{" dg-mono" if mono else ""} dg-strong" x="{x + w / 2}" y="{y + h / 2 + 4}" text-anchor="middle">{escape(text)}</text>')
        return self

    def rect(self, x, y, w, h, kind="plain", accent=False, rx=4):
        self.els.append(f'<rect class="dg-box k-{kind}{" dg-hl" if accent else ""}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/>')
        return self

    def group(self, x, y, w, h, label, kind="plain", bottom=False):
        ly = y + h - 10 if bottom else y + 18
        self.els.append(f'<rect class="dg-group k-{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="12"/>'
                        f'<text class="dg-glabel" x="{x + 12}" y="{ly}">{escape(label)}</text>')
        return self

    def text(self, x, y, s, cls="dg-note", anchor="start"):
        self.els.append(f'<text class="{cls}" x="{x}" y="{y}" text-anchor="{anchor}">{escape(s)}</text>')
        return self

    def line(self, pts, dashed=True, cls="dg-guide"):
        d = " ".join(f"{px},{py}" for px, py in pts)
        self.els.append(f'<polyline class="{cls}{" dg-dash" if dashed else ""}" points="{d}" fill="none"/>')
        return self

    def anchor(self, key, side, off=0.0):
        """Point on a box edge. side in l/r/t/b; off in [-0.5, 0.5] slides along the edge."""
        x, y, w, h = self.boxes[key]
        return {"l": (x, y + h / 2 + off * h), "r": (x + w, y + h / 2 + off * h),
                "t": (x + w / 2 + off * w, y), "b": (x + w / 2 + off * w, y + h)}[side]

    def arrow(self, a, b, label=None, sides=None, via=(), dashed=False, hot=False, lpos=None, lanchor="middle",
              aoff=0.0, boff=0.0):
        """Arrow from a to b. a/b are box keys or (x, y) points. sides='rl' means leave a's right edge,
        enter b's left edge; omitted sides are chosen from the relative position. `hot` = accent colour."""
        def center(k):
            if isinstance(k, tuple):
                return k
            x, y, w, h = self.boxes[k]
            return (x + w / 2, y + h / 2)
        ca, cb = center(a), center(b)
        if sides is None:
            dx, dy = cb[0] - ca[0], cb[1] - ca[1]
            sides = ("rl" if dx > 0 else "lr") if abs(dx) >= abs(dy) else ("bt" if dy > 0 else "tb")
        p0 = a if isinstance(a, tuple) else self.anchor(a, sides[0], aoff)
        p1 = b if isinstance(b, tuple) else self.anchor(b, sides[1], boff)
        pts = [p0, *via, p1]
        d = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        marker = f"{self.id}-ah" if hot else f"{self.id}-a"
        cls = "dg-edge" + (" dg-hot" if hot else "") + (" dg-dash" if dashed else "")
        out = [f'<polyline class="{cls}" points="{d}" fill="none" marker-end="url(#{marker})"/>']
        if label:
            if lpos is None:   # middle of the longest segment, nudged above horizontal lines
                segs = list(zip(pts, pts[1:]))
                (sx, sy), (ex, ey) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
                lpos = ((sx + ex) / 2, (sy + ey) / 2 - (6 if abs(ex - sx) >= abs(ey - sy) else -4))
            out.append(f'<text class="dg-elabel" x="{lpos[0]:.1f}" y="{lpos[1]:.1f}" text-anchor="{lanchor}">{escape(label)}</text>')
        self.els.append("".join(out))
        return self

    # ---------- output ----------
    def _fit(self, key, line, kind, w):
        need = len(line) * CHAR_W[kind] + 14
        if need > w:
            warnings.append(f"{self.id}/{key}: '{line}' needs ~{need:.0f}px, box is {w}px")

    def svg(self):
        defs = (f'<defs>'
                f'<marker id="{self.id}-a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="dg-head" d="M0,0 L10,5 L0,10 z"/></marker>'
                f'<marker id="{self.id}-ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="dg-head dg-hot" d="M0,0 L10,5 L0,10 z"/></marker>'
                f'</defs>')
        return (f'<svg class="dg" viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.claim)}" '
                f'xmlns="http://www.w3.org/2000/svg">{defs}{"".join(self.els)}</svg>')

    def figure(self):
        return (f'<figure class="diagram" id="dg-{self.id}">'
                f'<div class="fig-scroll" style="--fig-min:{min(self.w, 640)}px">{self.svg()}</div>'
                f'<figcaption>{escape(self.caption)}</figcaption></figure>')


# =====================================================================================
# The diagrams
# =====================================================================================

def lifecycle():
    d = Diagram("lifecycle", 880, 270,
                "The GenAI application lifecycle mapped to the exam sections, with governance applying to every stage.",
                "The exam follows the life of one application. Monitoring feeds failing traces back into development, "
                "and governance isn't a stage: it applies everywhere.")
    stages = [("design", "Design", "§1 · 14%", "prompt · tasks · tools"),
              ("prep", "Data prep", "§2 · 14%", "chunks + index"),
              ("dev", "Develop", "§3 · 30%", "agent · LLM choice"),
              ("deploy", "Assemble & deploy", "§4 · 22%", "UC model → endpoint"),
              ("mon", "Evaluate &\nmonitor", "§6 · 12%", "judges · cost")]
    for i, (k, label, sub, note) in enumerate(stages):
        x = 20 + i * 172
        d.box(k, x, 40, 152, 72, label, [sub, note], kind="app")
    for a, b in zip(stages, stages[1:]):
        d.arrow(a[0], b[0])
    d.arrow("mon", "dev", "failing traces → evaluation dataset", sides="bb", via=[(784, 152), (440, 152)], hot=True, dashed=True,
            lpos=(612, 146))
    d.box("gov", 20, 196, 840, 52, "Governance (§5 · 8%) applies at every stage",
          ["mask PII before indexing · guardrails on input and output · licensed data only · Unity Catalog permissions"], kind="gov")
    return d


def which_tool():
    d = Diagram("which-tool", 880, 452,
                "Decision ladder: which Databricks approach fits a GenAI requirement.",
                "Ask the questions top to bottom and take the first 'yes'. Exam answers usually favour the most managed "
                "option that meets every constraint.")
    qs = [("q1", "Questions over structured tables?", "a1", "Genie space", ["natural language → SQL (now Genie Agent)"], "tool"),
          ("q2", "Q&A over documents, low code, with citations?", "a2", "Knowledge Assistant", ["Agent Bricks: docs in a UC volume"], "tool"),
          ("q3", "Turn documents into table fields?", "a3", "Information Extraction", ["Agent Bricks, or ai_extract() in SQL"], "tool"),
          ("q4", "Several specialists behind one chat?", "a4", "Multi-Agent Supervisor", ["routes to Genie, KA, UC functions, MCP"], "tool"),
          ("q5", "Millions of rows, nobody waiting?", "a5", "Batch: ai_query()", ["SQL / Lakeflow job, not an endpoint"], "data")]
    for i, (qk, q, ak, a, asub, kind) in enumerate(qs):
        y = 20 + i * 68
        d.box(qk, 20, y, 400, 44, q, kind="plain")
        d.box(ak, 500, y, 360, 44, a, asub, kind=kind)
        d.arrow(qk, ak, "yes")
        if i:
            d.arrow(qs[i - 1][0], qk, "no", lpos=(232, y - 8), lanchor="start")
    d.box("a6", 500, 360, 360, 48, "Custom agent (Agent Framework)",
          ["ResponsesAgent + LangGraph / OpenAI SDK, full control"], kind="app")
    d.arrow("q5", "a6", "no: custom logic", sides="bl", via=[(220, 384)], lpos=(360, 378))
    d.text(20, 438, "Facts that change often → RAG, not fine-tuning. Fine-tune only for style, format or domain language.",
           cls="dg-note dg-strong")
    return d


def rag_ingest():
    d = Diagram("rag-ingest", 880, 440,
                "RAG ingestion pipeline: files in a UC volume are parsed, cleaned, chunked into a Delta table with "
                "Change Data Feed, then synced into a Vector Search index.",
                "The offline half of RAG, in the order the exam expects. The Delta Sync index needs Change Data Feed on the "
                "chunks table and a primary key per chunk.")
    rows = [("vol", "UC Volume: raw files", "/Volumes/main/rag/raw_docs/*.pdf"),
            ("bronze", "Bronze: raw table", "path · content (binary) · modification_time"),
            ("silver", "Silver: parsed text", "path · text · title / page / section"),
            ("gold", "Gold: chunks (Delta, CDF on)", "chunk_id (PK) · path · chunk_text · metadata"),
            ("index", "Vector Search index", "main.rag.doc_chunks_index  (HNSW, synced)")]
    for i, (k, label, cols) in enumerate(rows):
        y = 20 + i * 86
        d.box(k, 40, y, 250, 46, label, ["(now AI Search)"] if k == "index" else [], kind="data")
        d.text(580, y + 28, cols, cls="dg-sub dg-mono")
    steps = ["1 · ingest: read_files(binaryFile) / Auto Loader",
             "2 · parse: ai_parse_document (OCR for scans)",
             "3 · clean  ·  4 · chunk  ·  add chunk_id",
             "5 · enable CDF  ·  6 · Delta Sync"]
    for i, s in enumerate(steps):
        y0 = 20 + i * 86 + 46
        d.arrow(rows[i][0], rows[i + 1][0], s, lpos=(176, y0 + 24), lanchor="start")
    d.text(580, 20 + 2 * 86 + 66, "drop boilerplate & duplicates · mask PII",
           cls="dg-note dg-govtext")
    d.box("emb", 370, 364, 180, 46, "Embedding endpoint", ["databricks-gte-large-en"], kind="model")
    d.arrow("emb", "index", "embeds", lpos=(330, 380))
    return d


def chunking():
    d = Diagram("chunking", 880, 300,
                "Three chunking strategies applied to the same document: fixed-size with overlap cuts across sections, "
                "structure-aware follows headings, parent-child matches small chunks but returns the parent.",
                "Same document, three strategies. Dotted lines are section boundaries. Red chunks straddle two sections, "
                "which is the weakness of fixed-size splitting.")
    secs = [(180, 220, "## Eligibility"), (400, 260, "## Accrual"), (660, 200, "## Carry-over")]
    d.text(20, 38, "Source document", cls="dg-label")
    for x, w, t in secs:
        d.rect(x, 22, w, 26, kind="plain")
        d.text(x + 10, 40, t, cls="dg-sub dg-mono")
    for bx in (400, 660):
        d.line([(bx, 18), (bx, 236)])
    d.text(20, 82, "Fixed-size + overlap", cls="dg-label")
    d.text(20, 98, "every N tokens", cls="dg-sub")
    for i, x in enumerate(range(180, 860, 110)):
        w = min(140, 860 - x)
        if w < 40:
            continue
        crosses = any(x < b < x + w for b in (400, 660))
        d.rect(x, 66 + (i % 2) * 20, w, 16, kind="gov" if crosses else "data", accent=crosses)
    d.text(20, 140, "Structure-aware", cls="dg-label")
    d.text(20, 156, "split at headings", cls="dg-sub")
    for x, w, _ in secs:
        d.rect(x + 2, 128, w - 4, 26, kind="data")
    d.text(20, 196, "Parent → child", cls="dg-label")
    d.text(20, 212, "embed small, return big", cls="dg-sub")
    for j, (x, w, _) in enumerate(secs):
        d.rect(x + 2, 176, w - 4, 46, kind="app" if j == 1 else "plain", accent=j == 1)
        cw = (w - 4 - 5 * 6) / 4
        for c in range(4):
            d.rect(x + 8 + c * (cw + 6), 200, cw, 14, kind="model" if (j == 1 and c == 1) else "data", accent=(j == 1 and c == 1))
    d.text(530, 192, "parent section → LLM", cls="dg-sub dg-strong", anchor="middle")
    d.text(20, 262, "Chunks ≈ doc tokens / (chunk size − overlap).  Fewer records → bigger chunks or less overlap.",
           cls="dg-note dg-strong")
    d.text(20, 282, "Chunk size must fit the embedding model's context window, or the text is silently truncated.",
           cls="dg-note")
    return d


def retrieval():
    d = Diagram("retrieval", 880, 268,
                "Two-stage retrieval: hybrid vector plus keyword search fused with reciprocal rank fusion, then a "
                "cross-encoder re-ranker keeps the best few chunks for the prompt.",
                "Stage 1 is fast and recall-oriented, stage 2 is slower and precision-oriented. Turn hybrid search and "
                "re-ranking on for quality, and off when latency is the critical metric.")
    d.group(186, 14, 400, 196, "Stage 1 · recall (fast)")
    d.group(600, 14, 160, 196, "Stage 2 · precision")
    d.box("q", 20, 92, 130, 44, "User query", kind="app")
    d.box("vec", 206, 42, 190, 50, "Vector (ANN)", ["bi-encoder · semantic"], kind="data")
    d.box("kw", 206, 140, 190, 50, "Keyword (BM25)", ["exact terms · SKUs · codes"], kind="data")
    d.box("rrf", 436, 89, 130, 50, "Fusion (RRF)", ["query_type=HYBRID"], kind="plain")
    d.box("rr", 614, 89, 132, 50, "Re-ranker", ["cross-encoder"], kind="model")
    d.box("llm", 790, 92, 70, 44, "LLM", kind="model")
    d.arrow("q", "vec", sides="rl")
    d.arrow("q", "kw", sides="rl")
    d.arrow("vec", "rrf", sides="rl", aoff=0.1, boff=-0.25)
    d.arrow("kw", "rrf", sides="rl", aoff=-0.1, boff=0.25)
    d.arrow("rrf", "rr", "top 50")
    d.arrow("rr", "llm", "top 5")
    d.text(614, 236, "+ better chunks at the top, fewer tokens", cls="dg-note dg-oktext")
    d.text(614, 254, "− extra latency and compute", cls="dg-note dg-govtext")
    d.text(206, 236, "filters narrow both lists:  {\"department\": \"HR\"}", cls="dg-sub dg-mono")
    return d


def agent_loop():
    d = Diagram("agent-loop", 880, 330,
                "Agent tool-calling loop: the LLM reasons, calls a tool chosen by its description, observes the result and "
                "repeats until it can answer.",
                "The ReAct loop. The model picks tools by name and description, so write clear, typed tool definitions. "
                "Gather knowledge first, and put a confirmation in front of any action with side effects.")
    d.group(160, 20, 360, 290, "Agent (ResponsesAgent)", kind="app")
    d.group(560, 20, 300, 290, "Tools", kind="tool")
    d.box("user", 20, 110, 110, 48, "User", kind="app")
    d.box("reason", 186, 56, 150, 52, "Reason", ["LLM picks next step"], kind="model")
    d.box("act", 366, 56, 136, 52, "Act", ["tool call + args"], kind="model")
    d.box("obs", 286, 196, 150, 52, "Observe", ["read tool result"], kind="model")
    tools = [("t1", "Vector Search retriever", "knowledge · RAG", "data"),
             ("t2", "Genie space", "knowledge · text → SQL", "tool"),
             ("t3", "UC function", "get_order_status(id)", "tool"),
             ("t4", "MCP server", "managed · external · custom", "tool"),
             ("t5", "Action tool", "update_address() · confirm first", "gov")]
    for i, (k, l, s, kind) in enumerate(tools):
        d.box(k, 580, 44 + i * 52, 260, 44, l, [s], kind=kind)
    d.arrow("user", "reason", "question", sides="rl", aoff=-0.2, boff=0.2, lpos=(75, 100))
    d.arrow("reason", "act", sides="rl")
    d.arrow("act", (580, 82), "call", sides="r_", lpos=(541, 76))
    d.arrow((580, 222), "obs", "result", sides="_r", lpos=(508, 216))
    d.arrow("obs", "reason", "not done yet: loop", sides="tb", aoff=-0.2, boff=0.35, lpos=(323, 158), lanchor="start")
    d.arrow("reason", "user", "final answer", sides="bb", aoff=-0.3, via=((216, 274), (75, 274)), hot=True, lpos=(142, 268))
    d.text(186, 296, "order: identify → look up → validate → act", cls="dg-note")
    return d


def multi_agent():
    d = Diagram("multi-agent", 880, 320,
                "A Multi-Agent Supervisor routes each request to a specialised sub-agent: a Genie space for tables, a "
                "Knowledge Assistant for documents, UC functions for actions, and MCP for external systems.",
                "One chat in front of several specialists. Each sub-agent keeps its own data access, and the supervisor "
                "only decides who answers.")
    d.box("user", 20, 136, 110, 48, "User", kind="app")
    d.box("sup", 186, 122, 230, 76, "Multi-Agent Supervisor", ["(now Supervisor Agent)", "routes each request by intent"], kind="app", accent=True)
    subs = [("g", "Genie space  (now Genie Agent)", "“Q3 sales by region?” → SQL on UC tables"),
            ("k", "Knowledge Assistant", "“What's the PTO policy?” → docs + citations"),
            ("f", "UC function", "“Reset my password” → governed lookup/action"),
            ("m", "MCP server / agent endpoint", "external systems and custom agents")]
    for i, (k, l, s) in enumerate(subs):
        d.box(k, 500, 24 + i * 70, 360, 52, l, [s], kind="tool")
        d.arrow("sup", k, sides="rl", aoff=(i - 1.5) * 0.22)
    d.arrow("user", "sup", "question")
    d.text(20, 236, "Genie needs: access to the space, CAN USE on its", cls="dg-note")
    d.text(20, 252, "SQL warehouse, SELECT on the underlying tables.", cls="dg-note")
    d.text(20, 302, "In code: LangGraph supervisor + GenieAgent (DatabricksGenieSpace resource) · apps: Genie Conversation API",
           cls="dg-note")
    return d


def mcp():
    d = Diagram("mcp", 880, 300,
                "Three kinds of MCP servers an agent can use: managed by Databricks, external through a UC connection, "
                "or custom code hosted as a Databricks App.",
                "Prefer managed, then external, then custom. Each step down adds more for you to run and secure.")
    d.box("agent", 20, 116, 150, 56, "Agent", ["DatabricksMCPClient"], kind="app")
    rows = [("man", "Managed MCP", ["/api/2.0/mcp/functions|vector-search|genie"], "res1", "Databricks data",
             ["UC functions · VS · Genie"], "data"),
            ("ext", "External MCP (via proxy)", ["UC connection + secret / managed OAuth"], "res2", "Third-party server",
             ["GitHub, web search, …"], "tool"),
            ("cus", "Custom MCP", ["your server code as a Databricks App"], "res3", "Your own APIs", ["proprietary logic"], "app")]
    for i, (k, l, s, rk, rl, rs, rkind) in enumerate(rows):
        y = 24 + i * 92
        d.box(k, 230, y, 300, 56, l, s, kind="tool", mono=(k == "man"))
        d.box(rk, 660, y, 200, 56, rl, rs, kind=rkind)
        d.arrow("agent", k, sides="rl", aoff=(i - 1) * 0.3)
        d.arrow(k, rk, "governed by UC" if k != "cus" else "you maintain it")
    d.text(20, 290, "least maintenance  →  most maintenance", cls="dg-note dg-strong")
    return d


def rag_query():
    d = Diagram("rag-query", 880, 384,
                "Online RAG request path: question to the agent endpoint, hybrid retrieval and re-ranking, augmented prompt "
                "to the LLM, answer with citations, every step captured in an MLflow trace.",
                "The online half of RAG, numbered in order. Steps 2-3 are retrieval (Vector Search + re-ranker). The trace "
                "records each step as a span, which is what judges and monitoring read later.")
    d.box("user", 20, 60, 140, 60, "User", ["App · Slack", "Review App"], kind="app")
    d.box("agent", 310, 52, 210, 76, "Agent serving endpoint", ["ResponsesAgent", "deployed with agents.deploy()"], kind="app", accent=True)
    d.box("llm", 660, 60, 200, 60, "LLM endpoint", ["Foundation Model API"], kind="model")
    d.box("vs", 250, 216, 200, 64, "Vector Search index", ["hybrid + filters", "(now AI Search)"], kind="data")
    d.box("rr", 520, 222, 170, 56, "Re-ranker", ["cross-encoder"], kind="model")
    d.arrow("user", "agent", "1 · question", sides="rl", aoff=-0.22, boff=-0.22)
    d.arrow("agent", "user", "6 · answer + citations", sides="lr", aoff=0.22, boff=0.22, hot=True)
    d.arrow("agent", "llm", "4 · prompt + context", sides="rl", aoff=-0.22, boff=-0.22)
    d.arrow("llm", "agent", "5 · completion", sides="lr", aoff=0.22, boff=0.22)
    d.arrow("agent", "vs", "2 · embed + search", sides="bt", aoff=-0.3, boff=0.0, lpos=(344, 178), lanchor="end")
    d.arrow("vs", "rr", "top 50")
    d.arrow("rr", "agent", "3 · top 5 chunks", sides="tb", via=((605, 170), (478, 170)), boff=0.3, lpos=(612, 164),
            lanchor="start")
    d.box("trace", 20, 318, 840, 48, "Every step is traced",
          ["MLflow trace spans (RETRIEVER, LLM, tokens, latency) → inference table in UC → judges & monitoring"], kind="eval")
    d.arrow("llm", "trace", "spans", sides="bt", aoff=0.35, boff=0.464, dashed=True, lpos=(838, 230), lanchor="start")
    return d


def vs_index():
    d = Diagram("vs-index", 880, 330,
                "Delta Sync index versus Direct Vector Access index: Delta Sync follows a source Delta table through Change "
                "Data Feed, Direct Vector Access is written by your own code.",
                "The difference is who keeps the index fresh. Delta Sync follows a table (deletes propagate too). With Direct "
                "Vector Access your code owns every upsert and delete.")
    d.group(20, 14, 410, 296, "Delta Sync index", kind="data")
    d.group(450, 14, 410, 296, "Direct Vector Access index", kind="data")
    d.box("tbl", 50, 52, 200, 52, "Source Delta table", ["Change Data Feed ON"], kind="data")
    d.box("pipe", 50, 142, 200, 60, "Sync pipeline", ["TRIGGERED: index.sync()", "CONTINUOUS: streams changes"], kind="plain")
    d.box("idx1", 50, 240, 200, 52, "Index", ["catalog.schema.index"], kind="data", accent=True)
    d.box("emb", 280, 146, 130, 52, "Embedding", ["endpoint (managed)"], kind="model")
    d.arrow("tbl", "pipe", "inserts · updates · deletes", lpos=(158, 128), lanchor="start")
    d.arrow("pipe", "idx1", "writes vectors", lpos=(158, 226), lanchor="start")
    d.arrow("emb", "pipe")
    d.text(280, 226, "managed embeddings:", cls="dg-sub")
    d.text(280, 240, "Databricks embeds a", cls="dg-sub")
    d.text(280, 254, "text column. Self-", cls="dg-sub")
    d.text(280, 268, "managed: table has a", cls="dg-sub")
    d.text(280, 282, "vector column.", cls="dg-sub")
    d.box("code", 480, 52, 200, 52, "Your code / pipeline", ["computes embeddings"], kind="app")
    d.box("idx2", 480, 240, 200, 52, "Index", ["catalog.schema.index"], kind="data", accent=True)
    d.arrow("code", "idx2", "upsert() / delete()  (SDK / REST)", lpos=(588, 176), lanchor="start")
    d.text(700, 64, "no source table", cls="dg-note")
    d.text(700, 80, "no automatic sync", cls="dg-note")
    d.text(700, 96, "you handle freshness", cls="dg-note")
    d.text(700, 112, "and deletes", cls="dg-note")
    return d


def vs_config():
    d = Diagram("vs-config", 880, 290,
                "Three Vector Search configuration decisions: endpoint type by scale and latency, sync mode by freshness, "
                "and embedding management by who computes vectors.",
                "Three independent choices. Read the constraint words in the question (latency, cost, freshness, least code) "
                "and pick one branch in each.")
    cols = [("Endpoint type?", [("Standard", ["lowest latency", "~320M vectors", "continuous OK"], "latency critical"),
                                ("Storage-\noptimized", ["1B+ vectors", "cheaper, ~+250 ms", "triggered only"], "huge, cost-sensitive")]),
            ("How fresh?", [("Continuous", ["seconds-fresh", "Standard only", "costs more"], "within seconds"),
                            ("Triggered", ["daily / weekly", "sync() after ETL", "cheapest"], "after each ETL")]),
            ("Who embeds?", [("Managed", ["Delta Sync +", "embedding endpoint", "least code"], "Databricks"),
                             ("Self-managed", ["own vector column", "or Direct Vector", "Access upserts"], "your pipeline")])]
    for c, (q, answers) in enumerate(cols):
        x = 20 + c * 290
        qk = f"q{c}"
        d.box(qk, x, 20, 270, 40, q, kind="plain")
        for j, (label, sub, why) in enumerate(answers):
            ak = f"a{c}{j}"
            d.box(ak, x + j * 140, 128, 130, 92, label, sub, kind="data")
            d.arrow(qk, ak, sides="bt", aoff=(j - 0.5) * 0.5)
            d.text(x + 74 if j == 0 else x + 196, 92 + j * 20, why, cls="dg-elabel", anchor="start" if j == 0 else "end")
    d.text(20, 250, "Too many vectors? Bigger chunks · less overlap · dedupe · drop irrelevant documents.", cls="dg-note dg-strong")
    d.text(20, 272, "Accuracy first and latency allows → hybrid + re-ranker. Latency critical → keep them off.", cls="dg-note")
    return d


def model_lifecycle():
    d = Diagram("model-lifecycle", 900, 330,
                "Agent lifecycle with MLflow: author with ResponsesAgent, log with resources and an input example, register "
                "in Unity Catalog with aliases, deploy with agents.deploy, while prompts live in the Prompt Registry.",
                "Promotion and rollback never change code: move the alias (@champion for models, @production for prompts) "
                "to another immutable version.")
    steps = [("author", "Author", ["agent.py", "ResponsesAgent", "set_model(...)"], "app"),
             ("log", "Log", ["log_model(...)", "resources=[...]", "input_example"], "eval"),
             ("reg", "Register in UC", ["main.rag.hr_agent", "needs a signature", ""], "model"),
             ("dep", "Deploy", ["agents.deploy(", "  name, version)", ""], "model"),
             ("serve", "Serve & watch", ["serving endpoint", "Review App (SMEs)", "inference tables", "MLflow traces"], "app")]
    for i, (k, l, s, kind) in enumerate(steps):
        d.box(k, 20 + i * 177, 40, 152, 140, l, [x for x in s if x], kind=kind, num=i + 1, mono=k in ("author", "dep"),
              top=k == "reg")
    for a, b in zip(steps, steps[1:]):
        d.arrow(a[0], b[0])
    # versions + alias inside Register
    for i, v in enumerate(["v1", "v2", "v3"]):
        d.chip(381 + i * 46, 108, 40, v, kind="plain")
    d.chip(410, 148, 74, "@champion", kind="model")
    d.arrow((447, 148), (447, 130), hot=True)
    d.box("pr", 20, 230, 330, 72, "MLflow Prompt Registry (UC)", ["main.prompts.support_answer"], kind="eval", mono=False)
    for i, v in enumerate(["v1", "v2", "v3"]):
        d.chip(380 + i * 46, 256, 40, v, kind="plain")
    d.chip(536, 256, 92, "@production", kind="eval")
    d.arrow((536, 266), (514, 266), hot=True)
    d.arrow("pr", "author", "load_prompt(\"prompts:/...@production\")", sides="tb", aoff=-0.27, boff=0.0, lpos=(110, 214),
            lanchor="start")
    d.text(650, 262, "versions are immutable", cls="dg-note")
    d.text(650, 278, "aliases move: promote / roll back", cls="dg-note dg-strong")
    return d


def endpoint_auth():
    d = Diagram("endpoint-auth", 880, 310,
                "Three ways a deployed agent authenticates to other resources: automatic passthrough with a short-lived "
                "service principal, on-behalf-of-user credentials, or manual secrets.",
                "Same endpoint, three identities. The identity that reaches the resource decides what data comes back. Only "
                "on-behalf-of-user makes row filters and column masks apply per person.")
    for x, h in [(250, "endpoint"), (470, "identity it uses"), (755, "what it reaches")]:
        d.text(x, 18, h, cls="dg-glabel", anchor="middle")
    rows = [("1 · Automatic", "passthrough · recommended", "Short-lived SP credential", "from resources=[...] at log time",
             "Declared resources", "LLM · VS index · UC function"),
            ("2 · On-behalf-of-user", "UC permissions per user", "End user's credentials", "ModelServingUserCredentials()",
             "UC tables, Genie…", "row filters & masks apply"),
            ("3 · Manual", "external services", "Env vars from secrets", "{{secrets/scope/key}}",
             "External API", "or unsupported resource")]
    for i, (name, why, cred, cs, res, rs) in enumerate(rows):
        y = 34 + i * 84
        d.text(20, y + 26, name, cls="dg-label")
        d.text(20, y + 42, why, cls="dg-sub")
        d.box(f"e{i}", 190, y, 120, 56, "Agent", ["serving endpoint"], kind="app")
        d.box(f"c{i}", 360, y, 220, 56, cred, [cs], kind="gov", mono=(i == 2))
        d.box(f"r{i}", 650, y, 210, 56, res, [rs], kind="data")
        d.arrow(f"e{i}", f"c{i}")
        d.arrow(f"c{i}", f"r{i}")
    d.text(20, 298, "Who may call the endpoint at all is separate: endpoint permissions (CAN QUERY) and AI Gateway rate limits.",
           cls="dg-note")
    return d


def uc_assets():
    d = Diagram("uc-assets", 880, 300,
                "Unity Catalog holds every GenAI asset under catalog.schema: volumes, tables, vector indexes, functions, "
                "models and prompts, all governed by the same privileges.",
                "Everything a GenAI app needs lives under one three-level namespace, so lineage, permissions and CI/CD "
                "promotion (dev → prod catalogs) work the same way for all of it.")
    d.box("ms", 20, 24, 180, 44, "Metastore", kind="plain")
    d.box("cat", 20, 104, 180, 52, "Catalog: main", ["dev / staging / prod"], kind="data")
    d.box("sch", 20, 192, 180, 52, "Schema: main.rag", kind="data")
    d.arrow("ms", "cat", "contains", lpos=(118, 92), lanchor="start")
    d.arrow("cat", "sch", "contains", lpos=(118, 180), lanchor="start")
    d.group(250, 14, 610, 244, "Securables in main.rag")
    leaves = [("Volume", "raw_docs", "PDFs to parse", "data"), ("Table", "doc_chunks", "Delta, CDF on", "data"),
              ("Vector index", "doc_chunks_index", "synced from table", "data"),
              ("Function", "get_order_status", "agent tool", "tool"), ("Model", "hr_agent @champion", "the agent", "model"),
              ("Prompt", "support_answer", "@production", "eval")]
    for i, (l, n, s, kind) in enumerate(leaves):
        x, y = 268 + (i % 3) * 196, 46 + (i // 3) * 104
        d.box(f"l{i}", x, y, 180, 76, l, [n, s], kind=kind)
    d.arrow("sch", (250, 218), sides="r_")
    d.text(20, 286, "Privileges: USE CATALOG → USE SCHEMA → SELECT (tables) · READ VOLUME · EXECUTE (functions, models) · CREATE MODEL",
           cls="dg-note")
    return d


def guardrails():
    d = Diagram("guardrails", 900, 340,
                "Layered guardrails around an agent: input checks, a scoped system prompt, least-privilege tools with human "
                "approval, output checks, and PII masked during data preparation.",
                "Defense in depth. Injected instructions can also arrive through retrieved documents (indirect injection), "
                "so treat retrieved text as data and keep the tools least-privileged.")
    d.box("in", 20, 80, 90, 56, "Request", kind="app")
    d.box("ig", 150, 66, 190, 84, "Input guardrails", ["injection / jailbreak filter", "PII mask · length limit", "rate limit"], kind="gov")
    d.box("ag", 380, 66, 170, 84, "Agent", ["scoped system prompt", "instructions ≠ data"], kind="app", accent=True)
    d.box("og", 590, 66, 190, 84, "Output guardrails", ["safety filter", "PII mask · leak check", "groundedness"], kind="gov")
    d.box("out", 820, 80, 70, 56, "Answer", kind="app")
    for a, b in [("in", "ig"), ("ig", "ag"), ("ag", "og"), ("og", "out")]:
        d.arrow(a, b)
    d.text(245, 52, "AI Gateway guardrails", cls="dg-sub dg-govtext", anchor="middle")
    d.text(685, 52, "AI Gateway guardrails", cls="dg-sub dg-govtext", anchor="middle")
    d.box("docs", 150, 232, 190, 64, "Retrieved documents", ["may hide instructions:", "indirect injection"], kind="data", accent=True)
    d.box("tools", 380, 232, 170, 64, "Tools", ["least privilege · OBO", "approval for actions"], kind="tool")
    d.box("prep", 20, 232, 112, 64, "Data prep", ["ai_mask before", "indexing"], kind="gov")
    d.arrow("prep", "docs")
    d.arrow("docs", "ag", "context", sides="tb", via=((245, 190), (414, 190)), aoff=0, boff=-0.3, lpos=(253, 184), lanchor="start")
    d.arrow("ag", "tools", "calls", sides="bt", aoff=0.15, boff=0.15, lpos=(497, 212), lanchor="start")
    d.text(590, 250, "Watch it in production:", cls="dg-note dg-strong")
    d.text(590, 268, "Safety judge on sampled traces,", cls="dg-note")
    d.text(590, 286, "red-team prompts in the eval set.", cls="dg-note")
    return d


def gateway():
    d = Diagram("gateway", 880, 390,
                "AI Gateway sits in front of serving endpoints and adds rate limits, guardrails, traffic splitting, usage "
                "tracking and inference tables, which land as Unity Catalog and system tables.",
                "One control layer in front of every endpoint type. The two logging features are where monitoring and cost "
                "questions are answered: payloads go to an inference table, token counts to the usage system table.")
    for i, (l, s) in enumerate([("Apps & agents", "REST / SDK"), ("SQL users", "ai_query()"), ("Notebooks", "OpenAI client")]):
        d.box(f"c{i}", 20, 50 + i * 70, 140, 48, l, [s], kind="app")
        d.arrow(f"c{i}", (200, 74 + i * 70), sides="r_")
    d.group(200, 20, 320, 270, "AI Gateway (now Unity Gateway)", kind="gov")
    d.box("rl", 216, 46, 288, 40, "Rate limits", ["QPM / TPM per user, group, SP, endpoint"], kind="gov")
    d.box("gr", 216, 96, 288, 40, "Guardrails", ["safety · PII block or mask, in and out"], kind="gov")
    d.box("ts", 216, 146, 288, 40, "Traffic split & fallbacks", ["A/B % · fail over on errors"], kind="gov")
    d.box("ut", 216, 208, 140, 52, "Usage tracking", ["tokens · requests"], kind="eval")
    d.box("it", 364, 208, 140, 52, "Inference table", ["full payloads"], kind="eval")
    eps = [("Foundation Model API", "pay-per-token"), ("Foundation Model API", "provisioned throughput"),
           ("External models", "OpenAI · Anthropic · Bedrock"), ("Custom model / agent", "your agents.deploy() endpoint")]
    for i, (l, s) in enumerate(eps):
        d.box(f"e{i}", 600, 30 + i * 66, 260, 48, l, [s], kind="model")
        d.arrow((520, 54 + i * 66), f"e{i}", sides="_l")
    d.box("ust", 200, 322, 220, 48, "Usage system table", ["system.serving.endpoint_usage"], kind="data", mono=True)
    d.box("pay", 430, 322, 230, 48, "Inference table (UC Delta)", ["<endpoint>_payload"], kind="data", mono=True)
    d.arrow("ut", (286, 322), sides="b_")
    d.arrow("it", (434, 322), sides="b_")
    return d


def eval_monitor():
    d = Diagram("eval-monitor", 900, 400,
                "Evaluation and monitoring form one loop: offline evaluation with ground truth gates releases, production "
                "monitoring scores sampled live traces without ground truth, and failing traces become new test cases.",
                "Two phases, one loop. Judges that compare against an expected answer only work offline. Production "
                "monitoring uses judges that need no ground truth.")
    d.group(20, 14, 860, 140, "Offline evaluation (before release)", kind="eval")
    d.group(20, 246, 860, 140, "Production monitoring (after deploy)", kind="eval", bottom=True)
    top = [("ds", "Evaluation dataset", ["inputs + expectations"]), ("ev", "Evaluate", ["mlflow.genai.evaluate()", "predict_fn + scorers"]),
           ("gate", "Quality gate", ["compare with baseline run"]), ("dep", "Deploy", ["agents.deploy()"])]
    bot = [("sme", "SME labeling", ["Review App sessions"]), ("sc", "Registered scorers", ["sampled · + user feedback"]),
           ("tr", "Inference tables", ["traces of every request"]), ("live", "Live traffic", ["real users"])]
    for i, ((k1, l1, s1), (k2, l2, s2)) in enumerate(zip(top, bot)):
        x = 44 + i * 212
        d.box(k1, x, 54, 188, 60, l1, s1, kind="app" if k1 == "dep" else "eval", mono=(k1 == "ev"))
        d.box(k2, x, 286, 188, 60, l2, s2, kind="app" if k2 == "live" else "eval")
    for a, b in zip(top, top[1:]):
        d.arrow(a[0], b[0])
    for a, b in zip(bot[::-1], bot[::-1][1:]):
        d.arrow(a[0], b[0])
    d.arrow("dep", "live", "users", sides="bt", lpos=(738, 204), lanchor="end")
    d.arrow("sme", "ds", "corrected answers → expectations", sides="tb", hot=True, lpos=(146, 204), lanchor="start")
    d.text(450, 176, "Offline can use ground truth: Correctness · RetrievalSufficiency · ToolCallCorrectness", cls="dg-sub dg-strong", anchor="middle")
    d.text(450, 228, "Online has none: Safety · RelevanceToQuery · RetrievalGroundedness · Guidelines", cls="dg-sub dg-strong", anchor="middle")
    return d


DIAGRAMS = {f().id: f for f in [lifecycle, which_tool, rag_ingest, chunking, retrieval, agent_loop, multi_agent, mcp,
                                 rag_query, vs_index, vs_config, model_lifecycle, endpoint_auth, uc_assets, guardrails,
                                 gateway, eval_monitor]}


def render(did):
    return DIAGRAMS[did]().figure()


if __name__ == "__main__":
    for k in DIAGRAMS:
        render(k)
    print("\n".join(warnings) or "all labels fit")
