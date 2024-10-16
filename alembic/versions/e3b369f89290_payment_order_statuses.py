"""payment & order statuses

Revision ID: e3b369f89290
Revises: 1079259bdec5
Create Date: 2024-10-16 17:43:06.286971

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e3b369f89290"
down_revision: Union[str, None] = "1079259bdec5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    order_status_enum = postgresql.ENUM(
        "PENDING", "CONFIRMED", "CANCELLED", name="orderstatus"
    )
    order_status_enum.create(op.get_bind())
    payment_method_enum = postgresql.ENUM("CASH", "CARD", name="paymentmethod")
    payment_method_enum.create(op.get_bind())
    payment_status_enum = postgresql.ENUM(
        "PENDING", "SUCCESS", "FAILED", name="paymentstatus"
    )
    payment_status_enum.create(op.get_bind())

    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "orders",
        "status",
        existing_type=sa.VARCHAR(),
        type_=sa.Enum("PENDING", "CONFIRMED", "CANCELLED", name="orderstatus"),
        nullable=True,
        postgresql_using="status::text::orderstatus",
    )
    op.add_column(
        "payments",
        sa.Column(
            "method", sa.Enum("CASH", "CARD", name="paymentmethod"), nullable=True
        ),
    )
    op.alter_column(
        "payments",
        "status",
        existing_type=sa.VARCHAR(),
        type_=sa.Enum("PENDING", "SUCCESS", "FAILED", name="paymentstatus"),
        nullable=True,
        postgresql_using="status::text::paymentstatus",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column(
        "payments",
        "status",
        existing_type=sa.Enum("PENDING", "SUCCESS", "FAILED", name="paymentstatus"),
        type_=sa.VARCHAR(),
        nullable=False,
    )
    op.drop_column("payments", "method")
    op.alter_column(
        "orders",
        "status",
        existing_type=sa.Enum("PENDING", "CONFIRMED", "CANCELLED", name="orderstatus"),
        type_=sa.VARCHAR(),
        nullable=False,
    )
    # ### end Alembic commands ###

    order_status_enum = postgresql.ENUM(
        "PENDING", "CONFIRMED", "CANCELLED", name="orderstatus"
    )
    order_status_enum.drop(op.get_bind())
    payment_method_enum = postgresql.ENUM("CASH", "CARD", name="paymentmethod")
    payment_method_enum.drop(op.get_bind())
    payment_status_enum = postgresql.ENUM(
        "PENDING", "SUCCESS", "FAILED", name="paymentstatus"
    )
    payment_status_enum.drop(op.get_bind())
