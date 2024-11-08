"""preregistered users

Revision ID: ff861c79333d
Revises: 952a100dae1e
Create Date: 2024-10-15 16:34:16.459332

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlmodel import Session, insert

from alembic import op
from deep_ice.core.security import get_password_hash
from deep_ice.models import User

# revision identifiers, used by Alembic.
revision: str = "ff861c79333d"
down_revision: Union[str, None] = "952a100dae1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "hashed_password", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    # ### end Alembic commands ###

    # Insert initial data.
    with Session(bind=op.get_bind()) as session:
        session.exec(  # type: ignore
            insert(User).values(
                [
                    {
                        "name": "Cosmin Poieana",
                        "email": "cmin764@gmail.com",
                        "hashed_password": get_password_hash("cosmin-password"),
                    },
                    {
                        "name": "John Doe",
                        "email": "john.doe@deepicecream.ai",
                        "hashed_password": get_password_hash("john-password"),
                    },
                    {
                        "name": "Sam Smith",
                        "email": "sam.smith@deepicecream.ai",
                        "hashed_password": get_password_hash("sam-password"),
                    },
                ]
            )
        )
        session.commit()


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    # ### end Alembic commands ###
