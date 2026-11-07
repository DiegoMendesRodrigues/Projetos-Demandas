# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import pytest

from extensions import db
from models import Anexo, Categoria, Projeto, Tarefa


@pytest.fixture
def dados_alheios(outro_cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(outro_cliente.usuario_id, "Projeto alheia")
    tarefa = criar_tarefa(projeto, "Tarefa alheia")
    categoria = Categoria(nome="Categoria alheia", usuario_id=outro_cliente.usuario_id)
    anexo = Anexo(nome="alheio.txt", arquivo="a" * 32, tamanho=1, tarefa_id=tarefa.id)
    db.session.add_all([categoria, anexo])
    db.session.commit()
    return {"projeto": projeto, "tarefa": tarefa, "categoria": categoria, "anexo": anexo}


def test_quadro_nao_exibe_dados_de_outro_usuario(cliente, dados_alheios):
    html = cliente.get("/").get_data(as_text=True)

    assert "Projeto alheia" not in html
    assert "Tarefa alheia" not in html
    assert "Categoria alheia" not in html


@pytest.mark.parametrize(
    "modelo, url",
    [
        ("tarefa", "/tarefas/{}/excluir"),
        ("tarefa", "/tarefas/{}/editar"),
        ("tarefa", "/tarefas/{}/ocultar"),
        ("anexo", "/anexos/{}/renomear"),
        ("anexo", "/anexos/{}/excluir"),
        ("projeto", "/projetos/{}/excluir"),
        ("projeto", "/projetos/{}/editar"),
        ("categoria", "/categorias/{}/excluir"),
        ("categoria", "/categorias/{}/editar"),
    ],
)
def test_alteracoes_em_dados_de_outro_usuario_retornam_404(
    cliente, dados_alheios, modelo, url
):
    resposta = cliente.post(url.format(dados_alheios[modelo].id), data={"nome": "Invadido"})

    assert resposta.status_code == 404


def test_download_de_anexo_de_outro_usuario_retorna_404(cliente, dados_alheios):
    resposta = cliente.get("/anexos/{}/baixar".format(dados_alheios["anexo"].id))

    assert resposta.status_code == 404


def test_filtro_por_categoria_de_outro_usuario_retorna_404(cliente, dados_alheios):
    resposta = cliente.get("/?categoria={}".format(dados_alheios["categoria"].id))

    assert resposta.status_code == 404


def test_nao_move_tarefa_de_outro_usuario(cliente, criar_projeto, dados_alheios):
    meu_projeto = criar_projeto(cliente.usuario_id)

    resposta = cliente.post(
        "/api/tarefas/{}/mover".format(dados_alheios["tarefa"].id),
        json={"projeto_id": meu_projeto.id, "posicao": 0},
    )

    assert resposta.status_code == 404


def test_nao_move_tarefa_para_projeto_de_outro_usuario(
    cliente, criar_projeto, criar_tarefa, dados_alheios
):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))

    resposta = cliente.post(
        "/api/tarefas/{}/mover".format(tarefa.id),
        json={"projeto_id": dados_alheios["projeto"].id, "posicao": 0},
    )

    assert resposta.status_code == 404
    assert db.session.get(Tarefa, tarefa.id).projeto_id != dados_alheios["projeto"].id


def test_nao_cria_tarefa_em_projeto_de_outro_usuario(cliente, dados_alheios):
    cliente.post(
        "/tarefas",
        data={
            "nome": "Invasora",
            "prioridade": "media",
            "projeto_id": dados_alheios["projeto"].id,
        },
    )

    assert Tarefa.query.filter_by(nome="Invasora").count() == 0
    assert Projeto.query.count() == 1
