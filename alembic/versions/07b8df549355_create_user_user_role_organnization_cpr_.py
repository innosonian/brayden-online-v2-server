"""create user, user_role, organnization, cpr_guideline

Revision ID: 07b8df549355
Revises: 
Create Date: 2024-03-08 16:43:59.742961

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07b8df549355'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
