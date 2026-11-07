# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re

import pytest
from flask import get_template_attribute

from extensions import db
from app import CORES_ANTIGAS, atualizar_banco
from models import CORES_PROJETO, ICONES_CATEGORIA, Categoria, Projeto, Tarefa


def nomes_dos_projetos(usuario_id):
    projetos = Projeto.query.filter_by(usuario_id=usuario_id).order_by(Projeto.posicao)
    return [projeto.nome for projeto in projetos]


def test_criar_categoria(cliente):
    cliente.post("/categorias", data={"nome": "Trabalho", "icone": "casa"})

    assert Categoria.query.filter_by(usuario_id=cliente.usuario_id).one().nome == "Trabalho"


def test_criar_categoria_sem_nome_e_recusado(cliente):
    cliente.post("/categorias", data={"nome": ""})

    assert Categoria.query.count() == 0


def test_editar_categoria(cliente):
    categoria = Categoria(nome="Antiga", usuario_id=cliente.usuario_id)
    db.session.add(categoria)
    db.session.commit()

    cliente.post("/categorias/{}/editar".format(categoria.id), data={"nome": "Nova", "icone": "casa"})

    assert db.session.get(Categoria, categoria.id).nome == "Nova"


def test_excluir_categoria_sem_projetos(cliente):
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add(categoria)
    db.session.commit()

    cliente.post("/categorias/{}/excluir".format(categoria.id))

    assert Categoria.query.count() == 0


def test_nao_exclui_categoria_com_projetos(cliente):
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    projeto = Projeto(nome="Compras", usuario_id=cliente.usuario_id, categoria=categoria)
    db.session.add_all([categoria, projeto])
    db.session.commit()

    resposta = cliente.post(
        "/categorias/{}/excluir".format(categoria.id), follow_redirects=True
    )

    assert "Remova os projetos desta categoria antes de excluí-la." in resposta.get_data(as_text=True)
    assert Categoria.query.count() == 1
    assert db.session.get(Projeto, projeto.id).categoria_id == categoria.id


def test_icone_de_excluir_categoria_fica_bloqueado_com_projetos(cliente):
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    vazia = Categoria(nome="Vazia", usuario_id=cliente.usuario_id)
    projeto = Projeto(nome="Compras", usuario_id=cliente.usuario_id, categoria=categoria)
    db.session.add_all([categoria, vazia, projeto])
    db.session.commit()

    html = cliente.get("/").get_data(as_text=True)

    assert re.search(r'aria-label="Excluir categoria Casa"[^>]*disabled', html)
    assert not re.search(r'aria-label="Excluir categoria Vazia"[^>]*disabled', html)
    assert 'aria-label="Editar categoria Casa"' in html


def test_ha_24_icones_distintos_e_cada_um_tem_desenho_proprio(app):
    desenhar = get_template_attribute("_icones.html", "icone_categoria")

    chaves = [chave for chave, _ in ICONES_CATEGORIA]
    assert len(set(chaves)) == 24
    assert len({str(desenhar(chave)) for chave in chaves + ["todas"]}) == 25


def test_dialogo_de_categoria_oferece_os_24_icones_sem_escolha_previa(cliente):
    html = cliente.get("/").get_data(as_text=True)

    dialogo = html.split('id="dialogo-categoria"')[1].split("</dialog>")[0]
    icones = [campo for campo in re.findall(r"<input[^>]*>", dialogo) if 'name="icone"' in campo]
    assert len(icones) == 24
    assert not any("checked" in campo for campo in icones)


def test_criar_categoria_salva_o_icone(cliente):
    cliente.post("/categorias", data={"nome": "Lar", "icone": "casa"})

    assert Categoria.query.one().icone == "casa"


def test_criar_categoria_sem_icone_e_recusado(cliente):
    resposta = cliente.post(
        "/categorias", data={"nome": "Lar"}, follow_redirects=True
    )

    assert "Escolha um ícone para a categoria." in resposta.get_data(as_text=True)
    assert Categoria.query.count() == 0


def test_criar_categoria_com_icone_invalido_e_recusado(cliente):
    resposta = cliente.post(
        "/categorias", data={"nome": "Lar", "icone": "foguete"}, follow_redirects=True
    )

    assert "Escolha um ícone válido." in resposta.get_data(as_text=True)
    assert Categoria.query.count() == 0


def test_editar_categoria_altera_o_icone(cliente):
    categoria = Categoria(nome="Lar", icone="casa", usuario_id=cliente.usuario_id)
    db.session.add(categoria)
    db.session.commit()

    cliente.post(
        "/categorias/{}/editar".format(categoria.id),
        data={"nome": "Lar", "icone": "estrela"},
    )

    assert db.session.get(Categoria, categoria.id).icone == "estrela"


def test_icone_aparece_na_lateral_e_na_area_central(app, cliente):
    desenhar = get_template_attribute("_icones.html", "icone_categoria")
    categoria = Categoria(nome="Lar", icone="casa", usuario_id=cliente.usuario_id)
    db.session.add(categoria)
    db.session.commit()

    html = cliente.get("/?categoria={}".format(categoria.id)).get_data(as_text=True)

    lateral = html.split('<aside class="lateral"')[1].split("</aside>")[0]
    barra = html.split('<section class="barra"')[1].split("</section>")[0]
    assert str(desenhar("casa")) in lateral
    assert str(desenhar("casa")) in barra
    assert str(desenhar("todas")) in lateral


def test_projeto_exibe_o_icone_a_esquerda_do_nome_da_categoria(app, cliente):
    desenhar = get_template_attribute("_icones.html", "icone_categoria")
    categoria = Categoria(nome="Lar", icone="casa", usuario_id=cliente.usuario_id)
    projeto = Projeto(nome="Compras", usuario_id=cliente.usuario_id, categoria=categoria)
    db.session.add_all([categoria, projeto])
    db.session.commit()

    html = cliente.get("/").get_data(as_text=True)

    assert '<p class="projeto-categoria">{}<span>Lar</span></p>'.format(desenhar("casa")) in html


def test_visao_todas_usa_o_icone_do_sistema(app, cliente):
    desenhar = get_template_attribute("_icones.html", "icone_categoria")

    html = cliente.get("/").get_data(as_text=True)

    barra = html.split('<section class="barra"')[1].split("</section>")[0]
    assert str(desenhar("todas")) in barra


def test_criar_projetos_define_posicoes_em_sequencia(cliente, criar_categoria):
    dados = {"cor": "#1a6fe0", "categoria_id": criar_categoria(cliente.usuario_id).id}
    cliente.post("/projetos", data=dict(dados, nome="Primeira"))
    cliente.post("/projetos", data=dict(dados, nome="Segunda"))

    posicoes = [projeto.posicao for projeto in Projeto.query.order_by(Projeto.id)]
    assert posicoes == [0, 1]


def test_criar_projeto_com_cor_fora_da_paleta_e_recusado(cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)

    cliente.post(
        "/projetos",
        data={"nome": "Projeto", "cor": "#123456", "categoria_id": categoria.id},
    )

    assert Projeto.query.count() == 0


def test_criar_projeto_salva_a_categoria(cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)

    cliente.post(
        "/projetos",
        data={"nome": "Projeto", "cor": "#1a6fe0", "categoria_id": categoria.id},
    )

    assert Projeto.query.one().categoria_id == categoria.id


@pytest.mark.parametrize("dados", [{}, {"categoria_id": ""}, {"categoria_id": "0"}])
def test_criar_projeto_sem_categoria_e_recusado(cliente, criar_categoria, dados):
    criar_categoria(cliente.usuario_id)

    resposta = cliente.post(
        "/projetos",
        data=dict(dados, nome="Projeto", cor="#1a6fe0"),
        follow_redirects=True,
    )

    html = resposta.get_data(as_text=True)
    assert html.count("Escolha uma categoria para o projeto.") == 1
    assert Projeto.query.count() == 0


@pytest.mark.parametrize("dados", [{}, {"categoria_id": ""}, {"categoria_id": "0"}])
def test_editar_projeto_sem_categoria_e_recusado(cliente, criar_categoria, dados):
    categoria = criar_categoria(cliente.usuario_id)
    projeto = Projeto(nome="Compras", usuario_id=cliente.usuario_id, categoria=categoria)
    db.session.add(projeto)
    db.session.commit()

    resposta = cliente.post(
        "/projetos/{}/editar".format(projeto.id),
        data=dict(dados, nome="Renomeada", cor="#1a6fe0"),
        follow_redirects=True,
    )

    assert "Escolha uma categoria para o projeto." in resposta.get_data(as_text=True)
    alterada = db.session.get(Projeto, projeto.id)
    assert alterada.nome == "Compras"
    assert alterada.categoria_id == categoria.id


def test_projeto_antigo_sem_categoria_so_salva_com_uma_categoria(
    cliente, criar_categoria, criar_projeto
):
    categoria = criar_categoria(cliente.usuario_id)
    projeto = criar_projeto(cliente.usuario_id)
    url = "/projetos/{}/editar".format(projeto.id)
    dados = {"nome": "Renomeada", "cor": "#1a6fe0"}

    cliente.post(url, data=dict(dados, categoria_id=""))
    assert db.session.get(Projeto, projeto.id).nome == "A fazer"

    cliente.post(url, data=dict(dados, categoria_id=categoria.id))
    alterada = db.session.get(Projeto, projeto.id)
    assert alterada.nome == "Renomeada"
    assert alterada.categoria_id == categoria.id


def test_dialogo_de_projeto_exige_a_escolha_da_categoria(cliente, criar_categoria):
    criar_categoria(cliente.usuario_id, "Lar")

    html = cliente.get("/").get_data(as_text=True)

    dialogo = html.split('id="dialogo-projeto"')[1].split("</dialog>")[0]
    campo = re.search(r'<select[^>]*id="projeto-categoria"[^>]*>(.*?)</select>', dialogo, re.S)
    assert "required" in campo.group(0).split(">")[0]
    assert re.search(r'<option selected value="">Selecione uma categoria</option>', campo.group(1))
    assert ">Lar</option>" in campo.group(1)
    assert "Sem categoria" not in html


def test_sem_categorias_o_quadro_orienta_e_bloqueia_novo_projeto(cliente):
    html = cliente.get("/").get_data(as_text=True)

    botao = re.search(r"<button[^>]*data-novo-projeto[^>]*>", html).group(0)
    assert "disabled" in botao
    assert 'data-dica="Crie uma categoria para criar um projeto"' in botao
    assert "Crie sua primeira categoria" in html


def test_com_categoria_novo_projeto_fica_liberada(cliente, criar_categoria):
    criar_categoria(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    botao = re.search(r"<button[^>]*data-novo-projeto[^>]*>", html).group(0)
    assert "disabled" not in botao
    assert 'data-dica="Criar novo projeto"' in botao
    assert "Crie seu primeiro projeto" in html


def test_criar_projeto_com_categoria_de_outro_usuario_e_recusado(cliente, outro_cliente):
    categoria = Categoria(nome="Alheia", usuario_id=outro_cliente.usuario_id)
    db.session.add(categoria)
    db.session.commit()

    cliente.post(
        "/projetos",
        data={"nome": "Projeto", "cor": "#1a6fe0", "categoria_id": categoria.id},
    )

    assert Projeto.query.count() == 0


def test_paleta_tem_12_cores_distintas():
    assert len({cor for cor, _ in CORES_PROJETO}) == 12


def test_dialogo_de_projeto_oferece_apenas_as_cores_da_paleta(cliente):
    html = cliente.get("/").get_data(as_text=True)

    dialogo = html.split('id="dialogo-projeto"')[1].split("</dialog>")[0]
    assert dialogo.count('type="radio"') == 12
    assert 'type="color"' not in dialogo


def test_editar_projeto_com_cor_fora_da_paleta_e_recusado(cliente, criar_categoria, criar_projeto):
    categoria = criar_categoria(cliente.usuario_id)
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post(
        "/projetos/{}/editar".format(projeto.id),
        data={"nome": "Renomeada", "cor": "#123456", "categoria_id": categoria.id},
    )

    assert db.session.get(Projeto, projeto.id).nome == "A fazer"


@pytest.mark.so_sqlite
def test_projeto_antigo_recebe_a_cor_mais_proxima_da_paleta(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    projeto.cor = "#20b050"
    db.session.commit()

    atualizar_banco()

    assert db.session.get(Projeto, projeto.id).cor == "#22b455"


@pytest.mark.so_sqlite
@pytest.mark.parametrize("antiga, nova", CORES_ANTIGAS.items())
def test_atualizar_banco_troca_cada_cor_pastel_pela_vibrante(cliente, criar_projeto, antiga, nova):
    projeto = criar_projeto(cliente.usuario_id)
    projeto.cor = antiga
    db.session.commit()

    atualizar_banco()

    assert db.session.get(Projeto, projeto.id).cor == nova


def test_cores_antigas_cobrem_toda_a_paleta_atual():
    assert sorted(CORES_ANTIGAS.values()) == sorted(cor for cor, _ in CORES_PROJETO)


def test_editar_projeto(cliente, criar_categoria, criar_projeto):
    categoria = criar_categoria(cliente.usuario_id)
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post(
        "/projetos/{}/editar".format(projeto.id),
        data={"nome": "Renomeada", "cor": "#ff5a4f", "categoria_id": categoria.id},
    )

    alterada = db.session.get(Projeto, projeto.id)
    assert alterada.nome == "Renomeada"
    assert alterada.cor == "#ff5a4f"
    assert alterada.categoria_id == categoria.id


def test_excluir_projeto_vazio_reordena_as_demais(cliente, criar_projeto):
    primeira = criar_projeto(cliente.usuario_id, "Primeira", 0)
    segunda = criar_projeto(cliente.usuario_id, "Segunda", 1)

    cliente.post("/projetos/{}/excluir".format(primeira.id))

    assert db.session.get(Projeto, primeira.id) is None
    assert db.session.get(Projeto, segunda.id).posicao == 0


def test_nao_exclui_projeto_com_tarefas(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    criar_tarefa(projeto)

    resposta = cliente.post(
        "/projetos/{}/excluir".format(projeto.id), follow_redirects=True
    )

    assert "Remova as demandas deste projeto antes de excluí-lo." in resposta.get_data(as_text=True)
    assert Projeto.query.count() == 1
    assert Tarefa.query.count() == 1


def test_icone_de_excluir_projeto_fica_bloqueado_com_tarefas(
    cliente, criar_projeto, criar_tarefa
):
    criar_tarefa(criar_projeto(cliente.usuario_id, "Cheia", 0))
    criar_projeto(cliente.usuario_id, "Vazia", 1)

    html = cliente.get("/").get_data(as_text=True)

    assert re.search(r'aria-label="Excluir projeto Cheia"[^>]*disabled', html)
    assert not re.search(r'aria-label="Excluir projeto Vazia"[^>]*disabled', html)
    assert 'aria-label="Editar projeto Cheia"' in html


def ordenar(cliente, ids):
    return cliente.post("/api/projetos/ordem", json={"projetos": ids})


def test_ordenar_projetos_salva_a_nova_ordem(cliente, criar_projeto):
    primeira = criar_projeto(cliente.usuario_id, "Primeira", 0)
    segunda = criar_projeto(cliente.usuario_id, "Segunda", 1)
    terceira = criar_projeto(cliente.usuario_id, "Terceira", 2)

    resposta = ordenar(cliente, [terceira.id, primeira.id, segunda.id])

    assert resposta.status_code == 200
    assert nomes_dos_projetos(cliente.usuario_id) == ["Terceira", "Primeira", "Segunda"]


def test_ordenar_projetos_filtrados_preserva_as_demais(cliente):
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    a = Projeto(nome="A", usuario_id=cliente.usuario_id, posicao=0, categoria=categoria)
    b = Projeto(nome="B", usuario_id=cliente.usuario_id, posicao=1)
    c = Projeto(nome="C", usuario_id=cliente.usuario_id, posicao=2, categoria=categoria)
    db.session.add_all([categoria, a, b, c])
    db.session.commit()

    ordenar(cliente, [c.id, a.id])

    assert nomes_dos_projetos(cliente.usuario_id) == ["C", "B", "A"]


def test_ordenar_projetos_nao_aceita_projeto_de_outro_usuario(
    cliente, outro_cliente, criar_projeto
):
    minha = criar_projeto(cliente.usuario_id, "Minha", 0)
    alheia = criar_projeto(outro_cliente.usuario_id, "Alheia", 0)

    resposta = ordenar(cliente, [alheia.id, minha.id])

    assert resposta.status_code == 404
    assert db.session.get(Projeto, alheia.id).posicao == 0


@pytest.mark.parametrize("ids", [[], "1", ["1"], [True], [1, 1]])
def test_ordenar_projetos_com_dados_invalidos_retorna_400(cliente, criar_projeto, ids):
    criar_projeto(cliente.usuario_id)

    assert ordenar(cliente, ids).status_code == 400


def test_projeto_tem_alca_para_arrastar_e_nao_tem_setas(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    assert 'class="projeto-alca"' in html
    assert 'data-url-ordem="/api/projetos/ordem"' in html
    assert 'name="direcao"' not in html


def test_quadro_filtra_por_categoria(cliente):
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add_all(
        [
            categoria,
            Projeto(nome="Da casa", usuario_id=cliente.usuario_id, categoria=categoria),
            Projeto(nome="Sem categoria", usuario_id=cliente.usuario_id, posicao=1),
        ]
    )
    db.session.commit()

    html = cliente.get("/?categoria={}".format(categoria.id)).get_data(as_text=True)

    assert "Da casa" in html
    assert "<h2>Sem categoria</h2>" not in html
