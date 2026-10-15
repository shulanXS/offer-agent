#!/usr/bin/env bash
# F3：OpenAPI schema → TypeScript types
# 用法：bash scripts/gen-types.sh

set -e

API_BASE="${1:-http://localhost:8000}"
OUT_DIR="${2:-frontend/src/types/generated}"

mkdir -p "$OUT_DIR"

echo "Fetching OpenAPI schema from $API_BASE ..."
curl -sf "$API_BASE/openapi.json" -o "$OUT_DIR/openapi.json"

echo "Generating TypeScript types ..."
npx --yes openapi-typescript "$OUT_DIR/openapi.json" \
  --output "$OUT_DIR/api.ts" \
  --options \
    --prettier-config '{"semi":false,"singleQuote":true}' \
  || echo "openapi-typescript failed, types not generated"

echo "Done. Types written to $OUT_DIR/api.ts"
