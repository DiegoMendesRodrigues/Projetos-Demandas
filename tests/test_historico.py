# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Histórico e comentários do cartão (EventoDaTarefa)."""
from datetime import datetime
from unittest.mock import patch

import pytest

from extensions import db
from models import (
    TAMANHO_DO_COMENTARIO,
    Categoria,
    CompartilhamentoDeCategoria,
    EventoDaTarefa,
    GrupoDeUsuarios,
    Projeto,
    Tarefa,
    Usuario,
)

MOMENTO = datetime(2026, 11, 6, 10, 30)


def tipos(tarefa):
    return [evento.tipo for evento in db.session.get(Tarefa, tarefa.id).eventos]


@pytest.fixture
def cenario(cliente, outro_cliente):
    """Ana (cliente) é dona de Casa, compartilhada com Bruno (outro_cliente)."""
    ana = db.session.get(Usuario, cliente.usuario_id)
    bruno = db.session.get(Usuario, outro_cliente.usuario_id)
    ana.nome, bruno.nome = "Ana", "Bruno"
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=ana.id)
    grupo.membros.extend([ana, bruno])
    casa = Categoria(nome="Casa", usuario_id=ana.id)
    db.session.add_all([grupo, casa])
    db.session.flush()
    a_fazer = Projeto(nome="A fazer", usuario_id=ana.id, categoria_id=casa.id, posicao=0)
    feito = Projeto(nome="Feito", usuario_id=ana.id, categoria_id=casa.id, posicao=1)
    compartilhamento = CompartilhamentoDeCategoria(categoria_id=casa.id, grupo_id=grupo.id, permissao="editar")
    db.session.add_all([a_fazer, feito, compartilhamento])
    db.session.commit()
    tarefa = Tarefa(nome="Feira", projeto_id=a_fazer.id, previsao_execucao=datetime(2026, 11, 9, 8, 0))
    db.session.add(tarefa)
    db.session.commit()
    return ana, bruno, a_fazer, feito, tarefa, compartilhamento


def historico(cliente, tarefa):
    resposta = cliente.get(f"/tarefas/{tarefa.id}/historico")
    assert resposta.status_code == 200
    return resposta.get_data(as_text=True)


# ---------- Registro das ações


def test_criar_registra(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    cliente.post("/tarefas", data={"nome": "Pagar", "prioridade": "baixa", "projeto_id": projeto.id})
    tarefa = Tarefa.query.one()
    assert tipos(tarefa) == ["criou"]
    assert tarefa.eventos[0].usuario_id == cliente.usuario_id


def test_editar_registra(cliente, cenario):
    _, _, a_fazer, _, tarefa, _ = cenario
    cliente.post(f"/tarefas/{tarefa.id}/editar", data={"nome": "Mercado", "prioridade": "alta", "projeto_id": a_fazer.id})
    assert tipos(tarefa) == ["alterou"]


def test_concluir_e_reabrir_registram(cliente, cenario):
    *_, tarefa, _ = cenario
    with patch("routes.agora", return_value=MOMENTO):
        cliente.post(f"/tarefas/{tarefa.id}/concluir")
    cliente.post(f"/tarefas/{tarefa.id}/concluir")
    assert tipos(tarefa) == ["reabriu", "concluiu"]


def test_ocultar_e_reexibir_registram(cliente, cenario):
    *_, tarefa, _ = cenario
    cliente.post(f"/tarefas/{tarefa.id}/ocultar")
    cliente.post(f"/tarefas/{tarefa.id}/ocultar")
    assert tipos(tarefa) == ["reexibiu", "ocultou"]


def test_mover_de_projeto_registra_e_reordenar_nao(outro_cliente, cenario):
    _, _, a_fazer, feito, tarefa, _ = cenario
    outro_cliente.post(f"/api/tarefas/{tarefa.id}/mover", json={"projeto_id": a_fazer.id, "posicao": 0})
    assert tipos(tarefa) == []
    outro_cliente.post(f"/api/tarefas/{tarefa.id}/mover", json={"projeto_id": feito.id, "posicao": 0})
    evento = db.session.get(Tarefa, tarefa.id).eventos[0]
    assert (evento.tipo, evento.descricao, evento.usuario_id) == ("moveu", "moveu para o projeto Feito", outro_cliente.usuario_id)


def test_responsavel_registra_so_quando_muda(cliente, cenario):
    _, bruno, *_ = cenario
    tarefa = cenario[4]
    cliente.post(f"/tarefas/{tarefa.id}/responsavel", data={"responsavel_id": bruno.id})
    cliente.post(f"/tarefas/{tarefa.id}/responsavel", data={"responsavel_id": bruno.id})
    cliente.post(f"/tarefas/{tarefa.id}/responsavel", data={})
    eventos = db.session.get(Tarefa, tarefa.id).eventos
    assert [evento.descricao for evento in eventos] == ["removeu o responsável", "definiu Bruno como responsável"]


def test_calendario_registra_a_nova_previsao(cliente, cenario):
    *_, tarefa, _ = cenario
    cliente.post(f"/api/tarefas/{tarefa.id}/previsao", json={"data": "2026-11-12"})
    assert db.session.get(Tarefa, tarefa.id).eventos[0].descricao == "mudou a Previsão de Execução para 12/11/2026 08:00"


def test_lista_de_tarefas_completa_registra_a_conclusao(cliente, cenario):
    _, _, a_fazer, *_ = cenario
    cliente.post("/tarefas", data={
        "nome": "Mudança", "prioridade": "baixa", "projeto_id": a_fazer.id, "tipo": "lista_de_tarefas",
        "itens": '[{"texto": "Caixas", "concluido": true}]',
    })
    tarefa = Tarefa.query.filter_by(nome="Mudança").one()
    # Os dois têm o mesmo momento: o mais novo (concluiu) vem primeiro pelo id.
    assert tipos(tarefa) == ["concluiu", "criou"]


# ---------- Ver o histórico


def test_historico_mostra_quem_fez_o_que(cliente, outro_cliente, cenario):
    *_, feito, tarefa, _ = cenario
    with patch("routes.agora", return_value=MOMENTO):
        outro_cliente.post(f"/api/tarefas/{tarefa.id}/mover", json={"projeto_id": feito.id, "posicao": 0})
    html = historico(cliente, tarefa)
    assert "<strong>Bruno</strong>" in html and "moveu para o projeto Feito" in html
    assert "06/11/2026 às 10:30" in html
    assert '<p class="historico-nome">Feira</p>' in html


def test_historico_vazio(cliente, cenario):
    *_, tarefa, _ = cenario
    assert "Nada registrado ainda" in historico(cliente, tarefa)


def test_quem_so_visualiza_ve_mas_nao_comenta(outro_cliente, cenario):
    *_, tarefa, compartilhamento = cenario
    compartilhamento.permissao = "visualizar"
    db.session.commit()
    assert "data-comentar" not in historico(outro_cliente, tarefa)
    resposta = outro_cliente.post(f"/api/tarefas/{tarefa.id}/comentarios", json={"texto": "Oi"})
    assert resposta.status_code == 404


def test_quem_nao_tem_acesso_nao_ve(app, cenario, criar_cliente):
    *_, tarefa, _ = cenario
    estranho = criar_cliente("estranho@exemplo.com")
    assert estranho.get(f"/tarefas/{tarefa.id}/historico").status_code == 404


def test_cartao_leva_o_endereco_do_historico(cliente, cenario):
    *_, tarefa, _ = cenario
    html = cliente.get("/").get_data(as_text=True)
    assert f'data-url-historico="/tarefas/{tarefa.id}/historico"' in html
    assert html.count("data-abrir-historico hidden") == 2


# ---------- Comentários


def test_comentar(outro_cliente, cliente, cenario):
    *_, tarefa, _ = cenario
    with patch("routes.agora", return_value=MOMENTO):
        resposta = outro_cliente.post(f"/api/tarefas/{tarefa.id}/comentarios", json={"texto": "  Já comprei o pão.\nFalta o leite.  "})
    assert resposta.status_code == 200
    assert "Já comprei o pão.\nFalta o leite.</p>" in resposta.get_data(as_text=True)
    evento = db.session.get(Tarefa, tarefa.id).eventos[0]
    assert (evento.tipo, evento.texto, evento.usuario_id) == ("comentario", "Já comprei o pão.\nFalta o leite.", outro_cliente.usuario_id)
    assert "<strong>Bruno</strong>" in historico(cliente, tarefa)


def test_comentario_e_escapado(cliente, cenario):
    *_, tarefa, _ = cenario
    html = cliente.post(f"/api/tarefas/{tarefa.id}/comentarios", json={"texto": "<script>alert(1)</script>"}).get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("corpo", [None, {}, {"texto": "   "}, {"texto": 5}, {"texto": "x" * (TAMANHO_DO_COMENTARIO + 1)}])
def test_comentario_invalido(cliente, cenario, corpo):
    *_, tarefa, _ = cenario
    resposta = cliente.post(f"/api/tarefas/{tarefa.id}/comentarios", json=corpo)
    assert resposta.status_code == 400 and resposta.get_json()["erro"]
    assert EventoDaTarefa.query.count() == 0


# ---------- Exclusões


def test_excluir_o_cartao_apaga_o_historico(cliente, cenario):
    *_, tarefa, _ = cenario
    cliente.post(f"/api/tarefas/{tarefa.id}/comentarios", json={"texto": "Oi"})
    cliente.post(f"/tarefas/{tarefa.id}/excluir")
    assert EventoDaTarefa.query.count() == 0


def test_conta_excluida_continua_no_historico(app, cliente, outro_cliente, cenario, criar_cliente):
    *_, tarefa, _ = cenario
    outro_cliente.post(f"/api/tarefas/{tarefa.id}/comentarios", json={"texto": "Oi"})
    administrador = db.session.get(Usuario, cliente.usuario_id)
    administrador.administrador = True
    db.session.commit()
    cliente.post(f"/administracao/usuarios/{outro_cliente.usuario_id}/excluir")
    assert db.session.get(Usuario, outro_cliente.usuario_id) is None
    evento = EventoDaTarefa.query.one()
    assert evento.usuario_id is None
    assert "<strong>Conta excluída</strong>" in historico(cliente, tarefa)


# ---------- Interface


def test_botao_do_historico_some_e_continua_ligado_no_modo_leitura():
    with open("static/css/style.css", encoding="utf-8") as arquivo:
        assert ".dialogo-acoes .botao-historico[hidden] {\n  display: none;" in arquivo.read()
    with open("static/js/app.js", encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    leitura = codigo[codigo.index("function definirSomenteLeitura"):]
    assert ":not([data-abrir-historico])" in leitura[:leitura.index("}")]
