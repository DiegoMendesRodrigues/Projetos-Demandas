# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from pathlib import Path

CSS = Path("static/css/style.css").read_text(encoding="utf-8")
JS = Path("static/js/app.js").read_text(encoding="utf-8")


def test_site_inteiro_em_90_por_cento():
    regra = re.search(r"\nhtml \{(.*?)\}", CSS, re.S).group(1)
    assert "--escala: 0.9;" in regra
    assert "zoom: var(--escala);" in regra


def test_medidas_da_tela_compensam_a_escala():
    # Com o zoom, 100vh vale só 90% da tela: toda medida em vh ou vw é dividida por --escala.
    for medida in re.findall(r"[\d.]+d?v[hw]\b[^;]*", CSS):
        assert "/ var(--escala)" in medida, medida


def test_arrasto_divide_as_coordenadas_pela_escala():
    assert "function escalaDaPagina()" in JS
    for trecho in ("fantasma.style.left", "fantasma.style.top", "fantasma.style.width", "quadro.scrollLeft = rolagem"):
        for linha in (l for l in JS.splitlines() if trecho in l and "=" in l):
            assert "escalaDaPagina()" in linha, linha
