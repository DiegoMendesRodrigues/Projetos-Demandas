# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""E-mails de aviso dos cartões perto do vencimento e atrasados (área Automação do Meu Perfil).

Os avisos seguem as escolhas do proprietário do cartão: quem recebe e com quantos dias de
antecedência. Cada aviso vai uma única vez por pessoa e por Previsão de Execução: mudar a
data permite um novo aviso. A tarefa periódica de `iniciar_avisos` roda dentro do próprio app.
"""
import logging
import threading
import time
from datetime import timedelta

from flask import current_app, render_template
from flask_mail import Message
from sqlalchemy import false

from extensions import db, mail
from models import (
    ANTECEDENCIAS_DOS_AVISOS,
    TIPO_VIDEO,
    AvisoEnviado,
    Projeto,
    Tarefa,
)

registro = logging.getLogger(__name__)

# Atrasos mais antigos que isto não geram e-mail: evita uma enxurrada de avisos de cartões
# esquecidos quando o envio é ligado pela primeira vez.
ATRASO_MAXIMO_PARA_AVISAR = timedelta(days=1)
MAIOR_ANTECEDENCIA = max(dias for dias, _ in ANTECEDENCIAS_DOS_AVISOS)
ASSUNTOS = {
    "proximo": "Projetos & Demandas: “{}” vence em breve",
    "atrasado": "Projetos & Demandas: “{}” está atrasada",
}


def destinatarios(tarefa):
    """O proprietário e, se ele escolheu assim, o responsável atual do cartão."""
    proprietario = tarefa.proprietario
    pessoas = [proprietario]
    responsavel = tarefa.responsavel_atual
    if responsavel is not None and proprietario.avisa_o_responsavel:
        pessoas.append(responsavel)
    return pessoas


def tipo_do_aviso(tarefa, momento):
    """"proximo", "atrasado" ou None, pela Previsão de Execução e pela antecedência do proprietário."""
    previsao = tarefa.previsao_execucao
    if previsao <= momento:
        return "atrasado" if momento - previsao <= ATRASO_MAXIMO_PARA_AVISAR else None
    if previsao - timedelta(days=tarefa.proprietario.aviso_antecedencia) <= momento:
        return "proximo"
    return None


def email_configurado():
    return bool(current_app.config.get("MAIL_SERVER")) and bool(current_app.config.get("MAIL_DEFAULT_SENDER"))


def enviar_avisos(momento):
    """Envia os avisos pendentes e devolve quantos foram enviados."""
    if not email_configurado():
        return 0
    candidatas = (
        Tarefa.query.join(Projeto)
        .filter(
            Tarefa.tipo != TIPO_VIDEO,
            Tarefa.concluida_em.is_(None),
            Tarefa.previsao_execucao.isnot(None),
            Tarefa.previsao_execucao <= momento + timedelta(days=MAIOR_ANTECEDENCIA),
            Tarefa.previsao_execucao >= momento - ATRASO_MAXIMO_PARA_AVISAR,
            Projeto.concluida == false(),
        )
        .all()
    )
    enviados = 0
    for tarefa in candidatas:
        tipo = tipo_do_aviso(tarefa, momento)
        if tipo is None:
            continue
        for pessoa in destinatarios(tarefa):
            ja_enviado = AvisoEnviado.query.filter_by(
                tarefa_id=tarefa.id, usuario_id=pessoa.id, tipo=tipo, previsao=tarefa.previsao_execucao
            ).first()
            if ja_enviado:
                continue
            dados = {"pessoa": pessoa, "tarefa": tarefa, "tipo": tipo}
            mensagem = Message(
                # Sem quebras de linha, que o Flask-Mail recusa no assunto: o aviso falharia sempre.
                subject=ASSUNTOS[tipo].format(" ".join(tarefa.nome.split())),
                recipients=[pessoa.email],
                body=render_template("avisos/aviso.txt", **dados),
                html=render_template("avisos/aviso.html", **dados),
            )
            try:
                mail.send(mensagem)
            except Exception:  # noqa: BLE001 - uma falha de SMTP não pode parar os demais avisos.
                registro.exception("Falha ao enviar o aviso da demanda %s para %s", tarefa.id, pessoa.email)
                continue
            db.session.add(
                AvisoEnviado(tarefa_id=tarefa.id, usuario_id=pessoa.id, tipo=tipo, previsao=tarefa.previsao_execucao)
            )
            db.session.commit()
            enviados += 1
    return enviados


def iniciar_avisos(app, agora, limpar=None):
    """Roda `enviar_avisos` a cada AVISOS_INTERVALO segundos, numa thread do próprio app.

    `limpar(momento)`, se informada, roda antes de cada rodada, mesmo sem o envio de e-mails
    configurado: é a limpeza das imagens da descrição que ficaram sem uso.
    """

    def repetir():
        time.sleep(app.config["AVISOS_PRIMEIRA_EXECUCAO"])
        while True:
            try:
                with app.app_context():
                    if limpar:
                        limpar(agora())
                    enviar_avisos(agora())
                    db.session.remove()
            except Exception:  # noqa: BLE001 - a tarefa precisa continuar viva.
                registro.exception("Falha na rodada de avisos")
            time.sleep(app.config["AVISOS_INTERVALO"])

    tarefa = threading.Thread(target=repetir, name="avisos-de-vencimento", daemon=True)
    tarefa.start()
    return tarefa
