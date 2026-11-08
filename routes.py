# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import hashlib
import html
import json
import os
import re
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_security import auth_required, current_user, hash_password, url_for_security
from flask_wtf import FlaskForm
from sqlalchemy import and_, false, func, or_, select, true

from banco import TIPOS_DE_BANCO, tipo_da_url
from captcha_imagem import novo_desafio
from foto_do_perfil import FotoInvalida, preparar_foto
from config import FUSO_HORARIO, LIMITE_ANEXOS, TAMANHO_MAXIMO_ANEXO, seguranca_smtp
from extensions import db, mail, security
from seguranca import cifrar, decifrar
import videos
from youtube import EnderecoInvalido, ErroDeConexao, ErroNasInformacoes
from icones_grupo import CATEGORIAS_DE_ICONE_GRUPO, ICONES_GRUPO
from forms import (
    IMAGEM_DA_DESCRICAO,
    AnexoForm,
    CategoriaForm,
    ConfiguracoesForm,
    GrupoForm,
    ProjetoForm,
    PerfilForm,
    PlanoForm,
    TarefaForm,
    UsuarioForm,
    VideoForm,
    nome_de_arquivo,
)
from models import (
    AVATAR_FOTO,
    FUNDO_PADRAO,
    TAMANHO_DO_COMENTARIO,
    AvisoEnviado,
    EventoDaTarefa,
    Anexo,
    Categoria,
    CompartilhamentoDeCategoria,
    ConfiguracaoEmail,
    GrupoDeUsuarios,
    Imagem,
    ItemDaTarefa,
    Marcacao,
    LIMITES_DO_PLANO,
    PERMISSOES_DE_COMPARTILHAMENTO,
    TIPO_GENERALISTA,
    TIPO_VIDEO,
    Projeto,
    PlanoDeUsuario,
    Tarefa,
    Usuario,
    VideoDoYoutube,
    membros_dos_grupos,
    rotulo_de_tamanho,
)

principal = Blueprint("principal", __name__)

# Imagens da descrição enviadas e ainda não salvas numa demanda: no máximo 20 por pessoa,
# e as que passam de 24 horas sem uso são apagadas.
LIMITE_IMAGENS_PENDENTES = 20
PRAZO_DAS_IMAGENS_PENDENTES = timedelta(hours=24)

ASSINATURAS_DE_IMAGEM = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}


def agora():
    return datetime.now(FUSO_HORARIO).replace(tzinfo=None)


def projeto_do_usuario(projeto_id):
    return Projeto.query.filter_by(
        id=projeto_id, usuario_id=current_user.id
    ).first_or_404()


def categoria_do_usuario(categoria_id):
    return Categoria.query.filter_by(
        id=categoria_id, usuario_id=current_user.id
    ).first_or_404()


def tarefa_do_usuario(tarefa_id):
    return (
        Tarefa.query.join(Projeto)
        .filter(Tarefa.id == tarefa_id, Projeto.usuario_id == current_user.id)
        .first_or_404()
    )


def permissao_no_projeto(projeto):
    if projeto.usuario_id == current_user.id:
        return "dono"
    return projeto.categoria.permissao_de(current_user) if projeto.categoria else None


def projeto_editavel(projeto_id):
    """O projeto do usuário ou o de uma categoria compartilhada com ele para editar."""
    projeto = db.get_or_404(Projeto, projeto_id)
    if permissao_no_projeto(projeto) not in ("dono", "editar"):
        abort(404)
    return projeto


def tarefa_acessivel(tarefa_id, editar=False):
    tarefa = db.get_or_404(Tarefa, tarefa_id)
    permissoes = ("dono", "editar") if editar else ("dono", "editar", "visualizar")
    if permissao_no_projeto(tarefa.projeto) not in permissoes:
        abort(404)
    return tarefa


def categorias_compartilhadas():
    """As categorias de outros usuários compartilhadas com algum grupo do usuário."""
    # Subconsulta em vez de DISTINCT: o PostgreSQL e o Oracle recusam DISTINCT com ORDER BY
    # de uma expressão fora do SELECT, como o lower(nome).
    recebidas = (
        db.session.query(CompartilhamentoDeCategoria.categoria_id)
        .join(GrupoDeUsuarios)
        .filter(GrupoDeUsuarios.membros.any(Usuario.id == current_user.id))
    )
    return (
        Categoria.query.filter(Categoria.id.in_(recebidas), Categoria.usuario_id != current_user.id)
        .order_by(func.lower(Categoria.nome), Categoria.id)
        .all()
    )


# Como cada limite aparece na mensagem de erro.
NOMES_DOS_LIMITES = {
    "categorias": "categorias",
    "projetos": "projetos",
    "atividades": "demandas",
    "listas_de_tarefas": "listas de tarefas",
    "videos": "vídeos",
}
# O cartão generalista conta como demanda, também quando tem um vídeo.
LIMITE_POR_TIPO = {
    "atividade": "atividades",
    TIPO_GENERALISTA: "atividades",
    "lista_de_tarefas": "listas_de_tarefas",
    TIPO_VIDEO: "videos",
}


def quantidade_do_dono(dono, recurso):
    if recurso == "categorias":
        return Categoria.query.filter_by(usuario_id=dono.id).count()
    if recurso == "projetos":
        return Projeto.query.filter_by(usuario_id=dono.id).count()
    tipos = [tipo for tipo, chave in LIMITE_POR_TIPO.items() if chave == recurso]
    # As ocultas e as concluídas também contam: continuam sendo do usuário.
    return Tarefa.query.join(Projeto).filter(Projeto.usuario_id == dono.id, Tarefa.tipo.in_(tipos)).count()


def erro_de_limite(dono, recurso):
    """A mensagem quando o plano do dono não permite criar mais um item; senão, None.

    Na categoria compartilhada, vale o plano do dono dela, como o espaço para anexos.
    Rebaixar o plano não apaga nada: só impede que novos itens sejam criados.
    """
    plano = dono.plano_efetivo
    limite = getattr(plano, recurso) if plano else None
    if limite is None or quantidade_do_dono(dono, recurso) < limite:
        return None
    quem = "O seu plano" if dono.id == current_user.id else "O plano de {}".format(dono.nome or dono.email)
    return "{} permite até {} {}.".format(quem, limite, NOMES_DOS_LIMITES[recurso])


def anexo_do_usuario(anexo_id):
    return (
        Anexo.query.join(Tarefa)
        .join(Projeto)
        .filter(Anexo.id == anexo_id, Projeto.usuario_id == current_user.id)
        .first_or_404()
    )


def aplicar_configuracao_de_email(app, configuracao):
    """Passa a usar, sem reiniciar, as configurações salvas na tela de Configurações."""
    remetente = (configuracao.nome_envio, configuracao.email_envio)
    # Com o servidor configurado, os e-mails automáticos passam a ser enviados.
    app.config.update(
        SECURITY_RECOVERABLE=True,
        # Quem se cadastra confirma o e-mail antes de entrar.
        SECURITY_CONFIRMABLE=True,
        SECURITY_SEND_REGISTER_EMAIL=True,
        SECURITY_SEND_PASSWORD_CHANGE_EMAIL=True,
        SECURITY_SEND_PASSWORD_RESET_NOTICE_EMAIL=True,
    )
    app.config.update(
        MAIL_SERVER=configuracao.servidor,
        MAIL_PORT=configuracao.porta,
        MAIL_USERNAME=configuracao.usuario,
        MAIL_PASSWORD=decifrar(configuracao.senha, app.config["SECRET_KEY"]),
        MAIL_DEFAULT_SENDER=remetente,
        SECURITY_EMAIL_SENDER=remetente,
        **seguranca_smtp(configuracao.porta, configuracao.usar_tls),
    )
    # O Flask-Mail guarda uma cópia da configuração ao iniciar: ela é refeita aqui.
    app.extensions["mail"] = mail.state = mail.init_mail(app.config, app.debug, app.testing)


def exigir_administrador():
    if not current_user.administrador:
        abort(403)


def tarefas_atrasadas():
    """As do proprietário e as de que o usuário é o responsável, se ainda tiver acesso ao quadro."""
    atrasadas = (
        Tarefa.query.join(Projeto)
        .filter(
            or_(Projeto.usuario_id == current_user.id, Tarefa.responsavel_id == current_user.id),
            Projeto.concluida == false(),
            Tarefa.concluida_em.is_(None),
            Tarefa.previsao_execucao < agora(),
        )
        .order_by(Tarefa.previsao_execucao, Tarefa.id)
        .all()
    )
    return [
        tarefa
        for tarefa in atrasadas
        if tarefa.projeto.usuario_id == current_user.id
        or (
            tarefa.responsavel_atual
            and tarefa.responsavel_atual.id == current_user.id
            and tarefa.proprietario.avisa_o_responsavel
        )
    ]


# Meu Dia: as atrasadas, as de hoje, as de amanhã e as dos dias seguintes, até este limite.
DIAS_DO_MEU_DIA = 7
DIAS_DA_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
GRUPOS_DO_MEU_DIA = [
    ("atrasadas", "Atrasadas"),
    ("hoje", "Hoje"),
    ("amanha", "Amanhã"),
    ("proximos", "Próximos dias"),
]


def data_por_extenso(dia):
    """Ex.: sexta-feira, 6 de novembro."""
    return "{}, {} de {}".format(DIAS_DA_SEMANA[dia.weekday()], dia.day, MESES[dia.month - 1])


def cartoes_com_previsao(fim, inicio=None):
    """Os cartões do Meu Dia e do Calendário com previsão antes de `fim` (e a partir de `inicio`).

    São os dos projetos do usuário e aqueles de que ele é o responsável atual, sem vídeos, demandas
    concluídas e projetos marcados como concluídos. As ocultas entram.
    """
    filtros = [
        or_(Projeto.usuario_id == current_user.id, Tarefa.responsavel_id == current_user.id),
        Tarefa.tipo != TIPO_VIDEO,
        Projeto.concluida == false(),
        Tarefa.concluida_em.is_(None),
        Tarefa.previsao_execucao.isnot(None),
        Tarefa.previsao_execucao < fim,
    ]
    if inicio is not None:
        filtros.append(Tarefa.previsao_execucao >= inicio)
    candidatas = Tarefa.query.join(Projeto).filter(*filtros).order_by(Tarefa.previsao_execucao, Tarefa.id).all()
    visiveis = []
    for tarefa in candidatas:
        if tarefa.projeto.usuario_id != current_user.id:
            responsavel = tarefa.responsavel_atual
            if responsavel is None or responsavel.id != current_user.id:
                continue
        visiveis.append(tarefa)
    return visiveis


def tarefas_do_meu_dia(momento):
    """Os cartões com previsão até DIAS_DO_MEU_DIA dias, separados em GRUPOS_DO_MEU_DIA.

    Entram os dos projetos do usuário e os de que ele é o responsável atual, como no alerta, mas sem a
    escolha "Proprietário do cartão" da Automação, que vale só para os avisos. Ficam de fora os
    vídeos, as demandas concluídas e os projetos marcados como concluídos; as ocultas entram.
    """
    hoje = momento.date()
    limite = datetime.combine(hoje + timedelta(days=DIAS_DO_MEU_DIA + 1), datetime.min.time())
    grupos = {chave: [] for chave, _ in GRUPOS_DO_MEU_DIA}
    for tarefa in cartoes_com_previsao(limite):
        previsao = tarefa.previsao_execucao
        if previsao < momento:
            grupos["atrasadas"].append(tarefa)
        elif previsao.date() == hoje:
            grupos["hoje"].append(tarefa)
        elif previsao.date() == hoje + timedelta(days=1):
            grupos["amanha"].append(tarefa)
        else:
            grupos["proximos"].append(tarefa)
    return grupos


@principal.route("/meu-dia")
@auth_required()
def meu_dia():
    momento = agora()
    grupos = tarefas_do_meu_dia(momento)
    return render_template(
        "meu_dia.html",
        grupos=grupos,
        grupos_do_meu_dia=GRUPOS_DO_MEU_DIA,
        total=sum(len(tarefas) for tarefas in grupos.values()),
        hoje=data_por_extenso(momento.date()),
        dias=DIAS_DO_MEU_DIA,
    )


# Calendário: a semana começa no domingo, como nos calendários do Brasil.
VISOES_DO_CALENDARIO = ("mes", "semana")
DIAS_CURTOS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"]


def inicio_da_semana(dia):
    return dia - timedelta(days=(dia.weekday() + 1) % 7)


def titulo_da_semana(inicio, fim):
    """Ex.: 1 a 7 de novembro de 2026; 29 de novembro a 5 de dezembro de 2026."""
    if (inicio.year, inicio.month) == (fim.year, fim.month):
        return "{} a {} de {} de {}".format(inicio.day, fim.day, MESES[fim.month - 1], fim.year)
    if inicio.year == fim.year:
        return "{} de {} a {} de {} de {}".format(
            inicio.day, MESES[inicio.month - 1], fim.day, MESES[fim.month - 1], fim.year
        )
    return "{} de {} de {} a {} de {} de {}".format(
        inicio.day, MESES[inicio.month - 1], inicio.year, fim.day, MESES[fim.month - 1], fim.year
    )


def periodo_do_calendario(visao, dia):
    """Primeiro e último dia da tela, as datas de anterior e próximo e o título."""
    if visao == "semana":
        inicio = inicio_da_semana(dia)
        fim = inicio + timedelta(days=6)
        return inicio, fim, inicio - timedelta(days=7), inicio + timedelta(days=7), titulo_da_semana(inicio, fim)
    primeiro = dia.replace(day=1)
    ultimo = (primeiro + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    inicio = inicio_da_semana(primeiro)
    fim = inicio_da_semana(ultimo) + timedelta(days=6)
    anterior = (primeiro - timedelta(days=1)).replace(day=1)
    titulo = "{} de {}".format(MESES[primeiro.month - 1].capitalize(), primeiro.year)
    return inicio, fim, anterior, ultimo + timedelta(days=1), titulo


@principal.route("/calendario")
@auth_required()
def calendario():
    visao = request.args.get("visao", "mes")
    if visao not in VISOES_DO_CALENDARIO:
        visao = "mes"
    momento = agora()
    hoje = momento.date()
    try:
        dia = date.fromisoformat(request.args.get("data", ""))
    except ValueError:
        dia = hoje
    inicio, fim, anterior, proximo, titulo = periodo_do_calendario(visao, dia)
    por_dia = {}
    for tarefa in cartoes_com_previsao(
        datetime.combine(fim + timedelta(days=1), datetime.min.time()),
        datetime.combine(inicio, datetime.min.time()),
    ):
        por_dia.setdefault(tarefa.previsao_execucao.date(), []).append(tarefa)
    dias = [inicio + timedelta(days=numero) for numero in range((fim - inicio).days + 1)]
    return render_template(
        "calendario.html",
        visao=visao,
        dia=dia,
        hoje=hoje,
        momento=momento,
        titulo=titulo,
        anterior=anterior,
        proximo=proximo,
        semanas=[dias[numero:numero + 7] for numero in range(0, len(dias), 7)],
        por_dia=por_dia,
        dias_curtos=DIAS_CURTOS,
        pode_mover={
            tarefa.id: permissao_no_projeto(tarefa.projeto) in ("dono", "editar")
            for tarefas in por_dia.values()
            for tarefa in tarefas
        },
    )


@principal.route("/api/tarefas/<int:tarefa_id>/previsao", methods=["POST"])
@auth_required()
def mudar_previsao(tarefa_id):
    """Arrastar no Calendário: muda o dia da previsão e mantém o horário."""
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    if tarefa.e_video or tarefa.previsao_execucao is None:
        abort(404)
    dados = request.get_json(silent=True)
    try:
        novo_dia = date.fromisoformat(dados["data"])
    except (TypeError, KeyError, ValueError):
        return jsonify(erro="Data inválida."), 400
    tarefa.previsao_execucao = datetime.combine(novo_dia, tarefa.previsao_execucao.time())
    registrar(tarefa, "previsao", tarefa.previsao_execucao.strftime("%d/%m/%Y %H:%M"))
    db.session.commit()
    return jsonify(
        previsao=tarefa.previsao_execucao.strftime("%d/%m/%Y %H:%M"),
        vencida=tarefa.previsao_execucao < agora(),
    )


def candidatos_a_responsavel(categoria, dono):
    """Quem pode ver o quadro: o dono e os membros dos grupos com que a categoria foi compartilhada."""
    candidatos = {dono.id: dono}
    if categoria is not None:
        for compartilhamento in categoria.compartilhamentos:
            for membro in compartilhamento.grupo.membros:
                candidatos.setdefault(membro.id, membro)
    outros = sorted(
        (usuario for usuario in candidatos.values() if usuario.id != dono.id),
        key=lambda usuario: (chave_de_texto(usuario.nome or usuario.email), usuario.email),
    )
    return [dono] + outros


def projetos_ordenados():
    return (
        Projeto.query.filter_by(usuario_id=current_user.id)
        .order_by(Projeto.posicao, Projeto.id)
        .all()
    )


def preparar_projeto_form(form):
    categorias = Categoria.query.filter_by(usuario_id=current_user.id).order_by(
        Categoria.nome
    )
    form.categoria_id.choices = [("", "Selecione uma categoria")] + [
        (categoria.id, categoria.nome) for categoria in categorias
    ]
    return form


def projetos_editaveis():
    compartilhadas = [
        projeto
        for categoria in categorias_compartilhadas()
        if categoria.permissao_de(current_user) == "editar"
        for projeto in categoria.projetos
        if projeto.usuario_id == categoria.usuario_id
    ]
    return projetos_ordenados() + compartilhadas


def preparar_tarefa_form(form):
    form.projeto_id.choices = [(projeto.id, projeto.nome) for projeto in projetos_editaveis()]
    return form


def proxima_posicao_tarefa(projeto_id):
    maior = (
        db.session.query(func.max(Tarefa.posicao)).filter_by(projeto_id=projeto_id).scalar()
    )
    return 0 if maior is None else maior + 1


def renumerar(itens):
    for posicao, item in enumerate(itens):
        item.posicao = posicao


def informar_erros(form):
    for erros in form.errors.values():
        for erro in erros:
            flash(erro, "erro")


def arquivos_enviados():
    return [arquivo for arquivo in request.files.getlist("anexos") if arquivo.filename]


def tamanho_do_arquivo(arquivo):
    arquivo.stream.seek(0, os.SEEK_END)
    tamanho = arquivo.stream.tell()
    arquivo.stream.seek(0)
    return tamanho


def espaco_usado(usuario=None):
    """Os anexos das demandas dos projetos da pessoa e as imagens da descrição que são dela."""
    usuario = usuario or current_user
    anexos = (
        db.session.query(func.coalesce(func.sum(Anexo.tamanho), 0))
        .join(Tarefa)
        .join(Projeto)
        .filter(Projeto.usuario_id == usuario.id)
        .scalar()
    )
    imagens = (
        db.session.query(func.coalesce(func.sum(Imagem.tamanho), 0))
        .filter(Imagem.usuario_id == usuario.id)
        .scalar()
    )
    return anexos + imagens


def apagar_imagens_pendentes(momento):
    """Apaga as imagens enviadas há mais de PRAZO_DAS_IMAGENS_PENDENTES que nenhuma demanda usa."""
    antigas = Imagem.query.filter(
        Imagem.tarefa_id.is_(None),
        or_(Imagem.criado_em.is_(None), Imagem.criado_em < momento - PRAZO_DAS_IMAGENS_PENDENTES),
    ).all()
    codigos = [imagem.arquivo for imagem in antigas]
    for imagem in antigas:
        db.session.delete(imagem)
    db.session.commit()
    apagar_arquivos(codigos)
    return len(codigos)


def erro_nos_arquivos(arquivos, quantidade_atual, dono=None):
    """Os anexos ocupam o espaço do dono do projeto, mesmo quando outro membro os envia."""
    dono = dono or current_user
    if quantidade_atual + len(arquivos) > LIMITE_ANEXOS:
        return "Cada demanda pode ter até {} arquivos.".format(LIMITE_ANEXOS)
    tamanhos = [tamanho_do_arquivo(arquivo) for arquivo in arquivos]
    if any(tamanho > TAMANHO_MAXIMO_ANEXO for tamanho in tamanhos):
        return "Cada arquivo pode ter até {} MB.".format(TAMANHO_MAXIMO_ANEXO // (1024 * 1024))
    usado = espaco_usado(dono)
    espaco = dono.espaco_para_anexos
    if tamanhos and usado + sum(tamanhos) > espaco:
        return "Os anexos não cabem no seu espaço de {}: {} já estão em uso.".format(
            rotulo_de_tamanho(espaco), rotulo_de_tamanho(usado)
        )
    return None


def guardar_arquivos(tarefa, arquivos):
    for arquivo in arquivos:
        # O nome em disco é aleatório: o nome enviado pelo usuário vale só para exibição.
        codigo = uuid4().hex
        tamanho = tamanho_do_arquivo(arquivo)
        arquivo.save(current_app.config["ANEXOS_DIR"] / codigo)
        tarefa.anexos.append(
            Anexo(
                nome=nome_de_arquivo(arquivo.filename) or "arquivo",
                arquivo=codigo,
                tamanho=tamanho,
            )
        )


def apagar_arquivos(codigos):
    for codigo in codigos:
        (current_app.config["ANEXOS_DIR"] / codigo).unlink(missing_ok=True)


def tipo_da_imagem(arquivo):
    # O tipo vem do conteúdo do arquivo: o nome e o tipo enviados pelo navegador não são confiáveis.
    inicio = arquivo.stream.read(12)
    arquivo.stream.seek(0)
    if inicio[:4] == b"RIFF" and inicio[8:] == b"WEBP":
        return "image/webp"
    for assinatura, tipo in ASSINATURAS_DE_IMAGEM.items():
        if inicio.startswith(assinatura):
            return tipo
    return None


def sincronizar_imagens(tarefa):
    """Liga à tarefa as imagens do texto e devolve os arquivos que deixaram de ser usados."""
    usadas = set(IMAGEM_DA_DESCRICAO.findall(tarefa.descricao))
    descartadas = []
    imagens = Imagem.query.filter(
        or_(
            and_(Imagem.usuario_id == current_user.id, Imagem.tarefa_id.is_(None)),
            Imagem.tarefa_id == tarefa.id,
        )
    )
    for imagem in imagens:
        if imagem.arquivo in usadas:
            imagem.tarefa = tarefa
            # Assim a imagem não some se a conta de quem a enviou for excluída.
            imagem.usuario_id = tarefa.projeto.usuario_id
        else:
            descartadas.append(imagem.arquivo)
            db.session.delete(imagem)
    return descartadas


def secoes_do_formulario(tarefa, form):
    """As seções do cartão generalista. Com arquivos, a seção Arquivos não pode ser retirada."""
    secoes = list(form.secoes.data or [])
    if tarefa is not None and tarefa.anexos and "arquivos" not in secoes:
        secoes.insert(0, "arquivos")
    return secoes


def video_do_formulario(form, secoes, atual):
    """O vídeo do cartão generalista: (erro, dados).

    dados é None para tirar o vídeo, o próprio vídeo atual para mantê-lo sem acessar a internet,
    ou as informações lidas do YouTube ou do Vimeo, para gravar. O servidor acessa só o endereço oficial.
    """
    endereco = form.video_endereco.data or ""
    if "video" not in secoes or not endereco:
        return None, None
    try:
        plataforma, codigo = videos.identificar(endereco)
        if (
            atual is not None
            and (atual.plataforma or videos.YOUTUBE, atual.codigo) == (plataforma, codigo)
            and form.video_atualizar.data != "1"
        ):
            return None, atual
        informacoes = videos.informacoes(plataforma, codigo)
    except tuple(MENSAGENS_DO_VIDEO) as erro:
        return MENSAGENS_DO_VIDEO[type(erro)][1], None
    informacoes["endereco"] = endereco
    return None, informacoes


def gravar_video(tarefa, dados):
    if dados is None:
        tarefa.video = None
        return
    if isinstance(dados, VideoDoYoutube):
        return
    video = tarefa.video or VideoDoYoutube()
    video.endereco = dados["endereco"]
    video.plataforma = dados["plataforma"]
    video.codigo = dados["codigo"]
    video.endereco_da_miniatura = dados["miniatura"]
    video.autor = dados["autor"]
    video.titulo = dados["titulo"]
    video.descricao = dados["descricao"]
    video.duracao = dados["duracao"]
    video.publicado_em = dados["publicacao"]
    tarefa.video = video


def salvar_conteudo(tarefa, form):
    """A lista de tarefas guarda os itens no lugar da Descrição.

    O cartão generalista guarda só o que está nas seções acrescentadas: tirar uma seção apaga o conteúdo dela.
    """
    if tarefa.generalista:
        secoes = tarefa.secoes_ativas
        tarefa.descricao = (form.descricao.data or "") if "descricao" in secoes else ""
        itens = form.itens.data if "tarefas" in secoes else []
        tarefa.itens = [
            ItemDaTarefa(texto=item["texto"], concluido=item["concluido"], posicao=posicao)
            for posicao, item in enumerate(itens)
        ]
    elif tarefa.lista_de_tarefas:
        tarefa.descricao = ""
        tarefa.itens = [
            ItemDaTarefa(texto=item["texto"], concluido=item["concluido"], posicao=posicao)
            for posicao, item in enumerate(form.itens.data)
        ]
    else:
        tarefa.descricao = form.descricao.data or ""
    salvar_marcacoes(tarefa, form)


def salvar_marcacoes(tarefa, form):
    # Como os itens, as marcações são todas substituídas a cada gravação.
    tarefa.marcacoes = [
        Marcacao(texto=texto, posicao=posicao) for posicao, texto in enumerate(form.marcacoes.data)
    ]


def registrar(tarefa, tipo, detalhe="", texto=""):
    """Acrescenta uma linha ao histórico do cartão, em nome de quem está logado."""
    tarefa.eventos.append(
        EventoDaTarefa(usuario_id=current_user.id, tipo=tipo, detalhe=detalhe[:200], texto=texto, momento=agora())
    )


def concluir_tarefa_agora(tarefa):
    """Guarda a data e a hora da conclusão e tira a demanda do quadro."""
    tarefa.concluida_em = agora()
    tarefa.oculta = True


def concluir_se_completa(tarefa):
    # A lista de tarefas é concluída sozinha quando a última tarefa é marcada.
    if tarefa.lista_de_tarefas and tarefa.concluida_em is None and tarefa.todas_as_tarefas_concluidas:
        concluir_tarefa_agora(tarefa)
        return True
    return False


def voltar_ao_quadro():
    categoria = request.form.get("categoria", type=int)
    busca = (request.form.get("busca") or "").strip()[:TAMANHO_DA_BUSCA] or None
    return redirect(url_for("principal.quadro", categoria=categoria, busca=busca))


TAMANHO_DA_BUSCA = 100
ETIQUETA_HTML = re.compile(r"<[^>]+>")


def textos_da_tarefa(tarefa):
    """Os textos de um cartão que entram na Pesquisar."""
    textos = [tarefa.nome, tarefa.local, html.unescape(ETIQUETA_HTML.sub(" ", tarefa.descricao or ""))]
    textos.extend(item.texto for item in tarefa.itens)
    textos.extend(marcacao.texto for marcacao in tarefa.marcacoes)
    if tarefa.video:
        video = tarefa.video
        textos.extend([video.titulo, video.autor, video.descricao, video.informacoes_adicionais])
    return textos


def tarefa_combina_com_a_busca(tarefa, busca):
    """Sem diferenciar maiúsculas nem acentos: "cafe" encontra "Café"."""
    termo = chave_de_texto(busca)
    return any(termo in chave_de_texto(texto) for texto in textos_da_tarefa(tarefa))


# ---------- Aplicativo instalável (PWA)

NOME_CURTO_DO_APP = "Projetos"  # até 12 caracteres, para caber sob o ícone
COR_DO_FUNDO_DO_APP = "#f6f5f2"  # --fundo de style.css
COR_DO_TEMA_DO_APP = "#0b3f91"  # --cabecalho do tema Azul; o base.html troca pela do tema do usuário
# Arquivos estáticos guardados pelo service worker para o app abrir mais rápido. Só arquivos
# públicos: as páginas, que têm dados do usuário, nunca entram no cache.
ARQUIVOS_DO_APP = (
    "css/style.css",
    "js/app.js",
    "img/favicon.ico",
    "img/favicon-32.png",
    "img/icone_cabecalho.png",
    "img/icone-192.png",
    "img/icone-512.png",
    "img/icone-maskable-512.png",
    "img/apple-touch-icon.png",
)


# Resumo do conteúdo de cada arquivo, pelo nome e pelo momento da última alteração.
_VERSOES_DOS_ESTATICOS = {}


def estatico(nome):
    """Endereço de um arquivo de static/ com a versão do conteúdo (?v=), usado por base.html.

    Quando o arquivo muda, o endereço muda: o navegador busca o novo já no primeiro carregamento,
    sem esperar o service worker, que só serve do cache os endereços sem ?v= (os da /offline).
    """
    caminho = os.path.join(current_app.static_folder, nome)
    chave = (caminho, os.stat(caminho).st_mtime_ns)
    if chave not in _VERSOES_DOS_ESTATICOS:
        with open(caminho, "rb") as arquivo:
            _VERSOES_DOS_ESTATICOS[chave] = hashlib.sha256(arquivo.read()).hexdigest()[:12]
    return url_for("static", filename=nome, v=_VERSOES_DOS_ESTATICOS[chave])


def versao_dos_arquivos_do_app():
    """Muda quando algum arquivo guardado ou o próprio service worker muda, para o cache ser trocado."""
    resumo = hashlib.sha256()
    for nome in ARQUIVOS_DO_APP + ("js/sw.js",):
        with open(os.path.join(current_app.static_folder, nome), "rb") as arquivo:
            resumo.update(arquivo.read())
    resumo.update(render_template("offline.html").encode("utf-8"))
    return resumo.hexdigest()[:16]


def icone_do_app(nome, tamanho, finalidade="any"):
    return {"src": url_for("static", filename=f"img/{nome}"), "sizes": tamanho, "type": "image/png", "purpose": finalidade}


@principal.route("/manifest.webmanifest")
def manifesto():
    dados = {
        "id": "/",
        "name": "Projetos & Demandas",
        "short_name": NOME_CURTO_DO_APP,
        "description": "Solução on-line para a gestão de projetos e demandas",
        "lang": "pt-BR",
        "dir": "ltr",
        "start_url": url_for("principal.quadro"),
        "scope": "/",
        "display": "standalone",
        "background_color": COR_DO_FUNDO_DO_APP,
        "theme_color": COR_DO_TEMA_DO_APP,
        "icons": [
            icone_do_app("icone-192.png", "192x192"),
            icone_do_app("icone-512.png", "512x512"),
            icone_do_app("icone-maskable-512.png", "512x512", "maskable"),
        ],
        "shortcuts": [
            {"name": "Meu Dia", "url": url_for("principal.meu_dia"), "icons": [icone_do_app("icone-192.png", "192x192")]},
            {"name": "Calendário", "url": url_for("principal.calendario"), "icons": [icone_do_app("icone-192.png", "192x192")]},
        ],
    }
    resposta = current_app.response_class(json.dumps(dados, ensure_ascii=False), mimetype="application/manifest+json")
    resposta.headers["Cache-Control"] = "no-cache"
    return resposta


@principal.route("/sw.js")
def service_worker():
    # Servido na raiz, e não em /static/js/, para o service worker valer para todo o site.
    with open(os.path.join(current_app.static_folder, "js", "sw.js"), encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    arquivos = [url_for("static", filename=nome) for nome in ARQUIVOS_DO_APP]
    codigo = codigo.replace('"__VERSAO__"', json.dumps(versao_dos_arquivos_do_app()))
    codigo = codigo.replace('"__OFFLINE__"', json.dumps(url_for("principal.offline")))
    codigo = codigo.replace("[] /* __ARQUIVOS__ */", json.dumps(arquivos))
    resposta = current_app.response_class(codigo, mimetype="text/javascript")
    resposta.headers["Cache-Control"] = "no-cache"
    resposta.headers["Service-Worker-Allowed"] = "/"
    return resposta


@principal.route("/favicon.ico")
def favicon():
    # Para os navegadores que pedem o ícone na raiz, sem ler o <link rel="icon"> da página.
    resposta = send_from_directory(
        os.path.join(current_app.static_folder, "img"), "favicon.ico", mimetype="image/vnd.microsoft.icon"
    )
    resposta.cache_control.max_age = 7 * 24 * 60 * 60
    return resposta


@principal.route("/offline")
def offline():
    # Página pública e sem dados do usuário: é a única página que o service worker guarda.
    return render_template("offline.html")


@principal.route("/captcha.png")
def imagem_captcha():
    # Cada imagem troca o desafio da sessão: vale o código da última imagem exibida.
    resposta = current_app.response_class(novo_desafio(), mimetype="image/png")
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


def categoria_do_quadro():
    """A categoria do parâmetro `categoria` e a permissão do usuário nela (404 sem acesso)."""
    categoria_id = request.args.get("categoria", type=int)
    if categoria_id is None:
        return None, "dono"
    categoria = db.get_or_404(Categoria, categoria_id)
    permissao = categoria.permissao_de(current_user)
    if permissao is None:
        abort(404)
    return categoria, permissao


def projetos_do_quadro(categoria, permissao, todos_os_projetos=None):
    """Os projetos da tela: os do usuário (todos ou os da categoria) ou os do dono da categoria compartilhada."""
    if permissao != "dono":
        return (
            Projeto.query.filter_by(categoria_id=categoria.id, usuario_id=categoria.usuario_id)
            .order_by(Projeto.posicao, Projeto.id)
            .all()
        )
    projetos = projetos_ordenados() if todos_os_projetos is None else todos_os_projetos
    if categoria:
        return [projeto for projeto in projetos if projeto.categoria_id == categoria.id]
    return projetos


def versao_dos_projetos(projetos):
    """Um resumo de tudo o que aparece nos projetos da tela. Muda quando alguém altera qualquer cartão."""
    dados = []
    for projeto in projetos:
        dados.append(("projeto", projeto.id, projeto.nome, projeto.cor, projeto.posicao, projeto.categoria_id, projeto.concluida))
        for tarefa in projeto.tarefas:
            dados.append((
                "tarefa", tarefa.id, tarefa.nome, tarefa.tipo, tarefa.prioridade, tarefa.posicao,
                tarefa.previsao_execucao, tarefa.local, tarefa.descricao, tarefa.oculta, tarefa.concluida_em,
                tarefa.responsavel_id, tarefa.secoes,
                tuple((item.texto, item.concluido, item.posicao) for item in tarefa.itens),
                tuple(marcacao.texto for marcacao in tarefa.marcacoes),
                tuple((anexo.id, anexo.nome) for anexo in tarefa.anexos),
                (
                    tarefa.video.simplificado, tarefa.video.informacoes_adicionais, tarefa.video.autor,
                    tarefa.video.titulo, tarefa.video.descricao, tarefa.video.duracao, tarefa.video.publicado_em,
                    tarefa.video.plataforma, tarefa.video.codigo, tarefa.video.endereco_da_miniatura,
                ) if tarefa.video else None,
            ))
    return hashlib.sha256(repr(dados).encode("utf-8")).hexdigest()[:16]


def quadro_compartilhado(projetos, permissao):
    """Só vale atualizar sozinho o quadro que outras pessoas também podem mudar."""
    return permissao != "dono" or any(projeto.categoria and projeto.categoria.compartilhamentos for projeto in projetos)


@principal.route("/api/quadro/versao")
@auth_required()
def versao_do_quadro():
    categoria, permissao = categoria_do_quadro()
    return jsonify(versao=versao_dos_projetos(projetos_do_quadro(categoria, permissao)))


@principal.route("/")
def quadro():
    # Sem login, a página inicial é a apresentação da área externa (Projetos & Demandas). O endereço
    # com parâmetros (o link de um cartão, como nos e-mails de aviso) vai ao login e volta ao cartão.
    if not current_user.is_authenticated:
        if not request.args:
            return redirect(url_for("publico.apresentacao"))
        return redirect(url_for_security("login", next=url_for("principal.quadro", **request.args)))

    categoria_selecionada, permissao = categoria_do_quadro()

    # Vinda dos alertas, a tarefa pode estar oculta ou fora da categoria selecionada.
    tarefa_id = request.args.get("tarefa", type=int)
    tarefa_aberta = None
    if tarefa_id is not None and permissao == "dono":
        tarefa_aberta = tarefa_do_usuario(tarefa_id)
    elif tarefa_id is not None:
        # Na categoria compartilhada, só abre o que está nela, com a permissão dela.
        tarefa_aberta = tarefa_acessivel(tarefa_id)
        if tarefa_aberta.projeto.categoria_id != categoria_selecionada.id:
            abort(404)

    todos_os_projetos = projetos_ordenados()
    projetos = projetos_do_quadro(categoria_selecionada, permissao, todos_os_projetos)
    dono = categoria_selecionada.usuario if permissao != "dono" else current_user

    # A Pesquisar filtra só os cartões dos projetos da tela: os do usuário ou os da categoria compartilhada.
    busca = (request.args.get("busca") or "").strip()[:TAMANHO_DA_BUSCA]
    encontradas = None
    if busca:
        encontradas = {
            tarefa.id
            for projeto in projetos
            for tarefa in projeto.tarefas
            if (current_user.mostrar_ocultas or not tarefa.oculta)
            and tarefa_combina_com_a_busca(tarefa, busca)
        }

    # Para a caixa Adicionar Responsável: as pessoas de cada categoria dos projetos da tela.
    responsaveis_possiveis = {}
    if permissao == "dono":
        for projeto in projetos:
            if (projeto.categoria_id or 0) not in responsaveis_possiveis:
                responsaveis_possiveis[projeto.categoria_id or 0] = candidatos_a_responsavel(projeto.categoria, current_user)

    return render_template(
        "quadro.html",
        projetos=projetos,
        busca=busca,
        responsaveis_possiveis=responsaveis_possiveis,
        encontradas=encontradas,
        tem_projetos=bool(todos_os_projetos),
        categorias=Categoria.query.filter_by(usuario_id=current_user.id)
        .order_by(Categoria.nome)
        .all(),
        categoria_selecionada=categoria_selecionada,
        categorias_compartilhadas=categorias_compartilhadas(),
        permissao=permissao,
        dono=dono,
        espaco_do_dono=espaco_usado(dono),
        tarefa_aberta=tarefa_aberta,
        versao=versao_dos_projetos(projetos),
        quadro_compartilhado=quadro_compartilhado(projetos, permissao),
        mostrar_ocultas=current_user.mostrar_ocultas,
        agora=agora(),
        categoria_form=CategoriaForm(formdata=None),
        projeto_form=preparar_projeto_form(ProjetoForm(formdata=None)),
        tarefa_form=preparar_tarefa_form(TarefaForm(formdata=None)),
        anexo_form=AnexoForm(formdata=None),
        limite_anexos=LIMITE_ANEXOS,
        tamanho_maximo_anexo=TAMANHO_MAXIMO_ANEXO,
        espaco_usado=espaco_usado(),
    )


@principal.route("/categorias", methods=["POST"])
@auth_required()
def criar_categoria():
    form = CategoriaForm()
    erro = erro_de_limite(current_user, "categorias")
    if erro:
        flash(erro, "erro")
    elif form.validate_on_submit():
        db.session.add(
            Categoria(
                nome=form.nome.data,
                icone=form.icone.data,
                fundo=form.fundo.data or FUNDO_PADRAO,
                usuario_id=current_user.id,
            )
        )
        db.session.commit()
    else:
        informar_erros(form)
    return voltar_ao_quadro()


@principal.route("/categorias/<int:categoria_id>/editar", methods=["POST"])
@auth_required()
def editar_categoria(categoria_id):
    categoria = categoria_do_usuario(categoria_id)
    form = CategoriaForm()
    if form.validate_on_submit():
        categoria.nome = form.nome.data
        categoria.icone = form.icone.data
        categoria.fundo = form.fundo.data or FUNDO_PADRAO
        db.session.commit()
    else:
        informar_erros(form)
    return voltar_ao_quadro()


@principal.route("/categorias/<int:categoria_id>/excluir", methods=["POST"])
@auth_required()
def excluir_categoria(categoria_id):
    categoria = categoria_do_usuario(categoria_id)
    if categoria.projetos:
        flash("Remova os projetos desta categoria antes de excluí-la.", "erro")
        return voltar_ao_quadro()

    db.session.delete(categoria)
    db.session.commit()
    flash("Categoria excluída.", "sucesso")
    return redirect(url_for("principal.quadro"))


@principal.route("/projetos", methods=["POST"])
@auth_required()
def criar_projeto():
    form = preparar_projeto_form(ProjetoForm())
    erro = erro_de_limite(current_user, "projetos")
    if erro:
        flash(erro, "erro")
    elif form.validate_on_submit():
        db.session.add(
            Projeto(
                nome=form.nome.data,
                cor=form.cor.data,
                categoria_id=form.categoria_id.data,
                concluida=form.concluida.data,
                posicao=len(projetos_ordenados()),
                usuario_id=current_user.id,
            )
        )
        db.session.commit()
    else:
        informar_erros(form)
    return voltar_ao_quadro()


@principal.route("/projetos/<int:projeto_id>/editar", methods=["POST"])
@auth_required()
def editar_projeto(projeto_id):
    projeto = projeto_do_usuario(projeto_id)
    form = preparar_projeto_form(ProjetoForm())
    if form.validate_on_submit():
        projeto.nome = form.nome.data
        projeto.cor = form.cor.data
        projeto.categoria_id = form.categoria_id.data
        projeto.concluida = form.concluida.data
        db.session.commit()
    else:
        informar_erros(form)
    return voltar_ao_quadro()


@principal.route("/projetos/<int:projeto_id>/excluir", methods=["POST"])
@auth_required()
def excluir_projeto(projeto_id):
    projeto = projeto_do_usuario(projeto_id)
    if projeto.tarefas:
        flash("Remova as demandas deste projeto antes de excluí-lo.", "erro")
        return voltar_ao_quadro()

    db.session.delete(projeto)
    db.session.flush()
    renumerar(projetos_ordenados())
    db.session.commit()
    flash("Projeto excluído.", "sucesso")
    return voltar_ao_quadro()


@principal.route("/api/projetos/ordem", methods=["POST"])
@auth_required()
def ordenar_projetos():
    dados = request.get_json(silent=True)
    ids = dados.get("projetos") if isinstance(dados, dict) else None
    if (
        not isinstance(ids, list)
        or not ids
        or any(type(projeto_id) is not int for projeto_id in ids)
        or len(set(ids)) != len(ids)
    ):
        return jsonify(erro="Dados inválidos."), 400

    projetos = projetos_ordenados()
    por_id = {projeto.id: projeto for projeto in projetos}
    if any(projeto_id not in por_id for projeto_id in ids):
        return jsonify(erro="Projeto não encontrado."), 404

    # Com o filtro de categoria, só os projetos visíveis trocam de lugar entre si.
    renumerar(projetos)
    posicoes = sorted(por_id[projeto_id].posicao for projeto_id in ids)
    for projeto_id, posicao in zip(ids, posicoes):
        por_id[projeto_id].posicao = posicao

    db.session.commit()
    return jsonify(projetos=ids)


@principal.route("/tarefas", methods=["POST"])
@auth_required()
def criar_tarefa():
    form = preparar_tarefa_form(TarefaForm())
    if form.validate_on_submit():
        tipo = form.tipo.data or "atividade"
        secoes = secoes_do_formulario(None, form) if tipo == TIPO_GENERALISTA else []
        arquivos = arquivos_enviados()
        if tipo == TIPO_GENERALISTA and "arquivos" not in secoes:
            arquivos = []
        dono = db.session.get(Projeto, form.projeto_id.data).usuario
        erro = erro_de_limite(dono, LIMITE_POR_TIPO[tipo]) or erro_nos_arquivos(arquivos, 0, dono)
        video = None
        if not erro and tipo == TIPO_GENERALISTA:
            # Antes de gravar: se o YouTube falhar, nada é criado.
            erro, video = video_do_formulario(form, secoes, None)
        if erro:
            flash(erro, "erro")
            return voltar_ao_quadro()

        tarefa = Tarefa(
            nome=form.nome.data,
            prioridade=form.prioridade.data,
            previsao_execucao=form.previsao_execucao.data,
            local=form.local.data or "",
            tipo=tipo,
            secoes=",".join(secoes),
            projeto_id=form.projeto_id.data,
            posicao=proxima_posicao_tarefa(form.projeto_id.data),
        )
        salvar_conteudo(tarefa, form)
        if tarefa.generalista:
            gravar_video(tarefa, video)
        registrar(tarefa, "criou")
        if concluir_se_completa(tarefa):
            registrar(tarefa, "concluiu")
        guardar_arquivos(tarefa, arquivos)
        db.session.add(tarefa)
        db.session.flush()
        descartadas = sincronizar_imagens(tarefa)
        db.session.commit()
        apagar_arquivos(descartadas)
    else:
        informar_erros(form)
    return voltar_ao_quadro()


@principal.route("/tarefas/<int:tarefa_id>/editar", methods=["POST"])
@auth_required()
def editar_tarefa(tarefa_id):
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    if tarefa.e_video:
        # O vídeo é salvo por editar_video: o formulário da demanda apagaria os dados dele.
        abort(404)
    form = preparar_tarefa_form(TarefaForm())
    if form.validate_on_submit():
        secoes = secoes_do_formulario(tarefa, form) if tarefa.generalista else []
        arquivos = arquivos_enviados()
        if tarefa.generalista and "arquivos" not in secoes:
            arquivos = []
        erro = erro_nos_arquivos(arquivos, len(tarefa.anexos), tarefa.projeto.usuario)
        video = None
        if not erro and tarefa.generalista:
            # Antes de alterar o cartão: se o YouTube falhar, nada muda.
            erro, video = video_do_formulario(form, secoes, tarefa.video)
        if erro:
            flash(erro, "erro")
            return voltar_ao_quadro()

        tarefa.nome = form.nome.data
        tarefa.prioridade = form.prioridade.data
        tarefa.previsao_execucao = form.previsao_execucao.data
        # O tipo é definido ao criar: o valor enviado na edição é ignorado.
        if tarefa.generalista:
            tarefa.secoes = ",".join(secoes)
            gravar_video(tarefa, video)
        salvar_conteudo(tarefa, form)
        registrar(tarefa, "alterou")
        if concluir_se_completa(tarefa):
            registrar(tarefa, "concluiu")
        tarefa.local = form.local.data or ""
        guardar_arquivos(tarefa, arquivos)
        descartadas = sincronizar_imagens(tarefa)
        db.session.commit()
        apagar_arquivos(descartadas)
    else:
        informar_erros(form)
    return voltar_ao_quadro()


@principal.route("/tarefas/<int:tarefa_id>/excluir", methods=["POST"])
@auth_required()
def excluir_tarefa(tarefa_id):
    tarefa = tarefa_do_usuario(tarefa_id)
    codigos = [item.arquivo for item in tarefa.anexos + tarefa.imagens]
    db.session.delete(tarefa)
    db.session.commit()
    apagar_arquivos(codigos)
    flash("Cartão excluído.", "sucesso")
    return voltar_ao_quadro()


@principal.route("/api/imagens", methods=["POST"])
@auth_required()
def enviar_imagem():
    arquivo = request.files.get("imagem")
    tipo = tipo_da_imagem(arquivo) if arquivo else None
    if not tipo:
        return jsonify(erro="Envie uma imagem PNG, JPEG, GIF ou WebP."), 400
    tamanho = tamanho_do_arquivo(arquivo)
    if tamanho > TAMANHO_MAXIMO_ANEXO:
        limite = TAMANHO_MAXIMO_ANEXO // (1024 * 1024)
        return jsonify(erro="Cada imagem pode ter até {} MB.".format(limite)), 400
    apagar_imagens_pendentes(agora())
    pendentes = Imagem.query.filter_by(usuario_id=current_user.id, tarefa_id=None).count()
    if pendentes >= LIMITE_IMAGENS_PENDENTES:
        return jsonify(
            erro="Salve a demanda antes de enviar mais imagens: são até {} imagens por vez.".format(
                LIMITE_IMAGENS_PENDENTES
            )
        ), 400
    usado = espaco_usado(current_user)
    espaco = current_user.espaco_para_anexos
    if usado + tamanho > espaco:
        return jsonify(
            erro="A imagem não cabe no seu espaço de {}: {} já estão em uso.".format(
                rotulo_de_tamanho(espaco), rotulo_de_tamanho(usado)
            )
        ), 400

    codigo = uuid4().hex
    arquivo.save(current_app.config["ANEXOS_DIR"] / codigo)
    db.session.add(
        Imagem(arquivo=codigo, tipo=tipo, usuario_id=current_user.id, tamanho=tamanho, criado_em=agora())
    )
    db.session.commit()
    return jsonify(url=url_for("principal.ver_imagem", codigo=codigo))


@principal.route("/api/perfil/foto", methods=["POST"])
@auth_required()
def enviar_foto():
    """Grava a foto ajustada na caixa do Meu Perfil e a usa como o ícone da pessoa."""
    arquivo = request.files.get("foto")
    try:
        conteudo = preparar_foto(arquivo.read() if arquivo else b"")
    except FotoInvalida as erro:
        return jsonify(erro=str(erro)), 400

    anterior = current_user.foto
    nome = "foto-{}.png".format(uuid4().hex)
    (current_app.config["ANEXOS_DIR"] / nome).write_bytes(conteudo)
    current_user.foto = nome
    current_user.avatar = AVATAR_FOTO
    db.session.commit()
    # A foto anterior sai do sistema.
    if anterior:
        apagar_arquivos([anterior])
    return jsonify(url=url_for("principal.ver_foto", nome=nome))


@principal.route("/fotos/<nome>")
@auth_required()
def ver_foto(nome):
    # O nome é aleatório e só aparece nas páginas em que a pessoa aparece.
    usuario = Usuario.query.filter_by(foto=nome).first_or_404()
    resposta = send_from_directory(current_app.config["ANEXOS_DIR"], usuario.foto, mimetype="image/png")
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    return resposta


@principal.route("/imagens/<codigo>")
@auth_required()
def ver_imagem(codigo):
    imagem = Imagem.query.filter_by(arquivo=codigo).first_or_404()
    # Quem vê a demanda, inclusive pela categoria compartilhada, vê as imagens dela.
    if imagem.usuario_id != current_user.id and not (
        imagem.tarefa and permissao_no_projeto(imagem.tarefa.projeto)
    ):
        abort(404)
    resposta = send_from_directory(
        current_app.config["ANEXOS_DIR"], imagem.arquivo, mimetype=imagem.tipo
    )
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    return resposta


@principal.route("/anexos/<int:anexo_id>/baixar")
@auth_required()
def baixar_anexo(anexo_id):
    anexo = db.get_or_404(Anexo, anexo_id)
    tarefa_acessivel(anexo.tarefa_id)
    # Sempre como download: um HTML enviado não pode rodar dentro do domínio da aplicação.
    resposta = send_from_directory(
        current_app.config["ANEXOS_DIR"],
        anexo.arquivo,
        as_attachment=True,
        download_name=anexo.nome,
        mimetype="application/octet-stream",
    )
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    return resposta


@principal.route("/anexos/<int:anexo_id>/renomear", methods=["POST"])
@auth_required()
def renomear_anexo(anexo_id):
    anexo = db.get_or_404(Anexo, anexo_id)
    tarefa_acessivel(anexo.tarefa_id, editar=True)
    form = AnexoForm()
    if form.validate_on_submit():
        # Sem extensão no novo nome, a atual é mantida para o arquivo continuar abrindo.
        anexo.nome = nome_de_arquivo(form.nome.data, os.path.splitext(anexo.nome)[1])
        db.session.commit()
    else:
        informar_erros(form)
    return voltar_ao_quadro()


@principal.route("/anexos/<int:anexo_id>/excluir", methods=["POST"])
@auth_required()
def excluir_anexo(anexo_id):
    anexo = anexo_do_usuario(anexo_id)
    codigo = anexo.arquivo
    db.session.delete(anexo)
    db.session.commit()
    apagar_arquivos([codigo])
    flash("Arquivo excluído.", "sucesso")
    return voltar_ao_quadro()


@principal.route("/tarefas/<int:tarefa_id>/ocultar", methods=["POST"])
@auth_required()
def ocultar_tarefa(tarefa_id):
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    tarefa.oculta = not tarefa.oculta
    registrar(tarefa, "ocultou" if tarefa.oculta else "reexibiu")
    db.session.commit()
    return voltar_ao_quadro()


@principal.route("/tarefas/<int:tarefa_id>/responsavel", methods=["POST"])
@auth_required()
def definir_responsavel(tarefa_id):
    # Só o proprietário escolhe; vídeos não têm responsável.
    tarefa = tarefa_do_usuario(tarefa_id)
    if tarefa.e_video:
        abort(404)
    escolhido = request.form.get("responsavel_id", type=int)
    candidatos = {usuario.id for usuario in candidatos_a_responsavel(tarefa.projeto.categoria, current_user)}
    anterior = tarefa.responsavel_id
    if escolhido is None or escolhido == current_user.id:
        tarefa.responsavel_id = None
    elif escolhido in candidatos:
        tarefa.responsavel_id = escolhido
    else:
        flash("Escolha alguém que tenha acesso a este quadro.", "erro")
        return voltar_ao_quadro()
    if tarefa.responsavel_id != anterior:
        if tarefa.responsavel_id is None:
            registrar(tarefa, "sem_responsavel")
        else:
            pessoa = db.session.get(Usuario, tarefa.responsavel_id)
            registrar(tarefa, "responsavel", pessoa.nome or pessoa.email)
    db.session.commit()
    return voltar_ao_quadro()


@principal.route("/tarefas/<int:tarefa_id>/simplificar", methods=["POST"])
@auth_required()
def simplificar_video(tarefa_id):
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    if not tarefa.e_video:
        abort(404)
    tarefa.video.simplificado = not tarefa.video.simplificado
    db.session.commit()
    return voltar_ao_quadro()


@principal.route("/tarefas/<int:tarefa_id>/concluir", methods=["POST"])
@auth_required()
def concluir_tarefa(tarefa_id):
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    if tarefa.concluida_em is None:
        concluir_tarefa_agora(tarefa)
        registrar(tarefa, "concluiu")
    else:
        # Desfazer a conclusão devolve a demanda ao quadro.
        tarefa.concluida_em = None
        tarefa.oculta = False
        registrar(tarefa, "reabriu")
    db.session.commit()
    return voltar_ao_quadro()


def historico_da_tarefa(tarefa):
    return render_template(
        "_historico.html",
        tarefa=tarefa,
        pode_comentar=permissao_no_projeto(tarefa.projeto) in ("dono", "editar"),
        tamanho_do_comentario=TAMANHO_DO_COMENTARIO,
    )


@principal.route("/tarefas/<int:tarefa_id>/historico")
@auth_required()
def ver_historico(tarefa_id):
    """O trecho da caixa Histórico: quem vê o cartão vê o histórico dele."""
    return historico_da_tarefa(tarefa_acessivel(tarefa_id))


@principal.route("/api/tarefas/<int:tarefa_id>/comentarios", methods=["POST"])
@auth_required()
def comentar_tarefa(tarefa_id):
    """Comenta quem pode editar o cartão; a resposta é o histórico já com o comentário."""
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    dados = request.get_json(silent=True)
    texto = dados.get("texto") if isinstance(dados, dict) else None
    if not isinstance(texto, str) or not texto.strip():
        return jsonify(erro="Escreva o comentário."), 400
    texto = texto.strip()
    if len(texto) > TAMANHO_DO_COMENTARIO:
        return jsonify(erro=f"O comentário deve ter no máximo {TAMANHO_DO_COMENTARIO} caracteres."), 400
    registrar(tarefa, "comentario", texto=texto)
    db.session.commit()
    return historico_da_tarefa(tarefa)


@principal.route("/tarefas/ocultas", methods=["POST"])
@auth_required()
def alternar_tarefas_ocultas():
    current_user.mostrar_ocultas = not current_user.mostrar_ocultas
    db.session.commit()
    return voltar_ao_quadro()


@principal.route("/api/tarefas/<int:tarefa_id>/mover", methods=["POST"])
@auth_required()
def mover_tarefa(tarefa_id):
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify(erro="Dados inválidos."), 400

    projeto_id = dados.get("projeto_id")
    posicao = dados.get("posicao")
    for valor in (projeto_id, posicao):
        if type(valor) is not int:
            return jsonify(erro="Dados inválidos."), 400

    destino = projeto_editavel(projeto_id)
    origem = tarefa.projeto
    # A demanda não muda de dono: quem edita a categoria de outro usuário só a move dentro dela.
    if destino.usuario_id != origem.usuario_id or (
        origem.usuario_id != current_user.id and destino.categoria_id != origem.categoria_id
    ):
        abort(404)
    origem_id = tarefa.projeto_id

    irmas = (
        Tarefa.query.filter(Tarefa.projeto_id == destino.id, Tarefa.id != tarefa.id)
        .order_by(Tarefa.posicao, Tarefa.id)
        .all()
    )
    tarefa.projeto_id = destino.id
    # A posição enviada conta só os cartões na tela; as tarefas ocultas não aparecem nela.
    visiveis = [
        irma for irma in irmas if current_user.mostrar_ocultas or not irma.oculta
    ]
    posicao = max(0, posicao)
    indice = irmas.index(visiveis[posicao]) if posicao < len(visiveis) else len(irmas)
    irmas.insert(indice, tarefa)
    renumerar(irmas)

    if origem_id != destino.id:
        registrar(tarefa, "moveu", destino.nome)
        renumerar(
            Tarefa.query.filter(Tarefa.projeto_id == origem_id, Tarefa.id != tarefa.id)
            .order_by(Tarefa.posicao, Tarefa.id)
            .all()
        )

    db.session.commit()
    return jsonify(projeto_id=destino.id, posicao=tarefa.posicao)


def concluidas_entre(inicio, fim):
    """Quantos cartões dos projetos do usuário, ou de que ele é o responsável atual, foram concluídos no período."""
    concluidas = (
        Tarefa.query.join(Projeto)
        .filter(
            or_(Projeto.usuario_id == current_user.id, Tarefa.responsavel_id == current_user.id),
            Tarefa.concluida_em >= inicio,
            Tarefa.concluida_em < fim,
        )
        .all()
    )
    return sum(
        1
        for tarefa in concluidas
        if tarefa.projeto.usuario_id == current_user.id
        or (tarefa.responsavel_atual and tarefa.responsavel_atual.id == current_user.id)
    )


def resumo_da_semana(momento):
    """Os números do Resumo da semana do Meu Perfil. A semana começa no domingo, como no Calendário."""
    inicio = datetime.combine(inicio_da_semana(momento.date()), datetime.min.time())
    semana_passada = inicio - timedelta(days=7)
    limite = datetime.combine(momento.date() + timedelta(days=DIAS_DO_MEU_DIA + 1), datetime.min.time())
    return {
        "concluidas": concluidas_entre(inicio, inicio + timedelta(days=7)),
        "semana_passada": concluidas_entre(semana_passada, inicio),
        "atrasadas": len(cartoes_com_previsao(momento)),
        "proximas": len(cartoes_com_previsao(limite, momento)),
    }


@principal.route("/perfil", methods=["GET", "POST"])
@auth_required()
def perfil():
    form = PerfilForm(
        nome=current_user.nome,
        avatar=current_user.avatar,
        telefone=current_user.telefone,
        tema=current_user.tema,
        aviso_destinatarios=current_user.aviso_destinatarios,
        aviso_antecedencia=current_user.aviso_antecedencia,
    )
    if form.validate_on_submit():
        current_user.nome = form.nome.data
        current_user.telefone = form.telefone.data
        if form.avatar.data and (form.avatar.data != AVATAR_FOTO or current_user.foto):
            current_user.avatar = form.avatar.data
        # A Cor da Aplicação saiu do cabeçalho e é escolhida aqui.
        if form.tema.data:
            current_user.tema = form.tema.data
        if form.aviso_destinatarios.data:
            current_user.aviso_destinatarios = form.aviso_destinatarios.data
        if form.aviso_antecedencia.data:
            current_user.aviso_antecedencia = form.aviso_antecedencia.data
        db.session.commit()
        return redirect(url_for("principal.quadro"))
    return render_template("perfil.html", form=form, resumo=resumo_da_semana(agora()), dias=DIAS_DO_MEU_DIA)


def email_em_uso(email, usuario_id=None):
    consulta = Usuario.query.filter(func.lower(Usuario.email) == email)
    if usuario_id:
        consulta = consulta.filter(Usuario.id != usuario_id)
    # first(), e não SELECT EXISTS: o SQL Server e o Oracle não aceitam EXISTS fora do WHERE.
    return consulta.with_entities(Usuario.id).first() is not None


@principal.route("/administracao/configuracoes", methods=["GET", "POST"])
@auth_required()
def configuracoes():
    exigir_administrador()
    salva = db.session.get(ConfiguracaoEmail, 1)
    if salva:
        form = ConfiguracoesForm(
            servidor=salva.servidor,
            porta=str(salva.porta),
            usar_tls="sim" if salva.usar_tls else "nao",
            usuario=salva.usuario,
            email_envio=salva.email_envio,
            nome_envio=salva.nome_envio,
        )
    else:
        form = ConfiguracoesForm()
    senha_atual = salva.senha if salva else None
    if form.validate_on_submit():
        if not form.senha.data and not senha_atual:
            form.senha.errors.append("Informe a senha.")
        else:
            salva = salva or ConfiguracaoEmail(id=1)
            salva.servidor = form.servidor.data
            salva.porta = int(form.porta.data)
            salva.usar_tls = form.usar_tls.data == "sim"
            salva.usuario = form.usuario.data
            # Cifrada no banco: uma cópia do arquivo do banco não entrega a senha do e-mail.
            salva.senha = cifrar(form.senha.data, current_app.config["SECRET_KEY"]) if form.senha.data else senha_atual
            salva.email_envio = form.email_envio.data
            salva.nome_envio = form.nome_envio.data
            db.session.add(salva)
            db.session.commit()
            aplicar_configuracao_de_email(current_app, salva)
            if "security.forgot_password" not in current_app.view_functions:
                # As rotas de recuperação de senha e de confirmação são criadas ao iniciar a aplicação.
                flash(
                    "Reinicie a aplicação para ativar a recuperação de senha e a confirmação do e-mail.",
                    "aviso",
                )
            return redirect(url_for("principal.quadro"))
    banco_em_uso, aviso_do_banco = descrever_banco()
    return render_template(
        "configuracoes.html", form=form, tem_senha=bool(senha_atual),
        sem_hosts_permitidos=not current_app.config.get("HOSTS_PERMITIDOS") and not current_app.debug,
        banco_em_uso=banco_em_uso, aviso_do_banco=aviso_do_banco,
    )


def descrever_banco():
    """O banco em uso, para a tela de Configurações (sem a senha), e o aviso sobre a cifra."""
    configuracao = current_app.config["BANCO"]
    url = db.engine.url
    tipo = tipo_da_url(url)
    if configuracao.em_servidor and tipo == configuracao.tipo:
        return configuracao.descricao(), configuracao.aviso_de_tls()
    # O SQLite, ou um endereço definido direto no SQLALCHEMY_DATABASE_URI (os testes).
    nome = Path(url.database or "").name if tipo == "sqlite" else (url.database or "")
    return {
        "tipo": TIPOS_DE_BANCO.get(tipo, url.get_backend_name()), "servidor": url.host or "",
        "nome": nome, "usuario": url.username or "", "tls": "",
    }, ""


def chave_de_texto(texto):
    """Para ordenar sem diferenciar maiúsculas nem acentos: Álvaro vem antes de Ana."""
    decomposto = unicodedata.normalize("NFD", (texto or "").casefold())
    return "".join(letra for letra in decomposto if not unicodedata.combining(letra))


ORDENS_DOS_USUARIOS = {
    "nome": lambda usuario: chave_de_texto(usuario.nome),
    "email": lambda usuario: chave_de_texto(usuario.email),
    # Crescente: primeiro os que não são administradores (Não), depois os que são (Sim).
    "administrador": lambda usuario: usuario.administrador,
    "plano": lambda usuario: chave_de_texto(usuario.plano_rotulo),
}


@principal.route("/administracao/usuarios")
@auth_required()
def usuarios():
    exigir_administrador()
    ordem = request.args.get("ordem", "nome")
    if ordem not in ORDENS_DOS_USUARIOS:
        ordem = "nome"
    decrescente = request.args.get("sentido") == "desc"
    # O desempate é sempre pelo nome e pelo e-mail. A ordem é feita no Python porque o SQLite
    # não ignora os acentos.
    todos = sorted(Usuario.query.all(), key=lambda usuario: (chave_de_texto(usuario.nome), usuario.email))
    todos.sort(key=ORDENS_DOS_USUARIOS[ordem], reverse=decrescente)
    return render_template(
        "usuarios.html",
        todos_os_usuarios=todos,
        ordem=ordem,
        sentido="desc" if decrescente else "asc",
    )


def preparar_usuario_form(form):
    planos = PlanoDeUsuario.query.order_by(func.lower(PlanoDeUsuario.nome)).all()
    form.plano_id.choices = [(plano.id, plano.nome) for plano in planos]
    if form.plano_id.data is None:
        padrao = next((plano for plano in planos if plano.padrao), None)
        form.plano_id.data = padrao.id if padrao else None
    return form


@principal.route("/administracao/usuarios/novo", methods=["GET", "POST"])
@auth_required()
def criar_usuario():
    exigir_administrador()
    form = preparar_usuario_form(UsuarioForm())
    if form.validate_on_submit():
        erros_da_senha, senha = security.password_util.validate(
            form.senha.data, True, nome=form.nome.data, email=form.email.data
        )
        if email_em_uso(form.email.data):
            form.email.errors.append("Este e-mail já está cadastrado.")
        elif erros_da_senha:
            form.senha.errors.extend(erros_da_senha)
        else:
            security.datastore.create_user(
                nome=form.nome.data,
                email=form.email.data,
                telefone=form.telefone.data,
                password=hash_password(senha),
                administrador=form.administrador.data == "sim",
                plano_id=form.plano_id.data,
                # Criada pelo administrador, a conta não precisa confirmar o e-mail.
                confirmed_at=agora(),
            )
            db.session.commit()
            return redirect(url_for("principal.usuarios"))
    return render_template("usuario.html", form=form, usuario=None)


@principal.route("/administracao/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@auth_required()
def editar_usuario(usuario_id):
    exigir_administrador()
    usuario = db.get_or_404(Usuario, usuario_id)
    form = UsuarioForm(
        nome=usuario.nome,
        email=usuario.email,
        telefone=usuario.telefone,
        administrador="sim" if usuario.administrador else "nao",
        plano_id=usuario.plano_id,
    )
    preparar_usuario_form(form)
    # A senha de outra pessoa não é alterada por aqui.
    del form.senha
    if form.validate_on_submit():
        administrador = form.administrador.data == "sim"
        if email_em_uso(form.email.data, usuario.id):
            form.email.errors.append("Este e-mail já está cadastrado.")
        elif usuario.id == current_user.id and not administrador:
            # Sem esta regra, o administrador poderia perder o acesso a esta tela.
            form.administrador.errors.append("Você não pode remover o seu próprio acesso de administrador.")
        else:
            usuario.nome = form.nome.data
            usuario.email = form.email.data
            usuario.telefone = form.telefone.data
            usuario.administrador = administrador
            usuario.plano_id = form.plano_id.data
            db.session.commit()
            return redirect(url_for("principal.usuarios"))
    return render_template("usuario.html", form=form, usuario=usuario)


@principal.route("/administracao/usuarios/<int:usuario_id>/excluir", methods=["POST"])
@auth_required()
def excluir_usuario(usuario_id):
    exigir_administrador()
    usuario = db.get_or_404(Usuario, usuario_id)
    if usuario.id == current_user.id:
        flash("Você não pode excluir a sua própria conta.", "erro")
        return redirect(url_for("principal.usuarios"))

    anexos = (
        Anexo.query.join(Tarefa).join(Projeto).filter(Projeto.usuario_id == usuario.id).all()
    )
    imagens = Imagem.query.filter_by(usuario_id=usuario.id).all()
    codigos = [item.arquivo for item in anexos + imagens] + ([usuario.foto] if usuario.foto else [])
    for imagem in imagens:
        db.session.delete(imagem)
    # Nos cartões de outros usuários, quem é excluído deixa de ser o responsável.
    Tarefa.query.filter_by(responsavel_id=usuario.id).update({Tarefa.responsavel_id: None})
    AvisoEnviado.query.filter_by(usuario_id=usuario.id).delete()
    EventoDaTarefa.query.filter_by(usuario_id=usuario.id).update({EventoDaTarefa.usuario_id: None})
    db.session.delete(usuario)
    db.session.commit()
    apagar_arquivos(codigos)
    flash("Usuário excluído.", "sucesso")
    return redirect(url_for("principal.usuarios"))


# A contagem é uma subconsulta, e não um GROUP BY do grupo: o Oracle e o SQL Server exigem no
# GROUP BY todas as colunas do SELECT, e a descrição (texto longo) não pode entrar nele.
QUANTIDADE_DE_MEMBROS = (
    select(func.count())
    .select_from(membros_dos_grupos)
    .where(membros_dos_grupos.c.grupo_id == GrupoDeUsuarios.id)
    .correlate(GrupoDeUsuarios)
    .scalar_subquery()
)
ORDENS_DOS_GRUPOS = {
    "nome": func.lower(GrupoDeUsuarios.nome),
    "usuarios": QUANTIDADE_DE_MEMBROS,
}


def grupo_por_id(grupo_id):
    return db.get_or_404(GrupoDeUsuarios, grupo_id)


def exigir_administrador_do_grupo(grupo):
    if not grupo.administrado_por(current_user):
        abort(403)


def contexto_do_grupo_form(form, grupo=None):
    return {
        "form": form,
        "grupo": grupo,
        "categorias_de_icone": [
            (categoria, [(chave, rotulo) for chave, rotulo, c in ICONES_GRUPO if c == categoria])
            for categoria in CATEGORIAS_DE_ICONE_GRUPO
        ],
    }


@principal.route("/grupos")
@auth_required()
def grupos():
    ordem = request.args.get("ordem", "nome")
    if ordem not in ORDENS_DOS_GRUPOS:
        ordem = "nome"
    decrescente = request.args.get("sentido") == "desc"
    expressao = ORDENS_DOS_GRUPOS[ordem]
    todos = (
        db.session.query(GrupoDeUsuarios)
        .order_by(
            expressao.desc() if decrescente else expressao.asc(),
            # O SQL Server recusa a mesma expressão duas vezes no ORDER BY.
            *([] if ordem == "nome" else [func.lower(GrupoDeUsuarios.nome)]),
            GrupoDeUsuarios.id,
        )
        .all()
    )
    return render_template(
        "grupos.html",
        todos_os_grupos=todos,
        ordem=ordem,
        sentido="desc" if decrescente else "asc",
    )


@principal.route("/grupos/novo", methods=["GET", "POST"])
@auth_required()
def criar_grupo():
    form = GrupoForm(icone="pessoas")
    if form.validate_on_submit():
        grupo = GrupoDeUsuarios(
            nome=form.nome.data,
            descricao=form.descricao.data,
            cor=form.cor.data,
            icone=form.icone.data,
            ingresso=form.ingresso.data,
            administrador_id=current_user.id,
        )
        grupo.membros.append(current_user._get_current_object())
        db.session.add(grupo)
        db.session.commit()
        return redirect(url_for("principal.grupos"))
    return render_template("grupo.html", **contexto_do_grupo_form(form))


@principal.route("/grupos/<int:grupo_id>/editar", methods=["GET", "POST"])
@auth_required()
def editar_grupo(grupo_id):
    grupo = grupo_por_id(grupo_id)
    exigir_administrador_do_grupo(grupo)
    form = GrupoForm(
        nome=grupo.nome,
        descricao=grupo.descricao,
        cor=grupo.cor,
        icone=grupo.icone,
        ingresso=grupo.ingresso,
    )
    if form.validate_on_submit():
        grupo.nome = form.nome.data
        grupo.descricao = form.descricao.data
        grupo.cor = form.cor.data
        grupo.icone = form.icone.data
        grupo.ingresso = form.ingresso.data
        db.session.commit()
        return redirect(url_for("principal.grupos"))
    return render_template("grupo.html", **contexto_do_grupo_form(form, grupo))


@principal.route("/grupos/<int:grupo_id>/excluir", methods=["POST"])
@auth_required()
def excluir_grupo(grupo_id):
    grupo = grupo_por_id(grupo_id)
    exigir_administrador_do_grupo(grupo)
    db.session.delete(grupo)
    db.session.commit()
    flash("Grupo excluído.", "sucesso")
    return redirect(url_for("principal.grupos"))


@principal.route("/grupos/<int:grupo_id>/membros")
@auth_required()
def membros_do_grupo(grupo_id):
    grupo = grupo_por_id(grupo_id)
    # Os nomes e os e-mails dos membros ficam só entre eles.
    if not grupo.tem_membro(current_user):
        abort(403)
    membros = sorted(grupo.membros, key=lambda u: ((u.nome or "").lower(), u.email))
    return render_template("membros.html", grupo=grupo, membros=membros)


@principal.route("/grupos/<int:grupo_id>/membros/<int:usuario_id>/excluir", methods=["POST"])
@auth_required()
def excluir_membro(grupo_id, usuario_id):
    grupo = grupo_por_id(grupo_id)
    exigir_administrador_do_grupo(grupo)
    membro = db.get_or_404(Usuario, usuario_id)
    if membro.id == grupo.administrador_id:
        # Sem o administrador, ninguém mais poderia alterar o grupo.
        flash("O administrador não pode ser excluído do grupo.", "erro")
    elif grupo.tem_membro(membro):
        grupo.membros.remove(membro)
        db.session.commit()
        flash("Membro excluído do grupo.", "sucesso")
    return redirect(url_for("principal.membros_do_grupo", grupo_id=grupo.id))


@principal.route("/grupos/<int:grupo_id>/ingressar", methods=["POST"])
@auth_required()
def ingressar_no_grupo(grupo_id):
    grupo = grupo_por_id(grupo_id)
    if not grupo.pode_ingressar(current_user):
        abort(403)
    grupo.membros.append(current_user._get_current_object())
    db.session.commit()
    return redirect(url_for("principal.grupos"))


@principal.route("/grupos/<int:grupo_id>/adicionar")
@auth_required()
def adicionar_membros(grupo_id):
    grupo = grupo_por_id(grupo_id)
    if not grupo.pode_adicionar(current_user):
        abort(403)
    # Sem a lista de contas: só a pessoa com o e-mail informado por inteiro.
    busca = request.args.get("busca", "").strip()[:255]
    candidatos = []
    if busca:
        candidatos = Usuario.query.filter(
            func.lower(Usuario.email) == busca.lower(),
            Usuario.id.notin_([membro.id for membro in grupo.membros]),
            Usuario.active == true(),
        ).all()
    return render_template(
        "adicionar_membros.html", grupo=grupo, candidatos=candidatos, busca=busca
    )


@principal.route("/grupos/<int:grupo_id>/adicionar/<int:usuario_id>", methods=["POST"])
@auth_required()
def adicionar_membro(grupo_id, usuario_id):
    grupo = grupo_por_id(grupo_id)
    if not grupo.pode_adicionar(current_user):
        abort(403)
    usuario = db.get_or_404(Usuario, usuario_id)
    if not grupo.tem_membro(usuario):
        grupo.membros.append(usuario)
        db.session.commit()
    return redirect(
        url_for("principal.adicionar_membros", grupo_id=grupo.id, busca=request.form.get("busca") or None)
    )


@principal.route("/categorias/<int:categoria_id>/compartilhar", methods=["GET", "POST"])
@auth_required()
def compartilhar_categoria(categoria_id):
    categoria = categoria_do_usuario(categoria_id)
    grupos_do_usuario = sorted(
        current_user.grupos, key=lambda grupo: (grupo.nome.lower(), grupo.id)
    )
    atuais = {item.grupo_id: item for item in categoria.compartilhamentos}
    validas = {valor for valor, _ in PERMISSOES_DE_COMPARTILHAMENTO}
    form = FlaskForm()
    if form.validate_on_submit():
        for grupo in grupos_do_usuario:
            escolha = request.form.get("grupo-{}".format(grupo.id), "")
            atual = atuais.get(grupo.id)
            if escolha not in validas:
                if atual:
                    db.session.delete(atual)
            elif atual:
                atual.permissao = escolha
            else:
                categoria.compartilhamentos.append(
                    CompartilhamentoDeCategoria(grupo_id=grupo.id, permissao=escolha)
                )
        db.session.commit()
        return redirect(url_for("principal.quadro", categoria=categoria.id))
    return render_template(
        "compartilhar.html",
        form=form,
        categoria=categoria,
        grupos_do_usuario=grupos_do_usuario,
        atuais={grupo_id: item.permissao for grupo_id, item in atuais.items()},
        permissoes=PERMISSOES_DE_COMPARTILHAMENTO,
    )


MENSAGENS_DO_VIDEO = {
    EnderecoInvalido: (400, "Informe o endereço de um vídeo do YouTube ou do Vimeo, com até 400 caracteres."),
    ErroDeConexao: (502, "Não foi possível conectar ao endereço informado. Verifique a conexão com a internet e tente novamente."),
    ErroNasInformacoes: (422, "Não foi possível buscar as informações do vídeo. Confira se o vídeo existe e é público."),
}


@principal.route("/api/videos", methods=["POST"])
@auth_required()
def criar_video():
    dados = request.get_json(silent=True)
    if (
        not isinstance(dados, dict)
        or type(dados.get("projeto_id")) is not int
        or not isinstance(dados.get("endereco"), str)
    ):
        return jsonify(erro="Dados inválidos."), 400
    projeto = projeto_editavel(dados["projeto_id"])
    erro = erro_de_limite(projeto.usuario, "videos")
    if erro:
        # Antes de acessar a internet: sem vaga no plano, não há o que buscar.
        return jsonify(erro=erro), 422
    endereco = dados["endereco"].strip()
    try:
        informacoes = videos.buscar_informacoes(endereco)
    except tuple(MENSAGENS_DO_VIDEO) as erro:
        codigo, mensagem = MENSAGENS_DO_VIDEO[type(erro)]
        return jsonify(erro=mensagem), codigo

    tarefa = Tarefa(
        nome=informacoes["titulo"][:120],
        tipo=TIPO_VIDEO,
        projeto_id=projeto.id,
        posicao=proxima_posicao_tarefa(projeto.id),
    )
    tarefa.video = VideoDoYoutube(
        endereco=endereco,
        plataforma=informacoes["plataforma"],
        codigo=informacoes["codigo"],
        endereco_da_miniatura=informacoes["miniatura"],
        autor=informacoes["autor"],
        titulo=informacoes["titulo"],
        descricao=informacoes["descricao"],
        duracao=informacoes["duracao"],
        publicado_em=informacoes["publicacao"],
    )
    registrar(tarefa, "criou")
    db.session.add(tarefa)
    db.session.commit()
    return jsonify(
        id=tarefa.id,
        publicacao=tarefa.video.data_de_publicacao,
        **{chave: informacoes[chave] for chave in ("autor", "titulo", "descricao", "duracao")},
    ), 201


@principal.route("/api/videos/previa", methods=["POST"])
@auth_required()
def previa_do_video():
    """Receber Informações no cartão generalista: lê o vídeo no YouTube ou no Vimeo sem gravar nada.

    Ao salvar o cartão, o servidor lê de novo: o que o navegador envia não é usado como dado do vídeo.
    """
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict) or not isinstance(dados.get("endereco"), str):
        return jsonify(erro="Dados inválidos."), 400
    try:
        informacoes = videos.buscar_informacoes(dados["endereco"].strip())
    except tuple(MENSAGENS_DO_VIDEO) as erro:
        codigo, mensagem = MENSAGENS_DO_VIDEO[type(erro)]
        return jsonify(erro=mensagem), codigo
    video = VideoDoYoutube(
        plataforma=informacoes["plataforma"], codigo=informacoes["codigo"],
        endereco_da_miniatura=informacoes["miniatura"], publicado_em=informacoes["publicacao"],
    )
    return jsonify(
        plataforma=video.plataforma, nome_da_plataforma=video.nome_da_plataforma,
        autor=informacoes["autor"], titulo=informacoes["titulo"], descricao=informacoes["descricao"],
        duracao=informacoes["duracao"], publicacao=video.data_de_publicacao,
        player=video.endereco_do_player, miniatura=video.miniatura,
    )


@principal.route("/api/videos/<int:tarefa_id>/atualizar", methods=["POST"])
@auth_required()
def atualizar_video(tarefa_id):
    """Busca de novo no YouTube ou no Vimeo, pelo código gravado, os dados lidos ao criar o vídeo.

    As Informações Adicionais e as marcações, escritas por quem usa o sistema, não mudam.
    """
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    if not tarefa.e_video:
        abort(404)
    try:
        informacoes = videos.informacoes(tarefa.video.plataforma or videos.YOUTUBE, tarefa.video.codigo)
    except (ErroDeConexao, ErroNasInformacoes) as erro:
        codigo, mensagem = MENSAGENS_DO_VIDEO[type(erro)]
        return jsonify(erro=mensagem), codigo

    video = tarefa.video
    video.autor = informacoes["autor"]
    video.titulo = informacoes["titulo"]
    video.descricao = informacoes["descricao"]
    video.duracao = informacoes["duracao"]
    video.publicado_em = informacoes["publicacao"]
    video.endereco_da_miniatura = informacoes["miniatura"]
    tarefa.nome = informacoes["titulo"][:120]
    registrar(tarefa, "atualizou_video")
    db.session.commit()
    return jsonify(
        autor=video.autor, titulo=video.titulo, descricao=video.descricao,
        duracao=video.duracao, publicacao=video.data_de_publicacao,
    )


@principal.route("/videos/<int:tarefa_id>/editar", methods=["POST"])
@auth_required()
def editar_video(tarefa_id):
    tarefa = tarefa_acessivel(tarefa_id, editar=True)
    if not tarefa.e_video:
        abort(404)
    form = VideoForm()
    if form.validate_on_submit():
        tarefa.video.informacoes_adicionais = form.informacoes_adicionais.data
        salvar_marcacoes(tarefa, form)
        registrar(tarefa, "alterou")
        db.session.commit()
    else:
        informar_erros(form)
    return voltar_ao_quadro()


def capacidades_para_ordenar(plano):
    # Armazenamento primeiro e, no empate, os limites na ordem da coluna; Ilimitadas é o maior.
    limites = [float("inf") if getattr(plano, chave) is None else getattr(plano, chave) for chave in LIMITES_DO_PLANO]
    return [plano.armazenamento_mb] + limites


ORDENS_DOS_PLANOS = {
    "nome": lambda plano: plano.nome.casefold(),
    "capacidades": capacidades_para_ordenar,
    "usuarios": lambda plano: len(plano.usuarios),
}


def nome_de_plano_em_uso(nome, plano_id=None):
    # A comparação é feita no Python: o lower() do SQLite não converte letras acentuadas.
    return any(
        plano.nome.casefold() == nome.casefold()
        for plano in PlanoDeUsuario.query.filter(PlanoDeUsuario.id != (plano_id or 0))
    )


def salvar_plano(plano, form):
    plano.nome = form.nome.data
    plano.armazenamento_mb = form.armazenamento_mb.data
    for chave in LIMITES_DO_PLANO:
        setattr(plano, chave, form[chave].data)
    if form.padrao.data and not plano.padrao:
        # Só um plano é o padrão: marcar este desmarca o anterior.
        PlanoDeUsuario.query.filter(PlanoDeUsuario.padrao == true()).update({"padrao": False})
        plano.padrao = True


def motivo_para_nao_excluir(plano):
    if plano.padrao:
        return "O plano padrão não pode ser excluído: marque outro plano como padrão antes."
    if plano.usuarios:
        return "Este plano tem usuários: mude o plano deles antes de excluí-lo."
    return None


@principal.route("/administracao/planos")
@auth_required()
def planos():
    exigir_administrador()
    # Sem escolha na tela, a listagem começa pelas capacidades, do menor plano para o maior.
    ordem = request.args.get("ordem", "capacidades")
    if ordem not in ORDENS_DOS_PLANOS:
        ordem = "capacidades"
    decrescente = request.args.get("sentido") == "desc"
    # São poucos planos: a ordem é feita no Python, com o nome como desempate.
    todos = sorted(PlanoDeUsuario.query.all(), key=lambda plano: plano.nome.casefold())
    todos.sort(key=ORDENS_DOS_PLANOS[ordem], reverse=decrescente)
    return render_template(
        "planos.html",
        todos_os_planos=todos,
        ordem=ordem,
        sentido="desc" if decrescente else "asc",
        motivo_para_nao_excluir=motivo_para_nao_excluir,
    )


@principal.route("/administracao/planos/novo", methods=["GET", "POST"])
@auth_required()
def criar_plano():
    exigir_administrador()
    form = PlanoForm()
    if form.validate_on_submit():
        if nome_de_plano_em_uso(form.nome.data):
            form.nome.errors.append("Já existe um plano com este nome.")
        else:
            plano = PlanoDeUsuario()
            salvar_plano(plano, form)
            db.session.add(plano)
            db.session.commit()
            return redirect(url_for("principal.planos"))
    return render_template("plano.html", form=form, plano=None, limites=LIMITES_DO_PLANO)


@principal.route("/administracao/planos/<int:plano_id>/editar", methods=["GET", "POST"])
@auth_required()
def editar_plano(plano_id):
    exigir_administrador()
    plano = db.get_or_404(PlanoDeUsuario, plano_id)
    form = PlanoForm(obj=plano)
    if form.validate_on_submit():
        if nome_de_plano_em_uso(form.nome.data, plano.id):
            form.nome.errors.append("Já existe um plano com este nome.")
        elif plano.padrao and not form.padrao.data:
            # Sem um plano padrão, as contas novas ficariam sem plano.
            form.padrao.errors.append("Para desmarcar, marque outro plano como padrão.")
        else:
            salvar_plano(plano, form)
            db.session.commit()
            return redirect(url_for("principal.planos"))
    return render_template("plano.html", form=form, plano=plano, limites=LIMITES_DO_PLANO)


@principal.route("/administracao/planos/<int:plano_id>/excluir", methods=["POST"])
@auth_required()
def excluir_plano(plano_id):
    exigir_administrador()
    plano = db.get_or_404(PlanoDeUsuario, plano_id)
    motivo = motivo_para_nao_excluir(plano)
    if motivo:
        flash(motivo, "erro")
    else:
        db.session.delete(plano)
        db.session.commit()
        flash("Plano excluído.", "sucesso")
    return redirect(url_for("principal.planos"))
