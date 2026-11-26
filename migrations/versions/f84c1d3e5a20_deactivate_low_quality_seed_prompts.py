"""Deactivate low-quality / off-topic seed image prompts without breaking existing recordings.

Revision ID: f84c1d3e5a20
Revises: e73b9c2d4f10
Create Date: 2026-11-26 17:27:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f84c1d3e5a20"
down_revision: Union[str, None] = "e73b9c2d4f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEACTIVATE_TITLES = (
    "Scène de marché #1",
    "Scène de marché #3",
    "Scène de marché #5",
    "Cuisine et repas #1",
    "Cuisine et repas #2",
    "Cuisine et repas #3",
    "Cuisine et repas #6",
    "Transports et déplacements #1",
    "Transports et déplacements #5",
    "Transports et déplacements #6",
    "Agriculture et pêche #2",
    "Agriculture et pêche #4",
    "Agriculture et pêche #5",
    "Agriculture et pêche #6",
    "Vie quotidienne #3",
    "Santé et hygiène #1",
    "Santé et hygiène #2",
    "Santé et hygiène #5",
    "Nature et paysages #4",
    "Nature et paysages #6",
    "Sport et loisirs #1",
    "Sport et loisirs #4",
    "Culture et musique #1",
    "Culture et musique #3",
    "Culture et musique #4",
    "Culture et musique #5",
    "Culture et musique #6",
    "Ville et village #2",
    "Ville et village #3",
)


def upgrade() -> None:
    bind = op.get_bind()
    stmt = sa.text(
        "UPDATE prompts SET active = FALSE "
        "WHERE prompt_type = 'image' AND title = ANY(:titles)"
    )
    bind.execute(stmt, {"titles": list(DEACTIVATE_TITLES)})


def downgrade() -> None:
    bind = op.get_bind()
    stmt = sa.text(
        "UPDATE prompts SET active = TRUE "
        "WHERE prompt_type = 'image' AND title = ANY(:titles)"
    )
    bind.execute(stmt, {"titles": list(DEACTIVATE_TITLES)})
