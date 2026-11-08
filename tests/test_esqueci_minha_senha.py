# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import io
import logging
import threading

import pytest
from PIL import Image

import captcha_imagem
import seguranca
from extensions import db, mail
from models import Usuario
from seguranca import EMAILS_DE_NOVA_SENHA_POR_CONTA, limitador

MENSAGEM = (
    "Recebemos seu e-mail para recuperar a senha. Caso ele esteja cadastrado, você receberá as "
    "informações para acessar o Projetos &amp; Demandas novamente nos próximos minutos. Verifique "
    "sua pasta de Spam na sua caixa de e-mail."
)


@pytest.fixture
def email_configurado(app):
    app.config.update(MAIL_SERVER="smtp.exemplo.com", SECURITY_EMAIL_SENDER=("Projetos & Demandas", "envio@exemplo.com"))


@pytest.fixture
def ana(criar_cliente):
    cliente = criar_cliente("ana@exemplo.com")
    cliente.post("/logout")
    return db.session.get(Usuario, cliente.usuario_id)


def pedir(app, email):
    return app.test_client().post("/reset", data={"email": email}).get_data(as_text=True)


def caixa_de_notificacao(html):
    return html.split('data-notificacao-texto>')[1].split("</div>")[0]


# ---------- Link e tela


def test_link_fica_a_direita_do_criar_conta_no_login(app):
    html = app.test_client().get("/login").get_data(as_text=True)
    menu = html.split('class="menu-conta"')[1].split("</nav>")[0]

    assert '<a href="/reset">Esqueci minha senha</a>' in menu
    assert menu.index(">Criar conta</a>") < menu.index(">Esqueci minha senha</a>")


def test_tela_pede_so_o_email(app):
    html = app.test_client().get("/reset").get_data(as_text=True)
    formulario = html.split('name="forgot_password_form"')[1].split("</form>")[0]

    assert "<h1>Esqueci minha senha</h1>" in html
    assert 'name="email"' in formulario and 'value="Enviar"' in formulario
    assert 'name="password"' not in formulario
    # A própria tela não tem o link para ela mesma.
    assert '<a href="/reset">' not in html


def test_tela_usa_o_captcha(app):
    app.config["CAPTCHA_ATIVO"] = True
    html = app.test_client().get("/reset").get_data(as_text=True)

    assert 'src="/captcha.png"' in html and 'name="captcha"' in html


def test_codigo_errado_nao_envia(app, ana, email_configurado, monkeypatch):
    app.config["CAPTCHA_ATIVO"] = True
    monkeypatch.setattr(captcha_imagem, "sortear_codigo", lambda: "ABC23")
    cliente = app.test_client()
    cliente.get("/captcha.png")

    with mail.record_messages() as enviados:
        html = cliente.post("/reset", data={"email": "ana@exemplo.com", "captcha": "ERRAD"}).get_data(as_text=True)

    assert "não confere com a imagem" in html and MENSAGEM not in html
    assert enviados == []


# ---------- Resposta sempre igual


def test_email_cadastrado_recebe_as_instrucoes(app, ana, email_configurado):
    with mail.record_messages() as enviados:
        html = pedir(app, "ana@exemplo.com")

    assert MENSAGEM in html
    assert len(enviados) == 1 and enviados[0].recipients == ["ana@exemplo.com"]
    assert "/reset/" in enviados[0].body


@pytest.mark.parametrize("email", ["ninguem@exemplo.com", "abc", ""])
def test_email_sem_conta_ou_invalido_recebe_a_mesma_mensagem(app, ana, email_configurado, email):
    with mail.record_messages() as enviados:
        html = pedir(app, email)

    assert MENSAGEM in html
    assert enviados == []


def test_mensagem_fica_na_tela_e_nao_na_notificacao(app, ana, email_configurado):
    html = pedir(app, "ana@exemplo.com")

    assert '<p class="aviso-da-conta" role="status">' + MENSAGEM + "</p>" in html
    assert MENSAGEM not in caixa_de_notificacao(html)
    assert 'name="forgot_password_form"' not in html


def test_sem_envio_configurado_a_mensagem_e_a_mesma(app, ana, caplog):
    with mail.record_messages() as enviados, caplog.at_level(logging.WARNING):
        html = pedir(app, "ana@exemplo.com")

    assert MENSAGEM in html
    assert enviados == []
    assert "sem o envio de e-mails configurado" in caplog.text


def test_falha_no_smtp_nao_aparece_para_quem_pediu(app, ana, email_configurado, monkeypatch, caplog):
    def falhar(_mensagem):
        raise OSError("SMTP fora do ar")

    monkeypatch.setattr(mail, "send", falhar)

    resposta = app.test_client().post("/reset", data={"email": "ana@exemplo.com"})

    assert resposta.status_code == 200 and MENSAGEM in resposta.get_data(as_text=True)
    assert "Falha ao enviar as instruções" in caplog.text


def test_limite_de_emails_por_conta(app, ana, email_configurado):
    app.config["LIMITES_ATIVOS"] = True
    limitador.zerar()
    quantidade = EMAILS_DE_NOVA_SENHA_POR_CONTA[0]
    try:
        with mail.record_messages() as enviados:
            respostas = [pedir(app, "ana@exemplo.com") for _ in range(quantidade + 1)]
    finally:
        limitador.zerar()

    assert all(MENSAGEM in html for html in respostas)
    assert len(enviados) == quantidade


def test_envio_sai_numa_thread(monkeypatch):
    monkeypatch.undo()
    feito = threading.Event()
    principal = threading.current_thread()
    vistas = []

    def tarefa():
        vistas.append(threading.current_thread())
        feito.set()

    seguranca.em_segundo_plano(tarefa)

    assert feito.wait(5)
    assert vistas[0] is not principal


def test_outros_emails_continuam_na_hora(app, email_configurado, cliente):
    from flask_security.utils import send_mail

    usuario = db.session.get(Usuario, cliente.usuario_id)
    with app.test_request_context(), mail.record_messages() as enviados:
        send_mail("Assunto", usuario.email, "security/email/reset_notice", user=usuario)

    assert len(enviados) == 1


# ---------- Imagem do CAPTCHA


def test_imagem_do_captcha_alinha_o_botao_com_os_campos(app):
    app.config["CAPTCHA_ATIVO"] = True
    cliente = app.test_client()

    imagem = Image.open(io.BytesIO(cliente.get("/captcha.png").data))
    html = cliente.get("/login").get_data(as_text=True)

    assert imagem.size == (captcha_imagem.LARGURA, captcha_imagem.ALTURA) == (332, 70)
    assert 'width="332" height="70"' in html
