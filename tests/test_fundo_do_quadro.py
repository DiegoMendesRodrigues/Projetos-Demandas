# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from pathlib import Path

import pytest
from sqlalchemy import text

from app import atualizar_banco
from extensions import db
from models import FUNDO_PADRAO, FUNDOS_DO_QUADRO, Categoria, CompartilhamentoDeCategoria, GrupoDeUsuarios, Usuario


def central(html):
    return re.search(r'<div class="central[^"]*">', html).group(0)


def test_criar_categoria_com_fundo(cliente):
    cliente.post("/categorias", data={"nome": "Casa", "icone": "casa", "fundo": "menta"})
    assert Categoria.query.one().fundo == "menta"


def test_sem_o_campo_o_fundo_e_o_padrao(cliente):
    cliente.post("/categorias", data={"nome": "Casa", "icone": "casa"})
    assert Categoria.query.one().fundo == FUNDO_PADRAO


def test_editar_o_fundo(cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)
    cliente.post(f"/categorias/{categoria.id}/editar", data={"nome": "Casa", "icone": "casa", "fundo": "por_do_sol"})
    assert db.session.get(Categoria, categoria.id).fundo == "por_do_sol"


def test_fundo_invalido_e_recusado(cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)
    cliente.post(f"/categorias/{categoria.id}/editar", data={"nome": "Outro", "icone": "casa", "fundo": "url(x)"})
    categoria = db.session.get(Categoria, categoria.id)
    assert (categoria.nome, categoria.fundo) == ("Casa", FUNDO_PADRAO)


def test_quadro_da_categoria_usa_o_fundo(cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)
    categoria.fundo = "oceano"
    db.session.commit()
    assert central(cliente.get(f"/?categoria={categoria.id}").get_data(as_text=True)) == '<div class="central fundo-oceano">'
    # "Todas" e o fundo Padrão não ganham classe.
    assert central(cliente.get("/").get_data(as_text=True)) == '<div class="central">'
    categoria.fundo = FUNDO_PADRAO
    db.session.commit()
    assert central(cliente.get(f"/?categoria={categoria.id}").get_data(as_text=True)) == '<div class="central">'


def test_membro_ve_o_fundo_da_categoria_compartilhada(cliente, outro_cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)
    categoria.fundo = "lavanda"
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=cliente.usuario_id)
    grupo.membros.extend([db.session.get(Usuario, cliente.usuario_id), db.session.get(Usuario, outro_cliente.usuario_id)])
    db.session.add(grupo)
    db.session.flush()
    db.session.add(CompartilhamentoDeCategoria(categoria_id=categoria.id, grupo_id=grupo.id, permissao="visualizar"))
    db.session.commit()
    html = outro_cliente.get(f"/?categoria={categoria.id}").get_data(as_text=True)
    assert central(html) == '<div class="central fundo-lavanda">'


def test_dialogo_oferece_os_fundos_e_o_botao_de_editar_leva_o_atual(cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)
    categoria.fundo = "areia"
    db.session.commit()
    html = cliente.get("/").get_data(as_text=True)
    dialogo = html.split('id="dialogo-categoria"')[1].split("</dialog>")[0]
    for chave, rotulo in FUNDOS_DO_QUADRO:
        assert f'class="cor-opcao fundo-opcao fundo-{chave}" data-dica="{rotulo}"' in dialogo
    assert 'data-fundo="areia"' in html


def test_todo_fundo_tem_o_desenho_no_css():
    css = Path("static/css/style.css").read_text(encoding="utf-8")
    for chave, _ in FUNDOS_DO_QUADRO:
        assert re.search(r"\.fundo-%s \{\s*--fundo-quadro:" % chave, css), chave


@pytest.mark.so_sqlite
def test_migracao_cria_a_coluna_com_o_padrao(app):
    with db.engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE categoria DROP COLUMN fundo"))
    atualizar_banco()
    colunas = {linha[1]: linha for linha in db.session.execute(text("PRAGMA table_info(categoria)"))}
    assert colunas["fundo"][4] == f"'{FUNDO_PADRAO}'"


def test_amostras_do_dialogo_vencem_a_cor_das_opcoes():
    css = Path("static/css/style.css").read_text(encoding="utf-8")
    assert re.search(r"\.dialogo \.cor-opcao\.fundo-opcao \{[^}]*background: var\(--fundo-quadro\)", css)


def test_pilulas_da_cor_do_perfil_nao_vazam_para_os_dialogos():
    css = Path("static/css/style.css").read_text(encoding="utf-8")
    assert re.search(r"^\.perfil \.cor-opcao::before \{", css, re.M)
    assert not re.search(r"^\.cor-opcao::before \{", css, re.M)
    assert not re.search(r"^\.cor-opcao:has\(input:checked\) \{\s*border-color: var\(--acento\)", css, re.M)
