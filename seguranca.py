# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Proteções que valem para todas as páginas.

- Cabeçalhos de segurança (CSP, proteção contra a página aberta dentro de outro site e HSTS).
- Limite de requisições por endereço IP ou por usuário, em memória: o Gunicorn roda com um
  processo só (INSTALL.md), e todas as threads dele compartilham os contadores. O login também
  tem um limite por conta, para as senhas erradas de uma pessoa vindas de muitos IPs.
- Páginas com dados do usuário não ficam guardadas no navegador nem em proxies (no-store).
- Só os endereços de HOSTS_PERMITIDOS são atendidos, para os links dos e-mails não serem desviados.
- Troca obrigatória da senha da conta inicial no primeiro login.
- Último acesso de cada conta, para a exclusão por inatividade.
- Criptografia da senha do SMTP gravada no banco, com uma chave derivada da SECRET_KEY.
- Permissões dos arquivos do banco e das chaves.
- Validação da força da senha com mensagens em português.
- Envio das instruções do Esqueci minha senha em segundo plano, sem revelar se o e-mail tem conta.
"""
import base64
import logging
import os
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from flask import current_app, flash, g, jsonify, redirect, render_template, request
from flask_mail import Message
from flask_security import MailUtil, PasswordUtil, current_user, url_for_security
from flask_security.utils import get_message

from extensions import db, mail
from models import agora_em_sao_paulo

registro = logging.getLogger(__name__)

# ---------- Cabeçalhos

# As páginas não têm script nem folha de estilos embutidos, e todos os arquivos vêm do próprio
# sistema. O 'unsafe-inline' do style-src é só para os atributos style= dos modelos (as cores dos
# projetos e dos grupos). De fora vêm apenas as miniaturas e o player dos vídeos do YouTube e do Vimeo.
POLITICA_DE_CONTEUDO = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https://i.ytimg.com https://i.vimeocdn.com",
    "frame-src https://www.youtube-nocookie.com https://player.vimeo.com",
    "connect-src 'self'",
    "font-src 'self'",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
CABECALHOS = {
    "Content-Security-Policy": POLITICA_DE_CONTEUDO,
    # Para navegadores sem o frame-ancestors: a página não abre dentro de outro site.
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    # Os endereços do quadro têm ?tarefa= e ?busca=: para outros sites vai só o domínio, sem o
    # caminho. O player do YouTube precisa desse domínio; sem ele, o vídeo não abre (erro 153).
    # O do Vimeo também o usa, para os vídeos limitados a alguns domínios.
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    # Uma janela aberta por outro site não fica com acesso a esta (window.opener).
    "Cross-Origin-Opener-Policy": "same-origin",
}
# Os arquivos de static/ e os do aplicativo instalável podem ficar no cache e ser usados por
# outros sites (os e-mails, por exemplo). Todo o resto tem dados de alguém: não fica guardado no
# navegador nem em proxies, e só as páginas do próprio sistema podem carregá-lo.
PUBLICOS = {"static", "principal.service_worker", "principal.manifesto", "principal.favicon", "principal.offline"}
SEM_CACHE = "no-store, private"
# Só em HTTPS. Os navegadores ignoram o HSTS quando o site é acessado pelo IP.
HSTS = "max-age=31536000; includeSubDomains"


def nome_do_host(host):
    """O domínio ou IP do cabeçalho Host, sem a porta: "exemplo.com:8002" e "[::1]:8002"."""
    host = (host or "").strip().lower()
    if host.startswith("["):
        return host[1:host.find("]")] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def conferir_host():
    permitidos = current_app.config.get("HOSTS_PERMITIDOS")
    if permitidos and nome_do_host(request.host) not in permitidos:
        return current_app.response_class("Endereço não atendido por este servidor.", status=400, mimetype="text/plain")
    return None


def aplicar_cabecalhos(resposta):
    for nome, valor in CABECALHOS.items():
        resposta.headers.setdefault(nome, valor)
    if request.is_secure:
        resposta.headers.setdefault("Strict-Transport-Security", HSTS)
    if request.endpoint not in PUBLICOS:
        # Também nos anexos e nas imagens: o send_from_directory permite o cache por padrão.
        if "no-store" not in resposta.headers.get("Cache-Control", ""):
            resposta.headers["Cache-Control"] = SEM_CACHE
        resposta.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    return resposta


# ---------- Limite de requisições

MINUTO = 60
HORA = 60 * MINUTO
# Endpoint: (métodos, quantidade, janela em segundos, contar por "ip" ou "usuario").
LIMITES = {
    "security.login": ({"POST"}, 20, 10 * MINUTO, "ip"),
    "security.register": ({"POST"}, 5, HORA, "ip"),
    "security.forgot_password": ({"POST"}, 5, HORA, "ip"),
    "security.reset_password": ({"POST"}, 10, HORA, "ip"),
    "security.send_confirmation": ({"POST"}, 5, HORA, "ip"),
    "security.change_password": ({"POST"}, 10, 10 * MINUTO, "usuario"),
    # Sem login, cada imagem grava um desafio no banco.
    "principal.imagem_captcha": ({"GET"}, 30, MINUTO, "ip"),
    # Os que fazem o servidor acessar o YouTube.
    "principal.criar_video": ({"POST"}, 30, MINUTO, "usuario"),
    "principal.previa_do_video": ({"POST"}, 30, MINUTO, "usuario"),
    "principal.atualizar_video": ({"POST"}, 30, MINUTO, "usuario"),
    # Os que gravam arquivos.
    "principal.enviar_imagem": ({"POST"}, 60, HORA, "usuario"),
    "principal.enviar_foto": ({"POST"}, 30, HORA, "usuario"),
    "principal.criar_tarefa": ({"POST"}, 60, MINUTO, "usuario"),
    "principal.editar_tarefa": ({"POST"}, 60, MINUTO, "usuario"),
    "principal.comentar_tarefa": ({"POST"}, 30, MINUTO, "usuario"),
    # Adicionar Membros diz se o e-mail informado tem conta.
    "principal.adicionar_membros": ({"GET"}, 30, HORA, "usuario"),
    "principal.adicionar_membro": ({"POST"}, 60, HORA, "usuario"),
    # Sem login, cada mensagem do Atendimento sai como um e-mail.
    "publico.atendimento": ({"POST"}, 5, HORA, "ip"),
}
# Senhas erradas por conta, vindas de qualquer IP. Contam só as tentativas que passaram pelo
# CAPTCHA (a senha só é conferida com o código certo): sem resolvê-lo, ninguém bloqueia a conta
# de outra pessoa. Acertar a senha zera a contagem.
TENTATIVAS_POR_CONTA = (10, 15 * MINUTO)
# E-mails do Esqueci minha senha por conta, pedidos de qualquer IP: ninguém enche a caixa de
# entrada de outra pessoa. Acima disso, o pedido recebe a mesma mensagem, mas nada é enviado.
EMAILS_DE_NOVA_SENHA_POR_CONTA = (3, HORA)
MENSAGEM_DO_LIMITE = "Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente novamente."


class Limitador:
    """Janela deslizante: guarda o momento de cada requisição contada, por chave."""

    def __init__(self, relogio=time.monotonic):
        self.relogio = relogio
        self.registros = defaultdict(deque)
        self.trava = threading.Lock()
        self.ultima_limpeza = relogio()

    def _espera(self, chave, quantidade, janela, agora):
        """Os segundos até haver vaga, ou 0 se já houver. Chamado com a trava."""
        momentos = self.registros[chave]
        while momentos and momentos[0] <= agora - janela:
            momentos.popleft()
        if len(momentos) >= quantidade:
            return max(1, int(momentos[0] + janela - agora) + 1)
        return 0

    def permitir(self, chave, quantidade, janela):
        """True e conta a requisição se ainda houver vaga; senão, False e os segundos para a próxima."""
        agora = self.relogio()
        with self.trava:
            espera = self._espera(chave, quantidade, janela, agora)
            if espera:
                return False, espera
            self.registros[chave].append(agora)
            self._limpar(agora)
            return True, 0

    def espera(self, chave, quantidade, janela):
        """Como permitir, mas sem contar: os segundos até haver vaga, ou 0."""
        with self.trava:
            return self._espera(chave, quantidade, janela, self.relogio())

    def registrar(self, chave):
        agora = self.relogio()
        with self.trava:
            self.registros[chave].append(agora)
            self._limpar(agora)

    def esquecer(self, chave):
        with self.trava:
            self.registros.pop(chave, None)

    def _limpar(self, agora):
        # De tempos em tempos, as chaves sem requisições recentes saem da memória.
        if agora - self.ultima_limpeza < 10 * MINUTO:
            return
        self.ultima_limpeza = agora
        maior_janela = max([janela for _, _, janela, _ in LIMITES.values()] + [TENTATIVAS_POR_CONTA[1]])
        for chave in [chave for chave, momentos in self.registros.items()
                      if not momentos or momentos[-1] <= agora - maior_janela]:
            del self.registros[chave]

    def zerar(self):
        with self.trava:
            self.registros.clear()


limitador = Limitador()


def resposta_de_limite(espera):
    if request.path.startswith("/api/") or request.is_json:
        resposta = jsonify(erro=MENSAGEM_DO_LIMITE)
    else:
        resposta = current_app.make_response(
            render_template("erro.html", codigo=429, mensagem=MENSAGEM_DO_LIMITE)
        )
    resposta.status_code = 429
    resposta.headers["Retry-After"] = str(espera)
    return resposta


def chave_da_conta():
    """A conta do login em andamento, pelo e-mail digitado (formulário ou JSON)."""
    dados = request.get_json(silent=True) if request.is_json else request.form
    email = dados.get("email") if isinstance(dados, dict) or hasattr(dados, "get") else None
    if not isinstance(email, str) or not email.strip():
        return None
    return "conta:{}".format(email.strip().lower()[:255])


def login_em_andamento():
    return request.endpoint == "security.login" and request.method == "POST"


def senha_conferida():
    """Chamado pelo formulário do login quando o CAPTCHA confere e a senha vai ser testada."""
    g.senha_conferida = True


def contar_senha_errada(resposta):
    """Depois do login: conta a senha errada da conta, ou zera a contagem se a pessoa entrou."""
    if not current_app.config.get("LIMITES_ATIVOS", True) or not login_em_andamento():
        return resposta
    chave = chave_da_conta()
    if chave is None:
        return resposta
    if current_user.is_authenticated:
        limitador.esquecer(chave)
    elif g.get("senha_conferida"):
        limitador.registrar(chave)
    return resposta


def conferir_limite():
    if not current_app.config.get("LIMITES_ATIVOS", True):
        return None
    if login_em_andamento() and chave_da_conta():
        espera = limitador.espera(chave_da_conta(), *TENTATIVAS_POR_CONTA)
        if espera:
            return resposta_de_limite(espera)
    regra = LIMITES.get(request.endpoint)
    if not regra or request.method not in regra[0]:
        return None
    _, quantidade, janela, por = regra
    if por == "usuario" and current_user.is_authenticated:
        quem = "usuario:{}".format(current_user.id)
    else:
        # Atrás do Nginx, o remote_addr só é o do visitante com o ProxyFix (PROXY_CONFIAVEL).
        quem = "ip:{}".format(request.remote_addr)
    permitido, espera = limitador.permitir("{}|{}".format(request.endpoint, quem), quantidade, janela)
    return None if permitido else resposta_de_limite(espera)


# ---------- Troca obrigatória da senha

# O que continua acessível enquanto a senha não é trocada.
LIVRES_NA_TROCA_DE_SENHA = {
    "security.change_password",
    "security.logout",
    "static",
    "principal.service_worker",
    "principal.manifesto",
    "principal.favicon",
    "principal.offline",
    "principal.imagem_captcha",
}
MENSAGEM_DA_TROCA = "Antes de continuar, crie uma nova senha para esta conta."


def exigir_troca_de_senha():
    if request.endpoint in LIVRES_NA_TROCA_DE_SENHA or request.endpoint is None:
        return None
    if not current_user.is_authenticated or not current_user.trocar_senha:
        return None
    if request.path.startswith("/api/") or request.is_json:
        return jsonify(erro=MENSAGEM_DA_TROCA), 403
    flash(MENSAGEM_DA_TROCA, "aviso")
    return redirect(url_for_security("change_password"))


# ---------- Último acesso (inatividade.py)

# O último acesso só é gravado de novo depois deste intervalo: não é preciso um UPDATE por clique.
INTERVALO_DO_ACESSO = timedelta(minutes=5)
# Pedidos que o navegador faz sozinho e não são uso do sistema pela pessoa. A consulta da versão
# do quadro compartilhado roda a cada 20 s: com ela, uma aba esquecida manteria a conta para sempre.
FORA_DO_ACESSO = {
    "static",
    "principal.versao_do_quadro",
    "principal.service_worker",
    "principal.manifesto",
    "principal.favicon",
    "principal.offline",
}


def marcar_acesso(usuario, momento, sempre=False):
    """Grava o último acesso e apaga o aviso de exclusão por inatividade, se já houver um."""
    anterior = usuario.ultimo_acesso
    if not sempre and anterior is not None and momento - anterior < INTERVALO_DO_ACESSO and not usuario.aviso_de_exclusao_em:
        return False
    usuario.ultimo_acesso = momento
    usuario.aviso_de_exclusao_em = None
    db.session.commit()
    return True


def registrar_acesso():
    """before_request: o uso do sistema por quem está logado conta como acesso."""
    if request.endpoint is None or request.endpoint in FORA_DO_ACESSO:
        return None
    if not current_app.config.get("BANCO_PRONTO", True) or not current_user.is_authenticated:
        return None
    marcar_acesso(current_user, agora_em_sao_paulo())
    return None


def acesso_no_login(_app, user, **_dados):
    """Sinal user_authenticated do Flask-Security: o login sempre grava o último acesso."""
    marcar_acesso(user, agora_em_sao_paulo(), sempre=True)


# ---------- Senha do SMTP

PREFIXO_CIFRADO = "cifrada:"


def _cofre(segredo):
    # A chave sai da SECRET_KEY, que fica fora do banco: uma cópia do banco não entrega a senha.
    chave = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"projetos-demandas:smtp").derive(
        segredo.encode("utf-8")
    )
    return Fernet(base64.urlsafe_b64encode(chave))


def esta_cifrada(valor):
    return bool(valor) and valor.startswith(PREFIXO_CIFRADO)


def cifrar(texto, segredo):
    return PREFIXO_CIFRADO + _cofre(segredo).encrypt(texto.encode("utf-8")).decode("ascii")


def decifrar(valor, segredo):
    """A senha em texto. Vazia se a SECRET_KEY mudou: o administrador informa a senha de novo."""
    if not esta_cifrada(valor):
        return valor or ""
    try:
        return _cofre(segredo).decrypt(valor[len(PREFIXO_CIFRADO):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""


# ---------- Arquivos do banco e das chaves

SUFIXOS_DO_SQLITE = ("", "-wal", "-shm", "-journal")


def proteger_arquivos(caminhos):
    """Só o usuário do serviço lê e grava. No Windows, o chmod só controla o somente leitura."""
    if os.name != "posix":
        return
    for caminho in caminhos:
        if caminho and os.path.exists(caminho):
            os.chmod(caminho, 0o600)


def arquivos_do_banco(caminho_do_banco):
    if not caminho_do_banco or caminho_do_banco == ":memory:":
        return []
    return [str(caminho_do_banco) + sufixo for sufixo in SUFIXOS_DO_SQLITE]


# ---------- Força da senha

class SenhaUtil(PasswordUtil):
    """Como a validação do Flask-Security, mas com a mensagem de senha fraca sempre em português.

    O zxcvbn explica o motivo em inglês, e o Flask-Security não traduz esse texto.
    """

    def validate(self, password, is_register, **kwargs):
        mensagens, normalizada = super().validate(password, is_register, **kwargs)
        if mensagens and len(normalizada) >= current_app.config["SECURITY_PASSWORD_LENGTH_MIN"]:
            vazada = get_message("PASSWORD_BREACHED")[0]
            mensagens = [mensagem if mensagem == vazada else get_message("PASSWORD_TOO_SIMPLE")[0]
                         for mensagem in mensagens]
            mensagens = list(dict.fromkeys(mensagens))
        return mensagens, normalizada


# ---------- E-mails do Flask-Security

def em_segundo_plano(funcao):
    threading.Thread(target=funcao, daemon=True).start()


class EnvioDeEmails(MailUtil):
    """Como o envio do Flask-Security, mas com as instruções do Esqueci minha senha em segundo plano.

    A tela responde igual para qualquer e-mail (SECURITY_RETURN_GENERIC_RESPONSES). Se o envio
    acontecesse durante a requisição, a demora do SMTP, ou um erro dele, mostraria que o e-mail
    tem conta. Uma falha no envio só vai para o log.
    """

    def send_mail(self, template, subject, recipient, sender, body, html, **kwargs):
        if template != current_app.config["SECURITY_EMAIL_TEMPLATE_PASSWORD_RESET"]:
            return super().send_mail(template, subject, recipient, sender, body, html, **kwargs)
        if current_app.config.get("LIMITES_ATIVOS", True):
            permitido, _ = limitador.permitir("nova-senha:{}".format(str(recipient).lower()),
                                              *EMAILS_DE_NOVA_SENHA_POR_CONTA)
            if not permitido:
                registro.warning("Esqueci minha senha: limite de e-mails da conta atingido; nada foi enviado.")
                return None
        if isinstance(sender, tuple) and len(sender) == 2:
            sender = (str(sender[0]), str(sender[1]))
        mensagem = Message(str(subject), sender=sender, recipients=[recipient], body=body, html=html)
        app = current_app._get_current_object()

        def enviar():
            with app.app_context():
                if not app.config.get("MAIL_SERVER"):
                    registro.warning("Esqueci minha senha sem o envio de e-mails configurado: nada foi enviado.")
                    return
                try:
                    mail.send(mensagem)
                except Exception:  # noqa: BLE001 - quem pediu já recebeu a resposta; fica o registro.
                    registro.exception("Falha ao enviar as instruções para criar uma nova senha")

        em_segundo_plano(enviar)
        return None
