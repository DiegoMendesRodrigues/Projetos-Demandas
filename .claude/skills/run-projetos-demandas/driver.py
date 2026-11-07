# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Sobe uma cópia do app com banco temporário e sem CAPTCHA, e a dirige por HTTP.

Uso (a partir da raiz do projeto):
  .venv/Scripts/python .claude/skills/run-projetos-demandas/driver.py smoke
  .venv/Scripts/python .claude/skills/run-projetos-demandas/driver.py serve

smoke: sobe o servidor na porta 8011, entra como administrador, percorre as
telas principais, alterna o Simplificar de um vídeo e encerra o servidor.
serve: só sobe o servidor semeado e fica rodando (Ctrl+C para parar).

Contas de teste (existem só no banco temporário):
  admin@exemplo.com (administrador) e ana@exemplo.com, senha Teste-Driver-1
"""
import http.cookiejar
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJETO = Path(__file__).resolve().parents[3]
PORTA = 8011
BASE = "http://127.0.0.1:{}".format(PORTA)
SENHA = "Teste-Driver-1"


def servir(pasta):
    sys.path.insert(0, str(PROJETO))
    from flask_security import hash_password

    from app import create_app
    from config import Config
    from extensions import db, security
    from models import Categoria, CompartilhamentoDeCategoria, GrupoDeUsuarios, Projeto, Tarefa, VideoDoYoutube

    class ConfigDoDriver(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format((pasta / "driver.db").as_posix())
        ANEXOS_DIR = pasta / "anexos"
        CONTA_INICIAL_EMAIL = None
        CAPTCHA_ATIVO = False

    app = create_app(ConfigDoDriver)
    with app.app_context():
        admin = security.datastore.create_user(
            email="admin@exemplo.com", nome="Zélia Admin", password=hash_password(SENHA), administrador=True
        )
        ana = security.datastore.create_user(email="ana@exemplo.com", nome="Ana", password=hash_password(SENHA))
        db.session.flush()
        categoria = Categoria(nome="Casa", icone="casa", usuario_id=admin.id)
        # A Casa é compartilhada com o grupo Família (Zélia e Ana), só para visualizar.
        grupo = GrupoDeUsuarios(nome="Família", administrador_id=admin.id, cor="#22b455", icone="casa")
        grupo.membros.extend([admin, ana])
        db.session.add_all([categoria, grupo])
        db.session.flush()
        db.session.add(CompartilhamentoDeCategoria(categoria_id=categoria.id, grupo_id=grupo.id, permissao="visualizar"))
        projeto = Projeto(nome="A fazer", usuario_id=admin.id, categoria_id=categoria.id, posicao=0)
        db.session.add(projeto)
        db.session.flush()
        video = Tarefa(nome="Me at the zoo", tipo="video", projeto_id=projeto.id, posicao=1)
        video.video = VideoDoYoutube(
            endereco="https://www.youtube.com/watch?v=jNQXAC9IVRw", codigo="jNQXAC9IVRw",
            autor="jawed", titulo="Me at the zoo", duracao="0:19",
        )
        db.session.add_all([Tarefa(nome="Comprar pão", projeto_id=projeto.id, posicao=0), video])
        db.session.commit()
    app.run(host="127.0.0.1", port=PORTA, use_reloader=False)


class Navegador:
    def __init__(self):
        self.abridor = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def get(self, caminho):
        with self.abridor.open(BASE + caminho, timeout=10) as resposta:
            return resposta.geturl(), resposta.read().decode("utf-8")

    def post(self, caminho, dados):
        corpo = urllib.parse.urlencode(dados).encode()
        with self.abridor.open(BASE + caminho, corpo, timeout=10) as resposta:
            return resposta.geturl(), resposta.read().decode("utf-8")


def csrf(html):
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)


def esperar_servidor(processo):
    for _ in range(60):
        if processo.poll() is not None:
            raise SystemExit("O servidor terminou ao iniciar (código {}).".format(processo.returncode))
        try:
            urllib.request.urlopen(BASE + "/login", timeout=2)
            return
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.5)
    raise SystemExit("O servidor não respondeu em 30 s.")


def conferir(condicao, mensagem):
    print(("OK   " if condicao else "FALHA ") + mensagem)
    return condicao


def smoke():
    sys.stdout.reconfigure(encoding="utf-8")
    processo = subprocess.Popen([sys.executable, __file__, "serve"], cwd=PROJETO)
    try:
        esperar_servidor(processo)
        nav = Navegador()
        _, html = nav.get("/login")
        conferir("captcha" not in html.lower(), "login sem CAPTCHA no banco temporário")
        url, html = nav.post("/login", {"csrf_token": csrf(html), "email": "admin@exemplo.com", "password": SENHA})
        ok = conferir(url.rstrip("/") == BASE, "login redireciona ao quadro")
        ok &= conferir("Comprar pão" in html and "Me at the zoo" in html, "quadro mostra a demanda e o vídeo")
        id_video = re.search(r'/tarefas/(\d+)/simplificar', html).group(1)
        _, html = nav.post("/tarefas/{}/simplificar".format(id_video), {"csrf_token": csrf(html)})
        ok &= conferir("video-simplificado" in html, "Simplificar deixa o vídeo simplificado")
        _, html = nav.get("/administracao/usuarios")
        nomes = re.findall(r"<tr>\s*<td>([^<]+)</td>", html)
        ok &= conferir(nomes == ["Ana", "Zélia Admin"], "Usuários começa por Nome crescente: {}".format(nomes))
        _, html = nav.get("/administracao/planos")
        ok &= conferir("Iniciante" in html, "Planos de Usuários lista o plano padrão")
        _, html = nav.get("/grupos")
        ok &= conferir("Grupos" in html, "página de Grupos abre")
        raise SystemExit(0 if ok else 1)
    finally:
        processo.terminate()
        processo.wait(10)


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    if comando == "serve":
        # No Windows, parar o processo o mata sem passar pelo finally: limpa as cópias antigas aqui.
        for antiga in Path(tempfile.gettempdir()).glob("projetos-demandas-driver-*"):
            shutil.rmtree(antiga, ignore_errors=True)
        pasta = Path(tempfile.mkdtemp(prefix="projetos-demandas-driver-"))
        try:
            servir(pasta)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
    else:
        smoke()
