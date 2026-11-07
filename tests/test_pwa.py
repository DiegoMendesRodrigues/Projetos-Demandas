# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Aplicativo instalável (PWA): manifesto, service worker e página sem conexão."""
import json
import re
from pathlib import Path

import pytest
from PIL import Image

import routes

RAIZ = Path(__file__).resolve().parent.parent


def manifesto(cliente):
    resposta = cliente.get("/manifest.webmanifest")
    assert resposta.status_code == 200
    assert resposta.mimetype == "application/manifest+json"
    return json.loads(resposta.get_data(as_text=True))


def codigo_do_service_worker(cliente):
    resposta = cliente.get("/sw.js")
    assert resposta.status_code == 200
    return resposta


def codigo_do_app():
    return (RAIZ / "static/js/app.js").read_text(encoding="utf-8")


# ---------- Manifesto


def test_manifesto_e_publico_e_instalavel(app):
    dados = manifesto(app.test_client())
    assert dados["name"] == "Projetos & Demandas"
    assert dados["short_name"] == "Projetos"
    assert dados["lang"] == "pt-BR"
    assert (dados["start_url"], dados["scope"], dados["display"]) == ("/", "/", "standalone")
    tamanhos = {icone["sizes"] for icone in dados["icons"] if icone["type"] == "image/png"}
    assert {"192x192", "512x512"} <= tamanhos
    assert any(icone.get("purpose") == "maskable" for icone in dados["icons"])


def test_manifesto_tem_atalhos_para_meu_dia_e_calendario(app):
    atalhos = {atalho["name"]: atalho["url"] for atalho in manifesto(app.test_client())["shortcuts"]}
    assert atalhos == {"Meu Dia": "/meu-dia", "Calendário": "/calendario"}


def test_cores_do_manifesto_sao_as_do_style_css(app):
    dados = manifesto(app.test_client())
    css = (RAIZ / "static/css/style.css").read_text(encoding="utf-8")
    assert f"--fundo: {dados['background_color']};" in css
    assert f'[data-tema="azul"] {{ --cabecalho: {dados["theme_color"]};' in css


@pytest.mark.parametrize("nome, lado, transparente", [
    ("icone-192.png", 192, True),
    ("icone-512.png", 512, True),
    ("icone-maskable-512.png", 512, False),
    ("apple-touch-icon.png", 180, False),
])
def test_icones_existem_no_tamanho_certo(nome, lado, transparente):
    imagem = Image.open(RAIZ / "static/img" / nome)
    assert imagem.size == (lado, lado)
    # O maskable e o do iPhone precisam de fundo: o sistema não aceita transparência neles.
    assert (imagem.mode == "RGBA") is transparente


def test_icones_do_manifesto_sao_servidos(app):
    cliente = app.test_client()
    for icone in manifesto(cliente)["icons"]:
        assert cliente.get(icone["src"]).status_code == 200


# ---------- Service worker


def test_service_worker_na_raiz_e_sem_cache_http(app):
    resposta = codigo_do_service_worker(app.test_client())
    assert resposta.mimetype == "text/javascript"
    assert resposta.headers["Cache-Control"] == "no-cache"
    assert resposta.headers["Service-Worker-Allowed"] == "/"


def test_service_worker_recebe_versao_arquivos_e_pagina_offline(app):
    codigo = codigo_do_service_worker(app.test_client()).get_data(as_text=True)
    assert "__VERSAO__" not in codigo and "__ARQUIVOS__" not in codigo and "__OFFLINE__" not in codigo
    assert re.search(r'const VERSAO = "[0-9a-f]{16}";', codigo)
    assert 'const PAGINA_OFFLINE = "/offline";' in codigo
    arquivos = json.loads(re.search(r"const ARQUIVOS = (\[.*?\]);", codigo).group(1))
    assert arquivos == [f"/static/{nome}" for nome in routes.ARQUIVOS_DO_APP]


def test_arquivos_guardados_existem(app):
    cliente = app.test_client()
    for nome in routes.ARQUIVOS_DO_APP:
        assert cliente.get(f"/static/{nome}").status_code == 200


def test_versao_muda_quando_um_arquivo_guardado_muda(app, tmp_path, monkeypatch):
    for nome in routes.ARQUIVOS_DO_APP + ("js/sw.js",):
        destino = tmp_path / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes((RAIZ / "static" / nome).read_bytes())
    monkeypatch.setattr(app, "static_folder", str(tmp_path))
    with app.test_request_context():
        antes = routes.versao_dos_arquivos_do_app()
        assert routes.versao_dos_arquivos_do_app() == antes
        (tmp_path / "css/style.css").write_text("/* nova versão */", encoding="utf-8")
        assert routes.versao_dos_arquivos_do_app() != antes


def test_service_worker_nao_guarda_paginas_com_dados():
    codigo = (RAIZ / "static/js/sw.js").read_text(encoding="utf-8")
    # As navegações vão sempre ao servidor; o cache só é a reserva da página sem conexão.
    assert "evento.respondWith(fetch(pedido).catch(() => caches.match(PAGINA_OFFLINE)));" in codigo
    assert 'pedido.method !== "GET"' in codigo
    assert "endereco.origin !== self.location.origin" in codigo
    assert codigo.count("cache.put") == 0
    assert 'new Request(PAGINA_OFFLINE, { credentials: "omit" })' in codigo


# ---------- Página sem conexão


def test_pagina_offline_e_publica_e_sem_dados_do_usuario(cliente):
    html = cliente.get("/offline").get_data(as_text=True)
    assert "Sem conexão" in html and "Tentar de novo" in html
    assert "csrf-token" not in html and "menu-usuario" not in html


def test_pagina_offline_sem_login(app):
    assert app.test_client().get("/offline").status_code == 200


# ---------- Páginas e app.js


def test_paginas_apontam_para_o_manifesto(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert '<link rel="apple-touch-icon" href="/static/img/apple-touch-icon.png">' in html
    assert '<meta name="theme-color" content="#0b3f91">' in html
    assert '<meta name="apple-mobile-web-app-title" content="Projetos">' in html


def test_login_tambem_aponta_para_o_manifesto(app):
    assert 'rel="manifest"' in app.test_client().get("/login").get_data(as_text=True)


def test_menu_do_usuario_tem_instalar_escondido(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert re.search(r'<button class="menu-item" type="button" data-instalar-app hidden>.*Instalar o aplicativo</button>', html)
    css = (RAIZ / "static/css/style.css").read_text(encoding="utf-8")
    assert ".menu-item[hidden] {\n  display: none;" in css


def test_app_registra_o_service_worker_antes_do_quadro():
    codigo = codigo_do_app()
    guarda = codigo.index("if (!quadro) {")
    for trecho in (
        'navigator.serviceWorker.register("/sw.js")',
        '"beforeinstallprompt"',
        "function atualizarCorDaBarra",
    ):
        assert codigo.index(trecho) < guarda, trecho
    assert "window.isSecureContext" in codigo
    # A prévia da Cor da Aplicação também troca a cor da barra do sistema.
    preview = codigo[codigo.index("document.documentElement.dataset.tema = opcao.value;"):]
    assert preview.index("atualizarCorDaBarra();") < 80


def test_icones_vem_do_icone_do_cabecalho():
    """Os ícones são o icone_cabecalho.png centralizado: o centro tem o desenho, não o fundo."""
    for nome in ("icone-192.png", "icone-512.png", "icone-maskable-512.png", "apple-touch-icon.png"):
        imagem = Image.open(RAIZ / "static/img" / nome).convert("RGBA")
        lado = imagem.width
        assert imagem.getpixel((lado // 2, lado // 2))[3] > 200, nome
    # O maskable deixa o desenho dentro da zona segura: o círculo de 80% do lado.
    maskable = Image.open(RAIZ / "static/img/icone-maskable-512.png").convert("RGB")
    fundo = maskable.getpixel((0, 0))
    desenho = [
        (x, y) for x in range(0, 512, 4) for y in range(0, 512, 4)
        if sum(abs(a - b) for a, b in zip(maskable.getpixel((x, y)), fundo)) > 30
    ]
    assert desenho
    assert all(((x - 256) ** 2 + (y - 256) ** 2) ** 0.5 <= 0.4 * 512 for x, y in desenho)


def test_cabecalho_usa_o_logo_de_60_pixels():
    css = (RAIZ / "static/css/style.css").read_text(encoding="utf-8")
    regra = css.split(".marca-logo {")[1].split("}")[0]

    assert "height: 60px;" in regra
    # Sem largura fixa (vem da proporção da imagem) e sem cor de fundo.
    assert "width:" not in regra and "background: none;" in regra
    nome = css.split(".marca-nome {")[1].split("}")[0]
    assert "color: #ffffff;" in nome
    # Os atributos width e height de base.html seguem a proporção da imagem.
    largura, altura = Image.open(RAIZ / "static/img/icone_cabecalho.png").size
    assert round(60 * largura / altura) == 87
    assert "img/icone_cabecalho.png" in routes.ARQUIVOS_DO_APP


def test_favicon_tem_os_tamanhos_pequenos():
    ico = Image.open(RAIZ / "static/img/favicon.ico")
    assert ico.info["sizes"] == {(16, 16), (32, 32), (48, 48)}
    png = Image.open(RAIZ / "static/img/favicon-32.png")
    assert png.size == (32, 32) and png.mode == "RGBA"
    assert png.getpixel((16, 16))[3] > 200  # o desenho no centro, não o fundo transparente


def test_favicon_na_raiz(app):
    resposta = app.test_client().get("/favicon.ico")

    assert resposta.status_code == 200
    assert resposta.mimetype == "image/vnd.microsoft.icon"
    assert resposta.data == (RAIZ / "static/img/favicon.ico").read_bytes()


def test_manifesto_e_paginas_sem_o_logo_antigo(app):
    cliente = app.test_client()

    assert "logo.svg" not in json.dumps(manifesto(cliente))
    assert "logo.svg" not in cliente.get("/offline").get_data(as_text=True)


def test_paginas_pedem_css_e_js_com_a_versao_do_conteudo(app, tmp_path, monkeypatch):
    import hashlib

    html = app.test_client().get("/login").get_data(as_text=True)

    for nome in ("css/style.css", "js/app.js"):
        versao = hashlib.sha256((RAIZ / "static" / nome).read_bytes()).hexdigest()[:12]
        assert "/static/{}?v={}".format(nome, versao) in html
        # O service worker não serve do cache os endereços com ?v=: o arquivo novo chega na hora.
        assert app.test_client().get("/static/{}?v={}".format(nome, versao)).status_code == 200


def test_versao_do_estatico_muda_com_o_conteudo(app, tmp_path):
    import os

    pasta = tmp_path / "static"
    pasta.mkdir()
    arquivo = pasta / "teste.js"
    arquivo.write_text("um", encoding="utf-8")
    app.static_folder = str(pasta)

    with app.test_request_context():
        primeira = routes.estatico("teste.js")
        assert routes.estatico("teste.js") == primeira
        arquivo.write_text("dois", encoding="utf-8")
        momento = os.stat(arquivo).st_mtime_ns + 10**9
        os.utime(arquivo, ns=(momento, momento))
        assert routes.estatico("teste.js") != primeira


def test_pagina_offline_usa_os_enderecos_guardados_pelo_service_worker(app):
    html = app.test_client().get("/offline").get_data(as_text=True)

    assert 'href="/static/css/style.css"' in html
