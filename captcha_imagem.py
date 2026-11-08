# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""CAPTCHA de imagem gerado pela própria aplicação, sem serviço externo.

A resposta fica no banco, em DesafioCaptcha, e não na sessão: o cookie de sessão do Flask
é assinado, mas pode ser lido por quem o tem. Cada desafio vale uma única tentativa.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from captcha.image import ImageCaptcha
from flask import session

from config import FUSO_HORARIO
from extensions import db
from models import DesafioCaptcha

# Sem 0/O, 1/I e outras letras que se confundem na imagem.
ALFABETO = "ABCDEFGHJKLMNPRSTUVWXYZ23456789"
TAMANHO_DO_CODIGO = 5
VALIDADE = timedelta(minutes=10)
# A largura alinha o botão Gerar outra imagem com os campos da tela de login (style.css, .captcha).
LARGURA, ALTURA = 332, 70
CHAVE_DA_SESSAO = "captcha"


def agora():
    return datetime.now(FUSO_HORARIO).replace(tzinfo=None)


def resumo(codigo):
    return hashlib.sha256(codigo.strip().upper().encode()).hexdigest()


def sortear_codigo():
    return "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO_DO_CODIGO))


def descartar_desafio_da_sessao():
    token = session.pop(CHAVE_DA_SESSAO, None)
    desafio = db.session.get(DesafioCaptcha, token) if token else None
    if desafio:
        db.session.delete(desafio)
    return desafio


def novo_desafio():
    """Cria o desafio desta sessão, no lugar do anterior, e devolve a imagem em PNG."""
    descartar_desafio_da_sessao()
    DesafioCaptcha.query.filter(DesafioCaptcha.criado_em < agora() - VALIDADE).delete()
    codigo = sortear_codigo()
    token = secrets.token_hex(16)
    db.session.add(DesafioCaptcha(token=token, resposta_hash=resumo(codigo), criado_em=agora()))
    db.session.commit()
    session[CHAVE_DA_SESSAO] = token
    return ImageCaptcha(width=LARGURA, height=ALTURA).generate(codigo, format="png").getvalue()


def conferir_resposta(resposta):
    """Confere e consome o desafio da sessão: acertando ou não, ele não vale de novo."""
    desafio = descartar_desafio_da_sessao()
    db.session.commit()
    if not desafio or not resposta or desafio.criado_em < agora() - VALIDADE:
        return False
    return hmac.compare_digest(desafio.resposta_hash, resumo(resposta))
