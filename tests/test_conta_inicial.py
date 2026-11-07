# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from pathlib import Path

import pytest

from app import create_app
from config import Config
from extensions import db
from models import Usuario

EMAIL = "administrador@demandas.aplicativoia.online"


@pytest.fixture
def config_inicial(tmp_path):
    class ConfigInicial(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format((tmp_path / "teste.db").as_posix())
        WTF_CSRF_ENABLED = False
        ANEXOS_DIR = tmp_path / "anexos"
        CONTA_INICIAL_SENHA = "Senha-de-teste-1"
        # Aqui só a senha decide: com o CAPTCHA ligado, toda tentativa seria recusada.
        CAPTCHA_ATIVO = False

    return ConfigInicial


def entrar(aplicacao, senha):
    return aplicacao.test_client().post("/login", data={"email": EMAIL, "password": senha})


@pytest.mark.so_sqlite
def test_primeira_execucao_cria_a_conta_inicial(config_inicial):
    aplicacao = create_app(config_inicial)

    with aplicacao.app_context():
        conta = Usuario.query.filter_by(email=EMAIL).one()

        assert conta.nome == "Administrador do Sistema"
        assert conta.active is True
        assert conta.password != "Senha-de-teste-1"
        assert conta.administrador is True
        db.session.remove()


@pytest.mark.so_sqlite
def test_conta_inicial_entra_com_a_senha_configurada(config_inicial):
    aplicacao = create_app(config_inicial)

    assert entrar(aplicacao, "Senha-de-teste-1").status_code == 302


@pytest.mark.so_sqlite
def test_conta_inicial_nao_entra_com_outra_senha(config_inicial):
    aplicacao = create_app(config_inicial)

    assert entrar(aplicacao, "Senha-errada-1").status_code == 200


@pytest.mark.so_sqlite
def test_reiniciar_nao_duplica_nem_redefine_a_senha(config_inicial):
    aplicacao = create_app(config_inicial)
    with aplicacao.app_context():
        conta = Usuario.query.filter_by(email=EMAIL).one()
        conta.password = senha_alterada = conta.password + "-alterada"
        db.session.commit()
        db.session.remove()

    reiniciada = create_app(config_inicial)

    with reiniciada.app_context():
        assert Usuario.query.filter_by(email=EMAIL).one().password == senha_alterada
        db.session.remove()


@pytest.mark.so_sqlite
def test_conta_inicial_e_criada_em_banco_que_ja_tem_usuarios(config_inicial):
    class SemConta(config_inicial):
        CONTA_INICIAL_EMAIL = None

    aplicacao = create_app(SemConta)
    with aplicacao.app_context():
        from extensions import security

        security.datastore.create_user(email="ana@exemplo.com", password="x")
        db.session.commit()
        db.session.remove()

    reiniciada = create_app(config_inicial)

    with reiniciada.app_context():
        assert Usuario.query.count() == 2
        db.session.remove()


def test_sem_email_configurado_nenhuma_conta_e_criada(app):
    assert Usuario.query.count() == 0


def test_senha_padrao_e_a_informada_no_readme():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "`{}`".format(EMAIL) in readme
    assert "CONTA_INICIAL_SENHA" in Path("INSTALL.md").read_text(encoding="utf-8")
    assert Config.CONTA_INICIAL_EMAIL == EMAIL


def test_sistema_e_documentacao_usam_a_porta_8002():
    assert "port=8002" in Path("app.py").read_text(encoding="utf-8")
    instalacao = Path("INSTALL.md").read_text(encoding="utf-8")

    assert "--bind 127.0.0.1:8002" in instalacao
    assert "proxy_pass http://127.0.0.1:8002;" in instalacao
    assert "<http://localhost:8002>" in instalacao
