#!/usr/bin/env bash
# Publish the website, and refuse to leave it broken.
#
# Two real failures on 2026-08-26 are what this exists to prevent:
#
#   1. The site shipped for weeks with a download button that led to an install
#      section with no .dmg link and no .dmg file. Nothing was broken in a way
#      any check could see; the page simply did not contain what it promised.
#   2. The first Next deploy returned 404 on `/` while every other path served,
#      because the Vercel project still carried the old static site's settings
#      (Framework Preset "Other", Output Directory `public`). vercel.json pins
#      the framework now, but the PROJECT setting is still "Other" -- so if that
#      file is ever removed, the homepage 404s again exactly the same way.
#
# So this verifies the artifacts before publishing and verifies the live site
# after. A deploy that leaves `/` or the download broken exits non-zero and says
# which one.
set -euo pipefail
cd "$(dirname "$0")/.."

BASE=${ICARUS_SITE_URL:-https://icarus-website-kappa.vercel.app}

echo "==> release check"
python3 scripts/check_release.py

echo "==> build"
( cd web && npm run build >/dev/null )
echo "  ok  next build"

echo "==> deploy"
( cd web && vercel --prod --yes >/dev/null 2>&1 )
echo "  ok  vercel --prod"

echo "==> verify live: $BASE"
fail=0
code=$(curl -s -o /dev/null -m 45 -w '%{http_code}' "$BASE/")
if [ "$code" = "200" ]; then echo "  ok  /  ($code)"; else
  echo "  ✗  /  returned $code."
  echo "     If every other path works, the framework preset is the cause:"
  echo "     Vercel is serving web/public as the output directory."
  fail=1
fi

expected_sha=$(python3 -c 'import json;print(json.load(open("release.json"))["dmg"]["sha256"])')
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
code=$(curl -s -m 300 -o "$tmp" -w '%{http_code}' "$BASE/Icarus.dmg")
got=$(shasum -a 256 "$tmp" | cut -d' ' -f1)
if [ "$code" = "200" ] && [ "$got" = "$expected_sha" ]; then
  echo "  ok  /Icarus.dmg  ($(wc -c < "$tmp") bytes, sha matches)"
else
  echo "  ✗  /Icarus.dmg  http=$code sha=${got:0:12}… expected=${expected_sha:0:12}…"
  fail=1
fi

for path in /appcast.xml /install.sh /graph.json; do
  code=$(curl -s -o /dev/null -m 45 -w '%{http_code}' "$BASE$path")
  if [ "$code" = "200" ]; then echo "  ok  $path"; else echo "  ✗  $path returned $code"; fail=1; fi
done

ctype=$(curl -sI -m 45 "$BASE/install.sh" | tr -d '\r' | awk -F': ' 'tolower($1)=="content-type"{print $2}')
case "$ctype" in
  text/plain*) echo "  ok  install.sh is text/plain" ;;
  *) echo "  ✗  install.sh is '$ctype' — the site tells people to read it before running it"; fail=1 ;;
esac

# These were served publicly by the old site: a log of named prospects and their
# email addresses. Never again, and never silently.
for path in /for/URLS.txt /for/outreach_log.jsonl /for/build_page.py /release-dmg.sh; do
  code=$(curl -s -o /dev/null -m 45 -w '%{http_code}' "$BASE$path")
  if [ "$code" = "404" ]; then echo "  ok  $path is not public"; else echo "  ✗  $path is PUBLIC ($code)"; fail=1; fi
done

if [ "$fail" -ne 0 ]; then
  echo; echo "DEPLOY VERIFICATION FAILED — the site is live and broken. Fix or roll back."
  exit 1
fi
echo; echo "site published and verified."
