#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPT="$HERE/../spec-questions.py"
FIX="$HERE/fixtures/spec-questions.yaml"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
FAIL=0
python3 -c 'import yaml' 2>/dev/null || { echo "FAIL PyYAML is not installed for $(command -v python3): python3 -m pip install pyyaml"; exit 1; }

expect() {
  if printf '%s' "$2" | grep -qF -- "$3"; then echo "ok   $1"
  else echo "FAIL $1: expected '$3' in:"; printf '%s\n' "$2" | sed 's/^/     /' | head -20; FAIL=1; fi
}
reject() {
  if printf '%s' "$2" | grep -qF -- "$3"; then echo "FAIL $1: did not expect '$3'"; FAIL=1
  else echo "ok   $1"; fi
}
# variant <name> <python editing d>
variant() {
  python3 - "$FIX" "$TMP/$1.yaml" "$2" <<'EOF'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
exec(sys.argv[3])
yaml.safe_dump(d, open(sys.argv[2], "w"), allow_unicode=True, sort_keys=False)
EOF
  echo "$TMP/$1.yaml"
}

# A project with a knowledge base, its docs and a domain vocabulary.
PROJECT="$TMP/project"
KB="$PROJECT/.besman"
mkdir -p "$KB" "$PROJECT/docs"
echo "# Domain model" > "$PROJECT/docs/domain-model.md"
cat > "$KB/project.md" <<'EOF'
# Project

## Domain vocabulary

- GiftCardLedger — the record of every gift card balance
- `ReadingCopy`
- **BackOrder**: a title ordered from the publisher

## Services

- StorefrontApiGateway
EOF
lint() { python3 "$SCRIPT" lint "$1" --kb "$KB" "${@:2}" 2>&1 || true; }

# A ticket text the quotes are checked against, and fake checkouts for the citations.
cat > "$TMP/context.md" <<'EOF'
# Ticket 101
1. A reserved copy stays on hold for **48 hours**. **The shop's own reading copy must never be put on hold.**
4. Held copies are for collection only, in the "In stock" line.
### Success Metrics
Not yet defined.
EOF
R="$TMP/repos"
mkdir -p "$R/storefront/src/reservations" "$R/storefront/web/pages/reservation" "$R/till/src/checkout"
seq 1 120 > "$R/storefront/src/reservations/reservation_rules.py"
seq 1 60  > "$R/storefront/src/reservations/unavailable_notice.py"
seq 1 80  > "$R/storefront/src/reservations/hold_expiry.py"
seq 1 150 > "$R/storefront/web/pages/reservation/HoldStatus.tsx"
seq 1 30  > "$R/till/src/checkout/held_copies.py"

OK=$(lint "$FIX" --ticket "$TMP/context.md" --repos "$R")
expect "a sound file passes"                  "$OK" "ok: 3 questions (2 blocking), 2 settled, 1 assumptions"
mkdir -p "$R/storefront/.git" "$R/till/.git"
expect "checkouts given one by one"           "$(lint "$FIX" --repos "$R/storefront" --repos "$R/till")" "ok: 3 questions"
expect "a slug ticket id is fine"             "$(lint "$(variant slug 'd["ticket"]="SHOP-17"')")" "ok: 3 questions"
expect "a missing ticket id is a fault"       "$(lint "$(variant noticket 'del d["ticket"]')")" "ticket: an issue number or a slug is required"

# The three anchors.
F=$(variant noquote 'del d["questions"][0]["anchor"]["ticket"]')
expect "no ticket quote is a fault"           "$(lint "$F")" "Q1.anchor.ticket: quote the sentence"
F=$(variant badquote 'd["questions"][0]["anchor"]["ticket"]="show a spinner while reserving"')
expect "a quote not in the ticket is a fault" "$(lint "$F" --ticket "$TMP/context.md")" "is not in the ticket or its comments"
F=$(variant nocode 'd["questions"][0]["anchor"]["code"]=[]')
expect "no code anchor is a fault"            "$(lint "$F")" "Q1.anchor.code: cite what the system does today"
F=$(variant badcite 'd["questions"][0]["anchor"]["code"]=["storefront/made/up/file.py:12"]')
expect "a citation that does not resolve"     "$(lint "$F" --repos "$R")" "storefront/made/up/file.py:12 does not exist"
F=$(variant badrepo 'd["questions"][0]["anchor"]["code"]=["warehouse/src/x.py:1"]')
expect "a repository not among the checkouts" "$(lint "$F" --repos "$R")" "no checkout named 'warehouse'"
F=$(variant escape 'd["questions"][0]["anchor"]["code"]=["storefront/../till/src/checkout/held_copies.py:1"]')
expect "a citation may not leave its checkout" "$(lint "$F" --repos "$R")" "points outside the checkout"
F=$(variant pastend 'd["questions"][1]["anchor"]["code"]=["storefront/web/pages/reservation/HoldStatus.tsx:900"]')
expect "a line past the end of the file"      "$(lint "$F" --repos "$R")" "is past the end of the file (150 lines)"
F=$(variant notcite 'd["questions"][1]["anchor"]["code"]=["HoldStatus.tsx"]')
expect "a citation must be Repo/path:line"    "$(lint "$F")" "is not Repo/path:line"
F=$(variant nodocs 'del d["questions"][0]["anchor"]["docs"]')
expect "no docs anchor is a fault"            "$(lint "$F")" "Q1.anchor.docs: a path relative to the project root, or 'silent'"
F=$(variant baddoc 'd["questions"][0]["anchor"]["docs"]="docs/no-such-file.md"')
expect "a docs path that does not exist"      "$(lint "$F")" "'docs/no-such-file.md' does not exist under"
F=$(variant absdoc 'd["questions"][0]["anchor"]["docs"]="/etc/hosts"')
expect "a docs path must be relative"         "$(lint "$F")" "must be relative to the project root"
F=$(variant noopen 'd["questions"][0]["anchor"]["open_because"]=""')
expect "no reason it is open is a fault"      "$(lint "$F")" "Q1.anchor.open_because"

# The shape of a question.
F=$(variant notype 'd["questions"][0]["type"]="technical"')
expect "a technical question is not asked"    "$(lint "$F")" "a question that fits none is technical and is not asked"
F=$(variant depends 'd["questions"][1]["depends_on"]="Q1"')
expect "a dependent question is folded"       "$(lint "$F")" "Q2: depends on Q1, fold it into that question's conditions"
F=$(variant onecons 'del d["questions"][0]["options"][1]["consequence"]')
expect "every option has a consequence"       "$(lint "$F")" "Q1.B: no consequence"
F=$(variant badrec 'd["questions"][0]["recommendation"]="Z"')
expect "the recommendation is an option"      "$(lint "$F")" "recommendation must name one of the options"
F=$(variant dup 'import copy; q=copy.deepcopy(d["questions"][0]); q["id"]="Q4"; q["question"]="Same thing asked again?"; d["questions"].append(q)')
expect "two questions with the same options"  "$(lint "$F")" "Q4: the same options as Q1, one question, not two"
F=$(variant many 'import copy
for i in range(4, 9):
    q=copy.deepcopy(d["questions"][0]); q["id"]=f"Q{i}"; q["options"][0]["text"]=f"Option {i}"; d["questions"].append(q)')
OUT=$(lint "$F")
expect "more than four blocking is a fault"   "$OUT" "7 BLOCKING questions; at most 4 per stop"
expect "more than six in total is a fault"    "$OUT" "8 questions; at most 6 per stop"

# The language of the visible layer.
F=$(variant path 'd["questions"][0]["question"]="Should hold_expiry.py keep the grace period?"')
expect "a file name in the question"          "$(lint "$F")" "file name 'hold_expiry.py'"
F=$(variant cls 'd["questions"][0]["options"][0]["text"]="Keep the ReservationHoldExpiryScheduler rule."')
expect "a class name in an option"            "$(lint "$F")" "implementation name 'ReservationHoldExpiryScheduler'"
F=$(variant stop 'd["questions"][0]["reason"]="The DTO has no copy id and the page polls the endpoint."')
OUT=$(lint "$F")
expect "an implementation word: DTO"          "$OUT" "implementation word 'DTO'"
expect "an implementation word: polls"        "$OUT" "implementation word 'polls'"
expect "an implementation word: endpoint"     "$OUT" "implementation word 'endpoint'"
F=$(variant span 'd["questions"][1]["question"]="What does `heldCopies` show?"')
expect "a code span in the question"          "$(lint "$F")" "code span \`heldCopies\`"
F=$(variant ms 'd["questions"][1]["reason"]="The page refreshes every 30000 ms."')
expect "a timing setting"                     "$(lint "$F")" "timing detail '30000 ms'"
F=$(variant snake 'd["questions"][1]["reason"]="The hold_until date decides it."')
expect "a snake_case identifier"              "$(lint "$F")" "identifier 'hold_until'"
F=$(variant domain 'd["questions"][1]["question"]="Does a GiftCardLedger entry exist for a ReadingCopy, and is a BackOrder held?"')
reject "domain vocabulary names are allowed"  "$(lint "$F")" "FAULT"
expect "without the vocabulary they are not"  "$(python3 "$SCRIPT" lint "$F" 2>&1 || true)" "implementation name 'GiftCardLedger'"
F=$(variant notvocab 'd["questions"][1]["question"]="Does the StorefrontApiGateway hold it?"')
expect "only the vocabulary section counts"   "$(lint "$F")" "implementation name 'StorefrontApiGateway'"

# Rendering.
RENDER=$(python3 "$SCRIPT" render "$FIX" --kb "$KB")
expect "the headline counts blocking only"    "$RENDER" "### Spec run stopped: 2 decisions need you first"
expect "settled facts are listed"             "$RENDER" "- The message for a reservation that cannot be filled is already built"
expect "evidence is folded"                   "$RENDER" "<details><summary>Evidence</summary>"
expect "a question with its type"             "$RENDER" "#### Q1: Should the reading copy count as an available copy when a reader reserves a title?  \`BLOCKING\` · business"
expect "options with consequences"            "$RENDER" "**C**: In stock: 1. *Consequence:* The visitor keeps waiting"
expect "the recommendation"                   "$RENDER" "*Recommended: B.* Telling a visitor how many copies are free"
expect "conditions replace dependent questions" "$RENDER" "- If A, and the reading copy is the only one"
expect "anchors are folded"                   "$RENDER" "<details><summary>Why this is still open</summary>"
expect "silent docs are said in words"        "$RENDER" "the documentation says nothing about this"
expect "a docs path is shown"                 "$RENDER" "- Docs: \`docs/domain-model.md\`"
expect "deferrable questions come after"      "$RENDER" "#### Can wait: answer if you like"
expect "assumptions are listed"               "$RENDER" "- **A-1** A hold is placed on the copy nearest"
expect "how to answer"                        "$RENDER" "Reply with one line per question, for example: \`Q1 B, Q2 B\`"
expect "the questions marker"                 "$RENDER" "<!-- besman:spec-questions -->"
expect "the awaiting marker"                  "$RENDER" "<!-- besman:awaiting spec -->"
reject "no live mention"                      "$RENDER" "@claude"
F=$(variant broken 'del d["questions"][0]["reason"]')
OUT=$(python3 "$SCRIPT" render "$F" --kb "$KB" 2>&1 || true)
expect "render refuses a faulty file"         "$OUT" "nothing rendered"
reject "and renders nothing"                  "$OUT" "### Spec run stopped"
F=$(variant none 'd["questions"]=[]')
RENDER=$(python3 "$SCRIPT" render "$F" --kb "$KB")
expect "no questions: a confirmation comment" "$RENDER" "### Spec run: nothing blocks"
expect "no questions: the confirmations marker" "$RENDER" "<!-- besman:spec-confirmations -->"
reject "no questions: no awaiting marker"     "$RENDER" "besman:awaiting spec"

# Eight questions a first run once posted: the lint must refuse them, for these reasons.
OUT=$(lint "$HERE/fixtures/spec-questions-as-posted.yaml")
expect "as posted: too many blocking"         "$OUT" "7 BLOCKING questions; at most 4 per stop"
expect "as posted: too many in total"         "$OUT" "8 questions; at most 6 per stop"
expect "as posted: Q5 depends on Q4"          "$OUT" "Q5: depends on Q4"
expect "as posted: Q7 depends on Q2"          "$OUT" "Q7: depends on Q2"
expect "as posted: a file name in Q2"         "$OUT" "Q2.question: file name 'ReadingCopyPolicyRuleHandler.py'"
expect "as posted: polling in Q6"             "$OUT" "Q6.question: implementation word 'polls'"
reject "as posted: the anchor is not linted"  "$OUT" "open_because: implementation word"

exit $FAIL
