# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
import sqlite3

import pytest
from flask_security import verify_password
from sqlalchemy import inspect

import captcha_imagem
from app import create_app
from config import Config
from extensions import db
from models import ICONE_PADRAO, Categoria, Usuario
from tests.conftest import SENHA


@pytest.mark.parametrize("url", ["/login", "/register"])
def test_telas_de_entrada_oferecem_o_icone_de_ver_a_senha(app, url):
    html = app.test_client().get(url).get_data(as_text=True)

    modelo = html.split('<template id="modelo-ver-senha">')[1].split("</template>")[0]
    assert 'type="button"' in modelo
    assert 'aria-label="Mostrar senha"' in modelo
    assert 'data-dica="Mostrar senha"' in modelo
    assert 'type="password"' in html


def test_alterar_senha_oferece_o_icone_de_ver_a_senha(cliente):
    assert 'id="modelo-ver-senha"' in cliente.get("/change").get_data(as_text=True)


@pytest.mark.parametrize("url", ["/perfil", "/change", "/administracao/usuarios"])
def test_telas_da_conta_nao_exibem_o_link_voltar_ao_quadro(cliente, url):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()

    html = cliente.get(url).get_data(as_text=True)

    assert "Voltar ao quadro" not in html
    assert "menu-conta" not in html


def test_quadro_exige_login(app):
    resposta = app.test_client().get("/")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_api_sem_login_retorna_401(app):
    resposta = app.test_client().post(
        "/api/tarefas/1/mover", json={"projeto_id": 1, "posicao": 0}
    )

    assert resposta.status_code == 401


def test_login_em_portugues(app):
    html = app.test_client().get("/login").get_data(as_text=True)

    assert 'lang="pt-BR"' in html
    assert "Senha" in html


def test_paginas_exibem_logotipo_e_favicon(app):
    cliente = app.test_client()

    html = cliente.get("/login").get_data(as_text=True)

    # O favicon vem do ícone do cabeçalho, em .ico (16, 32 e 48 px) e em PNG de 32 px.
    assert '<link rel="icon" href="/static/img/favicon.ico" sizes="48x48">' in html
    assert '<link rel="icon" type="image/png" href="/static/img/favicon-32.png" sizes="32x32">' in html
    assert "logo.svg" not in html
    for endereco in ("/static/img/favicon.ico", "/static/img/favicon-32.png"):
        assert cliente.get(endereco).status_code == 200
    # O cabeçalho mostra o ícone e, ao lado, o nome do sistema estilizado.
    assert re.search(r'<img class="marca-logo" src="/static/img/icone_cabecalho.png\?v=[0-9a-f]{12}" alt="" width="87" height="60">', html)
    assert '<span class="marca-nome">Projetos <span class="marca-e">&amp;</span> Demandas</span>' in html
    assert cliente.get("/static/img/icone_cabecalho.png").status_code == 200


def test_mensagem_de_acesso_negado_em_portugues(app):
    resposta = app.test_client().get("/perfil", follow_redirects=True)

    assert "Entre para acessar esta página." in resposta.get_data(as_text=True)


def test_pagina_inicial_sem_login_nao_exibe_notificacao(app):
    resposta = app.test_client().get("/", follow_redirects=True)

    assert "/login" in resposta.request.path
    assert "Entre para acessar esta página." not in resposta.get_data(as_text=True)


def test_cadastro_cria_usuario_e_autentica(app):
    cliente = app.test_client()

    resposta = cliente.post(
        "/register",
        data={
            "nome": "Maria da Silva",
            "email": "nova@exemplo.com",
            "password": "uma-senha-bem-longa-42",
            "password_confirm": "uma-senha-bem-longa-42",
        },
    )

    assert resposta.status_code == 302
    assert Usuario.query.filter_by(email="nova@exemplo.com").one().nome == "Maria da Silva"
    html = cliente.get("/").get_data(as_text=True)
    assert "Maria da Silva" in html


CADASTRO_VALIDO = {
    "nome": "Maria da Silva",
    "email": "nova@exemplo.com",
    "password": "uma-senha-bem-longa-42",
    "password_confirm": "uma-senha-bem-longa-42",
}


@pytest.mark.parametrize(
    "nome, mensagem",
    [
        ("", "Informe seu nome completo."),
        ("   ", "Informe seu nome completo."),
        ("Maria", "Informe seu nome e sobrenome."),
    ],
)
def test_cadastro_exige_nome_completo(app, nome, mensagem):
    resposta = app.test_client().post(
        "/register", data=dict(CADASTRO_VALIDO, nome=nome)
    )

    assert mensagem in resposta.get_data(as_text=True)
    assert Usuario.query.count() == 0


@pytest.mark.parametrize(
    "campos, mensagem",
    [
        ({"email": ""}, "Email não informado"),
        ({"email": "abc"}, "Endereço de email inválido"),
        ({"password": "", "password_confirm": ""}, "Senha não informada"),
        (
            {"password": "abc", "password_confirm": "abc"},
            "A senha deve ter pelo menos 10 caracteres.",
        ),
        (
            {"password": "abcdefghij", "password_confirm": "abcdefghij"},
            "A senha é fácil de adivinhar. Use uma frase ou misture palavras, números e símbolos.",
        ),
        ({"password_confirm": "outra-senha-qualquer"}, "Senhas não conferem"),
    ],
)
def test_erros_de_cadastro_em_portugues(app, campos, mensagem):
    resposta = app.test_client().post(
        "/register", data=dict(CADASTRO_VALIDO, **campos)
    )

    assert mensagem in resposta.get_data(as_text=True)


def test_erro_de_senha_curta_na_alteracao_em_portugues(cliente):
    resposta = cliente.post(
        "/change",
        data={
            "password": SENHA,
            "new_password": "abc",
            "new_password_confirm": "abc",
        },
    )

    assert "A senha deve ter pelo menos 10 caracteres." in resposta.get_data(as_text=True)


@pytest.mark.parametrize(
    "dados, mensagem",
    [
        # As respostas genéricas não revelam se o e-mail tem conta.
        ({"email": "", "password": ""}, "E-mail ou senha inválidos."),
        ({"email": "z@exemplo.com", "password": "x12345678"}, "E-mail ou senha inválidos."),
    ],
)
def test_erros_de_login_em_portugues(app, dados, mensagem):
    resposta = app.test_client().post("/login", data=dados)

    assert mensagem in resposta.get_data(as_text=True)


@pytest.mark.parametrize(
    "url, mensagem",
    [
        ("/inexistente", "Página não encontrada."),
        ("/tarefas", "Esta ação não é permitida nesta página."),
    ],
)
def test_paginas_de_erro_em_portugues(app, url, mensagem):
    assert mensagem in app.test_client().get(url).get_data(as_text=True)


def test_formulario_de_cadastro_exibe_nome_completo(app):
    html = app.test_client().get("/register").get_data(as_text=True)

    assert "Nome completo" in html


@pytest.mark.so_sqlite
def test_banco_antigo_recebe_coluna_icone_sem_perder_categorias(tmp_path):
    arquivo = tmp_path / "antigo.db"
    conexao = sqlite3.connect(arquivo)
    conexao.execute(
        "CREATE TABLE categoria (id INTEGER PRIMARY KEY, nome VARCHAR(80), usuario_id INTEGER)"
    )
    conexao.execute("INSERT INTO categoria VALUES (1, 'Antiga', 1)")
    conexao.commit()
    conexao.close()

    class ConfigAntiga(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format(arquivo.as_posix())

    aplicacao = create_app(ConfigAntiga)

    with aplicacao.app_context():
        categoria = Categoria.query.one()
        assert categoria.nome == "Antiga"
        assert categoria.icone == ICONE_PADRAO
        db.session.remove()
        db.engine.dispose()


@pytest.mark.so_sqlite
@pytest.mark.parametrize(
    "endereco",
    ["https://203.0.113.10", "https://192.168.0.25:8443", "https://[2001:db8::1]"],
)
def test_login_funciona_em_qualquer_ip_com_csrf_e_https(tmp_path, endereco, monkeypatch):
    class ConfigPorIp(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format((tmp_path / "ip.db").as_posix())
        CONTA_INICIAL_SENHA = "Senha-de-teste-1"

    aplicacao = create_app(ConfigPorIp)
    cliente = aplicacao.test_client()

    pagina = cliente.get("/login", base_url=endereco).get_data(as_text=True)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', pagina).group(1)
    # Com a configuração real, o CAPTCHA está ligado: o código da imagem é fixado no teste.
    monkeypatch.setattr(captcha_imagem, "sortear_codigo", lambda: "ABC23")
    assert cliente.get("/captcha.png", base_url=endereco).status_code == 200
    resposta = cliente.post(
        "/login",
        base_url=endereco,
        headers={"Referer": endereco + "/login"},
        data={
            "email": ConfigPorIp.CONTA_INICIAL_EMAIL,
            "password": ConfigPorIp.CONTA_INICIAL_SENHA,
            "csrf_token": token,
            "captcha": "ABC23",
        },
    )

    assert resposta.status_code == 302
    # A conta inicial entra, mas precisa trocar a senha antes de usar o sistema.
    quadro = cliente.get("/", base_url=endereco)
    assert quadro.status_code == 302 and quadro.headers["Location"].endswith("/change")
    assert cliente.get("/change", base_url=endereco).status_code == 200

    with aplicacao.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.mark.so_sqlite
def test_banco_antigo_recebe_coluna_nome_sem_perder_usuarios(tmp_path):
    arquivo = tmp_path / "antigo.db"
    conexao = sqlite3.connect(arquivo)
    conexao.execute(
        "CREATE TABLE usuario (id INTEGER PRIMARY KEY, email VARCHAR(255), "
        "password VARCHAR(255), active BOOLEAN, fs_uniquifier VARCHAR(64), "
        "tema VARCHAR(20), modo VARCHAR(20))"
    )
    conexao.execute(
        "INSERT INTO usuario VALUES (1, 'antiga@exemplo.com', 'x', 1, 'u', 'azul', 'claro')"
    )
    conexao.commit()
    conexao.close()

    class ConfigAntiga(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format(arquivo.as_posix())
        CONTA_INICIAL_EMAIL = None

    aplicacao = create_app(ConfigAntiga)

    with aplicacao.app_context():
        usuario = Usuario.query.one()
        assert usuario.email == "antiga@exemplo.com"
        assert usuario.nome == ""
        assert "modo" not in {
            coluna["name"] for coluna in inspect(db.engine).get_columns("usuario")
        }
        db.session.remove()
        db.engine.dispose()


def test_alterar_senha_nao_exibe_notificacao(cliente):
    nova_senha = "outra-senha-bem-longa-42"

    resposta = cliente.post(
        "/change",
        data={
            "password": SENHA,
            "new_password": nova_senha,
            "new_password_confirm": nova_senha,
        },
        follow_redirects=True,
    )

    usuario = db.session.get(Usuario, cliente.usuario_id)
    assert verify_password(nova_senha, usuario.password)
    html = resposta.get_data(as_text=True)
    assert "<p>" not in html.split('id="notificacao"')[1].split("</dialog>")[0]


def test_alterar_senha_identifica_a_senha_atual(cliente):
    html = cliente.get("/change").get_data(as_text=True)

    assert "Senha atual" in html


def test_logout_encerra_sessao(cliente):
    cliente.post("/logout")

    assert cliente.get("/").status_code == 302
