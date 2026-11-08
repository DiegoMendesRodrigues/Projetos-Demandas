# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import io
import json
import sqlite3
from datetime import timedelta
from unittest.mock import patch

import pytest
from flask_security import hash_password, verify_password

import captcha_imagem
import config
import seguranca
from app import SENHA_PADRAO_PUBLICADA, create_app
from config import Config
from extensions import db, security
from models import ConfiguracaoEmail, GrupoDeUsuarios, Imagem, Usuario
from routes import (
    LIMITE_IMAGENS_PENDENTES,
    PRAZO_DAS_IMAGENS_PENDENTES,
    agora,
    aplicar_configuracao_de_email,
    apagar_imagens_pendentes,
    espaco_usado,
)
from seguranca import (
    HSTS,
    LIMITES,
    TENTATIVAS_POR_CONTA,
    POLITICA_DE_CONTEUDO,
    Limitador,
    arquivos_do_banco,
    cifrar,
    decifrar,
    esta_cifrada,
    limitador,
    proteger_arquivos,
)
from tests.conftest import SENHA

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 20
NOVA_SENHA = "Outra-Senha-Forte-2026"


def config_de_teste(tmp_path, **opcoes):
    class ConfigDaConta(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format((tmp_path / "conta.db").as_posix())
        WTF_CSRF_ENABLED = False
        ANEXOS_DIR = tmp_path / "anexos"
        CAPTCHA_ATIVO = False
        LIMITES_ATIVOS = False

    for nome, valor in opcoes.items():
        setattr(ConfigDaConta, nome, valor)
    return ConfigDaConta


def fechar(aplicacao):
    with aplicacao.app_context():
        db.session.remove()
        db.engine.dispose()


def enviar_imagem(cliente, conteudo=PNG):
    return cliente.post(
        "/api/imagens",
        data={"imagem": (io.BytesIO(conteudo), "foto.png")},
        content_type="multipart/form-data",
    )


# ---------- Troca obrigatória da senha da conta inicial


@pytest.fixture
def conta_inicial(tmp_path):
    aplicacao = create_app(config_de_teste(tmp_path))
    cliente = aplicacao.test_client()
    resposta = cliente.post(
        "/login",
        data={"email": Config.CONTA_INICIAL_EMAIL, "password": Config.CONTA_INICIAL_SENHA},
    )
    assert resposta.status_code == 302
    yield aplicacao, cliente
    fechar(aplicacao)


def test_conta_inicial_nasce_obrigada_a_trocar_a_senha(conta_inicial):
    aplicacao, _ = conta_inicial

    with aplicacao.app_context():
        conta = Usuario.query.filter_by(email=Config.CONTA_INICIAL_EMAIL).one()
        assert conta.trocar_senha is True
        assert conta.confirmed_at is not None


@pytest.mark.parametrize("endereco", ["/", "/meu-dia", "/perfil", "/administracao/usuarios"])
def test_sem_trocar_a_senha_as_paginas_levam_a_alterar_a_senha(conta_inicial, endereco):
    _, cliente = conta_inicial

    resposta = cliente.get(endereco)

    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/change")
    pagina = cliente.get("/change").get_data(as_text=True)
    assert "Antes de continuar, crie uma nova senha para esta conta." in pagina


def test_sem_trocar_a_senha_a_api_responde_403_em_json(conta_inicial):
    _, cliente = conta_inicial

    resposta = cliente.post("/api/projetos/ordem", json={"ordem": []})

    assert resposta.status_code == 403
    assert resposta.get_json()["erro"] == "Antes de continuar, crie uma nova senha para esta conta."


def test_trocar_a_senha_libera_o_sistema(conta_inicial):
    aplicacao, cliente = conta_inicial

    resposta = cliente.post(
        "/change",
        data={
            "password": Config.CONTA_INICIAL_SENHA,
            "new_password": NOVA_SENHA,
            "new_password_confirm": NOVA_SENHA,
        },
    )

    assert resposta.status_code == 302
    assert cliente.get("/").status_code == 200
    with aplicacao.app_context():
        conta = Usuario.query.filter_by(email=Config.CONTA_INICIAL_EMAIL).one()
        assert conta.trocar_senha is False
        assert verify_password(NOVA_SENHA, conta.password)


def test_sair_continua_possivel_sem_trocar_a_senha(conta_inicial):
    _, cliente = conta_inicial

    assert cliente.post("/logout").status_code == 302
    # Fora da conta, a página inicial é a apresentação da área externa.
    assert cliente.get("/").headers["Location"] == "/projetos-e-demandas"


def criar_banco_sem_a_coluna(arquivo, email, senha):
    """Um banco de antes da troca obrigatória, com a conta inicial e outra conta."""
    aplicacao = create_app(config_de_teste(arquivo.parent, CONTA_INICIAL_EMAIL=None))
    with aplicacao.app_context():
        security.datastore.create_user(email=email, password=hash_password(senha))
        security.datastore.create_user(email="outra@exemplo.com", password=hash_password(SENHA_PADRAO_PUBLICADA))
        db.session.commit()
    fechar(aplicacao)
    conexao = sqlite3.connect(arquivo)
    conexao.execute("ALTER TABLE usuario DROP COLUMN trocar_senha")
    # Um banco de antes do Alembic não tem a tabela das revisões.
    conexao.execute("DROP TABLE alembic_version")
    conexao.commit()
    conexao.close()


@pytest.mark.so_sqlite
@pytest.mark.parametrize("senha, obrigada", [(SENHA_PADRAO_PUBLICADA, True), (NOVA_SENHA, False)])
def test_migracao_obriga_a_trocar_so_a_senha_padrao_da_conta_inicial(tmp_path, senha, obrigada):
    criar_banco_sem_a_coluna(tmp_path / "conta.db", Config.CONTA_INICIAL_EMAIL, senha)

    aplicacao = create_app(config_de_teste(tmp_path))

    with aplicacao.app_context():
        assert Usuario.query.filter_by(email=Config.CONTA_INICIAL_EMAIL).one().trocar_senha is obrigada
        # As demais contas não são afetadas, mesmo com a mesma senha.
        assert Usuario.query.filter_by(email="outra@exemplo.com").one().trocar_senha is False
    fechar(aplicacao)


# ---------- Cadastro: CAPTCHA e confirmação do e-mail

CADASTRO = {
    "nome": "Carla Dias",
    "email": "carla@exemplo.com",
    "password": "Pera-Uva-Maca-42",
    "password_confirm": "Pera-Uva-Maca-42",
}


def test_cadastro_mostra_o_captcha(app):
    app.config["CAPTCHA_ATIVO"] = True

    html = app.test_client().get("/register").get_data(as_text=True)

    assert "data-captcha-imagem" in html and 'name="captcha"' in html


def test_cadastro_exige_o_codigo_da_imagem(app, monkeypatch):
    app.config["CAPTCHA_ATIVO"] = True
    monkeypatch.setattr(captcha_imagem, "sortear_codigo", lambda: "ABC23")
    cliente = app.test_client()

    cliente.get("/captcha.png")
    errado = cliente.post("/register", data=dict(CADASTRO, captcha="ZZZ99"))
    assert errado.status_code == 200
    assert Usuario.query.count() == 0

    cliente.get("/captcha.png")
    certo = cliente.post("/register", data=dict(CADASTRO, captcha="ABC23"))
    assert certo.status_code == 302
    assert Usuario.query.filter_by(email="carla@exemplo.com").count() == 1


def test_sem_envio_de_emails_a_conta_cadastrada_ja_nasce_confirmada(app):
    app.test_client().post("/register", data=CADASTRO)

    assert Usuario.query.filter_by(email="carla@exemplo.com").one().confirmed_at is not None


def test_configuracao_de_email_liga_a_confirmacao(app):
    salva = ConfiguracaoEmail(
        servidor="smtp.exemplo.com", porta=587, usar_tls=True, usuario="u",
        senha=cifrar("s", app.config["SECRET_KEY"]), email_envio="e@exemplo.com", nome_envio="P",
    )

    aplicar_configuracao_de_email(app, salva)

    assert app.config["SECURITY_CONFIRMABLE"] is True
    assert app.config["MAIL_PASSWORD"] == "s"


@pytest.fixture
def com_email_configurado(tmp_path):
    """Uma aplicação iniciada com o envio de e-mails já salvo em Configurações."""
    configuracao = config_de_teste(tmp_path, CONTA_INICIAL_EMAIL=None)
    aplicacao = create_app(configuracao)
    with aplicacao.app_context():
        db.session.add(ConfiguracaoEmail(
            id=1, servidor="smtp.exemplo.com", porta=587, usar_tls=True, usuario="u",
            senha=cifrar("s", "chave-de-teste"), email_envio="e@exemplo.com", nome_envio="P",
        ))
        db.session.commit()
    fechar(aplicacao)
    aplicacao = create_app(configuracao)
    yield aplicacao
    fechar(aplicacao)
    # O objeto global do Flask-Security não fica com a confirmação ligada para os outros testes.
    security.confirmable = False


def test_com_email_configurado_o_cadastro_exige_confirmar_o_email(com_email_configurado):
    aplicacao = com_email_configurado
    cliente = aplicacao.test_client()

    with aplicacao.app_context():
        # Com TESTING, o Flask-Mail não envia de fato o e-mail de confirmação.
        resposta = cliente.post("/register", data=CADASTRO)
        assert resposta.status_code == 302
        conta = Usuario.query.filter_by(email="carla@exemplo.com").one()
        assert conta.confirmed_at is None

    assert "security.confirm_email" in aplicacao.view_functions
    entrada = cliente.post("/login", data={"email": CADASTRO["email"], "password": CADASTRO["password"]})
    assert entrada.status_code == 200
    assert cliente.get("/").status_code == 302


def test_conta_criada_pelo_administrador_ja_nasce_confirmada(cliente):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()

    cliente.post(
        "/administracao/usuarios/novo",
        data={"nome": "Carla Dias", "email": "carla@exemplo.com", "senha": "senha-da-carla", "administrador": "nao"},
    )

    assert Usuario.query.filter_by(email="carla@exemplo.com").one().confirmed_at is not None


@pytest.mark.so_sqlite
def test_migracao_confirma_as_contas_que_ja_existiam(tmp_path):
    aplicacao = create_app(config_de_teste(tmp_path, CONTA_INICIAL_EMAIL=None))
    with aplicacao.app_context():
        security.datastore.create_user(email="antiga@exemplo.com", password=hash_password(SENHA))
        db.session.commit()
    fechar(aplicacao)
    conexao = sqlite3.connect(tmp_path / "conta.db")
    conexao.execute("ALTER TABLE usuario DROP COLUMN confirmed_at")
    # Um banco de antes do Alembic não tem a tabela das revisões.
    conexao.execute("DROP TABLE alembic_version")
    conexao.commit()
    conexao.close()

    aplicacao = create_app(config_de_teste(tmp_path, CONTA_INICIAL_EMAIL=None))

    with aplicacao.app_context():
        assert Usuario.query.one().confirmed_at is not None
    fechar(aplicacao)


# ---------- Senhas


def test_senhas_exigem_10_caracteres_e_o_zxcvbn(app):
    assert app.config["SECURITY_PASSWORD_LENGTH_MIN"] == 10
    assert app.config["SECURITY_PASSWORD_COMPLEXITY_CHECKER"] == "zxcvbn"


@pytest.mark.parametrize("senha", ["1234567890", "abcdefghij", "carla@exemplo.com"])
def test_senha_facil_de_adivinhar_e_recusada_em_portugues(app, senha):
    with app.test_request_context():
        erros, _ = security.password_util.validate(senha, True, email="carla@exemplo.com")

    assert erros == ["A senha é fácil de adivinhar. Use uma frase ou misture palavras, números e símbolos."]


def test_senha_forte_e_aceita(app):
    with app.test_request_context():
        assert security.password_util.validate("Pera-Uva-Maca-42", True)[0] is None


def test_lembrar_de_mim_dura_60_dias(app):
    assert app.config["REMEMBER_COOKIE_DURATION"] == timedelta(days=60)


def test_respostas_genericas_nao_revelam_se_o_email_tem_conta(app, cliente):
    assert app.config["SECURITY_RETURN_GENERIC_RESPONSES"] is True
    visitante = app.test_client()

    existente = visitante.post("/login", data={"email": "ana@exemplo.com", "password": "errada-1234"})
    inexistente = visitante.post("/login", data={"email": "zz@exemplo.com", "password": "errada-1234"})

    assert "E-mail ou senha inválidos." in existente.get_data(as_text=True)
    assert "E-mail ou senha inválidos." in inexistente.get_data(as_text=True)


# ---------- Cabeçalhos


def test_paginas_trazem_os_cabecalhos_de_seguranca(app):
    resposta = app.test_client().get("/login")

    assert resposta.headers["Content-Security-Policy"] == POLITICA_DE_CONTEUDO
    assert resposta.headers["X-Frame-Options"] == "DENY"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" not in resposta.headers


def test_hsts_so_em_https(app):
    resposta = app.test_client().get("/login", base_url="https://localhost")

    assert resposta.headers["Strict-Transport-Security"] == HSTS


@pytest.mark.parametrize(
    "diretiva",
    [
        "script-src 'self'",
        "img-src 'self' data: https://i.ytimg.com https://i.vimeocdn.com",
        "frame-src https://www.youtube-nocookie.com https://player.vimeo.com",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
    ],
)
def test_politica_de_conteudo(diretiva):
    assert diretiva in POLITICA_DE_CONTEUDO.split("; ")


def test_politica_de_conteudo_nao_libera_script_embutido():
    assert "'unsafe-inline'" not in POLITICA_DE_CONTEUDO.split("style-src")[0]
    assert "'unsafe-eval'" not in POLITICA_DE_CONTEUDO


def test_modelos_nao_tem_script_embutido():
    """Com o script-src 'self', um <script> com código ou um onclick= não rodaria."""
    from pathlib import Path
    import re

    for arquivo in Path(__file__).resolve().parent.parent.joinpath("templates").rglob("*.html"):
        texto = arquivo.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", texto), arquivo
        assert not re.search(r"\son[a-z]+=", texto), arquivo


# ---------- Limite de requisições


def test_limitador_conta_numa_janela_deslizante():
    relogio = [0.0]
    contador = Limitador(relogio=lambda: relogio[0])

    assert [contador.permitir("a", 2, 60)[0] for _ in range(3)] == [True, True, False]
    assert contador.permitir("b", 2, 60)[0] is True  # cada chave tem a sua conta
    relogio[0] = 30
    permitido, espera = contador.permitir("a", 2, 60)
    assert permitido is False and espera == 31
    relogio[0] = 61
    assert contador.permitir("a", 2, 60)[0] is True


def test_limitador_esquece_as_chaves_antigas():
    relogio = [0.0]
    contador = Limitador(relogio=lambda: relogio[0])
    contador.permitir("a", 5, 60)

    relogio[0] = 100 * 60 * 60
    contador.permitir("b", 5, 60)

    assert set(contador.registros) == {"b"}


@pytest.fixture
def com_limites(app):
    app.config["LIMITES_ATIVOS"] = True
    limitador.zerar()
    yield app
    limitador.zerar()


def test_cadastro_tem_limite_por_ip(com_limites):
    cliente = com_limites.test_client()
    _, quantidade, _, _ = LIMITES["security.register"]

    for _ in range(quantidade):
        assert cliente.post("/register", data={}).status_code == 200
    resposta = cliente.post("/register", data={})

    assert resposta.status_code == 429
    assert int(resposta.headers["Retry-After"]) > 0
    assert "Muitas tentativas em pouco tempo." in resposta.get_data(as_text=True)
    # Abrir a página continua possível: só os envios contam.
    assert cliente.get("/register").status_code == 200
    # Outro IP tem a sua própria conta.
    outro = cliente.post("/register", data={}, environ_base={"REMOTE_ADDR": "10.0.0.9"})
    assert outro.status_code == 200


def test_imagem_do_captcha_tem_limite_por_ip(com_limites):
    cliente = com_limites.test_client()
    _, quantidade, _, _ = LIMITES["principal.imagem_captcha"]

    for _ in range(quantidade):
        cliente.get("/captcha.png")

    assert cliente.get("/captcha.png").status_code == 429


def test_api_tem_limite_por_usuario_em_json(com_limites, cliente, outro_cliente):
    _, quantidade, _, _ = LIMITES["principal.previa_do_video"]

    for _ in range(quantidade):
        cliente.post("/api/videos/previa", json={"endereco": ""})
    resposta = cliente.post("/api/videos/previa", json={"endereco": ""})

    assert resposta.status_code == 429
    assert resposta.get_json()["erro"].startswith("Muitas tentativas")
    # Do mesmo IP, outra pessoa tem a sua própria conta.
    assert outro_cliente.post("/api/videos/previa", json={"endereco": ""}).status_code != 429


def test_rotas_com_limite_existem(app):
    endpoints = set(app.view_functions)
    # send_confirmation só existe com o envio de e-mails ligado.
    opcionais = {"security.send_confirmation"}

    assert set(LIMITES) - opcionais <= endpoints


@pytest.mark.so_sqlite
def test_proxy_confiavel_le_o_ip_do_visitante(tmp_path):
    aplicacao = create_app(config_de_teste(tmp_path, CONTA_INICIAL_EMAIL=None, PROXY_CONFIAVEL=True))

    @aplicacao.route("/ip-de-teste")
    def ip_de_teste():
        from flask import request

        return "{} {}".format(request.remote_addr, request.scheme)

    resposta = aplicacao.test_client().get(
        "/ip-de-teste", headers={"X-Forwarded-For": "203.0.113.7", "X-Forwarded-Proto": "https"}
    )

    assert resposta.get_data(as_text=True) == "203.0.113.7 https"
    assert resposta.headers["Strict-Transport-Security"] == HSTS
    fechar(aplicacao)


# ---------- Imagens da descrição


def test_imagens_pendentes_tem_limite(app, cliente):
    for _ in range(LIMITE_IMAGENS_PENDENTES):
        assert enviar_imagem(cliente).status_code == 200

    resposta = enviar_imagem(cliente)

    assert resposta.status_code == 400
    assert "Salve a demanda antes de enviar mais imagens" in resposta.get_json()["erro"]
    assert Imagem.query.count() == LIMITE_IMAGENS_PENDENTES


def test_imagem_guarda_o_tamanho_e_o_momento(app, cliente):
    enviar_imagem(cliente)

    imagem = Imagem.query.one()
    assert imagem.tamanho == len(PNG)
    assert imagem.criado_em is not None


def test_imagens_entram_no_espaco_usado(app, cliente):
    usuario = db.session.get(Usuario, cliente.usuario_id)
    enviar_imagem(cliente)
    enviar_imagem(cliente)

    assert espaco_usado(usuario) == 2 * len(PNG)


def test_imagem_que_nao_cabe_no_espaco_e_recusada(app, cliente):
    with patch("models.BYTES_POR_MB", 1):
        usuario = db.session.get(Usuario, cliente.usuario_id)
        usuario.plano.armazenamento_mb = len(PNG) + 10
        db.session.commit()
        assert enviar_imagem(cliente).status_code == 200

        resposta = enviar_imagem(cliente)

    assert resposta.status_code == 400
    assert "A imagem não cabe no seu espaço" in resposta.get_json()["erro"]


def test_imagens_pendentes_antigas_sao_apagadas(app, cliente, criar_projeto, criar_tarefa):
    enviar_imagem(cliente)
    enviar_imagem(cliente)
    enviar_imagem(cliente)
    antiga, recente, usada = Imagem.query.order_by(Imagem.id).all()
    momento = agora()
    antiga.criado_em = momento - PRAZO_DAS_IMAGENS_PENDENTES - timedelta(minutes=1)
    usada.criado_em = antiga.criado_em
    usada.tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    db.session.commit()
    arquivo_antigo = app.config["ANEXOS_DIR"] / antiga.arquivo

    assert apagar_imagens_pendentes(momento) == 1

    assert {imagem.id for imagem in Imagem.query} == {recente.id, usada.id}
    assert not arquivo_antigo.exists()


@pytest.mark.so_sqlite
def test_migracao_guarda_o_tamanho_das_imagens(tmp_path):
    aplicacao = create_app(config_de_teste(tmp_path, CONTA_INICIAL_EMAIL=None))
    with aplicacao.app_context():
        usuario = security.datastore.create_user(email="ana@exemplo.com", password=hash_password(SENHA))
        db.session.flush()
        (aplicacao.config["ANEXOS_DIR"] / "a").write_bytes(PNG)
        db.session.add(Imagem(arquivo="a", tipo="image/png", usuario_id=usuario.id))
        db.session.commit()
    fechar(aplicacao)
    conexao = sqlite3.connect(tmp_path / "conta.db")
    conexao.execute("ALTER TABLE imagem DROP COLUMN tamanho")
    # Um banco de antes do Alembic não tem a tabela das revisões.
    conexao.execute("DROP TABLE alembic_version")
    conexao.execute("ALTER TABLE imagem DROP COLUMN criado_em")
    conexao.commit()
    conexao.close()

    aplicacao = create_app(config_de_teste(tmp_path, CONTA_INICIAL_EMAIL=None))

    with aplicacao.app_context():
        imagem = Imagem.query.one()
        assert imagem.tamanho == len(PNG)
        assert imagem.criado_em is not None
    fechar(aplicacao)


# ---------- Grupos e compartilhamento


@pytest.mark.parametrize(
    "ingresso, aviso",
    [
        ("qualquer_usuario", "Grupo aberto: qualquer pessoa com conta pode ingressar"),
        ("qualquer_membro", "Qualquer membro pode adicionar outras pessoas"),
        ("administrador", None),
    ],
)
def test_compartilhar_avisa_quando_o_grupo_e_aberto(cliente, criar_categoria, ingresso, aviso):
    usuario = db.session.get(Usuario, cliente.usuario_id)
    categoria = criar_categoria(cliente.usuario_id)
    grupo = GrupoDeUsuarios(
        nome="Brigada", cor="#1a6fe0", icone="pessoas", ingresso=ingresso, administrador_id=usuario.id
    )
    grupo.membros.append(usuario)
    db.session.add(grupo)
    db.session.commit()

    html = cliente.get("/categorias/{}/compartilhar".format(categoria.id)).get_data(as_text=True)

    if aviso:
        assert aviso in html
    else:
        assert "compartilhar-alerta" not in html


# ---------- Senha do SMTP e arquivos do banco


def test_cifrar_e_decifrar_a_senha_do_smtp():
    cifrada = cifrar("senha-do-smtp", "chave")

    assert esta_cifrada(cifrada) and "senha-do-smtp" not in cifrada
    assert cifrar("senha-do-smtp", "chave") != cifrada  # cada cifragem é diferente
    assert decifrar(cifrada, "chave") == "senha-do-smtp"


def test_decifrar_com_outra_chave_devolve_vazio():
    assert decifrar(cifrar("senha-do-smtp", "chave"), "outra-chave") == ""


def test_decifrar_aceita_a_senha_antiga_em_texto():
    assert decifrar("em-texto", "chave") == "em-texto"
    assert decifrar(None, "chave") == ""


@pytest.mark.so_sqlite
def test_iniciar_cifra_a_senha_do_smtp_gravada_em_texto(tmp_path):
    configuracao = config_de_teste(tmp_path, CONTA_INICIAL_EMAIL=None)
    aplicacao = create_app(configuracao)
    fechar(aplicacao)
    conexao = sqlite3.connect(tmp_path / "conta.db")
    conexao.execute(
        "INSERT INTO configuracao_email (id, servidor, porta, usar_tls, usuario, senha, email_envio, nome_envio) "
        "VALUES (1, 'smtp.exemplo.com', 587, 1, 'u', 'em-texto', 'e@exemplo.com', 'P')"
    )
    conexao.commit()
    conexao.close()

    aplicacao = create_app(configuracao)

    with aplicacao.app_context():
        salva = db.session.get(ConfiguracaoEmail, 1)
        assert esta_cifrada(salva.senha)
        assert decifrar(salva.senha, "chave-de-teste") == "em-texto"
        assert aplicacao.config["MAIL_PASSWORD"] == "em-texto"
    fechar(aplicacao)
    security.confirmable = False


@pytest.mark.so_sqlite
def test_arquivos_do_banco_incluem_os_do_modo_wal():
    assert arquivos_do_banco("/dados/banco.db") == [
        "/dados/banco.db", "/dados/banco.db-wal", "/dados/banco.db-shm", "/dados/banco.db-journal",
    ]
    assert arquivos_do_banco(None) == [] and arquivos_do_banco(":memory:") == []


def test_proteger_arquivos_deixa_so_o_dono_ler(tmp_path, monkeypatch):
    existente = tmp_path / "banco.db"
    existente.write_text("x")
    chamadas = []
    monkeypatch.setattr(seguranca.os, "name", "posix")
    monkeypatch.setattr(seguranca.os, "chmod", lambda caminho, modo: chamadas.append((caminho, modo)))

    proteger_arquivos([existente, tmp_path / "inexistente-wal", None])

    assert chamadas == [(existente, 0o600)]


def test_segredos_sao_criados_no_arquivo_local(tmp_path, monkeypatch):
    arquivo = tmp_path / "segredos.json"
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(config, "DATABASE_DIR", tmp_path)
    monkeypatch.setattr(config, "ARQUIVO_SEGREDOS", arquivo)

    segredos = config.carregar_segredos()

    assert json.loads(arquivo.read_text(encoding="utf-8")) == segredos
    assert config.carregar_segredos() == segredos
    if config.os.name == "posix":
        assert arquivo.stat().st_mode & 0o777 == 0o600


# ---------- Limite por conta, cache e cabeçalhos entre sites


def criar_conta(email="ana@exemplo.com"):
    security.datastore.create_user(email=email, password=hash_password(SENHA))
    db.session.commit()


def test_limite_conta_so_senhas_erradas_que_passaram_pelo_captcha(com_limites):
    criar_conta()
    quantidade, _ = TENTATIVAS_POR_CONTA

    for numero in range(quantidade):
        # Cada tentativa vem de um IP diferente: o limite por IP não as pegaria.
        resposta = com_limites.test_client().post(
            "/login", data={"email": "Ana@Exemplo.com", "password": "errada-1234"},
            environ_base={"REMOTE_ADDR": "10.0.0.{}".format(numero)},
        )
        assert resposta.status_code == 200
    bloqueada = com_limites.test_client().post(
        "/login", data={"email": "ana@exemplo.com", "password": SENHA}, environ_base={"REMOTE_ADDR": "10.0.1.1"}
    )

    assert bloqueada.status_code == 429 and int(bloqueada.headers["Retry-After"]) > 0
    # As outras contas continuam entrando.
    criar_conta("bruno@exemplo.com")
    assert com_limites.test_client().post("/login", data={"email": "bruno@exemplo.com", "password": SENHA}).status_code == 302


def test_acertar_a_senha_zera_a_contagem_da_conta(com_limites):
    criar_conta()
    quantidade, _ = TENTATIVAS_POR_CONTA
    cliente = com_limites.test_client()

    for _ in range(quantidade - 1):
        cliente.post("/login", data={"email": "ana@exemplo.com", "password": "errada-1234"},
                     environ_base={"REMOTE_ADDR": "10.0.2.1"})
    assert cliente.post("/login", data={"email": "ana@exemplo.com", "password": SENHA},
                        environ_base={"REMOTE_ADDR": "10.0.2.2"}).status_code == 302
    cliente.post("/logout")
    for _ in range(quantidade - 1):
        assert com_limites.test_client().post(
            "/login", data={"email": "ana@exemplo.com", "password": "errada-1234"},
            environ_base={"REMOTE_ADDR": "10.0.2.3"},
        ).status_code == 200


def test_codigo_errado_do_captcha_nao_bloqueia_a_conta(com_limites):
    com_limites.config["CAPTCHA_ATIVO"] = True
    criar_conta()
    quantidade, _ = TENTATIVAS_POR_CONTA

    for numero in range(quantidade + 2):
        com_limites.test_client().post(
            "/login", data={"email": "ana@exemplo.com", "password": "errada-1234", "captcha": "ERRADO"},
            environ_base={"REMOTE_ADDR": "10.0.3.{}".format(numero)},
        )

    assert limitador.espera("conta:ana@exemplo.com", *TENTATIVAS_POR_CONTA) == 0


def test_busca_de_membros_tem_limite(com_limites):
    criar_conta()
    cliente = com_limites.test_client()
    cliente.post("/login", data={"email": "ana@exemplo.com", "password": SENHA})
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=1)
    grupo.membros.append(db.session.get(Usuario, 1))
    db.session.add(grupo)
    db.session.commit()
    _, quantidade, _, _ = LIMITES["principal.adicionar_membros"]

    for _ in range(quantidade):
        assert cliente.get("/grupos/{}/adicionar?busca=x@exemplo.com".format(grupo.id)).status_code == 200

    assert cliente.get("/grupos/{}/adicionar?busca=y@exemplo.com".format(grupo.id)).status_code == 429


def test_paginas_com_dados_nao_ficam_no_cache(cliente):
    for endereco in ("/", "/meu-dia", "/api/quadro/versao", "/login"):
        resposta = cliente.get(endereco)
        assert "no-store" in resposta.headers["Cache-Control"], endereco
        assert resposta.headers["Cross-Origin-Resource-Policy"] == "same-origin"
        assert resposta.headers["Cross-Origin-Opener-Policy"] == "same-origin"


def test_arquivos_publicos_continuam_no_cache(app):
    cliente = app.test_client()

    estatico = cliente.get("/static/css/style.css")
    assert "no-store" not in estatico.headers.get("Cache-Control", "")
    assert "Cross-Origin-Resource-Policy" not in estatico.headers
    assert cliente.get("/sw.js").headers["Cache-Control"] == "no-cache"


def test_logout_so_por_post(cliente):
    assert cliente.get("/logout").status_code == 405
    assert cliente.get("/").status_code == 200
    assert cliente.post("/logout").status_code == 302


def test_autenticacao_por_token_desligada(app):
    assert app.config["SECURITY_API_ENABLED_METHODS"] == ["session"]
    criar_conta()

    resposta = app.test_client().get("/api/quadro/versao", headers={"Authentication-Token": "qualquer"})

    assert resposta.status_code in (302, 401)


def test_resposta_grande_demais_do_youtube_falha():
    import youtube

    class Resposta:
        def read(self, tamanho):
            return b"x" * tamanho

    with pytest.raises(youtube.ErroNasInformacoes):
        youtube.ler_com_limite(Resposta())
    assert youtube.ler_com_limite(io.BytesIO(b"pequena")) == b"pequena"


@pytest.mark.parametrize("host, nome", [
    ("projetos.exemplo.com", "projetos.exemplo.com"), ("Projetos.Exemplo.com:8002", "projetos.exemplo.com"),
    ("192.168.0.10:443", "192.168.0.10"), ("[::1]:8002", "::1"), ("[::1]", "::1"), ("::1", "::1"),
])
def test_nome_do_host_sem_a_porta(host, nome):
    assert seguranca.nome_do_host(host) == nome


def test_so_atende_os_hosts_permitidos(app):
    app.config["HOSTS_PERMITIDOS"] = frozenset({"projetos.exemplo.com", "192.168.0.10"})
    cliente = app.test_client()

    assert cliente.get("/login", base_url="https://projetos.exemplo.com").status_code == 200
    assert cliente.get("/login", base_url="http://192.168.0.10:8002").status_code == 200
    recusado = cliente.post("/reset", data={"email": "ana@exemplo.com"}, base_url="https://evil.com")
    assert recusado.status_code == 400 and "Endereço não atendido" in recusado.get_data(as_text=True)


def test_sem_hosts_permitidos_aceita_qualquer_endereco(app):
    app.config["HOSTS_PERMITIDOS"] = frozenset()

    assert app.test_client().get("/login", base_url="http://qualquer.exemplo").status_code == 200


def test_hosts_permitidos_vem_do_ambiente(monkeypatch):
    import importlib

    monkeypatch.setenv("HOSTS_PERMITIDOS", " Projetos.Exemplo.com , 10.0.0.1,, ")
    recarregado = importlib.reload(config)
    try:
        assert recarregado.Config.HOSTS_PERMITIDOS == {"projetos.exemplo.com", "10.0.0.1"}
    finally:
        monkeypatch.delenv("HOSTS_PERMITIDOS")
        importlib.reload(config)


def test_configuracoes_avisam_sem_hosts_permitidos(app, criar_cliente):
    cliente = criar_cliente("admin@exemplo.com")
    usuario = db.session.get(Usuario, cliente.usuario_id)
    usuario.administrador = True
    db.session.commit()

    app.config["HOSTS_PERMITIDOS"] = frozenset()
    assert "Defina HOSTS_PERMITIDOS" in cliente.get("/administracao/configuracoes").get_data(as_text=True)
    app.config["HOSTS_PERMITIDOS"] = frozenset({"localhost"})
    assert "Defina HOSTS_PERMITIDOS" not in cliente.get("/administracao/configuracoes").get_data(as_text=True)


def test_nginx_do_install_nao_repassa_qualquer_host():
    from pathlib import Path as Caminho

    texto = (Caminho(__file__).resolve().parent.parent / "INSTALL.md").read_text(encoding="utf-8")
    assert "$http_host" not in texto and "proxy_set_header Host $host;" in texto
    assert texto.count("HOSTS_PERMITIDOS=") == 2 and "return 444;" in texto


@pytest.mark.parametrize("endereco", ["/login", "/register", "/change"])
def test_telas_de_conta_tem_cache_control_valido(cliente, endereco):
    assert cliente.get(endereco).headers["Cache-Control"] == "no-store, private"
