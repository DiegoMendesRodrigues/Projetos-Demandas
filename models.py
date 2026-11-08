# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from datetime import datetime

from flask_security import RoleMixin, UserMixin
from sqlalchemy import event, select, true

import videos
from config import FUSO_HORARIO
from extensions import db
from tipos_do_banco import DataHora, TextoLongoVazio, TextoVazio

def agora_em_sao_paulo():
    """O horário de São Paulo, sem fuso, como as demais datas do banco (routes.agora)."""
    return datetime.now(FUSO_HORARIO).replace(tzinfo=None)


TEMAS = [
    ("azul", "Azul"),
    ("cinza", "Cinza"),
    ("laranja", "Laranja"),
    ("verde", "Verde"),
    ("vermelho", "Vermelho"),
]
PRIORIDADES = [("baixa", "Baixa"), ("media", "Média"), ("alta", "Alta")]
# Automação, no Meu Perfil: quem recebe os avisos dos cartões e com quantos dias de antecedência.
DESTINATARIOS_DOS_AVISOS = [
    ("responsavel_e_proprietario", "Responsável e Proprietário do cartão"),
    ("proprietario", "Proprietário do cartão"),
]
DESTINATARIOS_PADRAO = "responsavel_e_proprietario"
ANTECEDENCIAS_DOS_AVISOS = [(3, "3 dias"), (2, "2 dias"), (1, "1 dia")]
ANTECEDENCIA_PADRAO = 2
# A demanda comum tem a Descrição; a lista de tarefas tem, no lugar dela, itens a concluir.
# O cartão generalista tem os campos iniciais e as seções que o usuário acrescentar.
TIPO_GENERALISTA = "generalista"
TIPOS_DE_ATIVIDADE = ["atividade", "lista_de_tarefas", TIPO_GENERALISTA]
# As seções que podem ser acrescentadas ao cartão generalista, na ordem em que aparecem.
SECOES_DO_GENERALISTA = ["arquivos", "descricao", "tarefas", "video"]
# O vídeo é criado só a partir do YouTube ou do Vimeo, por /api/videos: não entra no formulário da demanda.
TIPO_VIDEO = "video"
LIMITE_ITENS = 100
# Marcações ("tags") de cada cartão.
LIMITE_MARCACOES = 20
TAMANHO_DA_MARCACAO = 40
CORES_PROJETO = [
    ("#1a6fe0", "Azul"),
    ("#00b0f0", "Céu"),
    ("#00c2a8", "Turquesa"),
    ("#22b455", "Verde"),
    ("#8ed100", "Lima"),
    ("#ffc800", "Amarelo"),
    ("#ff8a00", "Laranja"),
    ("#ff5a4f", "Coral"),
    ("#ff3d9a", "Rosa"),
    ("#9b51e0", "Lilás"),
    ("#c8963e", "Areia"),
    ("#78839a", "Cinza"),
]
COR_PADRAO = CORES_PROJETO[0][0]
ICONES_CATEGORIA = [
    ("etiqueta", "Etiqueta"),
    ("trabalho", "Trabalho"),
    ("casa", "Casa"),
    ("estudo", "Estudo"),
    ("saude", "Saúde"),
    ("compras", "Compras"),
    ("dinheiro", "Dinheiro"),
    ("viagem", "Viagem"),
    ("carro", "Carro"),
    ("exercicio", "Exercício"),
    ("musica", "Música"),
    ("filmes", "Filmes"),
    ("jogos", "Jogos"),
    ("comida", "Comida"),
    ("cafe", "Café"),
    ("pessoas", "Pessoas"),
    ("animais", "Animais"),
    ("ideias", "Ideias"),
    ("estrela", "Estrela"),
    ("calendario", "Calendário"),
    ("ferramentas", "Ferramentas"),
    ("computador", "Computador"),
    ("plantas", "Plantas"),
    ("presente", "Presente"),
]
ICONE_PADRAO = ICONES_CATEGORIA[0][0]
# Fundos do quadro de cada categoria: o desenho de cada um está em .fundo-<chave> de style.css.
FUNDOS_DO_QUADRO = [
    ("padrao", "Padrão"),
    ("ceu", "Céu"),
    ("menta", "Menta"),
    ("lavanda", "Lavanda"),
    ("pessego", "Pêssego"),
    ("areia", "Areia"),
    ("rosa", "Rosa"),
    ("aurora", "Aurora"),
    ("oceano", "Oceano"),
    ("por_do_sol", "Pôr do sol"),
]
FUNDO_PADRAO = FUNDOS_DO_QUADRO[0][0]
# A chave é gênero-cabelo-acessório; o macro avatar de _icones.html desenha cada parte.
AVATARES = [
    ("masculino-sem", "Masculino sem cabelo"),
    ("masculino-curto", "Masculino com cabelo curto"),
    ("masculino-direita", "Masculino com cabelo curto para a direita"),
    ("masculino-esquerda", "Masculino com cabelo curto para a esquerda"),
    ("masculino-comprido", "Masculino com cabelo comprido"),
    ("masculino-sem-oculos", "Masculino sem cabelo, com óculos"),
    ("masculino-curto-oculos", "Masculino com cabelo curto e óculos"),
    ("masculino-sem-gravata", "Masculino sem cabelo, com gravata"),
    ("masculino-curto-gravata", "Masculino com cabelo curto e gravata"),
    ("masculino-curto-ideia", "Masculino com cabelo curto e ideia"),
    ("feminino-sem", "Feminino sem cabelo"),
    ("feminino-curto", "Feminino com cabelo curto"),
    ("feminino-direita", "Feminino com cabelo curto para a direita"),
    ("feminino-esquerda", "Feminino com cabelo curto para a esquerda"),
    ("feminino-comprido", "Feminino com cabelo comprido"),
    ("feminino-curto-oculos", "Feminino com cabelo curto e óculos"),
    ("feminino-comprido-oculos", "Feminino com cabelo comprido e óculos"),
    ("feminino-curto-gravata", "Feminino com cabelo curto e gravata"),
    ("feminino-comprido-gravata", "Feminino com cabelo comprido e gravata"),
    ("feminino-comprido-ideia", "Feminino com cabelo comprido e ideia"),
]
# Enquanto o usuário não escolhe, o sistema não presume um gênero.
AVATAR_PADRAO = "neutro-sem"
# Com a foto enviada em Meu Perfil, o avatar vale "foto" e o arquivo fica em Usuario.foto.
AVATAR_FOTO = "foto"
# O espaço para anexos é a soma dos tamanhos dos anexos de todas as demandas do usuário,
# limitada pelo plano. Os testes trocam esta constante para trabalhar com arquivos pequenos.
BYTES_POR_MB = 1024 * 1024
# Só vale se não houver plano nenhum, o que atualizar_banco() não deixa acontecer.
ESPACO_SEM_PLANO_MB = 10


# Quem pode colocar outros usuários em um grupo.
FORMAS_DE_INGRESSO = [
    ("qualquer_usuario", "Qualquer usuário do sistema pode ingressar"),
    ("qualquer_membro", "Qualquer usuário do grupo pode adicionar outros membros"),
    ("administrador", "Apenas o administrador pode adicionar outros membros"),
]
FORMA_DE_INGRESSO_PADRAO = FORMAS_DE_INGRESSO[2][0]
# O que os outros membros do grupo podem fazer em uma categoria compartilhada.
PERMISSOES_DE_COMPARTILHAMENTO = [("visualizar", "Visualizar"), ("editar", "Editar")]
LIMITE_NOME_GRUPO = 100


UNIDADES_DE_DURACAO = [
    ("dia", "dias", 24 * 60 * 60),
    ("hora", "horas", 60 * 60),
    ("minuto", "minutos", 60),
]


def rotulo_de_duracao(duracao):
    """Prazo por extenso em português, como "1 dia e 2 horas"."""
    segundos = int(duracao.total_seconds())
    partes = []
    for singular, plural, tamanho in UNIDADES_DE_DURACAO:
        quantidade, segundos = divmod(segundos, tamanho)
        if quantidade:
            partes.append("{} {}".format(quantidade, singular if quantidade == 1 else plural))
    if not partes:
        return "menos de 1 minuto"
    return " e ".join([", ".join(partes[:-1]), partes[-1]]) if len(partes) > 1 else partes[0]


def rotulo_em_megabytes(tamanho):
    valor = "{:.2f}".format(tamanho / (1024 * 1024)).removesuffix(".00")
    return "{} MB".format(valor.replace(".", ","))


def rotulo_de_tamanho(tamanho):
    if tamanho < 1024:
        return "{} B".format(tamanho)
    if tamanho < 1024 * 1024:
        return "{:.1f} KB".format(tamanho / 1024).replace(".", ",")
    return "{:.1f} MB".format(tamanho / (1024 * 1024)).replace(".", ",")

usuarios_papeis = db.Table(
    "usuarios_papeis",
    db.Column("usuario_id", db.ForeignKey("usuario.id"), primary_key=True),
    db.Column("papel_id", db.ForeignKey("papel.id"), primary_key=True),
)


membros_dos_grupos = db.Table(
    "membros_dos_grupos",
    db.Column("grupo_id", db.ForeignKey("grupo_de_usuarios.id"), primary_key=True),
    db.Column("usuario_id", db.ForeignKey("usuario.id"), primary_key=True),
)


class Papel(db.Model, RoleMixin):
    __tablename__ = "papel"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))


class Usuario(db.Model, UserMixin):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    nome = db.Column(TextoVazio(120), nullable=False, default="")
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    fs_uniquifier = db.Column(db.String(64), unique=True, nullable=False)
    tema = db.Column(db.String(20), nullable=False, default="azul")
    mostrar_ocultas = db.Column(db.Boolean, nullable=False, default=False)
    avatar = db.Column(db.String(40), nullable=False, default=AVATAR_PADRAO)
    # Nome aleatório do PNG da foto do perfil em ANEXOS_DIR; vazio sem foto.
    foto = db.Column(TextoVazio(64), nullable=False, default="")
    administrador = db.Column(db.Boolean, nullable=False, default=False)
    plano_id = db.Column(db.ForeignKey("plano_de_usuario.id"), index=True)
    telefone = db.Column(TextoVazio(15), nullable=False, default="")
    aviso_destinatarios = db.Column(db.String(30), nullable=False, default=DESTINATARIOS_PADRAO)
    aviso_antecedencia = db.Column(db.Integer, nullable=False, default=ANTECEDENCIA_PADRAO)
    # A conta inicial nasce com a senha padrão, que é pública: o primeiro login exige trocá-la.
    trocar_senha = db.Column(db.Boolean, nullable=False, default=False)
    # Preenchido pelo Flask-Security quando a pessoa confirma o e-mail (SECURITY_CONFIRMABLE).
    confirmed_at = db.Column(DataHora)
    # O último login ou uso do sistema (registrar_acesso, em seguranca.py). Conta o prazo de
    # inatividade do plano (inatividade.py); a conta nova começa a contar ao ser criada.
    ultimo_acesso = db.Column(DataHora, default=lambda: agora_em_sao_paulo())
    # Quando saiu o e-mail avisando da exclusão por inatividade; volta a vazio no próximo acesso.
    aviso_de_exclusao_em = db.Column(DataHora)

    roles = db.relationship("Papel", secondary=usuarios_papeis, backref="usuarios")
    categorias = db.relationship(
        "Categoria",
        back_populates="usuario",
        cascade="all, delete-orphan",
        order_by="Categoria.nome",
    )
    projetos = db.relationship(
        "Projeto",
        back_populates="usuario",
        cascade="all, delete-orphan",
        order_by="Projeto.posicao",
    )

    grupos_administrados = db.relationship(
        "GrupoDeUsuarios",
        foreign_keys="GrupoDeUsuarios.administrador_id",
        back_populates="administrador",
        cascade="all, delete-orphan",
    )
    grupos = db.relationship(
        "GrupoDeUsuarios", secondary=membros_dos_grupos, back_populates="membros"
    )

    plano = db.relationship("PlanoDeUsuario", back_populates="usuarios")

    @property
    def plano_efetivo(self):
        return self.plano or PlanoDeUsuario.query.filter_by(padrao=True).first()

    @property
    def plano_rotulo(self):
        plano = self.plano_efetivo
        return plano.nome if plano else "Sem plano"

    @property
    def espaco_para_anexos(self):
        plano = self.plano_efetivo
        return (plano.armazenamento_mb if plano else ESPACO_SEM_PLANO_MB) * BYTES_POR_MB


    @property
    def avisa_o_responsavel(self):
        """Nos cartões deste usuário, o responsável também recebe os avisos."""
        return self.aviso_destinatarios == "responsavel_e_proprietario"

class GrupoDeUsuarios(db.Model):
    __tablename__ = "grupo_de_usuarios"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    nome = db.Column(db.String(LIMITE_NOME_GRUPO), nullable=False)
    descricao = db.Column(TextoLongoVazio, nullable=False, default="")
    cor = db.Column(db.String(7), nullable=False, default=COR_PADRAO)
    icone = db.Column(db.String(30), nullable=False, default="pessoas")
    ingresso = db.Column(db.String(20), nullable=False, default=FORMA_DE_INGRESSO_PADRAO)
    administrador_id = db.Column(db.ForeignKey("usuario.id"), nullable=False, index=True)

    administrador = db.relationship(
        "Usuario", foreign_keys=[administrador_id], back_populates="grupos_administrados"
    )
    membros = db.relationship(
        "Usuario", secondary=membros_dos_grupos, back_populates="grupos"
    )
    compartilhamentos = db.relationship(
        "CompartilhamentoDeCategoria", back_populates="grupo", cascade="all, delete-orphan"
    )

    def administrado_por(self, usuario):
        return usuario.id == self.administrador_id

    def tem_membro(self, usuario):
        return any(membro.id == usuario.id for membro in self.membros)

    def pode_adicionar(self, usuario):
        """Quem vê o botão Adicionar Membros: o administrador, ou os membros se o grupo permitir."""
        if self.administrado_por(usuario):
            return self.ingresso != "qualquer_usuario"
        return self.ingresso == "qualquer_membro" and self.tem_membro(usuario)

    def pode_ingressar(self, usuario):
        return self.ingresso == "qualquer_usuario" and not self.tem_membro(usuario)


class Categoria(db.Model):
    __tablename__ = "categoria"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    icone = db.Column(db.String(30), nullable=False, default=ICONE_PADRAO)
    fundo = db.Column(db.String(20), nullable=False, default=FUNDO_PADRAO)
    usuario_id = db.Column(db.ForeignKey("usuario.id"), nullable=False, index=True)

    usuario = db.relationship("Usuario", back_populates="categorias")
    projetos = db.relationship("Projeto", back_populates="categoria")
    compartilhamentos = db.relationship(
        "CompartilhamentoDeCategoria", back_populates="categoria", cascade="all, delete-orphan"
    )

    def permissao_de(self, usuario):
        """Devolve dono, editar, visualizar ou None: vale a maior permissão entre os grupos do usuário."""
        if self.usuario_id == usuario.id:
            return "dono"
        permissoes = {
            compartilhamento.permissao
            for compartilhamento in self.compartilhamentos
            if compartilhamento.grupo.tem_membro(usuario)
        }
        if "editar" in permissoes:
            return "editar"
        return "visualizar" if permissoes else None


class CompartilhamentoDeCategoria(db.Model):
    """A categoria, com os seus projetos e demandas, vista pelos membros de um grupo."""

    __tablename__ = "compartilhamento_de_categoria"
    __table_args__ = (db.UniqueConstraint("categoria_id", "grupo_id"),)

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    categoria_id = db.Column(db.ForeignKey("categoria.id"), nullable=False, index=True)
    grupo_id = db.Column(db.ForeignKey("grupo_de_usuarios.id"), nullable=False, index=True)
    permissao = db.Column(db.String(20), nullable=False, default="visualizar")

    categoria = db.relationship("Categoria", back_populates="compartilhamentos")
    grupo = db.relationship("GrupoDeUsuarios", back_populates="compartilhamentos")


class Projeto(db.Model):
    __tablename__ = "projeto"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    cor = db.Column(db.String(7), nullable=False, default=COR_PADRAO)
    posicao = db.Column(db.Integer, nullable=False, default=0)
    concluida = db.Column(db.Boolean, nullable=False, default=False)
    usuario_id = db.Column(db.ForeignKey("usuario.id"), nullable=False, index=True)
    categoria_id = db.Column(db.ForeignKey("categoria.id"), index=True)

    usuario = db.relationship("Usuario", back_populates="projetos")
    categoria = db.relationship("Categoria", back_populates="projetos")
    tarefas = db.relationship(
        "Tarefa",
        back_populates="projeto",
        cascade="all, delete-orphan",
        order_by="(Tarefa.posicao, Tarefa.id)",
    )


class Tarefa(db.Model):
    __tablename__ = "tarefa"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    prioridade = db.Column(db.String(10), nullable=False, default="baixa")
    previsao_execucao = db.Column(DataHora)
    descricao = db.Column("descricao_html", TextoLongoVazio, nullable=False, default="")
    local = db.Column(TextoVazio(120), nullable=False, default="")
    oculta = db.Column(db.Boolean, nullable=False, default=False)
    posicao = db.Column(db.Integer, nullable=False, default=0)
    tipo = db.Column(db.String(20), nullable=False, default="atividade")
    # Só no cartão generalista: as seções acrescentadas, separadas por vírgula (SECOES_DO_GENERALISTA).
    secoes = db.Column(TextoVazio(60), nullable=False, default="")
    concluida_em = db.Column(DataHora)
    projeto_id = db.Column(db.ForeignKey("projeto.id"), nullable=False, index=True)
    # Quem executa o cartão, escolhido pelo proprietário (o dono do projeto) entre quem vê o quadro.
    responsavel_id = db.Column(db.ForeignKey("usuario.id"), index=True)

    projeto = db.relationship("Projeto", back_populates="tarefas")
    responsavel = db.relationship("Usuario", foreign_keys=[responsavel_id])
    anexos = db.relationship(
        "Anexo",
        back_populates="tarefa",
        cascade="all, delete-orphan",
        order_by="Anexo.id",
    )
    imagens = db.relationship("Imagem", back_populates="tarefa", cascade="all")
    itens = db.relationship(
        "ItemDaTarefa",
        back_populates="tarefa",
        cascade="all, delete-orphan",
        order_by="(ItemDaTarefa.posicao, ItemDaTarefa.id)",
    )

    video = db.relationship(
        "VideoDoYoutube", back_populates="tarefa", uselist=False, cascade="all, delete-orphan"
    )

    avisos = db.relationship("AvisoEnviado", cascade="all, delete-orphan")
    # Histórico e comentários, do mais novo para o mais antigo.
    eventos = db.relationship(
        "EventoDaTarefa",
        back_populates="tarefa",
        cascade="all, delete-orphan",
        order_by="(EventoDaTarefa.momento.desc(), EventoDaTarefa.id.desc())",
    )

    marcacoes = db.relationship(
        "Marcacao",
        back_populates="tarefa",
        cascade="all, delete-orphan",
        order_by="(Marcacao.posicao, Marcacao.id)",
    )

    @property
    def proprietario(self):
        return self.projeto.usuario

    @property
    def responsavel_atual(self):
        """O responsável, enquanto ele ainda tiver acesso ao quadro; senão, nenhum."""
        responsavel = self.responsavel
        if responsavel is None or responsavel.id == self.projeto.usuario_id:
            return None
        categoria = self.projeto.categoria
        if categoria is None or categoria.permissao_de(responsavel) is None:
            return None
        return responsavel

    @property
    def lista_de_tarefas(self):
        return self.tipo == "lista_de_tarefas"

    @property
    def e_video(self):
        return self.tipo == TIPO_VIDEO

    @property
    def generalista(self):
        return self.tipo == TIPO_GENERALISTA

    @property
    def secoes_ativas(self):
        escolhidas = set((self.secoes or "").split(","))
        return [secao for secao in SECOES_DO_GENERALISTA if secao in escolhidas]

    @property
    def todas_as_tarefas_concluidas(self):
        return bool(self.itens) and all(item.concluido for item in self.itens)

    @property
    def prioridade_rotulo(self):
        return dict(PRIORIDADES).get(self.prioridade, self.prioridade)


class VideoDoYoutube(db.Model):
    """Os dados lidos do YouTube ou do Vimeo ao criar o vídeo. Só as Informações Adicionais mudam depois.

    O nome da classe e da tabela vem de quando só havia o YouTube; mudá-lo exigiria migrar os dados.
    """

    __tablename__ = "video_do_youtube"

    tarefa_id = db.Column(db.ForeignKey("tarefa.id"), primary_key=True)
    endereco = db.Column(db.String(400), nullable=False)
    # "youtube" ou "vimeo" (videos.NOMES_DAS_PLATAFORMAS).
    plataforma = db.Column(db.String(10), nullable=False, default="youtube")
    # No YouTube, 11 caracteres; no Vimeo, o número e, nos vídeos não listados, ":" e o código de privacidade.
    codigo = db.Column(db.String(40), nullable=False)
    # Só no Vimeo, que não monta a miniatura pelo código: o endereço vem do oEmbed, sempre em i.vimeocdn.com.
    endereco_da_miniatura = db.Column(TextoVazio(300), nullable=False, default="")
    autor = db.Column(TextoVazio(100), nullable=False, default="")
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(TextoLongoVazio, nullable=False, default="")
    duracao = db.Column(TextoVazio(20), nullable=False, default="")
    # Vazia nos vídeos gravados antes de o campo existir ou quando o YouTube não informa a data.
    publicado_em = db.Column(db.Date)
    informacoes_adicionais = db.Column(TextoLongoVazio, nullable=False, default="")
    # No cartão simplificado, a miniatura fica pequena, à esquerda do título.
    simplificado = db.Column(db.Boolean, nullable=False, default=False)

    tarefa = db.relationship("Tarefa", back_populates="video")

    @property
    def data_de_publicacao(self):
        return self.publicado_em.strftime("%d/%m/%Y") if self.publicado_em else ""

    @property
    def nome_da_plataforma(self):
        return videos.NOMES_DAS_PLATAFORMAS.get(self.plataforma or videos.YOUTUBE, "YouTube")

    @property
    def miniatura(self):
        return videos.miniatura(self.plataforma or videos.YOUTUBE, self.codigo, self.endereco_da_miniatura)

    @property
    def endereco_do_player(self):
        return videos.endereco_do_player(self.plataforma or videos.YOUTUBE, self.codigo)


TAMANHO_DO_COMENTARIO = 1000
# O que cada evento do histórico diz; {} recebe o `detalhe` gravado.
TEXTOS_DOS_EVENTOS = {
    "criou": "criou o cartão",
    "alterou": "alterou o cartão",
    "moveu": "moveu para o projeto {}",
    "concluiu": "marcou como concluída",
    "reabriu": "desmarcou a conclusão",
    "ocultou": "ocultou o cartão",
    "reexibiu": "reexibiu o cartão",
    "responsavel": "definiu {} como responsável",
    "sem_responsavel": "removeu o responsável",
    "previsao": "mudou a Previsão de Execução para {}",
    "atualizou_video": "atualizou as informações do vídeo",
    "comentario": "comentou",
}


class EventoDaTarefa(db.Model):
    """Uma linha do histórico do cartão: uma ação ou um comentário (tipo "comentario", com o texto)."""

    __tablename__ = "evento_da_tarefa"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    tarefa_id = db.Column(db.ForeignKey("tarefa.id"), nullable=False, index=True)
    # Fica vazio quando a conta de quem agiu é excluída: o histórico continua.
    usuario_id = db.Column(db.ForeignKey("usuario.id"), index=True)
    tipo = db.Column(db.String(20), nullable=False)
    detalhe = db.Column(TextoVazio(200), nullable=False, default="")
    texto = db.Column(TextoLongoVazio, nullable=False, default="")
    momento = db.Column(DataHora, nullable=False)

    tarefa = db.relationship("Tarefa", back_populates="eventos")
    usuario = db.relationship("Usuario")

    @property
    def descricao(self):
        return TEXTOS_DOS_EVENTOS.get(self.tipo, self.tipo).format(self.detalhe)


class AvisoEnviado(db.Model):
    """Cada e-mail de aviso já enviado, para não repetir: um por pessoa, tipo e Previsão de Execução."""

    __tablename__ = "aviso_enviado"
    __table_args__ = (db.UniqueConstraint("tarefa_id", "usuario_id", "tipo", "previsao"),)

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    tarefa_id = db.Column(db.ForeignKey("tarefa.id"), nullable=False, index=True)
    usuario_id = db.Column(db.ForeignKey("usuario.id"), nullable=False, index=True)
    tipo = db.Column(db.String(10), nullable=False)
    previsao = db.Column(DataHora, nullable=False)


class Marcacao(db.Model):
    """As marcações ("tags") de um cartão: demanda, lista de tarefas ou vídeo."""

    __tablename__ = "marcacao"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    texto = db.Column(db.String(TAMANHO_DA_MARCACAO), nullable=False)
    posicao = db.Column(db.Integer, nullable=False, default=0)
    tarefa_id = db.Column(db.ForeignKey("tarefa.id"), nullable=False, index=True)

    tarefa = db.relationship("Tarefa", back_populates="marcacoes")


class ItemDaTarefa(db.Model):
    """Cada tarefa de uma lista de tarefas. Na interface, ela se chama "tarefa"."""

    __tablename__ = "item_da_tarefa"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    texto = db.Column(db.String(255), nullable=False)
    concluido = db.Column(db.Boolean, nullable=False, default=False)
    posicao = db.Column(db.Integer, nullable=False, default=0)
    tarefa_id = db.Column(db.ForeignKey("tarefa.id"), nullable=False, index=True)

    tarefa = db.relationship("Tarefa", back_populates="itens")

    @property
    def dados(self):
        return {"texto": self.texto, "concluido": self.concluido}


class DesafioCaptcha(db.Model):
    """A resposta de cada imagem do CAPTCHA. O navegador recebe só o token, na sessão."""

    __tablename__ = "desafio_captcha"

    token = db.Column(db.String(32), primary_key=True)
    resposta_hash = db.Column(db.String(64), nullable=False)
    criado_em = db.Column(DataHora, nullable=False, index=True)


def opcoes_de_quantidade(inicio, fim, passo, primeira=None, ultimas=()):
    """As quantidades da lista e, no fim, Ilimitadas, gravada como vazio (sem limite).

    `primeira` entra antes da sequência e `ultimas`, depois dela, para valores fora do passo.
    """
    valores = ([primeira] if primeira else []) + list(range(inicio, fim + 1, passo)) + list(ultimas)
    return [(str(valor), str(valor)) for valor in valores] + [("", "Ilimitadas")]


# Campo do plano: (rótulo, opções). A ordem é a dos campos na tela.
LIMITES_DO_PLANO = {
    "categorias": ("Quantidade de Categorias", opcoes_de_quantidade(10, 100, 10)),
    "projetos": ("Quantidade de Projetos", opcoes_de_quantidade(10, 200, 10, ultimas=(300, 400, 500))),
    "atividades": ("Quantidade de Demandas", opcoes_de_quantidade(50, 500, 50, primeira=25)),
    "listas_de_tarefas": ("Quantidade de Listas de Tarefas", opcoes_de_quantidade(50, 500, 50, primeira=25)),
    "videos": ("Quantidade de Vídeos", opcoes_de_quantidade(50, 500, 50, primeira=25)),
}
LIMITE_NOME_PLANO = 100
# Dias sem login ou uso até a conta ser excluída (inatividade.py). Ilimitado é gravado como vazio.
DIAS_DE_INATIVIDADE = [(str(dias), str(dias)) for dias in (15, 30, 60, 90, 120, 180)] + [("", "Ilimitado")]
DIAS_DE_INATIVIDADE_PADRAO = 15
LIMITE_ARMAZENAMENTO_MB = 1024 * 1024


class PlanoDeUsuario(db.Model):
    """Os limites de cada plano. Um limite vazio quer dizer Ilimitadas."""

    __tablename__ = "plano_de_usuario"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    nome = db.Column(db.String(LIMITE_NOME_PLANO), nullable=False, unique=True)
    armazenamento_mb = db.Column(db.Integer, nullable=False)
    categorias = db.Column(db.Integer)
    projetos = db.Column(db.Integer)
    atividades = db.Column(db.Integer)
    listas_de_tarefas = db.Column(db.Integer)
    videos = db.Column(db.Integer)
    # Dias de Inatividade para a Exclusão da Conta; vazio é Ilimitado (nenhuma conta é excluída).
    # Vazio é Ilimitado: os planos criados pelo sistema nascem assim; o formulário sugere 15.
    dias_de_inatividade = db.Column(db.Integer)
    # As contas novas recebem este plano. Há sempre um, e só um, marcado.
    padrao = db.Column(db.Boolean, nullable=False, default=False)

    usuarios = db.relationship("Usuario", back_populates="plano")

    @property
    def capacidades(self):
        """MB / categorias / projetos / demandas / listas de tarefas / vídeos / dias de inatividade;
        * é Ilimitadas."""
        limites = ["*" if getattr(self, chave) is None else str(getattr(self, chave)) for chave in LIMITES_DO_PLANO]
        inatividade = "*" if self.dias_de_inatividade is None else "{} dias".format(self.dias_de_inatividade)
        return " / ".join(["{} MB".format(self.armazenamento_mb)] + limites + [inatividade])

    @property
    def rotulo_da_inatividade(self):
        return "Ilimitado" if self.dias_de_inatividade is None else "{} dias".format(self.dias_de_inatividade)


@event.listens_for(Usuario, "before_insert")
def dar_o_plano_padrao(mapper, conexao, usuario):
    """Toda conta nasce com o plano padrão: pelo cadastro, pelo administrador ou a conta inicial."""
    if usuario.plano_id is None and usuario.plano is None:
        usuario.plano_id = conexao.execute(
            select(PlanoDeUsuario.id).where(PlanoDeUsuario.padrao == true())
        ).scalar()


PORTAS_SMTP = [25, 465, 587, 2525]


class ConfiguracaoEmail(db.Model):
    """Configurações de envio de e-mails salvas na tela de Configurações. Há uma linha só."""

    __tablename__ = "configuracao_email"

    # Sempre 1, gravado pelo sistema: sem IDENTITY, que no SQL Server recusaria o id informado.
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)
    servidor = db.Column(db.String(200), nullable=False)
    porta = db.Column(db.Integer, nullable=False)
    usar_tls = db.Column(db.Boolean, nullable=False, default=True)
    usuario = db.Column(TextoVazio(200), nullable=False)
    # Cifrada com uma chave derivada da SECRET_KEY (cifrar e decifrar, em seguranca.py).
    senha = db.Column(TextoVazio(500), nullable=False)
    email_envio = db.Column(db.String(200), nullable=False)
    nome_envio = db.Column(db.String(200), nullable=False)


class Imagem(db.Model):
    __tablename__ = "imagem"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    arquivo = db.Column(db.String(32), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    usuario_id = db.Column(db.ForeignKey("usuario.id"), nullable=False, index=True)
    # Fica vazio até a tarefa ser salva: a imagem é enviada enquanto o texto é escrito.
    tarefa_id = db.Column(db.ForeignKey("tarefa.id"), index=True)
    # Em bytes: as imagens ocupam o espaço do plano, como os anexos.
    tamanho = db.Column(db.Integer, nullable=False, default=0)
    # As pendentes (sem tarefa) mais antigas que PRAZO_DAS_IMAGENS_PENDENTES são apagadas.
    criado_em = db.Column(DataHora)

    tarefa = db.relationship("Tarefa", back_populates="imagens")


class Anexo(db.Model):
    __tablename__ = "anexo"

    id = db.Column(db.Integer, db.Identity(), primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    arquivo = db.Column(db.String(32), unique=True, nullable=False)
    tamanho = db.Column(db.Integer, nullable=False)
    tarefa_id = db.Column(db.ForeignKey("tarefa.id"), nullable=False, index=True)

    tarefa = db.relationship("Tarefa", back_populates="anexos")

    @property
    def tamanho_rotulo(self):
        return rotulo_de_tamanho(self.tamanho)
