# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import io
import json
import urllib.error
from datetime import date

import pytest

import videos
import youtube
from extensions import db
from models import ConfiguracaoDoYoutube, ConfiguracaoEmail, Usuario, VideoDoYoutube
from seguranca import cifrar, decifrar

CODIGO = "jNQXAC9IVRw"
CHAVE = "AIzaSy-chave-de-teste-123"
# Guardada antes de o conftest.py trocá-la em cada teste.
BAIXAR_DA_API = youtube.baixar_da_api


def resposta_da_api(codigo=CODIGO, **resumo):
    dados = {"title": "Me at the zoo", "channelTitle": "jawed", "description": "Elefantes",
             "publishedAt": "2005-04-24T03:31:52Z"}
    dados.update(resumo)
    return {"items": [{"id": codigo, "snippet": dados, "contentDetails": {"duration": "PT19S"}}]}


@pytest.fixture
def api_falsa(monkeypatch):
    estado = {"dados": resposta_da_api(), "pedidos": [], "erro": None}

    def baixar(codigo, chave):
        estado["pedidos"].append((codigo, chave))
        if estado["erro"]:
            raise estado["erro"]
        return estado["dados"]

    monkeypatch.setattr(youtube, "baixar_da_api", baixar)
    return estado


@pytest.fixture
def pagina_bloqueada(monkeypatch):
    """A página do vídeo como nos servidores de datacenter: a verificação de robô."""
    pedidos = []

    def baixar(codigo):
        pedidos.append(codigo)
        return '<script>var ytInitialPlayerResponse = {"playabilityStatus": {"status": "LOGIN_REQUIRED"}};</script>'

    monkeypatch.setattr(youtube, "baixar_pagina", baixar)
    return pedidos


@pytest.fixture
def administrador(cliente):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()
    return cliente


def salvar_chave(app, chave=CHAVE):
    db.session.add(ConfiguracaoDoYoutube(id=1, chave=cifrar(chave, app.config["SECRET_KEY"])))
    db.session.commit()


def enviar_chave(cliente, **dados):
    return cliente.post("/administracao/configuracoes/youtube", data={"chave": CHAVE, "acao": "salvar", **dados})


# ---------- Leitura pela API


def test_le_as_informacoes_da_api():
    assert youtube.informacoes_da_api(resposta_da_api(), CODIGO) == {
        "codigo": CODIGO, "autor": "jawed", "titulo": "Me at the zoo", "descricao": "Elefantes",
        "publicacao": date(2005, 4, 24), "duracao": "0:19",
    }


@pytest.mark.parametrize("texto, segundos", [
    ("PT19S", 19), ("PT12M34S", 754), ("PT1H2M5S", 3725), ("P1DT2H", 93600), ("P0D", 0), ("", None), ("x", None),
])
def test_duracao_iso(texto, segundos):
    assert youtube.duracao_iso(texto) == segundos


def test_data_da_api_no_fuso_de_sao_paulo():
    # 01:30 em UTC ainda é o dia anterior em São Paulo.
    assert youtube.data_em_sao_paulo("2020-01-02T01:30:00Z") == date(2020, 1, 1)


@pytest.mark.parametrize("dados", [
    {}, {"items": []}, resposta_da_api(codigo="outroCodigo"), resposta_da_api(title=" "),
])
def test_api_sem_o_video_e_erro_nas_informacoes(dados):
    with pytest.raises(youtube.ErroNasInformacoes):
        youtube.informacoes_da_api(dados, CODIGO)


def test_com_a_chave_usa_a_api_e_nao_a_pagina(api_falsa, pagina_bloqueada):
    dados = youtube.informacoes_do_codigo(CODIGO, CHAVE)

    assert dados["duracao"] == "0:19" and dados["descricao"] == "Elefantes"
    assert api_falsa["pedidos"] == [(CODIGO, CHAVE)]
    assert pagina_bloqueada == []


def test_sem_a_chave_nao_usa_a_api(api_falsa, pagina_bloqueada):
    with pytest.raises(youtube.ErroNasInformacoes):
        youtube.informacoes_do_codigo(CODIGO)
    assert api_falsa["pedidos"] == []


def test_falha_na_api_tenta_a_pagina_sem_registrar_a_chave(api_falsa, pagina_bloqueada, monkeypatch, caplog):
    api_falsa["erro"] = youtube.ChaveRecusada("API respondeu 400 keyInvalid")
    monkeypatch.setattr(youtube, "baixar_oembed", lambda codigo: {"title": "Me at the zoo", "author_name": "jawed"})

    dados = youtube.informacoes_do_codigo(CODIGO, CHAVE)

    assert dados["titulo"] == "Me at the zoo" and dados["parcial"] is True
    assert pagina_bloqueada == [CODIGO]
    assert "keyInvalid" in caplog.text
    assert CHAVE not in caplog.text


class Resposta:
    def __init__(self, corpo):
        self.corpo = corpo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _tamanho):
        return self.corpo


def erro_http(codigo, motivo):
    corpo = json.dumps({"error": {"errors": [{"reason": motivo}]}}).encode()

    def recusar(requisicao, timeout):
        raise urllib.error.HTTPError(requisicao.full_url, codigo, "erro", {}, io.BytesIO(corpo))

    return recusar


def test_baixar_da_api_monta_o_endereco_com_o_codigo_e_a_chave(monkeypatch):
    pedidos = []

    def abrir(requisicao, timeout):
        pedidos.append(requisicao.full_url)
        return Resposta(json.dumps(resposta_da_api()).encode())

    monkeypatch.setattr(youtube.urllib.request, "urlopen", abrir)

    assert BAIXAR_DA_API(CODIGO, CHAVE) == resposta_da_api()
    assert pedidos == [
        "https://www.googleapis.com/youtube/v3/videos?part=snippet%2CcontentDetails&id={}&key={}".format(CODIGO, CHAVE)
    ]


@pytest.mark.parametrize("codigo, motivo", [(400, "keyInvalid"), (403, "accessNotConfigured"), (403, "forbidden")])
def test_chave_recusada(monkeypatch, codigo, motivo):
    monkeypatch.setattr(youtube.urllib.request, "urlopen", erro_http(codigo, motivo))

    with pytest.raises(youtube.ChaveRecusada) as erro:
        BAIXAR_DA_API(CODIGO, CHAVE)
    # O erro original tem o endereço com a chave: ele não segue adiante.
    assert motivo in str(erro.value) and CHAVE not in str(erro.value)
    assert erro.value.__cause__ is None and erro.value.__suppress_context__


@pytest.mark.parametrize("motivo", ["quotaExceeded", "rateLimitExceeded"])
def test_cota_esgotada_nao_e_chave_recusada(monkeypatch, motivo):
    monkeypatch.setattr(youtube.urllib.request, "urlopen", erro_http(403, motivo))

    with pytest.raises(youtube.ErroNasInformacoes):
        BAIXAR_DA_API(CODIGO, CHAVE)


def test_baixar_da_api_sem_rede(monkeypatch):
    def recusar(requisicao, timeout):
        raise OSError("sem rede")

    monkeypatch.setattr(youtube.urllib.request, "urlopen", recusar)
    with pytest.raises(youtube.ErroDeConexao):
        BAIXAR_DA_API(CODIGO, CHAVE)


# ---------- Chave salva


def test_chave_do_youtube_vazia_sem_configuracao(app):
    assert videos.chave_do_youtube() == ""


def test_chave_do_youtube_decifra_a_salva(app):
    salvar_chave(app)
    assert videos.chave_do_youtube() == CHAVE


def test_criar_video_usa_a_chave_salva(app, cliente, criar_projeto, api_falsa, pagina_bloqueada):
    salvar_chave(app)
    projeto = criar_projeto(cliente.usuario_id)

    resposta = cliente.post("/api/videos", json={"projeto_id": projeto.id, "endereco": "https://youtu.be/" + CODIGO})

    assert resposta.status_code == 201
    video = VideoDoYoutube.query.one()
    assert (video.duracao, video.descricao, video.publicado_em) == ("0:19", "Elefantes", date(2005, 4, 24))
    assert api_falsa["pedidos"] == [(CODIGO, CHAVE)]
    assert pagina_bloqueada == []


# ---------- Tela Configurações


def test_so_o_administrador_salva_a_chave(cliente, api_falsa):
    assert enviar_chave(cliente).status_code == 403
    assert ConfiguracaoDoYoutube.query.count() == 0


def test_configuracoes_mostra_a_secao_sem_a_chave(app, administrador):
    html = administrador.get("/administracao/configuracoes").get_data(as_text=True)
    assert 'id="youtube"' in html and "Nenhuma chave salva." in html
    assert "Remover a chave" not in html

    salvar_chave(app)
    html = administrador.get("/administracao/configuracoes").get_data(as_text=True)
    assert "Chave salva." in html and "Remover a chave" in html
    assert CHAVE not in html


def test_salvar_a_chave_confere_e_grava_cifrada(app, administrador, api_falsa):
    resposta = enviar_chave(administrador, chave=" " + CHAVE + " ")

    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/administracao/configuracoes#youtube")
    salva = db.session.get(ConfiguracaoDoYoutube, 1)
    assert salva.chave != CHAVE and decifrar(salva.chave, app.config["SECRET_KEY"]) == CHAVE
    assert api_falsa["pedidos"] == [(youtube.VIDEO_DE_TESTE, CHAVE)]
    # O envio de e-mails não precisa estar configurado.
    assert ConfiguracaoEmail.query.count() == 0


def test_chave_recusada_nao_e_salva(administrador, api_falsa):
    api_falsa["erro"] = youtube.ChaveRecusada("API respondeu 400 keyInvalid")

    resposta = enviar_chave(administrador)

    assert resposta.status_code == 200
    assert "O Google recusou esta chave." in resposta.get_data(as_text=True)
    assert ConfiguracaoDoYoutube.query.count() == 0


def test_sem_conexao_a_chave_e_salva_com_aviso(administrador, api_falsa):
    api_falsa["erro"] = youtube.ErroDeConexao()

    resposta = administrador.post(
        "/administracao/configuracoes/youtube", data={"chave": CHAVE, "acao": "salvar"}, follow_redirects=True
    )

    assert "não foi possível conferi-la no Google agora" in resposta.get_data(as_text=True)
    assert ConfiguracaoDoYoutube.query.count() == 1


def test_chave_vazia_e_recusada(administrador, api_falsa):
    resposta = enviar_chave(administrador, chave="  ")

    assert resposta.status_code == 200
    assert "Informe a chave da API do YouTube." in resposta.get_data(as_text=True)
    assert api_falsa["pedidos"] == []


def test_chave_longa_demais_e_recusada(administrador, api_falsa):
    assert enviar_chave(administrador, chave="x" * 101).status_code == 200
    assert ConfiguracaoDoYoutube.query.count() == 0
    assert api_falsa["pedidos"] == []


def test_erro_na_chave_mantem_os_dados_do_email(administrador, api_falsa):
    db.session.add(ConfiguracaoEmail(id=1, servidor="smtp.exemplo.com", porta=587, usar_tls=True, usuario="u",
                                     senha="x", email_envio="envio@exemplo.com", nome_envio="Envio"))
    db.session.commit()

    html = enviar_chave(administrador, chave="").get_data(as_text=True)

    assert 'value="smtp.exemplo.com"' in html
    assert "Informe a senha." not in html


def test_remover_a_chave(app, administrador):
    salvar_chave(app)

    resposta = administrador.post("/administracao/configuracoes/youtube", data={"acao": "remover"}, follow_redirects=True)

    assert "Chave da API do YouTube removida." in resposta.get_data(as_text=True)
    assert ConfiguracaoDoYoutube.query.count() == 0
