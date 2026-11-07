# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import json

import pytest

from extensions import db
from forms import ler_marcacoes
from models import LIMITE_MARCACOES, Marcacao, Tarefa, VideoDoYoutube


def marcacoes(*textos):
    return json.dumps(list(textos), ensure_ascii=False)


def textos(tarefa_id):
    return [m.texto for m in db.session.get(Tarefa, tarefa_id).marcacoes]


@pytest.fixture
def video(criar_projeto, cliente):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = Tarefa(nome="Aula", tipo="video", projeto_id=projeto.id)
    tarefa.video = VideoDoYoutube(endereco="https://www.youtube.com/watch?v=jNQXAC9IVRw", codigo="jNQXAC9IVRw",
                                  autor="Zé", titulo="Aula")
    db.session.add(tarefa)
    db.session.commit()
    return tarefa


def test_ler_marcacoes_limpa_espacos_vazias_e_repetidas():
    assert ler_marcacoes(marcacoes("  casa  ", "", "Café", "cafe", "dois   espaços")) == ["casa", "Café", "dois espaços"]


@pytest.mark.parametrize("valor", ["{", '{"a": 1}', "[1, 2]"])
def test_ler_marcacoes_recusa_json_invalido(valor):
    with pytest.raises(ValueError):
        ler_marcacoes(valor)


def test_criar_atividade_com_marcacoes(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    cliente.post("/tarefas", data={"nome": "Feira", "projeto_id": projeto.id, "marcacoes": marcacoes("casa", "urgente")})
    assert textos(Tarefa.query.one().id) == ["casa", "urgente"]


def test_editar_substitui_e_remove_as_marcacoes(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    dados = {"nome": "Tarefa", "projeto_id": tarefa.projeto_id, "prioridade": "baixa"}
    cliente.post("/tarefas/{}/editar".format(tarefa.id), data={**dados, "marcacoes": marcacoes("a", "b")})
    assert textos(tarefa.id) == ["a", "b"]
    cliente.post("/tarefas/{}/editar".format(tarefa.id), data={**dados, "marcacoes": marcacoes("b")})
    assert textos(tarefa.id) == ["b"]
    assert Marcacao.query.count() == 1


def test_lista_de_tarefas_tambem_tem_marcacoes(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    cliente.post("/tarefas", data={"nome": "Mercado", "projeto_id": projeto.id, "tipo": "lista_de_tarefas",
                                   "itens": json.dumps([{"texto": "Arroz"}]), "marcacoes": marcacoes("compras")})
    assert textos(Tarefa.query.one().id) == ["compras"]


def test_limites_das_marcacoes(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    muitas = marcacoes(*["m{}".format(i) for i in range(LIMITE_MARCACOES + 1)])
    cliente.post("/tarefas", data={"nome": "A", "projeto_id": projeto.id, "marcacoes": muitas})
    cliente.post("/tarefas", data={"nome": "B", "projeto_id": projeto.id, "marcacoes": marcacoes("x" * 41)})
    assert Tarefa.query.count() == 0


def test_cartao_e_dialogo_mostram_as_marcacoes(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.marcacoes = [Marcacao(texto="casa", posicao=0)]
    db.session.commit()
    html = cliente.get("/").get_data(as_text=True)
    assert '<ul class="tarefa-marcacoes" aria-label="Marcações">' in html and "<li>casa</li>" in html
    assert "data-marcacoes='[\"casa\"]'" in html
    assert 'id="tarefa-marcacoes"' in html and 'id="video-marcacoes"' in html


def test_campo_fica_abaixo_do_local_e_abaixo_do_video(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)
    html = cliente.get("/").get_data(as_text=True)
    assert html.index('id="tarefa-local"') < html.index('id="tarefa-marcacoes"')
    assert html.index('id="video-player"') < html.index('id="video-marcacoes"')


def test_video_salva_as_marcacoes(cliente, video):
    cliente.post("/videos/{}/editar".format(video.id), data={"informacoes_adicionais": "", "marcacoes": marcacoes("música")})
    assert textos(video.id) == ["música"]


def test_excluir_o_cartao_apaga_as_marcacoes(cliente, video):
    cliente.post("/videos/{}/editar".format(video.id), data={"marcacoes": marcacoes("a")})
    cliente.post("/tarefas/{}/excluir".format(video.id))
    assert Marcacao.query.count() == 0


def test_pesquisa_encontra_pelas_marcacoes(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    com = criar_tarefa(projeto, nome="Com marcação")
    criar_tarefa(projeto, nome="Sem marcação", posicao=1)
    com.marcacoes = [Marcacao(texto="Urgência", posicao=0)]
    db.session.commit()
    html = cliente.get("/?busca=urgencia").get_data(as_text=True).split("<dialog")[0]
    assert "Com marcação" in html and "Sem marcação" not in html


def test_outro_usuario_nao_altera_as_marcacoes(cliente, outro_cliente, video):
    resposta = outro_cliente.post("/videos/{}/editar".format(video.id), data={"marcacoes": marcacoes("x")})
    assert resposta.status_code == 404
    assert textos(video.id) == []
