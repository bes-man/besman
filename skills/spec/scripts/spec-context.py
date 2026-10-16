#!/usr/bin/env python3
"""Everything a spec run needs to know about a ticket before any agent runs, in one bundle.

    spec-context.py 101 --out DIR                      a GitHub issue in --repo, or in the current directory's repository
    spec-context.py owner/name#101 --out DIR           the same, repository named
    spec-context.py https://github.com/owner/name/issues/101 --out DIR
    spec-context.py 101 --out DIR --repos ~/src        where the checkouts are, to quote what an earlier report cites
    spec-context.py 101 --out DIR --dump live.json     also save what was fetched, to replay or to make a fixture
    spec-context.py 101 --out DIR --fixture f.json     run the logic on saved data, no GitHub calls
    spec-context.py x --out DIR --from-file desc.md    a description pasted from any tracker; the id is the file stem

Writes <out>/context.md and <out>/context.json, and downloads the attachments the body and the
comments reference into <out>/attachments/, each type-checked by its magic bytes. Prints one line
per finding and, last, `phase=<investigate|write|revise|awaiting-answers|stop>`. Read-only against
GitHub (through `gh`); never clones.

Each comment is classified: `questions` (carries the questions or confirmations marker),
`document` (carries the document marker), `bot` (author type Bot) or `human`. The phase:
  investigate       nothing of this pipeline on the thread yet: run the full pipeline
  write             a questions report was posted and a person answered after it
  revise            a specification was posted and a person commented after it
  awaiting-answers  the last report or document has no human reply after it
  stop              the issue is closed or labelled spike; the reason is printed

On a repeat run (write or revise) every `Repo/path:line` the earlier report cites is quoted from
the --repos checkouts into the bundle, so nobody re-opens a settled fact. A cited line that no
longer resolves is marked NOT FOUND: that is the one thing worth a fresh look.
"""
import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent

TASK_TYPES = {
    "bug": "bug", "defect": "bug",
    "feature": "feature", "enhancement": "feature",
    "change": "change", "refactor": "change", "chore": "change",
    "spike": "spike",
}

ATTACHMENT_URL = re.compile(
    r"https://(?:github\.com/user-attachments/(?:assets|files)|(?:private-)?user-images\.githubusercontent\.com)"
    r"/[A-Za-z0-9./_%-]+")
ISSUE_REF = re.compile(r"(?<![\w/])#(\d{1,6})\b")
PARENT_REF = re.compile(r"\*\*Parent:?\*\*:?\s*#(\d+)")
TICKET_REF = re.compile(r"^([\w.-]+/[\w.-]+)#(\d+)$")
TICKET_URL = re.compile(r"^https?://github\.com/([\w.-]+/[\w.-]+)/(?:issues|pull)/(\d+)")
MARK_QUESTIONS = ("<!-- besman:spec-questions -->", "<!-- besman:spec-confirmations -->", "<!-- besman:awaiting spec -->")
MARK_DOCUMENT = "<!-- besman:spec-document -->"
ANSWER_LINE = re.compile(r"\b(Q\d+)\s*[-–:=]?\s*([A-F])\b")
MAX_ATTACHMENT = 25 * 1024 * 1024
MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "image/png", "png", True),
    (b"\xff\xd8\xff", "image/jpeg", "jpg", True),
    (b"GIF87a", "image/gif", "gif", True),
    (b"GIF89a", "image/gif", "gif", True),
    (b"%PDF-", "application/pdf", "pdf", True),
    (b"PK\x03\x04", "application/zip", "zip", False),
]


class TicketError(Exception):
    pass


def gh(*args):
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise TicketError("the GitHub CLI `gh` is not installed; use --from-file for a pasted description")
    if out.returncode != 0:
        raise TicketError(f"gh {' '.join(args[:3])}: {out.stderr.strip()[:200]}")
    return out.stdout


def gh_json(*args):
    text = gh(*args)
    return json.loads(text) if text.strip() else None


def parse_ticket(ticket, repo):
    """(repo or None, number) from `123`, `owner/name#123` or an issue URL."""
    m = TICKET_REF.match(ticket) or TICKET_URL.match(ticket)
    if m:
        return m.group(1), int(m.group(2))
    if ticket.lstrip("#").isdigit():
        return repo, int(ticket.lstrip("#"))
    raise TicketError(f"'{ticket}' is not an issue number, owner/name#number or a GitHub issue URL")


def current_repo():
    data = gh_json("repo", "view", "--json", "nameWithOwner")
    return data["nameWithOwner"]


# ---------------------------------------------------------------- fetch

def fetch(repo, number):
    issue = gh_json("api", f"repos/{repo}/issues/{number}")
    comments, page = [], 1
    while True:
        batch = gh_json("api", f"repos/{repo}/issues/{number}/comments?per_page=100&page={page}") or []
        comments += batch
        if len(batch) < 100:
            break
        page += 1
    linked = {}
    for n in linked_numbers(number, issue.get("body") or ""):
        try:
            other = gh_json("api", f"repos/{repo}/issues/{n}")
        except TicketError as exc:
            linked[n] = {"error": str(exc)}
            continue
        linked[n] = {"title": other.get("title"), "state": other.get("state"),
                     "labels": [l["name"] for l in other.get("labels", [])],
                     "body": (other.get("body") or "")[:3000]}
    return {"repo": repo, "issue": issue, "comments": comments, "linked": linked}


def from_file(path):
    text = path.read_text(errors="replace")
    heading = re.search(r"^#\s+(.+)$", text, re.M)
    return {"repo": None, "source": "file", "issue": {
        "number": path.stem, "title": heading.group(1).strip() if heading else path.stem,
        "state": "open", "labels": [], "body": text, "html_url": str(path.resolve())},
        "comments": [], "linked": {}}


def linked_numbers(number, body):
    parent = PARENT_REF.search(body)
    seen = []
    if parent:
        seen.append(parent.group(1))
    for n in ISSUE_REF.findall(body):
        if n not in seen and n != str(number):
            seen.append(n)
    return seen[:6]


def download_attachments(ident, urls, out):
    """Fetch each upload with the gh token and say what it actually is: a login page is 200 too."""
    out.mkdir(parents=True, exist_ok=True)
    try:
        token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        token = ""
    results = []
    for i, url in enumerate(urls, 1):
        path = out / f"{ident}-att-{i}"
        # curl, not urllib: it uses the system trust store, and drops the header when the
        # upload redirects off github.com. The token goes in on stdin, never in argv.
        config = f'header = "Authorization: token {token}"\n' if token else ""
        try:
            run = subprocess.run(["curl", "-sSfL", "--max-time", "60", "--max-filesize", str(MAX_ATTACHMENT),
                                  "-K", "-", "-o", str(path), url], input=config, capture_output=True, text=True)
        except FileNotFoundError:
            results.append({"url": url, "path": None, "kind": "missing (curl is not installed)", "readable": False})
            continue
        if run.returncode != 0:
            path.unlink(missing_ok=True)
            results.append({"url": url, "path": None, "kind": f"missing ({run.stderr.strip()[:100]})", "readable": False})
            continue
        results.append(describe_attachment(url, path))
    return results


def sniff(head):
    """(mime, extension, readable) from the first bytes of a file."""
    for magic, mime, ext, readable in MAGIC:
        if head.startswith(magic):
            return mime, ext, readable
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp", True
    if head[4:8] == b"ftyp":
        return "video/mp4", "mp4", False
    lowered = head.lstrip().lower()
    if lowered.startswith((b"<!doctype html", b"<html")):
        return "text/html", "html", False
    return "unknown", None, False


def describe_attachment(url, path):
    if not path.exists() or path.stat().st_size == 0:
        return {"url": url, "path": None, "kind": "missing", "readable": False}
    with path.open("rb") as fh:
        mime, ext, readable = sniff(fh.read(64))
    if ext:
        new = path.with_suffix("." + ext)
        path.rename(new)
        path = new
    return {"url": url, "path": str(path), "kind": mime, "readable": readable}


# ---------------------------------------------------------------- decide

def task_type(labels):
    for label in labels:
        key = re.sub(r"^(type|kind)\s*[:/]\s*", "", label.strip().lower())
        if key in TASK_TYPES:
            return TASK_TYPES[key], f"label {label}"
    return None, "no task label"


def is_bot(comment):
    user = comment.get("user") or {}
    return user.get("type") == "Bot" or user.get("login", "").endswith("[bot]")


def classify(comment):
    body = comment.get("body") or ""
    if MARK_DOCUMENT in body:
        return "document"
    if any(m in body for m in MARK_QUESTIONS):
        return "questions"
    if is_bot(comment):
        # Reports posted without a marker, and stops written by hand: a document by its shape,
        # a report by a stop headline or bold numbered questions.
        if "## TL;DR" in body and re.search(r"\bREQ-\d", body):
            return "document"
        if "decisions need you" in body or re.search(r"\*\*[QD]-?\d+\b", body):
            return "questions"
        return "bot"
    return "human"


def strip_trigger(body):
    return re.sub(r"^\s*@claude\s*/?(spec)?\s*", "", body, flags=re.I).strip()


def comment_order(c):
    return (c.get("created_at") or "", c.get("id") or 0)


def decide(ident, data):
    issue = data["issue"]
    labels = [l["name"] if isinstance(l, dict) else str(l) for l in issue.get("labels", [])]
    kind, why = task_type(labels)
    comments = sorted(data["comments"], key=comment_order)
    kinds = [(c, classify(c)) for c in comments]

    reports = [(i, c, k) for i, (c, k) in enumerate(kinds) if k in ("document", "questions")]
    ref_index, reference, ref_kind = reports[-1] if reports else (None, None, None)
    answers = []
    if reference is not None:
        answers = [{"author": (c.get("user") or {}).get("login"), "at": c.get("created_at"),
                    "url": c.get("html_url"), "text": strip_trigger(c.get("body") or "")}
                   for c, k in kinds[ref_index + 1:] if k == "human"]
        answers = [a for a in answers if a["text"]]

    stop = []
    if (issue.get("state") or "open").lower() == "closed":
        stop.append("The issue is closed; a closed ticket is not specified. Reopen it to continue.")
    if kind == "spike":
        stop.append("A spike is not a specification; it ends in findings, not requirements.")

    if stop:
        phase = "stop"
    elif reference is None:
        phase = "investigate"
    elif not answers:
        phase = "awaiting-answers"
    else:
        phase = "revise" if ref_kind == "document" else "write"

    parsed = {}
    for a in answers:
        for q, opt in ANSWER_LINE.findall(a["text"]):
            parsed[q] = opt

    urls = []
    for text in [issue.get("body") or ""] + [c.get("body") or "" for c in comments]:
        for u in ATTACHMENT_URL.findall(text):
            u = u.rstrip(".")
            if u not in urls:
                urls.append(u)

    return {
        "id": ident,
        "repo": data.get("repo"),
        "source": data.get("source", "github"),
        "url": issue.get("html_url"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "author": (issue.get("user") or {}).get("login"),
        "created_at": issue.get("created_at"),
        "labels": labels,
        "milestone": (issue.get("milestone") or {}).get("title"),
        "task_type": kind,
        "task_type_reason": why,
        "phase": phase,
        "stop_reasons": stop,
        "resume_from": reference.get("html_url") if reference else None,
        "resume_from_kind": ref_kind,
        "resume_from_at": reference.get("created_at") if reference else None,
        "resume_from_author": (reference.get("user") or {}).get("login") if reference else None,
        "resume_body": (reference.get("body") or "") if reference else "",
        "answers": answers,
        "answers_parsed": parsed,
        "attachment_urls": urls,
        "comment_kinds": [{"id": c.get("id"), "author": (c.get("user") or {}).get("login"), "kind": k}
                          for c, k in kinds],
    }


def load_lint():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("spec_lint", HERE / "spec-lint.py")
    lint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lint)
    return lint


def cited_lines(body, repos):
    """Every `path:line` the report cites, quoted from the checkouts; the lint's own resolver does the work."""
    lint = load_lint()
    faults, _warns, notes = lint.citation_faults(body, repos, True)
    quotes = [n for n in notes if not n.endswith("citations checked")]
    return quotes, [f"NOT FOUND: {f}" for f in faults]


# ---------------------------------------------------------------- render

def render(ctx, data, attachments):
    issue = data["issue"]
    name = f"{ctx['repo']}#{ctx['id']}" if ctx["repo"] else str(ctx["id"])
    lines = [f"# Ticket {name}, {ctx['title']}", ""]
    if ctx["source"] == "file":
        lines.append(f"- Source: a description pasted into {ctx['url']}; there is no thread")
    else:
        lines.append(f"- State: {ctx['state']}, author @{ctx['author']}, created {ctx['created_at']}, {ctx['url']}")
    lines += [f"- Labels: {', '.join(ctx['labels']) or 'none'}; milestone: {ctx['milestone'] or 'none'}",
              f"- Task type: **{ctx['task_type'] or 'undecided'}** ({ctx['task_type_reason']})",
              f"- Phase: **{ctx['phase']}**" + (f", resuming from the {ctx['resume_from_kind']} posted by "
                                                 f"@{ctx['resume_from_author']} at {ctx['resume_from_at']}: {ctx['resume_from']}"
                                                 if ctx["resume_from"] else "")]
    if ctx["phase"] in ("write", "revise"):
        lines.append(f"- Repeat run: the investigation is done. Write from the report at {ctx['resume_from']}; its text "
                     "is below under \"Comments, in order\". Do not investigate again: re-open only ground an answer "
                     "moved into, or a cited line marked NOT FOUND.")
    for reason in ctx["stop_reasons"]:
        lines.append(f"- STOP: {reason}")
    lines += ["", "## Body", "", issue.get("body") or "(empty)", ""]

    if ctx["answers"]:
        lines += ["## Answers given after the last report", "",
                  "Quote these into the document as decisions, with who gave each.", ""]
        for a in ctx["answers"]:
            lines += [f"### @{a['author']} at {a['at']}", "", a["text"], ""]
        if ctx["answers_parsed"]:
            lines += ["Parsed as: " + ", ".join(f"{q} {o}" for q, o in sorted(ctx["answers_parsed"].items())), ""]

    if ctx["phase"] in ("write", "revise"):
        lines += ["## Cited lines from the report", ""]
        if ctx.get("cited_lines") is None:
            lines += ["No --repos directory was given, so the citations were not quoted. Rerun with --repos "
                      "pointing at the checkouts to have them here.", ""]
        else:
            lines += [f"Every `path:line` the report cites, quoted from {', '.join(ctx['repos'])}. These are the "
                      "evidence: do not open these files to check them again. A line marked NOT FOUND moved or "
                      "vanished since the report; that alone is new ground.", ""]
            lines += [f"- {q}" for q in ctx["cited_lines"]] + [f"- {m}" for m in ctx["cited_missing"]]
            if not ctx["cited_lines"] and not ctx["cited_missing"]:
                lines.append("The report cites no `path:line`.")
            lines.append("")

    if ctx["comment_kinds"]:
        lines += ["## Comments, in order", ""]
        by_id = {c.get("id"): c for c in data["comments"]}
        for entry in ctx["comment_kinds"]:
            c = by_id[entry["id"]]
            lines += [f"### {entry['kind']}, @{entry['author']} at {c.get('created_at')} ({c.get('html_url')})", "",
                      c.get("body") or "(empty)", ""]

    if data.get("linked"):
        lines += ["## Linked tickets", ""]
        for n, other in data["linked"].items():
            if "error" in other:
                lines += [f"### #{n}: could not be read ({other['error']})", ""]
                continue
            lines += [f"### #{n}, {other['title']} ({other['state']}; {', '.join(other['labels']) or 'no labels'})", "",
                      other["body"] or "(empty)", ""]

    lines += ["## Attachments", ""]
    if not attachments:
        lines.append("None found in the body or the comments.")
    for a in attachments:
        if a["readable"]:
            lines.append(f"- {a['path']} ({a['kind']}), open it with Read and describe what it shows")
        else:
            lines.append(f"- {a['url']}: NOT READABLE ({a['kind']}); say so and ask what it shows")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- main

def load(args):
    """(ident, data) from the fixture, the pasted file or GitHub."""
    if args.from_file:
        path = pathlib.Path(args.from_file)
        return path.stem, from_file(path)
    if not args.ticket:
        raise TicketError("a ticket is required: an issue number, owner/name#number or a GitHub issue URL")
    repo, number = parse_ticket(args.ticket, args.repo)
    if args.fixture:
        data = json.loads(pathlib.Path(args.fixture).read_text())
        data["repo"] = repo or data.get("repo") or repo_from_url((data["issue"] or {}).get("html_url"))
        return number, data
    data = fetch(repo or current_repo(), number)
    if args.dump:
        pathlib.Path(args.dump).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return number, data


def repo_from_url(url):
    m = TICKET_URL.match(url or "")
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticket", nargs="?", help="an issue number, owner/name#number or a GitHub issue URL; not needed with --from-file")
    ap.add_argument("--out", required=True, help="directory for context.md, context.json and attachments/")
    ap.add_argument("--repo", help="owner/name for a bare issue number (default: the current directory's repository)")
    ap.add_argument("--from-file", help="a pasted ticket description (markdown or text) instead of a GitHub issue")
    ap.add_argument("--repos", action="append", help="a checkout, or a directory of checkouts, to quote citations from; repeatable")
    ap.add_argument("--fixture", help="replay saved data instead of calling GitHub")
    ap.add_argument("--dump", help="save the fetched data as JSON")
    ap.add_argument("--json", action="store_true", help="print context.json to stdout")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        ident, data = load(args)
    except (TicketError, OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    ctx = decide(ident, data)
    if args.fixture:
        attachments = data.get("attachments") or [
            {"url": u, "path": None, "kind": "not fetched (fixture)", "readable": False}
            for u in ctx["attachment_urls"]]
    else:
        attachments = download_attachments(ident, ctx["attachment_urls"], out / "attachments") if ctx["attachment_urls"] else []
    ctx["attachments"] = attachments
    if ctx["phase"] in ("write", "revise"):
        if args.repos:
            quotes, missing = cited_lines(ctx["resume_body"], args.repos)
            ctx.update({"cited_lines": quotes, "cited_missing": missing, "repos": args.repos})
        else:
            ctx.update({"cited_lines": None, "cited_missing": None, "repos": []})
    ctx.pop("resume_body", None)

    (out / "context.md").write_text(render(ctx, data, attachments))
    (out / "context.json").write_text(json.dumps(ctx, indent=2, ensure_ascii=False))

    if args.json:
        print(json.dumps(ctx, indent=2, ensure_ascii=False))
        return 0
    print(f"ticket={ctx['repo'] + '#' if ctx['repo'] else ''}{ctx['id']} {ctx['title']}")
    print(f"task_type={ctx['task_type'] or 'undecided'} ({ctx['task_type_reason']})")
    print(f"attachments={len(attachments)} readable={sum(1 for a in attachments if a['readable'])}")
    print(f"answers={len(ctx['answers'])}")
    if ctx["resume_from"]:
        print(f"resume_from={ctx['resume_from']}")
    if ctx.get("cited_lines") is not None:
        print(f"cited={len(ctx['cited_lines'])} quoted, {len(ctx['cited_missing'])} not found")
    elif ctx["phase"] in ("write", "revise"):
        print("cited=not quoted (no --repos)")
    for reason in ctx["stop_reasons"]:
        print(f"stop: {reason}")
    print(f"bundle={out / 'context.md'}")
    print(f"phase={ctx['phase']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
