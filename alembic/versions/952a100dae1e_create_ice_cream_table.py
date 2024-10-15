"""create ice cream table

Revision ID: 952a100dae1e
Revises:
Create Date: 2024-10-15 13:17:59.991129

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlmodel import Session, insert

from deep_ice.models import IceCream

# revision identifiers, used by Alembic.
revision: str = "952a100dae1e"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "icecream",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("flavor", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("blocked_quantity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###

    # Insert initial data.
    with Session(bind=op.get_bind()) as session:
        session.exec(
            insert(IceCream).values(
                [
                    {
                        "name": "Vanilla",
                        "flavor": "vanilla",
                        "stock": 100,
                        "price": 3.3,
                    },
                    {
                        "name": "Chocolate",
                        "flavor": "chocolate",
                        "stock": 200,
                        "price": 2.9,
                    },
                    {
                        "name": "Strawberry",
                        "flavor": "strawberry",
                        "stock": 50,
                        "price": 4,
                    },
                ]
            )
        )
        session.commit()


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("icecream")
    # ### end Alembic commands ###
