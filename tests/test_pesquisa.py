# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import pytest

from extensions import db
from models import (
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    ItemDaTarefa,
    Projeto,
    Tarefa,
    Usuario,
    VideoDoYoutube,
)


def quadro(cliente, **parametros):
    html = cliente.get("/", query_string=parametros).get_data(as_text=True)
    # Só o quadro: os diálogos repetem os nomes nos data-*.
    return html.split('<div class="quadro"')[-1].split("<dialog")[0] if 'class="quadro"' in html else html.split("<dialog")[0]


@pytest.fixture
def cartoes(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id, nome="Casa")
    outra = criar_projeto(cliente.usuario_id, nome="Trabalho", posicao=1)
    criar_tarefa(projeto, nome="Comprar café")
    descricao = Tarefa(nome="Ligar", projeto_id=projeto.id, posicao=1, descricao="<p>Falar com o <b>encanador</b></p>")
    local = Tarefa(nome="Consulta", projeto_id=projeto.id, posicao=2, local="Clínica São José")
    mercado = Tarefa(nome="Mercado", tipo="lista_de_tarefas", projeto_id=outra.id, itens=[ItemDaTarefa(texto="Feijão", posicao=0)])
    video = Tarefa(nome="Aula de violão", tipo="video", projeto_id=outra.id, posicao=1)
    video.video = VideoDoYoutube(endereco="https://www.youtube.com/watch?v=jNQXAC9IVRw", codigo="jNQXAC9IVRw",
                                 autor="Professor Zé", titulo="Aula de violão", informacoes_adicionais="acordes")
    db.session.add_all([descricao, local, mercado, video])
    db.session.commit()
    return projeto, outra


def test_lupa_aparece_e_a_caixa_comeca_fechada(cliente, cartoes):
    html = cliente.get("/").get_data(as_text=True)
    assert 'data-pesquisar' in html and 'aria-label="Pesquisar"' in html
    assert 'id="pesquisa" method="get"' in html
    assert 'role="search" hidden' in html


def test_lupa_fica_a_esquerda_do_botao_das_ocultas(cliente, cartoes):
    html = cliente.get("/").get_data(as_text=True)
    assert html.index("data-pesquisar") < html.index("tarefas/ocultas")


@pytest.mark.parametrize(
    "busca, esperado",
    [
        ("cafe", "Comprar café"),  # sem acento
        ("ENCANADOR", "Ligar"),  # na descrição, sem as etiquetas HTML
        ("sao jose", "Consulta"),  # no local
        ("feijão", "Mercado"),  # nos itens da lista de tarefas
        ("zé", "Aula de violão"),  # no autor do vídeo
        ("acordes", "Aula de violão"),  # nas Informações Adicionais
    ],
)
def test_pesquisa_encontra_pelos_campos_do_cartao(cliente, cartoes, busca, esperado):
    html = quadro(cliente, busca=busca)
    assert esperado in html
    outros = {"Comprar café", "Ligar", "Consulta", "Mercado", "Aula de violão"} - {esperado}
    assert not any(nome in html for nome in outros)


def test_pesquisa_esconde_os_projetos_sem_cartoes_encontrados(cliente, cartoes):
    html = quadro(cliente, busca="café")
    assert "Casa" in html and "Trabalho" not in html


def test_pesquisa_mantem_o_termo_e_mostra_o_cancelar(cliente, cartoes):
    html = cliente.get("/?busca=café").get_data(as_text=True)
    assert 'value="café"' in html
    assert 'role="search" hidden' not in html
    assert 'class="pesquisa-cancelar" href="/"' in html


def test_pesquisa_desliga_o_arrasto(cliente, cartoes):
    html = cliente.get("/?busca=café").get_data(as_text=True)
    assert "data-busca" in html
    assert "tarefa-alca" not in html.split("<dialog")[0] and "projeto-alca" not in html.split("<dialog")[0]


def test_pesquisa_sem_resultado_avisa(cliente, cartoes):
    html = cliente.get("/?busca=xyz").get_data(as_text=True)
    assert "Nenhum cartão encontrado" in html


def test_pesquisa_vazia_mostra_tudo(cliente, cartoes):
    html = quadro(cliente, busca="   ")
    assert "Comprar café" in html and "Aula de violão" in html


def test_pesquisa_respeita_as_ocultas(cliente, cartoes):
    tarefa = Tarefa.query.filter_by(nome="Comprar café").one()
    tarefa.oculta = True
    db.session.commit()
    assert "Nenhum cartão encontrado" in cliente.get("/?busca=café").get_data(as_text=True)
    cliente.post("/tarefas/ocultas")
    assert "Comprar café" in quadro(cliente, busca="café")


def test_pesquisa_nao_encontra_cartoes_de_outro_usuario(cliente, outro_cliente, cartoes):
    assert "Nenhum cartão encontrado" in outro_cliente.get("/?busca=café").get_data(as_text=True)


def test_acoes_do_cartao_voltam_para_a_pesquisa(cliente, cartoes):
    tarefa = Tarefa.query.filter_by(nome="Comprar café").one()
    html = cliente.get("/?busca=café").get_data(as_text=True)
    assert '<input type="hidden" name="busca" value="café">' in html
    resposta = cliente.post("/tarefas/{}/concluir".format(tarefa.id), data={"busca": "café"})
    assert resposta.headers["Location"] == "/?busca=caf%C3%A9"


def test_pesquisa_na_categoria_compartilhada(cliente, outro_cliente, criar_tarefa):
    ana = db.session.get(Usuario, cliente.usuario_id)
    bruno = db.session.get(Usuario, outro_cliente.usuario_id)
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=ana.id)
    grupo.membros.extend([ana, bruno])
    casa = Categoria(nome="Casa", usuario_id=ana.id)
    db.session.add_all([grupo, casa])
    db.session.flush()
    feira = Projeto(nome="Feira", usuario_id=ana.id, categoria_id=casa.id, posicao=0)
    db.session.add(feira)
    db.session.add(CompartilhamentoDeCategoria(categoria_id=casa.id, grupo_id=grupo.id, permissao="visualizar"))
    db.session.commit()
    criar_tarefa(feira, nome="Comprar frutas")
    criar_tarefa(feira, nome="Pagar luz", posicao=1)

    html = quadro(outro_cliente, categoria=casa.id, busca="frutas")
    assert "Comprar frutas" in html and "Pagar luz" not in html
