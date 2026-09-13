import os


# Settings are created during application import, so test environment values
# must exist before test modules import the app.
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+pysqlite:///:memory:",
)
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-secret-key-which-is-at-least-32-characters-long",
)
