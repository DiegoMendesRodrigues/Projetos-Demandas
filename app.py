# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import sys
from pathlib import Path

from flask import Flask, current_app, render_template, request
from flask_security import SQLAlchemyUserDatastore, current_user, hash_password, verify_password
from flask_security.signals import password_changed, password_reset, user_registered
from markupsafe import escape
from sqlalchemy import bindparam, inspect, text
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from config import (
    ARQUIVO_SEGREDOS,
    DATABASE_DIR,
    USERFILES_DIR,
    Config,
    carregar_segredos,
)
from extensions import babel, csrf, db, mail, security
from forms import AlterarSenhaForm, CadastroForm, EsqueciSenhaComCaptchaForm, LoginComCaptchaForm
from icones_grupo import icone_grupo
from models import (
    ANTECEDENCIA_PADRAO,
    DESTINATARIOS_PADRAO,
    AVATAR_PADRAO,
    CORES_PROJETO,
    FUNDO_PADRAO,
    ICONE_PADRAO,
    ConfiguracaoEmail,
    Imagem,
    Projeto,
    Papel,
    PlanoDeUsuario,
    Usuario,
    rotulo_de_tamanho,
    rotulo_de_duracao,
    rotulo_em_megabytes,
)
from avisos import iniciar_avisos
from paginas_publicas import publico
from banco import preparar_motor
from comandos_do_banco import banco, concluir_banco_antigo, preparar_banco
from routes import (
    agora,
    apagar_imagens_pendentes,
    aplicar_configuracao_de_email,
    estatico,
    principal,
    tarefas_atrasadas,
)
from seguranca import (
    SenhaUtil,
    aplicar_cabecalhos,
    arquivos_do_banco,
    cifrar,
    conferir_host,
    conferir_limite,
    contar_senha_errada,
    esta_cifrada,
    exigir_troca_de_senha,
    proteger_arquivos,
)

# Cada cor pastel anterior e a cor vibrante que a substituiu.
CORES_ANTIGAS = {
    "#bcd4ee": "#1a6fe0",
    "#a8dcf0": "#00b0f0",
    "#a6e3d8": "#00c2a8",
    "#bfe0c5": "#22b455",
    "#d6e8a8": "#8ed100",
    "#f7e7a1": "#ffc800",
    "#f6d2ae": "#ff8a00",
    "#f2b5ab": "#ff5a4f",
    "#f5bdd6": "#ff3d9a",
    "#d5c4ee": "#9b51e0",
    "#e5d6bf": "#c8963e",
    "#d2d3d6": "#78839a",
}
# Os tipos de usuário que existiam antes dos planos: viram planos com o mesmo espaço.
TIPOS_ANTIGOS = [
    ("iniciante", "Iniciante", 10),
    ("intermediario", "Intermediário", 50),
    ("avancado", "Avançado", 100),
    ("mestre", "Mestre", 250),
]
NOMES_DE_PROJETO_CONCLUIDO = ["Concluída", "Concluídas", "Concluído", "Concluídos"]
# A senha padrão da conta inicial, publicada no README: a conta que ainda a usa precisa trocá-la.
SENHA_PADRAO_PUBLICADA = "Admin@2026"
MENSAGEM_DE_ERRO_PADRAO = "Não foi possível concluir a solicitação."
MENSAGENS_DE_ERRO = {
    400: "Não foi possível processar a solicitação. Recarregue a página e tente novamente.",
    403: "Você não tem permissão para acessar esta página.",
    404: "Página não encontrada.",
    405: "Esta ação não é permitida nesta página.",
    413: "Os arquivos enviados ultrapassam o tamanho permitido.",
    429: "Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente novamente.",
    500: "Ocorreu um erro interno. Tente novamente em instantes.",
}


def registrar_erros(app):
    def pagina_de_erro(erro):
        mensagem = MENSAGENS_DE_ERRO.get(erro.code, MENSAGEM_DE_ERRO_PADRAO)
        return render_template("erro.html", codigo=erro.code, mensagem=mensagem), erro.code

    app.register_error_handler(HTTPException, pagina_de_erro)


def cor_mais_proxima(cor):
    def componentes(valor):
        return [int(valor[inicio:inicio + 2], 16) for inicio in (1, 3, 5)]

    def distancia(opcao):
        return sum((a - b) ** 2 for a, b in zip(componentes(cor), componentes(opcao[0])))

    return min(CORES_PROJETO, key=distancia)[0]


def adicionar_coluna(tabela, coluna, definicao):
    colunas = {item["name"] for item in inspect(db.engine).get_columns(tabela)}
    if coluna not in colunas:
        with db.engine.begin() as conexao:
            conexao.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}"))


def remover_coluna(tabela, coluna):
    colunas = {item["name"] for item in inspect(db.engine).get_columns(tabela)}
    if coluna in colunas:
        with db.engine.begin() as conexao:
            conexao.execute(text(f"ALTER TABLE {tabela} DROP COLUMN {coluna}"))


def migrar_previsao_execucao():
    colunas = {item["name"] for item in inspect(db.engine).get_columns("tarefa")}
    if "data_execucao" not in colunas:
        return

    adicionar_coluna("tarefa", "previsao_execucao", "DATETIME")
    # A data antiga não tinha hora: 23:59 mantém a tarefa em dia até o fim daquele dia.
    with db.engine.begin() as conexao:
        conexao.execute(
            text(
                "UPDATE tarefa SET previsao_execucao = data_execucao || ' 23:59:00.000000' "
                "WHERE data_execucao IS NOT NULL"
            )
        )
        conexao.execute(text("ALTER TABLE tarefa DROP COLUMN data_execucao"))


def migrar_descricao_formatada():
    colunas = {item["name"] for item in inspect(db.engine).get_columns("tarefa")}
    if "descricao" not in colunas:
        return

    adicionar_coluna("tarefa", "descricao_html", "TEXT NOT NULL DEFAULT ''")
    # O texto antigo era simples: sem o escape, um "<" digitado viraria uma marca de HTML.
    with db.engine.begin() as conexao:
        for tarefa_id, descricao in conexao.execute(
            text("SELECT id, descricao FROM tarefa")
        ).fetchall():
            linhas = (descricao or "").replace("\r\n", "\n").split("\n")
            conexao.execute(
                text("UPDATE tarefa SET descricao_html = :html WHERE id = :id"),
                {"html": "<br>".join(str(escape(linha)) for linha in linhas), "id": tarefa_id},
            )
        conexao.execute(text("ALTER TABLE tarefa DROP COLUMN descricao"))


def migrar_projeto_concluido():
    colunas = {item["name"] for item in inspect(db.engine).get_columns("projeto")}
    if "concluida" in colunas:
        return

    adicionar_coluna("projeto", "concluida", "BOOLEAN NOT NULL DEFAULT 0")
    # Os projetos já criados para isso não precisam ser marcados um a um pelo usuário.
    with db.engine.begin() as conexao:
        conexao.execute(
            text("UPDATE projeto SET concluida = 1 WHERE nome IN :nomes").bindparams(
                bindparam("nomes", expanding=True)
            ),
            {"nomes": NOMES_DE_PROJETO_CONCLUIDO},
        )


def colunas_da_tabela(tabela):
    return {item["name"] for item in inspect(db.engine).get_columns(tabela)}


def migrar_administrador(email):
    colunas = {item["name"] for item in inspect(db.engine).get_columns("usuario")}
    if "administrador" in colunas:
        return

    adicionar_coluna("usuario", "administrador", "BOOLEAN NOT NULL DEFAULT 0")
    # Sem isto, nenhum usuário dos bancos já criados conseguiria abrir a administração.
    with db.engine.begin() as conexao:
        conexao.execute(
            text("UPDATE usuario SET administrador = 1 WHERE email = :email"),
            {"email": email},
        )


def migrar_troca_de_senha(email):
    """A conta inicial que ainda entra com a senha padrão publicada é obrigada a trocá-la."""
    if "trocar_senha" in colunas_da_tabela("usuario"):
        return
    adicionar_coluna("usuario", "trocar_senha", "BOOLEAN NOT NULL DEFAULT 0")
    if not email:
        return
    with db.engine.begin() as conexao:
        linha = conexao.execute(
            text("SELECT id, password FROM usuario WHERE email = :email"), {"email": email}
        ).first()
        if linha and verify_password(SENHA_PADRAO_PUBLICADA, linha.password):
            conexao.execute(text("UPDATE usuario SET trocar_senha = 1 WHERE id = :id"), {"id": linha.id})


def migrar_confirmacao_do_email():
    """As contas criadas antes da confirmação do e-mail contam como confirmadas."""
    if "confirmed_at" in colunas_da_tabela("usuario"):
        return
    adicionar_coluna("usuario", "confirmed_at", "DATETIME")
    with db.engine.begin() as conexao:
        conexao.execute(text("UPDATE usuario SET confirmed_at = :agora"), {"agora": agora()})


def migrar_tamanho_das_imagens():
    """As imagens da descrição passaram a ocupar o espaço do plano: o tamanho sai do arquivo."""
    if "tamanho" in colunas_da_tabela("imagem"):
        return
    adicionar_coluna("imagem", "tamanho", "INTEGER NOT NULL DEFAULT 0")
    adicionar_coluna("imagem", "criado_em", "DATETIME")
    pasta = current_app.config["ANEXOS_DIR"]
    for imagem in Imagem.query:
        caminho = pasta / imagem.arquivo
        imagem.tamanho = caminho.stat().st_size if caminho.exists() else 0
        # As pendentes de antes ainda têm 24 horas para serem usadas.
        imagem.criado_em = agora()
    db.session.commit()


def cifrar_senha_do_smtp(segredo):
    """A senha do SMTP gravada em texto passa a ficar cifrada no banco."""
    configuracao = db.session.get(ConfiguracaoEmail, 1)
    if configuracao and configuracao.senha and not esta_cifrada(configuracao.senha):
        configuracao.senha = cifrar(configuracao.senha, segredo)
        db.session.commit()


def plano_pelo_nome(nome):
    # A comparação é feita no Python: o lower() do SQLite não converte letras acentuadas.
    return next(
        (plano for plano in PlanoDeUsuario.query if plano.nome.casefold() == nome.casefold()), None
    )


def migrar_tipo_para_plano():
    """Cada tipo de usuário vira um plano com o mesmo espaço, e cada usuário recebe o seu."""
    colunas = {item["name"] for item in inspect(db.engine).get_columns("usuario")}
    if "tipo" not in colunas:
        return

    for chave, nome, megabytes in TIPOS_ANTIGOS:
        plano = plano_pelo_nome(nome)
        if not plano:
            plano = PlanoDeUsuario(nome=nome, armazenamento_mb=megabytes)
            db.session.add(plano)
            db.session.flush()
        db.session.execute(
            text("UPDATE usuario SET plano_id = :plano WHERE tipo = :tipo AND plano_id IS NULL"),
            {"plano": plano.id, "tipo": chave},
        )
    if not PlanoDeUsuario.query.filter_by(padrao=True).first():
        plano_pelo_nome(TIPOS_ANTIGOS[0][1]).padrao = True
    db.session.commit()
    remover_coluna("usuario", "tipo")


def garantir_plano_padrao():
    """Há sempre um plano padrão, e nenhum usuário fica sem plano."""
    padrao = PlanoDeUsuario.query.filter_by(padrao=True).first()
    if not padrao:
        _, nome, megabytes = TIPOS_ANTIGOS[0]
        padrao = (
            plano_pelo_nome(nome)
            or PlanoDeUsuario.query.order_by(PlanoDeUsuario.nome).first()
            or PlanoDeUsuario(nome=nome, armazenamento_mb=megabytes)
        )
        padrao.padrao = True
        db.session.add(padrao)
        db.session.flush()
    db.session.execute(
        text("UPDATE usuario SET plano_id = :plano WHERE plano_id IS NULL"), {"plano": padrao.id}
    )
    db.session.commit()


def atualizar_banco(email_da_conta_inicial=None):
    """As migrações de antes do Alembic, só para os bancos SQLite criados antes dele.

    Uma alteração nova nas tabelas vai numa revisão de migracoes/versions (flask banco revisao).
    """
    adicionar_coluna("usuario", "nome", "VARCHAR(120) NOT NULL DEFAULT ''")
    adicionar_coluna(
        "categoria", "icone", f"VARCHAR(30) NOT NULL DEFAULT '{ICONE_PADRAO}'"
    )
    adicionar_coluna("categoria", "fundo", f"VARCHAR(20) NOT NULL DEFAULT '{FUNDO_PADRAO}'")
    adicionar_coluna("tarefa", "local", "VARCHAR(120) NOT NULL DEFAULT ''")
    migrar_previsao_execucao()
    migrar_descricao_formatada()
    migrar_projeto_concluido()
    adicionar_coluna("tarefa", "oculta", "BOOLEAN NOT NULL DEFAULT 0")
    adicionar_coluna("usuario", "mostrar_ocultas", "BOOLEAN NOT NULL DEFAULT 0")
    remover_coluna("usuario", "modo")
    adicionar_coluna(
        "usuario", "avatar", f"VARCHAR(40) NOT NULL DEFAULT '{AVATAR_PADRAO}'"
    )
    migrar_administrador(email_da_conta_inicial)
    adicionar_coluna("tarefa", "tipo", "VARCHAR(20) NOT NULL DEFAULT 'atividade'")
    adicionar_coluna("tarefa", "concluida_em", "DATETIME")
    adicionar_coluna("usuario", "telefone", "VARCHAR(15) NOT NULL DEFAULT ''")
    adicionar_coluna("plano_de_usuario", "padrao", "BOOLEAN NOT NULL DEFAULT 0")
    adicionar_coluna("usuario", "plano_id", "INTEGER REFERENCES plano_de_usuario(id)")
    migrar_tipo_para_plano()
    garantir_plano_padrao()
    adicionar_coluna("video_do_youtube", "simplificado", "BOOLEAN NOT NULL DEFAULT 0")
    adicionar_coluna("video_do_youtube", "publicado_em", "DATE")
    adicionar_coluna("tarefa", "secoes", "VARCHAR(60) NOT NULL DEFAULT ''")
    adicionar_coluna("video_do_youtube", "plataforma", "VARCHAR(10) NOT NULL DEFAULT 'youtube'")
    adicionar_coluna("video_do_youtube", "endereco_da_miniatura", "VARCHAR(300) NOT NULL DEFAULT ''")
    adicionar_coluna("usuario", "foto", "VARCHAR(64) NOT NULL DEFAULT ''")
    adicionar_coluna("tarefa", "responsavel_id", "INTEGER REFERENCES usuario(id)")
    adicionar_coluna(
        "usuario", "aviso_destinatarios", f"VARCHAR(30) NOT NULL DEFAULT '{DESTINATARIOS_PADRAO}'"
    )
    adicionar_coluna(
        "usuario", "aviso_antecedencia", f"INTEGER NOT NULL DEFAULT {ANTECEDENCIA_PADRAO}"
    )
    migrar_troca_de_senha(email_da_conta_inicial)
    migrar_confirmacao_do_email()
    migrar_tamanho_das_imagens()
    criar_indices_que_faltam()
    completar_dados()


def criar_indices_que_faltam():
    """Os índices dos modelos que os bancos antigos não receberam (as colunas acrescentadas
    por ALTER TABLE ficaram sem eles)."""
    inspetor = inspect(db.engine)
    for tabela in db.metadata.sorted_tables:
        existentes = {indice["name"] for indice in inspetor.get_indexes(tabela.name)}
        for indice in tabela.indexes:
            if indice.name not in existentes:
                indice.create(db.engine)


def completar_dados():
    """Os dados que o sistema garante a cada início, em qualquer banco (só alteram linhas)."""
    garantir_plano_padrao()
    paleta = [cor for cor, _ in CORES_PROJETO]
    for projeto in Projeto.query.filter(Projeto.cor.notin_(paleta)):
        projeto.cor = CORES_ANTIGAS.get(projeto.cor) or cor_mais_proxima(projeto.cor)
    db.session.commit()


def criar_conta_inicial(app):
    email = app.config["CONTA_INICIAL_EMAIL"]
    if not email or Usuario.query.filter_by(email=email).first():
        return

    security.datastore.create_user(
        email=email,
        nome=app.config["CONTA_INICIAL_NOME"],
        password=hash_password(app.config["CONTA_INICIAL_SENHA"]),
        administrador=True,
        confirmed_at=agora(),
        # A senha da conta inicial vem do README ou do ambiente: o primeiro login exige trocá-la.
        trocar_senha=True,
    )
    db.session.commit()


def senha_trocada(_app, user, **_dados):
    # O Flask-Security grava o usuário ao fim da requisição, junto com a senha nova.
    user.trocar_senha = False


def conta_criada(_app, user, **_dados):
    # Sem a confirmação do e-mail, a conta já nasce confirmada: se o envio for ligado depois,
    # quem se cadastrou antes não fica impedido de entrar.
    if not current_app.config["SECURITY_CONFIRMABLE"]:
        user.confirmed_at = agora()


PAGINA_DE_MANUTENCAO = (
    "<!DOCTYPE html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\">"
    "<title>Projetos &amp; Demandas</title></head><body><h1>Sistema em manutenção</h1>"
    "<p>O banco de dados ainda não está pronto. Tente novamente em alguns minutos.</p></body></html>"
)


def pagina_de_manutencao():
    """Com as tabelas por criar ou atualizar (flask banco atualizar), nenhuma página consulta o banco."""
    if current_app.config["BANCO_PRONTO"] or request.endpoint == "static":
        return None
    if request.path.startswith("/api/"):
        return {"erro": "Sistema em manutenção."}, 503, {"Retry-After": "300"}
    return PAGINA_DE_MANUTENCAO, 503, {"Retry-After": "300"}


def executando_comando_do_banco():
    """flask banco ...: os avisos por e-mail não devem rodar durante esses comandos."""
    programa = Path(sys.argv[0])
    # O executável flask, ou python -m flask (flask/__main__.py).
    pelo_flask = programa.stem == "flask" or programa.parent.name == "flask"
    return pelo_flask and "banco" in sys.argv[1:]


def registrar_protecoes(app):
    if app.config["PROXY_CONFIAVEL"]:
        # Só o Nginx da mesma máquina: um IP e o protocolo informados por um proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    # O endereço vem primeiro: um Host desconhecido não chega às páginas que enviam e-mails.
    app.before_request(conferir_host)
    app.before_request(pagina_de_manutencao)
    # A troca da senha vem antes do limite: a página de troca continua acessível.
    app.before_request(exigir_troca_de_senha)
    app.before_request(conferir_limite)
    app.after_request(aplicar_cabecalhos)
    app.after_request(contar_senha_errada)
    password_changed.connect(senha_trocada)
    password_reset.connect(senha_trocada)
    user_registered.connect(conta_criada)


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)

    if not app.config["SECRET_KEY"]:
        app.config.update(carregar_segredos())

    for diretorio in (DATABASE_DIR, USERFILES_DIR, app.config["ANEXOS_DIR"]):
        diretorio.mkdir(exist_ok=True)

    babel.init_app(app)
    csrf.init_app(app)
    db.init_app(app)
    mail.init_app(app)
    # O envio de e-mails é configurado só pela tela de Configurações. Ele precisa ser lido
    # antes do Flask-Security, que decide ao iniciar se a recuperação de senha existe.
    with app.app_context():
        if db.engine.dialect.name == app.config["BANCO"].tipo:
            preparar_motor(db.engine, app.config["BANCO"])
        situacao = preparar_banco(db.engine, app.config["BANCO_ATUALIZAR_AO_INICIAR"])
        app.config["BANCO_PRONTO"] = situacao in ("atual", "antigo")
        if app.config["BANCO_PRONTO"]:
            cifrar_senha_do_smtp(app.config["SECRET_KEY"])
            configuracao_de_email = db.session.get(ConfiguracaoEmail, 1)
            if configuracao_de_email:
                aplicar_configuracao_de_email(app, configuracao_de_email)
        db.session.remove()
    # O Flask-Security só copia a opção para o objeto global quando ela é verdadeira:
    # sem isto, uma aplicação criada antes com o envio ligado deixaria a recuperação ligada.
    security.recoverable = app.config["SECURITY_RECOVERABLE"]
    security.confirmable = app.config["SECURITY_CONFIRMABLE"]
    # O init_app só aceita formulários e opções: a classe da validação da senha vai direto no objeto.
    security._password_util_cls = SenhaUtil
    security.init_app(
        app,
        SQLAlchemyUserDatastore(db, Usuario, Papel),
        register_form=CadastroForm,
        change_password_form=AlterarSenhaForm,
        login_form=LoginComCaptchaForm,
        forgot_password_form=EsqueciSenhaComCaptchaForm,
    )
    registrar_protecoes(app)

    app.register_blueprint(principal)
    app.register_blueprint(publico)
    app.cli.add_command(banco)
    app.add_template_filter(rotulo_de_tamanho, "tamanho")
    app.add_template_filter(rotulo_em_megabytes, "megabytes")
    app.add_template_filter(rotulo_de_duracao, "duracao")
    app.add_template_global(icone_grupo, "icone_grupo")
    app.add_template_global(estatico, "estatico")
    registrar_erros(app)

    @app.context_processor
    def preferencias_visuais():
        # Fora de uma requisição (os e-mails de avisos.py), não há usuário logado.
        autenticado = bool(current_user) and current_user.is_authenticated
        return {
            "tema": current_user.tema if autenticado else "azul",
            "tarefas_atrasadas": tarefas_atrasadas() if autenticado else [],
        }

    with app.app_context():
        if situacao == "antigo":
            # As migrações antigas usam o Flask-Security (a senha da conta inicial).
            concluir_banco_antigo(db.engine, lambda: atualizar_banco(app.config["CONTA_INICIAL_EMAIL"]))
        if app.config["BANCO_PRONTO"]:
            completar_dados()
            criar_conta_inicial(app)
        # O banco e as chaves: leitura e gravação só para o usuário do serviço (no Linux).
        protegidos = [ARQUIVO_SEGREDOS]
        if db.engine.dialect.name == "sqlite":
            protegidos += arquivos_do_banco(db.engine.url.database)
        proteger_arquivos(protegidos)
        db.session.remove()

    # Os e-mails da Automação saem de uma tarefa periódica dentro do próprio app (avisos.py).
    if app.config["AVISOS_ATIVOS"] and app.config["BANCO_PRONTO"] and not app.testing and not executando_comando_do_banco():
        iniciar_avisos(app, agora, apagar_imagens_pendentes)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8002)
