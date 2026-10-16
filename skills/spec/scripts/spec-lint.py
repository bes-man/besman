#!/usr/bin/env python3
"""The mechanical half of reviewing a specification, done by a script instead of a reviewer.

    spec-lint.py 101-spec.md                              structure, budgets, traceability, language
    spec-lint.py 101-spec.md --repos DIR [--repos DIR]    and every `path:line` citation resolved in the checkouts
    spec-lint.py 101-spec.md --repos DIR --quote          also print the cited lines, for the reviewer

Exit 1 with one FAULT line per finding; WARN lines do not fail. It checks the file name
(<id>-spec.md, the id a number or a slug), the four-line TL;DR without identifiers, no code,
REQ/VC/AC identifiers, a traceability matrix with no holes, `shall` on every requirement, the
8 000-character open half and the 65 536-character comment limit, no acceptance criterion about
paperwork, no empty clause, no live @claude mention, the document marker, and, with --repos, that
every cited line exists.

A --repos directory is either a checkout itself (it holds .git) or a directory of checkouts. A
citation `Repo/path:line` names the checkout by its directory name; `Repo/.../file` and a bare
`file:line` are searched for in every checkout.
"""
import argparse
import glob
import pathlib
import re
import sys

OPEN_HALF_LIMIT = 8000
COMMENT_LIMIT = 65536
TLDR_WORDS_LIMIT = 120
MARKER = "<!-- besman:spec-document -->"

ID = re.compile(r"\b(REQ|ATT|VC|AC|A)-(\d+)\b")
CITATION = re.compile(r"`([A-Za-z0-9_][\w./-]*\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?`")
SPEC_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*-spec\.md")
PAPERWORK = re.compile(r"\b(ticket is raised|tickets? (are|is) raised|is recorded on|pasted into|attributed to|board field|field is set|"
                       r"told in writing|specification is (posted|published|commented)|moves? to ready|pull request review records|"
                       r"follow-up tickets?)\b", re.I)
EMPTY = re.compile(r"^\s*(none|n/a|not applicable|nothing)\.?\s*$", re.I)
CLASS_LIKE = re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+){2,}\b")
FILE_NAME = re.compile(r"\b[\w.-]+\.(?:cs|tsx?|jsx?|py|go|java|kt|rb|php|sql|json|ya?ml|csproj)\b")


def lint(text, name=None, repos=None, quote=False):
    faults, warns, notes = [], [], []
    lines = text.split("\n")

    if name and not SPEC_NAME.fullmatch(name):
        faults.append(f"file name '{name}' is not <id>-spec.md")
    if len(text) > COMMENT_LIMIT:
        faults.append(f"{len(text)} characters; GitHub takes {COMMENT_LIMIT} in one comment, decompose the ticket, do not split the comment")
    first_fold = text.find("<details")
    open_half = len(text) if first_fold < 0 else first_fold
    if open_half > OPEN_HALF_LIMIT:
        faults.append(f"open half is {open_half} characters; the budget is {OPEN_HALF_LIMIT}, fold or cut rationale before cutting a requirement")
    if first_fold < 0 and len(text) > OPEN_HALF_LIMIT:
        faults.append("nothing is folded; supporting material belongs behind <details>")
    if "```" in text:
        faults.append(f"{text.count('```') // 2} code fence(s); a specification carries no code")
    if re.search(r"(?<![\w/])@claude\b", text):
        faults.append("a live @claude mention; write the command without the mention")
    if MARKER not in text:
        faults.append(f"the document marker is missing; end the file with {MARKER}")

    f, w = tldr_faults(lines)
    faults += f
    warns += w

    ids = {kind: set() for kind in ("REQ", "ATT", "VC", "AC", "A")}
    for kind, n in ID.findall(text):
        ids[kind].add(int(n))
    for kind in ("REQ", "VC", "AC"):
        if not ids[kind]:
            faults.append(f"no {kind}-n identifiers")
    for kind, nums in ids.items():
        if nums and sorted(nums) != list(range(1, max(nums) + 1)):
            warns.append(f"{kind} numbering has gaps: {sorted(nums)}")

    faults += requirement_faults(lines)
    faults += traceability_faults(lines, ids)
    faults += criteria_faults(lines)
    faults += empty_clause_faults(lines)

    if repos:
        f, w, n = citation_faults(text, repos, quote)
        faults += f
        warns += w
        notes += n
    return faults, warns, notes


def tldr_faults(lines):
    """The TL;DR is written for a person: no identifiers of this document, no class, no file; but the
    thing itself named (a parameter, a route, a status, a value, a number), because a paraphrase hides
    the one fact a reader needs."""
    faults, warns = [], []
    start = next((i for i, l in enumerate(lines) if re.match(r"^#{1,3}\s*(0\.\s*)?TL;DR", l)), None)
    if start is None:
        return ["no TL;DR"], warns
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^#{1,3}\s", lines[i])), len(lines))
    body = [l for l in lines[start + 1:end] if l.strip() and l.strip() != "---"]
    labels = [re.match(r"^\*\*(Problem|Cause|Action|Result)\.?\*\*", l) for l in body]
    found = [m.group(1) for m in labels if m]
    if found != ["Problem", "Cause", "Action", "Result"]:
        faults.append(f"TL;DR must be four labelled lines Problem, Cause, Action, Result; found {found or 'none'}")
    words = sum(len(l.split()) for l in body)
    if words > TLDR_WORDS_LIMIT:
        faults.append(f"TL;DR is {words} words; about eighty, at most {TLDR_WORDS_LIMIT}")
    joined = "\n".join(body)
    if ID.search(joined):
        faults.append("TL;DR names an identifier (REQ, VC, AC…); it is written for a person")
    for s in re.findall(r"`([^`]+)`", joined):
        if len(s) > 40:
            faults.append(f"TL;DR code span `{s}` is code; a span there is a name: a parameter, a route, a status, a value")
    for m in FILE_NAME.findall(joined):
        faults.append(f"TL;DR names a file '{m}'")
    for m in CLASS_LIKE.findall(joined):
        faults.append(f"TL;DR names '{m}'; say what it is in words")
    concrete = [l for l in body if re.match(r"^\*\*(Problem|Cause)", l) and re.search(r"`[^`]+`|\d", l)]
    if found == ["Problem", "Cause", "Action", "Result"] and not concrete:
        warns.append("TL;DR Problem and Cause name nothing concrete (no parameter, route, status, value or number); "
                     "a paraphrase hides what a reader needs")
    return faults, warns


def requirement_faults(lines):
    faults = []
    for l in lines:
        m = re.match(r"^\s*[-*]\s*\*\*(REQ-\d+)\*\*", l)
        if m and not re.search(r"\bshall\b", l):
            faults.append(f"{m.group(1)} does not use 'shall'")
        if m and re.search(r"\bshall\b.*\band\b.*\bshall\b", l):
            faults.append(f"{m.group(1)} states two obligations; one 'shall' per requirement")
    return faults


def traceability_faults(lines, ids):
    """Rebuild the matrix from the text: a VC line or a table row that names both sides."""
    covered_req, covered_vc = set(), set()
    for l in lines:
        reqs = {int(n) for k, n in ID.findall(l) if k == "REQ"}
        atts = {int(n) for k, n in ID.findall(l) if k == "ATT"}
        vcs = {int(n) for k, n in ID.findall(l) if k == "VC"}
        if vcs and (reqs or atts):
            covered_req |= {("REQ", r) for r in reqs} | {("ATT", a) for a in atts}
            covered_vc |= vcs
    faults = []
    for r in sorted(ids["REQ"]):
        if ("REQ", r) not in covered_req:
            faults.append(f"REQ-{r} has no verification case")
    for a in sorted(ids["ATT"]):
        if ("ATT", a) not in covered_req:
            faults.append(f"ATT-{a} has no verification case")
    for v in sorted(ids["VC"]):
        if v not in covered_vc:
            faults.append(f"VC-{v} verifies no requirement")
    methods = {"test", "inspection", "analysis", "demonstration"}
    for l in lines:
        m = re.match(r"^\s*[-*]\s*\*\*(VC-\d+)\*\*", l)
        if m and not any(w in l.lower() for w in methods):
            faults.append(f"{m.group(1)} names no method (test, inspection, analysis, demonstration)")
    return faults


def criteria_faults(lines):
    faults = []
    for l in lines:
        m = re.match(r"^\s*[-*]\s*\*\*(AC-\d+)\*\*", l)
        if m and PAPERWORK.search(l):
            faults.append(f"{m.group(1)} is about paperwork, not the delivered software: '{PAPERWORK.search(l).group(0)}'")
    return faults


def empty_clause_faults(lines):
    faults = []
    for i, l in enumerate(lines[:-1]):
        if re.match(r"^#{2,4}\s", l):
            nxt = next((x for x in lines[i + 1:] if x.strip()), "")
            if EMPTY.match(nxt):
                faults.append(f"clause '{l.strip('# ').strip()}' is empty, delete the heading, do not fill it with '{nxt.strip()}'")
    return faults


def citation_faults(text, repos, quote):
    faults, warns, notes = [], [], []
    seen = set()
    for m in CITATION.finditer(text):
        path, first, last = m.group(1), int(m.group(2)), m.group(3)
        key = (path, first)
        if key in seen:
            continue
        seen.add(key)
        candidates = resolve(path, repos)
        if not candidates:
            faults.append(f"citation `{path}:{m.group(2)}` resolves to no file under {', '.join(map(str, repos))}")
            continue
        if len(candidates) > 1:
            warns.append(f"`{path}` matches {len(candidates)} files; cite the full path")
        elif "..." in path:
            warns.append(f"`{path}` is elided; a reader cannot open it, cite the full path")
        try:
            content = pathlib.Path(candidates[0]).read_text(errors="replace").splitlines()
        except OSError:
            faults.append(f"citation `{path}:{first}` could not be read")
            continue
        if first > len(content):
            faults.append(f"citation `{path}:{first}` is past the end of the file ({len(content)} lines)")
            continue
        if quote:
            stop = min(int(last) if last else first, len(content))
            for n in range(first, stop + 1):
                notes.append(f"{path}:{n}: {content[n - 1].rstrip()}")
    if seen:
        notes.insert(0, f"{len(seen)} citations checked")
    return faults, warns, notes


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


def inside(file, root):
    try:
        pathlib.Path(file).resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve(path, roots):
    """`Repo/dir/file` is exact; `Repo/.../file`, a path inside a checkout and a bare file name are searched."""
    cos = checkouts(roots)
    head, _, rest = path.partition("/")
    if rest and "..." not in rest:
        for name, co in cos:
            if name == head and (co / rest).is_file() and inside(co / rest, co):
                return [str(co / rest)]
    found = set()
    for name, co in cos:
        if "..." not in path and (co / path).is_file() and inside(co / path, co):
            return [str(co / path)]
        if "..." in path:
            sub = rest if name == head else path
            pattern = str(co / glob.escape(sub).replace("...", "**"))
        else:
            pattern = str(co / "**" / glob.escape(path))
        found |= {f for f in glob.glob(pattern, recursive=True) if pathlib.Path(f).is_file() and inside(f, co)}
    return sorted(found)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--repos", action="append", help="a checkout, or a directory of checkouts; repeatable")
    ap.add_argument("--quote", action="store_true", help="print each cited line")
    ap.add_argument("--no-name-check", action="store_true", help="skip the <id>-spec.md file-name rule")
    args = ap.parse_args()
    path = pathlib.Path(args.file)
    try:
        text = path.read_text()
    except OSError as exc:
        print(f"cannot read {args.file}: {exc}")
        return 1
    faults, warns, notes = lint(text, None if args.no_name_check else path.name, args.repos, args.quote)
    for n in notes:
        print(f"NOTE {n}")
    for w in warns:
        print(f"WARN {w}")
    for f in faults:
        print(f"FAULT {f}")
    print(f"{len(faults)} fault{'s' if len(faults) != 1 else ''}, {len(warns)} warning{'s' if len(warns) != 1 else ''}; "
          f"{len(text)} characters, open half {text.find('<details') if '<details' in text else len(text)}")
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
