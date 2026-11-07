# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Lê do oEmbed público do Vimeo o autor, o título, a descrição, a data de envio, a duração e a miniatura.

Não usa chave da API: o oEmbed é o serviço que o próprio Vimeo oferece para incorporar vídeos.
O servidor nunca acessa o endereço digitado: só o oEmbed, com o endereço oficial montado a partir
do número do vídeo (e do código de privacidade dos vídeos não listados).
"""
import json
import re
import urllib.error
import urllib.request
from datetime import date
from urllib.parse import parse_qs, quote, urlparse

from youtube import (
    LIMITE_AUTOR,
    LIMITE_DURACAO,
    LIMITE_TITULO,
    LIMITE_URL,
    TEMPO_LIMITE,
    EnderecoInvalido,
    ErroDeConexao,
    ErroNasInformacoes,
    formatar_duracao,
    ler_com_limite,
)

DOMINIOS = {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}
NUMERO = re.compile(r"[0-9]{1,12}")
# Os vídeos não listados têm, além do número, um código de privacidade (vimeo.com/123/abc123def).
CODIGO_DE_PRIVACIDADE = re.compile(r"[0-9a-f]{6,20}")
SEPARADOR = ":"
MINIATURA = re.compile(r"https://i\.vimeocdn\.com/[A-Za-z0-9_./%?=&-]{1,280}")
LARGURA_DA_MINIATURA = 640


def codigo_do_video(endereco):
    """O número do vídeo, seguido de ":" e do código de privacidade quando houver.

    Aceita vimeo.com/123, vimeo.com/123/abc, vimeo.com/channels/x/123, vimeo.com/groups/x/videos/123,
    vimeo.com/showcase/x/video/123 e player.vimeo.com/video/123?h=abc.
    """
    endereco = (endereco or "").strip()
    if not endereco or len(endereco) > LIMITE_URL:
        raise EnderecoInvalido
    if "://" not in endereco:
        endereco = "https://" + endereco
    partes = urlparse(endereco)
    if partes.scheme not in ("http", "https") or (partes.hostname or "").lower() not in DOMINIOS:
        raise EnderecoInvalido
    caminho = [parte for parte in partes.path.split("/") if parte]
    numericas = [indice for indice, parte in enumerate(caminho) if NUMERO.fullmatch(parte)]
    # Em showcase/<álbum>/video/<número> e groups/<nome>/videos/<número>, o vídeo vem depois de "video(s)".
    depois_de_video = [indice for indice in numericas if indice and caminho[indice - 1] in ("video", "videos")]
    posicao = (depois_de_video or numericas or [None])[0]
    if posicao is None:
        raise EnderecoInvalido
    numero = caminho[posicao]
    privacidade = (parse_qs(partes.query).get("h") or [None])[0]
    if not privacidade and posicao + 1 < len(caminho):
        privacidade = caminho[posicao + 1]
    if privacidade and not CODIGO_DE_PRIVACIDADE.fullmatch(privacidade):
        privacidade = None
    return numero + (SEPARADOR + privacidade if privacidade else "")


def partes_do_codigo(codigo):
    numero, _, privacidade = codigo.partition(SEPARADOR)
    return numero, privacidade


def endereco_oficial(codigo):
    numero, privacidade = partes_do_codigo(codigo)
    return "https://vimeo.com/{}".format(numero + ("/" + privacidade if privacidade else ""))


def endereco_do_player(codigo):
    # dnt=1: o player não grava cookies nem dados de navegação de quem assiste.
    numero, privacidade = partes_do_codigo(codigo)
    return "https://player.vimeo.com/video/{}?{}dnt=1".format(numero, "h={}&".format(privacidade) if privacidade else "")


def baixar_dados(codigo):
    requisicao = urllib.request.Request(
        "https://vimeo.com/api/oembed.json?url={}&width={}".format(
            quote(endereco_oficial(codigo), safe=""), LARGURA_DA_MINIATURA
        ),
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ProjetosEDemandas"},
    )
    try:
        with urllib.request.urlopen(requisicao, timeout=TEMPO_LIMITE) as resposta:
            return json.loads(ler_com_limite(resposta).decode("utf-8", "replace"))
    except urllib.error.HTTPError as erro:
        # 404: o vídeo não existe; 403: é privado ou não pode ser incorporado.
        raise ErroNasInformacoes from erro
    except ValueError as erro:
        raise ErroNasInformacoes from erro
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        raise ErroDeConexao from erro


def data_de_envio(dados):
    """A data em que o vídeo foi enviado, como "2013-10-15 14:08:29", ou None."""
    texto = dados.get("upload_date")
    if not isinstance(texto, str):
        return None
    try:
        return date.fromisoformat(texto.strip()[:10])
    except ValueError:
        return None


def informacoes_dos_dados(dados, codigo):
    numero, _ = partes_do_codigo(codigo)
    titulo = str(dados.get("title") or "").strip()
    if not isinstance(dados, dict) or str(dados.get("video_id")) != numero or not titulo:
        raise ErroNasInformacoes
    try:
        duracao = formatar_duracao(dados.get("duration") or 0)
    except (TypeError, ValueError):
        duracao = ""
    miniatura = str(dados.get("thumbnail_url") or "")
    return {
        "plataforma": "vimeo",
        "codigo": codigo,
        "autor": str(dados.get("author_name") or "").strip()[:LIMITE_AUTOR],
        "titulo": titulo[:LIMITE_TITULO],
        "descricao": str(dados.get("description") or "").strip(),
        "publicacao": data_de_envio(dados),
        "duracao": duracao[:LIMITE_DURACAO],
        # Só miniaturas do próprio Vimeo, como a política de conteúdo das páginas permite.
        "miniatura": miniatura if MINIATURA.fullmatch(miniatura) else "",
    }


def informacoes_do_codigo(codigo):
    return informacoes_dos_dados(baixar_dados(codigo), codigo)
