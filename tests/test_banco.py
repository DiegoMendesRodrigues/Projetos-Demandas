# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Escolha do banco pelo ambiente, tipos portáveis, migrações (Alembic), cópia e comandos."""
import re
import ssl
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.dialects import mssql, mysql, oracle, postgresql, sqlite
from sqlalchemy.schema import CreateTable

import app as modulo_app
import banco
import comandos_do_banco
from app import create_app
from banco import ErroNaConfiguracaoDoBanco, atualizar_ao_iniciar, ler_configuracao, tipo_da_url
from comandos_do_banco import (
    CopiaRecusada,
    copiar_dados,
    criar_tabelas,
    diferencas_da_estrutura,
    revisao_final,
    situacao_do_banco,
)
from config import Config
from extensions import db
from models import Categoria, GrupoDeUsuarios, PlanoDeUsuario, Projeto, Tarefa, Usuario
from tipos_do_banco import TextoLongoVazio, TextoVazio

RAIZ = Path(__file__).resolve().parent.parent


def ambiente(**valores):
    return {"BANCO_" + chave.upper(): valor for chave, valor in valores.items()}


def servidor(tipo, **extras):
    return ambiente(tipo=tipo, servidor="db.exemplo.com", nome="demandas", usuario="app", senha="s3gr3d0", **extras)


# ---------- Configuração pelo ambiente


def test_sem_variaveis_usa_o_sqlite_do_arquivo_padrao(tmp_path):
    configuracao = ler_configuracao({}, arquivo_padrao=tmp_path / "padrao.db")

    assert configuracao.tipo == "sqlite"
    assert configuracao.url.database == (tmp_path / "padrao.db").as_posix()
    assert configuracao.opcoes_do_motor == {}
    assert not configuracao.em_servidor


def test_banco_arquivo_troca_o_arquivo_do_sqlite(tmp_path):
    configuracao = ler_configuracao(ambiente(arquivo=str(tmp_path / "outro.db")), arquivo_padrao="x.db")

    assert configuracao.url.database.endswith("outro.db")


def test_tipo_desconhecido_e_recusado():
    with pytest.raises(ErroNaConfiguracaoDoBanco, match="BANCO_TIPO"):
        ler_configuracao(ambiente(tipo="access"))


def test_servidor_exige_endereco_nome_e_usuario():
    with pytest.raises(ErroNaConfiguracaoDoBanco, match="BANCO_SERVIDOR"):
        ler_configuracao(ambiente(tipo="postgresql", nome="demandas", usuario="app"))
    with pytest.raises(ErroNaConfiguracaoDoBanco, match="BANCO_USUARIO"):
        ler_configuracao(ambiente(tipo="postgresql", servidor="db", nome="demandas"))


@pytest.mark.parametrize("porta", ["abc", "0", "70000"])
def test_porta_invalida_e_recusada(porta):
    with pytest.raises(ErroNaConfiguracaoDoBanco, match="BANCO_PORTA"):
        ler_configuracao(servidor("mysql", porta=porta))


@pytest.mark.parametrize("tipo, porta", [("mariadb", 3306), ("mysql", 3306), ("postgresql", 5432), ("mssql", 1433)])
def test_porta_padrao_de_cada_banco(tipo, porta):
    assert ler_configuracao(servidor(tipo)).url.port == porta


def test_senha_vem_do_arquivo_sem_a_quebra_de_linha(tmp_path):
    arquivo = tmp_path / "senha"
    arquivo.write_text("senha com espaço \n", encoding="utf-8")
    valores = servidor("postgresql", senha_arquivo=str(arquivo))
    del valores["BANCO_SENHA"]

    assert ler_configuracao(valores).url.password == "senha com espaço "


def test_arquivo_da_senha_inexistente_e_recusado(tmp_path):
    with pytest.raises(ErroNaConfiguracaoDoBanco, match="BANCO_SENHA_ARQUIVO"):
        ler_configuracao(servidor("postgresql", senha_arquivo=str(tmp_path / "nao-existe")))


def test_endereco_sem_senha_esconde_a_senha():
    configuracao = ler_configuracao(servidor("postgresql"))

    assert "s3gr3d0" not in configuracao.endereco_sem_senha
    assert "s3gr3d0" not in str(configuracao.descricao())


def test_dono_usa_o_usuario_e_a_senha_do_dono(tmp_path):
    arquivo = tmp_path / "senha-dono"
    arquivo.write_text("do-dono", encoding="utf-8")
    valores = servidor("postgresql", usuario_dono="dono", senha_dono_arquivo=str(arquivo))

    assert ler_configuracao(valores).url.username == "app"
    dono = ler_configuracao(valores, dono=True)
    assert (dono.url.username, dono.url.password) == ("dono", "do-dono")


def test_servidores_tem_pre_ping_e_reciclagem_das_conexoes():
    opcoes = ler_configuracao(servidor("mariadb")).opcoes_do_motor

    assert opcoes["pool_pre_ping"] is True and opcoes["pool_recycle"] == 3600


@pytest.mark.parametrize("valor, tipo, esperado", [
    ("", "sqlite", True), ("", "postgresql", False), ("1", "oracle", True), ("0", "sqlite", False),
])
def test_atualizar_ao_iniciar(valor, tipo, esperado):
    assert atualizar_ao_iniciar(ambiente(atualizar_ao_iniciar=valor), tipo) is esperado


def test_tipo_da_url():
    assert tipo_da_url("sqlite:///x.db") == "sqlite"
    assert tipo_da_url("mariadb+pymysql://u@h/b") == "mariadb"
    assert tipo_da_url("mssql+pyodbc://@h/b") == "mssql"
    assert tipo_da_url("firebird://u@h/b") == ""


# ---------- TLS


def test_tls_padrao_verifica_fora_da_maquina_e_desliga_na_propria():
    assert ler_configuracao(servidor("postgresql")).tls == "verificar"
    local = servidor("postgresql")
    local["BANCO_SERVIDOR"] = "127.0.0.1"
    assert ler_configuracao(local).tls == "desligado"


def test_tls_invalido_e_autoridade_inexistente_sao_recusados(tmp_path):
    with pytest.raises(ErroNaConfiguracaoDoBanco, match="BANCO_TLS"):
        ler_configuracao(servidor("postgresql", tls="talvez"))
    with pytest.raises(ErroNaConfiguracaoDoBanco, match="BANCO_TLS_CA"):
        ler_configuracao(servidor("postgresql", tls_ca=str(tmp_path / "ca.pem")))


@pytest.mark.parametrize("modo, sslmode", [("verificar", "verify-full"), ("exigir", "require"), ("desligado", "disable")])
def test_postgresql_usa_o_sslmode_do_modo(modo, sslmode):
    argumentos = ler_configuracao(servidor("postgresql", tls=modo)).opcoes_do_motor["connect_args"]

    assert argumentos["sslmode"] == sslmode
    assert argumentos.get("sslrootcert") == ("system" if modo == "verificar" else None)


def test_postgresql_usa_a_autoridade_informada(tmp_path):
    autoridade = tmp_path / "ca.pem"
    autoridade.write_text("", encoding="utf-8")

    argumentos = ler_configuracao(servidor("postgresql", tls_ca=str(autoridade))).opcoes_do_motor["connect_args"]

    assert argumentos["sslrootcert"] == str(autoridade)


@pytest.mark.parametrize("tipo", ["mariadb", "mysql"])
def test_mysql_e_mariadb_usam_utf8mb4_e_conferem_o_certificado(tipo):
    configuracao = ler_configuracao(servidor(tipo))
    contexto = configuracao.opcoes_do_motor["connect_args"]["ssl"]

    assert configuracao.url.query["charset"] == "utf8mb4"
    assert configuracao.url.drivername == tipo + "+pymysql"
    assert contexto.verify_mode == ssl.CERT_REQUIRED and contexto.check_hostname


def test_mysql_exigir_cifra_sem_conferir_e_desligado_sem_ssl():
    contexto = ler_configuracao(servidor("mysql", tls="exigir")).opcoes_do_motor["connect_args"]["ssl"]
    assert contexto.verify_mode == ssl.CERT_NONE and not contexto.check_hostname

    assert "connect_args" not in ler_configuracao(servidor("mysql", tls="desligado")).opcoes_do_motor


def test_oracle_monta_o_dsn_com_tcps_e_confere_o_nome_do_servidor():
    configuracao = ler_configuracao(servidor("oracle"))
    argumentos = configuracao.opcoes_do_motor["connect_args"]

    assert argumentos["dsn"] == "tcps://db.exemplo.com:1521/demandas"
    assert argumentos["ssl_server_dn_match"] is True
    assert isinstance(argumentos["ssl_context"], ssl.SSLContext)
    assert configuracao.url.host is None and configuracao.url.username == "app"


def test_oracle_sem_tls_usa_tcp():
    argumentos = ler_configuracao(servidor("oracle", tls="desligado")).opcoes_do_motor["connect_args"]

    assert argumentos["dsn"] == "tcp://db.exemplo.com:1521/demandas"
    assert "ssl_context" not in argumentos


def test_dsn_do_oracle_e_aceito_pelo_driver():
    oracledb = pytest.importorskip("oracledb")
    parametros = oracledb.ConnectParams()
    parametros.parse_connect_string(ler_configuracao(servidor("oracle")).opcoes_do_motor["connect_args"]["dsn"])

    assert (parametros.host, parametros.port, parametros.service_name, parametros.protocol) == (
        "db.exemplo.com", 1521, "demandas", "tcps",
    )


@pytest.mark.parametrize("modo, cifra, confiar", [("verificar", "yes", "no"), ("exigir", "yes", "yes"), ("desligado", "no", "no")])
def test_sql_server_cifra_conforme_o_modo(modo, cifra, confiar):
    consulta = ler_configuracao(servidor("mssql", tls=modo)).url.query

    assert (consulta["Encrypt"], consulta["TrustServerCertificate"]) == (cifra, confiar)
    assert consulta["driver"] == "ODBC Driver 18 for SQL Server"
    assert consulta["LongAsMax"] == "Yes"
    assert "Trusted_Connection" not in consulta


def test_sql_server_sem_usuario_usa_a_autenticacao_do_windows():
    valores = ambiente(tipo="mssql", servidor=r"(localdb)\MSSQLLocalDB", nome="demandas", driver_odbc="ODBC Driver 17 for SQL Server")
    configuracao = ler_configuracao(valores)

    assert configuracao.url.query["Trusted_Connection"] == "yes"
    assert configuracao.url.port is None and configuracao.tls == "desligado"
    assert configuracao.descricao()["usuario"] == "Autenticação do Windows"


def test_aviso_de_tls_so_para_servidor_de_outra_maquina():
    assert "não é cifrada" in ler_configuracao(servidor("postgresql", tls="desligado")).aviso_de_tls()
    assert "BANCO_TLS=verificar" in ler_configuracao(servidor("postgresql", tls="exigir")).aviso_de_tls()
    assert ler_configuracao(servidor("postgresql")).aviso_de_tls() == ""
    local = servidor("postgresql", tls="desligado")
    local["BANCO_SERVIDOR"] = "localhost"
    assert ler_configuracao(local).aviso_de_tls() == ""
    assert ler_configuracao({}).aviso_de_tls() == ""


# ---------- Tipos portáveis


class DialetoFalso:
    def __init__(self, nome):
        self.name = nome


@pytest.mark.parametrize("tipo", [TextoVazio(10), TextoLongoVazio()])
def test_texto_vazio_vira_nulo_so_no_oracle_e_volta_como_vazio(tipo):
    assert tipo.process_bind_param("", DialetoFalso("oracle")) is None
    assert tipo.process_bind_param(None, DialetoFalso("postgresql")) == ""
    assert tipo.process_bind_param("", DialetoFalso("mssql")) == ""
    assert tipo.process_bind_param("texto", DialetoFalso("oracle")) == "texto"
    assert tipo.process_result_value(None, DialetoFalso("oracle")) == ""


def dialetos():
    o = oracle.dialect()
    o.server_version_info = (19, 0)
    m = mssql.dialect()
    m.server_version_info = (15, 0)
    return {
        "sqlite": sqlite.dialect(), "mysql": mysql.dialect(), "mariadb": mysql.dialect(is_mariadb=True),
        "postgresql": postgresql.dialect(), "oracle": o, "mssql": m,
    }


def ddl(dialeto):
    return {tabela.name: str(CreateTable(tabela).compile(dialect=dialeto)) for tabela in db.metadata.sorted_tables}


@pytest.mark.parametrize("nome", ["sqlite", "mysql", "mariadb", "postgresql", "oracle", "mssql"])
def test_todas_as_tabelas_compilam_em_cada_banco(nome):
    assert len(ddl(dialetos()[nome])) == len(db.metadata.tables)


def test_oracle_aceita_vazio_nas_colunas_de_texto_vazio_e_gera_identidade():
    tarefa = ddl(dialetos()["oracle"])["tarefa"]

    assert re.search(r"\blocal VARCHAR2\(120 CHAR\),", tarefa)
    assert "nome VARCHAR2(120 CHAR) NOT NULL" in tarefa
    assert "GENERATED BY DEFAULT AS IDENTITY" in tarefa
    assert "TIMESTAMP" in tarefa and "CLOB" in tarefa


def test_datas_guardam_os_microssegundos_em_cada_banco():
    banco_a_banco = dialetos()
    assert "DATETIME(6)" in ddl(banco_a_banco["mysql"])["tarefa"]
    assert "DATETIME2" in ddl(banco_a_banco["mssql"])["tarefa"]
    assert "MEDIUMTEXT" in ddl(banco_a_banco["mariadb"])["tarefa"]


def test_configuracao_do_email_nao_tem_identidade():
    """O id 1 é gravado pelo sistema: o SQL Server recusaria um id informado numa IDENTITY."""
    assert "IDENTITY" not in ddl(dialetos()["mssql"])["configuracao_email"]
    assert "IDENTITY" in ddl(dialetos()["mssql"])["usuario"]


def test_nomes_de_indices_cabem_no_oracle_19():
    for tabela in db.metadata.sorted_tables:
        for indice in tabela.indexes:
            assert len(indice.name) <= 128


def test_codigo_nao_usa_select_exists():
    """SELECT EXISTS (...) não existe no SQL Server nem no Oracle."""
    for caminho in RAIZ.glob("*.py"):
        assert "query(consulta.exists())" not in caminho.read_text(encoding="utf-8"), caminho.name
        assert not re.search(r"session\.query\([^)]*\.exists\(\)\)", caminho.read_text(encoding="utf-8")), caminho.name


def test_codigo_nao_compara_booleano_com_is():
    """col.is_(True) vira "IS 1" no SQL Server e no Oracle, que o recusam."""
    for caminho in RAIZ.glob("*.py"):
        codigo = caminho.read_text(encoding="utf-8")
        assert not re.search(r"\.is_\((True|False)\)|\.isnot\((True|False)\)", codigo), caminho.name


# ---------- Consultas que os outros bancos recusam


def capturar_sql(app):
    comandos = []
    event.listen(db.engine, "before_cursor_execute", lambda *a: comandos.append(a[2]))
    return comandos


def test_categorias_compartilhadas_sem_distinct(cliente):
    comandos = capturar_sql(cliente.application)

    cliente.get("/")

    consultas = [sql for sql in comandos if "compartilhamento_de_categoria" in sql]
    assert consultas and not any("DISTINCT" in sql for sql in consultas)


@pytest.mark.parametrize("ordem", ["nome", "usuarios"])
def test_listagem_dos_grupos_sem_group_by_nem_ordem_repetida(cliente, ordem):
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=cliente.usuario_id)
    grupo.membros.append(db.session.get(Usuario, cliente.usuario_id))
    db.session.add(grupo)
    db.session.commit()
    comandos = capturar_sql(cliente.application)

    html = cliente.get("/grupos?ordem={}".format(ordem)).get_data(as_text=True)

    assert "Família" in html
    consulta = next(sql for sql in comandos if "FROM grupo_de_usuarios" in sql and "ORDER BY" in sql)
    assert "GROUP BY" not in consulta
    ordem_sql = consulta.split("ORDER BY")[1]
    assert ordem_sql.count("lower(grupo_de_usuarios.nome)") == 1


# ---------- Migrações


def motor_sqlite(tmp_path, nome="banco.db"):
    return create_engine("sqlite:///{}".format((tmp_path / nome).as_posix()))


def test_ha_uma_unica_revisao_final():
    from alembic.script import ScriptDirectory

    assert len(ScriptDirectory.from_config(comandos_do_banco.configuracao_do_alembic()).get_heads()) == 1


def test_migracoes_do_zero_criam_as_mesmas_tabelas_dos_modelos(tmp_path):
    motor = motor_sqlite(tmp_path)

    comandos_do_banco.atualizar_estrutura(motor)

    assert situacao_do_banco(motor) == "atual"
    assert diferencas_da_estrutura(motor) == []


def test_criar_tabelas_marca_a_ultima_revisao(tmp_path):
    motor = motor_sqlite(tmp_path)
    assert situacao_do_banco(motor) == "vazio"

    criar_tabelas(motor)

    with motor.connect() as conexao:
        assert conexao.execute(text("SELECT version_num FROM alembic_version")).scalar() == revisao_final()


def test_situacao_de_banco_antigo_e_desatualizado(tmp_path):
    motor = motor_sqlite(tmp_path)
    db.metadata.create_all(motor)
    assert situacao_do_banco(motor) == "antigo"

    with motor.begin() as conexao:
        conexao.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conexao.execute(text("INSERT INTO alembic_version VALUES ('revisao-antiga')"))
    original = comandos_do_banco.revisao_final
    comandos_do_banco.revisao_final = lambda: "outra"
    try:
        assert situacao_do_banco(motor) == "desatualizado"
    finally:
        comandos_do_banco.revisao_final = original


def configuracao_de_teste(tmp_path, **extras):
    class ConfigDoBanco(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format((tmp_path / "app.db").as_posix())
        SQLALCHEMY_ENGINE_OPTIONS = {}
        ANEXOS_DIR = tmp_path / "anexos"
        CONTA_INICIAL_EMAIL = None
        CAPTCHA_ATIVO = False
        LIMITES_ATIVOS = False
        BANCO_ATUALIZAR_AO_INICIAR = True

    for chave, valor in extras.items():
        setattr(ConfigDoBanco, chave, valor)
    return ConfigDoBanco


@pytest.mark.so_sqlite
def test_banco_antigo_recebe_as_migracoes_antigas_e_a_revisao(tmp_path):
    motor = motor_sqlite(tmp_path, "app.db")
    db.metadata.create_all(motor)
    with motor.begin() as conexao:
        conexao.execute(text("DROP INDEX ix_tarefa_responsavel_id"))
        conexao.execute(text("ALTER TABLE tarefa DROP COLUMN secoes"))
    motor.dispose()

    aplicacao = create_app(configuracao_de_teste(tmp_path))

    with aplicacao.app_context():
        assert situacao_do_banco(db.engine) == "atual"
        assert diferencas_da_estrutura(db.engine) == []
        assert PlanoDeUsuario.query.filter_by(padrao=True).count() == 1
        db.session.remove()


@pytest.mark.so_sqlite
def test_reiniciar_nao_repete_as_migracoes_antigas(tmp_path, monkeypatch):
    configuracao = configuracao_de_teste(tmp_path)
    with create_app(configuracao).app_context():
        db.session.remove()
    chamadas = []
    monkeypatch.setattr(modulo_app, "atualizar_banco", lambda *a: chamadas.append(a))

    with create_app(configuracao).app_context():
        db.session.remove()

    assert chamadas == []


@pytest.mark.so_sqlite
def test_criar_indices_que_faltam(app):
    with db.engine.begin() as conexao:
        conexao.execute(text("DROP INDEX ix_usuario_plano_id"))

    modulo_app.criar_indices_que_faltam()

    assert "ix_usuario_plano_id" in {indice["name"] for indice in inspect(db.engine).get_indexes("usuario")}


# ---------- Manutenção (banco por atualizar)


@pytest.mark.so_sqlite
def test_banco_nao_atualizado_responde_em_manutencao(tmp_path):
    aplicacao = create_app(configuracao_de_teste(tmp_path, BANCO_ATUALIZAR_AO_INICIAR=False))
    cliente = aplicacao.test_client()

    with aplicacao.app_context():
        assert aplicacao.config["BANCO_PRONTO"] is False
        assert "usuario" not in inspect(db.engine).get_table_names()
        pagina = cliente.get("/")
        api = cliente.get("/api/quadro/versao")
        estatico = cliente.get("/static/css/style.css")
        db.session.remove()

    assert pagina.status_code == 503 and "Sistema em manutenção" in pagina.get_data(as_text=True)
    assert pagina.headers["Retry-After"] == "300"
    assert api.status_code == 503 and api.get_json() == {"erro": "Sistema em manutenção."}
    assert estatico.status_code == 200
    estatico.close()


def test_avisos_nao_rodam_nos_comandos_do_banco(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["/opt/.venv/bin/flask", "--app", "app", "banco", "copiar"])
    assert modulo_app.executando_comando_do_banco()
    monkeypatch.setattr(sys, "argv", [r"C:\x\flask\__main__.py", "--app", "app", "banco", "verificar"])
    assert modulo_app.executando_comando_do_banco()
    monkeypatch.setattr(sys, "argv", ["/opt/.venv/bin/gunicorn", "app:create_app()"])
    assert not modulo_app.executando_comando_do_banco()


# ---------- Cópia entre bancos


def banco_com_dados(tmp_path):
    motor = motor_sqlite(tmp_path, "origem.db")
    criar_tabelas(motor)
    with motor.begin() as conexao:
        conexao.execute(PlanoDeUsuario.__table__.insert(), [{"id": 7, "nome": "Plano", "armazenamento_mb": 5, "padrao": True}])
        conexao.execute(Usuario.__table__.insert(), [{
            "id": 3, "email": "ana@exemplo.com", "password": "x", "active": True, "fs_uniquifier": "u3",
            "tema": "azul", "mostrar_ocultas": False, "avatar": "neutro", "administrador": False,
            "aviso_destinatarios": "ambos", "aviso_antecedencia": 2, "trocar_senha": False, "plano_id": 7,
        }])
        conexao.execute(Categoria.__table__.insert(), [{"id": 4, "nome": "Casa", "icone": "casa", "fundo": "padrao", "usuario_id": 3}])
        conexao.execute(Projeto.__table__.insert(), [{"id": 5, "nome": "Feira", "cor": "#1a6fe0", "posicao": 0, "concluida": False, "usuario_id": 3, "categoria_id": 4}])
        conexao.execute(Tarefa.__table__.insert(), [{
            "id": 9, "nome": "Comprar pão", "prioridade": "baixa", "local": "", "oculta": False, "posicao": 0,
            "tipo": "atividade", "projeto_id": 5,
        }])
    return motor


def test_copiar_leva_todas_as_linhas_com_os_mesmos_ids(tmp_path):
    origem = banco_com_dados(tmp_path)
    destino = motor_sqlite(tmp_path, "destino.db")
    criar_tabelas(destino)

    copiadas = copiar_dados(origem, destino)

    assert copiadas["tarefa"] == 1 and copiadas["usuario"] == 1
    with destino.connect() as conexao:
        assert conexao.execute(text("SELECT id, nome, local FROM tarefa")).one() == (9, "Comprar pão", "")


def test_copiar_substitui_so_os_dados_iniciais_do_destino(tmp_path):
    origem = banco_com_dados(tmp_path)
    destino = motor_sqlite(tmp_path, "destino.db")
    criar_tabelas(destino)
    with destino.begin() as conexao:
        conexao.execute(PlanoDeUsuario.__table__.insert(), [{"id": 1, "nome": "Iniciante", "armazenamento_mb": 10, "padrao": True}])

    copiar_dados(origem, destino)

    with destino.connect() as conexao:
        assert conexao.execute(text("SELECT nome FROM plano_de_usuario")).scalars().all() == ["Plano"]


def test_copiar_recusa_destino_com_dados(tmp_path):
    origem = banco_com_dados(tmp_path)
    (tmp_path / "copia").mkdir()
    destino = banco_com_dados(tmp_path / "copia")

    with pytest.raises(CopiaRecusada, match="já tem dados"):
        copiar_dados(origem, destino)


def test_copiar_recusa_origem_fora_da_ultima_revisao(tmp_path):
    origem = motor_sqlite(tmp_path, "origem.db")
    db.metadata.create_all(origem)
    destino = motor_sqlite(tmp_path, "destino.db")
    criar_tabelas(destino)

    with pytest.raises(CopiaRecusada, match="origem não está na última versão"):
        copiar_dados(origem, destino)


# ---------- Comandos flask banco


def test_comando_verificar(app):
    resultado = app.test_cli_runner().invoke(args=["banco", "verificar"])

    assert resultado.exit_code == 0, resultado.output
    assert "Banco: {}".format(banco.TIPOS_DE_BANCO[tipo_da_url(db.engine.url)]) in resultado.output
    assert "Tabelas: na última versão ({})".format(revisao_final()) in resultado.output


def test_comando_atualizar_num_banco_ja_atual(app):
    resultado = app.test_cli_runner().invoke(args=["banco", "atualizar"])

    assert resultado.exit_code == 0, resultado.output
    assert "Tabelas na última versão" in resultado.output


@pytest.mark.so_sqlite
def test_comando_copiar_de_um_sqlite(app, tmp_path):
    origem = banco_com_dados(tmp_path)
    origem.dispose()
    with db.engine.begin() as conexao:
        for tabela in reversed(db.metadata.sorted_tables):
            conexao.execute(tabela.delete())

    resultado = app.test_cli_runner().invoke(
        args=["banco", "copiar", "--de", "sqlite:///{}".format((tmp_path / "origem.db").as_posix())]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Cópia concluída: 5 linhas." in resultado.output
    assert db.session.get(Tarefa, 9).nome == "Comprar pão"


def test_comando_copiar_recusa_endereco_desconhecido(app):
    resultado = app.test_cli_runner().invoke(args=["banco", "copiar", "--de", "firebird://x@y/z"])

    assert resultado.exit_code != 0 and "não reconhecido" in resultado.output


# ---------- Configurações


def test_configuracoes_mostram_o_banco_em_uso(cliente):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()

    html = cliente.get("/administracao/configuracoes").get_data(as_text=True)

    secao = html.split('<h2 class="subtitulo" id="banco-titulo">Banco de dados</h2>')[1]
    assert "<dt>Banco</dt>" in secao and "variáveis BANCO_*" in secao


def test_configuracoes_avisam_conexao_sem_cifra(cliente, monkeypatch):
    import routes

    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()
    remoto = ler_configuracao(servidor("postgresql", tls="desligado"))
    monkeypatch.setitem(cliente.application.config, "BANCO", remoto)
    monkeypatch.setattr(routes, "tipo_da_url", lambda url: "postgresql")

    html = cliente.get("/administracao/configuracoes").get_data(as_text=True)

    assert "data-aviso-do-banco" in html and "não é cifrada" in html
    assert "db.exemplo.com" in html and "PostgreSQL" in html and "s3gr3d0" not in html


# ---------- Oracle: esquema do dono


def test_oracle_usa_o_esquema_do_dono_para_o_usuario_da_aplicacao():
    valores = servidor("oracle", usuario_dono="pd_dono")

    assert ler_configuracao(valores).esquema == "pd_dono"
    assert ler_configuracao(valores, dono=True).esquema == ""
    assert ler_configuracao(servidor("oracle")).esquema == ""
    assert ler_configuracao(servidor("postgresql", usuario_dono="pd_dono")).esquema == ""


def test_esquema_invalido_do_oracle_e_recusado():
    with pytest.raises(ErroNaConfiguracaoDoBanco, match="BANCO_ESQUEMA"):
        ler_configuracao(servidor("oracle", esquema="dono; DROP TABLE usuario"))


def test_preparar_motor_troca_o_esquema_a_cada_conexao_so_no_oracle():
    from banco import preparar_motor

    pytest.importorskip("oracledb")
    configuracao = ler_configuracao(servidor("oracle", usuario_dono="pd_dono"))
    motor = create_engine(configuracao.url, **configuracao.opcoes_do_motor)
    antes = len(motor.pool.dispatch.connect)

    preparar_motor(motor, configuracao)

    assert len(motor.pool.dispatch.connect) == antes + 1
    sqlite_motor = create_engine("sqlite://")
    antes = len(sqlite_motor.pool.dispatch.connect)
    preparar_motor(sqlite_motor, configuracao)
    assert len(sqlite_motor.pool.dispatch.connect) == antes


def test_conceder_acesso_so_age_no_oracle_e_recusa_nome_invalido(tmp_path):
    from comandos_do_banco import conceder_acesso

    motor = motor_sqlite(tmp_path)
    conceder_acesso(motor, "pd_app")
    assert inspect(motor).get_table_names() == []

    class MotorOracle:
        class dialect:
            name = "oracle"

    with pytest.raises(ErroNaConfiguracaoDoBanco):
        conceder_acesso(MotorOracle, "pd_app; DROP")


def test_migracao_0002_comeca_a_contar_a_inatividade_agora_e_deixa_os_planos_ilimitados(tmp_path):
    from datetime import datetime, timedelta

    from alembic import command

    motor = motor_sqlite(tmp_path)
    comandos_do_banco._executar_alembic(motor, command.upgrade, "0001")
    with motor.begin() as conexao:
        conexao.execute(text("INSERT INTO plano_de_usuario (id, nome, armazenamento_mb, padrao) VALUES (1, 'Iniciante', 10, 1)"))
        conexao.execute(text(
            "INSERT INTO usuario (id, nome, email, password, active, fs_uniquifier, tema, mostrar_ocultas, avatar,"
            " foto, administrador, telefone, aviso_destinatarios, aviso_antecedencia, trocar_senha, plano_id)"
            " VALUES (1, 'Ana', 'ana@exemplo.com', 'x', 1, 'u1', 'azul', 0, 'a', '', 0, '', 'ambos', 2, 0, 1)"
        ))

    from config import FUSO_HORARIO

    antes = datetime.now(FUSO_HORARIO).replace(tzinfo=None) - timedelta(seconds=1)
    comandos_do_banco.atualizar_estrutura(motor)

    with motor.connect() as conexao:
        acesso, aviso = conexao.execute(text("SELECT ultimo_acesso, aviso_de_exclusao_em FROM usuario")).one()
        dias = conexao.execute(text("SELECT dias_de_inatividade FROM plano_de_usuario")).scalar()
    assert datetime.fromisoformat(str(acesso)) >= antes
    assert aviso is None
    assert dias is None
