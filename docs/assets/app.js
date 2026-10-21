/* GenAI Engineer Associate Prep: single-page app (vanilla JS, no build step). */
(() => {
  "use strict";
  const E = window.EXAM;
  const app = document.getElementById("app");
  const LETTERS = "ABCDEFGH";
  const SECTION_IDS = Object.keys(E.sections);
  const MOCK_MINUTES = 90;

  /* ---------------- utils ---------------- */
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const pct = (n, d) => (d ? Math.round((100 * n) / d) : 0);
  const byId = Object.fromEntries(E.questions.map((q) => [q.id, q]));
  const secName = (sid) => (E.sections[sid] ? `§${sid.slice(1)} ${E.sections[sid].name}` : sid);
  const h = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };

  /* ---------------- persistent state (per browser) ---------------- */
  const KEY = "gaiexam.v1";
  const defaults = () => ({ hist: {}, obj: {}, flash: {}, labs: {}, mocks: [], examDate: "", theme: "", mockActive: null });
  let S = defaults();
  try { S = Object.assign(defaults(), JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) { /* storage unavailable */ }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* ignore */ } };

  function record(q, correct) {
    const r = S.hist[q.id] || { seen: 0, correct: 0, wrong: 0, last: null };
    r.seen++; correct ? r.correct++ : r.wrong++; r.last = correct; r.ts = Date.now();
    S.hist[q.id] = r; save();
  }
  function sectionStats(sid) {
    const qs = E.questions.filter((q) => !sid || q.section === sid);
    const seen = qs.filter((q) => S.hist[q.id]);
    const mastered = qs.filter((q) => S.hist[q.id] && S.hist[q.id].last === true);
    return { total: qs.length, seen: seen.length, mastered: mastered.length, mastery: pct(mastered.length, qs.length) };
  }
  function objectiveStats(objective) {
    const qs = E.questions.filter((q) => q.objective === objective && S.hist[q.id]);
    return { seen: qs.length, right: qs.filter((q) => S.hist[q.id].last).length };
  }

  /* ---------------- theme ---------------- */
  const themeSel = document.getElementById("theme-sel");
  function applyTheme() {
    const t = S.theme;
    if (t) document.documentElement.setAttribute("data-theme", t); else document.documentElement.removeAttribute("data-theme");
    const light = document.getElementById("hl-light"), dark = document.getElementById("hl-dark");
    light.media = t === "dark" ? "not all" : t === "light" ? "all" : "(prefers-color-scheme: light)";
    dark.media = t === "light" ? "not all" : t === "dark" ? "all" : "(prefers-color-scheme: dark)";
    themeSel.value = t;
  }
  themeSel.addEventListener("change", () => { S.theme = themeSel.value; save(); applyTheme(); });
  applyTheme();
  document.getElementById("repo-link").href = E.repo;

  /* ---------------- navigation ---------------- */
  const sidebar = document.getElementById("sidebar");
  document.getElementById("menu-btn").addEventListener("click", () => sidebar.classList.toggle("open"));

  function renderNav(route) {
    const link = (href, label, extra = "") => `<a href="${href}" class="${("#" + route.path).startsWith(href) && href !== "#/" || (href === "#/" && route.path === "/") ? "active" : ""}">${label}${extra}</a>`;
    const secLinks = SECTION_IDS.map((sid) => link(`#/notes/${sid}`, `§${sid.slice(1)} ${esc(E.sections[sid].name)}`, `<span class="pct">${sectionStats(sid).mastery}%</span>`)).join("");
    document.getElementById("nav").innerHTML = `
      ${link("#/", "🏠 Dashboard")}
      ${link("#/notes/plan", "🗓️ Study plan & checklist")}
      ${link("#/notes/overview", "⚠️ Exam overview & renames")}
      <div class="group">Study notes</div>${secLinks}
      <div class="group">Practice</div>
      ${link("#/practice", "✍️ Practice questions")}
      ${link("#/mock", "⏱️ Mock exam (45 / 90 min)")}
      ${link("#/scenarios", "🧩 Design scenarios")}
      ${link("#/review", "🔁 Review mistakes", `<span class="pct">${Object.values(S.hist).filter((r) => r.last === false).length}</span>`)}
      <div class="group">Reference</div>
      ${link("#/flashcards", "🃏 Flashcards")}
      ${link("#/glossary", "📖 Glossary & renames")}
      ${link("#/labs", "🧪 Hands-on labs")}`;
  }

  function parseRoute() {
    const raw = location.hash.replace(/^#/, "") || "/";
    const [path, qs] = raw.split("?");
    const parts = path.split("/").filter(Boolean);
    return { path, parts, query: new URLSearchParams(qs || "") };
  }

  const routes = {
    "": viewHome, notes: viewNotes, practice: viewPractice, mock: viewMock, scenarios: viewScenarios,
    review: viewReview, flashcards: viewFlashcards, glossary: viewGlossary, labs: viewLabs, settings: viewSettings,
  };

  function render() {
    const route = parseRoute();
    renderNav(route);
    sidebar.classList.remove("open");
    if (timerHandle && route.parts[0] !== "mock") { clearInterval(timerHandle); timerHandle = null; }
    app.innerHTML = "";
    (routes[route.parts[0] || ""] || viewHome)(route);
    app.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", render);

  /* ---------------- question widget ---------------- */
  // Renders a question; returns {el, getSelection(), reveal()}. `order` maps display index -> original option index.
  function questionWidget(q, { order, selected = [], locked = false, showResult = false, number, onChange } = {}) {
    order = order || q.options.map((_, i) => i);
    const multi = q.answer.length > 1;
    const name = "q_" + q.id + "_" + Math.random().toString(36).slice(2, 7);
    const el = h(`<div class="card question">
      <div class="q-meta">
        ${number ? `<span class="tag">Q${number}</span>` : ""}
        <span class="tag accent">${esc(secName(q.section || ""))}</span>
        ${q.objective ? `<span class="tag" title="Exam objective">${esc(q.objective)}</span>` : ""}
        ${multi ? `<span class="tag" style="color:var(--warn)">Select ${q.answer.length}</span>` : ""}
      </div>
      <div class="q-stem">${esc(q.q)}</div>
      <div class="opts"></div>
      <div class="result"></div>
    </div>`);
    const optsEl = el.querySelector(".opts");
    const sel = new Set(selected);
    order.forEach((orig, di) => {
      const opt = h(`<label class="opt"><input type="${multi ? "checkbox" : "radio"}" name="${name}" value="${orig}"><span class="letter">${LETTERS[di]}.</span><span>${esc(q.options[orig])}</span></label>`);
      const input = opt.querySelector("input");
      input.checked = sel.has(orig);
      input.disabled = locked;
      if (locked) opt.classList.add("locked");
      input.addEventListener("change", () => {
        if (!multi) sel.clear();
        input.checked ? sel.add(orig) : sel.delete(orig);
        if (multi && sel.size > q.answer.length) { sel.delete(orig); input.checked = false; }
        onChange && onChange([...sel]);
      });
      optsEl.appendChild(opt);
    });
    function reveal() {
      const correct = isCorrect(q, [...sel]);
      optsEl.querySelectorAll(".opt").forEach((o) => {
        const orig = +o.querySelector("input").value;
        o.querySelector("input").disabled = true; o.classList.add("locked");
        if (q.answer.includes(orig)) o.classList.add("correct");
        else if (sel.has(orig)) o.classList.add("wrong");
      });
      const right = order.map((orig, di) => (q.answer.includes(orig) ? LETTERS[di] : null)).filter(Boolean).join(", ");
      el.querySelector(".result").innerHTML = `<div class="explain ${correct ? "ok" : "bad"}">
        <span class="verdict ${correct ? "ok" : "bad"}">${correct ? "✔ Correct" : "✘ Incorrect"}</span>
        <span class="muted">· Answer: ${right}</span><div style="margin-top:6px">${esc(q.explain)}</div>
        ${q.section && E.sections[q.section] ? `<div style="margin-top:6px"><a href="#/notes/${q.section}">Review ${esc(secName(q.section))} notes →</a></div>` : ""}</div>`;
      return correct;
    }
    if (showResult) reveal();
    return { el, getSelection: () => [...sel], reveal };
  }
  const isCorrect = (q, sel) => sel.length === q.answer.length && sel.every((s) => q.answer.includes(s));
  const makeItem = (q) => ({ id: q.id, order: shuffle(q.options.map((_, i) => i)) });

  /* ---------------- dashboard ---------------- */
  function viewHome() {
    const all = sectionStats();
    const mocks = S.mocks;
    const best = mocks.length ? Math.max(...mocks.map((m) => pct(m.score, m.total))) : null;
    const known = Object.values(S.flash).filter((b) => b >= 2).length;
    let countdown = "";
    if (S.examDate) {
      const days = Math.ceil((new Date(S.examDate + "T09:00:00") - new Date()) / 864e5);
      countdown = days >= 0 ? `<b>${days}</b> day${days === 1 ? "" : "s"} to go` : "Exam date passed";
    }
    app.innerHTML = `
      <h1>Databricks Generative AI Engineer Associate</h1>
      <p class="sub">An interactive prep guide for the <b>exam version published March 18, 2026</b>. It has notes per objective, ${E.questions.length} practice questions, weighted 45-question mock exams, design scenarios, flashcards and ${E.labs.length} hands-on Databricks labs.</p>
      <div class="callout warn"><b>Naming trap:</b> several products were renamed after the exam was written (Vector Search → AI Search, AI Gateway → Unity Gateway, Genie Spaces → Genie Agents…). The exam uses the March 2026 names. <a href="#/notes/overview">See the full table →</a></div>
      <div class="grid">
        <div class="card"><div class="label">Question mastery</div><div class="stat">${all.mastery}%</div><div class="bar" style="margin-top:8px"><span style="width:${all.mastery}%"></span></div><div class="label" style="margin-top:6px">${all.mastered} of ${all.total} answered correctly last time · ${all.seen} seen</div></div>
        <div class="card"><div class="label">Mock exams</div><div class="stat">${mocks.length}</div><div class="label">${best === null ? "none yet" : `best ${best}% · last ${pct(mocks[mocks.length - 1].score, mocks[mocks.length - 1].total)}%`}</div></div>
        <div class="card"><div class="label">Flashcards known</div><div class="stat">${known}<span class="label"> / ${E.glossary.length}</span></div></div>
        <div class="card"><div class="label">Exam date</div><input type="date" id="exam-date" value="${esc(S.examDate)}" style="margin:6px 0"><div class="label">${countdown || "Set your date for a countdown"}</div></div>
      </div>
      <div class="row" style="margin:16px 0">
        <a class="btn primary" href="#/practice">✍️ Practice questions</a>
        <a class="btn" href="#/mock">⏱️ Take a mock exam</a>
        <a class="btn" href="#/scenarios">🧩 Scenarios</a>
        <a class="btn" href="#/flashcards">🃏 Flashcards</a>
      </div>
      <h2>Sections</h2>
      <div class="card" style="padding:6px 16px">
        ${SECTION_IDS.map((sid) => { const s = sectionStats(sid), sec = E.sections[sid]; return `
          <div style="padding:10px 0;border-bottom:1px solid var(--border)">
            <div class="row"><b>§${sid.slice(1)} ${esc(sec.name)}</b><span class="tag">${sec.weight}% · ~${sec.mock} questions</span><span class="spacer"></span>
              <a class="btn small" href="#/notes/${sid}">Notes</a><a class="btn small" href="#/practice?s=${sid}&go=1">Practice</a></div>
            <div class="row" style="margin-top:6px"><div class="bar" style="flex:1"><span style="width:${s.mastery}%"></span></div><span class="label" style="min-width:110px;text-align:right">${s.mastered}/${s.total} mastered</span></div>
          </div>`; }).join("")}
      </div>
      ${mocks.length ? `<h2>Mock exam history</h2><div class="card">${mocks.slice(-8).reverse().map((m) => `<div class="row" style="padding:4px 0"><span>${new Date(m.date).toLocaleString()}</span><span class="spacer"></span><b>${pct(m.score, m.total)}%</b><span class="muted">(${m.score}/${m.total}, ${Math.round(m.secs / 60)} min)</span></div>`).join("")}</div>` : ""}
      <h2>How to use this guide</h2>
      <ol>
        <li><b>Diagnose:</b> take a 10-question practice quiz per section <i>before</i> reading.</li>
        <li><b>Learn & build:</b> read the notes for weak sections and do the matching labs in Databricks Free Edition.</li>
        <li><b>Drill:</b> flashcards daily, scenarios for design thinking, and <i>Review mistakes</i> to redo what you missed.</li>
        <li><b>Simulate:</b> timed mock exams in the final weeks. Aim for a steady ≥ 80%.</li>
      </ol>`;
    document.getElementById("exam-date").addEventListener("change", (e) => { S.examDate = e.target.value; save(); render(); });
  }

  /* ---------------- notes ---------------- */
  function viewNotes(route) {
    const id = route.parts[1] || "overview";
    const note = E.notes.find((n) => n.id === id);
    if (!note) { app.innerHTML = "<p>Not found.</p>"; return; }
    const isSection = !!E.sections[id];
    let header = "";
    if (isSection) {
      const objectives = [...new Set(E.questions.filter((q) => q.section === id).map((q) => q.objective))];
      const st = sectionStats(id);
      header = `
        <div class="row" style="margin-bottom:6px"><span class="tag accent">${E.sections[id].weight}% of exam</span><span class="tag">~${E.sections[id].mock} scored questions</span><span class="tag">${st.total} practice questions · ${st.mastery}% mastered</span></div>
        <div class="row" style="margin:10px 0 4px"><a class="btn primary" href="#/practice?s=${id}&go=1">Practice this section</a><a class="btn" href="#/flashcards?s=${id}">Flashcards for this section</a></div>
        <details class="card"><summary><b>Self-assessment: rate each objective</b> <span class="muted">(tick when confident; accuracy from your practice)</span></summary>
          <ul class="objectives" style="padding-left:0">${objectives.map((o, i) => { const os = objectiveStats(o); const key = id + ":" + o; return `
            <li><label><input type="checkbox" data-obj="${esc(key)}" ${S.obj[key] ? "checked" : ""}><span>${esc(o)} <span class="muted">${os.seen ? `· ${os.right}/${os.seen} right` : "· not practised"}</span></span></label></li>`; }).join("")}</ul>
        </details>`;
    }
    const toc = (note.toc || []).flatMap((t) => t.children && t.level === 1 ? t.children : [t]).filter((t) => t.level === 2);
    app.innerHTML = `${header}
      ${toc.length > 3 ? `<details class="card toc"><summary><b>On this page</b></summary><ul>${toc.map((t) => `<li><a href="#" data-anchor="${esc(t.id)}">${esc(t.name)}</a></li>`).join("")}</ul></details>` : ""}
      <article class="notes">${note.html}</article>
      ${isSection ? `<div class="row" style="margin-top:24px"><a class="btn primary" href="#/practice?s=${id}&go=1">Practice ${esc(secName(id))} →</a></div>` : ""}`;
    app.querySelectorAll("[data-obj]").forEach((cb) => cb.addEventListener("change", () => { S.obj[cb.dataset.obj] = cb.checked; save(); }));
    app.querySelectorAll("[data-anchor]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); const t = document.getElementById(a.dataset.anchor); t && t.scrollIntoView({ behavior: "smooth" }); }));
    highlight();
  }
  function highlight() {
    const run = () => window.hljs && app.querySelectorAll("pre code").forEach((b) => window.hljs.highlightElement(b));
    window.hljs ? run() : window.addEventListener("load", run, { once: true });
  }

  /* ---------------- practice ---------------- */
  let session = null;
  function viewPractice(route) {
    const pre = route.query.get("s");
    if (route.query.get("go") && pre) { startPractice({ sections: [pre], count: 10, filter: "smart" }); return; }
    if (route.parts[1] === "run" && session) { runPractice(); return; }
    app.innerHTML = `
      <h1>Practice questions</h1>
      <p class="sub">Immediate feedback after each question. Options are shuffled every time.</p>
      <div class="card">
        <h3 style="margin-top:0">Sections</h3>
        <div class="row">${SECTION_IDS.map((sid) => `<label class="tag" style="cursor:pointer;padding:5px 10px"><input type="checkbox" name="sec" value="${sid}" ${!pre || pre === sid ? "checked" : ""}> ${esc(secName(sid))} (${sectionStats(sid).total})</label>`).join("")}</div>
        <h3>Questions</h3>
        <div class="row">
          <select id="count"><option value="10">10 questions</option><option value="20">20 questions</option><option value="45">45 questions</option><option value="9999">All matching</option></select>
          <select id="filter">
            <option value="smart">Smart: unseen & missed first</option>
            <option value="all">Random from all</option>
            <option value="unseen">Unseen only</option>
            <option value="missed">Missed last time only</option>
          </select>
          <span class="spacer"></span><button class="btn primary" id="start">Start</button>
        </div>
      </div>`;
    document.getElementById("start").addEventListener("click", () => {
      const sections = [...app.querySelectorAll("input[name=sec]:checked")].map((i) => i.value);
      startPractice({ sections, count: +document.getElementById("count").value, filter: document.getElementById("filter").value });
    });
  }
  function pickQuestions({ sections, count, filter, ids }) {
    let pool = ids ? ids.map((id) => byId[id]) : E.questions.filter((q) => sections.includes(q.section));
    if (filter === "unseen") pool = pool.filter((q) => !S.hist[q.id]);
    if (filter === "missed") pool = pool.filter((q) => S.hist[q.id] && S.hist[q.id].last === false);
    pool = shuffle(pool);
    if (filter === "smart") {
      const rank = (q) => { const r = S.hist[q.id]; return !r ? 1 : r.last === false ? 0 : 2; };
      pool.sort((a, b) => rank(a) - rank(b));
    }
    return pool.slice(0, count);
  }
  function startPractice(opts) {
    const qs = pickQuestions(opts);
    if (!qs.length) { app.innerHTML = `<h1>Practice</h1><div class="card">No questions match that filter. <a href="#/practice">Back</a></div>`; return; }
    session = { items: qs.map(makeItem), idx: 0, results: {}, selections: {} };
    if (location.hash !== "#/practice/run") location.hash = "#/practice/run"; else runPractice();
  }
  function runPractice() {
    const s = session;
    if (s.idx >= s.items.length) return practiceSummary();
    const item = s.items[s.idx], q = byId[item.id];
    const done = item.id in s.results;
    app.innerHTML = `<div class="row"><h1 style="margin:0">Practice</h1><span class="spacer"></span><span class="muted">${s.idx + 1} / ${s.items.length} · ${Object.values(s.results).filter(Boolean).length} correct</span></div>
      <div class="bar" style="margin:10px 0"><span style="width:${pct(s.idx, s.items.length)}%"></span></div>`;
    const w = questionWidget(q, { order: item.order, selected: s.selections[item.id] || [], showResult: done, locked: done, onChange: (sel) => { s.selections[item.id] = sel; btn.disabled = sel.length !== q.answer.length; } });
    app.appendChild(w.el);
    const bar = h(`<div class="row"><button class="btn" id="prev" ${s.idx === 0 ? "disabled" : ""}>← Back</button><span class="spacer"></span><button class="btn primary" id="act"></button></div>`);
    app.appendChild(bar);
    const btn = bar.querySelector("#act");
    const setNext = () => { btn.textContent = s.idx + 1 < s.items.length ? "Next →" : "Finish"; btn.disabled = false; btn.onclick = () => { s.idx++; runPractice(); }; };
    if (done) setNext();
    else {
      btn.textContent = "Check answer"; btn.disabled = true;
      btn.onclick = () => { const ok = w.reveal(); s.results[item.id] = ok; record(q, ok); renderNav(parseRoute()); setNext(); };
    }
    bar.querySelector("#prev").onclick = () => { s.idx--; runPractice(); };
  }
  function practiceSummary() {
    const s = session, ids = s.items.map((i) => i.id);
    const right = ids.filter((id) => s.results[id]).length;
    const missed = ids.filter((id) => s.results[id] === false);
    app.innerHTML = `<h1>Session complete</h1>
      <div class="card"><div class="stat">${pct(right, ids.length)}%</div><div class="label">${right} of ${ids.length} correct</div></div>
      ${missed.length ? `<h2>Missed (${missed.length})</h2>${missed.map((id) => `<div class="card"><div class="q-meta"><span class="tag accent">${esc(secName(byId[id].section))}</span></div><div>${esc(byId[id].q)}</div><div class="explain" style="margin-top:8px"><b>Answer:</b> ${byId[id].answer.map((a) => esc(byId[id].options[a])).join(" <b>+</b> ")}<div class="muted" style="margin-top:4px">${esc(byId[id].explain)}</div></div></div>`).join("")}` : ""}
      <div class="row">${missed.length ? `<button class="btn primary" id="retry">Retry missed</button>` : ""}<a class="btn" href="#/practice">New session</a><a class="btn" href="#/">Dashboard</a></div>`;
    const r = document.getElementById("retry");
    r && r.addEventListener("click", () => startPractice({ ids: missed, count: 999, filter: "all" }));
  }

  /* ---------------- review mistakes ---------------- */
  function viewReview() {
    const missed = E.questions.filter((q) => S.hist[q.id] && S.hist[q.id].last === false);
    const shaky = E.questions.filter((q) => S.hist[q.id] && S.hist[q.id].last === true && S.hist[q.id].wrong > 0);
    app.innerHTML = `<h1>Review mistakes</h1>
      <p class="sub">Questions whose <b>most recent</b> attempt was wrong. Answer one correctly and it leaves this list. For each miss, ask yourself <i>which constraint word you overlooked</i>.</p>
      <div class="row"><button class="btn primary" id="go" ${missed.length ? "" : "disabled"}>Practice ${missed.length} missed</button>
      <button class="btn" id="go2" ${shaky.length ? "" : "disabled"}>Practice ${shaky.length} "shaky" (right now, wrong before)</button></div>
      ${SECTION_IDS.map((sid) => { const m = missed.filter((q) => q.section === sid); return m.length ? `<h2>${esc(secName(sid))} (${m.length})</h2>${m.map((q) => `<div class="card"><div class="muted" style="font-size:13px">${esc(q.objective)}</div><div>${esc(q.q)}</div><details style="margin-top:6px"><summary>Show answer</summary><div class="explain"><b>${q.answer.map((a) => esc(q.options[a])).join(" + ")}</b><div class="muted" style="margin-top:4px">${esc(q.explain)}</div></div></details></div>`).join("")}` : ""; }).join("") || `<div class="card">Nothing to review yet 🎉</div>`}`;
    document.getElementById("go").onclick = () => startPractice({ ids: missed.map((q) => q.id), count: 999, filter: "all" });
    document.getElementById("go2").onclick = () => startPractice({ ids: shaky.map((q) => q.id), count: 999, filter: "all" });
  }

  /* ---------------- mock exam ---------------- */
  let timerHandle = null;
  function viewMock(route) {
    if (route.parts[1] === "run" && S.mockActive) return runMock();
    if (route.parts[1] === "result" && S.mocks.length) return mockResult(S.mocks[S.mocks.length - 1]);
    app.innerHTML = `<h1>Mock exam</h1>
      <p class="sub">Matches the real exam's format: <b>45 scored questions in ${MOCK_MINUTES} minutes</b>, spread across sections by the official weights. You get no feedback until you submit. You can flag questions and jump around.</p>
      <div class="card"><table style="width:100%;border-collapse:collapse">${SECTION_IDS.map((sid) => `<tr><td style="padding:4px 0">${esc(secName(sid))}</td><td style="text-align:right">${E.sections[sid].weight}%</td><td style="text-align:right;padding-left:16px"><b>${E.sections[sid].mock}</b> q</td></tr>`).join("")}</table></div>
      <div class="callout">Databricks doesn't print a passing score in this exam guide. As a practical target, aim for <b>80%+</b> on mocks before you book. Questions are randomly drawn from the bank, so retakes differ.</div>
      ${S.mockActive ? `<div class="callout warn">You have a mock in progress. <a href="#/mock/run">Resume it</a> or start a new one.</div>` : ""}
      <div class="row"><button class="btn primary" id="start">Start new mock exam</button>${S.mocks.length ? `<a class="btn" href="#/mock/result">Last result</a>` : ""}</div>`;
    document.getElementById("start").onclick = () => {
      const ids = SECTION_IDS.flatMap((sid) => shuffle(E.questions.filter((q) => q.section === sid)).slice(0, E.sections[sid].mock).map((q) => q.id));
      S.mockActive = { items: shuffle(ids).map((id) => makeItem(byId[id])), answers: {}, flags: {}, idx: 0, start: Date.now() };
      save(); location.hash = "#/mock/run";
    };
  }
  function runMock() {
    const m = S.mockActive;
    const deadline = m.start + MOCK_MINUTES * 60e3;
    const draw = () => {
      const item = m.items[m.idx], q = byId[item.id];
      const answered = Object.keys(m.answers).filter((k) => m.answers[k].length).length;
      app.innerHTML = `<div class="exam-head"><div class="row"><b>Mock exam</b><span class="muted">Q ${m.idx + 1} / ${m.items.length} · answered ${answered}</span><span class="spacer"></span><span class="timer" id="timer"></span><button class="btn small" id="submit">Submit</button></div></div>`;
      const w = questionWidget({ ...q, objective: "" }, { order: item.order, selected: m.answers[item.id] || [], number: m.idx + 1, onChange: (sel) => { m.answers[item.id] = sel; save(); updateGrid(); } });
      w.el.querySelector(".tag.accent").remove();   // hide section in exam mode
      app.appendChild(w.el);
      const ctrl = h(`<div class="row"><button class="btn" id="prev" ${m.idx === 0 ? "disabled" : ""}>← Prev</button>
        <button class="btn" id="flag">${m.flags[item.id] ? "🚩 Unflag" : "🏳️ Flag for review"}</button><span class="spacer"></span>
        <button class="btn primary" id="next">${m.idx + 1 < m.items.length ? "Next →" : "Review & submit"}</button></div>`);
      app.appendChild(ctrl);
      const grid = h(`<div class="card"><div class="label" style="margin-bottom:8px">Navigator · <span style="color:var(--warn)">●</span> flagged</div><div class="navgrid"></div></div>`);
      app.appendChild(grid);
      function updateGrid() {
        grid.querySelector(".navgrid").innerHTML = m.items.map((it, i) => `<button data-i="${i}" class="${(m.answers[it.id] || []).length ? "answered" : ""} ${m.flags[it.id] ? "flagged" : ""} ${i === m.idx ? "current" : ""}">${i + 1}</button>`).join("");
        grid.querySelectorAll("button").forEach((b) => (b.onclick = () => { m.idx = +b.dataset.i; save(); draw(); }));
      }
      updateGrid();
      ctrl.querySelector("#prev").onclick = () => { m.idx--; save(); draw(); };
      ctrl.querySelector("#next").onclick = () => { if (m.idx + 1 < m.items.length) { m.idx++; save(); draw(); } else confirmSubmit(); };
      ctrl.querySelector("#flag").onclick = () => { m.flags[item.id] = !m.flags[item.id]; save(); draw(); };
      document.getElementById("submit").onclick = confirmSubmit;
      tick();
    };
    const confirmSubmit = () => {
      const unanswered = m.items.filter((it) => !(m.answers[it.id] || []).length).length;
      const flagged = m.items.filter((it) => m.flags[it.id]).length;
      if (confirm(`Submit the exam?\n\nUnanswered: ${unanswered}\nFlagged: ${flagged}`)) finishMock();
    };
    const tick = () => {
      const left = Math.max(0, deadline - Date.now());
      const t = document.getElementById("timer");
      if (t) { const mm = Math.floor(left / 60e3), ss = Math.floor((left % 60e3) / 1e3); t.textContent = `⏱ ${mm}:${String(ss).padStart(2, "0")}`; t.classList.toggle("low", left < 10 * 60e3); }
      if (left <= 0) { alert("Time is up. Submitting your exam."); finishMock(); }
    };
    if (timerHandle) clearInterval(timerHandle);
    timerHandle = setInterval(tick, 1000);
    draw();
  }
  function finishMock() {
    clearInterval(timerHandle); timerHandle = null;
    const m = S.mockActive; if (!m) return;
    const bySection = {}; let score = 0;
    const detail = m.items.map((it) => {
      const q = byId[it.id], sel = m.answers[it.id] || [], ok = isCorrect(q, sel);
      record(q, ok); if (ok) score++;
      (bySection[q.section] = bySection[q.section] || [0, 0])[1]++; if (ok) bySection[q.section][0]++;
      return { id: it.id, order: it.order, sel, ok };
    });
    const result = { date: Date.now(), score, total: m.items.length, bySection, secs: Math.round((Date.now() - m.start) / 1000), detail };
    S.mocks.push(result); S.mockActive = null;
    if (S.mocks.length > 30) S.mocks = S.mocks.slice(-30);
    save(); location.hash = "#/mock/result";
  }
  function mockResult(r) {
    const p = pct(r.score, r.total);
    app.innerHTML = `<h1>Mock exam result</h1>
      <div class="grid"><div class="card"><div class="label">Score</div><div class="stat" style="color:${p >= 80 ? "var(--ok)" : p >= 70 ? "var(--warn)" : "var(--bad)"}">${p}%</div><div class="label">${r.score} / ${r.total} · ${Math.round(r.secs / 60)} min</div></div>
      <div class="card"><div class="label">Readiness</div><div style="font-weight:600;margin-top:6px">${p >= 80 ? "On track. Keep it consistent across a few mocks." : p >= 70 ? "Borderline. Work on your weakest sections below." : "Not yet. Go back to the notes and labs for weak sections."}</div></div></div>
      <h2>By section</h2><div class="card">${SECTION_IDS.map((sid) => { const [c, t] = r.bySection[sid] || [0, 0]; return `<div style="margin:8px 0"><div class="row"><span>${esc(secName(sid))}</span><span class="spacer"></span><b>${c}/${t}</b></div><div class="bar"><span style="width:${pct(c, t)}%;background:${pct(c, t) >= 80 ? "var(--ok)" : pct(c, t) >= 60 ? "var(--warn)" : "var(--bad)"}"></span></div></div>`; }).join("")}</div>
      <div class="row" style="margin:12px 0"><label><input type="checkbox" id="wrong-only" checked> Show only incorrect</label><span class="spacer"></span><a class="btn" href="#/review">Review mistakes</a><a class="btn primary" href="#/mock">New mock</a></div>
      <div id="details"></div>`;
    const drawDetails = () => {
      const only = document.getElementById("wrong-only").checked, box = document.getElementById("details");
      box.innerHTML = "";
      (r.detail || []).forEach((d, i) => { if (only && d.ok) return; const w = questionWidget(byId[d.id], { order: d.order, selected: d.sel, locked: true, showResult: true, number: i + 1 }); box.appendChild(w.el); });
      if (!box.children.length) box.innerHTML = `<div class="card">No incorrect answers 🎉</div>`;
    };
    document.getElementById("wrong-only").onchange = drawDetails;
    drawDetails();
  }

  /* ---------------- scenarios ---------------- */
  function viewScenarios(route) {
    const id = route.parts[1];
    if (!id) {
      app.innerHTML = `<h1>Design scenarios</h1><p class="sub">Multi-step case studies like the exam's scenario questions. Each decision builds on the one before.</p>
        <div class="grid">${E.scenarios.map((s) => `<a class="card" href="#/scenarios/${s.id}" style="text-decoration:none;color:inherit"><b>${esc(s.title)}</b><div class="label" style="margin:6px 0">${s.steps.length} decisions</div><div class="row">${s.sections.map((x) => `<span class="tag">§${x.slice(1)}</span>`).join("")}</div></a>`).join("")}</div>`;
      return;
    }
    const s = E.scenarios.find((x) => x.id === id);
    if (!s) { app.innerHTML = "Not found"; return; }
    app.innerHTML = `<a href="#/scenarios">← All scenarios</a><h1>${esc(s.title)}</h1><div class="card" style="white-space:pre-wrap">${esc(s.context.trim())}</div><div id="steps"></div>`;
    const box = document.getElementById("steps");
    let score = 0;
    const showStep = (i) => {
      if (i >= s.steps.length) { box.appendChild(h(`<div class="card"><b>Scenario complete:</b> ${score} / ${s.steps.length} decisions correct. <a href="#/scenarios">Try another →</a></div>`)); return; }
      const st = { ...s.steps[i], section: "" };
      const w = questionWidget(st, { order: shuffle(st.options.map((_, k) => k)), number: i + 1, onChange: (sel) => (btn.disabled = sel.length !== st.answer.length) });
      w.el.querySelector(".tag.accent").remove();
      const btn = h(`<button class="btn primary" disabled>Check</button>`);
      w.el.appendChild(btn);
      btn.onclick = () => { if (w.reveal()) score++; btn.remove(); showStep(i + 1); };
      box.appendChild(w.el);
    };
    showStep(0);
  }

  /* ---------------- flashcards ---------------- */
  function viewFlashcards(route) {
    const sec = route.query.get("s") || "";
    let deck = E.glossary.filter((t) => !sec || t.section === sec);
    const box = (t) => S.flash[t.term] || 0;
    deck = shuffle(deck).sort((a, b) => box(a) - box(b));
    let i = 0, flipped = false;
    app.innerHTML = `<h1>Flashcards</h1>
      <div class="row" style="margin-bottom:12px"><select id="fsec"><option value="">All sections (${E.glossary.length})</option>${SECTION_IDS.map((sid) => `<option value="${sid}" ${sid === sec ? "selected" : ""}>${esc(secName(sid))}</option>`).join("")}</select>
      <span class="spacer"></span><span class="muted" id="fprog"></span></div>
      <div class="flash" id="card"><div class="flash-inner"><div class="flash-face front"></div><div class="flash-face back"></div></div></div>
      <div class="row" style="margin-top:14px;justify-content:center"><button class="btn" id="again">✘ Again <span class="kbd">1</span></button><button class="btn" id="flip">Flip <span class="kbd">Space</span></button><button class="btn primary" id="good">✔ Knew it <span class="kbd">2</span></button></div>
      <p class="muted" style="text-align:center;font-size:13px">Cards you miss come back first. A card counts as "known" after 2 correct reviews in a row.</p>`;
    const card = document.getElementById("card");
    const draw = () => {
      if (!deck.length) { card.innerHTML = `<div class="card">No cards.</div>`; return; }
      const t = deck[i % deck.length];
      card.classList.remove("flipped"); flipped = false;
      card.querySelector(".front").innerHTML = `<div class="flash-term">${esc(t.term)}</div><div class="label" style="margin-top:10px">${esc(secName(t.section))}</div>`;
      card.querySelector(".back").innerHTML = `<div><b>${esc(t.term)}</b>${t.now ? `<div class="now">Now called: ${esc(t.now)}</div>` : ""}<p>${esc(t.def)}</p></div>`;
      document.getElementById("fprog").textContent = `Card ${(i % deck.length) + 1} / ${deck.length} · known ${deck.filter((x) => box(x) >= 2).length}`;
    };
    const flip = () => { flipped = !flipped; card.classList.toggle("flipped", flipped); };
    const grade = (ok) => { const t = deck[i % deck.length]; S.flash[t.term] = ok ? Math.min(3, box(t) + 1) : 0; save(); i++; draw(); };
    card.onclick = flip;
    document.getElementById("flip").onclick = flip;
    document.getElementById("again").onclick = () => grade(false);
    document.getElementById("good").onclick = () => grade(true);
    document.getElementById("fsec").onchange = (e) => (location.hash = "#/flashcards" + (e.target.value ? "?s=" + e.target.value : ""));
    const onKey = (e) => {
      if (!location.hash.startsWith("#/flashcards")) return document.removeEventListener("keydown", onKey);
      if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT") return;
      if (e.code === "Space") { e.preventDefault(); flip(); } else if (e.key === "1") grade(false); else if (e.key === "2") grade(true);
    };
    document.addEventListener("keydown", onKey);
    draw();
  }

  /* ---------------- glossary ---------------- */
  function viewGlossary() {
    const renamed = E.glossary.filter((t) => t.now);
    app.innerHTML = `<h1>Glossary & renames</h1>
      <div class="card"><b>Renamed since the exam was written (Mar 2026 → Oct 2026)</b>
        <table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:14px">${renamed.map((t) => `<tr><td style="padding:4px 8px 4px 0;border-bottom:1px solid var(--border)">${esc(t.term)}</td><td style="padding:4px 0;border-bottom:1px solid var(--border)">→ <b>${esc(t.now)}</b></td></tr>`).join("")}</table>
        <div class="label" style="margin-top:8px">Full details on the <a href="#/notes/overview">Exam overview</a> page.</div></div>
      <div class="row" style="margin:12px 0"><input type="search" id="gq" placeholder="Search ${E.glossary.length} terms…" style="flex:1"><select id="gs"><option value="">All sections</option>${SECTION_IDS.map((sid) => `<option value="${sid}">${esc(secName(sid))}</option>`).join("")}</select></div>
      <div class="card" id="glist" style="padding:4px 18px"></div>`;
    const draw = () => {
      const q = document.getElementById("gq").value.toLowerCase(), s = document.getElementById("gs").value;
      const items = E.glossary.filter((t) => (!s || t.section === s) && (!q || (t.term + " " + t.def + " " + (t.now || "")).toLowerCase().includes(q))).sort((a, b) => a.term.localeCompare(b.term));
      document.getElementById("glist").innerHTML = items.map((t) => `<div class="gloss-item"><b>${esc(t.term)}</b> <span class="tag">§${t.section.slice(1)}</span>${t.now ? ` <span class="now">now: ${esc(t.now)}</span>` : ""}<div>${esc(t.def)}</div></div>`).join("") || `<p class="muted">No matches.</p>`;
    };
    document.getElementById("gq").oninput = draw;
    document.getElementById("gs").onchange = draw;
    draw();
  }

  /* ---------------- labs ---------------- */
  function viewLabs() {
    const done = E.labs.filter((l) => S.labs[l.file]).length;
    app.innerHTML = `<h1>Hands-on labs</h1>
      <p class="sub">Databricks notebooks in source format. They're designed for <b>Databricks Free Edition</b>, with a few steps noted where Free Edition limits apply. ${done}/${E.labs.length} completed.</p>
      <div class="callout"><b>Import:</b> in your workspace go to <i>Workspace → ⋮ → Import → URL</i> and paste the <b>Raw</b> link, or clone the whole repo with <i>Create → Git folder</i> (${esc(E.repo)}). Run <b>Lab 00</b> first. Labs 04, 05 and 09 should be run from the same folder because they share <code>agent.py</code>.</div>
      ${E.labs.map((l) => `<div class="card"><div class="row"><label style="display:flex;gap:8px;align-items:center;cursor:pointer"><input type="checkbox" data-lab="${esc(l.file)}" ${S.labs[l.file] ? "checked" : ""}><b>${esc(l.title)}</b></label><span class="spacer"></span><a class="btn small" href="${l.url}" target="_blank" rel="noopener">View</a><a class="btn small" href="${l.raw}" target="_blank" rel="noopener">Raw</a></div>
        ${l.meta ? `<div class="label" style="margin:4px 0 0 26px">${esc(l.meta.replace(/\*\*/g, ""))}</div>` : ""}
        ${l.objectives.length ? `<ul style="margin:6px 0 0 6px;font-size:14px">${l.objectives.map((o) => `<li>${esc(o)}</li>`).join("")}</ul>` : ""}</div>`).join("")}
      <p><a href="#/notes/plan">Full hands-on checklist (incl. UI-only tasks) →</a></p>`;
    app.querySelectorAll("[data-lab]").forEach((cb) => (cb.onchange = () => { S.labs[cb.dataset.lab] = cb.checked; save(); }));
  }

  /* ---------------- settings ---------------- */
  function viewSettings() {
    app.innerHTML = `<h1>Progress data</h1><p class="sub">Your progress lives only in this browser's local storage. Export it to move to another device.</p>
      <div class="row"><button class="btn" id="exp">⬇ Export JSON</button><label class="btn">⬆ Import JSON<input type="file" id="imp" accept="application/json" class="hidden"></label><button class="btn" id="reset" style="color:var(--bad)">Reset all progress</button></div>`;
    document.getElementById("exp").onclick = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(S, null, 1)], { type: "application/json" })); a.download = "genai-exam-progress.json"; a.click(); };
    document.getElementById("imp").onchange = (e) => { const f = e.target.files[0]; if (!f) return; f.text().then((t) => { try { S = Object.assign(defaults(), JSON.parse(t)); save(); alert("Imported."); render(); } catch (err) { alert("Invalid file."); } }); };
    document.getElementById("reset").onclick = () => { if (confirm("Delete all progress in this browser?")) { S = defaults(); save(); applyTheme(); render(); } };
  }

  render();
})();
