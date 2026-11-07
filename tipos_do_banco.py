# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Tipos de coluna que se comportam igual no SQLite, MariaDB, MySQL, PostgreSQL, Oracle e SQL Server.

Ficam fora de models.py porque as migrações (migracoes/versions) também os importam.
"""
from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects import mssql, mysql, oracle
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import CreateColumn
from sqlalchemy.types import TypeDecorator


class _VazioComoTexto:
    """O sistema grava "" nos textos não preenchidos (Local, Telefone, Descrição...).

    O Oracle guarda "" como NULL: nele, o "" é gravado como NULL e a coluna não leva NOT NULL
    (veja _coluna_no_oracle). Nos demais bancos, um NULL vindo do código vira "". Na leitura,
    NULL volta como "", em todos. Não filtre essas colunas por == "": no Oracle, a comparação
    com NULL nunca é verdadeira.
    """

    cache_ok = True

    def process_bind_param(self, valor, dialeto):
        if valor is None:
            valor = ""
        if valor == "" and dialeto.name == "oracle":
            return None
        return valor

    def process_result_value(self, valor, dialeto):
        return "" if valor is None else valor


class TextoVazio(_VazioComoTexto, TypeDecorator):
    """String com tamanho, que aceita ""."""

    impl = String


class TextoLongoVazio(_VazioComoTexto, TypeDecorator):
    """Text (sem tamanho), que aceita ""."""

    impl = Text

    def load_dialect_impl(self, dialeto):
        # O TEXT do MySQL e do MariaDB guarda só 64 KB: a descrição formatada pode passar disso.
        if dialeto.name in ("mysql", "mariadb"):
            return dialeto.type_descriptor(mysql.MEDIUMTEXT())
        return dialeto.type_descriptor(Text())


@compiles(CreateColumn, "oracle")
def _coluna_no_oracle(elemento, compilador, **argumentos):
    texto = compilador.visit_create_column(elemento, **argumentos)
    if texto and isinstance(elemento.element.type, _VazioComoTexto):
        texto = texto.replace(" NOT NULL", "")
    return texto


# Data e hora com os microssegundos em todos os bancos: o DATETIME do MySQL e do MariaDB os
# descarta, o do SQL Server arredonda para 3 ms e o DATE do Oracle nem guarda as frações.
DataHora = (
    DateTime()
    .with_variant(mysql.DATETIME(fsp=6), "mysql", "mariadb")
    .with_variant(mssql.DATETIME2(), "mssql")
    .with_variant(oracle.TIMESTAMP(), "oracle")
)
