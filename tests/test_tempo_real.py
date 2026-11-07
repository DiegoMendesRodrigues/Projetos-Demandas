# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Atualização em tempo real do quadro com categoria compartilhada (GET /api/quadro/versao)."""
import re
from datetime import datetime

import pytest

from extensions import db
from models import (
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    ItemDaTarefa,
    Projeto,
    Marcacao,
    Tarefa,
    Usuario,
)


@pytest.fixture
def cenario(cliente, outro_cliente):
    """Ana (cliente) é dona de Casa, compartilhada para editar com Bruno (outro_cliente)."""
    ana = db.session.get(Usuario, cliente.usuario_id)
    bruno = db.session.get(Usuario, outro_cliente.usuario_id)
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=ana.id)
    grupo.membros.extend([ana, bruno])
    casa = Categoria(nome="Casa", usuario_id=ana.id)
    db.session.add_all([grupo, casa])
    db.session.flush()
    projeto = Projeto(nome="A fazer", usuario_id=ana.id, categoria_id=casa.id, posicao=0)
    db.session.add(projeto)
    db.session.add(CompartilhamentoDeCategoria(categoria_id=casa.id, grupo_id=grupo.id, permissao="editar"))
    db.session.commit()
    tarefa = Tarefa(nome="Feira", projeto_id=projeto.id)
    db.session.add(tarefa)
    db.session.commit()
    return casa, projeto, tarefa


def versao(cliente, categoria=None):
    consulta = f"?categoria={categoria.id}" if categoria else ""
    resposta = cliente.get("/api/quadro/versao" + consulta)
    assert resposta.status_code == 200
    return resposta.get_json()["versao"]


def atributos_do_quadro(html):
    return re.search(r'<div class="quadro" id="quadro"[^>]*>', html).group(0)


def test_versao_do_quadro_e_a_mesma_da_api(cliente, cenario):
    casa, _, _ = cenario
    html = cliente.get(f"/?categoria={casa.id}").get_data(as_text=True)
    assert f'data-versao="{versao(cliente, casa)}"' in atributos_do_quadro(html)


def test_membro_e_dono_veem_a_mesma_versao(cliente, outro_cliente, cenario):
    casa, _, _ = cenario
    assert versao(cliente, casa) == versao(outro_cliente, casa)


@pytest.mark.parametrize("mudanca", [
    "nome", "posicao", "oculta", "concluida", "previsao", "responsavel", "item", "marcacao", "projeto", "nova",
])
def test_qualquer_mudanca_troca_a_versao(cliente, outro_cliente, cenario, mudanca):
    casa, projeto, tarefa = cenario
    antes = versao(outro_cliente, casa)
    if mudanca == "nome":
        tarefa.nome = "Mercado"
    elif mudanca == "posicao":
        tarefa.posicao = 3
    elif mudanca == "oculta":
        tarefa.oculta = True
    elif mudanca == "concluida":
        tarefa.concluida_em = datetime(2026, 11, 6, 10, 0)
    elif mudanca == "previsao":
        tarefa.previsao_execucao = datetime(2026, 11, 9, 8, 0)
    elif mudanca == "responsavel":
        tarefa.responsavel_id = outro_cliente.usuario_id
    elif mudanca == "item":
        tarefa.itens.append(ItemDaTarefa(texto="Pão", posicao=0))
    elif mudanca == "marcacao":
        tarefa.marcacoes.append(Marcacao(texto="urgente", posicao=0))
    elif mudanca == "projeto":
        projeto.nome = "Fazendo"
    else:
        db.session.add(Tarefa(nome="Nova", projeto_id=projeto.id, posicao=1))
    db.session.commit()
    assert versao(outro_cliente, casa) != antes


def test_sem_mudanca_a_versao_fica_igual(cliente, cenario):
    casa, _, _ = cenario
    assert versao(cliente, casa) == versao(cliente, casa)


def test_mudanca_em_outra_categoria_nao_troca_a_versao(cliente, cenario):
    casa, _, _ = cenario
    antes = versao(cliente, casa)
    db.session.add(Projeto(nome="Trabalho", usuario_id=cliente.usuario_id, posicao=5))
    db.session.commit()
    assert versao(cliente, casa) == antes


def test_categoria_de_quem_nao_tem_acesso_da_404(app, cenario, criar_cliente):
    casa, _, _ = cenario
    estranho = criar_cliente("estranho@exemplo.com")
    assert estranho.get(f"/api/quadro/versao?categoria={casa.id}").status_code == 404


def test_versao_exige_login(app):
    assert app.test_client().get("/api/quadro/versao").status_code in (302, 401)


def test_quadro_compartilhado_consulta_a_versao(cliente, outro_cliente, cenario):
    casa, _, _ = cenario
    for quem in (cliente, outro_cliente):
        atributos = atributos_do_quadro(quem.get(f"/?categoria={casa.id}").get_data(as_text=True))
        assert f'data-url-versao="/api/quadro/versao?categoria={casa.id}"' in atributos
    # Em "Todas", o dono também acompanha, porque um dos projetos é compartilhado.
    assert 'data-url-versao="/api/quadro/versao"' in atributos_do_quadro(cliente.get("/").get_data(as_text=True))


def test_quadro_sem_compartilhamento_nao_consulta(cliente, criar_projeto, criar_tarefa):
    criar_tarefa(criar_projeto(cliente.usuario_id))
    atributos = atributos_do_quadro(cliente.get("/").get_data(as_text=True))
    assert "data-versao=" in atributos and "data-url-versao" not in atributos


def test_codigo_da_atualizacao():
    with open("static/js/app.js", encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    assert "INTERVALO_DA_VERSAO = 20000" in codigo
    assert 'document.visibilityState !== "visible"' in codigo
    assert 'document.querySelector("dialog[open]")' in codigo[codigo.index("function ocupado"):]
    # Os arrastos próprios sincronizam sem o aviso.
    assert codigo.count("sincronizarSemAviso();") == 2
    assert 'document.addEventListener("close", () => setTimeout(() => consultarVersao(true), 0), true);' in codigo
