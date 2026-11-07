# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re

import pytest

from extensions import db
from models import LIMITES_DO_PLANO, PlanoDeUsuario, Usuario

DADOS = {
    "nome": "Básico",
    "armazenamento_mb": "100",
    "categorias": "10",
    "projetos": "200",
    "atividades": "",
    "listas_de_tarefas": "50",
    "videos": "500",
}


@pytest.fixture
def administrador(cliente):
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()
    return cliente


def criar(cliente, **alteracoes):
    return cliente.post("/administracao/planos/novo", data={**DADOS, **alteracoes})


def opcoes(html, campo):
    caixa = html.split('name="{}"'.format(campo))[1].split("</select>")[0]
    return [parte.split(">")[1].split("</option")[0] for parte in caixa.split("<option")[1:]]


def test_menu_administracao_tem_planos_de_usuarios(administrador):
    menu = administrador.get("/").get_data(as_text=True).split('id="menu-administracao"')[1].split("</div>")[0]

    assert 'href="/administracao/planos"' in menu and "Planos de Usuários</a>" in menu
    assert menu.index("Usuários</a>") < menu.index("Planos de Usuários</a>") < menu.index("Configurações</a>")


def test_so_o_administrador_acessa(cliente):
    db.session.add(PlanoDeUsuario(nome="X", armazenamento_mb=1))
    db.session.commit()
    plano = PlanoDeUsuario.query.filter_by(padrao=False).one()

    assert "/administracao/planos" not in cliente.get("/").get_data(as_text=True)
    for url in ("/administracao/planos", "/administracao/planos/novo", "/administracao/planos/{}/editar".format(plano.id)):
        assert cliente.get(url).status_code == 403
    assert criar(cliente).status_code == 403
    assert cliente.post("/administracao/planos/{}/excluir".format(plano.id)).status_code == 403
    assert PlanoDeUsuario.query.filter_by(padrao=False).count() == 1


def test_formulario_tem_as_listas_pedidas(administrador):
    html = administrador.get("/administracao/planos/novo").get_data(as_text=True)

    assert 'name="nome"' in html and 'name="armazenamento_mb"' in html
    assert "Quantidade de Armazenamento em MB" in html
    assert opcoes(html, "categorias") == [str(n) for n in range(10, 101, 10)] + ["Ilimitadas"]
    assert opcoes(html, "projetos") == [str(n) for n in range(10, 201, 10)] + ["300", "400", "500", "Ilimitadas"]
    for campo in ("atividades", "listas_de_tarefas", "videos"):
        assert opcoes(html, campo) == ["25"] + [str(n) for n in range(50, 501, 50)] + ["Ilimitadas"]
        # O formulário de plano novo começa no primeiro valor da lista.
        assert '<option selected value="25">25</option>' in html.split('name="{}"'.format(campo))[1].split("</select>")[0]
    assert [rotulo for rotulo, _ in LIMITES_DO_PLANO.values()] == [
        "Quantidade de Categorias", "Quantidade de Projetos", "Quantidade de Demandas",
        "Quantidade de Listas de Tarefas", "Quantidade de Vídeos",
    ]


def test_criar_plano_grava_os_limites_e_ilimitadas_como_vazio(administrador):
    assert criar(administrador).status_code == 302

    plano = PlanoDeUsuario.query.filter_by(padrao=False).one()
    assert (plano.nome, plano.armazenamento_mb) == ("Básico", 100)
    assert (plano.categorias, plano.projetos, plano.atividades) == (10, 200, None)
    assert (plano.listas_de_tarefas, plano.videos) == (50, 500)


@pytest.mark.parametrize("alteracao", [
    {"nome": ""}, {"nome": "x" * 101}, {"armazenamento_mb": ""}, {"armazenamento_mb": "abc"},
    {"armazenamento_mb": "0"}, {"armazenamento_mb": "1.5"}, {"categorias": "15"}, {"projetos": "210"},
    {"atividades": "40"}, {"videos": "ilimitadas"},
])
def test_dados_invalidos_nao_criam_o_plano(administrador, alteracao):
    resposta = criar(administrador, **alteracao)

    assert resposta.status_code == 200
    assert 'class="erro-campo"' in resposta.get_data(as_text=True)
    assert PlanoDeUsuario.query.filter_by(padrao=False).count() == 0


def test_nome_repetido_e_recusado_sem_diferenciar_maiusculas(administrador):
    criar(administrador)

    resposta = criar(administrador, nome="  BÁSICO ")

    assert "Já existe um plano com este nome." in resposta.get_data(as_text=True)
    assert PlanoDeUsuario.query.filter_by(padrao=False).count() == 1


def test_listagem_mostra_so_o_nome_e_as_acoes(administrador):
    criar(administrador)
    plano = PlanoDeUsuario.query.filter_by(padrao=False).one()

    html = administrador.get("/administracao/planos").get_data(as_text=True)
    tabela = html.split('<table class="tabela tabela-planos">')[1].split("</table>")[0]

    cabecalhos = [re.sub(r"<[^>]+>|[▲▼]", "", parte.split(">", 1)[1].split("</th>")[0]).strip()
                  for parte in tabela.split("<th scope")[1:]]
    assert len(cabecalhos) == 4 and "Nome" in cabecalhos[0]
    assert cabecalhos[1:] == ["Capacidades", "Quantidade de Usuários", "Ações"]
    # O Nome mostra só o nome; Atividades está como Ilimitadas nos dados do teste.
    assert "<td>Básico</td>" in tabela
    # A coluna Capacidades vem logo depois do Nome.
    depois_do_nome = tabela.split("<td>Básico</td>")[1].strip()
    assert depois_do_nome.startswith('<td class="tabela-capacidades" data-rotulo="Capacidades">100 MB / 10 / 200 / * / 50 / 500</td>')
    assert 'href="/administracao/planos/{}/editar"'.format(plano.id) in tabela and "Alterar</a>" in tabela
    assert 'data-url-excluir="/administracao/planos/{}/excluir"'.format(plano.id) in tabela and "Excluir</button>" in tabela


def test_listagem_reordena_pelo_nome(administrador):
    for nome in ("Prata", "bronze", "Ouro"):
        criar(administrador, nome=nome)

    def nomes(consulta=""):
        html = administrador.get("/administracao/planos" + consulta).get_data(as_text=True)
        return sorted(("Prata", "bronze", "Ouro"), key=html.index)

    assert nomes("?ordem=nome") == ["bronze", "Ouro", "Prata"]
    assert nomes("?ordem=nome&sentido=desc") == ["Prata", "Ouro", "bronze"]
    assert 'href="/administracao/planos?ordem=nome&amp;sentido=desc"' in administrador.get("/administracao/planos?ordem=nome").get_data(as_text=True)
    assert 'href="/administracao/planos?ordem=nome&amp;sentido=asc"' in administrador.get("/administracao/planos?ordem=nome&sentido=desc").get_data(as_text=True)


def test_alterar_mostra_os_valores_e_salva(administrador):
    criar(administrador)
    plano = PlanoDeUsuario.query.filter_by(padrao=False).one()
    url = "/administracao/planos/{}/editar".format(plano.id)

    html = administrador.get(url).get_data(as_text=True)
    assert 'value="Básico"' in html and 'value="100"' in html
    assert 'selected value="">Ilimitadas' in html.split('name="atividades"')[1].split("</select>")[0]

    resposta = administrador.post(url, data={**DADOS, "nome": "Avançado", "atividades": "300", "videos": ""})
    assert resposta.status_code == 302
    db.session.refresh(plano)
    assert (plano.nome, plano.atividades, plano.videos) == ("Avançado", 300, None)


def test_alterar_mantendo_o_proprio_nome_e_permitido(administrador):
    criar(administrador)
    plano = PlanoDeUsuario.query.filter_by(padrao=False).one()

    resposta = administrador.post("/administracao/planos/{}/editar".format(plano.id), data={**DADOS, "armazenamento_mb": "250"})

    assert resposta.status_code == 302
    db.session.refresh(plano)
    assert plano.armazenamento_mb == 250


def test_excluir_plano(administrador):
    criar(administrador)
    plano = PlanoDeUsuario.query.filter_by(padrao=False).one()

    resposta = administrador.post("/administracao/planos/{}/excluir".format(plano.id))

    assert resposta.status_code == 302
    assert PlanoDeUsuario.query.filter_by(padrao=False).count() == 0


def test_plano_inexistente_retorna_404(administrador):
    assert administrador.get("/administracao/planos/999/editar").status_code == 404
    assert administrador.post("/administracao/planos/999/excluir").status_code == 404


def test_nome_repetido_com_acento_em_maiuscula_e_recusado(administrador):
    criar(administrador, nome="Ácido")

    resposta = criar(administrador, nome="ácido")

    assert "Já existe um plano com este nome." in resposta.get_data(as_text=True)
    assert PlanoDeUsuario.query.filter_by(padrao=False).count() == 1


def test_listagem_mostra_a_quantidade_de_usuarios_centralizada(administrador, outro_cliente, criar_cliente):
    criar(administrador)
    basico = PlanoDeUsuario.query.filter_by(nome="Básico").one()
    terceira = criar_cliente("carla@exemplo.com")
    for conta in (outro_cliente, terceira):
        db.session.get(Usuario, conta.usuario_id).plano = basico
    db.session.commit()

    html = administrador.get("/administracao/planos").get_data(as_text=True)

    def quantidade(nome):
        linha = html.split("<td>{}".format(nome))[1].split("</tr>")[0]
        return linha.split('<td class="tabela-quantidade" data-rotulo="Usuários">')[1].split("</td>")[0]

    assert quantidade("Básico") == "2"
    assert quantidade("Iniciante") == "1"  # quem ficou no padrão: o administrador
    css = open("static/css/style.css", encoding="utf-8").read()
    regra = css.split(".tabela-planos .tabela-quantidade")[1].split("}")[0]
    assert "text-align: center" in regra


@pytest.mark.parametrize("limites, capacidades", [
    ({}, "250 MB / * / * / * / * / *"),
    ({"categorias": 10, "projetos": 20, "atividades": 50, "listas_de_tarefas": 100, "videos": 500},
     "250 MB / 10 / 20 / 50 / 100 / 500"),
    ({"projetos": 400, "videos": 25}, "250 MB / * / 400 / * / * / 25"),
])
def test_capacidades_na_ordem_dos_campos_com_asterisco_para_ilimitadas(limites, capacidades):
    assert PlanoDeUsuario(nome="Ouro", armazenamento_mb=250, **limites).capacidades == capacidades


@pytest.mark.parametrize("projetos", ["300", "400", "500"])
def test_plano_aceita_300_400_e_500_projetos(administrador, projetos):
    criar(administrador, projetos=projetos)

    assert PlanoDeUsuario.query.filter_by(nome="Básico").one().projetos == int(projetos)


@pytest.mark.parametrize("projetos", ["250", "600"])
def test_plano_recusa_projetos_fora_das_opcoes(administrador, projetos):
    assert criar(administrador, projetos=projetos).status_code == 200
    assert PlanoDeUsuario.query.filter_by(nome="Básico").count() == 0


def test_plano_aceita_25_atividades_listas_de_tarefas_e_videos(administrador):
    criar(administrador, atividades="25", listas_de_tarefas="25", videos="25")

    plano = PlanoDeUsuario.query.filter_by(nome="Básico").one()
    assert (plano.atividades, plano.listas_de_tarefas, plano.videos) == (25, 25, 25)


def test_25_continua_fora_das_categorias_e_projetos(administrador):
    assert criar(administrador, categorias="25").status_code == 200
    assert criar(administrador, projetos="25").status_code == 200
    assert PlanoDeUsuario.query.filter_by(nome="Básico").count() == 0


def ordem_da_listagem(cliente, consulta):
    html = cliente.get("/administracao/planos" + consulta).get_data(as_text=True)
    corpo = html.split("<tbody>")[1].split("</tbody>")[0]
    return [linha.split("<td>")[1].split("<")[0].strip() for linha in corpo.split("<tr>")[1:]]


def test_colunas_nome_capacidades_e_usuarios_sao_ordenaveis(administrador):
    html = administrador.get("/administracao/planos").get_data(as_text=True)

    for chave in ("nome", "capacidades", "usuarios"):
        assert 'href="/administracao/planos?ordem={}&amp;sentido='.format(chave) in html
    assert "?ordem=acoes" not in html


def test_ordenar_por_capacidades(administrador):
    criar(administrador, nome="Grande", armazenamento_mb="500")
    criar(administrador, nome="Médio limitado", armazenamento_mb="50", categorias="10")
    criar(administrador, nome="Médio ilimitado", armazenamento_mb="50", categorias="")

    # Iniciante tem 10 MB; no empate de 50 MB, Ilimitadas conta como o maior limite.
    assert ordem_da_listagem(administrador, "?ordem=capacidades") == ["Iniciante", "Médio limitado", "Médio ilimitado", "Grande"]
    assert ordem_da_listagem(administrador, "?ordem=capacidades&sentido=desc") == ["Grande", "Médio ilimitado", "Médio limitado", "Iniciante"]


def test_ordenar_pela_quantidade_de_usuarios(administrador, outro_cliente, criar_cliente):
    criar(administrador, nome="Vazio")
    criar(administrador, nome="Cheio")
    cheio = PlanoDeUsuario.query.filter_by(nome="Cheio").one()
    for conta in (outro_cliente, criar_cliente("carla@exemplo.com")):
        db.session.get(Usuario, conta.usuario_id).plano = cheio
    db.session.commit()

    # Cheio tem 2, Iniciante tem 1 (o administrador) e Vazio, nenhum.
    assert ordem_da_listagem(administrador, "?ordem=usuarios") == ["Vazio", "Iniciante", "Cheio"]
    assert ordem_da_listagem(administrador, "?ordem=usuarios&sentido=desc") == ["Cheio", "Iniciante", "Vazio"]


def test_listagem_comeca_por_capacidades_em_ordem_crescente(administrador):
    criar(administrador, nome="Aaa grande", armazenamento_mb="500")
    criar(administrador, nome="Zzz pequeno", armazenamento_mb="5")

    html = administrador.get("/administracao/planos").get_data(as_text=True)

    # Pelo nome, Aaa viria primeiro; pelas capacidades, o menor plano vem antes.
    assert ordem_da_listagem(administrador, "") == ["Zzz pequeno", "Iniciante", "Aaa grande"]
    cabecalho = html.split("<thead>")[1].split("</thead>")[0]
    assert 'aria-sort="ascending"' in cabecalho.split("Capacidades")[0].rsplit("<th", 1)[1]
    assert 'href="/administracao/planos?ordem=capacidades&amp;sentido=desc"' in html


def test_ordem_desconhecida_usa_as_capacidades(administrador):
    criar(administrador, nome="Aaa grande", armazenamento_mb="500")

    assert ordem_da_listagem(administrador, "?ordem=senha") == ["Iniciante", "Aaa grande"]
