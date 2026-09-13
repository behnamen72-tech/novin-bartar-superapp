# Migration Fix 0.1.1

Fixed duplicate PostgreSQL enum creation in B1 and B3 Alembic migrations.
The enum types are now created by the table DDL only once.
