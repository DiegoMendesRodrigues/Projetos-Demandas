# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from datetime import timedelta
from pathlib import Path

import pytest
from flask_security import send_mail

from config import Config
from extensions import db, mail
from models import Usuario, rotulo_de_duracao
from tests.conftest import SENHA

PASTA_DOS_MODELOS = Path(__file__).resolve().parent.parent / "templates" / "security" / "email"
# Os modelos que a configuração atual pode enviar: cadastro, confirmação, troca e recuperação de senha.
MODELOS = [
    "welcome",
    "welcome_existing",
    "change_notice",
    "reset_instructions",
    "reset_notice",
    "confirmation_instructions",
]
PALAVRAS_EM_INGLES = re.compile(
    r"\b(?:welcome|hello|password|your|has been|click|link below|reset it|someone|use this)\b",
    re.I,
)
CONTEXTO = {
    "confirmation_link": "https://exemplo.com/confirmar",
    "reset_link": "https://exemplo.com/nova-senha",
    "within": "1 dia",
}


def assunto(nome):
    return getattr(Config, "SECURITY_" + nome)


def em_portugues(mensagem):
    texto = " ".join([mensagem.subject, mensagem.body or "", mensagem.html or ""])
    return not PALAVRAS_EM_INGLES.search(texto)


@pytest.fixture
def envio_de_emails(app):
    app.config.update(
        SECURITY_SEND_REGISTER_EMAIL=True,
        SECURITY_SEND_PASSWORD_CHANGE_EMAIL=True,
        SECURITY_EMAIL_SENDER=("Projetos & Demandas", "atividades@exemplo.com"),
    )
    with mail.record_messages() as enviados:
        yield enviados


def test_todos_os_modelos_ativos_tem_versao_em_portugues():
    for modelo in MODELOS:
        for extensao in (".txt", ".html"):
            assert (PASTA_DOS_MODELOS / (modelo + extensao)).exists(), modelo + extensao


@pytest.mark.parametrize("modelo", MODELOS)
def test_modelo_renderiza_em_portugues(app, envio_de_emails, cliente, modelo):
    usuario = db.session.get(Usuario, cliente.usuario_id)
    usuario.nome = "Ana Souza"

    with app.test_request_context():
        send_mail("Assunto", usuario.email, "security/email/" + modelo, user=usuario, **CONTEXTO)

    mensagem = envio_de_emails[0]
    assert "Olá, Ana Souza!" in mensagem.body
    assert "Olá, Ana Souza!" in mensagem.html
    assert "Projetos & Demandas" in mensagem.body
    assert em_portugues(mensagem), mensagem.body


@pytest.mark.parametrize(
    "nome",
    [
        nome for nome in dir(Config)
        if nome.startswith("SECURITY_") and nome.endswith("SUBJECT") or "_SUBJECT_" in nome
    ],
)
def test_assuntos_dos_emails_estao_em_portugues(nome):
    valor = getattr(Config, nome)

    assert isinstance(valor, str)
    assert valor.endswith("Projetos & Demandas")
    assert not PALAVRAS_EM_INGLES.search(valor)


def test_email_de_cadastro_em_portugues(app, envio_de_emails):
    app.test_client().post(
        "/register",
        data={
            "nome": "Maria da Silva",
            "email": "nova@exemplo.com",
            "password": "uma-senha-bem-longa-42",
            "password_confirm": "uma-senha-bem-longa-42",
        },
    )

    mensagem = envio_de_emails[0]
    assert mensagem.subject == assunto("EMAIL_SUBJECT_REGISTER")
    assert mensagem.recipients == ["nova@exemplo.com"]
    assert "Olá, Maria da Silva!" in mensagem.body
    assert em_portugues(mensagem)


def test_email_de_senha_alterada_em_portugues(cliente, envio_de_emails):
    nova_senha = "outra-senha-bem-longa-42"

    cliente.post(
        "/change",
        data={"password": SENHA, "new_password": nova_senha, "new_password_confirm": nova_senha},
    )

    mensagem = envio_de_emails[0]
    assert mensagem.subject == assunto("EMAIL_SUBJECT_PASSWORD_CHANGE_NOTICE")
    assert "A senha da sua conta no Projetos & Demandas foi alterada." in mensagem.body
    assert em_portugues(mensagem)


@pytest.mark.parametrize(
    "duracao, rotulo",
    [
        (timedelta(days=1), "1 dia"),
        (timedelta(days=2), "2 dias"),
        (timedelta(hours=1, minutes=30), "1 hora e 30 minutos"),
        (timedelta(days=1, hours=2, minutes=1), "1 dia, 2 horas e 1 minuto"),
        (timedelta(seconds=20), "menos de 1 minuto"),
    ],
)
def test_rotulo_de_duracao(duracao, rotulo):
    assert rotulo_de_duracao(duracao) == rotulo


def test_email_de_nova_senha_mostra_o_prazo_em_portugues(app, envio_de_emails, cliente):
    usuario = db.session.get(Usuario, cliente.usuario_id)

    with app.test_request_context():
        send_mail("Assunto", usuario.email, "security/email/reset_instructions", user=usuario, **CONTEXTO)

    assert "Este endereço vale por 1 dia." in envio_de_emails[0].body
