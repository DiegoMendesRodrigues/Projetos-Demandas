# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app import atualizar_banco
from extensions import db
from models import Categoria, Projeto, Tarefa, Usuario
from routes import agora


def ordem(projeto):
    tarefas = Tarefa.query.filter_by(projeto_id=projeto.id).order_by(Tarefa.posicao)
    return [tarefa.nome for tarefa in tarefas]


def mover(cliente, tarefa, projeto, posicao):
    return cliente.post(
        "/api/tarefas/{}/mover".format(tarefa.id),
        json={"projeto_id": projeto.id, "posicao": posicao},
    )


def test_criar_tarefa_com_todos_os_campos(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post(
        "/tarefas",
        data={
            "nome": "Pagar conta",
            "prioridade": "alta",
            "previsao_execucao": "2026-12-25T14:30",
            "descricao": "Conta de luz",
            "local": "Banco do bairro",
            "projeto_id": projeto.id,
        },
    )

    tarefa = Tarefa.query.one()
    assert tarefa.nome == "Pagar conta"
    assert tarefa.prioridade == "alta"
    assert tarefa.previsao_execucao == datetime(2026, 12, 25, 14, 30)
    assert tarefa.descricao == "Conta de luz"
    assert tarefa.local == "Banco do bairro"
    assert tarefa.projeto_id == projeto.id


def test_criar_tarefa_sem_nome_e_recusado(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post("/tarefas", data={"nome": "", "prioridade": "alta", "projeto_id": projeto.id})

    assert Tarefa.query.count() == 0


def test_criar_tarefa_com_prioridade_invalida_e_recusado(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post(
        "/tarefas",
        data={"nome": "Tarefa", "prioridade": "urgente", "projeto_id": projeto.id},
    )

    assert Tarefa.query.count() == 0


def test_nova_tarefa_entra_no_fim_do_projeto(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    criar_tarefa(projeto, "Existente", 4)

    cliente.post(
        "/tarefas",
        data={"nome": "Nova", "prioridade": "media", "projeto_id": projeto.id},
    )

    assert ordem(projeto) == ["Existente", "Nova"]


def test_editar_tarefa_nao_troca_de_projeto(cliente, criar_projeto, criar_tarefa):
    origem = criar_projeto(cliente.usuario_id, "Origem")
    destino = criar_projeto(cliente.usuario_id, "Destino", 1)
    criar_tarefa(destino, "Já estava", 0)
    tarefa = criar_tarefa(origem, "Antiga")

    cliente.post(
        "/tarefas/{}/editar".format(tarefa.id),
        data={"nome": "Editada", "prioridade": "baixa", "projeto_id": destino.id},
    )

    assert ordem(origem) == ["Editada"]
    assert ordem(destino) == ["Já estava"]


def test_editar_tarefa_altera_o_local(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto)

    cliente.post(
        "/tarefas/{}/editar".format(tarefa.id),
        data={
            "nome": "Tarefa",
            "prioridade": "baixa",
            "local": "  Escritório  ",
            "projeto_id": projeto.id,
        },
    )

    assert db.session.get(Tarefa, tarefa.id).local == "Escritório"


def test_local_acima_do_limite_e_recusado(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post(
        "/tarefas",
        data={
            "nome": "Tarefa",
            "prioridade": "baixa",
            "local": "x" * 121,
            "projeto_id": projeto.id,
        },
    )

    assert Tarefa.query.count() == 0


def test_tarefa_sem_local_e_sem_prioridade_informada_usa_os_padroes(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post("/tarefas", data={"nome": "Tarefa", "projeto_id": projeto.id})

    tarefa = Tarefa.query.one()
    assert tarefa.prioridade == "baixa"
    assert tarefa.local == ""


def test_formulario_inicia_com_prioridade_baixa_e_local_abaixo_da_descricao(
    cliente, criar_projeto
):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    assert re.search(r'<option selected value="baixa">', html)
    assert "Local da demanda" in html


def test_descricao_fica_sozinha_na_coluna_direita_do_dialogo_da_tarefa(
    cliente, criar_projeto
):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    dialogo = html.split('id="dialogo-tarefa"')[1].split("</dialog>")[0]
    colunas = dialogo.split('class="colunas-da-tarefa"')[1]
    esquerda, direita = colunas.split('class="tarefa-campo-descricao"')

    assert 'id="tarefa-descricao"' in direita
    assert 'id="tarefa-editor"' in direita
    for campo in ("tarefa-nome", "tarefa-prioridade", "tarefa-previsao", "tarefa-local", "tarefa-arquivos"):
        assert 'id="{}"'.format(campo) in esquerda
        assert 'id="{}"'.format(campo) not in direita


def test_formulario_da_tarefa_nao_exibe_o_campo_projeto(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id, "Compras")

    html = cliente.get("/").get_data(as_text=True)
    dialogo = html.split('id="dialogo-tarefa"')[1].split("</dialog>")[0]

    assert '<input type="hidden" id="tarefa-projeto" name="projeto_id">' in dialogo
    assert "<select" in dialogo
    assert 'id="tarefa-prioridade"' in dialogo
    assert dialogo.count("<select") == 1
    assert 'for="tarefa-projeto"' not in dialogo


@pytest.mark.parametrize(
    "prioridade, rotulo",
    [("baixa", "Baixa"), ("media", "Média"), ("alta", "Alta")],
)
def test_cartao_mostra_a_prioridade_pela_borda_e_nao_por_texto(
    cliente, criar_projeto, criar_tarefa, prioridade, rotulo
):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.prioridade = prioridade
    db.session.commit()

    html = cliente.get("/").get_data(as_text=True)

    assert 'class="tarefa prioridade-{}"'.format(prioridade) in html
    assert 'title="Prioridade {}"'.format(rotulo) in html
    assert '<span class="prioridade' not in html


def test_cartao_exibe_o_local_somente_quando_informado(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    criar_tarefa(projeto)

    assert '<p class="tarefa-local">' not in cliente.get("/").get_data(as_text=True)

    criar_tarefa(projeto, "Com local").local = "Mercado"
    db.session.commit()
    html = cliente.get("/").get_data(as_text=True)

    assert '<p class="tarefa-local">' in html
    assert "<span>Mercado</span>" in html
    assert 'data-local="Mercado"' in html


@pytest.mark.so_sqlite
def test_atualizar_banco_adiciona_o_local_e_preserva_as_tarefas(
    cliente, criar_projeto, criar_tarefa
):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id), "Antiga")
    tarefa_id = tarefa.id
    db.session.commit()
    db.session.execute(text("ALTER TABLE tarefa DROP COLUMN local"))
    db.session.commit()

    atualizar_banco()

    db.session.expire_all()
    preservada = db.session.get(Tarefa, tarefa_id)
    assert preservada.nome == "Antiga"
    assert preservada.local == ""


def ocultar(cliente, tarefa):
    return cliente.post("/tarefas/{}/ocultar".format(tarefa.id), follow_redirects=True)


def alternar_ocultas(cliente, dados=None):
    return cliente.post("/tarefas/ocultas", data=dados, follow_redirects=True)


def test_tarefa_tem_icone_de_ocultar_abaixo_da_exclusao(cliente, criar_projeto, criar_tarefa):
    criar_tarefa(criar_projeto(cliente.usuario_id))

    html = cliente.get("/").get_data(as_text=True)
    acoes = html.split('<div class="tarefa-acoes">')[1]

    assert 'data-dica="Ocultar a demanda"' in acoes
    assert acoes.index('data-dica="Excluir demanda"') < acoes.index('data-dica="Ocultar a demanda"')


def test_ocultar_tarefa_a_retira_do_quadro_sem_excluir(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto, "Escondida", 0)
    criar_tarefa(projeto, "Visível", 1)

    resposta = ocultar(cliente, tarefa)

    html = resposta.get_data(as_text=True)
    assert 'data-nome="Escondida"' not in html
    assert 'data-nome="Visível"' in html
    assert '<span class="contador" data-contador>1</span>' in html
    assert db.session.get(Tarefa, tarefa.id).oculta is True
    assert "<p>" not in caixa_de_notificacao(resposta)


def test_botao_de_ocultas_fica_a_esquerda_de_criar_projeto(cliente):
    html = cliente.get("/").get_data(as_text=True)

    assert 'aria-pressed="false"' in html
    assert html.index('data-dica="Exibir as demandas ocultas"') < html.index("data-novo-projeto")


def test_exibir_ocultas_mostra_a_tarefa_e_permite_reexibir(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id), "Escondida")
    ocultar(cliente, tarefa)

    resposta = alternar_ocultas(cliente)

    html = resposta.get_data(as_text=True)
    assert 'data-nome="Escondida"' in html
    assert "tarefa-oculta" in html
    assert 'aria-pressed="true"' in html
    assert 'data-dica="Não exibir as demandas ocultas"' in html
    assert 'data-dica="Reexibir a demanda"' in html

    ocultar(cliente, tarefa)
    html = alternar_ocultas(cliente).get_data(as_text=True)

    assert db.session.get(Tarefa, tarefa.id).oculta is False
    assert 'data-nome="Escondida"' in html
    assert "tarefa-oculta" not in html


def test_exibir_ocultas_permanece_e_vale_so_para_o_usuario(cliente, outro_cliente):
    alternar_ocultas(cliente)

    assert 'aria-pressed="true"' in cliente.get("/").get_data(as_text=True)
    assert 'aria-pressed="false"' in outro_cliente.get("/").get_data(as_text=True)


def test_alternar_ocultas_mantem_a_categoria_selecionada(cliente):
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add(categoria)
    db.session.commit()

    resposta = cliente.post("/tarefas/ocultas", data={"categoria": categoria.id})

    assert resposta.headers["Location"].endswith("/?categoria={}".format(categoria.id))


def test_projeto_so_com_ocultas_nao_pode_ser_excluida(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    ocultar(cliente, criar_tarefa(projeto))

    html = cliente.get("/").get_data(as_text=True)
    excluir = re.search(r"<button[^>]*data-excluir-projeto[^>]*>", html, re.S).group()

    assert 'data-fora-da-tela="1"' in html
    assert "disabled" in excluir
    assert 'data-dica="Exiba as demandas ocultas para excluir"' in excluir

    cliente.post("/projetos/{}/excluir".format(projeto.id))

    assert db.session.get(Projeto, projeto.id) is not None


def test_mover_considera_a_posicao_entre_as_tarefas_visiveis(
    cliente, criar_projeto, criar_tarefa
):
    projeto = criar_projeto(cliente.usuario_id)
    a = criar_tarefa(projeto, "A", 0)
    oculta = criar_tarefa(projeto, "Oculta", 1)
    criar_tarefa(projeto, "B", 2)
    criar_tarefa(projeto, "C", 3)
    ocultar(cliente, oculta)

    # Na tela: A, B, C. Soltar A depois de B envia a posição 1 entre B e C.
    mover(cliente, a, projeto, 1)
    assert ordem(projeto) == ["Oculta", "B", "A", "C"]

    mover(cliente, a, projeto, 2)
    assert ordem(projeto) == ["Oculta", "B", "C", "A"]

    alternar_ocultas(cliente)
    mover(cliente, a, projeto, 0)
    assert ordem(projeto) == ["A", "Oculta", "B", "C"]


@pytest.mark.so_sqlite
def test_atualizar_banco_adiciona_as_colunas_de_ocultacao(cliente, criar_projeto, criar_tarefa):
    tarefa_id = criar_tarefa(criar_projeto(cliente.usuario_id), "Antiga").id
    db.session.commit()
    db.session.execute(text("ALTER TABLE tarefa DROP COLUMN oculta"))
    db.session.execute(text("ALTER TABLE usuario DROP COLUMN mostrar_ocultas"))
    db.session.commit()

    atualizar_banco()

    db.session.expire_all()
    assert db.session.get(Tarefa, tarefa_id).oculta is False
    assert db.session.get(Usuario, cliente.usuario_id).mostrar_ocultas is False


def test_excluir_tarefa(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))

    cliente.post("/tarefas/{}/excluir".format(tarefa.id))

    assert Tarefa.query.count() == 0


def test_mover_tarefa_para_outro_projeto(cliente, criar_projeto, criar_tarefa):
    origem = criar_projeto(cliente.usuario_id, "Origem")
    destino = criar_projeto(cliente.usuario_id, "Destino", 1)
    tarefa = criar_tarefa(origem, "Movida", 0)
    fica = criar_tarefa(origem, "Fica", 1)
    criar_tarefa(destino, "Primeira", 0)
    criar_tarefa(destino, "Última", 1)

    resposta = mover(cliente, tarefa, destino, 1)

    assert resposta.status_code == 200
    assert resposta.get_json() == {"projeto_id": destino.id, "posicao": 1}
    assert ordem(destino) == ["Primeira", "Movida", "Última"]
    assert db.session.get(Tarefa, fica.id).posicao == 0


def test_mover_tarefa_dentro_da_mesmo_projeto(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto, "A", 0)
    criar_tarefa(projeto, "B", 1)
    criar_tarefa(projeto, "C", 2)

    mover(cliente, tarefa, projeto, 2)

    assert ordem(projeto) == ["B", "C", "A"]


def test_mover_tarefa_limita_posicao_fora_do_intervalo(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto, "A", 0)
    criar_tarefa(projeto, "B", 1)

    assert mover(cliente, tarefa, projeto, 99).get_json()["posicao"] == 1
    assert mover(cliente, tarefa, projeto, -5).get_json()["posicao"] == 0


def test_mover_tarefa_com_dados_invalidos_retorna_400(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto)
    url = "/api/tarefas/{}/mover".format(tarefa.id)

    assert cliente.post(url, json={"projeto_id": "1", "posicao": 0}).status_code == 400
    assert cliente.post(url, json={"projeto_id": projeto.id, "posicao": True}).status_code == 400
    assert cliente.post(url, data="nao-e-json").status_code == 400


def test_confirmacao_de_exclusao_tem_titulo_texto_e_botoes(cliente):
    html = cliente.get("/").get_data(as_text=True)

    caixa = html.split('id="confirmacao"')[1].split("</dialog>")[0]
    assert ">Confirmação<" in caixa
    assert ">Confirma a exclusão?<" in caixa
    assert ">Sim<" in caixa
    assert ">Não<" in caixa


def test_tarefa_tem_icone_de_excluir_e_nao_de_editar(cliente, criar_projeto, criar_tarefa):
    criar_tarefa(criar_projeto(cliente.usuario_id), "Comprar pão")

    html = cliente.get("/").get_data(as_text=True)

    assert 'aria-label="Excluir demanda Comprar pão"' in html
    assert 'aria-label="Editar demanda' not in html


def caixa_de_notificacao(resposta):
    return resposta.get_data(as_text=True).split('id="notificacao"')[1].split("</dialog>")[0]


def test_notificacao_aparece_na_caixa_central_com_ok(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))

    resposta = cliente.post("/tarefas/{}/excluir".format(tarefa.id), follow_redirects=True)

    caixa = caixa_de_notificacao(resposta)
    assert "<h2 id=\"notificacao-titulo\">Notificação</h2>" in caixa
    assert "<p>Cartão excluído.</p>" in caixa
    assert ">Ok<" in caixa


def test_erro_continua_aparecendo_na_notificacao(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    resposta = cliente.post(
        "/tarefas", data={"nome": "", "projeto_id": projeto.id}, follow_redirects=True
    )

    assert "<p>Informe o nome da demanda.</p>" in caixa_de_notificacao(resposta)


def test_criar_e_atualizar_nao_exibem_notificacao(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto)
    categoria = {"nome": "Casa", "icone": "casa"}
    dados_tarefa = {"nome": "Nova", "projeto_id": projeto.id}

    cliente.post("/categorias", data=categoria)
    categoria_id = Categoria.query.filter_by(nome="Casa").one().id
    dados_projeto = {"nome": "Outra", "cor": "#1a6fe0", "categoria_id": categoria_id}
    envios = [
        ("/categorias", categoria),
        ("/categorias/{}/editar".format(categoria_id), categoria),
        ("/projetos", dados_projeto),
        ("/projetos/{}/editar".format(projeto.id), dados_projeto),
        ("/tarefas", dados_tarefa),
        ("/tarefas/{}/editar".format(tarefa.id), dados_tarefa),
        ("/perfil", {"nome": "Nome Novo"}),
    ]

    for url, dados in envios:
        resposta = cliente.post(url, data=dados, follow_redirects=True)

        assert resposta.status_code == 200
        assert "<p>" not in caixa_de_notificacao(resposta)


def test_quadro_tem_categorias_na_lateral_e_projetos_na_area_central(
    cliente, criar_projeto, criar_tarefa
):
    criar_tarefa(criar_projeto(cliente.usuario_id, "Projeto central"), "Tarefa central")
    cliente.post("/categorias", data={"nome": "Trabalho", "icone": "casa"})

    html = cliente.get("/").get_data(as_text=True)

    lateral = html.split('<aside class="lateral"')[1].split("</aside>")[0]
    central = html.split('<div class="central">')[1].split("<dialog")[0]
    assert "Trabalho" in lateral
    assert "Projeto central" not in lateral
    assert "Projeto central" in central
    assert "Tarefa central" in central


def test_categorias_tem_nome_acessivel_com_a_lateral_recolhida(cliente):
    cliente.post("/categorias", data={"nome": "Trabalho", "icone": "casa"})

    lateral = cliente.get("/").get_data(as_text=True).split("</aside>")[0]

    for nome in ("Todas", "Trabalho"):
        assert 'aria-label="{0}" data-dica="{0}"'.format(nome) in lateral
        assert "<span>{}</span></a>".format(nome) in lateral


def test_lateral_recolhida_mantem_os_icones_das_categorias():
    css = Path("static/css/style.css").read_text(encoding="utf-8")
    regra = re.search(r"([^{}]*)\{\s*display: none;\s*\}\s*\.lateral-oculta \.categoria-link \{", css)

    assert ".lateral-oculta .categoria-link span" in regra.group(1)
    assert ".lateral-oculta .categoria-item .botao-icone" in regra.group(1)
    assert ".lateral-oculta .categorias" not in css


def test_barra_lateral_tem_botao_para_ocultar(cliente):
    lateral = cliente.get("/").get_data(as_text=True).split("</aside>")[0]

    assert "data-alternar-lateral" in lateral
    assert 'aria-label="Ocultar categorias"' in lateral


@pytest.mark.parametrize("campo", ["tarefa-nome", "projeto-nome", "categoria-nome"])
def test_campo_nome_abre_vazio_e_sem_preenchimento_automatico(
    cliente, criar_projeto, criar_tarefa, campo
):
    criar_tarefa(criar_projeto(cliente.usuario_id, "Compras"), "Comprar pão")

    html = cliente.get("/").get_data(as_text=True)

    entrada = re.search(r'<input[^>]*id="{}"[^>]*>'.format(campo), html).group()
    assert 'value=""' in entrada
    assert 'autocomplete="off"' in entrada


def test_nome_da_tarefa_e_ignorado_por_gerenciadores_de_senhas(cliente):
    html = cliente.get("/").get_data(as_text=True)

    entrada = re.search(r'<input[^>]*id="tarefa-nome"[^>]*>', html).group()
    for atributo in ("data-lpignore", "data-1p-ignore", "data-bwignore"):
        assert atributo in entrada


def test_agora_usa_fuso_de_sao_paulo():
    # 01:00 UTC ainda é o dia anterior em São Paulo (UTC-3).
    instante = datetime(2026, 11, 3, 1, 0, tzinfo=timezone.utc)

    with patch("routes.datetime") as relogio:
        relogio.now.side_effect = lambda fuso: instante.astimezone(fuso)
        assert agora() == datetime(2026, 11, 2, 22, 0)


def test_previsao_e_opcional(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post(
        "/tarefas",
        data={"nome": "Sem previsão", "previsao_execucao": "", "projeto_id": projeto.id},
    )

    assert Tarefa.query.one().previsao_execucao is None


@pytest.mark.parametrize("valor", ["2026-12-25", "ontem", "2026-13-40T10:00"])
def test_previsao_invalida_e_recusada_em_portugues(cliente, criar_projeto, valor):
    projeto = criar_projeto(cliente.usuario_id)

    resposta = cliente.post(
        "/tarefas",
        data={"nome": "Tarefa", "previsao_execucao": valor, "projeto_id": projeto.id},
        follow_redirects=True,
    )

    assert Tarefa.query.count() == 0
    assert "Informe uma data e uma hora válidas." in resposta.get_data(as_text=True)


def test_editar_tarefa_altera_a_previsao(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto)

    cliente.post(
        "/tarefas/{}/editar".format(tarefa.id),
        data={
            "nome": "Tarefa",
            "previsao_execucao": "2026-12-25T08:05",
            "projeto_id": projeto.id,
        },
    )

    assert db.session.get(Tarefa, tarefa.id).previsao_execucao == datetime(2026, 12, 25, 8, 5)


def test_formulario_tem_campo_de_data_e_hora_com_o_novo_nome(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    assert re.search(r'<input[^>]*id="tarefa-previsao"[^>]*type="datetime-local"', html)
    assert ">Previsão de Execução</label>" in html
    assert "Data de execução" not in html


def test_cartao_exibe_a_previsao_abaixo_do_nome_so_com_data_e_hora(
    cliente, criar_projeto, criar_tarefa
):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.descricao = "Detalhes"
    tarefa.previsao_execucao = datetime(2026, 12, 25, 14, 30)
    db.session.commit()

    html = cliente.get("/").get_data(as_text=True)

    assert '>25/12/2026 14:30</time>' in html
    assert 'data-previsao="2026-12-25T14:30"' in html
    nome = html.index('<button class="tarefa-nome"')
    assert nome < html.index('<time class="tarefa-previsao"')
    assert html.index('<time class="tarefa-previsao"') < html.index('<div class="tarefa-descricao')


def test_tarefa_vencida_e_marcada_sem_texto_extra(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.previsao_execucao = agora() - timedelta(minutes=1)
    db.session.commit()

    html = cliente.get("/").get_data(as_text=True)

    assert 'class="tarefa prioridade-baixa tarefa-vencida"' in html
    assert 'title="Prioridade Baixa - Vencida"' in html
    assert "(atrasada)" not in html


@pytest.mark.parametrize("previsao", [None, timedelta(minutes=5)])
def test_tarefa_futura_ou_sem_previsao_nao_e_vencida(
    cliente, criar_projeto, criar_tarefa, previsao
):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.previsao_execucao = agora() + previsao if previsao else None
    db.session.commit()

    assert "tarefa-vencida" not in cliente.get("/").get_data(as_text=True)


@pytest.mark.so_sqlite
def test_atualizar_banco_converte_a_data_antiga_ate_o_fim_do_dia(
    cliente, criar_projeto, criar_tarefa
):
    projeto = criar_projeto(cliente.usuario_id)
    com_data = criar_tarefa(projeto, "Com data").id
    sem_data = criar_tarefa(projeto, "Sem data").id
    db.session.commit()
    db.session.execute(
        text("ALTER TABLE tarefa RENAME COLUMN previsao_execucao TO data_execucao")
    )
    db.session.execute(
        text("UPDATE tarefa SET data_execucao = '2026-11-02' WHERE id = :id"),
        {"id": com_data},
    )
    db.session.commit()

    atualizar_banco()
    atualizar_banco()

    db.session.expire_all()
    assert db.session.get(Tarefa, com_data).previsao_execucao == datetime(2026, 11, 2, 23, 59)
    assert db.session.get(Tarefa, sem_data).previsao_execucao is None
