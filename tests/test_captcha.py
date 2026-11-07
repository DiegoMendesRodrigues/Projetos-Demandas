# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from datetime import timedelta

import pytest
from flask_security import hash_password

import captcha_imagem
from captcha_imagem import ALFABETO, TAMANHO_DO_CODIGO, VALIDADE, resumo
from app import create_app
from config import Config
from extensions import db, security
from models import DesafioCaptcha, Usuario

SENHA = "senha-de-teste-123"


@pytest.fixture
def com_captcha(app, monkeypatch):
    """Liga o CAPTCHA e fixa o código sorteado, para o teste saber a resposta."""
    app.config["CAPTCHA_ATIVO"] = True
    codigos = iter(["ABC23", "XYZ89", "KLM45", "PQR67"])
    monkeypatch.setattr(captcha_imagem, "sortear_codigo", lambda: next(codigos))
    return app


@pytest.fixture
def conta(app):
    security.datastore.create_user(email="ana@exemplo.com", password=hash_password(SENHA))
    db.session.commit()


def entrar(cliente, captcha):
    dados = {"email": "ana@exemplo.com", "password": SENHA}
    if captcha is not None:
        dados["captcha"] = captcha
    return cliente.post("/login", data=dados)


def test_codigo_usa_so_o_alfabeto_sem_letras_parecidas(app):
    codigo = captcha_imagem.sortear_codigo()

    assert len(codigo) == TAMANHO_DO_CODIGO
    assert set(codigo) <= set(ALFABETO)
    assert not set("01OI") & set(ALFABETO)


def test_imagem_e_png_sem_cache_e_guarda_so_o_resumo(app):
    cliente = app.test_client()

    resposta = cliente.get("/captcha.png")

    assert resposta.status_code == 200
    assert resposta.mimetype == "image/png"
    assert resposta.data.startswith(b"\x89PNG")
    assert resposta.headers["Cache-Control"] == "no-store"
    desafio = DesafioCaptcha.query.one()
    with cliente.session_transaction() as sessao:
        assert sessao["captcha"] == desafio.token
        assert len(desafio.resposta_hash) == 64  # a resposta não fica na sessão nem no banco


def test_nova_imagem_substitui_o_desafio_anterior(app):
    cliente = app.test_client()
    cliente.get("/captcha.png")
    cliente.get("/captcha.png")

    assert DesafioCaptcha.query.count() == 1


@pytest.fixture
def app_com_recuperacao(app, tmp_path, monkeypatch):
    """A rota Esqueci minha senha só é criada quando a recuperação está ligada ao iniciar."""

    class ConfigComRecuperacao(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format((tmp_path / "recuperacao.db").as_posix())
        WTF_CSRF_ENABLED = False
        ANEXOS_DIR = tmp_path / "anexos-recuperacao"
        CONTA_INICIAL_EMAIL = None
        SECURITY_RECOVERABLE = True

    outra = create_app(ConfigComRecuperacao)
    codigos = iter(["ABC23", "XYZ89"])
    monkeypatch.setattr(captcha_imagem, "sortear_codigo", lambda: next(codigos))
    with outra.app_context():
        security.datastore.create_user(email="ana@exemplo.com", password=hash_password(SENHA))
        db.session.commit()
        yield outra
        db.session.remove()


def test_login_mostra_a_imagem_e_o_campo(com_captcha):
    login = com_captcha.test_client().get("/login").get_data(as_text=True)

    assert 'src="/captcha.png"' in login and 'name="captcha"' in login and "data-captcha-trocar" in login


@pytest.mark.so_sqlite
def test_esqueci_minha_senha_mostra_e_exige_o_codigo(app_com_recuperacao):
    cliente = app_com_recuperacao.test_client()

    pagina = cliente.get("/reset").get_data(as_text=True)
    assert 'src="/captcha.png"' in pagina and 'name="captcha"' in pagina

    cliente.get("/captcha.png")
    errado = cliente.post("/reset", data={"email": "ana@exemplo.com", "captcha": "ERRAD"})
    assert "não confere com a imagem" in errado.get_data(as_text=True)

    cliente.get("/captcha.png")
    certo = cliente.post("/reset", data={"email": "ana@exemplo.com", "captcha": "XYZ89"})
    assert "não confere com a imagem" not in certo.get_data(as_text=True)
    assert DesafioCaptcha.query.count() == 0


def test_login_com_o_codigo_certo_entra(com_captcha, conta):
    cliente = com_captcha.test_client()
    cliente.get("/captcha.png")

    resposta = entrar(cliente, "abc23")  # sem diferença entre maiúsculas e minúsculas

    assert resposta.status_code == 302
    assert DesafioCaptcha.query.count() == 0


@pytest.mark.parametrize("captcha", [None, "", "ERRAD"])
def test_login_sem_o_codigo_certo_nao_entra(com_captcha, conta, captcha):
    cliente = com_captcha.test_client()
    cliente.get("/captcha.png")

    resposta = entrar(cliente, captcha)

    assert resposta.status_code == 200
    assert "não confere com a imagem" in resposta.get_data(as_text=True)
    assert cliente.get("/").status_code == 302  # continua sem login


def test_codigo_vale_uma_unica_tentativa(com_captcha, conta):
    cliente = com_captcha.test_client()
    cliente.get("/captcha.png")
    entrar(cliente, "ERRAD")

    # A resposta certa da imagem antiga já não serve.
    assert entrar(cliente, "ABC23").status_code == 200


def test_codigo_reaproveitado_em_outra_sessao_nao_entra(com_captcha, conta):
    cliente = com_captcha.test_client()
    cliente.get("/captcha.png")
    with cliente.session_transaction() as sessao:
        token = sessao["captcha"]
    assert entrar(cliente, "ABC23").status_code == 302

    invasor = com_captcha.test_client()
    with invasor.session_transaction() as sessao:
        sessao["captcha"] = token
    assert entrar(invasor, "ABC23").status_code == 200


def test_codigo_vencido_nao_entra(com_captcha, conta):
    cliente = com_captcha.test_client()
    cliente.get("/captcha.png")
    desafio = DesafioCaptcha.query.one()
    desafio.criado_em -= VALIDADE + timedelta(seconds=1)
    db.session.commit()

    assert entrar(cliente, "ABC23").status_code == 200


def test_senha_nao_e_testada_sem_o_codigo(com_captcha, conta, monkeypatch):
    testadas = []
    monkeypatch.setattr(Usuario, "verify_and_update_password", lambda *a: testadas.append(a) or True)
    cliente = com_captcha.test_client()
    cliente.get("/captcha.png")

    entrar(cliente, "ERRAD")
    assert testadas == []

    cliente.get("/captcha.png")
    entrar(cliente, "XYZ89")
    assert len(testadas) == 1  # com o código certo, a senha é conferida


def test_captcha_desligado_dispensa_o_codigo(app, conta):
    assert app.config["CAPTCHA_ATIVO"] is False
    cliente = app.test_client()

    assert 'name="captcha"' not in cliente.get("/login").get_data(as_text=True)
    assert entrar(cliente, None).status_code == 302


def test_captcha_vem_ligado_na_configuracao():
    assert Config.CAPTCHA_ATIVO is True


def test_resumo_ignora_espacos_e_maiusculas():
    assert resumo(" abc23 ") == resumo("ABC23")
