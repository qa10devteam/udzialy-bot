#!/usr/bin/env bash
# Downloads the Google Fonts used by the spot into $1 so render.cjs can serve them offline.
set -euo pipefail
FC=${1:?font cache dir}; mkdir -p "$FC"
URL='https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap'
curl -sS -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36" "$URL" -o "$FC/fonts.css"
grep -o 'https://fonts.gstatic.com[^)]*' "$FC/fonts.css" | sort -u | while read -r u; do
  f="$FC/$(echo "$u" | md5sum | cut -c1-16).woff2"; [ -f "$f" ] || curl -sS "$u" -o "$f"
done
