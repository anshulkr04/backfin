#!/bin/bash
# Sync frontend to ~/marketwire-frontend
# Usage: ./sync-frontend.sh

set -e

SRC="/Users/anshulkumar/backfin/frontend/"
DEST="$HOME/marketwire-frontend/"

echo "⟳ Syncing frontend → $DEST"

# Copy source files, skip node_modules, .next, and .git (they break on copy)
rsync -av --delete \
  --exclude 'node_modules' \
  --exclude '.next' \
  --exclude '.git' \
  "$SRC" "$DEST"

# Install dependencies fresh
echo ""
echo "⟳ Installing dependencies..."
cd "$DEST" && npm install --silent

# Build to verify
echo ""
echo "⟳ Building..."
npx next build

echo ""
echo "✓ Done — $DEST is ready"
