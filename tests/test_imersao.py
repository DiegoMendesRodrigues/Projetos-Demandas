# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Recursos de imersão do quadro: ações sem recarregar, atalhos, modo foco, estados vazios e animações."""
import re

import pytest

from extensions import db


def ler(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


@pytest.fixture
def quadro_com_cartao(cliente, criar_categoria, criar_projeto, criar_tarefa):
    categoria = criar_categoria(cliente.usuario_id)
    projeto = criar_projeto(cliente.usuario_id)
    projeto.categoria_id = categoria.id
    db.session.commit()
    tarefa = criar_tarefa(projeto, nome="Feira")
    return categoria, projeto, tarefa


def test_cartao_tem_o_id_para_ser_trocado_no_lugar(cliente, quadro_com_cartao):
    _, _, tarefa = quadro_com_cartao
    html = cliente.get("/").get_data(as_text=True)
    assert f'data-tarefa-id="{tarefa.id}"' in html


def test_acoes_do_cartao_sao_enviadas_sem_recarregar(cliente, quadro_com_cartao):
    _, _, tarefa = quadro_com_cartao
    html = cliente.get("/").get_data(as_text=True)
    for rota in ("concluir", "ocultar"):
        assert f'action="/tarefas/{tarefa.id}/{rota}" data-acao-cartao' in html
    responsavel = html[html.index('id="dialogo-responsavel"'):]
    assert responsavel.index('<form method="post" data-acao-cartao>') < responsavel.index("</dialog>")


def test_acao_do_cartao_continua_redirecionando_ao_quadro(cliente, quadro_com_cartao):
    """O fetch segue este redirect e lê o cartão novo da página do quadro."""
    categoria, _, tarefa = quadro_com_cartao
    resposta = cliente.post(f"/tarefas/{tarefa.id}/ocultar", data={"categoria": categoria.id})
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith(f"/?categoria={categoria.id}")


def test_barra_tem_o_modo_foco(cliente, quadro_com_cartao):
    html = cliente.get("/").get_data(as_text=True)
    assert 'data-foco aria-pressed="false"' in html
    assert 'data-dica="Modo foco (F)"' in html


def test_dialogo_de_atalhos_lista_as_teclas(cliente, quadro_com_cartao):
    html = cliente.get("/").get_data(as_text=True)
    atalhos = html[html.index('id="dialogo-atalhos"'):]
    atalhos = atalhos[:atalhos.index("</dialog>")]
    for tecla in ("/", "N", "F", "Esc", "?"):
        assert f"<kbd>{tecla}</kbd>" in atalhos


def test_atalho_n_some_sem_projetos(cliente):
    html = cliente.get("/").get_data(as_text=True)
    atalhos = html[html.index('id="dialogo-atalhos"'):]
    assert "<kbd>N</kbd>" not in atalhos[:atalhos.index("</dialog>")]


def test_sem_categorias_o_vazio_tem_botao_de_criar_categoria(cliente):
    html = cliente.get("/").get_data(as_text=True)
    vazio = html[html.index('class="vazio"'):]
    assert 'class="ilustracao-vazia"' in vazio
    assert re.search(r'<button class="botao botao-primario" type="button" data-nova-categoria>.*Criar categoria</button>', vazio)


def test_sem_projetos_o_vazio_tem_botao_de_criar_projeto(cliente, criar_categoria):
    criar_categoria(cliente.usuario_id)
    html = cliente.get("/").get_data(as_text=True)
    vazio = html[html.index('class="vazio"'):]
    assert re.search(r'data-novo-projeto>.*Criar projeto</button>', vazio)


def test_categoria_vazia_cria_o_projeto_ja_na_categoria(cliente, criar_categoria):
    categoria = criar_categoria(cliente.usuario_id)
    html = cliente.get(f"/?categoria={categoria.id}").get_data(as_text=True)
    assert html.count(f'data-novo-projeto data-categoria-id="{categoria.id}"') == 1
    assert f'data-categoria-id="{categoria.id}"\n                  aria-label="Criar novo projeto"' in html


def test_codigo_dos_recursos_esta_no_app_js():
    codigo = ler("static/js/app.js")
    for trecho in ("form[data-acao-cartao]", "sessionStorage", "definirModoFoco", "dialogo-atalhos", "prefers-reduced-motion"):
        assert trecho in codigo
    # A troca do cartão reaproveita os contadores do projeto.
    assert codigo.index("function atualizarContadores") < codigo.index("form[data-acao-cartao]")


def test_animacoes_respeitam_menos_movimento():
    css = ler("static/css/style.css")
    bloco = css[css.index("@media (prefers-reduced-motion: no-preference)"):]
    for animacao in ("tarefa-entrar", "tarefa-sair", "tarefa-realce", "concluir-pulso"):
        assert f"@keyframes {animacao}" in bloco
        assert css.index(f"@keyframes {animacao}") > css.index("@media (prefers-reduced-motion: no-preference)")


def test_modo_foco_esconde_cabecalho_e_barra_lateral():
    css = ler("static/css/style.css")
    assert re.search(r"\.modo-foco \.topo,\s*\.modo-foco \.lateral \{\s*display: none;", css)
