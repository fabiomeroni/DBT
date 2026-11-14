#!/usr/bin/env bash
# Brings the server up to date with GitHub without ever stopping on "Aborting".
#
#   ./update.sh
#
# What it does, in order:
#   1. keeps whatever was changed on the server (the author's edits made through the site, new files, anything) in a commit of its own, so nothing
#      is lost and git has nothing left to complain about ("Your local changes would be overwritten", "untracked files would be overwritten");
#   2. fetches GitHub and merges it in. Files changed on one side only are simply updated. If the SAME lines were changed on both sides, the
#      SERVER's version is kept (the author's work on the server is never overwritten) and the file is listed at the end, so that you can look at it;
#   3. tells you what came in. Then restart the application (python app.py, or the service that runs it).
#
# To make GitHub win on the shared lines instead, run:  ./update.sh theirs
set -u
cd "$(dirname "$0")" || exit 1
WIN="${1:-ours}"
case "$WIN" in ours|theirs) ;; *) echo "Usage: ./update.sh [ours|theirs]   (ours = the server wins, the default)"; exit 1;; esac

git rev-parse --git-dir >/dev/null 2>&1 || { echo "This folder is not a git clone."; exit 1; }
[ -f .git/MERGE_HEAD ] && { echo "A merge was left unfinished: finishing it with the server's version."; git checkout --ours . 2>/dev/null; git add -A; git commit -q -m "Finish the merge (server version)" ; }
git rebase --abort >/dev/null 2>&1; git stash list | grep -q . && echo "Note: there are old stashes (git stash list); they are untouched."

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git config user.name  >/dev/null 2>&1 || git config user.name  "DBT server"
git config user.email >/dev/null 2>&1 || git config user.email "server@localhost"

# 1. keep the server's own changes
git add -A
if ! git diff --cached --quiet; then
  git commit -q -m "Edits made on the server, $(date '+%Y-%m-%d %H:%M')" && echo "Saved the edits made on the server (in a commit of its own)."
fi

# 2. fetch and merge
git fetch -q origin || { echo "Could not reach GitHub."; exit 1; }
REMOTE="origin/$BRANCH"
git rev-parse -q --verify "$REMOTE" >/dev/null || { echo "GitHub has no branch $BRANCH."; exit 1; }
BASE="$(git merge-base HEAD "$REMOTE")"
BOTH="$(comm -12 <(git diff --name-only "$BASE" HEAD | sort) <(git diff --name-only "$BASE" "$REMOTE" | sort))"
BEFORE="$(git rev-parse HEAD)"
if ! git merge -q --no-edit -X "$WIN" "$REMOTE" >/tmp/dbt-merge.log 2>&1; then
  # what is left (one side deleted a file the other changed, ...): take the chosen side for everything and finish
  git checkout "--$WIN" . >/dev/null 2>&1
  git add -A
  git commit -q --no-edit >/dev/null 2>&1 || { cat /tmp/dbt-merge.log; echo "The update could not be finished: nothing was lost (git merge --abort goes back)."; exit 1; }
fi

# 3. report
echo
CHANGED="$(git diff --name-only "$BEFORE" HEAD)"
if [ -z "$CHANGED" ]; then echo "Already up to date."; else echo "Updated from GitHub:"; echo "$CHANGED" | sed 's/^/   /'; fi
if [ -n "$BOTH" ]; then
  [ "$WIN" = ours ] && W="the server's version of the shared lines was kept" || W="GitHub's version of the shared lines was taken"
  echo; echo "Changed on BOTH sides ($W): look at these:"; echo "$BOTH" | sed 's/^/   /'
fi
echo; echo "Now restart the application (python app.py, or the service that runs it) and reload the pages."
