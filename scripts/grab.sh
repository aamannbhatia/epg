#!/usr/bin/env bash
# grab.sh <bucket dir> <output dir> <days> <minutes available>
# Runs every primary source in the bucket, then tries fallback sources for
# channels that came back empty. Each site gets a time limit so one slow site
# cannot stop the others.
set -u
BUCKET="$1"; OUT="$(realpath -m "$2")"; DAYS="$3"; MINUTES="$4"
mkdir -p "$OUT"
EPG="$(realpath epg)"
START=$(date +%s)
left() { echo $(( MINUTES * 60 - ($(date +%s) - START) )); }

run_site() {   # run_site <channels file> <output file>
  local file="$1" out="$2" limit
  limit=$(left); (( limit > 3600 )) && limit=3600
  (( limit < 120 )) && { echo "  no time left, skipping $(basename "$file")"; return; }
  echo "== $(basename "$file")  (limit ${limit}s)"
  ( cd "$EPG" && timeout "$limit" npx tsx scripts/commands/epg/grab.ts \
      --channels="$(realpath "$file")" --output="$out" --days="$DAYS" \
      --maxConnections=8 --timeout=20000 ) || echo "  finished with errors or timed out"
}

for f in "$BUCKET"/primary--*.channels.xml; do
  [ -e "$f" ] || continue
  site="$(basename "$f" .channels.xml)"; site="${site#primary--}"
  run_site "$f" "$OUT/p1--$site.xml"
done

# Second and third chance for channels with no programmes
for order in 1 2; do
  python3 "$(dirname "$0")/fallback.py" --bucket "$BUCKET" --guides "$OUT" --order "$order" --out "$BUCKET/fb$order" || break
  for f in "$BUCKET"/fb$order/*.channels.xml; do
    [ -e "$f" ] || continue
    site="$(basename "$f" .channels.xml)"
    run_site "$f" "$OUT/p$((order+1))--$site.xml"
  done
done
ls -la "$OUT" || true
