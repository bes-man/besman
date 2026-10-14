#!/usr/bin/env python3
"""Merge the four lenses' JSON into one ranked list, by mechanism.

    review-merge.py <out.json> <lens.json>...

Each lens file: {"lens": str, "findings": [...], "missing_information": [...], "not_checked": [...], "notes": [...]}.
A finding: severity Blocking|Major|Minor|Note, file, line, end_line, title, failure, evidence, fix, confidence.
Findings on the same file within two lines are one defect: the strictest severity wins, the sharpest
(longest) failure text is kept, and every lens that raised it is recorded. A lens file that does not
parse is reported as a check not run, never silently dropped.
"""
import json
import sys

ORDER = {"Blocking": 0, "Major": 1, "Minor": 2, "Note": 3}
LIMITS = {"title": 120, "failure": 600, "evidence": 400, "fix": 400}
MAX_PER_LENS = 15


def load(path):
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
            return None, f"{path}: not an object with a findings list"
        return data, None
    except (OSError, ValueError) as e:
        return None, f"{path}: {e}"


def clean(finding, lens):
    f = dict(finding)
    f["severity"] = f.get("severity") if f.get("severity") in ORDER else "Note"
    for k, n in LIMITS.items():
        v = f.get(k)
        f[k] = (v[:n] if isinstance(v, str) else None)
    try:
        f["line"] = int(f["line"]) if f.get("line") is not None else None
    except (TypeError, ValueError):
        f["line"] = None
    f["confidence"] = f.get("confidence") if f.get("confidence") in ("CONFIRMED", "PLAUSIBLE") else "PLAUSIBLE"
    f["lenses"] = [lens]
    return f


def same_defect(a, b):
    if not a.get("file") or a.get("file") != b.get("file"):
        return False
    if a.get("line") is None or b.get("line") is None:
        return a.get("title") == b.get("title")
    return abs(a["line"] - b["line"]) <= 2


# Written when a lens ran out of turns or time; its silence is not a clean result.
LENS_FAILED = ("lens did not deliver", "lens timed out")


def merge(files):
    merged, missing, not_checked, notes, failed, silent = [], [], [], [], [], []
    for path in files:
        data, err = load(path)
        if err:
            failed.append(err)
            continue
        lens = data.get("lens") or path
        for raw in data["findings"][:MAX_PER_LENS]:
            f = clean(raw, lens)
            for m in merged:
                if same_defect(m, f):
                    if ORDER[f["severity"]] < ORDER[m["severity"]]:
                        m["severity"] = f["severity"]
                    if len(f.get("failure") or "") > len(m.get("failure") or ""):
                        m["failure"], m["title"] = f["failure"], f["title"] or m["title"]
                    if f["confidence"] == "CONFIRMED":
                        m["confidence"] = "CONFIRMED"
                    if not m.get("fix") and f.get("fix"):
                        m["fix"] = f["fix"]
                    m["lenses"] = sorted(set(m["lenses"] + [lens]))
                    break
            else:
                merged.append(f)
        missing += [dict(m, lens=lens) for m in data.get("missing_information") or []]
        not_checked += [f"{lens}: {n}" for n in data.get("not_checked") or []]
        notes += [f"{lens}: {n}" for n in data.get("notes") or []]
        if any(str(n).startswith(LENS_FAILED) for n in data.get("not_checked") or []):
            silent.append(lens)
    merged.sort(key=lambda f: (ORDER[f["severity"]], f.get("file") or "", f.get("line") or 0))
    counts = {s: sum(1 for f in merged if f["severity"] == s) for s in ORDER}
    return {"findings": merged, "counts": counts, "missing_information": missing,
            "not_checked": not_checked + [f"lens output unreadable, {e}" for e in failed], "notes": notes,
            "incomplete": silent + failed,
            "verdict": "NOT READY" if counts["Blocking"] else "READY WITH FIXES" if counts["Major"]
            else "INCOMPLETE" if silent or failed else "READY"}


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    out, files = sys.argv[1], sys.argv[2:]
    result = merge(files)
    with open(out, "w") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    c = result["counts"]
    print(f"{result['verdict']}: {len(result['findings'])} finding(s) from {len(files)} lens file(s): "
          f"{c['Blocking']} blocking, {c['Major']} major, {c['Minor']} minor, {c['Note']} note; "
          f"{len(result['missing_information'])} missing, {len(result['not_checked'])} not checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
