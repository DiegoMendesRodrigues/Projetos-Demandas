# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Chave da API do YouTube: a tabela de uma linha com a chave cifrada, salva em Configurações.

Revisão: 0003
Anterior: 0002
Criada em: 2026-11-08
"""
from alembic import op
import sqlalchemy as sa
import tipos_do_banco

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # Um SQLite de antes do Alembic com as tabelas criadas pelos modelos atuais (comandos_do_banco,
    # situação "antigo") já tem a tabela.
    if sa.inspect(op.get_bind()).has_table('configuracao_youtube'):
        return
    op.create_table(
        'configuracao_youtube',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('chave', tipos_do_banco.TextoVazio(length=500), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('configuracao_youtube')
