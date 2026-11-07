# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Vídeos do Vimeo: no Cartão - Vídeo, na seção Vídeo do generalista e no Atualizar as informações."""
import io
import json
import urllib.error
from datetime import date

import pytest
from sqlalchemy import inspect, text

import videos
import vimeo
import youtube
from app import atualizar_banco
from extensions import db
from models import Tarefa, VideoDoYoutube

NUMERO = "76979871"
ENDERECO = "https://vimeo.com/" + NUMERO
MINIATURA = "https://i.vimeocdn.com/video/452001751-8216e0571c251a09d7a8387550942d89f7f86f6398f8ed886e639b0dd50d3c90-d_640?region=us"
CODIGO_YOUTUBE = "jNQXAC9IVRw"


def dados_do_oembed(numero=NUMERO, **campos):
    dados = {
        "type": "video", "video_id": int(numero), "title": "The New Vimeo Player (You Know, For Videos)",
        "author_name": "Vimeo", "description": "It may look like the old player", "duration": 62,
        "thumbnail_url": MINIATURA, "upload_date": "2013-10-15 14:08:29",
    }
    dados.update(campos)
    return dados


@pytest.fixture
def vimeo_falso(monkeypatch):
    """Substitui o acesso ao oEmbed: guarda os códigos pedidos e devolve os dados definidos."""
    estado = {"pedidos": [], "erro": None, "dados": None}

    def baixar(codigo):
        estado["pedidos"].append(codigo)
        if estado["erro"]:
            raise estado["erro"]
        return estado["dados"] or dados_do_oembed(codigo.partition(":")[0])

    monkeypatch.setattr(vimeo, "baixar_dados", baixar)
    return estado


@pytest.fixture
def sem_youtube(monkeypatch):
    """O YouTube não pode ser acessado nos testes do Vimeo."""
    def baixar(codigo):
        raise AssertionError("acessou o YouTube")

    monkeypatch.setattr(youtube, "baixar_pagina", baixar)


def criar(cliente, projeto, endereco=ENDERECO):
    return cliente.post("/api/videos", json={"projeto_id": projeto.id, "endereco": endereco})


@pytest.mark.parametrize("endereco, codigo", [
    (ENDERECO, NUMERO),
    ("vimeo.com/" + NUMERO, NUMERO),
    ("https://www.vimeo.com/{}?share=copy".format(NUMERO), NUMERO),
    ("https://vimeo.com/{}/a1b2c3d4e5".format(NUMERO), NUMERO + ":a1b2c3d4e5"),
    ("https://vimeo.com/channels/staffpicks/" + NUMERO, NUMERO),
    ("https://vimeo.com/groups/curtas/videos/" + NUMERO, NUMERO),
    ("https://vimeo.com/showcase/123/video/" + NUMERO, NUMERO),
    ("https://player.vimeo.com/video/{}?h=a1b2c3d4e5&badge=0".format(NUMERO), NUMERO + ":a1b2c3d4e5"),
])
def test_reconhece_os_enderecos_do_vimeo(endereco, codigo):
    assert vimeo.codigo_do_video(endereco) == codigo


def test_codigo_de_privacidade_estranho_e_ignorado():
    assert vimeo.codigo_do_video("https://vimeo.com/{}/<script>".format(NUMERO)) == NUMERO
    assert vimeo.codigo_do_video("https://player.vimeo.com/video/{}?h=../x".format(NUMERO)) == NUMERO


@pytest.mark.parametrize("endereco", [
    "", "https://vimeo.com/", "https://vimeo.com/canal", "https://evil.com/" + NUMERO,
    "https://vimeo.com.evil.com/" + NUMERO, "ftp://vimeo.com/" + NUMERO, "javascript:alert(1)",
    "https://vimeo.com/{}?x={}".format(NUMERO, "a" * 400), "https://vimeo.com/1234567890123",
])
def test_recusa_enderecos_que_nao_sao_videos_do_vimeo(endereco):
    with pytest.raises(youtube.EnderecoInvalido):
        vimeo.codigo_do_video(endereco)


def test_player_do_vimeo_sem_rastreamento():
    assert vimeo.endereco_do_player(NUMERO) == "https://player.vimeo.com/video/{}?dnt=1".format(NUMERO)
    assert vimeo.endereco_do_player(NUMERO + ":abc123") == "https://player.vimeo.com/video/{}?h=abc123&dnt=1".format(NUMERO)


def test_informacoes_vem_do_oembed():
    informacoes = vimeo.informacoes_dos_dados(dados_do_oembed(), NUMERO)

    assert informacoes == {
        "plataforma": "vimeo", "codigo": NUMERO, "autor": "Vimeo",
        "titulo": "The New Vimeo Player (You Know, For Videos)", "descricao": "It may look like the old player",
        "publicacao": date(2013, 10, 15), "duracao": "1:02", "miniatura": MINIATURA,
    }


@pytest.mark.parametrize("miniatura", [
    "http://i.vimeocdn.com/video/1.jpg", "https://evil.com/video/1.jpg",
    "https://i.vimeocdn.com.evil.com/1.jpg", 'https://i.vimeocdn.com/1.jpg" onerror="x', None,
])
def test_so_aceita_miniaturas_do_vimeo(miniatura):
    assert vimeo.informacoes_dos_dados(dados_do_oembed(thumbnail_url=miniatura), NUMERO)["miniatura"] == ""


@pytest.mark.parametrize("dados", [
    dados_do_oembed(video_id=1), dados_do_oembed(title=""), dados_do_oembed(title=None),
])
def test_dados_de_outro_video_ou_sem_titulo_falham(dados):
    with pytest.raises(youtube.ErroNasInformacoes):
        vimeo.informacoes_dos_dados(dados, NUMERO)


def test_data_e_duracao_invalidas_ficam_vazias():
    informacoes = vimeo.informacoes_dos_dados(dados_do_oembed(upload_date="ontem", duration="x"), NUMERO)

    assert informacoes["publicacao"] is None and informacoes["duracao"] == ""


def test_oembed_e_pedido_so_com_o_endereco_oficial(monkeypatch):
    pedidos = []

    def abrir(requisicao, timeout):
        pedidos.append((requisicao.full_url, timeout))
        return io.BytesIO(json.dumps(dados_do_oembed()).encode("utf-8"))

    monkeypatch.setattr(vimeo.urllib.request, "urlopen", abrir)

    assert vimeo.informacoes_do_codigo(NUMERO + ":abc123")["titulo"].startswith("The New")
    assert pedidos == [(
        "https://vimeo.com/api/oembed.json?url=https%3A%2F%2Fvimeo.com%2F{}%2Fabc123&width=640".format(NUMERO),
        youtube.TEMPO_LIMITE,
    )]


@pytest.mark.parametrize("erro, esperado", [
    (urllib.error.HTTPError("u", 404, "Not Found", {}, None), youtube.ErroNasInformacoes),
    (urllib.error.HTTPError("u", 403, "Forbidden", {}, None), youtube.ErroNasInformacoes),
    (urllib.error.URLError("sem rede"), youtube.ErroDeConexao),
    (TimeoutError(), youtube.ErroDeConexao),
])
def test_falhas_do_oembed(monkeypatch, erro, esperado):
    def abrir(requisicao, timeout):
        raise erro

    monkeypatch.setattr(vimeo.urllib.request, "urlopen", abrir)

    with pytest.raises(esperado):
        vimeo.baixar_dados(NUMERO)


def test_resposta_que_nao_e_json_falha(monkeypatch):
    monkeypatch.setattr(vimeo.urllib.request, "urlopen", lambda requisicao, timeout: io.BytesIO(b"<html>"))

    with pytest.raises(youtube.ErroNasInformacoes):
        vimeo.baixar_dados(NUMERO)


def test_identifica_a_plataforma_pelo_endereco():
    assert videos.identificar(ENDERECO) == ("vimeo", NUMERO)
    assert videos.identificar("https://youtu.be/" + CODIGO_YOUTUBE) == ("youtube", CODIGO_YOUTUBE)
    with pytest.raises(youtube.EnderecoInvalido):
        videos.identificar("https://exemplo.com/video/1")


def test_video_do_youtube_continua_igual():
    video = VideoDoYoutube(codigo=CODIGO_YOUTUBE)

    assert video.nome_da_plataforma == "YouTube"
    assert video.miniatura == "https://i.ytimg.com/vi/{}/mqdefault.jpg".format(CODIGO_YOUTUBE)
    assert video.endereco_do_player == "https://www.youtube-nocookie.com/embed/" + CODIGO_YOUTUBE


def test_cria_o_cartao_de_video_do_vimeo(cliente, criar_projeto, vimeo_falso, sem_youtube):
    resposta = criar(cliente, criar_projeto(cliente.usuario_id))

    assert resposta.status_code == 201
    tarefa = Tarefa.query.one()
    video = tarefa.video
    assert (video.plataforma, video.codigo, video.endereco_da_miniatura) == ("vimeo", NUMERO, MINIATURA)
    assert (video.autor, video.duracao, video.publicado_em) == ("Vimeo", "1:02", date(2013, 10, 15))
    assert tarefa.nome.startswith("The New Vimeo Player")
    assert vimeo_falso["pedidos"] == [NUMERO]

    html = cliente.get("/").get_data(as_text=True)
    cartao = html.split('data-tarefa-id="{}"'.format(tarefa.id))[1].split("</article>")[0]
    assert 'data-video-plataforma="Vimeo"' in html
    assert 'data-video-player="https://player.vimeo.com/video/{}?dnt=1"'.format(NUMERO) in html
    assert 'src="{}"'.format(MINIATURA.replace("&", "&amp;")) in cartao


def test_cartao_sem_miniatura_mostra_um_retangulo(cliente, criar_projeto, vimeo_falso, sem_youtube):
    vimeo_falso["dados"] = dados_do_oembed(thumbnail_url="https://evil.com/x.jpg")
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()

    html = cliente.get("/").get_data(as_text=True)
    cartao = html.split('data-tarefa-id="{}"'.format(tarefa.id))[1].split("</article>")[0]

    assert 'class="video-miniatura video-sem-miniatura"' in cartao and "evil.com" not in html


def test_falha_do_vimeo_nao_cria_o_cartao(cliente, criar_projeto, vimeo_falso, sem_youtube):
    vimeo_falso["erro"] = youtube.ErroNasInformacoes()

    resposta = criar(cliente, criar_projeto(cliente.usuario_id))

    assert resposta.status_code == 422
    assert "Não foi possível buscar as informações do vídeo" in resposta.get_json()["erro"]
    assert Tarefa.query.count() == 0


def test_atualizar_busca_de_novo_no_vimeo(cliente, criar_projeto, vimeo_falso, sem_youtube):
    criar(cliente, criar_projeto(cliente.usuario_id), "https://vimeo.com/{}/abc123".format(NUMERO))
    tarefa = Tarefa.query.one()
    vimeo_falso["pedidos"].clear()
    vimeo_falso["dados"] = dados_do_oembed(title="Novo título", thumbnail_url=MINIATURA + "&x=1")

    resposta = cliente.post("/api/videos/{}/atualizar".format(tarefa.id))

    assert resposta.status_code == 200 and resposta.get_json()["titulo"] == "Novo título"
    assert vimeo_falso["pedidos"] == [NUMERO + ":abc123"]
    video = db.session.get(VideoDoYoutube, tarefa.id)
    assert video.titulo == "Novo título" and video.endereco_da_miniatura == MINIATURA + "&x=1"
    assert db.session.get(Tarefa, tarefa.id).eventos[0].tipo == "atualizou_video"


def test_previa_do_generalista_com_o_vimeo(cliente, vimeo_falso, sem_youtube):
    resposta = cliente.post("/api/videos/previa", json={"endereco": ENDERECO})

    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert dados["plataforma"] == "vimeo" and dados["nome_da_plataforma"] == "Vimeo"
    assert dados["player"] == "https://player.vimeo.com/video/{}?dnt=1".format(NUMERO)
    assert dados["miniatura"] == MINIATURA
    assert Tarefa.query.count() == 0


def criar_generalista(cliente, projeto, endereco, **campos):
    dados = {"nome": "Estudo", "prioridade": "alta", "projeto_id": projeto.id, "tipo": "generalista",
             "secoes": json.dumps(["video"]), "video_endereco": endereco}
    dados.update(campos)
    return cliente.post("/tarefas", data=dados, content_type="multipart/form-data", follow_redirects=True)


def test_generalista_com_video_do_vimeo(cliente, criar_projeto, vimeo_falso, sem_youtube):
    criar_generalista(cliente, criar_projeto(cliente.usuario_id), ENDERECO)

    tarefa = Tarefa.query.one()
    assert (tarefa.video.plataforma, tarefa.video.codigo) == ("vimeo", NUMERO)
    html = cliente.get("/").get_data(as_text=True)
    cartao = html.split('data-tarefa-id="{}"'.format(tarefa.id))[1].split("</article>")[0]
    assert "i.vimeocdn.com" in cartao and 'class="tarefa-video-do-cartao"' in cartao


def test_generalista_troca_o_youtube_pelo_vimeo(cliente, criar_projeto, vimeo_falso, monkeypatch):
    pagina = "<script>var ytInitialPlayerResponse = {};</script>".format(json.dumps(
        {"videoDetails": {"videoId": CODIGO_YOUTUBE, "title": "Me at the zoo", "author": "jawed", "lengthSeconds": "19"}}
    ))
    monkeypatch.setattr(youtube, "baixar_pagina", lambda codigo: pagina)
    criar_generalista(cliente, criar_projeto(cliente.usuario_id), "https://youtu.be/" + CODIGO_YOUTUBE)
    tarefa = Tarefa.query.one()
    assert tarefa.video.plataforma == "youtube"

    cliente.post("/tarefas/{}/editar".format(tarefa.id), data={
        "nome": tarefa.nome, "prioridade": tarefa.prioridade, "projeto_id": tarefa.projeto_id,
        "secoes": json.dumps(["video"]), "video_endereco": ENDERECO,
    }, content_type="multipart/form-data", follow_redirects=True)

    video = db.session.get(VideoDoYoutube, tarefa.id)
    assert (video.plataforma, video.codigo, video.endereco_da_miniatura) == ("vimeo", NUMERO, MINIATURA)
    assert vimeo_falso["pedidos"] == [NUMERO]


def test_dialogos_falam_do_youtube_e_do_vimeo(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)

    assert "Novo vídeo do YouTube ou do Vimeo" in html
    assert html.count("Endereço do vídeo no YouTube ou no Vimeo") == 2
    assert "https://vimeo.com/..." in html


def test_politica_de_conteudo_libera_o_vimeo(cliente):
    politica = cliente.get("/login").headers["Content-Security-Policy"]

    assert "https://i.vimeocdn.com" in politica and "frame-src https://www.youtube-nocookie.com https://player.vimeo.com" in politica


@pytest.mark.so_sqlite
def test_atualizar_banco_cria_as_colunas_do_vimeo(app):
    with db.engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE video_do_youtube DROP COLUMN plataforma"))
        conexao.execute(text("ALTER TABLE video_do_youtube DROP COLUMN endereco_da_miniatura"))

    atualizar_banco()

    colunas = {coluna["name"]: coluna for coluna in inspect(db.engine).get_columns("video_do_youtube")}
    assert "plataforma" in colunas and "endereco_da_miniatura" in colunas


def test_versao_do_quadro_muda_com_a_plataforma(cliente, criar_projeto, vimeo_falso, sem_youtube):
    criar(cliente, criar_projeto(cliente.usuario_id))
    antes = cliente.get("/api/quadro/versao").get_json()["versao"]
    video = VideoDoYoutube.query.one()
    video.endereco_da_miniatura = MINIATURA + "&y=2"
    db.session.commit()

    assert cliente.get("/api/quadro/versao").get_json()["versao"] != antes
