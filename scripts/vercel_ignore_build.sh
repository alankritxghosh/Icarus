#!/usr/bin/env bash
# Vercel's Ignored Build Step. Runs from the REPO ROOT (not web/, even though
# the project's Root Directory is web/) on every push, before any build.
#
# Exit 0 = skip the deploy. Exit 1 (or any nonzero) = build and deploy.
#
# Purpose: this repo has one Vercel project (the website) fed by a monorepo
# where most commits are brain work -- evals/, demo/, docs/experiments/ -- that
# has nothing to do with the site. Without this, every one of those pushes
# rebuilds and redeploys web/ for no reason: wasted build minutes, and a new
# production deployment with nothing different in it.
#
# Fail SAFE toward building: if the previous commit is unknown (first deploy,
# shallow clone, force-push) `git diff` errors, and this treats "cannot tell"
# as "build it" rather than silently skipping a deploy that should have
# happened. A missed rebuild is invisible; an unwanted one costs a few minutes.
PREV="${VERCEL_GIT_PREVIOUS_SHA:-HEAD^}"

if ! git diff --quiet "$PREV" HEAD -- web/ release.json 2>/dev/null; then
  echo "web/ or release.json changed since $PREV — building"
  exit 1
fi

echo "no change under web/ or release.json since $PREV — skipping deploy"
exit 0
