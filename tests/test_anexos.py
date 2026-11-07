# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from extensions import db
from forms import nome_de_arquivo
from models import Anexo, PlanoDeUsuario, Tarefa, Usuario, rotulo_em_megabytes


def arquivo(nome="contrato.pdf", conteudo=b"conteudo"):
    return (BytesIO(conteudo), nome)


def criar_com_anexos(cliente, projeto, arquivos):
    return cliente.post(
        "/tarefas",
        data={"nome": "Com anexos", "projeto_id": projeto.id, "anexos": arquivos},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def editar_com_anexos(cliente, tarefa, arquivos):
    return cliente.post(
        "/tarefas/{}/editar".format(tarefa.id),
        data={"nome": tarefa.nome, "projeto_id": tarefa.projeto_id, "anexos": arquivos},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def arquivos_em_disco(app):
    return sorted(caminho.name for caminho in app.config["ANEXOS_DIR"].iterdir())


def test_criar_tarefa_com_anexo_guarda_nome_tamanho_e_arquivo(app, cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    criar_com_anexos(cliente, projeto, [arquivo("contrato.pdf", b"12345")])

    anexo = Anexo.query.one()
    assert anexo.nome == "contrato.pdf"
    assert anexo.tamanho == 5
    assert anexo.tarefa.nome == "Com anexos"
    assert re.fullmatch(r"[0-9a-f]{32}", anexo.arquivo)
    assert arquivos_em_disco(app) == [anexo.arquivo]
    assert (app.config["ANEXOS_DIR"] / anexo.arquivo).read_bytes() == b"12345"


def test_editar_tarefa_adiciona_anexo_e_mantem_os_atuais(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))

    editar_com_anexos(cliente, tarefa, [arquivo("um.txt")])
    editar_com_anexos(cliente, tarefa, [arquivo("dois.txt")])

    assert [anexo.nome for anexo in db.session.get(Tarefa, tarefa.id).anexos] == [
        "um.txt",
        "dois.txt",
    ]


def test_salvar_tarefa_sem_arquivo_nao_cria_anexo(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))

    editar_com_anexos(cliente, tarefa, [(BytesIO(b""), "")])

    assert Anexo.query.count() == 0


def test_criar_tarefa_com_quatro_arquivos_e_recusado(app, cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    resposta = criar_com_anexos(cliente, projeto, [arquivo(str(n)) for n in range(4)])

    assert "<p>Cada demanda pode ter até 3 arquivos.</p>" in resposta.get_data(as_text=True)
    assert Tarefa.query.count() == 0
    assert arquivos_em_disco(app) == []


def test_quarto_arquivo_na_tarefa_e_recusado_sem_alterar_a_tarefa(
    app, cliente, criar_projeto, criar_tarefa
):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id), "Original")
    editar_com_anexos(cliente, tarefa, [arquivo(str(n)) for n in range(3)])

    resposta = cliente.post(
        "/tarefas/{}/editar".format(tarefa.id),
        data={"nome": "Alterada", "projeto_id": tarefa.projeto_id, "anexos": [arquivo("quarto")]},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert "<p>Cada demanda pode ter até 3 arquivos.</p>" in resposta.get_data(as_text=True)
    assert Anexo.query.count() == 3
    assert len(arquivos_em_disco(app)) == 3
    assert db.session.get(Tarefa, tarefa.id).nome == "Original"


def test_arquivo_acima_do_tamanho_maximo_e_recusado(app, cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)

    with patch("routes.TAMANHO_MAXIMO_ANEXO", 4):
        resposta = criar_com_anexos(cliente, projeto, [arquivo("grande.bin", b"12345")])

    assert "Cada arquivo pode ter até" in resposta.get_data(as_text=True)
    assert Anexo.query.count() == 0
    assert arquivos_em_disco(app) == []


def test_envio_maior_que_o_limite_geral_mostra_erro_em_portugues(app, cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    app.config["MAX_CONTENT_LENGTH"] = 10

    resposta = criar_com_anexos(cliente, projeto, [arquivo("grande.bin", b"x" * 100)])

    assert resposta.status_code == 413
    assert "Os arquivos enviados ultrapassam o tamanho permitido." in resposta.get_data(
        as_text=True
    )


@pytest.mark.parametrize(
    "enviado, esperado",
    [
        ("../../segredo.txt", "segredo.txt"),
        ("relatório final.pdf", "relatório final.pdf"),
        ("a" * 300 + ".pdf", "a" * 251 + ".pdf"),
    ],
)
def test_nome_enviado_e_limpo_e_nao_define_o_caminho(
    app, cliente, criar_projeto, enviado, esperado
):
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo(enviado)])

    anexo = Anexo.query.one()
    assert anexo.nome == esperado
    assert arquivos_em_disco(app) == [anexo.arquivo]


def test_nome_de_arquivo_remove_caminho_do_windows_e_caracteres_de_controle():
    assert nome_de_arquivo("C:\\pasta\\..\\nota\x00\n.txt") == "nota.txt"


@pytest.mark.parametrize(
    "tamanho, rotulo",
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1536, "1,5 KB"),
        (1024 * 1024, "1,0 MB"),
        (int(2.5 * 1024 * 1024), "2,5 MB"),
    ],
)
def test_tamanho_e_formatado_em_portugues(tamanho, rotulo):
    assert Anexo(tamanho=tamanho).tamanho_rotulo == rotulo


def test_cartao_exibe_nome_e_tamanho_sem_link(cliente, criar_projeto):
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo("nota.txt", b"x" * 2048)])
    anexo = Anexo.query.one()

    html = cliente.get("/").get_data(as_text=True)
    cartao = html.split('<ul class="tarefa-anexos">')[1].split("</ul>")[0]

    assert "<span>nota.txt</span>" in cartao
    assert '<span class="anexo-tamanho">2,0 KB</span>' in cartao
    assert "<a " not in cartao and "href=" not in cartao
    # O diálogo monta o link de download a partir deste atributo.
    assert 'data-url-baixar="/anexos/{}/baixar"'.format(anexo.id) in cartao


def test_area_de_arquivos_fica_abaixo_do_local(cliente, criar_projeto):
    criar_projeto(cliente.usuario_id)

    html = cliente.get("/").get_data(as_text=True)
    dialogo = html.split('id="dialogo-tarefa"')[1].split("</dialog>")[0]

    assert 'enctype="multipart/form-data"' in dialogo
    assert dialogo.index('id="tarefa-local"') < dialogo.index('id="tarefa-arquivos"')
    assert 'name="anexos" multiple' in dialogo
    assert 'data-limite="3"' in dialogo


def test_download_sempre_como_anexo_com_o_nome_atual(cliente, criar_projeto):
    criar_com_anexos(
        cliente,
        criar_projeto(cliente.usuario_id),
        [arquivo("pagina.html", b"<script>alert(1)</script>")],
    )
    anexo = Anexo.query.one()

    resposta = cliente.get("/anexos/{}/baixar".format(anexo.id))

    assert resposta.status_code == 200
    assert resposta.get_data() == b"<script>alert(1)</script>"
    assert resposta.mimetype == "application/octet-stream"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["Content-Disposition"].startswith("attachment")
    assert "pagina.html" in resposta.headers["Content-Disposition"]


def test_download_exige_login(app, cliente, criar_projeto):
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo()])

    resposta = app.test_client().get("/anexos/{}/baixar".format(Anexo.query.one().id))

    assert resposta.status_code in (302, 401)


@pytest.mark.parametrize(
    "novo, esperado",
    [("novo nome", "novo nome.pdf"), ("novo.docx", "novo.docx"), ("../novo.pdf", "novo.pdf")],
)
def test_renomear_anexo_mantem_a_extensao_quando_omitida(
    app, cliente, criar_projeto, novo, esperado
):
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo("antigo.pdf")])
    anexo = Anexo.query.one()
    codigo = anexo.arquivo

    resposta = cliente.post(
        "/anexos/{}/renomear".format(anexo.id), data={"nome": novo}, follow_redirects=True
    )

    db.session.expire_all()
    assert db.session.get(Anexo, anexo.id).nome == esperado
    assert arquivos_em_disco(app) == [codigo]
    assert "<p>" not in resposta.get_data(as_text=True).split('id="notificacao"')[1].split(
        "</dialog>"
    )[0]


def test_renomear_anexo_com_nome_vazio_e_recusado(cliente, criar_projeto):
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo("antigo.pdf")])
    anexo = Anexo.query.one()

    resposta = cliente.post(
        "/anexos/{}/renomear".format(anexo.id), data={"nome": "   "}, follow_redirects=True
    )

    assert "<p>Informe o nome do arquivo.</p>" in resposta.get_data(as_text=True)
    assert db.session.get(Anexo, anexo.id).nome == "antigo.pdf"


def test_excluir_anexo_remove_do_banco_e_do_disco(app, cliente, criar_projeto):
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo("a.txt"), arquivo("b.txt")])
    primeiro, segundo = Anexo.query.order_by(Anexo.id).all()

    resposta = cliente.post("/anexos/{}/excluir".format(primeiro.id), follow_redirects=True)

    assert "<p>Arquivo excluído.</p>" in resposta.get_data(as_text=True)
    assert [anexo.nome for anexo in Anexo.query.all()] == ["b.txt"]
    assert arquivos_em_disco(app) == [segundo.arquivo]


def test_excluir_anexo_libera_vaga_na_tarefa(cliente, criar_projeto, criar_tarefa):
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    editar_com_anexos(cliente, tarefa, [arquivo(str(n)) for n in range(3)])

    cliente.post("/anexos/{}/excluir".format(Anexo.query.first().id))
    editar_com_anexos(cliente, tarefa, [arquivo("novo")])

    assert Anexo.query.count() == 3


def test_excluir_tarefa_remove_os_anexos_do_disco(app, cliente, criar_projeto):
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo("a.txt"), arquivo("b.txt")])

    cliente.post("/tarefas/{}/excluir".format(Tarefa.query.one().id))

    assert Anexo.query.count() == 0
    assert arquivos_em_disco(app) == []


def plano_com(nome, megabytes):
    plano = PlanoDeUsuario(nome=nome, armazenamento_mb=megabytes)
    db.session.add(plano)
    db.session.commit()
    return plano


@pytest.mark.parametrize("megabytes", [10, 50, 100, 250])
def test_espaco_para_anexos_depende_do_plano(cliente, megabytes):
    usuario = db.session.get(Usuario, cliente.usuario_id)
    usuario.plano = plano_com("Plano de {} MB".format(megabytes), megabytes)

    assert usuario.espaco_para_anexos == megabytes * 1024 * 1024


def test_anexos_que_ultrapassam_o_espaco_do_usuario_sao_recusados(
    app, cliente, criar_projeto, criar_tarefa
):
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto)

    # Com 1 byte por MB, os 10 MB do plano Iniciante viram 10 bytes.
    with patch("models.BYTES_POR_MB", 1):
        criar_com_anexos(cliente, projeto, [arquivo("um.txt", b"123456")])
        resposta = editar_com_anexos(cliente, tarefa, [arquivo("dois.txt", b"12345")])

    assert "Os anexos não cabem no seu espaço de 10 B: 6 B já estão em uso." in resposta.get_data(
        as_text=True
    )
    assert [anexo.nome for anexo in Anexo.query] == ["um.txt"]
    assert len(arquivos_em_disco(app)) == 1


def test_espaco_do_usuario_aceita_ate_o_limite_e_ignora_outros_usuarios(
    cliente, outro_cliente, criar_projeto
):
    projeto = criar_projeto(cliente.usuario_id)
    projeto_do_outro = criar_projeto(outro_cliente.usuario_id)

    with patch("models.BYTES_POR_MB", 1):
        criar_com_anexos(outro_cliente, projeto_do_outro, [arquivo("dele.txt", b"123456789")])
        criar_com_anexos(cliente, projeto, [arquivo("a.txt", b"12345"), arquivo("b.txt", b"12345")])

    assert sorted(anexo.nome for anexo in Anexo.query) == ["a.txt", "b.txt", "dele.txt"]


def test_plano_maior_libera_mais_espaco(cliente, criar_projeto):
    projeto = criar_projeto(cliente.usuario_id)
    PlanoDeUsuario.query.filter_by(padrao=True).one().armazenamento_mb = 1
    db.session.get(Usuario, cliente.usuario_id).plano = plano_com("Mestre", 10)
    db.session.commit()

    with patch("models.BYTES_POR_MB", 1):
        criar_com_anexos(cliente, projeto, [arquivo("a.txt", b"12345")])

    assert Anexo.query.count() == 1


def test_quadro_mostra_o_espaco_em_uso(cliente, criar_projeto):
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo("a.txt", b"x" * 2048)])

    html = cliente.get("/").get_data(as_text=True)

    assert "Espaço em uso: 2,0 KB de 10,0 MB." in html
    assert 'data-espaco="{}" data-espaco-usado="2048"'.format(10 * 1024 * 1024) in html


@pytest.mark.parametrize(
    "tamanho, rotulo",
    [
        (0, "0 MB"),
        (673296, "0,64 MB"),
        (8368537, "7,98 MB"),
        (int(2.5 * 1024 * 1024), "2,50 MB"),
        (10 * 1024 * 1024, "10 MB"),
        (10 * 1024 * 1024 + 1, "10 MB"),
    ],
)
def test_rotulo_em_megabytes(tamanho, rotulo):
    assert rotulo_em_megabytes(tamanho) == rotulo


def test_rodape_da_lateral_mostra_plano_e_espaco(cliente, criar_projeto):
    db.session.get(Usuario, cliente.usuario_id).plano = plano_com("Avançado", 100)
    db.session.commit()
    criar_com_anexos(cliente, criar_projeto(cliente.usuario_id), [arquivo("a.txt", b"x" * 3 * 1024 * 1024)])

    lateral = cliente.get("/").get_data(as_text=True).split('<aside class="lateral"')[1].split("</aside>")[0]

    assert '<footer class="lateral-rodape">Avançado: 3 MB de 100 MB</footer>' in lateral


def test_excluir_arquivo_no_cartao_aberto_salva_exclui_e_salva_de_novo(app, cliente, criar_projeto, criar_tarefa):
    """O caminho de app.js ao excluir um arquivo com o cartão aberto: as três requisições em sequência."""
    tarefa = criar_tarefa(criar_projeto(cliente.usuario_id))
    editar_com_anexos(cliente, tarefa, [arquivo("a.txt"), arquivo("b.txt")])
    primeiro, segundo = Anexo.query.order_by(Anexo.id).all()
    dados = {"nome": "Nome digitado antes de excluir", "projeto_id": tarefa.projeto_id, "local": "Sala 2"}

    # O que foi digitado é salvo antes, e a página devolvida não traz mensagem (sem erro).
    salvo = cliente.post("/tarefas/{}/editar".format(tarefa.id), data=dados, follow_redirects=True)
    mensagens = salvo.get_data(as_text=True).split("data-notificacao-texto")[1].split("</div>")[0]
    assert "<p>" not in mensagens
    cliente.post("/anexos/{}/excluir".format(primeiro.id))
    pagina = cliente.post("/tarefas/{}/editar".format(tarefa.id), data=dados, follow_redirects=True).get_data(as_text=True)

    tarefa = db.session.get(Tarefa, tarefa.id)
    assert (tarefa.nome, tarefa.local) == ("Nome digitado antes de excluir", "Sala 2")
    assert [anexo.id for anexo in tarefa.anexos] == [segundo.id]
    assert arquivos_em_disco(app) == [segundo.arquivo]
    # O quadro devolvido traz o cartão com o arquivo que ficou e o espaço em uso atualizado.
    cartao = pagina.split('data-tarefa-id="{}"'.format(tarefa.id))[1].split("</article>")[0]
    assert 'data-nome="b.txt"' in cartao and 'data-nome="a.txt"' not in cartao
    assert "data-espaco-em-uso" in pagina


def test_app_exclui_o_arquivo_sem_fechar_o_cartao():
    codigo = (Path(__file__).resolve().parent.parent / "static/js/app.js").read_text(encoding="utf-8")
    funcao = codigo.split("async function excluirArquivoDoCartaoAberto")[1].split("\n  }\n")[0]

    # Salva, exclui e salva de novo, nesta ordem, e preenche de novo os arquivos da caixa aberta.
    assert funcao.index("salvarCartaoAberto()") < funcao.index("fetch(url") < funcao.rindex("salvarCartaoAberto()")
    assert "preencherAnexos(cartao)" in funcao and ".close()" not in funcao
    # Sem evento submit artificial: extensões do navegador o tratam como envio e recarregam a página.
    salvar = codigo.split("async function salvarCartaoAberto")[1].split("\n  }\n")[0]
    assert "prepararEnvio(formularioDaTarefa);" in salvar
    assert "dispatchEvent" not in codigo
    assert 'formularioDaConfirmacao.dataset.excluirAnexo = botao.closest("#dialogo-tarefa")' in codigo
