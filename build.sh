#!/usr/bin/env bash
# Builds dist/install-besman.sh: one self-contained installer with every kit file embedded as plain text.
set -euo pipefail

KIT="$(cd "$(dirname "$0")" && pwd)"
OUT="$KIT/dist/install-besman.sh"
mkdir -p "$KIT/dist"

FILES=$(cd "$KIT" && find skills agents -type f ! -name '.DS_Store' ! -name '*.pyc' ! -path '*/__pycache__/*' | sort)

{
cat <<'HEAD'
#!/usr/bin/env bash
# besman: installs the review, test and project skills and their subagents into Claude Code.
set -euo pipefail

usage() {
  echo "bash install-besman.sh                    install into ~/.claude (every project)"
  echo "bash install-besman.sh --project <dir>    install into <dir>/.claude (one project, can be committed)"
  echo "Existing files with the same names are backed up to *.bak-<timestamp>."
}

DEST="$HOME/.claude"
case "${1:-}" in
  --project) DEST="$(cd "${2:?--project needs a directory}" && pwd)/.claude" ;;
  -h|--help) usage; exit 0 ;;
  "") ;;
  *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
esac

STAMP=$(date +%Y%m%d%H%M%S)
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
put() {
  local path="$DEST/$1"
  mkdir -p "$(dirname "$path")"
  if [ -e "$path" ] && ! cmp -s "$TMP" "$path"; then cp "$path" "$path.bak-$STAMP"; echo "backed up $path"; fi
  cp "$TMP" "$path"
  chmod 644 "$path"
}

HEAD
n=0
for f in $FILES; do
  n=$((n+1))
  marker="__REVIEW_KIT_EOF_${n}__"
  # The heredoc marker must not occur inside the file it wraps.
  if awk -v m="$marker" '$0 == m { found = 1 } END { exit !found }' "$KIT/$f"; then echo "marker clash in $f" >&2; exit 1; fi
  printf "cat > \"\$TMP\" <<'%s'\n" "$marker"
  cat "$KIT/$f"
  if [ -n "$(tail -c1 "$KIT/$f")" ]; then echo; fi
  printf '%s\nput %q\n\n' "$marker" "$f"
done
cat <<'TAIL'
chmod +x "$DEST"/skills/*/scripts/*.sh "$DEST"/skills/*/scripts/*.py 2>/dev/null || true

echo "besman installed into $DEST:"
echo "  skills: review, test, project  /review, /test, /project"
echo "  agents: review-* (4), test-* (4)"
for tool in git gh jq python3; do command -v "$tool" >/dev/null || echo "  warning: $tool not found; the skill needs it"; done
echo "Restart Claude Code (or start a new session) to pick them up."
TAIL
} > "$OUT"

chmod +x "$OUT"
bash -n "$OUT"
echo "built $OUT ($n files)"
