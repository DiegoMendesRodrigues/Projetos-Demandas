# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import json
import os
import re
import unicodedata

import nh3
from flask import current_app
from flask_security import ChangePasswordForm, ForgotPasswordForm, LoginForm, RegisterFormV2
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    DateTimeLocalField,
    EmailField,
    HiddenField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import (
    AnyOf,
    DataRequired,
    Email,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)

from captcha_imagem import TAMANHO_DO_CODIGO, conferir_resposta
from seguranca import senha_conferida
from icones_grupo import ICONES_GRUPO
from models import (
    ANTECEDENCIAS_DOS_AVISOS,
    DESTINATARIOS_DOS_AVISOS,
    AVATAR_FOTO,
    AVATARES,
    FORMA_DE_INGRESSO_PADRAO,
    FORMAS_DE_INGRESSO,
    LIMITE_ARMAZENAMENTO_MB,
    LIMITE_NOME_GRUPO,
    LIMITE_NOME_PLANO,
    LIMITES_DO_PLANO,
    COR_PADRAO,
    CORES_PROJETO,
    FUNDO_PADRAO,
    FUNDOS_DO_QUADRO,
    ICONES_CATEGORIA,
    LIMITE_ITENS,
    LIMITE_MARCACOES,
    TAMANHO_DA_MARCACAO,
    PORTAS_SMTP,
    PRIORIDADES,
    SECOES_DO_GENERALISTA,
    TIPOS_DE_ATIVIDADE,
    TEMAS,
)

TAGS_DA_DESCRICAO = {
    "a", "b", "blockquote", "br", "div", "em", "font", "i", "img",
    "li", "ol", "p", "span", "strong", "u", "ul",
}
ATRIBUTOS_DA_DESCRICAO = {
    "a": {"href"},
    "font": {"color", "size"},
    "img": {"src", "alt"},
}
IMAGEM_DA_DESCRICAO = re.compile(r"/imagens/([0-9a-f]{32})")
COR_DA_FONTE = re.compile(r"#[0-9a-fA-F]{6}|rgb\(\d{1,3}, ?\d{1,3}, ?\d{1,3}\)")


def nome_completo(formulario, campo):
    if len(campo.data.split()) < 2:
        raise ValidationError("Informe seu nome e sobrenome.")


def campo_nome_completo():
    return StringField(
        "Nome completo",
        filters=[lambda valor: valor.strip() if valor else valor],
        validators=[
            DataRequired("Informe seu nome completo."),
            Length(max=120, message="O nome deve ter no máximo 120 caracteres."),
            nome_completo,
        ],
    )


TELEFONE = re.compile(r"\(\d{2}\) \d{4,5}-\d{4}")


def telefone_valido(formulario, campo):
    if campo.data and not TELEFONE.fullmatch(campo.data):
        raise ValidationError("Informe o telefone no formato (00) 00000-0000.")


def campo_telefone():
    return StringField(
        "Telefone",
        filters=[lambda valor: valor.strip() if valor else ""],
        validators=[
            Optional(),
            Length(max=15, message="O telefone deve ter no máximo 15 caracteres."),
            telefone_valido,
        ],
    )


TAMANHO_DA_MENSAGEM_DE_ATENDIMENTO = 5000


class AtendimentoForm(FlaskForm):
    """Formulário da página Atendimento, aberto a qualquer visitante. Só o telefone é opcional."""

    nome = StringField(
        "Nome",
        filters=[lambda valor: valor.strip() if valor else valor],
        validators=[
            DataRequired("Informe seu nome."),
            Length(max=120, message="O nome deve ter no máximo 120 caracteres."),
        ],
    )
    email = EmailField(
        "E-mail",
        filters=[lambda valor: valor.strip() if valor else valor],
        validators=[
            DataRequired("Informe seu e-mail."),
            Length(max=255, message="O e-mail deve ter no máximo 255 caracteres."),
            Email("Informe um e-mail válido."),
        ],
    )
    telefone = campo_telefone()
    mensagem = TextAreaField(
        "Mensagem",
        filters=[lambda valor: valor.strip() if valor else valor],
        validators=[
            DataRequired("Escreva a sua mensagem."),
            Length(
                max=TAMANHO_DA_MENSAGEM_DE_ATENDIMENTO,
                message="A mensagem deve ter no máximo {} caracteres.".format(TAMANHO_DA_MENSAGEM_DE_ATENDIMENTO),
            ),
        ],
    )
    # Escondido das pessoas (CSS e aria-hidden): os robôs que preenchem todos os campos o revelam.
    site = StringField("Site")


class PerfilForm(FlaskForm):
    nome = campo_nome_completo()
    telefone = campo_telefone()
    # Sem valor enviado, os três campos abaixo mantêm o que o usuário já tinha.
    tema = RadioField(
        "Cor da Aplicação",
        choices=TEMAS,
        validate_choice=False,
        validators=[Optional(), AnyOf([valor for valor, _ in TEMAS], message="Escolha uma cor válida.")],
    )
    aviso_destinatarios = SelectField(
        "Quem recebe os avisos quando os cartões estão próximos ao vencimento",
        choices=DESTINATARIOS_DOS_AVISOS,
        validate_choice=False,
        validators=[
            Optional(),
            AnyOf([valor for valor, _ in DESTINATARIOS_DOS_AVISOS], message="Escolha quem recebe os avisos."),
        ],
    )
    aviso_antecedencia = SelectField(
        "O e-mail de aviso é enviado com quantos dias de antecedência",
        choices=ANTECEDENCIAS_DOS_AVISOS,
        coerce=lambda valor: int(valor) if valor not in (None, "") else None,
        validate_choice=False,
        validators=[
            Optional(),
            AnyOf([dias for dias, _ in ANTECEDENCIAS_DOS_AVISOS], message="Escolha a antecedência do aviso."),
        ],
    )
    # A foto enviada é a primeira opção; a rota só a aceita de quem tem uma foto.
    avatar = RadioField(
        "Ícone",
        choices=[(AVATAR_FOTO, "Minha foto")] + AVATARES,
        validate_choice=False,
        validators=[
            Optional(),
            AnyOf([AVATAR_FOTO] + [valor for valor, _ in AVATARES], message="Escolha um ícone válido."),
        ],
    )


def captcha_valido(formulario, campo):
    if current_app.config["CAPTCHA_ATIVO"] and not conferir_resposta(campo.data):
        # O desafio foi consumido: a página volta com uma imagem nova.
        raise ValidationError("O código não confere com a imagem. Digite o código da nova imagem.")
    # No login, a senha só é testada com o código certo: só essas tentativas entram no limite
    # por conta (seguranca.TENTATIVAS_POR_CONTA).
    senha_conferida()


def campo_captcha():
    return StringField(
        "Código da imagem",
        render_kw={
            "autocomplete": "off",
            "autocapitalize": "characters",
            "spellcheck": "false",
            "maxlength": TAMANHO_DO_CODIGO,
        },
        validators=[captcha_valido],
    )


class LoginComCaptchaForm(LoginForm):
    # Os campos do formulário são conferidos antes da senha: sem o código certo, ela nem é testada.
    captcha = campo_captcha()


class EsqueciSenhaComCaptchaForm(ForgotPasswordForm):
    captcha = campo_captcha()


class CadastroForm(RegisterFormV2):
    nome = campo_nome_completo()
    telefone = campo_telefone()
    # O mesmo CAPTCHA do login: o cadastro não pode ser automatizado.
    captcha = campo_captcha()


class AlterarSenhaForm(ChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.password.label.text = "Senha atual"


class UsuarioForm(FlaskForm):
    nome = campo_nome_completo()
    email = EmailField(
        "E-mail",
        filters=[lambda valor: valor.strip().lower() if valor else valor],
        validators=[
            DataRequired("Informe o e-mail."),
            Length(max=255, message="O e-mail deve ter no máximo 255 caracteres."),
            Email("Informe um e-mail válido."),
        ],
    )
    # Só existe ao criar: a tela de edição remove o campo.
    telefone = campo_telefone()
    senha = PasswordField(
        "Senha",
        validators=[
            DataRequired("Informe a senha."),
            Length(min=10, max=128, message="A senha deve ter entre 10 e 128 caracteres."),
        ],
    )
    administrador = SelectField(
        "Administrador",
        choices=[("sim", "Sim"), ("nao", "Não")],
        default="nao",
        validate_choice=False,
        validators=[AnyOf(["sim", "nao"], message="Escolha Sim ou Não.")],
    )
    # As opções são os planos cadastrados, preenchidas em preparar_usuario_form.
    plano_id = SelectField(
        "Plano",
        coerce=lambda valor: int(valor) if str(valor).isdigit() else None,
        validators=[DataRequired("Escolha um plano.")],
    )


def campo_de_texto(rotulo, mensagem, *validadores):
    return StringField(
        rotulo,
        filters=[lambda valor: valor.strip() if valor else valor],
        validators=[
            DataRequired(mensagem),
            Length(max=200, message="Use no máximo 200 caracteres."),
            *validadores,
        ],
    )


def campo_de_limite(chave):
    rotulo, opcoes = LIMITES_DO_PLANO[chave]
    return SelectField(
        rotulo,
        choices=opcoes,
        default=opcoes[0][0],
        # Ilimitadas vem como texto vazio e é gravada como None.
        coerce=lambda valor: int(valor) if valor not in (None, "", "None") else None,
        validate_choice=False,
        validators=[
            AnyOf(
                [int(valor) if valor else None for valor, _ in opcoes],
                message="Escolha uma das quantidades da lista.",
            )
        ],
    )


class CampoInteiro(IntegerField):
    def process_formdata(self, valores):
        try:
            super().process_formdata(valores)
        except ValueError:
            raise ValueError("Informe um número inteiro.")


class PlanoForm(FlaskForm):
    nome = StringField(
        "Nome",
        filters=[lambda valor: valor.strip() if valor else valor],
        validators=[
            DataRequired("Informe o nome do plano."),
            Length(
                max=LIMITE_NOME_PLANO,
                message="O nome deve ter no máximo {} caracteres.".format(LIMITE_NOME_PLANO),
            ),
        ],
    )
    armazenamento_mb = CampoInteiro(
        "Quantidade de Armazenamento em MB",
        validators=[
            InputRequired("Informe a quantidade de armazenamento em MB."),
            NumberRange(
                min=1,
                max=LIMITE_ARMAZENAMENTO_MB,
                message="Informe um número inteiro de 1 a {} MB.".format(LIMITE_ARMAZENAMENTO_MB),
            ),
        ],
    )
    categorias = campo_de_limite("categorias")
    projetos = campo_de_limite("projetos")
    atividades = campo_de_limite("atividades")
    listas_de_tarefas = campo_de_limite("listas_de_tarefas")
    videos = campo_de_limite("videos")
    padrao = BooleanField("Plano padrão para novas contas")


class ConfiguracoesForm(FlaskForm):
    servidor = campo_de_texto("Servidor SMTP", "Informe o servidor SMTP.")
    porta = SelectField(
        "Porta utilizada no Servidor SMTP",
        choices=[(str(porta), str(porta)) for porta in PORTAS_SMTP],
        validate_choice=False,
        validators=[AnyOf([str(porta) for porta in PORTAS_SMTP], message="Escolha uma porta válida.")],
    )
    usar_tls = SelectField(
        "Utilizar TLS na Autenticação",
        choices=[("sim", "Sim"), ("nao", "Não")],
        validate_choice=False,
        validators=[AnyOf(["sim", "nao"], message="Escolha Sim ou Não.")],
    )
    usuario = campo_de_texto("Usuário", "Informe o usuário.")
    # Em branco mantém a senha já salva: ela nunca volta para a página.
    senha = PasswordField(
        "Senha",
        validators=[Optional(), Length(max=200, message="Use no máximo 200 caracteres.")],
    )
    email_envio = campo_de_texto(
        "E-mail Usado no Envio", "Informe o e-mail usado no envio.", Email("Informe um e-mail válido.")
    )
    nome_envio = campo_de_texto("Nome Usado no Envio", "Informe o nome usado no envio.")


class CategoriaForm(FlaskForm):
    nome = StringField(
        "Nome",
        validators=[
            DataRequired("Informe o nome da categoria."),
            Length(max=80, message="O nome deve ter no máximo 80 caracteres."),
        ],
    )
    icone = RadioField(
        "Ícone",
        choices=ICONES_CATEGORIA,
        validate_choice=False,
        validators=[
            InputRequired("Escolha um ícone para a categoria."),
            AnyOf(
                [valor for valor, _ in ICONES_CATEGORIA],
                message="Escolha um ícone válido.",
            ),
        ],
    )
    # Opcional: sem o campo (formulários antigos ou testes), a categoria fica com o fundo Padrão.
    fundo = RadioField(
        "Fundo do quadro",
        choices=FUNDOS_DO_QUADRO,
        default=FUNDO_PADRAO,
        validate_choice=False,
        validators=[
            Optional(),
            AnyOf([valor for valor, _ in FUNDOS_DO_QUADRO], message="Escolha um fundo válido."),
        ],
    )


def categoria_escolhida(valor):
    # A opção inicial tem valor vazio para o navegador aplicar o atributo required.
    return int(valor) if valor else 0


class ProjetoForm(FlaskForm):
    nome = StringField(
        "Nome",
        validators=[
            DataRequired("Informe o nome do projeto."),
            Length(max=80, message="O nome deve ter no máximo 80 caracteres."),
        ],
    )
    cor = RadioField("Cor", choices=CORES_PROJETO, default=COR_PADRAO)
    categoria_id = SelectField(
        "Categoria",
        coerce=categoria_escolhida,
        default=0,
        validators=[DataRequired("Escolha uma categoria para o projeto.")],
    )
    concluida = BooleanField("Projeto concluído")


class GrupoForm(FlaskForm):
    nome = StringField(
        "Nome",
        filters=[lambda valor: valor.strip() if valor else valor],
        validators=[
            DataRequired("Informe o nome do grupo."),
            Length(
                max=LIMITE_NOME_GRUPO,
                message="O nome deve ter no máximo {} caracteres.".format(LIMITE_NOME_GRUPO),
            ),
        ],
    )
    descricao = TextAreaField(
        "Descrição", filters=[lambda valor: valor.strip() if valor else ""]
    )
    cor = RadioField(
        "Cor",
        choices=CORES_PROJETO,
        default=COR_PADRAO,
        validate_choice=False,
        validators=[AnyOf([valor for valor, _ in CORES_PROJETO], message="Escolha uma cor válida.")],
    )
    icone = RadioField(
        "Ícone",
        choices=[(chave, rotulo) for chave, rotulo, _ in ICONES_GRUPO],
        validate_choice=False,
        validators=[
            AnyOf([chave for chave, _, _ in ICONES_GRUPO], message="Escolha um ícone válido.")
        ],
    )
    ingresso = SelectField(
        "Forma de Ingresso",
        choices=FORMAS_DE_INGRESSO,
        default=FORMA_DE_INGRESSO_PADRAO,
        validate_choice=False,
        validators=[
            AnyOf(
                [valor for valor, _ in FORMAS_DE_INGRESSO],
                message="Escolha uma forma de ingresso válida.",
            )
        ],
    )


class CampoDataHora(DateTimeLocalField):
    def process_formdata(self, valores):
        try:
            super().process_formdata(valores)
        except ValueError:
            raise ValueError("Informe uma data e uma hora válidas.")


def filtrar_atributo_da_descricao(tag, atributo, valor):
    if tag == "img" and atributo == "src":
        return valor if IMAGEM_DA_DESCRICAO.fullmatch(valor) else None
    if tag == "font" and atributo == "color":
        return valor if COR_DA_FONTE.fullmatch(valor) else None
    if tag == "font" and atributo == "size":
        return valor if valor in set("1234567") else None
    return valor


def limpar_descricao(valor):
    # O texto vai para a página como HTML: só passa o que o editor da descrição produz.
    html = nh3.clean(
        valor or "",
        tags=TAGS_DA_DESCRICAO,
        attributes=ATRIBUTOS_DA_DESCRICAO,
        attribute_filter=filtrar_atributo_da_descricao,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
        set_tag_attribute_values={"a": {"target": "_blank"}},
    )
    html = re.sub(r"<img(?![^>]*\ssrc=)[^>]*>", "", html)
    texto = re.sub(r"<[^>]*>", "", html).replace("&nbsp;", "").strip()
    return html if texto or "<img" in html else ""


def ler_itens(valor):
    """Converte o JSON enviado pelo diálogo em [{"texto", "concluido"}], sem tarefas vazias."""
    if isinstance(valor, list):
        return valor
    try:
        itens = json.loads(valor or "[]")
    except ValueError:
        raise ValueError("Não foi possível ler as tarefas da lista.")
    if not isinstance(itens, list) or not all(isinstance(item, dict) for item in itens):
        raise ValueError("Não foi possível ler as tarefas da lista.")
    lidos = []
    for item in itens:
        texto = item.get("texto")
        texto = texto.strip() if isinstance(texto, str) else ""
        if texto:
            lidos.append({"texto": texto, "concluido": item.get("concluido") is True})
    return lidos


def itens_validos(formulario, campo):
    if len(campo.data) > LIMITE_ITENS:
        raise ValidationError("Cada lista pode ter até {} tarefas.".format(LIMITE_ITENS))
    if any(len(item["texto"]) > 255 for item in campo.data):
        raise ValidationError("Cada tarefa deve ter no máximo 255 caracteres.")


def ler_secoes(valor):
    """As seções do cartão generalista, do JSON enviado pelo diálogo, na ordem de SECOES_DO_GENERALISTA."""
    if isinstance(valor, list):
        return valor
    try:
        secoes = json.loads(valor or "[]")
    except ValueError:
        raise ValueError("Não foi possível ler as seções do cartão.")
    if not isinstance(secoes, list):
        raise ValueError("Não foi possível ler as seções do cartão.")
    return [secao for secao in SECOES_DO_GENERALISTA if secao in secoes]


class CampoDeSecoes(HiddenField):
    def process_formdata(self, valores):
        self.data = ler_secoes(valores[0] if valores else "")

    def _value(self):
        return json.dumps(self.data or [])


class CampoDeItens(HiddenField):
    def process_formdata(self, valores):
        self.data = ler_itens(valores[0] if valores else "")

    def _value(self):
        return json.dumps(self.data or [], ensure_ascii=False)


def chave_da_marcacao(texto):
    # "Café" e "cafe" são a mesma marcação.
    decomposto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(letra for letra in decomposto if not unicodedata.combining(letra))


def ler_marcacoes(valor):
    """Converte o JSON do diálogo em uma lista de textos, sem vazias nem repetidas."""
    if isinstance(valor, list):
        return valor
    try:
        marcacoes = json.loads(valor or "[]")
    except ValueError:
        raise ValueError("Não foi possível ler as marcações.")
    if not isinstance(marcacoes, list) or not all(isinstance(texto, str) for texto in marcacoes):
        raise ValueError("Não foi possível ler as marcações.")
    lidas, vistas = [], set()
    for texto in marcacoes:
        texto = " ".join(texto.split())
        if texto and chave_da_marcacao(texto) not in vistas:
            vistas.add(chave_da_marcacao(texto))
            lidas.append(texto)
    return lidas


def marcacoes_validas(formulario, campo):
    if len(campo.data) > LIMITE_MARCACOES:
        raise ValidationError("Cada cartão pode ter até {} marcações.".format(LIMITE_MARCACOES))
    if any(len(texto) > TAMANHO_DA_MARCACAO for texto in campo.data):
        raise ValidationError("Cada marcação deve ter no máximo {} caracteres.".format(TAMANHO_DA_MARCACAO))


class CampoDeMarcacoes(HiddenField):
    def process_formdata(self, valores):
        self.data = ler_marcacoes(valores[0] if valores else "")

    def _value(self):
        return json.dumps(self.data or [], ensure_ascii=False)


class TarefaForm(FlaskForm):
    nome = StringField(
        "Nome",
        validators=[
            DataRequired("Informe o nome da demanda."),
            Length(max=120, message="O nome deve ter no máximo 120 caracteres."),
        ],
    )
    prioridade = SelectField("Prioridade", choices=PRIORIDADES, default="baixa")
    previsao_execucao = CampoDataHora(
        "Previsão de Execução",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
    )
    descricao = TextAreaField("Descrição", filters=[limpar_descricao])
    local = StringField(
        "Local da demanda",
        filters=[lambda valor: valor.strip() if valor else valor],
        validators=[
            Length(max=120, message="O local deve ter no máximo 120 caracteres."),
        ],
    )
    projeto_id = SelectField("Projeto", coerce=int, validate_choice=True)
    tipo = HiddenField(
        default="atividade",
        validators=[
            Optional(),
            AnyOf(TIPOS_DE_ATIVIDADE, message="Tipo de demanda inválido."),
        ],
    )
    itens = CampoDeItens(default=list, validators=[itens_validos])
    marcacoes = CampoDeMarcacoes(default=list, validators=[marcacoes_validas])
    # Só no cartão generalista: as seções acrescentadas e o vídeo do YouTube ou do Vimeo, se houver.
    secoes = CampoDeSecoes(default=list)
    video_endereco = StringField(
        "Endereço do vídeo no YouTube ou no Vimeo",
        filters=[lambda valor: valor.strip() if valor else ""],
        validators=[Length(max=400, message="O endereço do vídeo deve ter no máximo 400 caracteres.")],
    )
    # "1" depois do Receber Informações: o servidor busca de novo, mesmo que o vídeo seja o mesmo.
    video_atualizar = HiddenField()


def nome_de_arquivo(valor, extensao=""):
    nome = re.split(r"[\\/]", valor or "")[-1]
    nome = "".join(letra for letra in nome if letra.isprintable()).strip()
    raiz, sufixo = os.path.splitext(nome)
    sufixo = sufixo or extensao
    return raiz[: 255 - len(sufixo)] + sufixo


class VideoForm(FlaskForm):
    # Os demais campos vêm do YouTube ou do Vimeo e não são alterados pelo usuário.
    informacoes_adicionais = TextAreaField(
        "Informações Adicionais", filters=[lambda valor: valor.strip() if valor else ""]
    )
    marcacoes = CampoDeMarcacoes(default=list, validators=[marcacoes_validas])


class AnexoForm(FlaskForm):
    nome = StringField(
        "Nome do arquivo",
        filters=[nome_de_arquivo],
        validators=[DataRequired("Informe o nome do arquivo.")],
    )

