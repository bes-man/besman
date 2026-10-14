#!/usr/bin/env bash
set -euo pipefail

# Posts one review from review.json: inline comments checked against the diff, the rest moved into the body.

FILE="${1:?review.json}"; REPO="${2:?owner/repo}"; PR="${3:?pull request number}"; SHA="${4:?head sha}"
jq -e 'type == "object" and has("body") and (.comments | type == "array")' "$FILE" >/dev/null \
  || { echo "review.json must be an object with body and a comments array" >&2; exit 2; }

# A file, not the environment: the patches of a large pull request exceed the argument limit.
FILES=$(mktemp)
if [ -n "${FILES_JSON:-}" ]; then printf '%s' "$FILES_JSON" > "$FILES"
else gh api "repos/${REPO}/pulls/${PR}/files?per_page=100" --paginate | jq -s 'add' > "$FILES"; fi

OUT=$(mktemp)
REVIEW_FILE="$FILE" FILES="$FILES" SHA="$SHA" OUT="$OUT" python3 - <<'PY'
import json, os, re

review = json.load(open(os.environ["REVIEW_FILE"]))
files = json.load(open(os.environ["FILES"]))
if isinstance(files, dict): files = [files]

# Lines RIGHT can carry: added and context lines of every hunk; LEFT: removed and context lines.
right, left = {}, {}
for f in files:
    r, l = set(), set()
    new = old = 0
    for line in (f.get("patch") or "").splitlines():
        m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            old, new = int(m.group(1)), int(m.group(2)); continue
        if line.startswith("+"): r.add(new); new += 1
        elif line.startswith("-"): l.add(old); old += 1
        elif line.startswith("\\"): continue
        else: r.add(new); l.add(old); new += 1; old += 1
    right[f["filename"]], left[f["filename"]] = r, l

kept, moved = [], []
for c in review.get("comments", []):
    side = c.get("side", "RIGHT"); ok = right if side == "RIGHT" else left
    lines = ok.get(c.get("path", ""), set())
    anchor = c.get("line"); start = c.get("start_line", anchor)
    if anchor in lines and start in lines:
        kept.append(c)
    else:
        moved.append(c)

body = review["body"]
if moved:
    body += "\n\n### Findings on lines the diff does not touch\n" + "\n".join(
        f"\n**{c.get('path')}:{c.get('line')}**\n{c.get('body')}" for c in moved)
payload = {"event": "COMMENT", "commit_id": os.environ["SHA"], "body": body, "comments": kept}
json.dump(payload, open(os.environ["OUT"], "w"))
print(f"anchored={len(kept)} moved_to_body={len(moved)}")
PY

if [ "${DRY_RUN:-}" = "1" ]; then echo "would post one review on ${REPO}#${PR} at ${SHA:0:7}"; jq -c '{event, commit_id, comments: (.comments | length)}' "$OUT"; exit 0; fi
gh api "repos/${REPO}/pulls/${PR}/reviews" --method POST --input "$OUT" --jq '"review \(.id) posted as \(.user.login) on \(.commit_id[:7])"'
WANT=$(jq '.comments | length' "$OUT")
HAVE=$(gh api "repos/${REPO}/pulls/${PR}/comments?per_page=100" --paginate --jq "[.[] | select(.commit_id==\"${SHA}\" and .in_reply_to_id == null)] | length")
echo "inline comments on ${SHA:0:7}: ${HAVE} (this review asked for ${WANT})"
[ "$HAVE" -ge "$WANT" ] || { echo "::error::the review posted but its inline comments did not land" >&2; exit 1; }
