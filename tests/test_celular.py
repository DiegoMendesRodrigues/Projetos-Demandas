# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Layout do celular: o bloco final de style.css e o que os modelos precisam ter para ele."""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CSS = (RAIZ / "static" / "css" / "style.css").read_text(encoding="utf-8")
TABELAS = ["usuarios.html", "grupos.html", "planos.html", "membros.html", "adicionar_membros.html", "compartilhar.html"]


def bloco_do_celular():
    inicio = CSS.index("/* ---------- Celular:")
    return CSS[inicio:]


def regra(bloco, seletor):
    """O corpo da regra cujo seletor termina com o texto dado."""
    achado = re.search(re.escape(seletor) + r"\s*\{([^}]*)\}", bloco)
    assert achado, seletor
    return achado.group(1)


def test_bloco_do_celular_fica_no_fim_do_css():
    bloco = bloco_do_celular()

    assert bloco.lstrip().startswith("/* ---------- Celular:")
    assert "@media (max-width: 640px)" in bloco
    # Nada depois dele: as regras do celular valem sobre as anteriores.
    assert "@media" not in bloco[bloco.index("@media (max-width: 640px)") + 10:]


def test_cabecalho_fica_numa_linha():
    bloco = bloco_do_celular()

    assert "flex-wrap: nowrap" in regra(bloco, ".topo")
    assert "width: auto" in regra(bloco, ".marca-logo")
    assert "text-overflow: ellipsis" in regra(bloco, ".marca-nome")


def test_categorias_viram_uma_faixa_que_rola_para_os_lados():
    bloco = bloco_do_celular()
    faixa = regra(bloco, ".lateral-oculta .lateral")

    assert "flex-direction: row" in faixa and "overflow-x: auto" in faixa
    assert "flex-flow: row nowrap" in regra(bloco, ".categorias")
    assert "display: none" in regra(bloco, ".categoria-item:not(.categoria-ativa) .botao-icone")


def test_caixas_ocupam_a_tela_com_os_botoes_fixos_no_pe():
    bloco = bloco_do_celular()
    caixa = regra(bloco, ":is(#dialogo-tarefa, .dialogo):not(.notificacao)")

    assert "width: calc(100vw / var(--escala))" in caixa
    assert "height: calc(100dvh / var(--escala))" in caixa
    acoes = regra(bloco, ".dialogo:not(.notificacao) .dialogo-acoes")
    assert "position: sticky" in acoes and "bottom: 0" in acoes


def test_tabelas_viram_cartoes_com_rotulos():
    bloco = bloco_do_celular()

    assert "content: attr(data-rotulo)" in regra(bloco, ".tabela td[data-rotulo]::before")
    assert "display: none" in regra(bloco, ".tabela th:not(:has(a))")


@pytest.mark.parametrize("modelo", TABELAS)
def test_celulas_das_tabelas_tem_rotulo(modelo):
    """Menos a primeira coluna (o nome, em destaque), as ações e as linhas de aviso."""
    texto = (RAIZ / "templates" / modelo).read_text(encoding="utf-8")
    corpo = texto[texto.index("<tbody>"):texto.index("</tbody>")]

    for linha in re.findall(r"<tr>(.*?)</tr>", corpo, re.S):
        celulas = re.findall(r"<td[^>]*>", linha)
        for celula in celulas[1:]:
            if "tabela-acoes" in celula or "colspan" in celula:
                continue
            assert "data-rotulo=" in celula, (modelo, celula)


def test_compartilhar_tem_nome_acessivel_sem_o_texto(app, cliente, criar_categoria, criar_projeto):
    categoria = criar_categoria(cliente.usuario_id)
    criar_projeto(cliente.usuario_id).categoria_id = categoria.id

    html = cliente.get("/?categoria={}".format(categoria.id)).get_data(as_text=True)
    botao = html[html.index('class="botao botao-compartilhar"'):]
    botao = botao[:botao.index("</a>")]

    assert 'aria-label="Compartilhar"' in botao
    assert '<span class="rotulo-do-botao">Compartilhar</span>' in botao
    assert "display: none" in regra(bloco_do_celular(), ".compartilhamento-nome")


def test_categoria_aberta_vem_para_a_vista_no_celular():
    js = (RAIZ / "static" / "js" / "app.js").read_text(encoding="utf-8")
    trecho = js[js.index('document.querySelector(".lateral .categoria-ativa")'):]

    assert 'matchMedia("(max-width: 640px)")' in trecho[:300]
    assert 'scrollIntoView({ block: "nearest", inline: "center" })' in trecho[:400]
    assert js.index(trecho[:60]) < js.index("if (!quadro) {")
