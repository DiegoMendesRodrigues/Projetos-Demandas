# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Lê da página pública do vídeo o autor, o título, a descrição, a data de publicação e a duração.

Não usa a API do Google nem chave: os dados vêm do objeto ytInitialPlayerResponse da página,
o mesmo que o navegador usa. Se o YouTube mudar a página, a leitura falha com ErroNasInformacoes.
O servidor nunca acessa o endereço digitado: só o endereço oficial montado com o código do vídeo.

Com a chave da API do YouTube salva em Configurações, os dados vêm primeiro da API oficial (Data
API v3, informacoes_da_api), que não passa pela verificação de robô. Sem a chave, ou se a API
falhar, vale a página pública.

Em servidores de datacenter, o YouTube costuma trocar a página pela verificação "confirme que você
não é um robô", sem os dados do vídeo. Nesse caso (e em qualquer falha na página), o título e o
autor vêm do oEmbed público (www.youtube.com/oembed), que não passa por essa verificação; a
descrição, a data de publicação e a duração ficam vazias. O motivo da falha vai para o log, nunca
com a chave.
"""
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse

from config import FUSO_HORARIO

LIMITE_URL = 400
LIMITE_AUTOR = 100
LIMITE_TITULO = 200
LIMITE_DURACAO = 20
TEMPO_LIMITE = 10
# A página de um vídeo tem cerca de 1 MB; acima disto, a resposta não é de um vídeo.
TAMANHO_MAXIMO_DA_RESPOSTA = 8 * 1024 * 1024
CODIGO = re.compile(r"[A-Za-z0-9_-]{11}")
DOMINIOS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}
MARCA_DOS_DADOS = "ytInitialPlayerResponse"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ProjetosEDemandas"
ENDERECO_DA_API = "https://www.googleapis.com/youtube/v3/videos"
LIMITE_CHAVE = 100
# Um vídeo público conhecido ("Me at the zoo"), usado para conferir a chave ao salvá-la.
VIDEO_DE_TESTE = "jNQXAC9IVRw"
DURACAO_ISO = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?")

registro = logging.getLogger(__name__)


class EnderecoInvalido(ValueError):
    pass


class ErroDeConexao(Exception):
    pass


class ErroNasInformacoes(Exception):
    pass


class ChaveRecusada(Exception):
    """O Google recusou a chave da API (inválida, sem a YouTube Data API v3 ou restrita)."""


def ler_com_limite(resposta):
    """O corpo da resposta, sem guardar na memória mais que TAMANHO_MAXIMO_DA_RESPOSTA."""
    corpo = resposta.read(TAMANHO_MAXIMO_DA_RESPOSTA + 1)
    if len(corpo) > TAMANHO_MAXIMO_DA_RESPOSTA:
        raise ErroNasInformacoes
    return corpo


def codigo_do_video(endereco):
    """O código de 11 caracteres do vídeo, de qualquer forma comum de endereço do YouTube."""
    endereco = (endereco or "").strip()
    if not endereco or len(endereco) > LIMITE_URL:
        raise EnderecoInvalido
    if "://" not in endereco:
        endereco = "https://" + endereco
    partes = urlparse(endereco)
    dominio = (partes.hostname or "").lower()
    caminho = [parte for parte in partes.path.split("/") if parte]
    candidato = None
    if partes.scheme not in ("http", "https"):
        raise EnderecoInvalido
    if dominio == "youtu.be" and caminho:
        candidato = caminho[0]
    elif dominio in DOMINIOS:
        if caminho[:1] == ["watch"]:
            candidato = (parse_qs(partes.query).get("v") or [None])[0]
        elif len(caminho) >= 2 and caminho[0] in ("embed", "shorts", "live", "v"):
            candidato = caminho[1]
    if not candidato or not CODIGO.fullmatch(candidato):
        raise EnderecoInvalido
    return candidato


def endereco_oficial(codigo):
    return "https://www.youtube.com/watch?v={}".format(codigo)


def baixar_pagina(codigo):
    requisicao = urllib.request.Request(
        endereco_oficial(codigo),
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9",
            # Sem isto, em alguns países o YouTube devolve a página de consentimento de cookies.
            "Cookie": "CONSENT=YES+1; SOCS=CAI",
        },
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            return ler_com_limite(resposta).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ErroDeConexao from erro


def baixar_da_api(codigo, chave):
    """A resposta da API para o vídeo, montada só com o código e a chave."""
    requisicao = urllib.request.Request(
        "{}?{}".format(ENDERECO_DA_API, urlencode({"part": "snippet,contentDetails", "id": codigo, "key": chave})),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            return json.loads(ler_com_limite(resposta).decode("utf-8", "replace"))
    except urllib.error.HTTPError as erro:
        # O endereço do erro tem a chave: só o código HTTP e o motivo do Google seguem adiante.
        motivo = motivo_do_erro_da_api(erro)
        if erro.code in (400, 401, 403) and motivo not in ("quotaExceeded", "rateLimitExceeded", "dailyLimitExceeded"):
            raise ChaveRecusada("API respondeu {} {}".format(erro.code, motivo).strip()) from None
        raise ErroNasInformacoes("API respondeu {} {}".format(erro.code, motivo).strip()) from None
    except ValueError:
        raise ErroNasInformacoes("API sem JSON") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ErroDeConexao("sem conexão com a API") from None


def motivo_do_erro_da_api(erro):
    """O "reason" do erro do Google (keyInvalid, quotaExceeded...), ou vazio."""
    try:
        corpo = json.loads(erro.read(64 * 1024).decode("utf-8", "replace"))
        return str(corpo["error"]["errors"][0]["reason"])[:60]
    except Exception:  # noqa: BLE001 - sem o corpo, fica só o código HTTP.
        return ""


def duracao_iso(texto):
    """A duração da API ("PT1M2S", "P1DT2H") em segundos, ou None."""
    combinacao = DURACAO_ISO.fullmatch(texto or "")
    if not combinacao or not texto:
        return None
    dias, horas, minutos, segundos = (int(parte or 0) for parte in combinacao.groups())
    return ((dias * 24 + horas) * 60 + minutos) * 60 + segundos


def informacoes_da_api(dados, codigo):
    itens = dados.get("items") if isinstance(dados, dict) else None
    if not itens:
        # O vídeo não existe ou é privado.
        raise ErroNasInformacoes("API sem o vídeo")
    item = itens[0]
    resumo = item.get("snippet") or {}
    titulo = (resumo.get("title") or "").strip()
    if item.get("id") != codigo or not titulo:
        raise ErroNasInformacoes("API sem o título do vídeo")
    segundos = duracao_iso((item.get("contentDetails") or {}).get("duration"))
    return {
        "codigo": codigo,
        "autor": (resumo.get("channelTitle") or "").strip()[:LIMITE_AUTOR],
        "titulo": titulo[:LIMITE_TITULO],
        "descricao": (resumo.get("description") or "").strip(),
        "publicacao": data_em_sao_paulo(resumo.get("publishedAt")),
        "duracao": formatar_duracao(segundos)[:LIMITE_DURACAO] if segundos is not None else "",
    }


def conferir_chave(chave):
    """Confere a chave com um vídeo público: ChaveRecusada, ErroDeConexao ou nada (a chave vale)."""
    informacoes_da_api(baixar_da_api(VIDEO_DE_TESTE, chave), VIDEO_DE_TESTE)


def baixar_oembed(codigo):
    """Os dados do oEmbed público do vídeo (título e autor), montado só com o código."""
    requisicao = urllib.request.Request(
        "https://www.youtube.com/oembed?url={}&format=json".format(quote(endereco_oficial(codigo), safe="")),
        headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            return json.loads(ler_com_limite(resposta).decode("utf-8", "replace"))
    except urllib.error.HTTPError as erro:
        # 404: o vídeo não existe; 401 e 403: é privado ou não pode ser incorporado.
        raise ErroNasInformacoes("oEmbed respondeu {}".format(erro.code)) from erro
    except ValueError as erro:
        raise ErroNasInformacoes("oEmbed sem JSON") from erro
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ErroDeConexao from erro


def informacoes_do_oembed(dados, codigo):
    titulo = (dados.get("title") or "").strip() if isinstance(dados, dict) else ""
    if not titulo:
        raise ErroNasInformacoes("oEmbed sem título")
    return {
        "codigo": codigo,
        "autor": (dados.get("author_name") or "").strip()[:LIMITE_AUTOR],
        "titulo": titulo[:LIMITE_TITULO],
        "descricao": "",
        "publicacao": None,
        "duracao": "",
        # Sem a descrição, a data e a duração: quem grava mantém as que o vídeo já tinha.
        "parcial": True,
    }


def dados_do_player(pagina):
    inicio = pagina.find(MARCA_DOS_DADOS)
    if inicio < 0:
        raise ErroNasInformacoes("página sem {}".format(MARCA_DOS_DADOS))
    chave = pagina.find("{", inicio)
    try:
        dados, _ = json.JSONDecoder().raw_decode(pagina, chave)
    except ValueError as erro:
        raise ErroNasInformacoes from erro
    return dados


def formatar_duracao(segundos):
    horas, resto = divmod(int(segundos), 3600)
    minutos, segundos = divmod(resto, 60)
    if horas:
        return "{}:{:02d}:{:02d}".format(horas, minutos, segundos)
    return "{}:{:02d}".format(minutos, segundos)


def data_de_publicacao(dados):
    """A data em que o vídeo foi publicado, no fuso de São Paulo, ou None se a página não a trouxer.

    Vem do microformat da página, como "2005-04-23" ou "2005-04-23T20:31:52-07:00".
    """
    formato = (dados.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    return data_em_sao_paulo(formato.get("publishDate") or formato.get("uploadDate"))


def data_em_sao_paulo(texto):
    """A data de "2005-04-23" ou "2005-04-23T20:31:52-07:00" (ou com Z), no fuso de São Paulo, ou None."""
    if not isinstance(texto, str):
        return None
    try:
        momento = datetime.fromisoformat(texto.strip())
    except ValueError:
        try:
            return date.fromisoformat(texto.strip()[:10])
        except ValueError:
            return None
    if momento.tzinfo is not None:
        momento = momento.astimezone(FUSO_HORARIO)
    return momento.date()


def informacoes_da_pagina(pagina, codigo):
    dados = dados_do_player(pagina)
    detalhes = dados.get("videoDetails") or {}
    titulo = (detalhes.get("title") or "").strip()
    if detalhes.get("videoId") != codigo or not titulo:
        # O vídeo não existe, é privado, a página mudou de formato ou o YouTube pediu a verificação
        # de robô (playabilityStatus LOGIN_REQUIRED, comum nos servidores de datacenter).
        situacao = dados.get("playabilityStatus") or {}
        raise ErroNasInformacoes("página sem os dados do vídeo: {} {}".format(
            situacao.get("status") or "-", situacao.get("reason") or ""
        ).strip())
    try:
        duracao = formatar_duracao(detalhes.get("lengthSeconds") or 0)
    except (TypeError, ValueError):
        duracao = ""
    return {
        "codigo": codigo,
        "autor": (detalhes.get("author") or "").strip()[:LIMITE_AUTOR],
        "titulo": titulo[:LIMITE_TITULO],
        "descricao": (detalhes.get("shortDescription") or "").strip(),
        "publicacao": data_de_publicacao(dados),
        "duracao": duracao[:LIMITE_DURACAO],
    }


def descrever(erro):
    return erro.__class__.__name__ + (": {}".format(erro) if str(erro) else "")


def informacoes_do_codigo(codigo, chave=""):
    """Os dados completos da API (com a chave) ou da página do vídeo; se as duas falharem, o título
    e o autor do oEmbed."""
    if chave:
        try:
            return informacoes_da_api(baixar_da_api(codigo, chave), codigo)
        except (ChaveRecusada, ErroDeConexao, ErroNasInformacoes) as erro:
            registro.warning("YouTube: a API falhou no vídeo %s (%s); tentando a página", codigo, descrever(erro))
    try:
        return informacoes_da_pagina(baixar_pagina(codigo), codigo)
    except (ErroDeConexao, ErroNasInformacoes) as erro:
        motivo = erro
    try:
        dados = informacoes_do_oembed(baixar_oembed(codigo), codigo)
    except (ErroDeConexao, ErroNasInformacoes) as erro:
        registro.warning(
            "YouTube: sem as informações do vídeo %s (página: %s; oEmbed: %s)",
            codigo, descrever(motivo), descrever(erro),
        )
        # Vale o erro da página, a fonte principal: a falha de conexão continua informada como tal.
        raise motivo from erro
    registro.warning(
        "YouTube: a página do vídeo %s falhou (%s); título e autor vieram do oEmbed",
        codigo, descrever(motivo),
    )
    return dados


def buscar_informacoes(endereco):
    return informacoes_do_codigo(codigo_do_video(endereco))
