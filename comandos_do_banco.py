# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Criação e atualização das tabelas (Alembic) e os comandos flask banco.

Situações do banco ao iniciar:
- vazio: as tabelas são criadas pelos modelos e o banco é marcado com a última revisão;
- antigo: um SQLite de antes do Alembic. Recebe as migrações antigas (atualizar_banco, em app.py)
  e é marcado com a revisão inicial, para depois receber as seguintes;
- desatualizado: tem uma revisão anterior à última e recebe as que faltam;
- atual: nada a fazer.

No SQLite isso acontece ao iniciar. Nos servidores, o usuário da aplicação não pode alterar as
tabelas: elas são criadas e atualizadas por flask banco atualizar, com o usuário dono
(BANCO_USUARIO_DONO). Até lá, o sistema responde 503 (pagina_de_manutencao).
"""
from pathlib import Path

import click
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config as ConfigDoAlembic
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask import current_app
from flask.cli import AppGroup
from sqlalchemy import create_engine, func, inspect, select, text

from banco import ESQUEMA_VALIDO, TIPOS_DE_BANCO, ErroNaConfiguracaoDoBanco, ler_configuracao, tipo_da_url
from extensions import db

PASTA_DAS_MIGRACOES = Path(__file__).resolve().parent / "migracoes"
REVISAO_INICIAL = "0001"
TABELA_DAS_REVISOES = "alembic_version"
# O que o próprio sistema grava ao iniciar num banco novo: copiar pode apagá-lo do destino.
TABELAS_DOS_DADOS_INICIAIS = {"plano_de_usuario", "usuario", "desafio_captcha"}
TAMANHO_DO_LOTE = 500
TABELA_DE_TESTE_DE_PERMISSAO = "teste_de_permissao_pd"

banco = AppGroup("banco", help="Verifica, cria, atualiza e copia o banco de dados.")


def configuracao_do_alembic(conexao=None):
    configuracao = ConfigDoAlembic()
    configuracao.set_main_option("script_location", PASTA_DAS_MIGRACOES.as_posix())
    configuracao.attributes["connection"] = conexao
    return configuracao


def revisao_final():
    return ScriptDirectory.from_config(configuracao_do_alembic()).get_current_head()


def revisao_do_banco(conexao):
    return MigrationContext.configure(conexao).get_current_revision()


def situacao_do_banco(motor):
    with motor.connect() as conexao:
        tabelas = set(inspect(conexao).get_table_names())
        if TABELA_DAS_REVISOES in tabelas:
            revisao = revisao_do_banco(conexao)
            if revisao == revisao_final():
                return "atual"
            return "desatualizado" if revisao else "vazio"
    if tabelas & set(db.metadata.tables):
        return "antigo"
    return "vazio"


def _executar_alembic(motor, funcao, *argumentos):
    with motor.begin() as conexao:
        funcao(configuracao_do_alembic(conexao), *argumentos)


def criar_tabelas(motor):
    db.metadata.create_all(motor)
    _executar_alembic(motor, command.stamp, "head")


def atualizar_estrutura(motor):
    _executar_alembic(motor, command.upgrade, "head")


def marcar_como_inicial(motor):
    _executar_alembic(motor, command.stamp, REVISAO_INICIAL)


def preparar_banco(motor, atualizar):
    """A primeira etapa, antes do Flask-Security: devolve a situação depois do que foi feito.

    O banco antigo só tem as tabelas que faltam criadas aqui: as migrações antigas precisam do
    Flask-Security (concluir_banco_antigo).
    """
    situacao = situacao_do_banco(motor)
    if situacao == "atual" or not atualizar:
        return situacao
    if situacao == "vazio":
        conferir_codificacao(motor)
        criar_tabelas(motor)
        return "atual"
    if situacao == "desatualizado":
        atualizar_estrutura(motor)
        return "atual"
    db.metadata.create_all(motor)
    return "antigo"


def concluir_banco_antigo(motor, migracoes_antigas):
    migracoes_antigas()
    db.session.remove()
    marcar_como_inicial(motor)
    atualizar_estrutura(motor)


def diferencas_da_estrutura(motor):
    """O que falta no banco para ficar igual aos modelos (vazio quando está tudo certo)."""
    with motor.connect() as conexao:
        sqlite = conexao.dialect.name == "sqlite"
        # O SQLite não tem tipos de verdade (um VARCHAR(11) guarda qualquer tamanho): só a
        # falta de tabelas, colunas e índices conta.
        contexto = MigrationContext.configure(conexao, opts={"compare_type": not sqlite})
        return compare_metadata(contexto, db.metadata)


# ---------- Conferências do servidor


CONSULTAS_DA_CODIFICACAO = {
    "postgresql": ("SHOW server_encoding", ("UTF8",)),
    "mysql": ("SELECT @@character_set_database", ("utf8mb4",)),
    "mariadb": ("SELECT @@character_set_database", ("utf8mb4",)),
    "oracle": ("SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET'", ("AL32UTF8",)),
    "mssql": ("SELECT CONVERT(varchar(256), DATABASEPROPERTYEX(DB_NAME(), 'Collation'))", None),
}
CONSULTAS_DO_TLS = {
    "postgresql": "SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()",
    "mysql": "SHOW SESSION STATUS LIKE 'Ssl_cipher'",
    "mariadb": "SHOW SESSION STATUS LIKE 'Ssl_cipher'",
    "oracle": "SELECT sys_context('USERENV', 'NETWORK_PROTOCOL') FROM dual",
    "mssql": "SELECT encrypt_option FROM sys.dm_exec_connections WHERE session_id = @@SPID",
}


class CodificacaoInvalida(RuntimeError):
    """O banco não guarda o texto em UTF-8: os acentos e os emojis seriam perdidos."""


def codificacao_do_banco(conexao):
    """(codificação, se serve)."""
    consulta = CONSULTAS_DA_CODIFICACAO.get(conexao.dialect.name)
    if not consulta:
        return "UTF-8", True
    sql, aceitas = consulta
    valor = str(conexao.execute(text(sql)).scalar() or "")
    if aceitas is None:
        # SQL Server: só as ordenações _UTF8 (2019 ou mais novo) guardam UTF-8 no VARCHAR.
        return valor, "UTF8" in valor.upper()
    return valor, valor in aceitas


def conferir_codificacao(motor):
    with motor.connect() as conexao:
        valor, serve = codificacao_do_banco(conexao)
    if not serve:
        raise CodificacaoInvalida(
            "O banco de dados usa {} e precisa de UTF-8 (veja o INSTALL.md).".format(valor or "outra codificação")
        )


def conexao_cifrada(conexao):
    """True ou False, ou None quando o servidor não informa."""
    sql = CONSULTAS_DO_TLS.get(conexao.dialect.name)
    if not sql:
        return None
    try:
        linha = conexao.execute(text(sql)).first()
    except Exception:  # noqa: BLE001 - sem permissão para a consulta: não se sabe
        conexao.rollback()
        return None
    if linha is None:
        return False
    valor = linha[-1]
    if isinstance(valor, str):
        return valor.strip().upper() in ("TRUE", "TCPS") or (
            conexao.dialect.name in ("mysql", "mariadb") and bool(valor.strip())
        )
    return bool(valor)


def pode_alterar_tabelas(conexao):
    """Se o usuário conectado consegue criar uma tabela (o da aplicação não deveria)."""
    try:
        conexao.execute(text("CREATE TABLE {} (id INTEGER)".format(TABELA_DE_TESTE_DE_PERMISSAO)))
    except Exception:  # noqa: BLE001 - recusado pelo servidor: é o esperado
        conexao.rollback()
        return False
    conexao.execute(text("DROP TABLE {}".format(TABELA_DE_TESTE_DE_PERMISSAO)))
    conexao.commit()
    return True


def conceder_acesso(motor, usuario):
    """Oracle: o usuário da aplicação lê e grava as tabelas do dono, sem poder alterá-las.

    O Oracle não tem privilégios padrão para as tabelas futuras (como o ALTER DEFAULT
    PRIVILEGES do PostgreSQL): o acesso é dado tabela a tabela, a cada atualização.
    """
    if motor.dialect.name != "oracle" or not usuario:
        return
    if not ESQUEMA_VALIDO.fullmatch(usuario):
        raise ErroNaConfiguracaoDoBanco("BANCO_USUARIO não é um nome válido do Oracle.")
    with motor.begin() as conexao:
        preparador = conexao.dialect.identifier_preparer
        for tabela in db.metadata.sorted_tables:
            conexao.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON {} TO {}".format(
                preparador.format_table(tabela), usuario.upper()
            )))
        conexao.execute(text("GRANT SELECT ON {} TO {}".format(TABELA_DAS_REVISOES, usuario.upper())))


def motor_do_dono():
    """O motor com o usuário dono das tabelas, ou o da aplicação, sem um dono configurado."""
    configuracao = ler_configuracao(arquivo_padrao=current_app.config["BANCO_ARQUIVO_PADRAO"], dono=True)
    if not configuracao.em_servidor or configuracao.usuario == current_app.config["BANCO"].usuario:
        return db.engine
    return create_engine(configuracao.url, **configuracao.opcoes_do_motor)


# ---------- Cópia entre bancos


class CopiaRecusada(RuntimeError):
    pass


def linhas_por_tabela(conexao):
    tabelas = set(inspect(conexao).get_table_names())
    return {
        tabela.name: conexao.execute(select(func.count()).select_from(tabela)).scalar()
        for tabela in db.metadata.sorted_tables
        if tabela.name in tabelas
    }


def so_dados_iniciais(contagem):
    preenchidas = {nome for nome, linhas in contagem.items() if linhas}
    return preenchidas <= TABELAS_DOS_DADOS_INICIAIS and contagem.get("usuario", 0) <= 1


def coluna_com_identidade(tabela):
    coluna = tabela.autoincrement_column
    return coluna if coluna is not None and coluna.identity is not None else None


def _antes_de_inserir(conexao, tabela):
    if conexao.dialect.name == "mssql" and coluna_com_identidade(tabela) is not None:
        conexao.execute(text("SET IDENTITY_INSERT {} ON".format(conexao.dialect.identifier_preparer.format_table(tabela))))


def _depois_de_inserir(conexao, tabela):
    coluna = coluna_com_identidade(tabela)
    if coluna is None:
        return
    preparador = conexao.dialect.identifier_preparer
    nome_da_tabela = preparador.format_table(tabela)
    nome_da_coluna = preparador.format_column(coluna)
    dialeto = conexao.dialect.name
    if dialeto == "mssql":
        conexao.execute(text("SET IDENTITY_INSERT {} OFF".format(nome_da_tabela)))
    elif dialeto == "postgresql":
        conexao.execute(text(
            "SELECT setval(pg_get_serial_sequence(:tabela, :coluna), COALESCE(MAX({c}), 0) + 1, false) "
            "FROM {t}".format(c=nome_da_coluna, t=nome_da_tabela)
        ), {"tabela": tabela.name, "coluna": coluna.name})
    elif dialeto == "oracle":
        conexao.execute(text(
            "ALTER TABLE {} MODIFY {} GENERATED BY DEFAULT AS IDENTITY (START WITH LIMIT VALUE)".format(
                nome_da_tabela, nome_da_coluna
            )
        ))


def copiar_dados(origem, destino, avisar=lambda texto: None):
    """Copia todas as linhas de origem para destino, que precisa estar vazio (ou só com os
    dados iniciais). Os dois precisam estar na última revisão. Devolve a contagem copiada."""
    final = revisao_final()
    with origem.connect() as conexao:
        if revisao_do_banco(conexao) != final:
            raise CopiaRecusada(
                "O banco de origem não está na última versão: inicie o sistema uma vez com ele "
                "ou rode flask banco atualizar nele."
            )
        contagem_da_origem = linhas_por_tabela(conexao)
    with destino.connect() as conexao:
        if revisao_do_banco(conexao) != final:
            raise CopiaRecusada("O banco de destino não está na última versão: rode flask banco atualizar.")
        contagem_do_destino = linhas_por_tabela(conexao)
    if not so_dados_iniciais(contagem_do_destino):
        raise CopiaRecusada("O banco de destino já tem dados: a cópia só é feita para um banco novo.")

    tabelas = db.metadata.sorted_tables
    with origem.connect() as leitura, destino.begin() as escrita:
        for tabela in reversed(tabelas):
            escrita.execute(tabela.delete())
        for tabela in tabelas:
            _antes_de_inserir(escrita, tabela)
            resultado = leitura.execute(select(tabela)).mappings()
            while lote := resultado.fetchmany(TAMANHO_DO_LOTE):
                escrita.execute(tabela.insert(), [dict(linha) for linha in lote])
            _depois_de_inserir(escrita, tabela)
            avisar("{}: {} linhas".format(tabela.name, contagem_da_origem.get(tabela.name, 0)))
    with destino.connect() as conexao:
        copiadas = linhas_por_tabela(conexao)
    if copiadas != contagem_da_origem:
        raise CopiaRecusada("A contagem das linhas copiadas não confere com a origem.")
    return copiadas


# ---------- Comandos


def _falhar(mensagem):
    raise click.ClickException(mensagem)


@banco.command("verificar")
def comando_verificar():
    """Mostra o banco em uso e confere a conexão, a codificação, a cifra e a versão das tabelas."""
    configuracao = current_app.config["BANCO"]
    tipo = tipo_da_url(db.engine.url)
    click.echo("Banco: {}".format(TIPOS_DE_BANCO.get(tipo, db.engine.url.get_backend_name())))
    click.echo("Endereço: {}".format(db.engine.url.render_as_string(hide_password=True)))
    with db.engine.connect() as conexao:
        versao = ".".join(str(parte) for parte in (conexao.dialect.server_version_info or ()))
        click.echo("Versão do servidor: {}".format(versao or "não informada"))
        valor, serve = codificacao_do_banco(conexao)
        click.echo("Codificação: {} ({})".format(valor, "ok" if serve else "PRECISA SER UTF-8"))
        if tipo != "sqlite":
            cifrada = conexao_cifrada(conexao)
            texto = {True: "cifrada", False: "SEM CIFRA", None: "o servidor não informou"}[cifrada]
            click.echo("Conexão: {}".format(texto))
            if pode_alterar_tabelas(conexao):
                click.echo(
                    "Aviso: o usuário da aplicação pode criar e apagar tabelas. Deixe isso só "
                    "com o usuário dono (BANCO_USUARIO_DONO)."
                )
    aviso = configuracao.aviso_de_tls()
    if aviso:
        click.echo("Aviso: {}".format(aviso))
    situacao = situacao_do_banco(db.engine)
    textos = {
        "atual": "na última versão ({})".format(revisao_final()),
        "desatualizado": "desatualizadas: rode flask banco atualizar",
        "antigo": "de antes das migrações: inicie o sistema uma vez para atualizá-las",
        "vazio": "não criadas: rode flask banco atualizar",
    }
    click.echo("Tabelas: {}".format(textos[situacao]))
    if situacao == "atual":
        diferencas = diferencas_da_estrutura(db.engine)
        if diferencas:
            click.echo("Aviso: {} diferenças entre as tabelas e os modelos.".format(len(diferencas)))


@banco.command("atualizar")
def comando_atualizar():
    """Cria as tabelas num banco novo ou aplica as migrações que faltam (com o usuário dono)."""
    try:
        motor = motor_do_dono()
    except ErroNaConfiguracaoDoBanco as erro:
        _falhar(str(erro))
    situacao = situacao_do_banco(motor)
    if situacao == "antigo":
        _falhar("Banco de antes das migrações: inicie o sistema uma vez com ele (só acontece no SQLite).")
    try:
        preparar_banco(motor, atualizar=True)
        if motor is not db.engine:
            conceder_acesso(motor, current_app.config["BANCO"].usuario)
    except CodificacaoInvalida as erro:
        _falhar(str(erro))
    finally:
        if motor is not db.engine:
            motor.dispose()
    click.echo("Tabelas na última versão ({}).".format(revisao_final()))
    if situacao == "vazio":
        click.echo("Reinicie o sistema para ele criar o plano padrão e a conta inicial.")


@banco.command("copiar")
@click.option("--de", "origem", required=True, help="Endereço SQLAlchemy do banco de origem, como sqlite:///database/projetos_demandas.db")
def comando_copiar(origem):
    """Copia todos os dados de outro banco (por exemplo, o SQLite) para o banco configurado."""
    if not tipo_da_url(origem):
        _falhar("Endereço de origem não reconhecido.")
    motor_de_origem = create_engine(origem)
    try:
        motor = motor_do_dono()
        if situacao_do_banco(motor) == "vazio":
            preparar_banco(motor, atualizar=True)
        copiadas = copiar_dados(motor_de_origem, motor, avisar=click.echo)
    except (CopiaRecusada, CodificacaoInvalida, ErroNaConfiguracaoDoBanco) as erro:
        _falhar(str(erro))
    finally:
        motor_de_origem.dispose()
    click.echo("Cópia concluída: {} linhas.".format(sum(copiadas.values())))
    click.echo("Copie também a pasta userfiles/, com os anexos, as imagens e as fotos.")


@banco.command("revisao")
@click.option("-m", "--mensagem", required=True, help="O que a revisão altera.")
def comando_revisao(mensagem):
    """(Desenvolvimento) Cria uma revisão com as alterações dos modelos, a partir do banco atual."""
    with db.engine.begin() as conexao:
        command.revision(configuracao_do_alembic(conexao), message=mensagem, autogenerate=True)
