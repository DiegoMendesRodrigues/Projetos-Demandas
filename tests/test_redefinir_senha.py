# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re

import pytest
from flask_security import verify_password

import routes
from extensions import db, mail
from models import Usuario
from routes import ALFABETO_DA_SENHA, ASSUNTO_DA_NOVA_SENHA, gerar_senha
from tests.conftest import SENHA


@pytest.fixture
def administrador(cliente):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()
    return cliente


@pytest.fixture
def email_configurado(app):
    app.config.update(MAIL_SERVER="smtp.exemplo.com", MAIL_DEFAULT_SENDER=("Projetos & Demandas", "envio@exemplo.com"))


def redefinir(cliente, usuario_id):
    return cliente.post("/administracao/usuarios/{}/redefinir-senha".format(usuario_id), follow_redirects=True)


def linha_de(html, email):
    return next(linha for linha in html.split("<tr>") if "<td data-rotulo=\"E-mail\">{}</td>".format(email) in linha)


def conta(usuario_id):
    db.session.expire_all()
    return db.session.get(Usuario, usuario_id)


# ---------- Tela Usuários


def test_botao_fica_a_esquerda_do_editar(administrador, outro_cliente):
    html = administrador.get("/administracao/usuarios").get_data(as_text=True)
    linha = linha_de(html, "bruno@exemplo.com")

    assert 'data-url="/administracao/usuarios/{}/redefinir-senha"'.format(outro_cliente.usuario_id) in linha
    assert linha.index("data-redefinir-senha") < linha.index('data-dica="Editar usuário"')
    assert 'data-dica="Redefinir a senha"' in linha


def test_botao_desligado_na_propria_conta(administrador):
    html = administrador.get("/administracao/usuarios").get_data(as_text=True)
    linha = linha_de(html, "ana@exemplo.com")
    botao = linha.split("data-redefinir-senha")[1].split("</button>")[0]

    assert "disabled" in botao and "Para trocar a sua senha, use Alterar a Senha" in botao


def test_caixa_de_confirmacao(administrador):
    html = administrador.get("/administracao/usuarios").get_data(as_text=True)
    caixa = html.split('id="confirmacao-senha"')[1].split("</dialog>")[0]

    assert "Confirma o redefinir a senha desse usuário?" in caixa
    assert ">Sim</button>" in caixa and ">Não</button>" in caixa


# ---------- Redefinir


def test_so_o_administrador_redefine(cliente, outro_cliente, email_configurado):
    resposta = cliente.post("/administracao/usuarios/{}/redefinir-senha".format(outro_cliente.usuario_id))

    assert resposta.status_code == 403
    assert verify_password(SENHA, conta(outro_cliente.usuario_id).password)


def test_redefine_e_envia_o_email(administrador, outro_cliente, email_configurado):
    uniquifier = conta(outro_cliente.usuario_id).fs_uniquifier
    with mail.record_messages() as enviados:
        resposta = redefinir(administrador, outro_cliente.usuario_id)

    assert "Senha redefinida. A nova senha foi enviada para bruno@exemplo.com." in resposta.get_data(as_text=True)
    assert len(enviados) == 1
    mensagem = enviados[0]
    assert mensagem.subject == ASSUNTO_DA_NOVA_SENHA
    assert mensagem.recipients == ["bruno@exemplo.com"]
    senha = re.search(r"Nova senha: (\S+)", mensagem.body).group(1)
    assert "Endereço de acesso: http://localhost/login" in mensagem.body
    assert "Usuário: bruno@exemplo.com" in mensagem.body
    assert senha in mensagem.html and 'href="http://localhost/login"' in mensagem.html

    bruno = conta(outro_cliente.usuario_id)
    assert verify_password(senha, bruno.password)
    assert not verify_password(SENHA, bruno.password)
    assert bruno.trocar_senha is True
    assert bruno.fs_uniquifier != uniquifier


def test_sessao_aberta_da_pessoa_deixa_de_valer(administrador, outro_cliente, email_configurado):
    assert outro_cliente.get("/").status_code == 200

    with mail.record_messages():
        redefinir(administrador, outro_cliente.usuario_id)

    resposta = outro_cliente.get("/")
    # Sem sessão, a pessoa volta à área externa.
    assert resposta.status_code == 302 and resposta.headers["Location"].endswith("/projetos-e-demandas")


def test_nova_senha_pede_a_troca_no_primeiro_acesso(app, administrador, outro_cliente, email_configurado):
    with mail.record_messages() as enviados:
        redefinir(administrador, outro_cliente.usuario_id)
    senha = re.search(r"Nova senha: (\S+)", enviados[0].body).group(1)

    cliente = app.test_client()
    assert cliente.post("/login", data={"email": "bruno@exemplo.com", "password": senha}).status_code == 302
    resposta = cliente.get("/")
    assert resposta.status_code == 302 and resposta.headers["Location"].endswith("/change")


def test_sem_envio_de_emails_nao_redefine(administrador, outro_cliente):
    with mail.record_messages() as enviados:
        resposta = redefinir(administrador, outro_cliente.usuario_id)

    assert "Configure o envio de e-mails em Configurações para redefinir a senha." in resposta.get_data(as_text=True)
    assert enviados == []
    assert verify_password(SENHA, conta(outro_cliente.usuario_id).password)


def test_falha_no_envio_mantem_a_senha(administrador, outro_cliente, email_configurado, monkeypatch, caplog):
    def falhar(_mensagem):
        raise OSError("SMTP fora do ar")

    monkeypatch.setattr(mail, "send", falhar)

    resposta = redefinir(administrador, outro_cliente.usuario_id)

    assert "Não foi possível enviar o e-mail. A senha não foi alterada." in resposta.get_data(as_text=True)
    bruno = conta(outro_cliente.usuario_id)
    assert verify_password(SENHA, bruno.password) and bruno.trocar_senha is False
    # A senha gerada não vai para o log.
    assert "Nova senha" not in caplog.text


def test_nao_redefine_a_propria_senha(administrador, email_configurado):
    resposta = redefinir(administrador, administrador.usuario_id)

    assert "Para trocar a sua senha, use Alterar a Senha." in resposta.get_data(as_text=True)
    assert verify_password(SENHA, conta(administrador.usuario_id).password)


def test_usuario_inexistente(administrador, email_configurado):
    assert administrador.post("/administracao/usuarios/9999/redefinir-senha").status_code == 404


def test_gerar_senha():
    senhas = {gerar_senha() for _ in range(50)}

    assert len(senhas) == 50
    for senha in senhas:
        assert re.fullmatch(r"([{0}]{{4}}-){{3}}[{0}]{{4}}".format(ALFABETO_DA_SENHA), senha)


def test_senha_gerada_passa_na_validacao_de_forca(app):
    from extensions import security

    mensagens, _ = security.password_util.validate(routes.gerar_senha(), True)
    assert mensagens is None or mensagens == []
