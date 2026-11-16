#!/bin/bash
# bake-stats.sh — render the two github-readme-stats cards from the local
# self-hosted instance and commit them into this repo as static SVGs.
# The README points at jsDelivr, so the profile never depends on a live
# tunnel or on the (paused) public vercel deployment.
set -uo pipefail

REPO="/home/ubuntu/profile-readme"
SRC="http://127.0.0.1:3000"
OUT="$REPO/assets"
STATS_URL="$SRC/api?username=EVM0x&show_icons=true&theme=dark&hide_border=true&count_private=true"
LANGS_URL="$SRC/api/top-langs/?username=EVM0x&layout=compact&theme=dark&hide_border=true&langs_count=8"

mkdir -p "$OUT"
fail=0

fetch() { # url outfile
  for attempt in 1 2 3; do
    code=$(curl -s -o "$2.tmp" -w '%{http_code}' --max-time 60 "$1")
    if [ "$code" = "200" ] && grep -q '<svg' "$2.tmp"; then
      mv "$2.tmp" "$2"
      return 0
    fi
    sleep 5
  done
  rm -f "$2.tmp"
  echo "FAIL $2 (http $code)" >&2
  return 1
}

fetch "$STATS_URL" "$OUT/github-stats.svg" || fail=1
fetch "$LANGS_URL" "$OUT/top-langs.svg" || fail=1

[ "$fail" = "0" ] || { echo "bake failed"; exit 1; }

cd "$REPO" || exit 1
git pull --rebase origin main --quiet 2>/dev/null || true

git add assets/github-stats.svg assets/top-langs.svg

if git diff --cached --quiet; then
  echo "cards unchanged"
else
  git commit -m "chore: refresh baked stats cards $(date -u +%Y-%m-%dT%H:%MZ)" --quiet
  git push origin main --quiet && echo "pushed"
fi

# jsDelivr caches gh assets; purge so the CDN serves the new render.
for f in assets/github-stats.svg assets/top-langs.svg; do
  curl -s -o /dev/null --max-time 30 "https://purge.jsdelivr.net/gh/EVM0x/EVM0x@main/$f"
done
echo "purged"
