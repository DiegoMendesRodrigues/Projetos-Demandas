# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Lê da página pública do vídeo o autor, o título, a descrição, a data de publicação e a duração.

Não usa a API do Google nem chave: os dados vêm do objeto ytInitialPlayerResponse da página,
o mesmo que o navegador usa. Se o YouTube mudar a página, a leitura falha com ErroNasInformacoes.
O servidor nunca acessa o endereço digitado: só o endereço oficial montado com o código do vídeo.
"""
import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from urllib.parse import parse_qs, urlparse

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


class EnderecoInvalido(ValueError):
    pass


class ErroDeConexao(Exception):
    pass


class ErroNasInformacoes(Exception):
    pass


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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ProjetosEDemandas",
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


def dados_do_player(pagina):
    inicio = pagina.find(MARCA_DOS_DADOS)
    if inicio < 0:
        raise ErroNasInformacoes
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
    texto = formato.get("publishDate") or formato.get("uploadDate")
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
        # O vídeo não existe, é privado ou a página mudou de formato.
        raise ErroNasInformacoes
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


def informacoes_do_codigo(codigo):
    return informacoes_da_pagina(baixar_pagina(codigo), codigo)


def buscar_informacoes(endereco):
    return informacoes_do_codigo(codigo_do_video(endereco))
