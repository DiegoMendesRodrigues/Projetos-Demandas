# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Cartão de contexto (tipo "generalista" no código): os campos iniciais da demanda e as seções Arquivos, Descrição, Lista de Tarefas e Vídeo."""
import json
import re
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

import youtube
from app import atualizar_banco
from extensions import db
from forms import ler_secoes
from models import (
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    PlanoDeUsuario,
    Projeto,
    Tarefa,
    Usuario,
    VideoDoYoutube,
)

CODIGO = "jNQXAC9IVRw"
OUTRO_CODIGO = "dQw4w9WgXcQ"
ENDERECO = "https://www.youtube.com/watch?v=" + CODIGO


def pagina(codigo=CODIGO, titulo="Me at the zoo"):
    dados = {
        "videoDetails": {"videoId": codigo, "title": titulo, "author": "jawed",
                         "shortDescription": "Elefantes", "lengthSeconds": "19"},
        "microformat": {"playerMicroformatRenderer": {"publishDate": "2005-04-23"}},
    }
    return "<script>var ytInitialPlayerResponse = {};</script>".format(json.dumps(dados))


@pytest.fixture
def youtube_falso(monkeypatch):
    """Substitui o acesso à internet: guarda os códigos pedidos e devolve a página do código pedido."""
    estado = {"pedidos": [], "erro": None, "titulo": "Me at the zoo"}

    def baixar(codigo):
        estado["pedidos"].append(codigo)
        if estado["erro"]:
            raise estado["erro"]
        return pagina(codigo, estado["titulo"])

    monkeypatch.setattr(youtube, "baixar_pagina", baixar)
    return estado


def itens(*textos, concluidos=()):
    return json.dumps([{"texto": texto, "concluido": indice in concluidos} for indice, texto in enumerate(textos)])


def criar(cliente, projeto, secoes=(), **campos):
    dados = {"nome": "Mudança", "prioridade": "alta", "projeto_id": projeto.id, "tipo": "generalista",
             "secoes": json.dumps(list(secoes))}
    dados.update(campos)
    return cliente.post("/tarefas", data=dados, content_type="multipart/form-data", follow_redirects=True)


def editar(cliente, tarefa, secoes=(), **campos):
    dados = {"nome": tarefa.nome, "prioridade": tarefa.prioridade, "projeto_id": tarefa.projeto_id,
             "secoes": json.dumps(list(secoes))}
    dados.update(campos)
    return cliente.post("/tarefas/{}/editar".format(tarefa.id), data=dados,
                        content_type="multipart/form-data", follow_redirects=True)


def test_ler_secoes_ignora_as_desconhecidas_e_poe_na_ordem():
    assert ler_secoes(json.dumps(["video", "x", "descricao", "video"])) == ["descricao", "video"]
    with pytest.raises(ValueError):
        ler_secoes("não é json")


def test_menu_do_mais_comeca_pelo_generalista(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    menu = html.split('id="menu-criar-{}"'.format(projeto.id))[1].split("</div>")[0]

    primeiro = menu.index(">Cartão - Contexto</button>")
    assert 'data-nova-tarefa data-tipo="generalista"' in menu
    assert primeiro < menu.index(">Cartão - Demanda</button>") < menu.index(">Cartão - Vídeo</button>")


def test_dialogo_tem_os_botoes_das_quatro_secoes(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    dialogo = html.split('id="dialogo-tarefa"')[1].split("</dialog>")[0]

    for secao, rotulo in (("arquivos", "Arquivos"), ("descricao", "Descrição"), ("tarefas", "Lista de Tarefas"), ("video", "Vídeo")):
        assert 'data-adicionar-secao="{}">'.format(secao) in dialogo and rotulo in dialogo
        assert 'data-secao="{}"'.format(secao) in dialogo
        assert 'data-remover-secao="{}"'.format(secao) in dialogo
    assert 'name="secoes"' in dialogo and 'name="video_endereco"' in dialogo


def test_generalista_so_com_os_campos_iniciais(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    criar(cliente, projeto, local="Casa", marcacoes=json.dumps(["urgente"]),
          previsao_execucao="2030-01-02T10:30", descricao="<p>Não vai</p>", itens=itens("Não vai"))

    tarefa = Tarefa.query.one()
    assert (tarefa.tipo, tarefa.nome, tarefa.prioridade, tarefa.local) == ("generalista", "Mudança", "alta", "Casa")
    assert tarefa.previsao_execucao.strftime("%d/%m/%Y %H:%M") == "02/01/2030 10:30"
    assert [marcacao.texto for marcacao in tarefa.marcacoes] == ["urgente"]
    # Sem as seções, a Descrição e as tarefas enviadas não são gravadas.
    assert tarefa.secoes_ativas == [] and tarefa.descricao == "" and tarefa.itens == [] and tarefa.video is None
    assert tarefa.eventos[0].tipo == "criou"


def test_generalista_com_todas_as_secoes(app, cliente, criar_projeto, youtube_falso):
    projeto = criar_projeto(cliente.usuario_id)

    criar(cliente, projeto, ["arquivos", "descricao", "tarefas", "video"],
          descricao="<p>Caixas</p>", itens=itens("Embalar", "Etiquetar", concluidos=(0,)),
          anexos=[(BytesIO(b"conteudo"), "lista.pdf")], video_endereco="https://youtu.be/" + CODIGO)

    tarefa = Tarefa.query.one()
    assert tarefa.secoes_ativas == ["arquivos", "descricao", "tarefas", "video"]
    assert tarefa.descricao == "<p>Caixas</p>"
    assert [(item.texto, item.concluido) for item in tarefa.itens] == [("Embalar", True), ("Etiquetar", False)]
    assert [anexo.nome for anexo in tarefa.anexos] == ["lista.pdf"]
    assert (tarefa.video.codigo, tarefa.video.titulo, tarefa.video.publicado_em) == (CODIGO, "Me at the zoo", date(2005, 4, 23))
    assert tarefa.video.endereco == "https://youtu.be/" + CODIGO
    # Todas as tarefas marcadas não concluem o generalista sozinho, como na lista de tarefas.
    assert tarefa.concluida_em is None


def test_cartao_do_quadro_mostra_as_secoes(cliente, criar_projeto, youtube_falso):
    projeto = criar_projeto(cliente.usuario_id)
    criar(cliente, projeto, ["descricao", "tarefas", "video"], descricao="<p>Caixas</p>",
          itens=itens("Embalar", "Etiquetar"), video_endereco=ENDERECO)
    tarefa = Tarefa.query.one()

    html = cliente.get("/").get_data(as_text=True)
    cartao = html.split('data-tarefa-id="{}"'.format(tarefa.id))[1].split("</article>")[0]

    assert "<p>Caixas</p>" in cartao and "Embalar" in cartao and "tarefa-progresso" in cartao
    assert "i.ytimg.com/vi/{}/".format(CODIGO) in cartao
    # O vídeo aparece no formato simplificado: só a miniatura e o título, sem o autor e a duração.
    video = cartao.split('class="tarefa-video-do-cartao"')[1].split("</div>")[0]
    assert '<span class="tarefa-video-do-cartao-titulo">Me at the zoo</span>' in video
    assert "jawed" not in video and "0:19" not in video
    assert """data-secoes='["descricao", "tarefas", "video"]'""" in cartao
    assert 'data-video-endereco="{}"'.format(ENDERECO) in cartao
    # Como a demanda: o responsável, o proprietário e o Concluir.
    assert "tarefa-proprietario" in cartao and "data-escolher-responsavel" in cartao
    assert "/tarefas/{}/concluir".format(tarefa.id) in cartao


def test_retirar_secoes_apaga_o_conteudo_delas(cliente, criar_projeto, youtube_falso):
    projeto = criar_projeto(cliente.usuario_id)
    criar(cliente, projeto, ["descricao", "tarefas", "video"], descricao="<p>Caixas</p>",
          itens=itens("Embalar"), video_endereco=ENDERECO)
    tarefa = Tarefa.query.one()

    editar(cliente, tarefa, ["tarefas"], descricao="<p>Caixas</p>", itens=itens("Embalar"), video_endereco=ENDERECO)

    tarefa = db.session.get(Tarefa, tarefa.id)
    assert tarefa.secoes_ativas == ["tarefas"]
    assert tarefa.descricao == "" and [item.texto for item in tarefa.itens] == ["Embalar"]
    assert tarefa.video is None and VideoDoYoutube.query.count() == 0


def test_acrescentar_secoes_ao_editar(cliente, criar_projeto, youtube_falso):
    projeto = criar_projeto(cliente.usuario_id)
    criar(cliente, projeto)
    tarefa = Tarefa.query.one()

    editar(cliente, tarefa, ["descricao", "video"], descricao="<p>Nova</p>", video_endereco=ENDERECO)

    tarefa = db.session.get(Tarefa, tarefa.id)
    assert tarefa.secoes_ativas == ["descricao", "video"]
    assert tarefa.descricao == "<p>Nova</p>" and tarefa.video.titulo == "Me at the zoo"
    assert tarefa.eventos[0].tipo == "alterou"


def test_mesmo_video_nao_e_buscado_de_novo_ao_salvar(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id), ["video"], video_endereco=ENDERECO)
    tarefa = Tarefa.query.one()
    youtube_falso["pedidos"].clear()

    editar(cliente, tarefa, ["video"], video_endereco=ENDERECO)
    assert youtube_falso["pedidos"] == []

    # Depois do Receber Informações, o servidor busca de novo.
    youtube_falso["titulo"] = "Título novo"
    editar(cliente, tarefa, ["video"], video_endereco=ENDERECO, video_atualizar="1")
    assert youtube_falso["pedidos"] == [CODIGO]
    assert db.session.get(VideoDoYoutube, tarefa.id).titulo == "Título novo"


def test_trocar_o_video_busca_o_novo(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id), ["video"], video_endereco=ENDERECO)
    tarefa = Tarefa.query.one()

    editar(cliente, tarefa, ["video"], video_endereco="https://www.youtube.com/watch?v=" + OUTRO_CODIGO)

    assert db.session.get(VideoDoYoutube, tarefa.id).codigo == OUTRO_CODIGO
    assert VideoDoYoutube.query.count() == 1


def test_secao_video_sem_endereco_nao_grava_video(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id), ["video"], video_endereco="")

    tarefa = Tarefa.query.one()
    assert tarefa.secoes_ativas == ["video"] and tarefa.video is None
    assert youtube_falso["pedidos"] == []


@pytest.mark.parametrize("endereco, erro, mensagem", [
    ("https://exemplo.com/video/1", None, "Informe o endereço de um vídeo do YouTube ou do Vimeo"),
    (ENDERECO, youtube.ErroDeConexao(), "Não foi possível conectar"),
    (ENDERECO, youtube.ErroNasInformacoes(), "Não foi possível buscar as informações do vídeo"),
])
def test_falha_no_video_nao_cria_o_cartao(cliente, criar_projeto, youtube_falso, endereco, erro, mensagem):
    youtube_falso["erro"] = erro

    resposta = criar(cliente, criar_projeto(cliente.usuario_id), ["video"], video_endereco=endereco)

    assert mensagem in resposta.get_data(as_text=True)
    assert Tarefa.query.count() == 0


def test_falha_no_video_nao_altera_o_cartao(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id), ["descricao"], descricao="<p>Antes</p>")
    tarefa = Tarefa.query.one()
    youtube_falso["erro"] = youtube.ErroDeConexao()

    editar(cliente, tarefa, ["video"], nome="Outro nome", video_endereco=ENDERECO)

    tarefa = db.session.get(Tarefa, tarefa.id)
    assert (tarefa.nome, tarefa.descricao, tarefa.secoes_ativas) == ("Mudança", "<p>Antes</p>", ["descricao"])


def test_arquivos_sem_a_secao_nao_sao_gravados(cliente, criar_projeto):
    criar(cliente, criar_projeto(cliente.usuario_id), ["descricao"], anexos=[(BytesIO(b"x"), "a.pdf")])

    assert Tarefa.query.one().anexos == []


def test_secao_arquivos_fica_enquanto_houver_arquivos(cliente, criar_projeto):
    criar(cliente, criar_projeto(cliente.usuario_id), ["arquivos"], anexos=[(BytesIO(b"x"), "a.pdf")])
    tarefa = Tarefa.query.one()

    editar(cliente, tarefa, [])

    tarefa = db.session.get(Tarefa, tarefa.id)
    assert tarefa.secoes_ativas == ["arquivos"] and [anexo.nome for anexo in tarefa.anexos] == ["a.pdf"]


def test_generalista_entra_na_pesquisa_pelo_video_e_pelas_tarefas(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id), ["tarefas", "video"], itens=itens("Etiquetar"), video_endereco=ENDERECO)

    assert "Mudança" in cliente.get("/?busca=zoo").get_data(as_text=True).split("<dialog")[0]
    assert "Mudança" in cliente.get("/?busca=etiquetar").get_data(as_text=True).split("<dialog")[0]


def test_generalista_conta_no_limite_de_demandas(cliente, criar_projeto):
    plano = PlanoDeUsuario(nome="Pequeno", armazenamento_mb=10, atividades=1, padrao=False)
    db.session.add(plano)
    db.session.flush()
    db.session.get(Usuario, cliente.usuario_id).plano_id = plano.id
    db.session.commit()
    projeto = criar_projeto(cliente.usuario_id)
    cliente.post("/tarefas", data={"nome": "Demanda", "projeto_id": projeto.id})

    resposta = criar(cliente, projeto)

    assert "O seu plano permite até 1 demandas." in resposta.get_data(as_text=True)
    assert Tarefa.query.count() == 1


def test_previa_do_video_nao_grava_nada(cliente, youtube_falso):
    resposta = cliente.post("/api/videos/previa", json={"endereco": "https://youtu.be/" + CODIGO})

    assert resposta.status_code == 200
    dados = resposta.get_json()
    assert (dados["titulo"], dados["autor"], dados["publicacao"], dados["duracao"]) == ("Me at the zoo", "jawed", "23/04/2005", "0:19")
    assert dados["player"] == "https://www.youtube-nocookie.com/embed/" + CODIGO
    assert Tarefa.query.count() == 0 and VideoDoYoutube.query.count() == 0


@pytest.mark.parametrize("dados, codigo", [({"endereco": "https://exemplo.com/video/1"}, 400), ({}, 400), ({"endereco": 5}, 400)])
def test_previa_recusa_dados_invalidos(cliente, youtube_falso, dados, codigo):
    assert cliente.post("/api/videos/previa", json=dados).status_code == codigo
    assert youtube_falso["pedidos"] == []


def test_previa_exige_login(app, youtube_falso):
    resposta = app.test_client().post("/api/videos/previa", json={"endereco": ENDERECO})

    assert resposta.status_code in (302, 401)
    assert youtube_falso["pedidos"] == []


def test_outro_usuario_nao_edita_o_generalista(cliente, outro_cliente, criar_projeto):
    criar(cliente, criar_projeto(cliente.usuario_id), ["descricao"], descricao="<p>Minha</p>")
    tarefa = Tarefa.query.one()

    resposta = outro_cliente.post("/tarefas/{}/editar".format(tarefa.id),
                                  data={"nome": "Invasão", "projeto_id": tarefa.projeto_id, "secoes": "[]"})

    assert resposta.status_code == 404
    assert db.session.get(Tarefa, tarefa.id).descricao == "<p>Minha</p>"


def test_membro_com_editar_altera_as_secoes(cliente, outro_cliente, youtube_falso):
    grupo = GrupoDeUsuarios(nome="Turma", administrador_id=cliente.usuario_id)
    grupo.membros.extend([db.session.get(Usuario, cliente.usuario_id), db.session.get(Usuario, outro_cliente.usuario_id)])
    casa = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add_all([grupo, casa])
    db.session.flush()
    projeto = Projeto(nome="Reforma", usuario_id=cliente.usuario_id, categoria_id=casa.id)
    db.session.add(projeto)
    db.session.add(CompartilhamentoDeCategoria(categoria_id=casa.id, grupo_id=grupo.id, permissao="editar"))
    db.session.commit()
    criar(cliente, projeto)
    tarefa = Tarefa.query.one()

    editar(outro_cliente, tarefa, ["video"], video_endereco=ENDERECO, categoria=casa.id)

    assert db.session.get(Tarefa, tarefa.id).video.codigo == CODIGO


@pytest.mark.so_sqlite
def test_atualizar_banco_cria_a_coluna_das_secoes(app):
    with db.engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE tarefa DROP COLUMN secoes"))

    atualizar_banco()

    assert "secoes" in {coluna["name"] for coluna in inspect(db.engine).get_columns("tarefa")}


def test_versao_do_quadro_muda_com_as_secoes(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    criar(cliente, projeto, ["tarefas"])
    tarefa = Tarefa.query.one()
    antes = cliente.get("/api/quadro/versao").get_json()["versao"]

    editar(cliente, tarefa, ["tarefas", "video"])

    assert cliente.get("/api/quadro/versao").get_json()["versao"] != antes


def test_dialogo_tem_as_abas_da_coluna_direita(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    dialogo = html.split('id="dialogo-tarefa"')[1].split("</dialog>")[0]
    abas = dialogo.split("data-abas-da-tarefa")[1].split("</div>")[0]

    assert 'role="tablist"' in dialogo.split("data-abas-da-tarefa")[0].rsplit("<div", 1)[1]
    for secao, rotulo in (("descricao", "Descrição"), ("tarefas", "Tarefas"), ("video", "Vídeo")):
        assert 'id="aba-{0}" aria-controls="painel-{0}"'.format(secao) in abas
        assert 'data-aba="{}" hidden>{}</button>'.format(secao, rotulo) in abas
        assert 'id="painel-{0}" data-secao="{0}"'.format(secao) in dialogo
    # As abas ficam no topo da coluna direita, antes das seções.
    direita = dialogo.split('class="tarefa-coluna-direita"')[1]
    assert direita.index("data-abas-da-tarefa") < direita.index('data-secao="descricao"')


def test_app_mostra_uma_secao_por_aba_so_no_generalista():
    from pathlib import Path

    codigo = (Path(__file__).resolve().parent.parent / "static/js/app.js").read_text(encoding="utf-8")
    funcao = codigo.split("function atualizarAbas(dialogo, generalista)")[1].split("\n  }\n")[0]

    assert 'const SECOES_EM_ABAS = ["descricao", "tarefas", "video"];' in codigo
    assert "const comAbas = generalista && emAbas.length > 0;" in funcao
    assert 'painel.hidden = painel.hidden || secao !== abaDoDialogo;' in funcao
    # Acrescentar uma seção abre a aba dela, e as setas trocam de aba.
    assert "abaDoDialogo = secao;" in codigo.split("function acrescentarSecao")[1].split("\n  }\n")[0]
    assert "ArrowRight" in codigo and "ArrowLeft" in codigo


def test_interface_diz_cartao_de_contexto_e_nao_generalista(cliente, criar_projeto):
    """O tipo continua "generalista" no código e no banco; na interface, é o cartão de contexto."""
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    sem_comentarios = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    textos = re.sub(r"<[^>]*>", " ", sem_comentarios)
    atributos = re.findall(r'(?:data-dica[\w-]*|aria-label|title|alt|placeholder)="([^"]*)"', sem_comentarios)
    javascript = Path("static/js/app.js").read_text(encoding="utf-8")

    assert ">Cartão - Contexto</button>" in html
    assert not re.search(r"generalista", textos + " ".join(atributos), re.I)
    # Textos do JavaScript (os que têm espaço); "generalista" e "tarefa-generalista" são nomes internos.
    frases = [texto for texto in re.findall(r'"([^"\n]*)"', javascript) if " " in texto]
    assert not [frase for frase in frases if re.search(r"generalista", frase, re.I)]
    assert '"Editar cartão de contexto"' in javascript


def test_receber_pelo_oembed_mantem_a_descricao_do_mesmo_video(cliente, criar_projeto, youtube_falso, monkeypatch):
    criar(cliente, criar_projeto(cliente.usuario_id), ["video"], video_endereco=ENDERECO)
    tarefa = Tarefa.query.one()
    youtube_falso["erro"] = youtube.ErroDeConexao()
    monkeypatch.setattr(youtube, "baixar_oembed", lambda codigo: {"title": "Pelo oEmbed", "author_name": "jawed"})

    editar(cliente, tarefa, ["video"], video_endereco=ENDERECO, video_atualizar="1")

    video = db.session.get(VideoDoYoutube, tarefa.id)
    assert (video.titulo, video.descricao, video.duracao) == ("Pelo oEmbed", "Elefantes", "0:19")


def test_outro_video_pelo_oembed_fica_sem_a_descricao_antiga(cliente, criar_projeto, youtube_falso, monkeypatch):
    criar(cliente, criar_projeto(cliente.usuario_id), ["video"], video_endereco=ENDERECO)
    tarefa = Tarefa.query.one()
    youtube_falso["erro"] = youtube.ErroDeConexao()
    monkeypatch.setattr(youtube, "baixar_oembed", lambda codigo: {"title": "Outro", "author_name": "alguém"})

    editar(cliente, tarefa, ["video"], video_endereco="https://www.youtube.com/watch?v=" + OUTRO_CODIGO)

    video = db.session.get(VideoDoYoutube, tarefa.id)
    assert (video.codigo, video.titulo, video.descricao, video.duracao) == (OUTRO_CODIGO, "Outro", "", "")
