# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import json

import pytest
from sqlalchemy import inspect, text

from app import atualizar_banco
from extensions import db
from forms import ler_itens
from models import LIMITE_ITENS, ItemDaTarefa, Tarefa


def itens(*textos, concluidos=()):
    return json.dumps(
        [{"texto": texto, "concluido": indice in concluidos} for indice, texto in enumerate(textos)]
    )


def criar_lista_de_tarefas(cliente, projeto, dados_dos_itens, **campos):
    dados = {
        "nome": "Mercado",
        "projeto_id": projeto.id,
        "tipo": "lista_de_tarefas",
        "itens": dados_dos_itens,
    }
    dados.update(campos)
    return cliente.post("/tarefas", data=dados, follow_redirects=True)


def test_ler_itens_descarta_tarefas_vazias_e_limpa_os_textos():
    lidos = ler_itens(json.dumps([
        {"texto": "  Arroz  ", "concluido": True},
        {"texto": "   "},
        {"texto": "Feijão", "concluido": "sim"},
        {"concluido": True},
    ]))

    assert lidos == [
        {"texto": "Arroz", "concluido": True},
        {"texto": "Feijão", "concluido": False},
    ]


@pytest.mark.parametrize("valor", ["não é json", '{"texto": "Arroz"}', '["Arroz"]'])
def test_ler_itens_recusa_dados_mal_formados(valor):
    with pytest.raises(ValueError):
        ler_itens(valor)


def test_atividade_comum_continua_sem_tarefas(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post("/tarefas", data={"nome": "Comum", "projeto_id": projeto.id, "descricao": "<p>Texto</p>"})

    tarefa = Tarefa.query.one()
    assert tarefa.tipo == "atividade"
    assert tarefa.lista_de_tarefas is False
    assert tarefa.descricao == "<p>Texto</p>"
    assert tarefa.itens == []


def test_criar_lista_de_tarefas_guarda_as_tarefas_em_ordem(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    criar_lista_de_tarefas(
        cliente, projeto, itens("Arroz", "Feijão", "Café", concluidos=(1,)),
        prioridade="alta", local="Supermercado", descricao="<p>ignorada</p>",
    )

    tarefa = Tarefa.query.one()
    assert tarefa.tipo == "lista_de_tarefas"
    assert tarefa.prioridade == "alta"
    assert tarefa.local == "Supermercado"
    assert tarefa.descricao == ""
    assert [(item.texto, item.concluido, item.posicao) for item in tarefa.itens] == [
        ("Arroz", False, 0),
        ("Feijão", True, 1),
        ("Café", False, 2),
    ]


def test_criar_lista_de_tarefas_recusa_tipo_invalido(cliente, criar_projeto):
    resposta = criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens("A"), tipo="outro")

    assert "Tipo de demanda inválido." in resposta.get_data(as_text=True)
    assert Tarefa.query.count() == 0


def test_criar_lista_de_tarefas_recusa_tarefas_demais(cliente, criar_projeto):
    textos = ["Tarefa {}".format(numero) for numero in range(LIMITE_ITENS + 1)]

    resposta = criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens(*textos))

    assert "Cada lista pode ter até {} tarefas.".format(LIMITE_ITENS) in resposta.get_data(as_text=True)
    assert Tarefa.query.count() == 0


def test_criar_lista_de_tarefas_recusa_tarefa_longa(cliente, criar_projeto):
    resposta = criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens("x" * 256))

    assert "Cada tarefa deve ter no máximo 255 caracteres." in resposta.get_data(as_text=True)
    assert Tarefa.query.count() == 0


def test_editar_lista_de_tarefas_substitui_as_tarefas_e_mantem_o_tipo(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    criar_lista_de_tarefas(cliente, projeto, itens("Arroz", "Feijão"))
    tarefa = Tarefa.query.one()

    cliente.post(
        "/tarefas/{}/editar".format(tarefa.id),
        data={"nome": "Mercado", "projeto_id": projeto.id, "tipo": "atividade", "itens": itens("Café", concluidos=(0,))},
    )

    db.session.expire_all()
    tarefa = db.session.get(Tarefa, tarefa.id)
    assert tarefa.tipo == "lista_de_tarefas"
    assert [(item.texto, item.concluido) for item in tarefa.itens] == [("Café", True)]
    assert ItemDaTarefa.query.count() == 1


def test_excluir_lista_de_tarefas_apaga_as_tarefas(cliente, criar_projeto):
    criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens("Arroz", "Feijão"))

    cliente.post("/tarefas/{}/excluir".format(Tarefa.query.one().id))

    assert ItemDaTarefa.query.count() == 0


def test_cartao_mostra_as_tarefas_e_marca_as_concluidas(cliente, criar_projeto):
    criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens("Arroz", "Feijão", concluidos=(1,)))

    html = cliente.get("/").get_data(as_text=True)

    cartao = html.split('<ul class="tarefa-itens">')[1].split("</ul>")[0]
    assert '<span class="item-texto">Arroz</span>' in cartao
    assert '<li class="item-concluido">' in cartao
    assert 'aria-label="Concluída"' in cartao and 'aria-label="Não concluída"' in cartao
    assert 'data-tipo="lista_de_tarefas"' in html
    dados = html.split("data-itens='")[1].split("'")[0]
    assert json.loads(dados) == [
        {"texto": "Arroz", "concluido": False},
        {"texto": "Feijão", "concluido": True},
    ]


def test_menu_do_mais_oferece_atividade_e_lista_de_tarefas(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    menu = html.split('id="menu-criar-{}"'.format(projeto.id))[1].split("</div>")[0]
    atividade = menu.index(">Cartão - Demanda</button>")
    lista_de_tarefas = menu.index(">Cartão - Lista de Tarefas</button>")
    assert atividade < lista_de_tarefas
    assert 'data-tipo="lista_de_tarefas"' in menu


def test_dialogo_tem_o_campo_de_tarefas(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    assert '<div class="tarefa-campo-itens" id="painel-tarefas" data-secao="tarefas" hidden>' in html
    assert 'id="tarefa-itens-dados"' in html
    assert 'id="tarefa-tipo"' in html
    assert "Adicionar tarefa" in html


@pytest.mark.so_sqlite
def test_atualizar_banco_adiciona_o_tipo_como_atividade(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    db.session.execute(text("ALTER TABLE tarefa DROP COLUMN tipo"))
    db.session.commit()

    atualizar_banco()

    colunas = {coluna["name"] for coluna in inspect(db.engine).get_columns("tarefa")}
    assert "tipo" in colunas
    db.session.expire_all()
    assert db.session.get(Tarefa, tarefa.id).tipo == "atividade"


@pytest.mark.parametrize(
    "quantidade, aviso",
    [(3, None), (4, "+ 1 tarefa"), (6, "+ 3 tarefas")],
)
def test_cartao_mostra_ate_3_tarefas_e_avisa_das_demais(cliente, criar_projeto, quantidade, aviso):
    textos = ["Tarefa {}".format(numero) for numero in range(1, quantidade + 1)]
    criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens(*textos))

    html = cliente.get("/").get_data(as_text=True)

    cartao = html.split('<ul class="tarefa-itens">')[1].split("</ul>")[0]
    assert cartao.count('class="item-texto"') == 3
    assert '<span class="item-texto">Tarefa 3</span>' in cartao
    assert "Tarefa 4<" not in cartao
    if aviso:
        assert '<li class="itens-a-mais">{}</li>'.format(aviso) in cartao
    else:
        assert "itens-a-mais" not in cartao
    assert len(json.loads(html.split("data-itens='")[1].split("'")[0])) == quantidade


def test_tarefa_do_dialogo_tem_alca_para_arrastar(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    modelo = html.split('<template id="modelo-item">')[1].split("</template>")[0]
    assert modelo.index('class="item-alca"') < modelo.index('class="item-marcador"')


def test_salvar_projeto_com_todas_as_tarefas_concluidas_conclui_o_projeto(cliente, criar_projeto):
    criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens("Arroz", "Feijão", concluidos=(0, 1)))

    tarefa = Tarefa.query.one()
    assert tarefa.concluida_em is not None
    assert tarefa.oculta is True


def test_projeto_sem_tarefas_nao_e_concluida_sozinha(cliente, criar_projeto):
    criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens())

    assert Tarefa.query.one().concluida_em is None


def test_dialogo_tem_o_botao_de_ordem_alfabetica(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    topo = html.split('<div class="itens-topo">')[1].split("</div>")[0]
    assert "data-ordenar-itens" in topo
    assert 'data-dica="Ordenar em ordem alfabética"' in topo


def test_tarefas_do_cartao_nao_podem_ser_marcadas(cliente, criar_projeto):
    criar_lista_de_tarefas(cliente, criar_projeto(cliente.usuario_id), itens("Arroz"))
    item = ItemDaTarefa.query.one()

    cartao = cliente.get("/").get_data(as_text=True).split('<ul class="tarefa-itens">')[1].split("</ul>")[0]

    assert "<button" not in cartao and "data-concluir-item" not in cartao
    resposta = cliente.post("/api/itens/{}/concluir".format(item.id), json={"concluido": True})
    assert resposta.status_code == 404
    assert db.session.get(ItemDaTarefa, item.id).concluido is False


def test_arquivos_aparecem_sem_link_nas_listas_de_tarefas_e_nas_atividades(cliente, criar_projeto, criar_tarefa):
    from models import Anexo

    projeto = criar_projeto(cliente.usuario_id)
    criar_lista_de_tarefas(cliente, projeto, itens("Arroz"))
    atividade = criar_tarefa(projeto, nome="Demanda comum", posicao=1)
    for numero, tarefa in enumerate((Tarefa.query.filter_by(tipo="lista_de_tarefas").one(), atividade)):
        db.session.add(Anexo(nome="nota{}.pdf".format(numero), arquivo="a" * 31 + str(numero), tamanho=10, tarefa_id=tarefa.id))
    db.session.commit()
    da_projeto, da_atividade = Anexo.query.order_by(Anexo.id)

    html = cliente.get("/").get_data(as_text=True)

    for anexo in (da_projeto, da_atividade):
        assert '<span class="anexo-nome">' in html and anexo.nome in html
        assert 'href="/anexos/{}/baixar"'.format(anexo.id) not in html
        assert 'data-url-baixar="/anexos/{}/baixar"'.format(anexo.id) in html  # o diálogo continua com o download
