# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Ambiente do Alembic: a conexão vem pronta de comandos_do_banco.py, nunca de um alembic.ini."""
from alembic import context

import models  # noqa: F401 (registra as tabelas em db.metadata)
from extensions import db

conexao = context.config.attributes["connection"]
context.configure(
    connection=conexao,
    target_metadata=db.metadata,
    compare_type=True,
    # O SQLite não altera colunas: o Alembic recria a tabela (modo "batch").
    render_as_batch=conexao.dialect.name == "sqlite",
    user_module_prefix="tipos_do_banco.",
)
with context.begin_transaction():
    context.run_migrations()
