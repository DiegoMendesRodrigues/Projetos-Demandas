# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from pathlib import Path

import pytest

from app import create_app
from config import Config
from extensions import db
from models import TEMAS, Usuario


@pytest.mark.parametrize("tema", [valor for valor, _ in TEMAS])
def test_cor_da_aplicacao_e_salva_no_perfil(cliente, tema):
    cliente.post("/perfil", data={"nome": "Ana Souza", "tema": tema})

    html = cliente.get("/").get_data(as_text=True)
    assert 'data-tema="{}"'.format(tema) in html


def test_nao_existe_mais_modo_escuro(cliente):
    html = cliente.get("/").get_data(as_text=True)
    css = Path("static/css/style.css").read_text(encoding="utf-8")

    assert "data-modo" not in html
    assert "modo escuro" not in html
    assert "claro e escuro" not in html
    assert "data-modo" not in css


def test_cabecalho_nao_tem_mais_a_cor_da_aplicacao(cliente):
    cabecalho = cliente.get("/").get_data(as_text=True).split("</header>")[0]

    assert "menu-cores" not in cabecalho and "Alterar a cor da aplicação" not in cabecalho
    assert cliente.post("/preferencias", data={"tema": "verde"}).status_code == 404


def test_perfil_oferece_a_cor_da_aplicacao_abaixo_do_telefone(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)

    # Na coluna esquerda, depois do Telefone; os ícones ficam na direita.
    assert html.index('id="telefone"') < html.index("Cor da Aplicação") < html.index('<fieldset class="avatares"')
    for valor, rotulo in TEMAS:
        assert 'value="{}"'.format(valor) in html and "<span>{}</span>".format(rotulo) in html
    assert re.search(r'<input[^>]*checked[^>]*value="azul"', html)


@pytest.mark.parametrize(
    "dica",
    [
        "Ir para a página inicial",
    ],
)
def test_cabecalho_exibe_dica_dos_icones(cliente, dica):
    cabecalho = cliente.get("/").get_data(as_text=True).split("</header>")[0]

    assert 'data-dica="{}"'.format(dica) in cabecalho


def test_cabecalho_e_barra_ficam_em_camadas_acima_do_conteudo():
    css = Path("static/css/style.css").read_text(encoding="utf-8")

    def camada(seletor):
        return int(re.search(seletor + r" \{[^}]*z-index: (\d+)", css).group(1))

    assert camada(r"\.topo") > camada(r"\.barra") > 0


def test_icones_de_criar_exibem_dica(cliente, criar_categoria, criar_projeto):
    criar_categoria(cliente.usuario_id)
    criar_projeto(cliente.usuario_id, "Compras")

    html = cliente.get("/").get_data(as_text=True)

    for dica in ("Criar nova categoria", "Criar novo projeto", "Criar um cartão"):
        assert 'data-dica="{}"'.format(dica) in html
    assert "botao-nova-tarefa" not in html


# "Tarefa" na interface é só o item da lista de tarefas.
TAREFA_COMO_ITEM = re.compile(
    r"lista de tarefas|\b(?:adicionar|remover|descreva|marcar|desmarcar|atualizar)\s+(?:a\s+)?tarefa\b"
    r'|aria-label="Tarefa"|>\s*Tarefas\s*<|"Tarefa"|" a tarefa "|\+ \d+ tarefas?',
    re.I,
)


def test_interface_diz_demanda_e_nao_tarefa(cliente, criar_projeto, criar_tarefa):
    criar_tarefa(criar_projeto(cliente.usuario_id, "Compras"), "Pagar a conta")

    html = cliente.get("/").get_data(as_text=True)
    sem_comentarios = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    sem_codigo = TAREFA_COMO_ITEM.sub("", re.sub(r"<script.*?</script>", "", sem_comentarios, flags=re.S))
    atributos = re.findall(r'(?:data-dica[\w-]*|aria-label|title)="([^"]*)"', sem_codigo)
    textos = re.sub(r"<[^>]*>", " ", sem_codigo)
    javascript = TAREFA_COMO_ITEM.sub("", Path("static/js/app.js").read_text(encoding="utf-8"))

    assert not re.search(r"tarefa", " ".join(atributos) + textos, re.I)
    assert not re.search(r'"[^"\n]* [Tt]arefas?\b[^"\n-]*"|"[Tt]arefas? [^"\n]*"', javascript)
    assert ">Cartão - Demanda</button>" in html


def test_interface_diz_demanda_e_nao_atividade(cliente, criar_projeto, criar_tarefa):
    criar_tarefa(criar_projeto(cliente.usuario_id, "Compras"), "Pagar a conta")
    paginas = [cliente.get(endereco).get_data(as_text=True) for endereco in ("/", "/perfil", "/meu-dia", "/calendario")]
    javascript = Path("static/js/app.js").read_text(encoding="utf-8")

    for html in paginas:
        sem_codigo = re.sub(r"<!--.*?-->|<script.*?</script>", "", html, flags=re.S)
        atributos = re.findall(r'(?:data-dica[\w-]*|aria-label|title|placeholder)="([^"]*)"', sem_codigo)
        textos = re.sub(r"<[^>]*>", " ", sem_codigo)
        assert not re.search(r"atividade", " ".join(atributos) + textos, re.I)
    # No JavaScript, "atividade" só fica como o valor interno do tipo do cartão.
    assert not re.search(r'"[^"\n]*\b[Aa]tividades?\b[^"\n]+"|"[^"\n]+\b[Aa]tividades?\b[^"\n]*"', javascript)
    assert "Nova demanda" in javascript


def test_meu_dia_e_calendario_voltam_para_todos_os_projetos(cliente):
    for endereco in ("/meu-dia", "/calendario"):
        html = cliente.get(endereco).get_data(as_text=True)
        assert '<a class="botao" href="/">Voltar para Todos os Projetos</a>' in html
        assert "Voltar ao quadro" not in html


# "Lista" só fica na interface no tipo de cartão "lista de tarefas" e nos botões do editor.
LISTA_PERMITIDA = re.compile(r'listas? de tarefas|(?:aria-label|data-dica)="Lista(?: numerada)?"', re.I)


def test_interface_diz_projeto_e_nao_projeto(cliente, criar_projeto, criar_tarefa):
    criar_tarefa(criar_projeto(cliente.usuario_id, "Compras"), "Pagar a conta")
    paginas = [cliente.get(endereco).get_data(as_text=True) for endereco in ("/", "/perfil", "/meu-dia", "/calendario")]

    for html in paginas:
        sem_comentarios = re.sub(r"<!--.*?-->", "", html, flags=re.S)
        sem_codigo = LISTA_PERMITIDA.sub("", re.sub(r"<script.*?</script>", "", sem_comentarios, flags=re.S))
        atributos = re.findall(r'(?:data-dica[\w-]*|aria-label|title|placeholder)="([^"]*)"', sem_codigo)
        textos = re.sub(r"<[^>]*>", " ", sem_codigo)
        assert not re.search(r"\blistas?\b", " ".join(atributos) + textos, re.I)
    javascript = LISTA_PERMITIDA.sub("", Path("static/js/app.js").read_text(encoding="utf-8"))
    assert not re.search(r'"[^"\n]* [Ll]istas?\b[^"\n-]*"|"[Ll]istas? [^"\n]*"', javascript)
    assert "Todos os projetos" in paginas[0]


def test_icone_de_nova_categoria_fica_na_lateral(cliente):
    lateral = cliente.get("/").get_data(as_text=True).split("</aside>")[0]

    assert "data-nova-categoria" in lateral


def test_titulo_categorias_tem_icone(cliente):
    lateral = cliente.get("/").get_data(as_text=True).split("</aside>")[0]

    assert "</svg>Categorias</h2>" in lateral


def test_menu_do_usuario_mostra_nome_e_opcoes(cliente):
    db.session.get(Usuario, cliente.usuario_id).nome = "Ana Souza"
    db.session.commit()

    cabecalho = cliente.get("/").get_data(as_text=True).split("</header>")[0]

    assert 'data-dica="Ana Souza"' in cabecalho
    for opcao in ("Meu Perfil", "Alterar a Senha", "Sair"):
        assert "</svg>{}".format(opcao) in cabecalho


def test_menu_de_administracao_fica_antes_do_usuario_e_mostra_opcoes(cliente):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()

    cabecalho = cliente.get("/").get_data(as_text=True).split("</header>")[0]

    assert 'data-dica="Administração"' in cabecalho
    assert cabecalho.index('aria-controls="menu-administracao"') < cabecalho.index('aria-controls="menu-usuario"')
    caixa = cabecalho.split('id="menu-administracao"')[1].split("</div>")[0]
    for opcao in ("Usuários", "Configurações"):
        assert "</svg>{}".format(opcao) in caixa
    assert 'href="/administracao/usuarios"' in caixa


def test_menu_de_administracao_nao_aparece_para_quem_nao_e_administrador(cliente):
    cabecalho = cliente.get("/").get_data(as_text=True).split("</header>")[0]

    assert "menu-administracao" not in cabecalho


def test_menu_de_administracao_nao_aparece_sem_login(app):
    html = app.test_client().get("/login").get_data(as_text=True)

    assert "menu-administracao" not in html


def test_menu_do_usuario_sem_nome_mostra_email(cliente):
    cabecalho = cliente.get("/").get_data(as_text=True).split("</header>")[0]

    assert 'data-dica="ana@exemplo.com"' in cabecalho


def test_preferencias_invalidas_sao_recusadas(cliente):
    cliente.post("/perfil", data={"nome": "Ana Souza", "tema": "roxo"})

    assert db.session.get(Usuario, cliente.usuario_id).tema == "azul"


@pytest.mark.so_sqlite
def test_requisicao_sem_token_csrf_e_recusada(tmp_path):
    class ConfigComCsrf(Config):
        TESTING = True
        SECRET_KEY = "chave-de-teste"
        SECURITY_PASSWORD_SALT = "sal-de-teste"
        SQLALCHEMY_DATABASE_URI = "sqlite:///{}".format(
            (tmp_path / "teste.db").as_posix()
        )

    aplicacao = create_app(ConfigComCsrf)

    resposta = aplicacao.test_client().post(
        "/api/tarefas/1/mover", json={"projeto_id": 1, "posicao": 0}
    )

    assert resposta.status_code == 400
