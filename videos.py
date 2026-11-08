# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Os vídeos aceitos pelo sistema: identifica a plataforma pelo endereço e lê as informações nela.

As funções de youtube.py e vimeo.py são chamadas pelo módulo, na hora, para os testes poderem
trocar o acesso à internet (youtube.baixar_da_api, youtube.baixar_pagina e vimeo.baixar_dados).
"""
from flask import current_app

import vimeo
import youtube
from youtube import EnderecoInvalido

YOUTUBE = "youtube"
VIMEO = "vimeo"
NOMES_DAS_PLATAFORMAS = {YOUTUBE: "YouTube", VIMEO: "Vimeo"}
MODULOS = {YOUTUBE: youtube, VIMEO: vimeo}


def identificar(endereco):
    """(plataforma, código) do vídeo, ou EnderecoInvalido se o endereço não for de nenhuma delas."""
    for plataforma, modulo in MODULOS.items():
        try:
            return plataforma, modulo.codigo_do_video(endereco)
        except EnderecoInvalido:
            continue
    raise EnderecoInvalido


def miniatura(plataforma, codigo, endereco_da_miniatura=""):
    if plataforma == VIMEO:
        return endereco_da_miniatura
    return "https://i.ytimg.com/vi/{}/mqdefault.jpg".format(codigo)


def endereco_do_player(plataforma, codigo):
    if plataforma == VIMEO:
        return vimeo.endereco_do_player(codigo)
    # O domínio sem cookies só grava cookies quando o vídeo é tocado.
    return "https://www.youtube-nocookie.com/embed/{}".format(codigo)


def chave_do_youtube():
    """A chave da API do YouTube salva em Configurações, já decifrada, ou vazia."""
    # Importados aqui: models.py importa este módulo.
    from extensions import db
    from models import ConfiguracaoDoYoutube
    from seguranca import decifrar

    salva = db.session.get(ConfiguracaoDoYoutube, 1)
    if salva is None or not salva.chave:
        return ""
    return decifrar(salva.chave, current_app.config["SECRET_KEY"])


def informacoes(plataforma, codigo):
    """As informações do vídeo, com "plataforma" e "miniatura" (vazia no YouTube, que a monta pelo código)."""
    if plataforma == YOUTUBE:
        dados = dict(youtube.informacoes_do_codigo(codigo, chave_do_youtube()))
    else:
        dados = dict(MODULOS[plataforma].informacoes_do_codigo(codigo))
    dados["plataforma"] = plataforma
    dados.setdefault("miniatura", "")
    return dados


def buscar_informacoes(endereco):
    return informacoes(*identificar(endereco))
