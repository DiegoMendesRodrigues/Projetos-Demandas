# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from datetime import datetime, timedelta

import pytest
from flask import get_template_attribute
from sqlalchemy import text

from app import atualizar_banco
from extensions import db
from models import Anexo, Categoria, Projeto
from routes import agora


@pytest.fixture
def criar_atrasada(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)

    def _criar_atrasada(nome="Atrasada", previsao=None, oculta=False):
        tarefa = criar_tarefa(projeto, nome)
        tarefa.previsao_execucao = previsao or agora() - timedelta(minutes=1)
        tarefa.oculta = oculta
        db.session.commit()
        return tarefa

    return _criar_atrasada


def cabecalho(cliente, url="/"):
    return cliente.get(url).get_data(as_text=True).split("</header>")[0]


def botao_de_alertas(html):
    return re.search(r'<div class="topo-acoes">\s*<div class="menu">(.*?)</button>', html, re.S).group(1)


def itens_do_menu(html):
    caixa = html.split('id="menu-alertas"')[1].split("</div>")[0]
    return re.findall(r'<a class="menu-item" href="([^"]*)">.*?<span>([^<]*)</span></a>', caixa, re.S)


def test_alerta_fica_a_esquerda_do_icone_de_grupos(cliente):
    html = cabecalho(cliente)

    assert 'aria-controls="menu-cores"' not in html
    assert html.index('data-dica="Nenhuma demanda atrasada"') < html.index('aria-label="Grupos"')


def test_sem_atrasadas_o_alerta_fica_neutro_e_sem_menu(cliente):
    html = cabecalho(cliente)
    botao = botao_de_alertas(html)

    assert "botao-alertas" not in botao
    assert "disabled" in botao
    assert "data-menu-gatilho" not in botao
    assert "alertas-contador" not in html
    assert 'id="menu-alertas"' not in html


@pytest.mark.parametrize("delta", [None, timedelta(minutes=5), timedelta(days=30)])
def test_atividade_no_prazo_ou_sem_previsao_nao_gera_alerta(
    cliente, criar_projeto, criar_tarefa, delta
):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    tarefa.previsao_execucao = agora() + delta if delta else None
    db.session.commit()

    assert "alertas-contador" not in cabecalho(cliente)


def test_atrasadas_destacam_o_alerta_com_a_quantidade(cliente, criar_atrasada):
    criar_atrasada("Primeira")
    criar_atrasada("Segunda")

    botao = botao_de_alertas(cabecalho(cliente))

    assert 'class="botao-topo botao-alertas"' in botao
    assert '<span class="alertas-contador" aria-hidden="true">2</span>' in botao
    assert 'data-dica="2 demandas atrasadas"' in botao
    assert 'aria-controls="menu-alertas"' in botao
    assert "disabled" not in botao


def test_uma_atrasada_usa_o_singular(cliente, criar_atrasada):
    criar_atrasada()

    assert 'data-dica="1 demanda atrasada"' in cabecalho(cliente)


def test_menu_lista_data_hora_e_nome_da_mais_antiga_para_a_mais_recente(cliente, criar_atrasada):
    recente = criar_atrasada("Recente", datetime(2026, 3, 2, 8, 5))
    antiga = criar_atrasada("Antiga", datetime(2025, 12, 25, 14, 30))

    assert itens_do_menu(cabecalho(cliente)) == [
        ("/?tarefa={}".format(antiga.id), "25/12/2025 14:30 - Antiga"),
        ("/?tarefa={}".format(recente.id), "02/03/2026 08:05 - Recente"),
    ]


def test_menu_exibe_o_icone_da_categoria_a_esquerda_da_data(app, cliente, criar_atrasada):
    desenhar = get_template_attribute("_icones.html", "icone_categoria")
    tarefa = criar_atrasada("Com categoria", datetime(2026, 3, 2, 8, 5))
    tarefa.projeto.categoria = Categoria(
        nome="Lar", icone="casa", usuario_id=cliente.usuario_id
    )
    db.session.commit()

    html = cabecalho(cliente)

    assert (
        '">{}<span>02/03/2026 08:05 - Com categoria</span></a>'.format(desenhar("casa"))
        in html
    )


def test_menu_de_projeto_antigo_sem_categoria_fica_sem_icone(cliente, criar_atrasada):
    criar_atrasada("Sem categoria", datetime(2026, 3, 2, 8, 5))

    html = cabecalho(cliente)

    assert '"><span>02/03/2026 08:05 - Sem categoria</span></a>' in html


def test_menu_escapa_o_nome_da_atividade(cliente, criar_atrasada):
    criar_atrasada("<script>alert(1)</script>")

    html = cabecalho(cliente)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_atividade_oculta_atrasada_continua_no_alerta(cliente, criar_atrasada):
    criar_atrasada("Escondida", oculta=True)

    assert "- Escondida" in cabecalho(cliente)


def test_alerta_aparece_nas_demais_paginas(cliente, criar_atrasada):
    criar_atrasada()

    assert '<span class="alertas-contador"' in cabecalho(cliente, "/perfil")


def test_alerta_nao_conta_atividades_de_outro_usuario(
    cliente, outro_cliente, criar_atrasada
):
    criar_atrasada("Alheia")

    assert "alertas-contador" not in cabecalho(outro_cliente)


def test_menu_mantem_a_categoria_selecionada(cliente, criar_atrasada):
    tarefa = criar_atrasada()
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add(categoria)
    db.session.commit()

    html = cabecalho(cliente, "/?categoria={}".format(categoria.id))

    assert 'categoria={}'.format(categoria.id) in itens_do_menu(html)[0][0]
    assert 'tarefa={}'.format(tarefa.id) in itens_do_menu(html)[0][0]


def test_quadro_sem_parametro_nao_abre_atividade(cliente, criar_atrasada):
    criar_atrasada()

    assert "data-abrir-tarefa" not in cliente.get("/").get_data(as_text=True)


def test_quadro_recebe_os_dados_da_atividade_a_abrir(cliente, criar_atrasada):
    tarefa = criar_atrasada("Com anexo")
    db.session.add(Anexo(nome="nota.txt", arquivo="a" * 32, tamanho=1, tarefa_id=tarefa.id))
    db.session.commit()

    html = cliente.get("/?tarefa={}".format(tarefa.id)).get_data(as_text=True)
    aberta = html.split("data-abrir-tarefa")[1].split("<dialog")[0]

    assert 'data-nome="Com anexo"' in aberta
    assert 'data-url="/tarefas/{}/editar"'.format(tarefa.id) in aberta
    assert 'data-anexo' in aberta
    assert 'data-nome="nota.txt"' in aberta


def dados_do_projeto(categoria, **extras):
    return dict(nome="Fim", cor="#1a6fe0", categoria_id=categoria.id, **extras)


def test_projeto_concluido_nao_gera_alerta(cliente, criar_atrasada):
    criar_atrasada().projeto.concluida = True
    db.session.commit()

    assert "alertas-contador" not in cabecalho(cliente)


def test_projeto_concluido_nao_entra_na_contagem_das_demais(
    cliente, criar_atrasada, criar_projeto, criar_tarefa
):
    criar_atrasada("Pendente")
    feita = criar_tarefa(criar_projeto(cliente.usuario_id, "Fim"), "Feita")
    feita.previsao_execucao = agora() - timedelta(days=1)
    feita.projeto.concluida = True
    db.session.commit()

    html = cabecalho(cliente)

    assert 'data-dica="1 demanda atrasada"' in html
    assert "- Pendente" in html
    assert "- Feita" not in html


def test_mover_para_projeto_concluido_tira_a_atividade_do_alerta(
    cliente, criar_atrasada, criar_projeto
):
    tarefa = criar_atrasada()
    fim = criar_projeto(cliente.usuario_id, "Fim", 1)
    fim.concluida = True
    db.session.commit()

    cliente.post(
        "/api/tarefas/{}/mover".format(tarefa.id), json={"projeto_id": fim.id, "posicao": 0}
    )

    assert "alertas-contador" not in cabecalho(cliente)


def test_criar_projeto_salva_a_marcacao_de_concluida(cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)

    cliente.post("/projetos", data=dados_do_projeto(categoria, concluida="y"))

    assert Projeto.query.one().concluida is True


def test_projeto_novo_nao_e_concluida_por_padrao(cliente, criar_categoria):
    cliente.post("/projetos", data=dados_do_projeto(criar_categoria(cliente.usuario_id)))

    assert Projeto.query.one().concluida is False


def test_editar_projeto_marca_e_desmarca_concluida(cliente, criar_categoria, criar_projeto):
    categoria = criar_categoria(cliente.usuario_id)
    projeto = criar_projeto(cliente.usuario_id)
    url = "/projetos/{}/editar".format(projeto.id)

    cliente.post(url, data=dados_do_projeto(categoria, concluida="y"))
    assert db.session.get(Projeto, projeto.id).concluida is True

    cliente.post(url, data=dados_do_projeto(categoria))
    assert db.session.get(Projeto, projeto.id).concluida is False


def test_dialogo_de_projeto_oferece_a_marcacao_e_o_botao_de_editar_a_informa(
    cliente, criar_projeto
):
    criar_projeto(cliente.usuario_id, "Comum")
    criar_projeto(cliente.usuario_id, "Fim", 1).concluida = True
    db.session.commit()

    html = cliente.get("/").get_data(as_text=True)
    dialogo = html.split('id="dialogo-projeto"')[1].split("</dialog>")[0]

    assert re.search(r'<input[^>]*id="projeto-concluido"[^>]*type="checkbox"', dialogo)
    assert "Projeto concluído" in dialogo
    assert html.count('data-concluida="sim"') == 1
    assert html.count('data-concluida=""') == 1


@pytest.mark.so_sqlite
@pytest.mark.parametrize(
    "nome, concluida",
    [("Concluídas", True), ("Concluído", True), ("Pendentes", False), ("Quase Concluídas", False)],
)
def test_atualizar_banco_marca_os_projetos_ja_criados_para_o_que_terminou(
    cliente, criar_projeto, nome, concluida
):
    projeto = criar_projeto(cliente.usuario_id, nome)
    db.session.commit()
    db.session.execute(text("ALTER TABLE projeto DROP COLUMN concluida"))
    db.session.commit()

    atualizar_banco()

    db.session.expire_all()
    assert db.session.get(Projeto, projeto.id).concluida is concluida


@pytest.mark.so_sqlite
def test_atualizar_banco_nao_remarca_projeto_que_o_usuario_desmarcou(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id, "Concluídas")

    atualizar_banco()

    db.session.expire_all()
    assert db.session.get(Projeto, projeto.id).concluida is False


def test_atividade_oculta_tambem_pode_ser_aberta(cliente, criar_atrasada):
    tarefa = criar_atrasada("Escondida", oculta=True)

    html = cliente.get("/?tarefa={}".format(tarefa.id)).get_data(as_text=True)

    assert 'data-url="/tarefas/{}/editar"'.format(tarefa.id) in html.split("data-abrir-tarefa")[1]
    assert '<article class="tarefa' not in html


def test_atividade_de_outra_categoria_tambem_pode_ser_aberta(cliente, criar_atrasada):
    tarefa = criar_atrasada("Fora do filtro")
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add_all(
        [categoria, Projeto(nome="Da casa", usuario_id=cliente.usuario_id, categoria=categoria)]
    )
    db.session.commit()

    html = cliente.get(
        "/?categoria={}&tarefa={}".format(categoria.id, tarefa.id)
    ).get_data(as_text=True)

    assert 'data-nome="Fora do filtro"' in html.split("data-abrir-tarefa")[1]


def test_atividade_de_outro_usuario_retorna_404(cliente, outro_cliente, criar_atrasada):
    tarefa = criar_atrasada("Alheia")

    assert outro_cliente.get("/?tarefa={}".format(tarefa.id)).status_code == 404
