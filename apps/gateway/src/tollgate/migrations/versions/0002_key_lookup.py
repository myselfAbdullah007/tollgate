"""Index the authoritative key hash lookup without changing key storage."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    expression = (
        "CAST((data ->> 'key_hash') AS VARCHAR)"
        if op.get_bind().dialect.name == "postgresql"
        else "CAST(JSON_EXTRACT(data, '$.key_hash') AS VARCHAR)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_records_key_hash ON records (" + expression + ")")


def downgrade():
    op.drop_index("ix_records_key_hash", table_name="records")
