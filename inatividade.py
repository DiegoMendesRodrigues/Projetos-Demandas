# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Exclusão das contas sem uso, pelo prazo do plano (Dias de Inatividade para a Exclusão da Conta).

O prazo conta a partir do último acesso (`Usuario.ultimo_acesso`, gravado no login e no uso do
sistema por `registrar_acesso`, em seguranca.py). Com o plano de 15 dias, a conta que passa de
15 dias sem uso é excluída com tudo o que é dela (`apagar_conta`). As contas de administradores
nunca são excluídas, e Ilimitado (vazio) desliga a exclusão no plano.

Com o envio de e-mails configurado, 3 dias antes do fim do prazo sai um aviso, e a exclusão só
acontece depois de passados 3 dias inteiros do aviso, mesmo que ele tenha saído atrasado. Usar
o sistema de novo apaga o aviso. Roda na tarefa periódica de `iniciar_avisos` (avisos.py).
"""
import logging
from datetime import timedelta

from flask_mail import Message
from flask import render_template
from sqlalchemy import false

from avisos import email_configurado
from extensions import db, mail
from models import PlanoDeUsuario, Usuario
from routes import apagar_conta

registro = logging.getLogger(__name__)

ANTECEDENCIA_DO_AVISO = timedelta(days=3)
ASSUNTO_DO_AVISO = "Projetos & Demandas: sua conta será excluída por inatividade"


def prazo_de_inatividade(usuario):
    """Quanto tempo a conta pode ficar sem uso, ou None quando ela nunca é excluída."""
    if usuario.administrador or usuario.plano is None or usuario.plano.dias_de_inatividade is None:
        return None
    return timedelta(days=usuario.plano.dias_de_inatividade)


def fim_do_prazo(usuario):
    """O momento a partir do qual a conta sem uso pode ser excluída, ou None."""
    prazo = prazo_de_inatividade(usuario)
    if prazo is None or usuario.ultimo_acesso is None:
        return None
    return usuario.ultimo_acesso + prazo


def data_da_exclusao(usuario, momento):
    """A data informada no aviso: o fim do prazo, mas nunca antes de 3 dias depois do aviso."""
    return max(fim_do_prazo(usuario), momento + ANTECEDENCIA_DO_AVISO)


def contas_com_prazo():
    """As contas que podem ser excluídas: fora os administradores e os planos Ilimitado."""
    return (
        Usuario.query.join(PlanoDeUsuario, Usuario.plano_id == PlanoDeUsuario.id)
        .filter(Usuario.administrador == false(), PlanoDeUsuario.dias_de_inatividade.isnot(None))
        .all()
    )


def enviar_avisos_de_exclusao(momento):
    """Avisa por e-mail as contas a 3 dias (ou menos) do fim do prazo; devolve quantos avisos saíram."""
    if not email_configurado():
        return 0
    enviados = 0
    for usuario in contas_com_prazo():
        fim = fim_do_prazo(usuario)
        if fim is None or usuario.aviso_de_exclusao_em is not None or momento < fim - ANTECEDENCIA_DO_AVISO:
            continue
        dados = {
            "pessoa": usuario,
            "dias": usuario.plano.dias_de_inatividade,
            "exclusao": data_da_exclusao(usuario, momento),
        }
        mensagem = Message(
            subject=ASSUNTO_DO_AVISO,
            recipients=[usuario.email],
            body=render_template("avisos/exclusao.txt", **dados),
            html=render_template("avisos/exclusao.html", **dados),
        )
        try:
            mail.send(mensagem)
        except Exception:  # noqa: BLE001 - sem o aviso, a conta não é excluída; tenta de novo depois.
            registro.exception("Falha ao enviar o aviso de exclusão por inatividade para %s", usuario.email)
            continue
        usuario.aviso_de_exclusao_em = momento
        db.session.commit()
        enviados += 1
    return enviados


def pode_excluir(usuario, momento, com_aviso):
    fim = fim_do_prazo(usuario)
    if fim is None or momento <= fim:
        return False
    if not com_aviso:
        return True
    # Com o envio configurado, só depois do aviso e de 3 dias inteiros desde ele.
    aviso = usuario.aviso_de_exclusao_em
    return aviso is not None and momento >= aviso + ANTECEDENCIA_DO_AVISO


def excluir_contas_inativas(momento):
    """Exclui as contas que passaram do prazo de inatividade do plano; devolve quantas."""
    com_aviso = email_configurado()
    excluidas = 0
    for usuario_id in [usuario.id for usuario in contas_com_prazo()]:
        usuario = db.session.get(Usuario, usuario_id)
        if usuario is None:
            continue
        if usuario.ultimo_acesso is None:
            # Conta sem registro de acesso: o prazo começa a contar agora.
            usuario.ultimo_acesso = momento
            db.session.commit()
            continue
        if not pode_excluir(usuario, momento, com_aviso):
            continue
        email, ultimo_acesso = usuario.email, usuario.ultimo_acesso
        try:
            apagar_conta(usuario)
        except Exception:  # noqa: BLE001 - uma falha não pode parar as demais contas.
            db.session.rollback()
            registro.exception("Falha ao excluir a conta inativa %s", email)
            continue
        registro.warning("Conta %s excluída por inatividade (último acesso em %s)", email, ultimo_acesso)
        excluidas += 1
    return excluidas


def cuidar_das_contas_inativas(momento):
    """Os avisos primeiro: um aviso que acaba de sair segura a exclusão por 3 dias."""
    enviar_avisos_de_exclusao(momento)
    return excluir_contas_inativas(momento)
