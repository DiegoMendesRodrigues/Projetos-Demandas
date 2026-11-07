# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import pytest

from extensions import db
from models import Usuario


def usuario(cliente):
    return db.session.get(Usuario, cliente.usuario_id)


def test_perfil_mostra_o_campo_com_placeholder_e_limite(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)

    assert 'placeholder="(00) 00000-0000"' in html
    assert 'maxlength="15"' in html
    assert "data-mascara-telefone" in html


def test_perfil_salva_o_telefone(cliente):
    resposta = cliente.post(
        "/perfil", data={"nome": "Ana Souza", "telefone": "(11) 91234-5678"}
    )

    assert resposta.status_code == 302
    assert usuario(cliente).telefone == "(11) 91234-5678"


def test_telefone_e_opcional_e_pode_ser_apagado(cliente):
    usuario(cliente).telefone = "(11) 91234-5678"
    db.session.commit()

    cliente.post("/perfil", data={"nome": "Ana Souza", "telefone": ""})

    assert usuario(cliente).telefone == ""


@pytest.mark.parametrize("valor", ["11912345678", "(11) 9123-45678", "(11) 91234-56789", "abc"])
def test_perfil_recusa_telefone_fora_do_formato(cliente, valor):
    resposta = cliente.post("/perfil", data={"nome": "Ana Souza", "telefone": valor})

    assert resposta.status_code == 200
    assert usuario(cliente).telefone == ""


def test_telefone_fixo_de_oito_digitos_e_aceito(cliente):
    cliente.post("/perfil", data={"nome": "Ana Souza", "telefone": "(11) 2345-6789"})

    assert usuario(cliente).telefone == "(11) 2345-6789"


def test_cadastro_aceita_telefone(app):
    resposta = app.test_client().post(
        "/register",
        data={
            "nome": "Carla Dias",
            "email": "carla@exemplo.com",
            "telefone": "(21) 99999-0000",
            "password": "senha-de-teste-123",
            "password_confirm": "senha-de-teste-123",
        },
    )

    assert resposta.status_code == 302
    assert Usuario.query.filter_by(email="carla@exemplo.com").one().telefone == "(21) 99999-0000"


def test_cadastro_sem_telefone_continua_valido(app):
    resposta = app.test_client().post(
        "/register",
        data={
            "nome": "Carla Dias",
            "email": "carla@exemplo.com",
            "password": "senha-de-teste-123",
            "password_confirm": "senha-de-teste-123",
        },
    )

    assert resposta.status_code == 302
    assert Usuario.query.filter_by(email="carla@exemplo.com").one().telefone == ""


def test_pagina_de_cadastro_tem_o_campo(app):
    html = app.test_client().get("/register").get_data(as_text=True)

    assert 'placeholder="(00) 00000-0000"' in html


def test_administrador_define_o_telefone_do_usuario(app, criar_cliente):
    admin = criar_cliente("admin@exemplo.com")
    usuario(admin).administrador = True
    db.session.commit()

    admin.post(
        "/administracao/usuarios/novo",
        data={
            "nome": "Dora Lima",
            "email": "dora@exemplo.com",
            "telefone": "(31) 98888-7777",
            "senha": "senha-de-teste-123",
            "administrador": "nao",
        },
    )
    dora = Usuario.query.filter_by(email="dora@exemplo.com").one()
    assert dora.telefone == "(31) 98888-7777"

    admin.post(
        "/administracao/usuarios/{}/editar".format(dora.id),
        data={
            "nome": "Dora Lima",
            "email": "dora@exemplo.com",
            "telefone": "",
            "administrador": "nao",
        },
    )
    db.session.refresh(dora)
    assert dora.telefone == ""
