"""
Adds `terms_accepted_at` and `health_data_consent_at` to `users` (see
UserDB's docstring in backend/models/db_models.py for what each records).

Unlike m0001/m0002, this ALTERs an EXISTING table rather than creating a
new one, so `Base.metadata.create_all` (which only ever creates missing
tables, never adds columns to ones that already exist) can't do this one -
hence a real ALTER TABLE here, written to work on both of this project's
supported backends (SQLite locally, Postgres/Neon in production): both
support plain `ALTER TABLE ... ADD COLUMN`, they just spell the boolean-
ish default differently, which is the one thing branched on `dialect.name`
below.

Existing rows get NULL for both columns (nullable=True on the model side)
rather than being back-dated to "consented" - an account created before
this migration existed never actually saw the consent checkbox, so
recording real consent for it here would be fiction. Practical effect:
existing users are treated as not-yet-consented for health-data purposes
until they next touch their injuries list (see UserProfileUpdate handling
in auth_service.update_profile), same as any new signup.

Idempotent against a database that never went through the pre-consent
schema at all: a brand-new database's very first migration (m0001) calls
`Base.metadata.create_all`, which builds `users` from whatever
`db_models.py` looks like AT THAT MOMENT - so on any install created
after this migration file was added, m0001 already creates `users` WITH
both of these columns, and this migration's job is already done before
it ever runs. Checked with an inspector rather than try/adding and
catching "duplicate column" (which is spelled/raised differently across
SQLite vs Postgres) - inspect-then-add works identically on both.
"""
from sqlalchemy import inspect, text

revision = "0003_consent_tracking"

_NEW_COLUMNS = ("terms_accepted_at", "health_data_consent_at")


def upgrade(connection):
    existing = {col["name"] for col in inspect(connection).get_columns("users")}
    dialect = connection.dialect.name  # "sqlite" or "postgresql"
    datetime_type = "DATETIME" if dialect == "sqlite" else "TIMESTAMP"
    for column in _NEW_COLUMNS:
        if column not in existing:
            connection.execute(text(
                f"ALTER TABLE users ADD COLUMN {column} {datetime_type} NULL"
            ))
