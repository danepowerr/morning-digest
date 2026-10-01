#!/bin/zsh
# Manual run. The daily "Morning Brief" scheduled task in the Claude app does all of this
# for you each morning using your subscription — you normally don't need this script.
#
#   ./run.sh           refresh the jobs dashboard and open the latest brief
#   ./run.sh api       also rebuild the brief now using an API key (needs a .env file)
#   ./run.sh preview   rebuild the brief with raw headlines, no AI (layout check)
cd "$(dirname "$0")"
.venv/bin/python jobs.py
if [ "$1" = "api" ]; then
  [ -f .env ] && source .env
  .venv/bin/python digest.py api || exit 1
elif [ "$1" = "preview" ]; then
  .venv/bin/python digest.py preview || exit 1
fi
open output/index.html
