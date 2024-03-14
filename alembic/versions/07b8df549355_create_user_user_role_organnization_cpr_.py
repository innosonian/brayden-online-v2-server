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
    op.create_table('user_role',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('role', sa.String(length=50), nullable=True),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_role'))
                    )
    op.create_index(op.f('ix_user_role_id'), 'user_role', ['id'], unique=False)

    op.create_table('organization',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('organization_name', sa.String(length=200), unique=True),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_organization'))
                    )
    op.create_index(op.f('ix_organization_id'), 'organization', ['id'], unique=False)

    op.create_table('user',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('email', sa.String(length=100), nullable=True),
                    sa.Column('password_hashed', sa.String(length=200), nullable=True),
                    sa.Column('name', sa.String(length=50), nullable=True),
                    sa.Column('employee_id', sa.String(length=100), nullable=True),
                    sa.Column('token', sa.String(length=100), nullable=True),
                    sa.Column('token_expiration', sa.DATETIME(), nullable=True),
                    sa.Column('user_role_id', sa.Integer(), nullable=True),
                    sa.Column('organization_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['user_role_id'], ['user_role.id'],
                                            name=op.f('fk_user_role_id_user_role')),
                    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'],
                                            name=op.f('fk_users_organization_id_organization')),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_user'))
                    )
    op.create_index(op.f('ix_user_id'), 'user', ['id'], unique=False)

    op.create_table('cpr_guideline',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('title', sa.String(length=100)),
                    sa.Column('compression_depth', sa.JSON),
                    sa.Column('ventilation_volume', sa.JSON),
                    sa.PrimaryKeyConstraint('id', name=op.f('pk_cpr_guideline'))
                    )
    op.create_index(op.f('ix_cpr_guideline_id'), 'cpr_guideline', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_id'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_user_role_id'), table_name='user_role')
    op.drop_table('user_role')
    op.drop_index(op.f('ix_organization_id'), table_name='organization')
    op.drop_table('organization')
    op.drop_index(op.f('ix_cpr_guideline_id'), table_name='cpr_guideline')
    op.drop_table('cpr_guideline')
