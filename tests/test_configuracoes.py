# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import pytest
from flask_security import send_mail

from app import create_app
from extensions import db, mail
from models import ConfiguracaoEmail, Usuario
from seguranca import decifrar

DADOS = {
    "servidor": "smtp.exemplo.com",
    "porta": "587",
    "usar_tls": "sim",
    "usuario": "envio@exemplo.com",
    "senha": "senha-do-smtp",
    "email_envio": "envio@exemplo.com",
    "nome_envio": "Projetos & Demandas",
}


@pytest.fixture
def administrador(cliente):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()
    return cliente


def salvar(cliente, **campos):
    return cliente.post("/administracao/configuracoes", data=dict(DADOS, **campos))


def test_configuracoes_exige_administrador(cliente):
    assert cliente.get("/administracao/configuracoes").status_code == 403
    assert salvar(cliente).status_code == 403
    assert ConfiguracaoEmail.query.count() == 0


def test_configuracoes_exige_login(app):
    resposta = app.test_client().get("/administracao/configuracoes")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_menu_de_administracao_leva_as_configuracoes(administrador):
    cabecalho = administrador.get("/").get_data(as_text=True).split("</header>")[0]

    assert 'href="/administracao/configuracoes"' in cabecalho


def test_formulario_tem_os_campos_e_as_opcoes(administrador):
    html = administrador.get("/administracao/configuracoes").get_data(as_text=True)

    for rotulo in (
        "Servidor SMTP", "Porta utilizada no Servidor SMTP", "Utilizar TLS na Autenticação",
        "Usuário", "Senha", "E-mail Usado no Envio", "Nome Usado no Envio",
    ):
        assert ">{}</label>".format(rotulo) in html
    porta = html.split('id="porta"')[1].split("</select>")[0]
    assert [valor for valor in ("25", "465", "587", "2525") if 'value="{}"'.format(valor) in porta] == [
        "25", "465", "587", "2525"
    ]
    assert 'value="sim">Sim' in html and 'value="nao">Não' in html
    assert html.count('maxlength="200"') == 5
    assert 'type="password"' in html
    acoes = html.split('class="perfil-acoes"')[1].split("</div>")[0]
    assert ">Cancelar</a>" in acoes and ">Salvar</button>" in acoes


def test_salvar_guarda_as_configuracoes(app, administrador):
    resposta = salvar(administrador)

    assert resposta.status_code == 302
    salva = db.session.get(ConfiguracaoEmail, 1)
    assert (salva.servidor, salva.porta, salva.usar_tls) == ("smtp.exemplo.com", 587, True)
    assert salva.usuario == "envio@exemplo.com"
    # A senha fica cifrada no banco, com a chave derivada da SECRET_KEY.
    assert "senha-do-smtp" not in salva.senha
    assert decifrar(salva.senha, app.config["SECRET_KEY"]) == "senha-do-smtp"
    assert (salva.email_envio, salva.nome_envio) == ("envio@exemplo.com", "Projetos & Demandas")


def test_salvar_passa_a_valer_sem_reiniciar(app, administrador):
    salvar(administrador, porta="465", nome_envio="Equipe")

    estado = app.extensions["mail"]
    assert (estado.server, estado.port, estado.username, estado.password) == (
        "smtp.exemplo.com", 465, "envio@exemplo.com", "senha-do-smtp"
    )
    assert (estado.use_ssl, estado.use_tls) == (True, False)
    assert app.config["SECURITY_EMAIL_SENDER"] == ("Equipe", "envio@exemplo.com")

    with mail.record_messages() as enviados:
        with app.test_request_context():
            send_mail("Assunto", "ana@exemplo.com", "security/email/reset_notice", user=None)
    assert enviados[0].sender == "Equipe <envio@exemplo.com>"


@pytest.mark.parametrize(
    "porta, tls, ssl, starttls",
    [("587", "sim", False, True), ("587", "nao", False, False), ("465", "nao", True, False), ("2525", "sim", False, True)],
)
def test_seguranca_da_conexao(app, administrador, porta, tls, ssl, starttls):
    salvar(administrador, porta=porta, usar_tls=tls)

    assert (app.config["MAIL_USE_SSL"], app.config["MAIL_USE_TLS"]) == (ssl, starttls)


def test_senha_em_branco_mantem_a_salva_e_nao_aparece_na_pagina(app, administrador):
    salvar(administrador)

    salvar(administrador, senha="", servidor="smtp.outro.com")

    salva = db.session.get(ConfiguracaoEmail, 1)
    assert salva.servidor == "smtp.outro.com"
    assert decifrar(salva.senha, app.config["SECRET_KEY"]) == "senha-do-smtp"
    html = administrador.get("/administracao/configuracoes").get_data(as_text=True)
    assert "senha-do-smtp" not in html
    assert 'value="smtp.outro.com"' in html
    assert "Deixe em branco para manter a senha atual." in html


def test_formulario_comeca_vazio_sem_configuracao_salva(administrador):
    html = administrador.get("/administracao/configuracoes").get_data(as_text=True)

    assert 'id="servidor" maxlength="200" name="servidor" required type="text" value=""' in html
    assert "Deixe em branco para manter a senha atual." not in html


def test_primeiro_salvamento_avisa_que_e_preciso_reiniciar(administrador):
    resposta = administrador.post(
        "/administracao/configuracoes", data=DADOS, follow_redirects=True
    )

    assert (
        "Reinicie a aplicação para ativar a recuperação de senha e a confirmação do e-mail."
        in resposta.get_data(as_text=True)
    )


def test_senha_e_obrigatoria_quando_nao_ha_nenhuma(administrador):
    resposta = salvar(administrador, senha="")

    assert "Informe a senha." in resposta.get_data(as_text=True)
    assert ConfiguracaoEmail.query.count() == 0


@pytest.mark.parametrize(
    "campo, valor, mensagem",
    [
        ("servidor", "", "Informe o servidor SMTP."),
        ("servidor", "s" * 201, "Use no máximo 200 caracteres."),
        ("porta", "8080", "Escolha uma porta válida."),
        ("usar_tls", "talvez", "Escolha Sim ou Não."),
        ("usuario", "", "Informe o usuário."),
        ("senha", "x" * 201, "Use no máximo 200 caracteres."),
        ("email_envio", "invalido", "Informe um e-mail válido."),
        ("nome_envio", "", "Informe o nome usado no envio."),
    ],
)
def test_salvar_recusa_dados_invalidos(administrador, campo, valor, mensagem):
    resposta = salvar(administrador, **{campo: valor})

    assert resposta.status_code == 200
    assert mensagem in resposta.get_data(as_text=True)
    assert ConfiguracaoEmail.query.count() == 0


def test_configuracoes_salvas_valem_ao_reiniciar(app, administrador):
    salvar(administrador, servidor="smtp.salvo.com", porta="2525")
    db.session.remove()

    reiniciada = create_app(type("ConfigReiniciada", (), dict(app.config)))

    assert reiniciada.extensions["mail"].server == "smtp.salvo.com"
    assert reiniciada.extensions["mail"].port == 2525


def test_configuracoes_em_duas_colunas_com_o_banco_acima_dos_botoes(administrador):
    html = administrador.get("/administracao/configuracoes").get_data(as_text=True)
    formulario = html.split('<form action="/administracao/configuracoes"')[1].split("</form>")[0]

    assert 'class="cartao-central perfil perfil-largo configuracoes"' in html
    colunas = formulario.split('<div class="perfil-colunas">')[1].split('<section class="configuracoes-banco"')[0]
    assert colunas.count('<div class="perfil-coluna">') == 2
    esquerda, direita = colunas.split('<div class="perfil-coluna">')[1:]
    assert 'id="servidor"' in esquerda and 'id="usuario"' in esquerda
    assert 'id="senha"' in direita and 'id="nome_envio"' in direita
    assert formulario.index("Banco de dados") < formulario.index('class="perfil-acoes"')
