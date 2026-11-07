# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import pytest
from flask_security import verify_password
from sqlalchemy import inspect, text

from app import atualizar_banco
from extensions import db
from models import Anexo, Categoria, Imagem, Projeto, PlanoDeUsuario, Tarefa, Usuario

DADOS = {
    "nome": "Carla Dias",
    "email": "carla@exemplo.com",
    "senha": "senha-da-carla",
    "administrador": "nao",
}


@pytest.fixture
def administrador(cliente):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()
    return cliente


def usuario_por_email(email):
    return Usuario.query.filter_by(email=email).first()


def endereco_de(acao, usuario_id):
    return "/administracao/usuarios/{}/{}".format(usuario_id, acao)


def test_novo_usuario_nao_e_administrador(app):
    usuario = Usuario(email="novo@exemplo.com", password="x", fs_uniquifier="u1")
    db.session.add(usuario)
    db.session.commit()

    assert usuario.administrador is False


def test_formulario_comeca_com_administrador_nao(administrador):
    html = administrador.get("/administracao/usuarios/novo").get_data(as_text=True)

    assert '<option selected value="nao">Não</option>' in html
    assert html.index('value="sim">Sim') < html.index('value="nao">Não')


@pytest.mark.parametrize(
    "endereco",
    [
        "/administracao/usuarios",
        "/administracao/usuarios/novo",
        "/administracao/usuarios/1/editar",
    ],
)
def test_telas_de_usuarios_exigem_administrador(cliente, endereco):
    assert cliente.get(endereco).status_code == 403


def test_acoes_de_usuarios_exigem_administrador(cliente, outro_cliente):
    cliente.post("/administracao/usuarios/novo", data=DADOS)
    resposta = cliente.post(endereco_de("excluir", outro_cliente.usuario_id))

    assert resposta.status_code == 403
    assert usuario_por_email(DADOS["email"]) is None
    assert db.session.get(Usuario, outro_cliente.usuario_id) is not None


def test_telas_de_usuarios_exigem_login(app):
    resposta = app.test_client().get("/administracao/usuarios")

    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_lista_mostra_todos_os_usuarios(administrador, outro_cliente):
    html = administrador.get("/administracao/usuarios").get_data(as_text=True)

    assert "ana@exemplo.com" in html
    assert "bruno@exemplo.com" in html
    assert '<td data-rotulo="Administrador">Sim</td>' in html
    assert '<td data-rotulo="Administrador">Não</td>' in html


def test_lista_nao_permite_excluir_a_propria_conta(administrador, outro_cliente):
    html = administrador.get("/administracao/usuarios").get_data(as_text=True)

    assert 'data-dica="Você não pode excluir a sua conta"' in html
    assert html.count(" disabled>") == 1


def test_criar_usuario(administrador):
    resposta = administrador.post(
        "/administracao/usuarios/novo",
        data=dict(DADOS, email="  Carla@Exemplo.com ", administrador="sim"),
    )

    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/administracao/usuarios")
    usuario = usuario_por_email("carla@exemplo.com")
    assert usuario.nome == "Carla Dias"
    assert usuario.administrador is True
    assert verify_password(DADOS["senha"], usuario.password)


def test_usuario_criado_consegue_entrar(app, administrador):
    administrador.post("/administracao/usuarios/novo", data=DADOS)

    resposta = app.test_client().post(
        "/login", data={"email": DADOS["email"], "password": DADOS["senha"]}
    )

    assert resposta.status_code == 302


@pytest.mark.parametrize(
    "campo, valor, mensagem",
    [
        ("senha", "", "Informe a senha."),
        ("senha", "curta", "A senha deve ter entre 10 e 128 caracteres."),
        ("senha", "abcdefghij", "A senha é fácil de adivinhar."),
        ("email", "invalido", "Informe um e-mail válido."),
        ("email", "BRUNO@exemplo.com", "Este e-mail já está cadastrado."),
        ("nome", "Carla", "Informe seu nome e sobrenome."),
        ("administrador", "talvez", "Escolha Sim ou Não."),
    ],
)
def test_criar_usuario_recusa_dados_invalidos(administrador, outro_cliente, campo, valor, mensagem):
    resposta = administrador.post(
        "/administracao/usuarios/novo", data=dict(DADOS, **{campo: valor})
    )

    assert resposta.status_code == 200
    assert mensagem in resposta.get_data(as_text=True)
    assert Usuario.query.count() == 2


def test_editar_usuario_preenche_o_formulario(administrador, outro_cliente):
    db.session.get(Usuario, outro_cliente.usuario_id).nome = "Bruno Lima"
    db.session.commit()

    html = administrador.get(endereco_de("editar", outro_cliente.usuario_id)).get_data(as_text=True)

    assert 'value="Bruno Lima"' in html
    assert 'value="bruno@exemplo.com"' in html
    assert '<option selected value="nao">Não</option>' in html


def test_editar_usuario_nao_tem_campo_senha(administrador, outro_cliente):
    html = administrador.get(endereco_de("editar", outro_cliente.usuario_id)).get_data(as_text=True)

    assert 'name="senha"' not in html
    assert 'type="password"' not in html


@pytest.mark.parametrize("endereco", ["novo", "1/editar"])
def test_formulario_de_usuario_tem_salvar_e_cancelar(administrador, endereco):
    html = administrador.get("/administracao/usuarios/" + endereco).get_data(as_text=True)

    acoes = html.split('class="formulario-acoes"')[1].split("</div>")[0]
    assert '<a class="botao" href="/administracao/usuarios">Cancelar</a>' in acoes
    assert '<button class="botao botao-primario" type="submit">Salvar</button>' in acoes
    assert "Voltar aos usuários" not in html


def test_editar_usuario_mantem_a_senha(administrador, outro_cliente):
    senha_anterior = db.session.get(Usuario, outro_cliente.usuario_id).password

    resposta = administrador.post(endereco_de("editar", outro_cliente.usuario_id), data=DADOS)

    assert resposta.status_code == 302
    usuario = db.session.get(Usuario, outro_cliente.usuario_id)
    assert usuario.nome == "Carla Dias"
    assert usuario.email == "carla@exemplo.com"
    assert usuario.password == senha_anterior
    assert not verify_password(DADOS["senha"], usuario.password)


def test_editar_usuario_altera_o_administrador(administrador, outro_cliente):
    administrador.post(
        endereco_de("editar", outro_cliente.usuario_id),
        data=dict(DADOS, email="bruno@exemplo.com", administrador="sim"),
    )

    assert db.session.get(Usuario, outro_cliente.usuario_id).administrador is True


def test_editar_usuario_recusa_email_de_outro(administrador, outro_cliente):
    resposta = administrador.post(
        endereco_de("editar", outro_cliente.usuario_id),
        data=dict(DADOS, email="ana@exemplo.com"),
    )

    assert "Este e-mail já está cadastrado." in resposta.get_data(as_text=True)
    assert db.session.get(Usuario, outro_cliente.usuario_id).email == "bruno@exemplo.com"


def test_administrador_nao_remove_o_proprio_acesso(administrador):
    resposta = administrador.post(
        endereco_de("editar", administrador.usuario_id),
        data=dict(DADOS, email="ana@exemplo.com"),
    )

    html = resposta.get_data(as_text=True)
    assert "Você não pode remover o seu próprio acesso de administrador." in html
    assert db.session.get(Usuario, administrador.usuario_id).administrador is True


def test_editar_usuario_inexistente(administrador):
    assert administrador.get(endereco_de("editar", 999)).status_code == 404


def test_excluir_usuario_apaga_dados_e_arquivos(app, administrador, outro_cliente):
    pasta = app.config["ANEXOS_DIR"]
    categoria = Categoria(nome="Casa", usuario_id=outro_cliente.usuario_id)
    projeto = Projeto(nome="A fazer", usuario_id=outro_cliente.usuario_id, categoria=categoria)
    tarefa = Tarefa(nome="Tarefa", projeto=projeto)
    db.session.add_all([
        categoria,
        projeto,
        tarefa,
        Anexo(nome="a.txt", arquivo="a" * 32, tamanho=1, tarefa=tarefa),
        Imagem(arquivo="b" * 32, tipo="image/png", usuario_id=outro_cliente.usuario_id),
    ])
    db.session.commit()
    for codigo in ("a" * 32, "b" * 32):
        (pasta / codigo).write_bytes(b"x")

    resposta = administrador.post(
        endereco_de("excluir", outro_cliente.usuario_id), follow_redirects=True
    )

    assert "Usuário excluído." in resposta.get_data(as_text=True)
    assert db.session.get(Usuario, outro_cliente.usuario_id) is None
    assert Projeto.query.count() == Categoria.query.count() == Tarefa.query.count() == 0
    assert Anexo.query.count() == Imagem.query.count() == 0
    assert list(pasta.iterdir()) == []


def test_administrador_nao_exclui_a_propria_conta(administrador):
    resposta = administrador.post(
        endereco_de("excluir", administrador.usuario_id), follow_redirects=True
    )

    assert "Você não pode excluir a sua própria conta." in resposta.get_data(as_text=True)
    assert db.session.get(Usuario, administrador.usuario_id) is not None


@pytest.mark.so_sqlite
def test_atualizar_banco_torna_administradora_a_conta_inicial(cliente, outro_cliente):
    db.session.execute(text("ALTER TABLE usuario DROP COLUMN administrador"))
    db.session.commit()

    atualizar_banco("ana@exemplo.com")

    colunas = {coluna["name"] for coluna in inspect(db.engine).get_columns("usuario")}
    assert "administrador" in colunas
    db.session.expire_all()
    assert db.session.get(Usuario, cliente.usuario_id).administrador is True
    assert db.session.get(Usuario, outro_cliente.usuario_id).administrador is False


@pytest.mark.so_sqlite
def test_atualizar_banco_marca_a_conta_inicial_uma_unica_vez(cliente):
    atualizar_banco("ana@exemplo.com")

    assert db.session.get(Usuario, cliente.usuario_id).administrador is False


def plano(nome, megabytes=10, **campos):
    novo = PlanoDeUsuario(nome=nome, armazenamento_mb=megabytes, **campos)
    db.session.add(novo)
    db.session.commit()
    return novo


def plano_padrao():
    return PlanoDeUsuario.query.filter_by(padrao=True).one()


def test_novo_usuario_recebe_o_plano_padrao(app):
    usuario = Usuario(email="novo@exemplo.com", password="x", fs_uniquifier="u1")
    db.session.add(usuario)
    db.session.commit()

    assert usuario.plano_id == plano_padrao().id
    assert usuario.plano_rotulo == "Iniciante"


def test_formulario_lista_os_planos_e_comeca_no_padrao(administrador):
    plano("Mestre", 250)
    plano("avançado", 100)

    html = administrador.get("/administracao/usuarios/novo").get_data(as_text=True)

    assert '<option selected value="{}">Iniciante</option>'.format(plano_padrao().id) in html
    posicoes = [html.index(rotulo) for rotulo in (">avançado<", ">Iniciante<", ">Mestre<")]
    assert posicoes == sorted(posicoes)
    assert "Tipo de Usuário" not in html


def test_criar_usuario_com_plano(administrador):
    mestre = plano("Mestre", 250)

    administrador.post("/administracao/usuarios/novo", data=dict(DADOS, plano_id=mestre.id))

    assert usuario_por_email(DADOS["email"]).plano_id == mestre.id


def test_criar_usuario_sem_plano_usa_o_padrao(administrador):
    administrador.post("/administracao/usuarios/novo", data=DADOS)

    assert usuario_por_email(DADOS["email"]).plano_id == plano_padrao().id


def test_criar_usuario_recusa_plano_inexistente(administrador):
    resposta = administrador.post("/administracao/usuarios/novo", data=dict(DADOS, plano_id=999))

    assert resposta.status_code == 200
    assert usuario_por_email(DADOS["email"]) is None


def test_editar_usuario_altera_o_plano(administrador, outro_cliente):
    avancado = plano("Avançado", 100)
    url = endereco_de("editar", outro_cliente.usuario_id)

    administrador.post(url, data=dict(DADOS, plano_id=avancado.id))

    assert db.session.get(Usuario, outro_cliente.usuario_id).plano_id == avancado.id
    assert '<option selected value="{}">Avançado</option>'.format(avancado.id) in administrador.get(url).get_data(as_text=True)


def test_lista_mostra_o_plano(administrador):
    db.session.get(Usuario, administrador.usuario_id).plano = plano("Intermediário", 50)
    db.session.commit()

    html = administrador.get("/administracao/usuarios").get_data(as_text=True)

    assert ">Plano</a>" in html and "Tipo de Usuário" not in html
    assert '<td data-rotulo="Plano">Intermediário</td>' in html


def test_cadastro_pela_tela_criar_conta_recebe_o_plano_padrao(app):
    novo_padrao = plano("Gratuito", 5)
    plano_padrao().padrao = False
    novo_padrao.padrao = True
    db.session.commit()

    app.test_client().post("/register", data={
        "nome": "Dora Lima", "email": "dora@exemplo.com",
        "password": "senha-de-teste-123", "password_confirm": "senha-de-teste-123",
    })

    assert usuario_por_email("dora@exemplo.com").plano_id == novo_padrao.id


@pytest.mark.so_sqlite
def test_atualizar_banco_troca_o_tipo_pelo_plano(cliente, outro_cliente, criar_cliente):
    terceira = criar_cliente("carla@exemplo.com")
    db.session.execute(text("UPDATE usuario SET plano_id = NULL"))
    db.session.execute(text("DELETE FROM plano_de_usuario"))
    db.session.execute(text("ALTER TABLE usuario ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'iniciante'"))
    db.session.execute(text("UPDATE usuario SET tipo = 'mestre' WHERE id = :id"), {"id": outro_cliente.usuario_id})
    db.session.execute(text("UPDATE usuario SET tipo = 'avancado' WHERE id = :id"), {"id": terceira.usuario_id})
    db.session.commit()

    atualizar_banco()

    db.session.expire_all()
    planos = {p.nome: p for p in PlanoDeUsuario.query}
    assert {nome: p.armazenamento_mb for nome, p in planos.items()} == {
        "Iniciante": 10, "Intermediário": 50, "Avançado": 100, "Mestre": 250}
    assert [p.nome for p in planos.values() if p.padrao] == ["Iniciante"]
    assert all(getattr(p, limite) is None for p in planos.values()
               for limite in ("categorias", "projetos", "atividades", "listas_de_tarefas", "videos"))
    assert db.session.get(Usuario, cliente.usuario_id).plano.nome == "Iniciante"
    assert db.session.get(Usuario, outro_cliente.usuario_id).plano.nome == "Mestre"
    assert db.session.get(Usuario, terceira.usuario_id).plano.nome == "Avançado"
    assert "tipo" not in {coluna["name"] for coluna in inspect(db.engine).get_columns("usuario")}


@pytest.mark.so_sqlite
def test_atualizar_banco_mantem_planos_ja_criados_com_o_mesmo_nome(cliente):
    db.session.execute(text("ALTER TABLE usuario ADD COLUMN tipo VARCHAR(20) NOT NULL DEFAULT 'iniciante'"))
    db.session.commit()
    existente = plano_padrao()
    existente.armazenamento_mb = 30
    db.session.commit()

    atualizar_banco()

    db.session.expire_all()
    assert PlanoDeUsuario.query.filter_by(nome="Iniciante").count() == 1
    assert db.session.get(PlanoDeUsuario, existente.id).armazenamento_mb == 30


@pytest.mark.so_sqlite
def test_atualizar_banco_cria_o_plano_padrao_quando_falta(cliente):
    db.session.execute(text("UPDATE usuario SET plano_id = NULL"))
    db.session.execute(text("DELETE FROM plano_de_usuario"))
    db.session.commit()

    atualizar_banco()

    db.session.expire_all()
    assert plano_padrao().nome == "Iniciante"
    assert db.session.get(Usuario, cliente.usuario_id).plano_id == plano_padrao().id


def test_administracao_fica_a_esquerda_do_icone_do_usuario(administrador):
    topo = administrador.get("/").get_data(as_text=True).split('<div class="topo-acoes">')[1].split("</header>")[0]

    grupos = topo.index('aria-label="Grupos"')
    administracao = topo.index('aria-controls="menu-administracao"')
    usuario = topo.index('aria-controls="menu-usuario"')
    assert grupos < administracao < usuario
    # Entre a Administração e o ícone do usuário não há outro botão do cabeçalho.
    assert "botao-topo" not in topo[topo.index("</div>", topo.index('id="menu-administracao"')):usuario].replace("botao-topo botao-usuario", "")


def test_colunas_administrador_e_plano_ficam_centralizadas(administrador):
    html = administrador.get("/administracao/usuarios").get_data(as_text=True)
    cabecalhos = html.split('<table class="tabela tabela-usuarios">')[1].split("</thead>")[0]
    css = open("static/css/style.css", encoding="utf-8").read()

    titulos = titulos_do_cabecalho(cabecalhos)
    assert titulos[2:4] == ["Administrador", "Plano"]
    regra = css.split(".tabela-usuarios th:nth-child(3)")[1].split("}")[0]
    assert ".tabela-usuarios td:nth-child(4)" in regra and "text-align: center" in regra


def titulos_do_cabecalho(cabecalhos):
    import re

    return [re.sub(r"<[^>]+>|[▲▼]", "", parte.split(">", 1)[1].split("</th>")[0]).strip()
            for parte in cabecalhos.split("<th ")[1:]]


def emails_na_ordem(cliente, consulta=""):
    html = cliente.get("/administracao/usuarios" + consulta).get_data(as_text=True)
    corpo = html.split("<tbody>")[1].split("</tbody>")[0]
    return [linha.split('<td data-rotulo="E-mail">')[1].split("<")[0] for linha in corpo.split("<tr>")[1:]]


@pytest.fixture
def varios_usuarios(administrador, criar_cliente):
    """Ana (administradora, Iniciante), Bruno, Álvaro e Zélia, com nomes, e-mails e planos variados."""
    mestre = PlanoDeUsuario(nome="Mestre", armazenamento_mb=250)
    db.session.add(mestre)
    db.session.get(Usuario, administrador.usuario_id).nome = "Ana Souza"
    for email, nome, plano_mestre in (("zz@exemplo.com", "Bruno Lima", True),
                                      ("aa@exemplo.com", "Zélia Dias", False),
                                      ("mm@exemplo.com", "Álvaro Reis", True)):
        conta = db.session.get(Usuario, criar_cliente(email).usuario_id)
        conta.nome = nome
        if plano_mestre:
            conta.plano = mestre
    db.session.commit()
    return administrador


def test_cabecalho_tem_acoes_centralizado(administrador):
    html = administrador.get("/administracao/usuarios").get_data(as_text=True)
    cabecalhos = html.split('<table class="tabela tabela-usuarios">')[1].split("</thead>")[0]
    css = open("static/css/style.css", encoding="utf-8").read()

    assert titulos_do_cabecalho(cabecalhos)[-1] == "Ações"
    regra = css.split(".tabela-usuarios th:nth-child(3)")[1].split("}")[0]
    assert ".tabela-usuarios th:last-child" in regra and "text-align: center" in regra


def test_colunas_ordenaveis(administrador):
    html = administrador.get("/administracao/usuarios").get_data(as_text=True)

    for chave in ("nome", "email", "administrador", "plano"):
        assert 'href="/administracao/usuarios?ordem={}&amp;sentido='.format(chave) in html


def test_ordem_inicial_e_pelo_nome_crescente(varios_usuarios):
    html = varios_usuarios.get("/administracao/usuarios").get_data(as_text=True)

    # Álvaro vem antes de Ana: o acento não joga o nome para o fim da lista.
    assert emails_na_ordem(varios_usuarios) == ["mm@exemplo.com", "ana@exemplo.com", "zz@exemplo.com", "aa@exemplo.com"]
    cabecalho_nome = html.split("<thead>")[1].split("Nome")[0].rsplit("<th", 1)[1]
    assert 'aria-sort="ascending"' in cabecalho_nome


@pytest.mark.parametrize("consulta, esperado", [
    ("?ordem=nome&sentido=desc", ["aa@exemplo.com", "zz@exemplo.com", "ana@exemplo.com", "mm@exemplo.com"]),
    ("?ordem=email", ["aa@exemplo.com", "ana@exemplo.com", "mm@exemplo.com", "zz@exemplo.com"]),
    ("?ordem=email&sentido=desc", ["zz@exemplo.com", "mm@exemplo.com", "ana@exemplo.com", "aa@exemplo.com"]),
    # Não antes de Sim; no empate, pelo nome.
    ("?ordem=administrador", ["mm@exemplo.com", "zz@exemplo.com", "aa@exemplo.com", "ana@exemplo.com"]),
    ("?ordem=administrador&sentido=desc", ["ana@exemplo.com", "mm@exemplo.com", "zz@exemplo.com", "aa@exemplo.com"]),
    ("?ordem=plano", ["ana@exemplo.com", "aa@exemplo.com", "mm@exemplo.com", "zz@exemplo.com"]),
    ("?ordem=senha", ["mm@exemplo.com", "ana@exemplo.com", "zz@exemplo.com", "aa@exemplo.com"]),
])
def test_ordenar_a_lista_de_usuarios(varios_usuarios, consulta, esperado):
    assert emails_na_ordem(varios_usuarios, consulta) == esperado
