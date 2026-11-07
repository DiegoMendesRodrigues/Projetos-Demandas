# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import pytest
from flask_security import send_mail

import config
from app import create_app
from extensions import db, mail
from models import ConfiguracaoEmail


def configuracao_salva(**campos):
    dados = {
        "id": 1,
        "servidor": "smtp.exemplo.com",
        "porta": 465,
        "usar_tls": True,
        "usuario": "envio@exemplo.com",
        "senha": "senha-do-smtp",
        "email_envio": "envio@exemplo.com",
        "nome_envio": "Projetos & Demandas",
    }
    dados.update(campos)
    return ConfiguracaoEmail(**dados)


def reiniciar(app):
    db.session.remove()
    return create_app(type("ConfigReiniciada", (), dict(app.config)))


@pytest.mark.parametrize(
    "porta, tls, ssl, starttls",
    [(465, True, True, False), (465, False, True, False), (587, True, False, True), (25, False, False, False)],
)
def test_seguranca_smtp(porta, tls, ssl, starttls):
    assert config.seguranca_smtp(porta, tls) == {"MAIL_USE_SSL": ssl, "MAIL_USE_TLS": starttls}


def test_configuracao_nao_vem_de_arquivo_nem_do_ambiente():
    assert not (config.BASE_DIR / "config_email.py").exists()
    for nome in ("MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME", "MAIL_PASSWORD", "EMAIL_ATIVO"):
        assert not hasattr(config.Config, nome)
        assert not hasattr(config, nome)


def test_sem_configuracao_salva_o_envio_fica_desligado(app):
    assert app.config["SECURITY_RECOVERABLE"] is False
    assert app.config["SECURITY_SEND_REGISTER_EMAIL"] is False
    assert app.extensions["security"].recoverable is False
    assert "Esqueci minha senha" not in app.test_client().get("/login").get_data(as_text=True)


def test_configuracao_salva_liga_o_envio_ao_iniciar(app, monkeypatch):
    monkeypatch.setenv("MAIL_SERVER", "smtp.do-ambiente.com")
    db.session.add(configuracao_salva(nome_envio="Equipe"))
    db.session.commit()

    reiniciada = reiniciar(app)

    assert reiniciada.extensions["security"].recoverable is True
    assert reiniciada.config["SECURITY_SEND_PASSWORD_CHANGE_EMAIL"] is True
    assert reiniciada.extensions["mail"].server == "smtp.exemplo.com"
    assert (reiniciada.extensions["mail"].use_ssl, reiniciada.extensions["mail"].use_tls) == (True, False)
    assert reiniciada.config["SECURITY_EMAIL_SENDER"] == ("Equipe", "envio@exemplo.com")
    assert "Esqueci minha senha" in reiniciada.test_client().get("/login").get_data(as_text=True)


def test_email_enviado_usa_o_nome_e_o_endereco_no_campo_de(app):
    app.config["SECURITY_EMAIL_SENDER"] = ("Projetos & Demandas", "atividades@exemplo.com")

    with mail.record_messages() as enviados:
        with app.test_request_context():
            send_mail("Assunto", "ana@exemplo.com", "security/email/change_notice", user=None)

    assert enviados[0].sender == "Projetos & Demandas <atividades@exemplo.com>"
    assert enviados[0].recipients == ["ana@exemplo.com"]
