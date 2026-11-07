# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from pathlib import Path

import pytest
from flask import get_template_attribute
from sqlalchemy import inspect, text

from app import atualizar_banco
from extensions import db
from models import AVATAR_PADRAO, AVATARES, Usuario


def test_perfil_exige_login(app):
    resposta = app.test_client().get("/perfil")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_perfil_exibe_nome_e_email(cliente):
    db.session.get(Usuario, cliente.usuario_id).nome = "Ana Souza"
    db.session.commit()

    html = cliente.get("/perfil").get_data(as_text=True)

    assert 'value="Ana Souza"' in html
    assert 'value="ana@exemplo.com"' in html


def test_perfil_atualiza_o_nome_apenas_do_usuario_conectado(cliente, outro_cliente):
    cliente.post("/perfil", data={"nome": "  Ana Souza  "})

    assert db.session.get(Usuario, cliente.usuario_id).nome == "Ana Souza"
    assert db.session.get(Usuario, outro_cliente.usuario_id).nome == ""


def test_salvar_perfil_leva_ao_quadro_sem_notificacao(cliente):
    resposta = cliente.post("/perfil", data={"nome": "Ana Souza"})

    assert resposta.status_code == 302
    assert resposta.headers["Location"] == "/"

    html = cliente.get("/").get_data(as_text=True)
    assert "<p>" not in html.split('id="notificacao"')[1].split("</dialog>")[0]


def test_perfil_com_erro_permanece_na_tela(cliente):
    resposta = cliente.post("/perfil", data={"nome": "Ana"})

    assert resposta.status_code == 200
    assert "<h1>Meu Perfil</h1>" in resposta.get_data(as_text=True)


def test_perfil_nao_altera_o_email(cliente):
    cliente.post("/perfil", data={"nome": "Ana Souza", "email": "outro@exemplo.com"})

    assert db.session.get(Usuario, cliente.usuario_id).email == "ana@exemplo.com"


def test_perfil_exige_nome_completo(cliente):
    resposta = cliente.post("/perfil", data={"nome": "Ana"})

    assert "Informe seu nome e sobrenome." in resposta.get_data(as_text=True)
    assert db.session.get(Usuario, cliente.usuario_id).nome == ""


def salvar_perfil(cliente, avatar=None):
    dados = {"nome": "Ana Souza"}
    if avatar:
        dados["avatar"] = avatar
    return cliente.post("/perfil", data=dados)


def test_existem_20_avatares_divididos_entre_masculinos_e_femininos():
    chaves = [chave for chave, _ in AVATARES]

    assert len(set(chaves)) == 20
    assert sum(chave.startswith("masculino") for chave in chaves) == 10
    assert sum(chave.startswith("feminino") for chave in chaves) == 10


@pytest.mark.parametrize("parte", ["sem", "curto", "comprido", "oculos", "gravata", "ideia", "direita", "esquerda"]
)
def test_avatares_incluem_cada_caracteristica_nos_dois_generos(parte):
    chaves = [chave.split("-") for chave, _ in AVATARES]

    for genero in ("masculino", "feminino"):
        assert any(genero in partes and parte in partes for partes in chaves)


def test_todos_os_avatares_sao_diferentes_e_tem_o_circulo(app):
    desenhar = get_template_attribute("_icones.html", "avatar")

    desenhos = [str(desenhar(chave)) for chave, _ in AVATARES + [(AVATAR_PADRAO, "")]]

    assert len(set(desenhos)) == 21
    assert all('class="avatar-anel"' in desenho for desenho in desenhos)


def test_cabelo_para_a_esquerda_espelha_o_cabelo_para_a_direita(app):
    desenhar = get_template_attribute("_icones.html", "avatar")

    for genero in ("masculino", "feminino"):
        assert "matrix(-1 0 0 1 48 0)" in str(desenhar(genero + "-esquerda"))
        assert "matrix" not in str(desenhar(genero + "-direita"))


def test_avatares_usam_apenas_as_cores_do_tema():
    css = Path("static/css/style.css").read_text(encoding="utf-8")

    regras = re.findall(r"\.avatar-[^{]*\{[^}]*\}", css)

    assert any("avatar-lampada" in regra for regra in regras)
    assert not any("#" in regra for regra in regras)


def test_perfil_oferece_os_20_icones(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)
    icones = html.split('<fieldset class="avatares"')[1].split("</fieldset>")[0]

    # Mais a opção da foto, escondida enquanto a pessoa não envia uma (test_foto_do_perfil.py).
    assert icones.count('type="radio"') == 21
    assert html.count('class="avatar-opcao"') == 20
    assert 'title="Feminino com cabelo curto e óculos"' in html
    assert "checked" not in html.split('<fieldset class="avatares"')[1].split("</fieldset>")[0]


def test_cabecalho_exibe_o_icone_escolhido(app, cliente):
    desenhar = get_template_attribute("_icones.html", "avatar")

    salvar_perfil(cliente, "feminino-curto-gravata")

    assert db.session.get(Usuario, cliente.usuario_id).avatar == "feminino-curto-gravata"
    cabecalho = cliente.get("/").get_data(as_text=True).split("</header>")[0]
    assert str(desenhar("feminino-curto-gravata")) in cabecalho


def test_perfil_marca_o_icone_atual(cliente):
    salvar_perfil(cliente, "masculino-curto-ideia")

    html = cliente.get("/perfil").get_data(as_text=True)
    icones = html.split('<fieldset class="avatares"')[1].split("</fieldset>")[0]

    assert icones.count("checked") == 1
    assert re.search(r'<input[^>]*checked[^>]*value="masculino-curto-ideia"', html)


def test_salvar_perfil_sem_escolher_icone_mantem_o_atual(cliente):
    salvar_perfil(cliente, "feminino-sem")

    salvar_perfil(cliente)

    assert db.session.get(Usuario, cliente.usuario_id).avatar == "feminino-sem"


def test_icone_invalido_e_recusado(cliente):
    resposta = salvar_perfil(cliente, "dragao")

    assert "Escolha um ícone válido." in resposta.get_data(as_text=True)
    assert db.session.get(Usuario, cliente.usuario_id).avatar == AVATAR_PADRAO


def test_icone_vale_apenas_para_o_usuario_conectado(cliente, outro_cliente):
    salvar_perfil(cliente, "masculino-comprido")

    assert db.session.get(Usuario, outro_cliente.usuario_id).avatar == AVATAR_PADRAO


@pytest.mark.so_sqlite
def test_atualizar_banco_adiciona_o_icone_e_preserva_o_usuario(cliente):
    db.session.execute(text("ALTER TABLE usuario DROP COLUMN avatar"))
    db.session.commit()

    atualizar_banco()

    colunas = {coluna["name"] for coluna in inspect(db.engine).get_columns("usuario")}
    assert "avatar" in colunas
    db.session.expire_all()
    usuario = db.session.get(Usuario, cliente.usuario_id)
    assert usuario.email == "ana@exemplo.com"
    assert usuario.avatar == AVATAR_PADRAO
