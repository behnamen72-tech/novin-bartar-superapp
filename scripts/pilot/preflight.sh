#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FAILURES=0
WARNINGS=0

pass() { printf 'PASS  %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; WARNINGS=$((WARNINGS + 1)); }
fail() { printf 'FAIL  %s\n' "$1"; FAILURES=$((FAILURES + 1)); }

printf 'Novin Bartar Super App — pilot preflight\n'
printf 'Root: %s\n\n' "$ROOT"

if command -v python >/dev/null 2>&1; then
  PYVER="$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if [[ "$PYVER" == "3.12" ]]; then pass "Python 3.12"; else warn "Python is $PYVER; CI baseline is Python 3.12"; fi
else
  fail "python command is unavailable"
fi

if command -v node >/dev/null 2>&1; then pass "Node available: $(node --version)"; else fail "Node is unavailable"; fi
if command -v npm >/dev/null 2>&1; then pass "npm available: $(npm --version)"; else fail "npm is unavailable"; fi

if [[ -f "$ROOT/frontend/package-lock.json" ]]; then
  pass "frontend/package-lock.json is committed/present"
else
  fail "frontend/package-lock.json is missing; reproducible frontend CI/pilot is blocked"
fi

ENV_FILE="${PILOT_ENV_FILE:-$ROOT/backend/.env}"
if [[ -f "$ENV_FILE" ]]; then
  pass "environment file found: $ENV_FILE"
  if grep -Eq '^JWT_SECRET_KEY=replace-with-' "$ENV_FILE"; then fail "JWT secret still uses example placeholder"; else pass "JWT secret is not the documented placeholder"; fi
  if grep -Eq '^CORS_ALLOWED_ORIGINS=.*\*' "$ENV_FILE"; then fail "wildcard CORS is not allowed for pilot"; else pass "CORS does not contain wildcard"; fi
  if grep -Eq '^DATABASE_URL=postgresql\+psycopg://' "$ENV_FILE"; then pass "DATABASE_URL uses PostgreSQL/psycopg"; else fail "DATABASE_URL must use PostgreSQL/psycopg for pilot"; fi
else
  warn "pilot environment file not found at $ENV_FILE; set PILOT_ENV_FILE to validate a deployment env file"
fi

if [[ -d "$ROOT/backend" ]]; then
  (
    cd "$ROOT/backend"
    HEADS="$(python -m alembic heads 2>/dev/null || true)"
    HEAD_COUNT="$(printf '%s\n' "$HEADS" | grep -c '(head)' || true)"
    if [[ "$HEAD_COUNT" -eq 1 ]]; then
      pass "exactly one Alembic head: $(printf '%s' "$HEADS" | tr '\n' ' ')"
    else
      fail "expected exactly one Alembic head; got: ${HEADS:-<none>}"
    fi
    if python -m compileall -q app tests scripts; then pass "backend compile sweep"; else fail "backend compile sweep"; fi
  )
else
  fail "backend directory missing"
fi

if node "$ROOT/frontend/scripts/check-d3-suppliers.cjs" >/dev/null; then
  pass "D3 frontend deterministic check"
else
  fail "D3 frontend deterministic check"
fi

printf '\nSummary: %d failure(s), %d warning(s)\n' "$FAILURES" "$WARNINGS"
if [[ "$FAILURES" -gt 0 ]]; then
  exit 1
fi
