# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import io
import re

import pytest
from flask import get_template_attribute
from sqlalchemy import text

from app import atualizar_banco
from extensions import db
from forms import limpar_descricao
from models import Imagem, Tarefa

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 20
ASSINATURAS = [
    (PNG, "image/png"),
    (b"\xff\xd8\xff\xe0" + b"\0" * 20, "image/jpeg"),
    (b"GIF89a" + b"\0" * 20, "image/gif"),
    (b"RIFF\0\0\0\0WEBP" + b"\0" * 20, "image/webp"),
]
BOTOES = [
    "Negrito",
    "Itálico",
    "Sublinhado",
    "Aumentar o tamanho da fonte",
    "Diminuir o tamanho da fonte",
    "Lista",
    "Lista numerada",
    "Aumentar o recuo",
    "Diminuir o recuo",
    "Inserir imagem",
    "Inserir link",
    "Alterar a cor da fonte",
]


def enviar_imagem(cliente, conteudo=PNG):
    return cliente.post(
        "/api/imagens",
        data={"imagem": (io.BytesIO(conteudo), "foto.png")},
        content_type="multipart/form-data",
    )


def url_de_imagem_enviada(cliente):
    return enviar_imagem(cliente).get_json()["url"]


def salvar_tarefa(cliente, projeto, descricao):
    cliente.post(
        "/tarefas",
        data={"nome": "Com texto", "projeto_id": projeto.id, "descricao": descricao},
    )
    return Tarefa.query.filter_by(nome="Com texto").one()


def arquivos(app):
    return list(app.config["ANEXOS_DIR"].iterdir())


@pytest.mark.parametrize(
    "html",
    [
        "<b>a</b><i>b</i><u>c</u>",
        '<font color="#d32f2f" size="5">a</font>',
        "<ul><li>a</li></ul><ol><li>b</li></ol>",
        "<blockquote>recuo</blockquote>",
        "<div>linha<br>outra</div>",
    ],
)
def test_limpar_descricao_mantem_a_formatacao_do_editor(html):
    assert limpar_descricao(html) == html


@pytest.mark.parametrize(
    "perigoso",
    [
        "<script>alert(1)</script>",
        '<b onclick="alert(1)">x</b>',
        '<img src="/imagens/{}" onerror="alert(1)">'.format("a" * 32),
        '<a href="javascript:alert(1)">x</a>',
        '<iframe src="https://exemplo.com"></iframe>',
        '<font color="red;background:url(x)">x</font>',
        '<div style="position:fixed">x</div>',
    ],
)
def test_limpar_descricao_remove_conteudo_perigoso(perigoso):
    limpo = limpar_descricao(perigoso)

    for trecho in ("script", "onclick", "onerror", "javascript", "iframe", "style", "url("):
        assert trecho not in limpo


def test_limpar_descricao_abre_link_em_nova_aba_com_seguranca():
    limpo = limpar_descricao('<a href="https://exemplo.com">site</a>')

    assert 'href="https://exemplo.com"' in limpo
    assert 'target="_blank"' in limpo
    assert 'rel="noopener noreferrer"' in limpo


@pytest.mark.parametrize(
    "fonte",
    ["https://exemplo.com/a.png", "data:image/png;base64,AAAA", "/anexos/1/baixar"],
)
def test_limpar_descricao_remove_imagem_que_nao_foi_enviada(fonte):
    assert limpar_descricao('texto<img src="{}">'.format(fonte)) == "texto"


def test_limpar_descricao_mantem_imagem_enviada():
    html = '<img src="/imagens/{}">'.format("a" * 32)

    assert limpar_descricao(html) == html


@pytest.mark.parametrize("vazio", ["", None, "<br>", "<div><br></div>", "<div>&nbsp;</div>"])
def test_descricao_sem_conteudo_fica_vazia(vazio):
    assert limpar_descricao(vazio) == ""


def test_tarefa_salva_a_descricao_limpa_e_o_quadro_a_exibe_formatada(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    tarefa = salvar_tarefa(cliente, projeto, "<b>Forte</b><script>alert(1)</script>")

    html = cliente.get("/").get_data(as_text=True)
    assert tarefa.descricao == "<b>Forte</b>"
    assert '<div class="tarefa-descricao texto-formatado"><b>Forte</b></div>' in html
    assert "alert(1)" not in html


def test_dialogo_da_tarefa_oferece_os_12_botoes_de_formatacao(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    dialogo = html.split('id="dialogo-tarefa"')[1].split("</dialog>")[0]
    barra = dialogo.split('class="editor-barra"')[1].split('id="tarefa-editor"')[0]

    for rotulo in BOTOES:
        assert 'data-dica="{}"'.format(rotulo) in barra
    assert 'contenteditable="true"' in dialogo
    assert re.search(r'<textarea[^>]*hidden', dialogo)


def test_cada_botao_do_editor_tem_desenho_proprio(app):
    desenhar = get_template_attribute("_icones.html", "icone_editor")
    nomes = [
        "bold", "italic", "underline", "maior", "menor", "insertUnorderedList",
        "insertOrderedList", "indent", "outdent", "imagem", "link", "cor",
    ]

    assert len({str(desenhar(nome)) for nome in nomes}) == 12
    assert all("<path" in str(desenhar(nome)) for nome in nomes)


@pytest.mark.parametrize("conteudo, tipo", ASSINATURAS)
def test_enviar_imagem_guarda_o_arquivo_e_registra_o_tipo(app, cliente, conteudo, tipo):
    resposta = enviar_imagem(cliente, conteudo)

    imagem = Imagem.query.one()
    assert resposta.status_code == 200
    assert resposta.get_json()["url"] == "/imagens/{}".format(imagem.arquivo)
    assert imagem.tipo == tipo
    assert imagem.usuario_id == cliente.usuario_id
    assert imagem.tarefa_id is None
    assert (app.config["ANEXOS_DIR"] / imagem.arquivo).read_bytes() == conteudo


@pytest.mark.parametrize("conteudo", [b"<svg onload=alert(1)>", b"<html>", b"", b"texto"])
def test_enviar_imagem_recusa_o_que_nao_e_imagem(app, cliente, conteudo):
    resposta = enviar_imagem(cliente, conteudo)

    assert resposta.status_code == 400
    assert resposta.get_json()["erro"] == "Envie uma imagem PNG, JPEG, GIF ou WebP."
    assert Imagem.query.count() == 0
    assert arquivos(app) == []


def test_enviar_imagem_sem_arquivo_e_recusado(cliente):
    assert cliente.post("/api/imagens").status_code == 400


def test_enviar_imagem_grande_demais_e_recusado(app, cliente):
    resposta = enviar_imagem(cliente, PNG + b"\0" * (10 * 1024 * 1024))

    assert resposta.status_code == 400
    assert resposta.get_json()["erro"] == "Cada imagem pode ter até 10 MB."
    assert arquivos(app) == []


def test_ver_imagem_devolve_o_conteudo_com_o_tipo_certo(cliente):
    resposta = cliente.get(url_de_imagem_enviada(cliente))

    assert resposta.status_code == 200
    assert resposta.data == PNG
    assert resposta.mimetype == "image/png"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert "attachment" not in resposta.headers.get("Content-Disposition", "")


def test_imagem_de_outro_usuario_retorna_404(cliente, outro_cliente):
    url = url_de_imagem_enviada(cliente)

    assert outro_cliente.get(url).status_code == 404


def test_imagem_exige_login(app, cliente):
    url = url_de_imagem_enviada(cliente)

    assert app.test_client().get(url).status_code != 200


def test_salvar_tarefa_liga_a_imagem_do_texto(cliente, criar_projeto):
    url = url_de_imagem_enviada(cliente)

    tarefa = salvar_tarefa(cliente, criar_projeto(cliente.usuario_id), '<img src="{}">'.format(url))

    assert Imagem.query.one().tarefa_id == tarefa.id


def test_remover_imagem_do_texto_apaga_o_arquivo(app, cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    url = url_de_imagem_enviada(cliente)
    tarefa = salvar_tarefa(cliente, projeto, '<img src="{}">'.format(url))

    cliente.post(
        "/tarefas/{}/editar".format(tarefa.id),
        data={"nome": "Com texto", "projeto_id": projeto.id, "descricao": "sem imagem"},
    )

    assert Imagem.query.count() == 0
    assert arquivos(app) == []


def test_imagem_de_edicao_cancelada_some_ao_salvar_outra_tarefa(app, cliente, criar_projeto):
    url_de_imagem_enviada(cliente)

    salvar_tarefa(cliente, criar_projeto(cliente.usuario_id), "texto")

    assert Imagem.query.count() == 0
    assert arquivos(app) == []


def test_salvar_tarefa_mantem_imagem_de_outra_tarefa(app, cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    url = url_de_imagem_enviada(cliente)
    tarefa = salvar_tarefa(cliente, projeto, '<img src="{}">'.format(url))

    cliente.post(
        "/tarefas/{}/editar".format(criar_tarefa(projeto, "Outra").id),
        data={"nome": "Outra", "projeto_id": projeto.id, "descricao": "texto"},
    )

    assert Imagem.query.one().tarefa_id == tarefa.id
    assert len(arquivos(app)) == 1


def test_salvar_tarefa_nao_mexe_na_imagem_de_outro_usuario(
    app, cliente, outro_cliente, criar_projeto
):
    url = url_de_imagem_enviada(outro_cliente)

    salvar_tarefa(cliente, criar_projeto(cliente.usuario_id), '<img src="{}">'.format(url))

    assert Imagem.query.one().tarefa_id is None
    assert len(arquivos(app)) == 1


def test_excluir_tarefa_apaga_as_imagens_do_texto(app, cliente, criar_projeto):
    url = url_de_imagem_enviada(cliente)
    tarefa = salvar_tarefa(cliente, criar_projeto(cliente.usuario_id), '<img src="{}">'.format(url))

    cliente.post("/tarefas/{}/excluir".format(tarefa.id))

    assert Imagem.query.count() == 0
    assert arquivos(app) == []


@pytest.mark.so_sqlite
def test_atualizar_banco_converte_a_descricao_antiga_em_html(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    with db.engine.begin() as conexao:
        conexao.execute(text("ALTER TABLE tarefa ADD COLUMN descricao TEXT"))
        conexao.execute(
            text("UPDATE tarefa SET descricao = :texto"),
            {"texto": "1 < 2 & <b>\r\nOutra linha"},
        )
    db.session.expire_all()

    atualizar_banco()

    db.session.expire_all()
    assert (
        db.session.get(Tarefa, tarefa.id).descricao
        == "1 &lt; 2 &amp; &lt;b&gt;<br>Outra linha"
    )
    colunas = db.session.execute(text("PRAGMA table_info(tarefa)")).fetchall()
    assert "descricao" not in [coluna[1] for coluna in colunas]


def test_barra_da_descricao_tem_o_botao_de_tela_inteira(cliente):
    html = cliente.get("/").get_data(as_text=True)

    barra = html.split('class="editor-barra"')[1].split('id="tarefa-editor"')[0]
    assert 'data-editor="tela-inteira"' in barra
    assert 'aria-pressed="false" aria-label="Editar em tela inteira" data-dica="Editar em tela inteira"' in barra
    assert barra.count("<span data-icone-ligado hidden>") == 2


def test_botao_de_visualizar_fica_ao_lado_do_de_tela_inteira(cliente):
    html = cliente.get("/").get_data(as_text=True)

    barra = html.split('class="editor-barra"')[1].split('id="tarefa-editor"')[0]
    visualizar = barra.index('data-editor="visualizar"')
    assert visualizar < barra.index('data-editor="tela-inteira"')
    assert 'data-dica="Apenas visualizar a descrição"' in barra[visualizar:]
    assert barra.index('id="editor-cor"') < visualizar


def test_links_da_descricao_abrem_em_outra_aba(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    cliente.post(
        "/tarefas",
        data={
            "nome": "Com link",
            "projeto_id": projeto.id,
            "descricao": '<a href="https://exemplo.com" target="_self">site</a>',
        },
    )

    descricao = Tarefa.query.one().descricao
    assert 'target="_blank"' in descricao
    assert 'target="_self"' not in descricao
    assert 'rel="noopener noreferrer"' in descricao
