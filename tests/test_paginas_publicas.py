# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Área externa: menu de navegação, Projetos & Demandas, Planos, Manual e Atendimento."""
import re
from pathlib import Path

import pytest

from extensions import db, mail
from models import PlanoDeUsuario
from paginas_publicas import (
    ATENDIMENTO_INDISPONIVEL,
    MENSAGEM_ENVIADA,
    MENU_PUBLICO,
    linhas_dos_planos,
    ordem_dos_planos,
)
from seguranca import LIMITES, limitador

PAGINAS = {
    "/projetos-e-demandas": "Projetos & Demandas",
    "/planos": "Planos",
    "/manual": "Manual",
    "/atendimento": "Atendimento",
}
RAIZ = Path(__file__).resolve().parent.parent
REMETENTE = ("Projetos & Demandas", "contato@exemplo.com")
DADOS = {
    "nome": "Maria Souza",
    "email": "maria@exemplo.com",
    "telefone": "(11) 98765-4321",
    "mensagem": "Como compartilho uma categoria?",
}


@pytest.fixture
def envio(app):
    app.config.update(MAIL_SERVER="smtp.exemplo.com", MAIL_DEFAULT_SENDER=REMETENTE)
    return app


def texto_visivel(html):
    """O texto e os atributos lidos pelas pessoas, sem os comentários e o código."""
    sem_comentarios = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    atributos = re.findall(r'(?:alt|aria-label|title|placeholder|data-dica)="([^"]*)"', sem_comentarios)
    return " ".join(atributos) + " " + re.sub(r"<[^>]*>", " ", sem_comentarios)


@pytest.mark.parametrize("endereco", PAGINAS)
def test_paginas_publicas_abrem_sem_login(app, endereco):
    resposta = app.test_client().get(endereco)

    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert 'class="navegacao-publica"' in html


@pytest.mark.parametrize("endereco, rotulo", PAGINAS.items())
def test_menu_tem_os_quatro_itens_e_marca_a_pagina_atual(app, endereco, rotulo):
    html = app.test_client().get(endereco).get_data(as_text=True)
    menu = html.split('class="navegacao-publica-itens"')[1].split("</ul>")[0]

    rotulos = re.findall(r">(?:<strong>)?([^<]+)(?:</strong>)?</a>", menu)
    assert rotulos == ["Projetos &amp; Demandas", "Planos", "Manual", "Atendimento"]
    assert re.findall(r'aria-current="page">(?:<strong>)?([^<]+)<', menu) == [rotulo.replace("&", "&amp;")]


@pytest.mark.parametrize("endereco", [*PAGINAS, "/login"])
def test_menu_fica_no_cabecalho_a_direita_do_logotipo(app, endereco):
    html = app.test_client().get(endereco).get_data(as_text=True)
    cabecalho = html.split('<header class="topo topo-publico">')[1].split("</header>")[0]

    assert cabecalho.index('class="marca"') < cabecalho.index('class="navegacao-publica"')
    assert html.count('class="navegacao-publica"') == 1


def test_menu_publico_na_ordem_pedida():
    assert [rotulo for _, rotulo in MENU_PUBLICO] == ["Projetos & Demandas", "Planos", "Manual", "Atendimento"]


def test_visitante_ve_entrar_e_criar_conta(app):
    html = app.test_client().get("/planos").get_data(as_text=True)

    assert ">Entrar</a>" in html
    assert ">Criar conta</a>" in html
    assert 'class="topo-acoes"' not in html


@pytest.mark.parametrize("endereco", PAGINAS)
def test_quem_esta_logado_fica_com_o_cabecalho_da_area_interna_e_sem_rodape(cliente, endereco):
    html = cliente.get(endereco).get_data(as_text=True)
    interno = cliente.get("/perfil").get_data(as_text=True)

    assert html.split("</header>")[0].split("<header")[1] == interno.split("</header>")[0].split("<header")[1]
    assert 'class="navegacao-publica"' not in html
    assert 'class="publico-rodape"' not in html
    assert 'class="topo-acoes"' in html


@pytest.mark.parametrize("endereco", PAGINAS)
def test_visitante_ve_o_rodape(app, endereco):
    assert 'class="publico-rodape"' in app.test_client().get(endereco).get_data(as_text=True)


@pytest.mark.parametrize("endereco", ["/", "/perfil", "/meu-dia"])
def test_menu_do_usuario_leva_ao_manual_e_ao_atendimento(cliente, endereco):
    html = cliente.get(endereco).get_data(as_text=True)
    menu = html.split('id="menu-usuario"')[1].split("</div>")[0]

    senha = menu.index("Alterar a Senha</a>")
    manual = menu.index('href="/manual"')
    atendimento = menu.index('href="/atendimento"')
    assert senha < manual < atendimento < menu.index("Sair</button>")
    assert ">Manual</a>" in menu.replace("</svg>", ">") and "Atendimento</a>" in menu


@pytest.mark.parametrize("endereco", PAGINAS)
def test_nome_do_sistema_em_negrito_nas_paginas_publicas(app, endereco):
    html = app.test_client().get(endereco).get_data(as_text=True)
    corpo = re.sub(r"<title>.*?</title>|<!--.*?-->", "", html, flags=re.S)
    # O nome do cabeçalho (.marca-nome) e o do rodapé têm o "&" em verde e já são negrito.
    corpo = corpo.replace('Projetos <span class="marca-e">&amp;</span> Demandas', "")
    corpo = re.sub(r'="[^"]*"', '=""', corpo)

    assert "Projetos &amp; Demandas" in corpo
    assert corpo.count("Projetos &amp; Demandas") == corpo.count("<strong>Projetos &amp; Demandas</strong>")


def test_atendimento_preenche_os_dados_de_quem_esta_logado(cliente):
    from models import Usuario

    usuario = db.session.get(Usuario, cliente.usuario_id)
    usuario.nome = "Ana Lima"
    usuario.telefone = "(11) 91234-5678"
    db.session.commit()

    html = cliente.get("/atendimento").get_data(as_text=True)

    assert 'value="Ana Lima"' in html
    assert 'value="ana@exemplo.com"' in html
    assert 'value="(11) 91234-5678"' in html


def test_login_e_cadastro_mostram_o_menu_so_para_visitantes(app, cliente):
    visitante = app.test_client()
    login = visitante.get("/login").get_data(as_text=True)
    cadastro = visitante.get("/register").get_data(as_text=True)

    assert 'class="navegacao-publica"' in login
    # O link da própria página sai do menu.
    assert ">Entrar</a>" not in login.split('class="navegacao-publica"')[1].split("</nav>")[0]
    assert ">Criar conta</a>" not in cadastro.split('class="navegacao-publica"')[1].split("</nav>")[0]
    assert 'class="navegacao-publica"' not in cliente.get("/change").get_data(as_text=True)


def test_quadro_nao_tem_o_menu_publico(cliente):
    assert 'class="navegacao-publica"' not in cliente.get("/").get_data(as_text=True)


def test_logotipo_leva_o_visitante_a_apresentacao(app, cliente):
    assert 'class="marca" href="/projetos-e-demandas"' in app.test_client().get("/login").get_data(as_text=True)
    assert 'class="marca" href="/"' in cliente.get("/manual").get_data(as_text=True)


def test_apresentacao_tem_os_recursos_e_a_captura_do_quadro(app):
    html = app.test_client().get("/projetos-e-demandas").get_data(as_text=True)

    for trecho in ("Meu Dia", "Calendário", "Trabalho em equipe", "O que você ganha", "img/manual/quadro.webp"):
        assert trecho in html
    assert 'href="/register"' in html


def test_capturas_usadas_existem():
    usadas = set()
    for modelo in (RAIZ / "templates" / "publico").glob("*.html"):
        usadas |= set(re.findall(r'captura\("([\w-]+)"', modelo.read_text(encoding="utf-8")))

    assert usadas
    for nome in usadas:
        assert (RAIZ / "static" / "img" / "manual" / f"{nome}.webp").is_file(), nome


def test_capturas_tem_texto_alternativo(app):
    for endereco in PAGINAS:
        html = app.test_client().get(endereco).get_data(as_text=True)
        for imagem in re.findall(r"<img [^>]*>", html):
            assert re.search(r'alt="[^"]*"', imagem), imagem
            if "img/manual/" in imagem:
                assert not re.search(r'alt=""', imagem), imagem


def test_planos_mostra_os_planos_do_banco(app):
    db.session.add(PlanoDeUsuario(nome="Empresa", armazenamento_mb=500, categorias=50, projetos=None,
                                  atividades=None, listas_de_tarefas=None, videos=None))
    db.session.commit()

    html = app.test_client().get("/planos").get_data(as_text=True)

    assert "Empresa" in html
    assert "500 MB" in html
    assert "Ilimitado" in html
    padrao = PlanoDeUsuario.query.filter_by(padrao=True).one()
    assert padrao.nome in html
    assert "Plano inicial" in html


def test_planos_acompanha_as_alteracoes_do_banco(app):
    cliente = app.test_client()
    plano = PlanoDeUsuario(nome="Temporário", armazenamento_mb=30, categorias=3, projetos=3,
                           atividades=3, listas_de_tarefas=3, videos=3)
    db.session.add(plano)
    db.session.commit()
    assert "Temporário" in cliente.get("/planos").get_data(as_text=True)

    plano.nome = "Renomeado"
    db.session.commit()
    html = cliente.get("/planos").get_data(as_text=True)
    assert "Renomeado" in html and "Temporário" not in html

    db.session.delete(plano)
    db.session.commit()
    assert "Renomeado" not in cliente.get("/planos").get_data(as_text=True)


def test_planos_ordenados_do_menor_para_o_maior(app):
    db.session.add_all([
        PlanoDeUsuario(nome="Grande", armazenamento_mb=900, categorias=1, projetos=1, atividades=1, listas_de_tarefas=1, videos=1),
        PlanoDeUsuario(nome="Igual limitado", armazenamento_mb=5, categorias=1, projetos=1, atividades=1, listas_de_tarefas=1, videos=1),
        PlanoDeUsuario(nome="Igual ilimitado", armazenamento_mb=5, categorias=None, projetos=1, atividades=1, listas_de_tarefas=1, videos=1),
    ])
    db.session.commit()

    nomes = [linha["nome"] for linha in linhas_dos_planos()]

    assert nomes.index("Igual limitado") < nomes.index("Igual ilimitado") < nomes.index("Grande")
    assert nomes[-1] == "Grande"


def test_ordem_dos_planos_trata_ilimitado_como_o_maior():
    pequeno = PlanoDeUsuario(nome="a", armazenamento_mb=10, categorias=999, projetos=1, atividades=1, listas_de_tarefas=1, videos=1)
    ilimitado = PlanoDeUsuario(nome="b", armazenamento_mb=10, categorias=None, projetos=1, atividades=1, listas_de_tarefas=1, videos=1)

    assert ordem_dos_planos(pequeno) < ordem_dos_planos(ilimitado)


def test_tabela_dos_planos_tem_rotulos_para_o_celular(app):
    html = app.test_client().get("/planos").get_data(as_text=True)
    linha = html.split("<tbody>")[1].split("</tr>")[0]

    rotulos = re.findall(r'data-rotulo="([^"]+)"', linha)
    assert rotulos == ["Espaço para arquivos", "Categorias", "Projetos", "Demandas", "Listas de tarefas", "Vídeos"]


def test_manual_tem_o_indice_e_as_secoes(app):
    html = app.test_client().get("/manual").get_data(as_text=True)

    ancoras = re.findall(r'<a href="#([\w-]+)"', html)
    assert len(ancoras) >= 15
    for ancora in ancoras:
        assert f'id="{ancora}"' in html
    for nome in ("menu-criar", "demanda", "lista-de-tarefas", "contexto", "video", "meu-dia", "calendario", "perfil", "atalhos"):
        assert f"img/manual/{nome}.webp" in html


@pytest.mark.parametrize("endereco", PAGINAS)
def test_paginas_publicas_usam_o_vocabulario_da_interface(app, endereco):
    html = app.test_client().get(endereco).get_data(as_text=True)
    # A seção da lista de tarefas do Manual é a única que fala das tarefas como itens.
    html = re.sub(r'<section id="lista-de-tarefas".*?</section>', "", html, flags=re.S)
    texto = re.sub(r"listas? de tarefas", "", texto_visivel(html), flags=re.I)

    assert not re.search(r"atividade", texto, re.I)
    assert not re.search(r"generalista", texto, re.I)
    assert not re.search(r"tarefa", texto, re.I)
    assert not re.search(r"\blistas?\b", texto, re.I)


def test_atendimento_tem_os_campos_pedidos(app):
    html = app.test_client().get("/atendimento").get_data(as_text=True)

    for campo in ("nome", "email", "telefone", "mensagem"):
        assert f'name="{campo}"' in html
    telefone = re.search(r'<input[^>]*name="telefone"[^>]*>', html).group(0)
    assert 'placeholder="(00) 00000-0000"' in telefone
    assert "data-mascara-telefone" in telefone
    assert "required" not in telefone
    for campo in ("nome", "email"):
        assert "required" in re.search(rf'<input[^>]*name="{campo}"[^>]*>', html).group(0)
    assert "required" in re.search(r'<textarea[^>]*name="mensagem"[^>]*>', html).group(0)
    assert 'class="atendimento-armadilha" aria-hidden="true"' in html


def test_atendimento_envia_para_o_proprio_remetente(envio):
    with mail.record_messages() as enviadas:
        resposta = envio.test_client().post("/atendimento", data=DADOS, follow_redirects=True)

    assert resposta.status_code == 200
    assert MENSAGEM_ENVIADA in resposta.get_data(as_text=True)
    assert len(enviadas) == 1
    mensagem = enviadas[0]
    assert mensagem.recipients == ["contato@exemplo.com"]
    assert mensagem.reply_to == "maria@exemplo.com"
    assert mensagem.subject == "Atendimento - Maria Souza"
    for valor in DADOS.values():
        assert valor in mensagem.body
        assert valor in mensagem.html


def test_atendimento_aceita_sem_telefone(envio):
    with mail.record_messages() as enviadas:
        envio.test_client().post("/atendimento", data={**DADOS, "telefone": ""})

    assert len(enviadas) == 1
    assert "não informado" in enviadas[0].body


@pytest.mark.parametrize("campo, mensagem", [
    ("nome", "Informe seu nome."),
    ("email", "Informe seu e-mail."),
    ("mensagem", "Escreva a sua mensagem."),
])
def test_atendimento_exige_os_campos_obrigatorios(envio, campo, mensagem):
    with mail.record_messages() as enviadas:
        resposta = envio.test_client().post("/atendimento", data={**DADOS, campo: ""})

    assert resposta.status_code == 200
    assert mensagem in resposta.get_data(as_text=True)
    assert enviadas == []


@pytest.mark.parametrize("campo, valor", [("email", "nao-e-email"), ("telefone", "123")])
def test_atendimento_recusa_dados_invalidos(envio, campo, valor):
    with mail.record_messages() as enviadas:
        resposta = envio.test_client().post("/atendimento", data={**DADOS, campo: valor})

    assert resposta.status_code == 200
    assert 'class="erro-campo"' in resposta.get_data(as_text=True)
    assert enviadas == []


def test_atendimento_tira_as_quebras_de_linha_do_assunto(envio):
    with mail.record_messages() as enviadas:
        envio.test_client().post("/atendimento", data={**DADOS, "nome": "Maria\r\nBcc: x@exemplo.com"})

    assert enviadas[0].subject == "Atendimento - Maria Bcc: x@exemplo.com"


def test_atendimento_ignora_os_robos(envio):
    with mail.record_messages() as enviadas:
        resposta = envio.test_client().post("/atendimento", data={**DADOS, "site": "http://spam"}, follow_redirects=True)

    assert MENSAGEM_ENVIADA in resposta.get_data(as_text=True)
    assert enviadas == []


def test_atendimento_sem_envio_configurado_avisa_e_mantem_os_dados(app):
    app.config["MAIL_SERVER"] = None
    with mail.record_messages() as enviadas:
        resposta = app.test_client().post("/atendimento", data=DADOS)

    html = resposta.get_data(as_text=True)
    assert ATENDIMENTO_INDISPONIVEL in html
    assert "Maria Souza" in html
    assert enviadas == []


def test_atendimento_com_falha_no_servidor_de_e_mail(envio, monkeypatch):
    def falhar(_mensagem):
        raise OSError("sem conexão")

    monkeypatch.setattr(mail, "send", falhar)
    resposta = envio.test_client().post("/atendimento", data=DADOS)

    assert resposta.status_code == 200
    assert ATENDIMENTO_INDISPONIVEL in resposta.get_data(as_text=True)


def test_atendimento_tem_limite_por_ip(envio):
    envio.config["LIMITES_ATIVOS"] = True
    limitador.zerar()
    metodos, quantidade, _, contagem = LIMITES["publico.atendimento"]
    cliente = envio.test_client()
    try:
        assert metodos == {"POST"} and contagem == "ip"
        for _ in range(quantidade):
            cliente.post("/atendimento", data={})
        assert cliente.post("/atendimento", data={}).status_code == 429
        assert cliente.get("/atendimento").status_code == 200
    finally:
        limitador.zerar()
