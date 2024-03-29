"""create training program table

Revision ID: f41cc180e680
Revises: 07b8df549355
Create Date: 2024-03-12 10:04:43.695225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f41cc180e680'
down_revision: Union[str, None] = '07b8df549355'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('training_program',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=50), nullable=True),
    sa.Column('manikin_type', sa.String(length=50), nullable=True),
    sa.Column('training_type', sa.String(length=50), nullable=True),
    sa.Column('feedback_type', sa.String(length=50), nullable=True),
    sa.Column('training_mode', sa.String(length=50), nullable=True),
    sa.Column('duration', sa.Integer(), nullable=True),
    sa.Column('compression_limit', sa.Integer(), nullable=True),
    sa.Column('cycle_limit', sa.Integer(), nullable=True),
    sa.Column('ventilation_limit', sa.Integer(), nullable=True),
    sa.Column('per_compression', sa.Integer(), nullable=True),
    sa.Column('per_ventilation', sa.Integer(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('cpr_guideline_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['cpr_guideline_id'], ['cpr_guideline.id'], name=op.f('fk_training_program_cpr_guideline_id_cpr_guideline')),
    sa.ForeignKeyConstraint(['organization_id'], ['organization.id'], name=op.f('fk_training_program_organization_id_organization')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_training_program'))
    )
    op.create_index(op.f('ix_training_program_id'), 'training_program', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_training_program_id'), table_name='training_program')
    op.drop_table('training_program')
    # ### end Alembic commands ###
