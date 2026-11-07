# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import inspect, text

from app import atualizar_banco
from extensions import db
from models import Tarefa

MOMENTO = datetime(2026, 11, 4, 15, 30)


def test_concluir_guarda_data_e_hora_e_oculta(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))

    with patch("routes.agora", return_value=MOMENTO):
        resposta = cliente.post("/tarefas/{}/concluir".format(tarefa.id))

    assert resposta.status_code == 302
    tarefa = db.session.get(Tarefa, tarefa.id)
    assert tarefa.concluida_em == MOMENTO
    assert tarefa.oculta is True


def test_desmarcar_como_concluida_apaga_a_data_e_reexibe(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    cliente.post("/tarefas/{}/concluir".format(tarefa.id))

    cliente.post("/tarefas/{}/concluir".format(tarefa.id))

    tarefa = db.session.get(Tarefa, tarefa.id)
    assert tarefa.concluida_em is None
    assert tarefa.oculta is False


def test_desmarcar_lista_de_tarefas_concluida_apaga_a_data_e_reexibe(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.tipo = "lista_de_tarefas"
    tarefa.concluida_em = MOMENTO
    tarefa.oculta = True
    db.session.commit()

    cliente.post("/tarefas/{}/concluir".format(tarefa.id))

    tarefa = db.session.get(Tarefa, tarefa.id)
    assert tarefa.concluida_em is None
    assert tarefa.oculta is False


def test_concluir_atividade_de_outro_usuario_retorna_404(cliente, outro_cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))

    assert outro_cliente.post("/tarefas/{}/concluir".format(tarefa.id)).status_code == 404
    assert db.session.get(Tarefa, tarefa.id).concluida_em is None


def test_icone_de_concluida_fica_entre_excluir_e_ocultar(cliente, criar_projeto, criar_tarefa):
    criar_tarefa(criar_projeto(cliente.usuario_id), "Pagar a conta")

    html = cliente.get("/").get_data(as_text=True)

    acoes = html.split('class="tarefa-acoes"')[1].split("</article>")[0]
    excluir = acoes.index('data-dica="Excluir demanda"')
    concluir = acoes.index('data-dica="Marcar como concluída"')
    ocultar = acoes.index('data-dica="Ocultar a demanda"')
    assert excluir < concluir < ocultar


def test_cartao_concluido_mostra_a_data_quando_as_ocultas_aparecem(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.concluida_em = MOMENTO
    tarefa.oculta = True
    db.session.commit()
    cliente.post("/tarefas/ocultas")

    html = cliente.get("/").get_data(as_text=True)

    assert "Concluída em 04/11/2026 15:30" in html
    assert 'data-dica="Desmarcar como concluída"' in html


def test_atividade_concluida_nao_gera_alerta(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.previsao_execucao = datetime.now() - timedelta(days=1)
    db.session.commit()
    cliente.get("/")
    assert tarefas_atrasadas_do(cliente) == [tarefa.id]

    cliente.post("/tarefas/{}/concluir".format(tarefa.id))

    assert tarefas_atrasadas_do(cliente) == []


def tarefas_atrasadas_do(cliente):
    html = cliente.get("/").get_data(as_text=True)
    return [int(parte.split("&")[0].split('"')[0]) for parte in html.split("/?tarefa=")[1:]]


@pytest.mark.so_sqlite
def test_atualizar_banco_adiciona_a_data_de_conclusao(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    db.session.execute(text("ALTER TABLE tarefa DROP COLUMN concluida_em"))
    db.session.commit()

    atualizar_banco()

    colunas = {coluna["name"] for coluna in inspect(db.engine).get_columns("tarefa")}
    assert "concluida_em" in colunas
    db.session.expire_all()
    assert db.session.get(Tarefa, tarefa.id).concluida_em is None
