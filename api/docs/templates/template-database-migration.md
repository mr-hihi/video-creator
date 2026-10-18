# Template — Alembic revision

`alembic/versions/NNNN_<slug>.py`

```python
"""<what the revision does>

Revision ID: NNNN
Revises: <previous>
Create Date: YYYY-MM-DD
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "NNNN"
down_revision: str | None = "<previous>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_TYPE = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    op.add_column("jobs", sa.Column("display_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "display_name")
```

Check without a DB: `APP_ENV=local uv run alembic upgrade head --sql`.
