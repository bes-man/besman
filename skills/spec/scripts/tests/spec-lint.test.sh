#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="$HERE/../spec-lint.py"
GOOD="$HERE/fixtures/102-spec.md"
POSTED="$HERE/fixtures/spec-as-posted.md"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAIL=0

expect() {
  if printf '%s' "$2" | grep -qF -- "$3"; then echo "ok   $1"
  else echo "FAIL $1: expected '$3' in:"; printf '%s\n' "$2" | sed 's/^/     /' | head -20; FAIL=1; fi
}
reject() {
  if printf '%s' "$2" | grep -qF -- "$3"; then echo "FAIL $1: did not expect '$3'"; FAIL=1
  else echo "ok   $1"; fi
}
# variant <name> <python editing s> : a copy of the good document, edited, named like a spec
variant() {
  mkdir -p "$TMP/$1"
  python3 - "$GOOD" "$TMP/$1/102-spec.md" "$2" <<'EOF'
import sys, pathlib
s = pathlib.Path(sys.argv[1]).read_text()
exec(sys.argv[3])
pathlib.Path(sys.argv[2]).write_text(s)
EOF
  echo "$TMP/$1/102-spec.md"
}
lint() { python3 "$SCRIPT" "$@" 2>&1 || true; }

REPOS="$TMP/repos"
mkdir -p "$REPOS/storefront/src/orders"
seq 1 40 > "$REPOS/storefront/src/orders/order_summary.py"

expect "a sound document passes"            "$(lint "$GOOD" --repos "$REPOS")" "0 faults, 0 warnings"
expect "citations are counted"              "$(lint "$GOOD" --repos "$REPOS")" "NOTE 1 citations checked"
expect "--quote prints the cited line"      "$(lint "$GOOD" --repos "$REPOS" --quote)" "order_summary.py:12: 12"
mkdir -p "$REPOS/storefront/.git"
expect "--repos may be a checkout itself"   "$(lint "$GOOD" --repos "$REPOS/storefront")" "0 faults, 0 warnings"

# Name, size, code, mention, marker.
cp "$GOOD" "$TMP/spec_102.md"
expect "the file name rule"                 "$(lint "$TMP/spec_102.md")" "file name 'spec_102.md' is not <id>-spec.md"
expect "the name rule can be skipped"       "$(lint "$TMP/spec_102.md" --no-name-check)" "0 faults"
cp "$GOOD" "$TMP/gift-wrapping-spec.md"
expect "a slug id is a valid name"          "$(lint "$TMP/gift-wrapping-spec.md")" "0 faults"
cp "$GOOD" "$TMP/SHOP-17-spec.md"
expect "a tracker key is a valid name"      "$(lint "$TMP/SHOP-17-spec.md")" "0 faults"
F=$(variant fence 's=s.replace("## Decisions taken", "```python\nx = 1\n```\n\n## Decisions taken")')
expect "a code fence is a fault"            "$(lint "$F")" "1 code fence(s); a specification carries no code"
F=$(variant mention 's=s.replace("Decisions taken", "Decisions taken (run @claude /spec again)")')
expect "a live mention is a fault"          "$(lint "$F")" "a live @claude mention"
F=$(variant nomarker 's=s.replace("<!-- besman:spec-document -->", "")')
expect "a missing marker is a fault"        "$(lint "$F")" "the document marker is missing"
F=$(variant long 's=s.replace("## 3.1 Functional requirements", "## 3.1 Functional requirements\n\n" + ("Rationale that grew into paragraphs. " * 250))')
expect "an open half over budget"           "$(lint "$F")" "open half is"
F=$(variant huge 's=s + ("x" * 70000)')
expect "over the comment limit"             "$(lint "$F")" "GitHub takes 65536 in one comment"

# The TL;DR.
F=$(variant tldr3 's=s.replace("**Result.** The summary matches what the reader was actually charged.\n", "")')
expect "three TL;DR lines is a fault"       "$(lint "$F")" "found ['Problem', 'Cause', 'Action']"
F=$(variant tldrid 's=s.replace("**Action.** Show", "**Action.** Per REQ-1, show")')
expect "an identifier in the TL;DR"         "$(lint "$F")" "TL;DR names an identifier"
F=$(variant tldrcls 's=s.replace("**Cause.** The summary", "**Cause.** OrderSummaryQueryHandler")')
expect "a class name in the TL;DR"          "$(lint "$F")" "TL;DR names 'OrderSummaryQueryHandler'"
F=$(variant tldrfile 's=s.replace("**Cause.** The summary", "**Cause.** order_summary.py")')
expect "a file name in the TL;DR"           "$(lint "$F")" "TL;DR names a file 'order_summary.py'"
# Names are what make it checkable: a parameter, a status or a value in a span passes; code and paraphrase do not.
F=$(variant tldrspan 's=s.replace("**Cause.** The summary", "**Cause.** The `orderTotal` summary")')
expect "a name in a span passes"            "$(lint "$F")" "0 faults, 0 warnings"
F=$(variant tldrcode 's=s.replace("**Cause.** The summary", "**Cause.** `total = sum(p.amount for p in payments) - refunds`; the summary")')
expect "code in a span is a fault"          "$(lint "$F")" "is code; a span there is a name"
F=$(variant tldrvague 's=s.replace("£42 instead of £30, ", "")')
expect "nothing concrete is a warning"      "$(lint "$F")" "WARN TL;DR Problem and Cause name nothing concrete"

# Requirements, traceability, criteria, empty clauses.
F=$(variant noshall 's=s.replace("shall list every refund", "lists every refund")')
expect "a requirement without shall"        "$(lint "$F")" "REQ-1 does not use 'shall'"
F=$(variant twoshall 's=s.replace("as a separate line.", "as a separate line and shall email the reader.")')
expect "two obligations in one requirement" "$(lint "$F")" "REQ-1 states two obligations"
F=$(variant orphanreq 's=s.replace("- **REQ-2** The total", "- **REQ-3** The reader shall be emailed.\n- **REQ-2** The total")')
expect "a requirement with no VC"           "$(lint "$F")" "REQ-3 has no verification case"
F=$(variant orphanvc 's=s.replace("## 4.4 Traceability", "- **VC-3** `test`: something unrelated.\n\n## 4.4 Traceability")')
expect "a VC verifying nothing"             "$(lint "$F")" "VC-3 verifies no requirement"
F=$(variant nomethod 's=s.replace("- **VC-2** `test`:", "- **VC-2**:")')
expect "a VC with no method"                "$(lint "$F")" "VC-2 names no method"
F=$(variant paperwork 's=s.replace("## Decisions taken", "- **AC-2** The follow-up ticket is raised and the board field is set.\n\n## Decisions taken")')
expect "a paperwork criterion"              "$(lint "$F")" "AC-2 is about paperwork"
F=$(variant empty 's=s.replace("## Decisions taken", "## 5.3 Rejected alternatives\n\nNone.\n\n## Decisions taken")')
expect "an empty clause"                    "$(lint "$F")" "clause '5.3 Rejected alternatives' is empty"
F=$(variant gap 's=s.replace("AC-1", "AC-2")')
expect "numbering gaps are a warning"       "$(lint "$F")" "WARN AC numbering has gaps"

# Citations.
F=$(variant badcite 's=s.replace("order_summary.py:12", "order_summary.py:99")')
expect "a line past the end of the file"    "$(lint "$F" --repos "$REPOS")" "is past the end of the file (40 lines)"
F=$(variant nofile 's=s.replace("orders/order_summary.py:12", "orders/invented.py:3")')
expect "a file that does not exist"         "$(lint "$F" --repos "$REPOS")" "resolves to no file"
F=$(variant bare 's=s.replace("`storefront/src/orders/order_summary.py:12`", "`order_summary.py:12`")')
expect "a bare file name is searched"       "$(lint "$F" --repos "$REPOS")" "0 faults"
reject "no repos, no citation check"        "$(lint "$GOOD")" "citations checked"
F=$(variant elided 's=s.replace("`storefront/src/orders/order_summary.py:12`", "`storefront/.../orders/order_summary.py:12`")')
OUT=$(lint "$F" --repos "$REPOS")
expect "an elided path is resolved"         "$OUT" "0 faults, 1 warning"
expect "and asked to be written in full"    "$OUT" "is elided; a reader cannot open it"
mkdir -p "$TMP/workspace/shop-docs/docs/testing" && seq 1 10 > "$TMP/workspace/shop-docs/docs/testing/rc-tests.md"
F=$(variant tworoots 's=s.replace("## Decisions taken", "The release script `docs/testing/rc-tests.md:7` covers it.\n\n## Decisions taken")')
expect "a second root is searched"          "$(lint "$F" --repos "$REPOS" --repos "$TMP/workspace")" "NOTE 2 citations checked"
expect "a second root is searched: clean"   "$(lint "$F" --repos "$REPOS" --repos "$TMP/workspace")" "0 faults"
mkdir -p "$TMP/outside" && seq 1 10 > "$TMP/outside/secret.py"
F=$(variant escape 's=s.replace("`storefront/src/orders/order_summary.py:12`", "`storefront/../../outside/secret.py:1`")')
expect "a citation may not leave its checkout" "$(lint "$F" --repos "$REPOS")" "resolves to no file"

# A document as a first run once posted it: structurally sound, but it carries no marker.
OUT=$(lint "$POSTED" --no-name-check)
expect "as posted: the document has no marker" "$OUT" "the document marker is missing"
expect "as posted: one fault only"             "$OUT" "1 fault, 0 warnings"
expect "as posted: within the open-half budget" "$OUT" "open half 5057"

exit $FAIL
