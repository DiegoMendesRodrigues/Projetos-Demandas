# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from pathlib import Path

import pytest
from flask import render_template

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ / "templates" / "base.html"
LINHAS = (
    "Projetos & Demandas | Solução on-line para a gestão de projetos e demandas",
    "Desenvolvido por Diego Mendes Rodrigues",
)
COMENTARIOS = {
    ".py": "# {}",
    ".html": "{{# {} -#}}",
    ".txt": "{{# {} -#}}",
    ".css": "/* {} */",
    ".js": "// {}",
}
ARQUIVOS = sorted(
    list(RAIZ.glob("*.py"))
    + [
        caminho
        for pasta in ("templates", "static", "tests", "migracoes")
        for caminho in (RAIZ / pasta).rglob("*")
        if caminho.suffix in COMENTARIOS
    ]
)


def test_todos_os_tipos_de_codigo_fonte_foram_encontrados():
    assert {caminho.suffix for caminho in ARQUIVOS} == set(COMENTARIOS)


@pytest.mark.parametrize("caminho", ARQUIVOS, ids=lambda c: c.relative_to(RAIZ).as_posix())
def test_arquivo_comeca_com_o_cabecalho_do_sistema(caminho):
    linhas = caminho.read_text(encoding="utf-8").splitlines()

    if caminho == BASE:
        # Aqui o comentário é HTML, depois do doctype, para aparecer no código da página.
        assert linhas[2:4] == ["<!-- {} -->".format(linha) for linha in LINHAS]
    else:
        formato = COMENTARIOS[caminho.suffix]
        assert linhas[:2] == [formato.format(linha) for linha in LINHAS]


def test_cabecalho_aparece_uma_vez_no_html_enviado_ao_navegador(cliente):
    html = cliente.get("/").get_data(as_text=True)

    assert html.startswith("<!DOCTYPE html>")
    for linha in LINHAS:
        assert html.count(linha) == 1
        assert "<!-- {} -->".format(linha) in html


def test_alteracao_em_template_aparece_sem_reiniciar_o_servidor(app):
    assert app.jinja_env.auto_reload is True


def test_mensagens_das_telas_de_conta_continuam_vazias(app):
    with app.test_request_context():
        assert render_template("security/_messages.html").strip() == ""
