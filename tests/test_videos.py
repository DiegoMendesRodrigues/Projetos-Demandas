# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import json
from datetime import date
from pathlib import Path

import pytest

import youtube
from extensions import db
from models import (
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    Projeto,
    Tarefa,
    Usuario,
    VideoDoYoutube,
)

CODIGO = "jNQXAC9IVRw"
# A função real, guardada antes de o conftest.py trocá-la em cada teste.
BAIXAR_OEMBED = youtube.baixar_oembed
ENDERECO = "https://www.youtube.com/watch?v=" + CODIGO


def pagina(codigo=CODIGO, **detalhes):
    dados = {"videoId": codigo, "title": "Me at the zoo", "author": "jawed",
             "shortDescription": "Elefantes; muito longos", "lengthSeconds": "19"}
    dados.update(detalhes)
    return '<html><script>var ytInitialPlayerResponse = {};var meta = 1;</script></html>'.format(
        json.dumps({"videoDetails": dados})
    )


@pytest.fixture
def youtube_falso(monkeypatch):
    """Substitui o acesso à internet: guarda os códigos pedidos e devolve a página definida."""
    estado = {"pagina": pagina(), "pedidos": [], "erro": None}

    def baixar(codigo):
        estado["pedidos"].append(codigo)
        if estado["erro"]:
            raise estado["erro"]
        return estado["pagina"]

    monkeypatch.setattr(youtube, "baixar_pagina", baixar)
    return estado


def criar(cliente, projeto, endereco=ENDERECO):
    return cliente.post("/api/videos", json={"projeto_id": projeto.id, "endereco": endereco})


@pytest.mark.parametrize("endereco", [
    ENDERECO,
    "youtube.com/watch?v={}&t=10s".format(CODIGO),
    "https://youtu.be/{}?si=abc".format(CODIGO),
    "https://m.youtube.com/watch?feature=share&v={}".format(CODIGO),
    "https://www.youtube.com/shorts/{}".format(CODIGO),
    "https://www.youtube.com/embed/{}".format(CODIGO),
    "https://www.youtube-nocookie.com/embed/{}".format(CODIGO),
])
def test_reconhece_os_enderecos_do_youtube(endereco):
    assert youtube.codigo_do_video(endereco) == CODIGO


@pytest.mark.parametrize("endereco", [
    "", "https://vimeo.com/123456", "https://www.youtube.com/watch?v=curto",
    "https://evil.com/watch?v={}".format(CODIGO), "ftp://youtu.be/{}".format(CODIGO),
    "https://www.youtube.com/watch?v={}&x={}".format(CODIGO, "a" * 400),
])
def test_recusa_enderecos_que_nao_sao_videos_do_youtube(endereco):
    with pytest.raises(youtube.EnderecoInvalido):
        youtube.codigo_do_video(endereco)


@pytest.mark.parametrize("segundos, texto", [(19, "0:19"), (754, "12:34"), (3725, "1:02:05")])
def test_formata_a_duracao(segundos, texto):
    assert youtube.formatar_duracao(segundos) == texto


def test_le_as_informacoes_da_pagina():
    informacoes = youtube.informacoes_da_pagina(pagina(), CODIGO)

    assert informacoes == {"codigo": CODIGO, "autor": "jawed", "titulo": "Me at the zoo",
                           "descricao": "Elefantes; muito longos", "publicacao": None, "duracao": "0:19"}


@pytest.mark.parametrize("formato, data", [
    ({"publishDate": "2005-04-23"}, date(2005, 4, 23)),
    # 23h30 em Brasília, já 24/04 no horário de Greenwich: vale a data de São Paulo.
    ({"publishDate": "2005-04-24T02:30:00+00:00"}, date(2005, 4, 23)),
    ({"uploadDate": "2005-04-23T20:31:52-07:00"}, date(2005, 4, 24)),
    ({"publishDate": "data inválida"}, None),
    ({}, None),
])
def test_le_a_data_de_publicacao(formato, data):
    conteudo = pagina_com_publicacao(formato)

    assert youtube.informacoes_da_pagina(conteudo, CODIGO)["publicacao"] == data


def pagina_com_publicacao(formato):
    dados = {"videoDetails": {"videoId": CODIGO, "title": "Me at the zoo"},
             "microformat": {"playerMicroformatRenderer": formato}}
    return "<script>var ytInitialPlayerResponse = {};</script>".format(json.dumps(dados))


def test_receber_informacoes_grava_e_devolve_a_data_de_publicacao(cliente, criar_projeto, youtube_falso):
    youtube_falso["pagina"] = pagina_com_publicacao({"publishDate": "2005-04-23"})

    resposta = criar(cliente, criar_projeto(cliente.usuario_id))

    assert resposta.get_json()["publicacao"] == "23/04/2005"
    tarefa = Tarefa.query.one()
    assert tarefa.video.publicado_em == date(2005, 4, 23)
    html = cliente.get("/?tarefa={}".format(tarefa.id)).get_data(as_text=True)
    assert 'data-video-publicacao="23/04/2005"' in html.split("data-abrir-tarefa")[1].split(">")[0]


def test_data_de_publicacao_vem_antes_da_duracao_nas_caixas_do_video(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    novo = html.split('id="dialogo-video-novo"')[1].split("</dialog>")[0]
    edicao = html.split('id="dialogo-video"')[1].split("</dialog>")[0]

    assert novo.index(">Data de publicação</label>") < novo.index(">Duração</label>")
    assert 'data-video-campo="publicacao"' in novo
    assert edicao.index('id="video-publicacao"') < edicao.index('id="video-duracao"')


def test_video_sem_data_de_publicacao_fica_em_branco(cliente, criar_projeto, youtube_falso):
    resposta = criar(cliente, criar_projeto(cliente.usuario_id))

    assert resposta.get_json()["publicacao"] == ""
    assert Tarefa.query.one().video.publicado_em is None


def test_corta_os_textos_nos_limites_dos_campos():
    informacoes = youtube.informacoes_da_pagina(pagina(title="T" * 300, author="A" * 150), CODIGO)

    assert len(informacoes["titulo"]) == 200 and len(informacoes["autor"]) == 100


@pytest.mark.parametrize("conteudo", ["<html>sem dados</html>", pagina(codigo="outrovideo1"), pagina(title=""),
                                      "ytInitialPlayerResponse = {quebrado"])
def test_pagina_sem_as_informacoes_gera_erro(conteudo):
    with pytest.raises(youtube.ErroNasInformacoes):
        youtube.informacoes_da_pagina(conteudo, CODIGO)


def test_menu_do_mais_oferece_criar_um_novo_video(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    menu = html.split('id="menu-criar-{}"'.format(projeto.id))[1].split("</div>")[0]

    assert 'data-novo-video data-projeto-id="{}">Cartão - Vídeo</button>'.format(projeto.id) in menu
    assert "Novo vídeo do YouTube ou do Vimeo" in html and "Receber Informações" in html
    assert 'id="video-novo-endereco" required maxlength="400"' in html


def test_receber_informacoes_grava_o_video(cliente, criar_projeto, youtube_falso):
    projeto = criar_projeto(cliente.usuario_id)

    resposta = criar(cliente, projeto, "https://youtu.be/{}?t=3".format(CODIGO))

    assert resposta.status_code == 201
    assert resposta.get_json()["titulo"] == "Me at the zoo"
    tarefa = Tarefa.query.one()
    assert (tarefa.tipo, tarefa.nome, tarefa.projeto_id) == ("video", "Me at the zoo", projeto.id)
    assert (tarefa.video.autor, tarefa.video.duracao, tarefa.video.codigo) == ("jawed", "0:19", CODIGO)
    assert tarefa.video.endereco == "https://youtu.be/{}?t=3".format(CODIGO)
    # O servidor busca o endereço oficial, nunca o texto digitado.
    assert youtube_falso["pedidos"] == [CODIGO]


def test_endereco_invalido_nao_acessa_a_internet(cliente, criar_projeto, youtube_falso):
    resposta = criar(cliente, criar_projeto(cliente.usuario_id), "http://127.0.0.1:8010/administracao")

    assert resposta.status_code == 400
    assert "endereço de um vídeo do YouTube ou do Vimeo" in resposta.get_json()["erro"]
    assert youtube_falso["pedidos"] == [] and Tarefa.query.count() == 0


def test_falha_de_conexao_e_informada(cliente, criar_projeto, youtube_falso):
    youtube_falso["erro"] = youtube.ErroDeConexao()

    resposta = criar(cliente, criar_projeto(cliente.usuario_id))

    assert resposta.status_code == 502
    assert "Não foi possível conectar ao endereço informado" in resposta.get_json()["erro"]
    assert Tarefa.query.count() == 0


def test_falha_ao_buscar_as_informacoes_e_informada(cliente, criar_projeto, youtube_falso):
    youtube_falso["pagina"] = "<html>o vídeo não está disponível</html>"

    resposta = criar(cliente, criar_projeto(cliente.usuario_id))

    assert resposta.status_code == 422
    assert "Não foi possível buscar as informações do vídeo" in resposta.get_json()["erro"]
    assert Tarefa.query.count() == 0


def test_baixar_pagina_converte_erros_de_rede(monkeypatch):
    def recusar(*args, **kwargs):
        raise OSError("sem rede")

    monkeypatch.setattr(youtube.urllib.request, "urlopen", recusar)

    with pytest.raises(youtube.ErroDeConexao):
        youtube.baixar_pagina(CODIGO)


def test_dados_invalidos_sao_recusados(cliente, youtube_falso):
    assert cliente.post("/api/videos", json={"projeto_id": "1", "endereco": ENDERECO}).status_code == 400
    assert cliente.post("/api/videos", data="texto").status_code == 400


def test_nao_cria_video_no_projeto_de_outro_usuario(cliente, outro_cliente, criar_projeto, youtube_falso):
    projeto = criar_projeto(outro_cliente.usuario_id)

    assert criar(cliente, projeto).status_code == 404
    assert youtube_falso["pedidos"] == []


def test_cartao_mostra_miniatura_titulo_autor_duracao_excluir_e_ocultar(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()

    html = cliente.get("/").get_data(as_text=True)
    cartao = html.split('<article class="tarefa tarefa-video')[1].split("</article>")[0]

    assert 'src="https://i.ytimg.com/vi/{}/mqdefault.jpg"'.format(CODIGO) in cartao
    assert ">Me at the zoo</button>" in cartao and "jawed · 0:19" in cartao
    assert 'data-url-excluir="/tarefas/{}/excluir"'.format(tarefa.id) in cartao
    assert "Ocultar o vídeo" in cartao and "Excluir vídeo" in cartao
    assert "botao-concluir" not in cartao
    assert 'data-url="/videos/{}/editar"'.format(tarefa.id) in cartao
    assert 'data-video-player="https://www.youtube-nocookie.com/embed/{}"'.format(CODIGO) in cartao


def test_quadro_abre_a_edicao_do_video_criado(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()

    html = cliente.get("/?tarefa={}".format(tarefa.id)).get_data(as_text=True)

    abrir = html.split("data-abrir-tarefa")[1].split(">")[0]
    assert 'data-tipo="video"' in abrir and 'data-video-autor="jawed"' in abrir
    assert "Editar vídeo" in html and 'id="video-informacoes" name="informacoes_adicionais"' in html


def test_salvar_grava_so_as_informacoes_adicionais(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()

    resposta = cliente.post(
        "/videos/{}/editar".format(tarefa.id),
        data={"informacoes_adicionais": "  Rever na aula de sexta  ", "titulo": "Outro", "autor": "Outro"},
    )

    assert resposta.status_code == 302
    db.session.expire_all()
    video = db.session.get(VideoDoYoutube, tarefa.id)
    assert video.informacoes_adicionais == "Rever na aula de sexta"
    assert (video.titulo, video.autor) == ("Me at the zoo", "jawed")


def test_formulario_da_atividade_nao_altera_o_video(cliente, criar_projeto, youtube_falso):
    projeto = criar_projeto(cliente.usuario_id)
    criar(cliente, projeto)
    tarefa = Tarefa.query.one()

    resposta = cliente.post("/tarefas/{}/editar".format(tarefa.id), data={
        "nome": "Trocado", "prioridade": "baixa", "projeto_id": projeto.id, "tipo": "atividade"})

    assert resposta.status_code == 404
    assert db.session.get(Tarefa, tarefa.id).nome == "Me at the zoo"


def test_formulario_da_atividade_nao_cria_video_sem_o_youtube(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    cliente.post("/tarefas", data={"nome": "Falso", "prioridade": "baixa", "projeto_id": projeto.id, "tipo": "video"})

    assert Tarefa.query.filter_by(tipo="video").count() == 0


def test_ocultar_e_excluir_o_video(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()

    cliente.post("/tarefas/{}/ocultar".format(tarefa.id))
    assert db.session.get(Tarefa, tarefa.id).oculta is True
    assert "Me at the zoo" not in cliente.get("/").get_data(as_text=True).split("<dialog")[0]

    cliente.post("/tarefas/{}/excluir".format(tarefa.id))
    assert Tarefa.query.count() == 0 and VideoDoYoutube.query.count() == 0


def test_outro_usuario_nao_salva_o_video(cliente, outro_cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()

    resposta = outro_cliente.post("/videos/{}/editar".format(tarefa.id), data={"informacoes_adicionais": "x"})

    assert resposta.status_code == 404


@pytest.fixture
def compartilhado(cliente, outro_cliente, youtube_falso):
    """Ana compartilha a categoria Estudos, que tem um vídeo, com o grupo em que Bruno está."""
    grupo = GrupoDeUsuarios(nome="Turma", administrador_id=cliente.usuario_id)
    grupo.membros.extend([db.session.get(Usuario, cliente.usuario_id), db.session.get(Usuario, outro_cliente.usuario_id)])
    estudos = Categoria(nome="Estudos", usuario_id=cliente.usuario_id)
    db.session.add_all([grupo, estudos])
    db.session.flush()
    aulas = Projeto(nome="Aulas", usuario_id=cliente.usuario_id, categoria_id=estudos.id)
    db.session.add(aulas)
    db.session.commit()
    criar(cliente, aulas)

    def compartilhar(permissao):
        db.session.add(CompartilhamentoDeCategoria(categoria_id=estudos.id, grupo_id=grupo.id, permissao=permissao))
        db.session.commit()

    return {"projeto": aulas, "categoria": estudos, "video": Tarefa.query.one(), "compartilhar": compartilhar}


def test_visualizar_mostra_o_video_mas_nao_altera(outro_cliente, compartilhado):
    compartilhado["compartilhar"]("visualizar")
    video = compartilhado["video"]

    html = outro_cliente.get("/?categoria={}".format(compartilhado["categoria"].id)).get_data(as_text=True)
    assert "Me at the zoo" in html and "data-novo-video" not in html
    assert outro_cliente.post("/videos/{}/editar".format(video.id), data={"informacoes_adicionais": "x"}).status_code == 404
    assert outro_cliente.post("/tarefas/{}/ocultar".format(video.id)).status_code == 404
    assert criar(outro_cliente, compartilhado["projeto"]).status_code == 404


def test_editar_cria_salva_e_oculta_mas_nao_exclui(outro_cliente, compartilhado):
    compartilhado["compartilhar"]("editar")
    video = compartilhado["video"]

    html = outro_cliente.get("/?categoria={}".format(compartilhado["categoria"].id)).get_data(as_text=True)
    assert "data-novo-video" in html and "Excluir vídeo" not in html.split("<dialog")[0]
    assert outro_cliente.post("/videos/{}/editar".format(video.id), data={"informacoes_adicionais": "Visto"}).status_code == 302
    assert outro_cliente.post("/tarefas/{}/ocultar".format(video.id)).status_code == 302
    assert outro_cliente.post("/tarefas/{}/excluir".format(video.id)).status_code == 404
    assert criar(outro_cliente, compartilhado["projeto"]).status_code == 201

    db.session.expire_all()
    assert db.session.get(VideoDoYoutube, video.id).informacoes_adicionais == "Visto"
    assert all(t.projeto.usuario_id == compartilhado["projeto"].usuario_id for t in Tarefa.query)


def test_membro_abre_o_video_pela_categoria_compartilhada(outro_cliente, compartilhado):
    compartilhado["compartilhar"]("visualizar")
    video = compartilhado["video"]

    url = "/?categoria={}&tarefa={}".format(compartilhado["categoria"].id, video.id)
    assert 'data-abrir-tarefa' in outro_cliente.get(url).get_data(as_text=True)
    # Sem a categoria, a atividade de outro usuário não é aberta.
    assert outro_cliente.get("/?tarefa={}".format(video.id)).status_code == 404


def test_descricao_do_video_e_um_bloco_que_aceita_links(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    caixa = html.split('id="dialogo-video"')[1].split("</dialog>")[0]

    assert '<div class="video-descricao" id="video-descricao"' in caixa
    assert 'textarea id="video-descricao"' not in caixa
    # O texto entra como texto: o JavaScript cria os links, sem interpretar HTML da descrição.
    javascript = open("static/js/app.js", encoding="utf-8").read()
    corpo = javascript.split("function preencherComLinks")[1].split("\n  }\n")[0]
    assert "innerHTML" not in corpo and "textContent" in corpo


def test_simplificar_o_video_alterna_o_cartao(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()
    pagina = cliente.get("/").get_data(as_text=True)
    assert 'data-dica="Simplificar o vídeo"' in pagina
    assert "video-simplificado" not in pagina.split("<dialog")[0]

    cliente.post("/tarefas/{}/simplificar".format(tarefa.id))
    assert db.session.get(VideoDoYoutube, tarefa.id).simplificado is True
    pagina = cliente.get("/").get_data(as_text=True)
    assert "video-simplificado" in pagina
    assert 'data-dica="Exibir o vídeo completo"' in pagina

    cliente.post("/tarefas/{}/simplificar".format(tarefa.id))
    assert db.session.get(VideoDoYoutube, tarefa.id).simplificado is False


def test_simplificar_so_existe_nos_videos(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = Tarefa(nome="Comum", projeto_id=projeto.id)
    db.session.add(tarefa)
    db.session.commit()
    assert "Simplificar o vídeo" not in cliente.get("/").get_data(as_text=True)
    assert cliente.post("/tarefas/{}/simplificar".format(tarefa.id)).status_code == 404


def test_outro_usuario_nao_simplifica_o_video(cliente, outro_cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()
    assert outro_cliente.post("/tarefas/{}/simplificar".format(tarefa.id)).status_code == 404


def atualizar(cliente, tarefa):
    return cliente.post("/api/videos/{}/atualizar".format(tarefa.id))


def test_botao_atualizar_as_informacoes_fica_a_esquerda_do_cancelar(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    acoes = html.split('id="dialogo-video"')[1].split("</dialog>")[0].split('class="dialogo-acoes"')[1]

    atualizar_botao = acoes.index('data-atualizar-video>Atualizar as informações</button>')
    assert acoes.index("data-abrir-historico") < atualizar_botao < acoes.index(">Cancelar</button>") < acoes.index(">Salvar</button>")


def test_atualizar_busca_de_novo_no_youtube(cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()
    tarefa.video.informacoes_adicionais = "Minhas notas"
    db.session.commit()
    youtube_falso["pedidos"].clear()
    dados = {"videoDetails": {"videoId": CODIGO, "title": "Novo título", "author": "outro",
                              "shortDescription": "Nova descrição", "lengthSeconds": "754"},
             "microformat": {"playerMicroformatRenderer": {"publishDate": "2005-04-23"}}}
    youtube_falso["pagina"] = "<script>var ytInitialPlayerResponse = {};</script>".format(json.dumps(dados))

    resposta = atualizar(cliente, tarefa)

    assert resposta.status_code == 200
    assert resposta.get_json() == {"autor": "outro", "titulo": "Novo título", "descricao": "Nova descrição",
                                   "duracao": "12:34", "publicacao": "23/04/2005"}
    video = db.session.get(VideoDoYoutube, tarefa.id)
    assert (video.autor, video.titulo, video.descricao, video.duracao) == ("outro", "Novo título", "Nova descrição", "12:34")
    assert video.publicado_em == date(2005, 4, 23) and video.informacoes_adicionais == "Minhas notas"
    assert db.session.get(Tarefa, tarefa.id).nome == "Novo título"
    assert youtube_falso["pedidos"] == [CODIGO]
    assert db.session.get(Tarefa, tarefa.id).eventos[0].tipo == "atualizou_video"
    html = cliente.get("/?tarefa={}".format(tarefa.id)).get_data(as_text=True)
    assert 'data-video-url-atualizar="/api/videos/{}/atualizar"'.format(tarefa.id) in html


@pytest.mark.parametrize("erro, codigo", [(youtube.ErroDeConexao(), 502), (youtube.ErroNasInformacoes(), 422)])
def test_falha_ao_atualizar_mantem_os_dados(cliente, criar_projeto, youtube_falso, erro, codigo):
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()
    youtube_falso["erro"] = erro

    resposta = atualizar(cliente, tarefa)

    assert resposta.status_code == codigo and resposta.get_json()["erro"]
    assert db.session.get(VideoDoYoutube, tarefa.id).titulo == "Me at the zoo"


def test_atualizar_so_existe_nos_videos(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = Tarefa(nome="Comum", projeto_id=projeto.id)
    db.session.add(tarefa)
    db.session.commit()

    assert atualizar(cliente, tarefa).status_code == 404


def test_outro_usuario_nao_atualiza_o_video(cliente, outro_cliente, criar_projeto, youtube_falso):
    criar(cliente, criar_projeto(cliente.usuario_id))

    assert atualizar(outro_cliente, Tarefa.query.one()).status_code == 404


def test_quem_so_visualiza_nao_atualiza_o_video(outro_cliente, compartilhado):
    compartilhado["compartilhar"]("visualizar")

    assert atualizar(outro_cliente, compartilhado["video"]).status_code == 404


def test_quem_edita_a_categoria_atualiza_o_video(outro_cliente, compartilhado):
    compartilhado["compartilhar"]("editar")

    assert atualizar(outro_cliente, compartilhado["video"]).status_code == 200


def test_dica_do_simplificar_fica_acima_do_botao():
    css = Path("static/css/style.css").read_text(encoding="utf-8")
    regra = css.split(".botao-simplificar[data-dica]::after {")[1].split("}")[0]

    assert "top: auto;" in regra and "bottom: calc(100% + 6px);" in regra


# ---------- Reserva pelo oEmbed (servidores em que o YouTube pede a verificação de robô)

PAGINA_DE_ROBO = '<html><script>var ytInitialPlayerResponse = {};</script></html>'.format(json.dumps({
    "playabilityStatus": {"status": "LOGIN_REQUIRED", "reason": "Faça login para confirmar que você não é um robô"},
}))
OEMBED = {"title": "Me at the zoo", "author_name": "jawed", "type": "video"}


@pytest.fixture
def oembed_falso(monkeypatch):
    estado = {"dados": dict(OEMBED), "pedidos": [], "erro": None}

    def baixar(codigo):
        estado["pedidos"].append(codigo)
        if estado["erro"]:
            raise estado["erro"]
        return estado["dados"]

    monkeypatch.setattr(youtube, "baixar_oembed", baixar)
    return estado


def test_verificacao_de_robo_usa_o_titulo_e_o_autor_do_oembed(youtube_falso, oembed_falso, caplog):
    youtube_falso["pagina"] = PAGINA_DE_ROBO

    dados = youtube.informacoes_do_codigo(CODIGO)

    assert dados == {"codigo": CODIGO, "autor": "jawed", "titulo": "Me at the zoo", "descricao": "",
                     "publicacao": None, "duracao": "", "parcial": True}
    assert oembed_falso["pedidos"] == [CODIGO]
    assert "LOGIN_REQUIRED" in caplog.text and "oEmbed" in caplog.text


def test_falha_de_conexao_na_pagina_tambem_tenta_o_oembed(youtube_falso, oembed_falso):
    youtube_falso["erro"] = youtube.ErroDeConexao()

    assert youtube.informacoes_do_codigo(CODIGO)["titulo"] == "Me at the zoo"


def test_sem_conexao_nas_duas_continua_falha_de_conexao(youtube_falso, oembed_falso):
    youtube_falso["erro"] = youtube.ErroDeConexao()
    oembed_falso["erro"] = youtube.ErroDeConexao()

    with pytest.raises(youtube.ErroDeConexao):
        youtube.informacoes_do_codigo(CODIGO)


def test_pagina_completa_nao_usa_o_oembed(youtube_falso, oembed_falso):
    assert youtube.informacoes_do_codigo(CODIGO)["duracao"] == "0:19"
    assert oembed_falso["pedidos"] == []


@pytest.mark.parametrize("erro", [youtube.ErroNasInformacoes("oEmbed respondeu 404"), youtube.ErroDeConexao()])
def test_sem_a_pagina_e_sem_o_oembed_vale_o_erro_da_pagina(youtube_falso, oembed_falso, erro, caplog):
    youtube_falso["pagina"] = PAGINA_DE_ROBO
    oembed_falso["erro"] = erro

    with pytest.raises(youtube.ErroNasInformacoes):
        youtube.informacoes_do_codigo(CODIGO)
    assert "sem as informações do vídeo {}".format(CODIGO) in caplog.text
    assert "LOGIN_REQUIRED" in caplog.text


def test_oembed_sem_titulo_e_recusado(youtube_falso, oembed_falso):
    youtube_falso["pagina"] = PAGINA_DE_ROBO
    oembed_falso["dados"] = {"author_name": "jawed"}

    with pytest.raises(youtube.ErroNasInformacoes):
        youtube.informacoes_do_codigo(CODIGO)


def test_criar_video_pelo_oembed_no_servidor_bloqueado(cliente, criar_projeto, youtube_falso, oembed_falso):
    projeto = criar_projeto(cliente.usuario_id)
    youtube_falso["pagina"] = PAGINA_DE_ROBO

    resposta = criar(cliente, projeto)

    assert resposta.status_code == 201, resposta.get_data(as_text=True)
    video = VideoDoYoutube.query.one()
    assert (video.titulo, video.autor, video.duracao, video.descricao) == ("Me at the zoo", "jawed", "", "")


def test_baixar_oembed_monta_o_endereco_so_com_o_codigo(monkeypatch):
    pedidos = []

    class Resposta:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, _tamanho):
            return json.dumps(OEMBED).encode()

    def abrir(requisicao, timeout):
        pedidos.append(requisicao.full_url)
        return Resposta()

    monkeypatch.setattr(youtube.urllib.request, "urlopen", abrir)

    assert BAIXAR_OEMBED(CODIGO) == OEMBED
    assert pedidos == ["https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D{}&format=json".format(CODIGO)]


@pytest.mark.parametrize("codigo_http", [401, 403, 404])
def test_baixar_oembed_converte_os_erros_http(monkeypatch, codigo_http):
    import urllib.error

    def recusar(requisicao, timeout):
        raise urllib.error.HTTPError(requisicao.full_url, codigo_http, "erro", {}, None)

    monkeypatch.setattr(youtube.urllib.request, "urlopen", recusar)
    with pytest.raises(youtube.ErroNasInformacoes):
        BAIXAR_OEMBED(CODIGO)


def test_baixar_oembed_converte_os_erros_de_rede(monkeypatch):
    def recusar(requisicao, timeout):
        raise OSError("sem rede")

    monkeypatch.setattr(youtube.urllib.request, "urlopen", recusar)
    with pytest.raises(youtube.ErroDeConexao):
        BAIXAR_OEMBED(CODIGO)


def test_atualizar_pelo_oembed_mantem_a_descricao_a_data_e_a_duracao(cliente, criar_projeto, youtube_falso, oembed_falso):
    youtube_falso["pagina"] = pagina(**{"lengthSeconds": "754"}).replace(
        '"videoDetails"', '"microformat": {"playerMicroformatRenderer": {"publishDate": "2005-04-23"}}, "videoDetails"'
    )
    criar(cliente, criar_projeto(cliente.usuario_id))
    tarefa = Tarefa.query.one()
    youtube_falso["pagina"] = PAGINA_DE_ROBO
    oembed_falso["dados"] = {"title": "Título do oEmbed", "author_name": "outro"}

    resposta = atualizar(cliente, tarefa)

    assert resposta.status_code == 200
    assert resposta.get_json() == {"autor": "outro", "titulo": "Título do oEmbed", "descricao": "Elefantes; muito longos",
                                   "duracao": "12:34", "publicacao": "23/04/2005"}
    video = db.session.get(VideoDoYoutube, tarefa.id)
    assert (video.titulo, video.descricao, video.duracao, video.publicado_em) == (
        "Título do oEmbed", "Elefantes; muito longos", "12:34", date(2005, 4, 23))
