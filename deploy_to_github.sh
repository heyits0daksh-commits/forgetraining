#!/bin/sh
# Usage: sh deploy_to_github.sh https://github.com/YOURNAME/forge.git
set -e
git init -q
git add -A
git commit -q -m "FORGE" || true
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$1"
git push -u origin main
