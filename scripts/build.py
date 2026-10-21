#!/usr/bin/env python3
"""Build docs/data/content.js from notes/*.md, questions/*.yaml, scenarios/*.yaml and labs/*.py.

Usage:  python3 scripts/build.py          (requires: pip install pyyaml markdown)
Validates every question (answer letters, unique ids, "Which TWO" counts) and fails loudly.
"""
import glob, json, os, re, sys
import markdown
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_URL = "https://github.com/lukaleet/databricks-gen-ai-exam-notes"
SECTIONS = {
    "d1": {"name": "Design Applications", "weight": 14, "mock": 6},
    "d2": {"name": "Data Preparation", "weight": 14, "mock": 6},
    "d3": {"name": "Application Development", "weight": 30, "mock": 14},
    "d4": {"name": "Assembling and Deploying Applications", "weight": 22, "mock": 10},
    "d5": {"name": "Governance", "weight": 8, "mock": 4},
    "d6": {"name": "Evaluation and Monitoring", "weight": 12, "mock": 5},
}
LETTERS = "ABCDEFGH"
NUM_WORDS = {"TWO": 2, "THREE": 3}
errors = []


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return (yaml.safe_load(m.group(1)), text[m.end():]) if m else ({}, text)


def build_notes():
    notes = []
    for path in sorted(glob.glob(os.path.join(ROOT, "notes", "*.md"))):
        meta, body = front_matter(open(path, encoding="utf-8").read())
        md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists"],
                               extension_configs={"toc": {"toc_depth": "2-3"}})
        html = md.convert(body)
        notes.append({**meta, "html": html, "toc": md.toc_tokens, "file": os.path.basename(path)})
    return notes


def check_question(q, where):
    qid = q.get("id", "?")
    opts, ans = q.get("options", []), q.get("answer", [])
    if not q.get("q") or len(opts) < 2:
        errors.append(f"{where}:{qid} missing text/options")
    for a in ans:
        if a not in LETTERS[:len(opts)]:
            errors.append(f"{where}:{qid} bad answer letter {a}")
    if len(set(ans)) != len(ans) or not ans:
        errors.append(f"{where}:{qid} empty/duplicate answers")
    for word, n in NUM_WORDS.items():
        if re.search(rf"\b{word}\b", q["q"]) and len(ans) != n:
            errors.append(f"{where}:{qid} says {word} but has {len(ans)} answers")
    if len(ans) > 1 and not re.search(r"\b(TWO|THREE|Select TWO|Select THREE)\b", q["q"]):
        errors.append(f"{where}:{qid} multi-answer but question doesn't say how many")
    return {**q, "answer": [LETTERS.index(a) for a in ans]}


def build_questions():
    out, ids = [], set()
    for path in sorted(glob.glob(os.path.join(ROOT, "questions", "d*.yaml"))):
        data = yaml.safe_load(open(path, encoding="utf-8"))
        for q in data["questions"]:
            if q["id"] in ids:
                errors.append(f"duplicate id {q['id']}")
            ids.add(q["id"])
            out.append({**check_question(q, os.path.basename(path)), "section": data["section"]})
    return out


def build_scenarios():
    data = yaml.safe_load(open(os.path.join(ROOT, "scenarios", "scenarios.yaml"), encoding="utf-8"))
    for s in data["scenarios"]:
        s["steps"] = [check_question({**st, "id": f"{s['id']}-{i}"}, "scenarios") for i, st in enumerate(s["steps"])]
    return data["scenarios"]


def build_glossary():
    return yaml.safe_load(open(os.path.join(ROOT, "questions", "glossary.yaml"), encoding="utf-8"))["terms"]


def build_labs():
    labs = []
    for path in sorted(glob.glob(os.path.join(ROOT, "labs", "*.py"))):
        src = open(path, encoding="utf-8").read()
        title = re.search(r"# MAGIC # (.+)", src).group(1)
        objectives = re.findall(r"# MAGIC - (§\d .+)", src.split("COMMAND")[0])
        meta = re.search(r"# MAGIC \*\*Time:\*\* (.+)", src)
        name = os.path.basename(path)
        labs.append({"file": name, "title": title, "objectives": objectives,
                     "meta": meta.group(1) if meta else "",
                     "url": f"{REPO_URL}/blob/main/labs/{name}",
                     "raw": f"{REPO_URL}/raw/main/labs/{name}"})
    return labs


def main():
    content = {
        "sections": SECTIONS,
        "notes": build_notes(),
        "questions": build_questions(),
        "scenarios": build_scenarios(),
        "glossary": build_glossary(),
        "labs": build_labs(),
        "repo": REPO_URL,
    }
    for sid, s in SECTIONS.items():
        n = sum(q["section"] == sid for q in content["questions"])
        if n < s["mock"]:
            errors.append(f"section {sid} has {n} questions < mock quota {s['mock']}")
    if errors:
        print("BUILD FAILED:\n  " + "\n  ".join(errors))
        sys.exit(1)
    out = os.path.join(ROOT, "docs", "data", "content.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.EXAM = " + json.dumps(content, ensure_ascii=False) + ";\n")
    print(f"OK: {len(content['notes'])} notes, {len(content['questions'])} questions, "
          f"{len(content['scenarios'])} scenarios, {len(content['glossary'])} terms, "
          f"{len(content['labs'])} labs -> {os.path.relpath(out, ROOT)}")


if __name__ == "__main__":
    main()
