# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from banco import atualizar_ao_iniciar, ler_configuracao

BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
USERFILES_DIR = BASE_DIR / "userfiles"
ARQUIVO_SEGREDOS = DATABASE_DIR / "segredos.json"
ARQUIVO_DO_BANCO = DATABASE_DIR / "projetos_demandas.db"

FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")

LIMITE_ANEXOS = 3
TAMANHO_MAXIMO_ANEXO = 10 * 1024 * 1024


def seguranca_smtp(porta, tls):
    """A porta 465 cifra a conexão desde o início (SSL). O TLS do Flask-Mail é o STARTTLS
    das portas 25, 587 e 2525: ligado na 465, a conexão não se estabelece."""
    return {"MAIL_USE_SSL": porta == 465, "MAIL_USE_TLS": bool(tls) and porta != 465}


def carregar_segredos():
    """Lê as chaves do ambiente ou de um arquivo local gerado na primeira execução."""
    if os.environ.get("SECRET_KEY") and os.environ.get("SECURITY_PASSWORD_SALT"):
        return {
            "SECRET_KEY": os.environ["SECRET_KEY"],
            "SECURITY_PASSWORD_SALT": os.environ["SECURITY_PASSWORD_SALT"],
        }

    if ARQUIVO_SEGREDOS.exists():
        return json.loads(ARQUIVO_SEGREDOS.read_text(encoding="utf-8"))

    segredos = {
        "SECRET_KEY": secrets.token_hex(32),
        "SECURITY_PASSWORD_SALT": secrets.token_hex(16),
    }
    DATABASE_DIR.mkdir(exist_ok=True)
    # Criado já com leitura e gravação só para o usuário do serviço (no Linux).
    descritor = os.open(ARQUIVO_SEGREDOS, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(segredos))
    return segredos


class Config:
    SECRET_KEY = None
    SECURITY_PASSWORD_SALT = None

    # O banco vem das variáveis BANCO_* do ambiente (banco.py); sem elas, o SQLite de ARQUIVO_DO_BANCO.
    BANCO_ARQUIVO_PADRAO = ARQUIVO_DO_BANCO
    BANCO = ler_configuracao(arquivo_padrao=ARQUIVO_DO_BANCO)
    SQLALCHEMY_DATABASE_URI = BANCO.url
    SQLALCHEMY_ENGINE_OPTIONS = BANCO.opcoes_do_motor
    # No SQLite as tabelas são criadas e atualizadas ao iniciar; nos servidores, por flask banco atualizar.
    BANCO_ATUALIZAR_AO_INICIAR = atualizar_ao_iniciar(tipo=BANCO.tipo)

    BABEL_DEFAULT_LOCALE = "pt_BR"
    BABEL_DEFAULT_TIMEZONE = "America/Sao_Paulo"

    SESSION_COOKIE_SAMESITE = "Lax"
    # O "Lembrar de mim" do login vale por 60 dias.
    REMEMBER_COOKIE_DURATION = timedelta(days=60)
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True

    # Sem isto, uma alteração nos templates só aparece depois de reiniciar o servidor.
    TEMPLATES_AUTO_RELOAD = True

    # Criada na primeira execução. A senha padrão é pública: em produção, defina outra no ambiente.
    CONTA_INICIAL_EMAIL = "administrador@demandas.aplicativoia.online"
    CONTA_INICIAL_NOME = "Administrador do Sistema"
    CONTA_INICIAL_SENHA = os.environ.get("CONTA_INICIAL_SENHA", "Admin@2026")

    # CAPTCHA de imagem no login e em Esqueci minha senha (captcha_imagem.py).
    CAPTCHA_ATIVO = True
    # Limite de requisições por IP ou por usuário (LIMITES em seguranca.py).
    LIMITES_ATIVOS = True
    # Atrás do Nginx, PROXY_CONFIAVEL=1 faz o sistema ler o IP do visitante e o HTTPS dos
    # cabeçalhos X-Forwarded-For e X-Forwarded-Proto. Sem um proxy, esses cabeçalhos seriam falsificáveis.
    PROXY_CONFIAVEL = os.environ.get("PROXY_CONFIAVEL") == "1"
    # Os nomes (domínio ou IP, sem a porta) pelos quais o sistema é acessado, separados por vírgulas.
    # Os links dos e-mails, como o de criar uma nova senha, usam o endereço do pedido: sem esta
    # lista, um pedido com outro Host faria o link apontar para outro site. Vazia, aceita qualquer um.
    HOSTS_PERMITIDOS = frozenset(
        nome.strip().lower() for nome in os.environ.get("HOSTS_PERMITIDOS", "").split(",") if nome.strip()
    )
    # Avisos de vencimento por e-mail: a primeira rodada sai um minuto depois de iniciar e as
    # seguintes, a cada 10 minutos. Só envia com o e-mail configurado em Administração.
    AVISOS_ATIVOS = True
    AVISOS_PRIMEIRA_EXECUCAO = 60
    AVISOS_INTERVALO = 600

    ANEXOS_DIR = USERFILES_DIR
    # Os arquivos de uma tarefa mais uma folga para os demais campos do formulário.
    MAX_CONTENT_LENGTH = LIMITE_ANEXOS * TAMANHO_MAXIMO_ANEXO + 1024 * 1024

    SECURITY_REGISTERABLE = True
    SECURITY_CHANGEABLE = True
    # O login, o cadastro e o Esqueci minha senha não revelam se um e-mail tem conta.
    SECURITY_RETURN_GENERIC_RESPONSES = True
    # Só a sessão do navegador: o sistema não usa os tokens de API do Flask-Security.
    SECURITY_API_ENABLED_METHODS = ["session"]
    # Sair só pelo botão do menu (POST com o token CSRF): um link de outro site não desconecta ninguém.
    SECURITY_LOGOUT_METHODS = ["POST"]
    # O Cache-Control das telas de conta vem de seguranca.aplicar_cabecalhos: o do Flask-Security
    # sai como "private=True, no-store=True", que os navegadores podem não reconhecer.
    SECURITY_CACHE_CONTROL = {}
    # Senhas com pelo menos 10 caracteres e que não sejam fáceis de adivinhar (zxcvbn, nota 3 de 4).
    SECURITY_PASSWORD_LENGTH_MIN = 10
    SECURITY_PASSWORD_COMPLEXITY_CHECKER = "zxcvbn"
    # Confirmação do e-mail no cadastro: ligada por aplicar_configuracao_de_email.
    SECURITY_CONFIRMABLE = False
    # Lido também pelo e-mail de confirmação, que escreve o prazo em português.
    SECURITY_CONFIRM_EMAIL_WITHIN = timedelta(days=2)
    # O Esqueci minha senha existe sempre, com o link na tela de login. Sem o envio de e-mails
    # configurado, o pedido recebe a mesma mensagem e nada é enviado (seguranca.EnvioDeEmails).
    SECURITY_RECOVERABLE = True
    # Sem a tela de Configurações salva, os recursos que dependem de envio ficam desligados.
    # aplicar_configuracao_de_email, em routes.py, os liga.
    SECURITY_SEND_REGISTER_EMAIL = False
    SECURITY_SEND_PASSWORD_CHANGE_EMAIL = False
    SECURITY_SEND_PASSWORD_RESET_NOTICE_EMAIL = False
    # Lido também pelo e-mail de nova senha, que escreve o prazo em português.
    SECURITY_RESET_PASSWORD_WITHIN = timedelta(days=1)

    # Os e-mails são sempre em português: os assuntos ficam aqui e os textos em
    # templates/security/email/, que substituem os modelos em inglês da extensão.
    SECURITY_EMAIL_SUBJECT_REGISTER = "Bem-vindo ao Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_CONFIRM = "Confirme o seu e-mail - Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_PASSWORDLESS = "Instruções para entrar - Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_PASSWORD_NOTICE = "Sua senha foi redefinida - Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_PASSWORD_CHANGE_NOTICE = "Sua senha foi alterada - Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_PASSWORD_RESET = "Crie uma nova senha - Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_USERNAME_CHANGE_NOTICE = "Seu nome de usuário foi alterado - Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_USERNAME_RECOVERY = "Seu nome de usuário - Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_TWO_FACTOR = "Código de acesso - Projetos & Demandas"
    SECURITY_EMAIL_SUBJECT_TWO_FACTOR_RESCUE = "Recuperação do acesso em duas etapas - Projetos & Demandas"
    SECURITY_CHANGE_EMAIL_SUBJECT = "Confirme o seu novo e-mail - Projetos & Demandas"
    SECURITY_US_EMAIL_SUBJECT = "Código de verificação - Projetos & Demandas"

    # Mensagens sem tradução para pt_BR no Flask-Security-Too.
    SECURITY_MSG_ANONYMOUS_USER_REQUIRED = (
        "Esta página só pode ser acessada sem estar conectado.",
        "error",
    )
    # A categoria "silenciosa" é descartada em base.html: alterar a senha não gera aviso.
    SECURITY_MSG_PASSWORD_CHANGE = ("Senha alterada.", "silenciosa")
    SECURITY_MSG_API_ERROR = ("Dados inválidos para esta solicitação.", "error")
    SECURITY_MSG_CONFIRMATION_EXPIRED = (
        "O prazo para confirmar seu e-mail expirou.",
        "error",
    )
    SECURITY_MSG_CONFIRM_REGISTRATION = (
        "Enviamos um link de confirmação para %(email)s.",
        "success",
    )
    SECURITY_MSG_IDENTITY_ALREADY_ASSOCIATED = (
        "Este valor já está associado a uma conta.",
        "error",
    )
    SECURITY_MSG_INVALID_INPUT = ("O valor informado não é válido.", "error")
    SECURITY_MSG_INVALID_INPUT_LENGTH = (
        "O valor deve ter menos de %(length)s caracteres.",
        "error",
    )
    SECURITY_MSG_PASSWORD_INVALID_LENGTH = (
        "A senha deve ter pelo menos %(length)s caracteres.",
        "error",
    )
    # A mesma resposta para qualquer e-mail, cadastrado ou não. A categoria "recuperacao" não abre a
    # caixa de notificação (que fecha sozinha): o texto fica na própria tela do Esqueci minha senha.
    SECURITY_MSG_PASSWORD_RESET_REQUEST = (
        "Recebemos seu e-mail para recuperar a senha. Caso ele esteja cadastrado, você receberá as "
        "informações para acessar o Projetos & Demandas novamente nos próximos minutos. Verifique "
        "sua pasta de Spam na sua caixa de e-mail.",
        "recuperacao",
    )
    SECURITY_MSG_PASSWORD_RESET_EXPIRED = (
        "O prazo para redefinir sua senha expirou.",
        "error",
    )
    SECURITY_MSG_GENERIC_AUTHN_FAILED = ("E-mail ou senha inválidos.", "error")
    SECURITY_MSG_GENERIC_RECOVERY = (
        "Se o e-mail estiver cadastrado, você receberá as instruções "
        "para redefinir sua senha.",
        "info",
    )
    SECURITY_MSG_IDENTITY_NOT_REGISTERED = ("E-mail ou senha inválidos.", "error")
    SECURITY_MSG_INVALID_PASSWORD_CODE = ("A senha informada não é válida.", "error")
    SECURITY_MSG_PASSWORD_BREACHED = (
        "Esta senha aparece em listas de senhas vazadas.",
        "error",
    )
    SECURITY_MSG_PASSWORD_BREACHED_SITE_ERROR = (
        "Não foi possível verificar se a senha foi vazada.",
        "error",
    )
    SECURITY_MSG_PASSWORD_RESET_NO_LOGIN = (
        "Sua senha foi redefinida. Entre com a nova senha.",
        "success",
    )
    SECURITY_MSG_PASSWORD_TOO_SIMPLE = (
        "A senha é fácil de adivinhar. Use uma frase ou misture palavras, números e símbolos.",
        "error",
    )
    SECURITY_MSG_REAUTHENTICATION_REQUIRED = (
        "Confirme sua identidade para acessar esta página.",
        "error",
    )
    SECURITY_MSG_REAUTHENTICATION_SUCCESSFUL = ("Identidade confirmada.", "info")
    SECURITY_MSG_UNAUTHENTICATED = ("Entre para acessar esta página.", "error")
    SECURITY_MSG_UNAUTHORIZED = (
        "Você não tem permissão para acessar esta página.",
        "error",
    )

    # Substituído pelo que for salvo na tela de Configurações.
    MAIL_DEFAULT_SENDER = ("Projetos & Demandas", "nao-responda@projetosedemandas.local")
    SECURITY_EMAIL_SENDER = MAIL_DEFAULT_SENDER
