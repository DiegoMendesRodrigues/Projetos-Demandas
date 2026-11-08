# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Inatividade das contas: o último acesso de cada usuário e o prazo de cada plano.

As contas que já existem começam a contar o prazo agora, e os planos que já existem ficam com
Ilimitado (nenhuma conta excluída até o administrador escolher um prazo).

Revisão: 0002
Anterior: 0001
Criada em: 2026-11-08
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa
import tipos_do_banco

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def colunas(tabela):
    return {coluna['name'] for coluna in sa.inspect(op.get_bind()).get_columns(tabela)}


def upgrade():
    # Só as colunas que faltam: um SQLite de antes do Alembic com as tabelas criadas pelos modelos
    # atuais (comandos_do_banco.preparar_banco, situação "antigo") já pode tê-las.
    faltam = [
        coluna for coluna in (
            sa.Column('ultimo_acesso', tipos_do_banco.DataHora, nullable=True),
            sa.Column('aviso_de_exclusao_em', tipos_do_banco.DataHora, nullable=True),
        )
        if coluna.name not in colunas('usuario')
    ]
    if faltam:
        with op.batch_alter_table('usuario', schema=None) as batch_op:
            for coluna in faltam:
                batch_op.add_column(coluna)
    if 'dias_de_inatividade' not in colunas('plano_de_usuario'):
        with op.batch_alter_table('plano_de_usuario', schema=None) as batch_op:
            batch_op.add_column(sa.Column('dias_de_inatividade', sa.Integer(), nullable=True))

    # Sem isto, quem não entra há mais tempo que o prazo seria excluído na primeira rodada.
    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    usuario = sa.table('usuario', sa.column('ultimo_acesso', tipos_do_banco.DataHora))
    op.execute(usuario.update().values(ultimo_acesso=agora))


def downgrade():
    with op.batch_alter_table('plano_de_usuario', schema=None) as batch_op:
        batch_op.drop_column('dias_de_inatividade')
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_column('aviso_de_exclusao_em')
        batch_op.drop_column('ultimo_acesso')
