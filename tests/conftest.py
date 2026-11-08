# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import os

import pytest
from flask import g
from flask.testing import FlaskClient
from flask_security import hash_password

from app import create_app
from banco import tipo_da_url
from config import Config
from extensions import db, security
from models import Categoria, Projeto, Tarefa
import seguranca
import youtube

SENHA = "senha-de-teste-123"
# Com um endereço SQLAlchemy aqui, os testes rodam nesse banco, que é apagado a cada teste:
# use um banco só para isso. Sem ele, cada teste usa um SQLite novo.
URL_DO_BANCO_DE_TESTE = os.environ.get("URL_DO_BANCO_DE_TESTE", "")


def esvaziar_banco(url):
    """Apaga as tabelas do banco de teste externo, para o teste começar de um banco vazio."""
    from sqlalchemy import create_engine, inspect, text

    motor = create_engine(url)
    with motor.begin() as conexao:
        if "alembic_version" in inspect(conexao).get_table_names():
            conexao.execute(text("DROP TABLE alembic_version"))
    db.metadata.drop_all(motor)
    motor.dispose()


class ClienteDeTeste(FlaskClient):
    """Impede que o usuário fique guardado no `g` do contexto compartilhado pelo teste."""

    def open(self, *args, **kwargs):
        g.pop("_login_user", None)
        return super().open(*args, **kwargs)


@pytest.fixture(autouse=True)
def oembed_do_youtube_sem_internet(monkeypatch):
    """Os testes nunca acessam o oEmbed nem a API do YouTube: por padrão, os dois falham.
    tests/test_videos.py e tests/test_chave_do_youtube.py os trocam quando precisam."""
    def recusar(_codigo):
        raise youtube.ErroNasInformacoes("oEmbed desligado nos testes")

    def sem_api(_codigo, _chave):
        raise youtube.ErroDeConexao("API desligada nos testes")

    monkeypatch.setattr(youtube, "baixar_oembed", recusar)
    monkeypatch.setattr(youtube, "baixar_da_api", sem_api)


@pytest.fixture(autouse=True)
def envio_sem_thread(monkeypatch):
    """O e-mail do Esqueci minha senha sai numa thread: nos testes, sai na hora."""
    monkeypatch.setattr(seguranca, "em_segundo_plano", lambda funcao: funcao())


@pytest.fixture
def app(tmp_path):
    class ConfigDeTeste(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = URL_DO_BANCO_DE_TESTE or "sqlite:///{}".format(
            (tmp_path / "teste.db").as_posix()
        )
        SQLALCHEMY_ENGINE_OPTIONS = {}
        BANCO_ATUALIZAR_AO_INICIAR = True
        WTF_CSRF_ENABLED = False
        ANEXOS_DIR = tmp_path / "anexos"
        CONTA_INICIAL_EMAIL = None
        # Os testes do CAPTCHA o ligam em tests/test_captcha.py; os demais entram sem ele.
        CAPTCHA_ATIVO = False
        # Os testes fazem muitas requisições seguidas; tests/test_seguranca.py religa o limite.
        LIMITES_ATIVOS = False

    if URL_DO_BANCO_DE_TESTE:
        esvaziar_banco(URL_DO_BANCO_DE_TESTE)
    aplicacao = create_app(ConfigDeTeste)
    aplicacao.test_client_class = ClienteDeTeste
    with aplicacao.app_context():
        yield aplicacao
        db.session.remove()


@pytest.fixture
def criar_cliente(app):
    def _criar_cliente(email):
        usuario = security.datastore.create_user(
            email=email, password=hash_password(SENHA)
        )
        db.session.commit()
        cliente = app.test_client()
        resposta = cliente.post("/login", data={"email": email, "password": SENHA})
        assert resposta.status_code == 302
        cliente.usuario_id = usuario.id
        return cliente

    return _criar_cliente


@pytest.fixture
def cliente(criar_cliente):
    return criar_cliente("ana@exemplo.com")


@pytest.fixture
def outro_cliente(criar_cliente):
    return criar_cliente("bruno@exemplo.com")


@pytest.fixture
def criar_categoria():
    def _criar_categoria(usuario_id, nome="Casa"):
        categoria = Categoria(nome=nome, usuario_id=usuario_id)
        db.session.add(categoria)
        db.session.commit()
        return categoria

    return _criar_categoria


@pytest.fixture
def criar_projeto():
    def _criar_projeto(usuario_id, nome="A fazer", posicao=0):
        projeto = Projeto(nome=nome, usuario_id=usuario_id, posicao=posicao)
        db.session.add(projeto)
        db.session.commit()
        return projeto

    return _criar_projeto


@pytest.fixture
def criar_tarefa():
    def _criar_tarefa(projeto, nome="Tarefa", posicao=0):
        tarefa = Tarefa(nome=nome, projeto_id=projeto.id, posicao=posicao)
        db.session.add(tarefa)
        db.session.commit()
        return tarefa

    return _criar_tarefa


def pytest_collection_modifyitems(config, items):
    """Os testes marcados com so_sqlite (que leem o arquivo do banco, por exemplo) ficam de fora
    quando a suíte roda num banco externo."""
    if not URL_DO_BANCO_DE_TESTE:
        return
    pular = pytest.mark.skip(reason="só no SQLite ({} em uso)".format(tipo_da_url(URL_DO_BANCO_DE_TESTE)))
    for item in items:
        if "so_sqlite" in item.keywords:
            item.add_marker(pular)
