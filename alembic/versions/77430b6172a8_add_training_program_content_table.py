"""add training program content table

Revision ID: 77430b6172a8
Revises: 027b467c6515
Create Date: 2024-03-12 14:54:34.245344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77430b6172a8'
down_revision: Union[str, None] = '027b467c6515'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('training_program_content',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('s3_key', sa.String(length=100), nullable=True),
    sa.Column('file_name', sa.String(length=100), nullable=True),
    sa.Column('training_program_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['training_program_id'], ['training_program.id'], name=op.f('fk_training_program_content_training_program_id_training_program')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_training_program_content'))
    )
    op.create_index(op.f('ix_training_program_content_id'), 'training_program_content', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_training_program_content_id'), table_name='training_program_content')
    op.drop_table('training_program_content')
    # ### end Alembic commands ###