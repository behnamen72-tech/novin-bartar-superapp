# Phase A1 — Initial Project Skeleton (Revision 2)

Status: Approved

## Applied review fixes
1. Physical Core and Business Module package boundaries were added to source code.
2. DATABASE_URL is now required; there is no password-bearing default in config.py.
3. CORS configuration was added and is environment-controlled.
4. Ruff and Mypy were added, and public API routes are versioned under /api/v1.

## Extra hardening
PostgreSQL credentials are no longer hardcoded in docker-compose.yml; they are loaded from environment variables.
