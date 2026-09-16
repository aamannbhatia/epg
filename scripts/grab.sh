#!/usr/bin/env bash
# grab.sh <bucket dir> <output dir> <days> <minutes available>
# Runs every primary source in the bucket, then tries fallback sources for
# channels that came back empty. Each site gets a time limit so one slow site
# cannot stop the others. The job fails (red) if no guide was downloaded at all.
set -u
BUCKET="$(realpath -m "$1")"; OUT="$(realpath -m "$2")"; DAYS="$3"; MINUTES="$4"
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
EPG="$(realpath epg)"
mkdir -p "$OUT"
START=$(date +%s)
left() { echo $(( MINUTES * 60 - ($(date +%s) - START) )); }

run_site() {   # run_site <channels file> <output file>
  local file out limit
  file="$(realpath "$1")"        # absolute path BEFORE changing directory
  out="$2"
  limit=$(left); (( limit > 3600 )) && limit=3600
  if (( limit < 120 )); then echo "  no time left, skipping $(basename "$file")"; return; fi
  echo "== $(basename "$file")  ($(grep -c '<channel ' "$file") channels, limit ${limit}s)"
  ( cd "$EPG" && timeout "$limit" npx tsx scripts/commands/epg/grab.ts \
      --channels="$file" --output="$out" --days="$DAYS" \
      --maxConnections=8 --timeout=20000 ) || echo "  finished with errors or timed out"
  if [ -s "$out" ]; then
    echo "  saved $(grep -o '<programme ' "$out" | wc -l) programmes"
  fi
}

for f in "$BUCKET"/primary--*.channels.xml; do
  [ -e "$f" ] || continue
  site="$(basename "$f" .channels.xml)"; site="${site#primary--}"
  run_site "$f" "$OUT/p1--$site.xml"
done

# Second and third chance for channels with no programmes
for order in 1 2; do
  python3 "$SCRIPTS/fallback.py" --bucket "$BUCKET" --guides "$OUT" --order "$order" --out "$BUCKET/fb$order" || break
  for f in "$BUCKET"/fb$order/*.channels.xml; do
    [ -e "$f" ] || continue
    site="$(basename "$f" .channels.xml)"
    run_site "$f" "$OUT/p$((order+1))--$site.xml"
  done
done

echo
ls -la "$OUT"
if ! ls "$OUT"/*.xml >/dev/null 2>&1; then
  echo "ERROR: no guide file was downloaded in this bucket."
  exit 1
fi
