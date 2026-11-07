# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""${message}

Revisão: ${up_revision}
Anterior: ${down_revision | comma,n}
Criada em: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
import tipos_do_banco
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
