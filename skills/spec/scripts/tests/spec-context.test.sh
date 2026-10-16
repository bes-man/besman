#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="$HERE/../spec-context.py"
FIX="$HERE/fixtures/spec-context.json"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAIL=0
# No network: a gh on the path that fails loudly if anything calls it.
mkdir -p "$TMP/bin"; printf '#!/bin/sh\necho "gh called: $*" >&2; exit 9\n' > "$TMP/bin/gh"; chmod +x "$TMP/bin/gh"
export PATH="$TMP/bin:$PATH"

expect() {
  if printf '%s' "$2" | grep -qF -- "$3"; then echo "ok   $1"
  else echo "FAIL $1: expected '$3' in:"; printf '%s\n' "$2" | sed 's/^/     /' | head -30; FAIL=1; fi
}
reject() {
  if printf '%s' "$2" | grep -qF -- "$3"; then echo "FAIL $1: did not expect '$3'"; FAIL=1
  else echo "ok   $1"; fi
}

# variant <name> <python expression editing d> : writes a fixture derived from the base one
variant() {
  python3 - "$FIX" "$TMP/$1.json" "$2" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
exec(sys.argv[3])
json.dump(d, open(sys.argv[2], "w"))
EOF
  echo "$TMP/$1.json"
}
run() { python3 "$SCRIPT" 101 --fixture "$1" --out "$TMP/out-$(basename "$1" .json)" "${@:2}" 2>&1; }
bundle() { cat "$TMP/out-$1/context.md"; }
mkdir -p "$TMP/repos/storefront/src"; seq 1 5 | sed 's/^/line /' > "$TMP/repos/storefront/src/holds.py"

# The whole thread: a document was posted and a person commented after it.
FULL=$(run "$FIX")
expect "task type from the label"               "$FULL" "task_type=change (label chore)"
expect "the repository comes from the issue"    "$FULL" "ticket=example/bookstore#101"
expect "a comment after the document revises"   "$FULL" "phase=revise"
expect "one answer after the document"          "$FULL" "answers=1"
expect "attachment listed even unfetched"       "$FULL" "attachments=1"
expect "the bundle is written in --out"         "$FULL" "bundle=$TMP/out-spec-context/context.md"
test -f "$TMP/out-spec-context/context.json" && echo "ok   context.json is written" || { echo "FAIL context.json is written"; FAIL=1; }
BUNDLE=$(bundle spec-context)
expect "the answer is quoted without the mention" "$BUNDLE" "REQ-1 should also cover e-book loans."
ANSWERS=$(printf '%s\n' "$BUNDLE" | sed -n '/^## Answers given/,/^## Comments/p')
reject "the mention itself is not an answer"    "$ANSWERS" "@claude"
expect "the parent ticket is in the bundle"     "$BUNDLE" "#90, Feature: Reservations for out-of-stock titles"
expect "a referenced ticket is in the bundle"   "$BUNDLE" "#95, Bug: Reservation shows as collected"
expect "the document comment is classified"     "$BUNDLE" "### document, @shop-bot[bot]"
expect "the report comment is classified"       "$BUNDLE" "### questions, @shop-bot[bot]"
expect "the progress comment is a bot"          "$BUNDLE" "### bot, @shop-bot[bot]"
expect "a person's comment is human"            "$BUNDLE" "### human, @bob"
expect "an unfetched attachment is flagged"     "$BUNDLE" "NOT READABLE"
expect "the resume point names the document"    "$BUNDLE" "resuming from the document posted by @shop-bot[bot]"
expect "no --repos: citations not quoted"       "$BUNDLE" "No --repos directory was given"

# The ticket in its other spellings.
expect "owner/name#n is accepted"               "$(python3 "$SCRIPT" other/shop#101 --fixture "$FIX" --out "$TMP/o1" 2>&1)" "ticket=other/shop#101"
expect "an issue URL is accepted"               "$(python3 "$SCRIPT" https://github.com/other/shop/issues/101 --fixture "$FIX" --out "$TMP/o2" 2>&1)" "ticket=other/shop#101"
expect "--repo names the repository"            "$(python3 "$SCRIPT" 101 --repo other/shop --fixture "$FIX" --out "$TMP/o3" 2>&1)" "ticket=other/shop#101"
expect "garbage is refused"                     "$(python3 "$SCRIPT" not-a-ticket --fixture "$FIX" --out "$TMP/o4" 2>&1 || true)" "is not an issue number"

# Only the trigger and the report: the run is waiting for a person.
F=$(variant waiting 'd["comments"]=d["comments"][:2]')
expect "report and no answer waits"             "$(run "$F")" "phase=awaiting-answers"

# Report, then answers: write the document from the earlier investigation.
F=$(variant answered 'd["comments"]=d["comments"][:3]')
OUT=$(run "$F")
expect "answers after the report mean write"    "$OUT" "phase=write"
expect "the resume point is the report"         "$(bundle answered)" "https://github.com/example/bookstore/issues/101#issuecomment-202"
expect "letter answers are parsed"              "$(bundle answered)" "Parsed as: Q1 A"

# A confirmations comment counts as a report too.
F=$(variant confirm 'd["comments"]=d["comments"][:3]; d["comments"][1]["body"]="### Spec run: nothing blocks\n\n<!-- besman:spec-confirmations -->"; d["comments"][1]["user"]={"login":"alice","type":"User"}')
expect "a confirmations marker from a person"   "$(run "$F")" "phase=write"

# A report from a bot without any marker still counts as questions.
F=$(variant legacy 'd["comments"]=d["comments"][:3]; b=d["comments"][1]["body"]; d["comments"][1]["body"]=b.split("<!--")[0]')
expect "an unmarked bot report is recognised"   "$(run "$F")" "phase=write"

# A stop written by hand: numbered questions, no marker. Still a report.
F=$(variant handwritten 'd["comments"]=d["comments"][:3]; d["comments"][1]["body"]="### Specification not written: the premise does not survive the code\n\n**Q1. Has anyone seen a hold end early?** Recommendation: measure it.\n\n**Q2. Does the ticket stay open?** Recommendation: yes."')
OUT=$(run "$F")
expect "a stop written by hand is recognised"   "$OUT" "phase=write"
expect "and is the resume point"                "$(bundle handwritten)" "issuecomment-202"
expect "and the bundle says what is skipped"    "$(bundle handwritten)" "Repeat run: the investigation is done"

# On a repeat run the lines the report cites are quoted from the checkouts; a vanished one is marked.
F=$(variant cited 'd["comments"]=d["comments"][:3]; d["comments"][1]["body"]+="\n\nThe hold is set at `storefront/src/holds.py:3` and the old check at `storefront/src/gone.py:7`."')
OUT=$(run "$F" --repos "$TMP/repos")
expect "the cited lines are counted"            "$OUT" "cited=1 quoted, 1 not found"
BUNDLE=$(bundle cited)
expect "a cited line is quoted verbatim"        "$BUNDLE" "- storefront/src/holds.py:3: line 3"
expect "a vanished citation is marked"          "$BUNDLE" "NOT FOUND: citation \`storefront/src/gone.py:7\` resolves to no file"
# --repos may also be a checkout itself.
mkdir -p "$TMP/repos/storefront/.git"
expect "a checkout as --repos"                  "$(run "$F" --repos "$TMP/repos/storefront")" "cited=1 quoted, 1 not found"

# Nothing of this pipeline on the thread yet.
F=$(variant fresh 'd["comments"]=d["comments"][:1]')
expect "no report means investigate"            "$(run "$F")" "phase=investigate"
reject "a first run is not told to skip"        "$(bundle fresh)" "Repeat run:"
reject "a first run quotes nothing"             "$(bundle fresh)" "Cited lines from the report"

# A document nobody has answered yet waits too.
F=$(variant docwait 'd["comments"]=d["comments"][:5]')
expect "a document without a reply waits"       "$(run "$F")" "phase=awaiting-answers"

# The gates.
F=$(variant closed 'd["issue"]["state"]="closed"')
OUT=$(run "$F")
expect "a closed issue stops"                   "$OUT" "phase=stop"
expect "and says why"                           "$OUT" "The issue is closed"
F=$(variant spike 'd["issue"]["labels"]=[{"name":"spike"}]')
OUT=$(run "$F")
expect "a spike stops"                          "$OUT" "phase=stop"
expect "and says why"                           "$OUT" "A spike is not a specification"
F=$(variant unlabelled 'd["issue"]["labels"]=[]')
OUT=$(run "$F")
expect "no task label is left to the agent"     "$OUT" "task_type=undecided (no task label)"
reject "and does not stop"                      "$OUT" "phase=stop"
F=$(variant bug 'd["issue"]["labels"]=[{"name":"Bug"},{"name":"frontend"}]')
expect "bug is a bug"                           "$(run "$F")" "task_type=bug (label Bug)"
F=$(variant defect 'd["issue"]["labels"]=[{"name":"type: defect"}]')
expect "a prefixed defect is a bug"             "$(run "$F")" "task_type=bug"
F=$(variant enh 'd["issue"]["labels"]=[{"name":"enhancement"}]')
expect "enhancement is a feature"               "$(run "$F")" "task_type=feature"
F=$(variant refactor 'd["issue"]["labels"]=[{"name":"refactor"}]')
expect "refactor is a change"                   "$(run "$F")" "task_type=change"

# A description pasted from any tracker.
printf '# Gift wrapping at checkout\n\nReaders want to add gift wrap to an order.\n' > "$TMP/SHOP-17.md"
OUT=$(python3 "$SCRIPT" --from-file "$TMP/SHOP-17.md" --out "$TMP/out-file" 2>&1)
expect "a pasted file is read"                  "$OUT" "ticket=SHOP-17 Gift wrapping at checkout"
expect "and investigated"                       "$OUT" "phase=investigate"
expect "the bundle carries the text"            "$(cat "$TMP/out-file/context.md")" "Readers want to add gift wrap"
JSON=$(python3 "$SCRIPT" --from-file "$TMP/SHOP-17.md" --out "$TMP/out-file" --json 2>&1)
expect "--json prints the context"              "$JSON" "\"source\": \"file\""

# Attachments are typed by their bytes, not their name or status code.
SNIFF=$(python3 - "$SCRIPT" <<'EOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ctx", sys.argv[1]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(m.sniff(b"\x89PNG\r\n\x1a\n...."), m.sniff(b"<!DOCTYPE html><html>"), m.sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 "), m.sniff(b"\x00\x00\x00\x18ftypmp42"))
EOF
)
expect "a PNG is readable"                      "$SNIFF" "('image/png', 'png', True)"
expect "a login page is not"                    "$SNIFF" "('text/html', 'html', False)"
expect "a WebP is readable"                     "$SNIFF" "('image/webp', 'webp', True)"
expect "a video is not"                         "$SNIFF" "('video/mp4', 'mp4', False)"

exit $FAIL
