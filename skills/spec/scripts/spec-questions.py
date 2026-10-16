#!/usr/bin/env python3
"""The questions a spec run puts to a person: checked as data, rendered as one comment.

    spec-questions.py lint questions.yaml [--ticket context.md] [--repos DIR ...] [--kb .besman]
    spec-questions.py render questions.yaml [same options] > comment.md

`lint` exits 1 with one line per fault. `render` lints first and refuses a file with faults, so the
comment on the thread is always one the checks passed. Both are offline. Needs PyYAML.

What a question must carry:
  type            business | flow | constraint; a question that fits none is technical and is not asked
  status          BLOCKING | DEFERRABLE
  anchor.ticket   a sentence quoted from the ticket or its comments that this question refines
  anchor.code     Repo/path:line citations for what the system does today
  anchor.docs     a path relative to the project root (the parent of --kb), or the word `silent`
  anchor.open_because  one sentence on why the ticket, the code and the docs leave this open
  question, options (id, text, consequence), recommendation, reason
  conditions      optional; the place for what would have been a dependent question

At most 4 BLOCKING and 6 questions in all per stop. Visible text (question, options, reason,
conditions, settled facts, assumptions) is read by the ticket's author: domain names are fine,
implementation names are not. The language check keeps paths, file names, code spans, class-like
identifiers and a stop list of implementation words out. Domain names that look like identifiers
are allowed when listed, one per bullet, under `## Domain vocabulary` in <kb>/project.md.

With --repos (a checkout, or a directory of checkouts; repeatable) every citation must resolve to
a line that exists; the Repo part of a citation is the checkout's directory name.
"""
import argparse
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

TYPES = {"business", "flow", "constraint"}
STATUSES = {"BLOCKING", "DEFERRABLE"}
MAX_BLOCKING = 4
MAX_TOTAL = 6
CITATION = re.compile(r"^[A-Za-z0-9._-]+/[^\s:]+:\d+(?:-\d+)?$")
QUESTION_ID = re.compile(r"^Q\d+$")
OPTION_ID = re.compile(r"^[A-F]$")
TICKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MARK_QUESTIONS = "<!-- besman:spec-questions -->"
MARK_CONFIRMATIONS = "<!-- besman:spec-confirmations -->"
MARK_AWAITING = "<!-- besman:awaiting spec -->"

# Implementation vocabulary. Domain vocabulary (entities, commands, queues, tables) is allowed.
STOP_WORDS = {
    "dto", "dtos", "api", "apis", "endpoint", "endpoints", "poll", "polls", "polling", "cache", "cached",
    "caching", "handler", "handlers", "migration", "migrations", "controller", "controllers", "hook", "hooks",
    "prop", "props", "component", "components", "mutation", "schema", "json", "graphql", "sql", "regex",
    "refactor", "backend", "frontend", "repository", "repositories", "config", "configuration", "null",
    "boolean", "enum", "middleware", "payload", "serializer", "deserializer", "interface", "class",
    "method", "function", "variable", "parameter", "callback", "thread", "async", "sync", "http", "https",
    "url", "uri", "header", "cookie", "token", "sdk", "cli", "namespace", "partition", "index", "typescript",
    "javascript", "react", "dotnet", "kubernetes", "docker",
}
CODE_SPAN = re.compile(r"`[^`]+`")
FILE_NAME = re.compile(r"\b[\w.-]+\.(?:cs|tsx?|jsx?|py|go|java|kt|rb|php|sql|json|ya?ml|md|csproj|sh)\b", re.I)
PATH_LIKE = re.compile(r"(?<![\w/])[\w.-]+/[\w./-]+")
CLASS_LIKE = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+){2,}\b")   # three humps: ReservationExpiryJob
SUFFIXED = re.compile(r"\b[A-Za-z]+(?:Service|Handler|Controller|Dto|Repository|Query|Command|Builder|Provider|Factory|Processor|Middleware)\b")
SNAKE = re.compile(r"\b[a-z]+_[a-z_]+\b")
NUMBERED_SETTING = re.compile(r"\b\d+\s?(?:ms|milliseconds)\b", re.I)


def load_allow(kb):
    """Terms under `## Domain vocabulary` in <kb>/project.md, one per bullet; empty without one."""
    allow = set()
    if not kb:
        return allow
    path = pathlib.Path(kb) / "project.md"
    if not path.is_file():
        return allow
    in_section = False
    for line in path.read_text(errors="replace").splitlines():
        heading = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if heading:
            in_section = heading.group(1).strip().lower() == "domain vocabulary"
            continue
        bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if in_section and bullet:
            term = re.split(r"\s+[—–-]\s+|:\s", bullet.group(1), maxsplit=1)[0]
            term = re.sub(r"[*_`]", "", term).strip()
            if term:
                allow.add(term)
    return allow


def norm(text):
    text = re.sub(r"[*_`>#\[\]]", "", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def language_faults(where, text, allow):
    faults = []
    if not isinstance(text, str):
        return faults
    for span in CODE_SPAN.findall(text):
        faults.append(f"{where}: code span {span}, say it in words, or move it to the anchor")
    stripped = CODE_SPAN.sub(" ", text)
    for m in FILE_NAME.findall(stripped):
        faults.append(f"{where}: file name '{m}'")
    for m in PATH_LIKE.findall(stripped):
        if "/" in m and not re.match(r"^\d+/\d+$", m) and not re.match(r"^[a-z]+/[a-z]+$", m):
            faults.append(f"{where}: path '{m}'")
    for m in CLASS_LIKE.findall(stripped):
        if m not in allow:
            faults.append(f"{where}: implementation name '{m}'")
    for m in SUFFIXED.findall(stripped):
        if m not in allow and not CLASS_LIKE.fullmatch(m):
            faults.append(f"{where}: implementation name '{m}'")
    for m in SNAKE.findall(stripped):
        if m not in allow:
            faults.append(f"{where}: identifier '{m}'")
    for w in re.findall(r"[A-Za-z]+", stripped):
        if w.lower() in STOP_WORDS and w not in allow:
            faults.append(f"{where}: implementation word '{w}'")
    for m in NUMBERED_SETTING.findall(stripped):
        faults.append(f"{where}: timing detail '{m}' belongs to the implementer")
    return faults


def lint(doc, ticket_text=None, repos=None, kb=None):
    faults = []
    allow = load_allow(kb)
    if not isinstance(doc, dict):
        return ["the file is not a mapping"]
    ticket = doc.get("ticket")
    if isinstance(ticket, bool) or not (isinstance(ticket, int) or (isinstance(ticket, str) and TICKET_ID.match(ticket))):
        faults.append("ticket: an issue number or a slug is required")
    questions = doc.get("questions")
    if not isinstance(questions, list):
        return faults + ["questions: a list is required (empty when nothing is open)"]

    for i, s in enumerate(doc.get("settled") or [], 1):
        where = f"settled[{i}]"
        if not isinstance(s, dict) or not s.get("fact"):
            faults.append(f"{where}: needs a fact")
            continue
        if not s.get("evidence"):
            faults.append(f"{where}: needs evidence (citations)")
        faults += language_faults(where + ".fact", s["fact"], allow)
        for c in as_list(s.get("evidence")):
            faults += citation_faults(where + ".evidence", c, repos)

    for i, a in enumerate(doc.get("assumptions") or [], 1):
        where = f"assumptions[{i}]"
        if not isinstance(a, dict) or not a.get("id") or not a.get("text") or not a.get("reason"):
            faults.append(f"{where}: needs id, text and reason")
            continue
        faults += language_faults(where + ".text", a["text"], allow)
        faults += language_faults(where + ".reason", a["reason"], allow)

    seen_ids, option_sets = set(), {}
    blocking = 0
    for i, q in enumerate(questions, 1):
        where = f"questions[{i}]"
        if not isinstance(q, dict):
            faults.append(f"{where}: not a mapping")
            continue
        qid = str(q.get("id", ""))
        if not QUESTION_ID.match(qid):
            faults.append(f"{where}: id must be Q<n>, got '{qid}'")
        elif qid in seen_ids:
            faults.append(f"{where}: duplicate id {qid}")
        seen_ids.add(qid)
        where = qid or where
        if q.get("type") not in TYPES:
            faults.append(f"{where}: type must be one of {sorted(TYPES)}; a question that fits none is technical and is not asked")
        if q.get("status") not in STATUSES:
            faults.append(f"{where}: status must be BLOCKING or DEFERRABLE")
        if q.get("status") == "BLOCKING":
            blocking += 1
        if q.get("depends_on"):
            faults.append(f"{where}: depends on {q['depends_on']}, fold it into that question's conditions; a dependent question is not asked on its own")
        faults += anchor_faults(where, q.get("anchor"), ticket_text, repos, kb)
        if not q.get("question"):
            faults.append(f"{where}: no question text")
        faults += language_faults(where + ".question", q.get("question"), allow)
        options = q.get("options")
        if not isinstance(options, list) or len(options) < 2:
            faults.append(f"{where}: at least two options")
            options = []
        ids = []
        for o in options:
            if not isinstance(o, dict) or not OPTION_ID.match(str(o.get("id", ""))):
                faults.append(f"{where}: option ids are single letters A-F")
                continue
            ids.append(o["id"])
            if not o.get("text"):
                faults.append(f"{where}.{o['id']}: no text")
            if not o.get("consequence"):
                faults.append(f"{where}.{o['id']}: no consequence, the author must see what each choice costs")
            faults += language_faults(f"{where}.{o['id']}.text", o.get("text"), allow)
            faults += language_faults(f"{where}.{o['id']}.consequence", o.get("consequence"), allow)
        if len(ids) != len(set(ids)):
            faults.append(f"{where}: option ids repeat")
        if q.get("recommendation") not in ids:
            faults.append(f"{where}: recommendation must name one of the options {ids}")
        if not q.get("reason"):
            faults.append(f"{where}: no reason for the recommendation")
        faults += language_faults(where + ".reason", q.get("reason"), allow)
        for k, c in enumerate(as_list(q.get("conditions")), 1):
            faults += language_faults(f"{where}.conditions[{k}]", c, allow)
        key = tuple(sorted(norm(o.get("text", "")) for o in options if isinstance(o, dict)))
        if key and key in option_sets:
            faults.append(f"{where}: the same options as {option_sets[key]}, one question, not two")
        elif key:
            option_sets[key] = where

    if blocking > MAX_BLOCKING:
        faults.append(f"{blocking} BLOCKING questions; at most {MAX_BLOCKING} per stop, carry the rest as assumptions")
    if len(questions) > MAX_TOTAL:
        faults.append(f"{len(questions)} questions; at most {MAX_TOTAL} per stop")
    return faults


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def checkouts(roots):
    """(name, path) for every checkout: a root holding .git is one, otherwise each subdirectory is one."""
    found = []
    for root in roots or []:
        r = pathlib.Path(root)
        if (r / ".git").exists():
            found.append((r.resolve().name, r))
        elif r.is_dir():
            found += [(c.name, c) for c in sorted(r.iterdir()) if c.is_dir() and not c.name.startswith(".")]
    return found


def citation_faults(where, cite, repos):
    if not isinstance(cite, str) or not CITATION.match(cite):
        return [f"{where}: citation '{cite}' is not Repo/path:line"]
    if not repos:
        return []
    repo, rest = cite.split("/", 1)
    path, _, line = rest.rpartition(":")
    roots = [co for name, co in checkouts(repos) if name == repo]
    if not roots:
        return [f"{where}: {cite} does not exist, no checkout named '{repo}' under --repos"]
    file = roots[0] / path
    try:
        file.resolve().relative_to(roots[0].resolve())
    except ValueError:
        return [f"{where}: {cite} points outside the checkout"]
    if not file.is_file():
        return [f"{where}: {cite} does not exist in the checkout"]
    first = int(line.split("-")[0])
    try:
        with file.open(errors="replace") as fh:
            count = sum(1 for _ in fh)
    except OSError:
        return [f"{where}: {cite} could not be read"]
    if first > count:
        return [f"{where}: {cite} is past the end of the file ({count} lines)"]
    return []


def anchor_faults(where, anchor, ticket_text, repos, kb):
    faults = []
    if not isinstance(anchor, dict):
        return [f"{where}: no anchor (ticket, code, docs, open_because)"]
    quote = anchor.get("ticket")
    if not quote:
        faults.append(f"{where}.anchor.ticket: quote the sentence of the ticket this refines; a question the ticket never raised is an assumption, not a question")
    elif ticket_text is not None and norm(quote) not in norm(ticket_text):
        faults.append(f"{where}.anchor.ticket: '{quote[:60]}' is not in the ticket or its comments")
    codes = as_list(anchor.get("code"))
    if not codes:
        faults.append(f"{where}.anchor.code: cite what the system does today")
    for c in codes:
        faults += citation_faults(f"{where}.anchor.code", c, repos)
    docs = anchor.get("docs")
    if not docs:
        faults.append(f"{where}.anchor.docs: a path relative to the project root, or 'silent'")
    elif docs != "silent":
        root = pathlib.Path(kb).resolve().parent if kb else None
        for d in as_list(docs):
            p = pathlib.PurePosixPath(str(d))
            if p.is_absolute() or ".." in p.parts:
                faults.append(f"{where}.anchor.docs: '{d}' must be relative to the project root")
            elif root and not (root / str(d)).exists():
                faults.append(f"{where}.anchor.docs: '{d}' does not exist under {root}")
    if not anchor.get("open_because"):
        faults.append(f"{where}.anchor.open_because: say why ticket, code and docs leave this open")
    return faults


# ---------------------------------------------------------------- render

def render(doc):
    qs = doc.get("questions") or []
    blocking = [q for q in qs if q.get("status") == "BLOCKING"]
    deferrable = [q for q in qs if q.get("status") != "BLOCKING"]
    n = len(blocking)
    out = []
    if n:
        out.append(f"### Spec run stopped: {n} decision{'s' if n != 1 else ''} need{'' if n != 1 else 's'} you first")
        out.append("")
        out.append("**No specification was written yet.** The investigation is done and kept on this thread; "
                   "answer below and the next run writes the document from it.")
    else:
        out.append("### Spec run: nothing blocks, a few things to confirm")
        out.append("")
        out.append("The specification follows on this thread. What is listed here was decided by evidence or "
                   "carried as an assumption; object here if any of it is wrong.")
    out.append("")

    settled = doc.get("settled") or []
    if settled:
        out += ["#### Settled without you", ""]
        for s in settled:
            out.append(f"- {s['fact']}")
        out += ["", "<details><summary>Evidence</summary>", ""]
        for s in settled:
            out.append(f"- {s['fact']}: " + ", ".join(f"`{c}`" for c in as_list(s.get('evidence'))))
        out += ["", "</details>", ""]

    for q in blocking:
        out += render_question(q)
    if deferrable:
        out += ["#### Can wait: answer if you like", ""]
        for q in deferrable:
            out += render_question(q)

    assumptions = doc.get("assumptions") or []
    if assumptions:
        out += ["#### Taken as assumptions unless you object", ""]
        for a in assumptions:
            out.append(f"- **{a['id']}** {a['text']} *({a['reason']})*")
        out.append("")

    if qs:
        example = ", ".join(f"{q['id']} {q.get('recommendation', 'A')}" for q in qs[:2])
        out += ["#### How to answer", "",
                f"Reply with one line per question, for example: `{example}`. Your own words are fine too; "
                "the next run quotes them into the document as your decisions. Answer in full: every choice "
                "left open here is taken later by whoever implements the ticket.", ""]
    out += ["*Not done: no specification, no branch, no code. The ticket stays where it is until the document exists.*", ""]
    out.append(MARK_QUESTIONS if qs else MARK_CONFIRMATIONS)
    if blocking:
        out.append(MARK_AWAITING)
    return "\n".join(out) + "\n"


def render_question(q):
    out = [f"#### {q['id']}: {q['question']}  `{q['status']}` · {q['type']}", ""]
    for o in q.get("options", []):
        out.append(f"**{o['id']}**: {o['text']} *Consequence:* {o['consequence']}")
    out += ["", f"*Recommended: {q['recommendation']}.* {q['reason']}"]
    for c in as_list(q.get("conditions")):
        out.append(f"- {c}")
    a = q.get("anchor") or {}
    out += ["", "<details><summary>Why this is still open</summary>", "",
            f"- Ticket: “{a.get('ticket', '')}”",
            "- Code: " + ", ".join(f"`{c}`" for c in as_list(a.get("code"))),
            "- Docs: " + (", ".join(f"`{d}`" for d in as_list(a.get("docs"))) if a.get("docs") != "silent" else "the documentation says nothing about this"),
            f"- Open because: {a.get('open_because', '')}",
            "", "</details>", ""]
    return out


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["lint", "render"])
    ap.add_argument("file")
    ap.add_argument("--ticket", help="context.md from spec-context.py; ticket quotes are checked against it")
    ap.add_argument("--repos", action="append", help="a checkout, or a directory of checkouts; citations are checked against it; repeatable")
    ap.add_argument("--kb", help="the project's .besman directory; docs anchors resolve against its parent, the domain vocabulary comes from its project.md")
    args = ap.parse_args()

    if yaml is None:
        print("spec-questions.py needs PyYAML: python3 -m pip install pyyaml")
        return 2
    try:
        doc = yaml.safe_load(pathlib.Path(args.file).read_text())
    except (OSError, yaml.YAMLError) as exc:
        print(f"cannot read {args.file}: {exc}")
        return 1
    try:
        ticket_text = pathlib.Path(args.ticket).read_text() if args.ticket else None
    except OSError as exc:
        print(f"cannot read {args.ticket}: {exc}")
        return 1
    faults = lint(doc, ticket_text, args.repos, args.kb)
    if faults:
        for f in faults:
            print(f"FAULT {f}")
        plural = "s" if len(faults) != 1 else ""
        print(f"{len(faults)} fault{plural}; nothing rendered" if args.command == "render" else f"{len(faults)} fault{plural}")
        return 1
    if args.command == "lint":
        qs = doc.get("questions") or []
        print(f"ok: {len(qs)} questions ({sum(1 for q in qs if q.get('status') == 'BLOCKING')} blocking), "
              f"{len(doc.get('settled') or [])} settled, {len(doc.get('assumptions') or [])} assumptions")
        return 0
    sys.stdout.write(render(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
