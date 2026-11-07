# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Área externa: as páginas abertas a qualquer visitante, com o menu de navegação abaixo do cabeçalho.

Projetos & Demandas (apresentação), Planos (lidos do banco), Manual e Atendimento (formulário
que envia um e-mail com a configuração de Administração > Configurações).
"""
import logging

from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_mail import Message

from extensions import mail
from forms import AtendimentoForm
from models import LIMITES_DO_PLANO, PlanoDeUsuario

publico = Blueprint("publico", __name__)
registro = logging.getLogger(__name__)

# Itens do menu da área externa, na ordem em que aparecem.
MENU_PUBLICO = [
    ("publico.apresentacao", "Projetos & Demandas"),
    ("publico.planos", "Planos"),
    ("publico.manual", "Manual"),
    ("publico.atendimento", "Atendimento"),
]
# Como cada limite do plano aparece na tabela da página Planos.
COLUNAS_DOS_PLANOS = {
    "categorias": "Categorias",
    "projetos": "Projetos",
    "atividades": "Demandas",
    "listas_de_tarefas": "Listas de tarefas",
    "videos": "Vídeos",
}
ASSUNTO_DO_ATENDIMENTO = "Atendimento - {}"
MENSAGEM_ENVIADA = "Mensagem enviada. Nossa equipe vai responder no e-mail informado."
ATENDIMENTO_INDISPONIVEL = (
    "O envio de mensagens está indisponível no momento. Tente novamente mais tarde."
)


def ordem_dos_planos(plano):
    """Do menor para o maior: o armazenamento e, no empate, os limites; Ilimitadas é o maior."""
    limites = [float("inf") if getattr(plano, chave) is None else getattr(plano, chave) for chave in LIMITES_DO_PLANO]
    return [plano.armazenamento_mb] + limites


def linhas_dos_planos():
    """Os planos cadastrados pelo administrador, sempre lidos do banco."""
    linhas = []
    for plano in sorted(PlanoDeUsuario.query.all(), key=ordem_dos_planos):
        linhas.append({
            "nome": plano.nome,
            "padrao": plano.padrao,
            "armazenamento_mb": plano.armazenamento_mb,
            "limites": [
                (rotulo, getattr(plano, chave)) for chave, rotulo in COLUNAS_DOS_PLANOS.items()
            ],
        })
    return linhas


def envio_configurado():
    return bool(current_app.config.get("MAIL_SERVER"))


def enviar_atendimento(dados):
    """O remetente e o destinatário são o e-mail de envio de Administração > Configurações; a
    resposta vai para o visitante (Reply-To)."""
    remetente = current_app.config["MAIL_DEFAULT_SENDER"]
    destinatario = remetente[1] if isinstance(remetente, (tuple, list)) else remetente
    mensagem = Message(
        # Sem quebras de linha, que o Flask-Mail recusa no assunto.
        subject=ASSUNTO_DO_ATENDIMENTO.format(" ".join(dados["nome"].split())),
        recipients=[destinatario],
        reply_to=dados["email"],
        body=render_template("publico/email/atendimento.txt", **dados),
        html=render_template("publico/email/atendimento.html", **dados),
    )
    mail.send(mensagem)


@publico.app_context_processor
def menu_publico():
    return {"menu_publico": MENU_PUBLICO}


@publico.route("/projetos-e-demandas")
def apresentacao():
    return render_template("publico/apresentacao.html")


@publico.route("/planos")
def planos():
    return render_template(
        "publico/planos.html", planos=linhas_dos_planos(), colunas=list(COLUNAS_DOS_PLANOS.values())
    )


@publico.route("/manual")
def manual():
    return render_template("publico/manual.html")


@publico.route("/atendimento", methods=["GET", "POST"])
def atendimento():
    form = AtendimentoForm()
    if form.validate_on_submit():
        # Campo invisível para pessoas: preenchido, é um robô. Ele vê a mesma resposta.
        if form.site.data:
            flash(MENSAGEM_ENVIADA, "sucesso")
            return redirect(url_for("publico.atendimento"))
        if not envio_configurado():
            flash(ATENDIMENTO_INDISPONIVEL, "erro")
            return render_template("publico/atendimento.html", form=form)
        dados = {
            "nome": form.nome.data,
            "email": form.email.data,
            "telefone": form.telefone.data,
            "mensagem": form.mensagem.data,
        }
        try:
            enviar_atendimento(dados)
        except Exception:  # noqa: BLE001 - uma falha do SMTP vira uma mensagem ao visitante.
            registro.exception("Falha ao enviar a mensagem do Atendimento")
            flash(ATENDIMENTO_INDISPONIVEL, "erro")
            return render_template("publico/atendimento.html", form=form)
        flash(MENSAGEM_ENVIADA, "sucesso")
        return redirect(url_for("publico.atendimento"))
    return render_template("publico/atendimento.html", form=form)
