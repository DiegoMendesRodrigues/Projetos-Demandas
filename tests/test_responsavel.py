# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from datetime import timedelta

import pytest

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
from routes import agora


def usuario(cliente):
    return db.session.get(Usuario, cliente.usuario_id)


def cartao(html, nome):
    """O trecho do quadro com o cartão de uma demanda."""
    quadro = html.split("<dialog")[0]
    inicio = quadro.index('data-nome="{}"'.format(nome))
    return quadro[inicio:quadro.index("</article>", inicio)]


@pytest.fixture
def cenario(cliente, outro_cliente, criar_cliente, criar_tarefa):
    """Ana compartilha a categoria Casa com o grupo Família (Bruno); Carla está fora."""
    carla = criar_cliente("carla@exemplo.com")
    ana, bruno = usuario(cliente), usuario(outro_cliente)
    ana.nome, bruno.nome = "Ana", "Bruno"
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=ana.id)
    grupo.membros.extend([ana, bruno])
    casa = Categoria(nome="Casa", usuario_id=ana.id)
    trabalho = Categoria(nome="Trabalho", usuario_id=ana.id)
    db.session.add_all([grupo, casa, trabalho])
    db.session.flush()
    feira = Projeto(nome="Feira", usuario_id=ana.id, categoria_id=casa.id, posicao=0)
    reuniao = Projeto(nome="Reuniões", usuario_id=ana.id, categoria_id=trabalho.id, posicao=1)
    db.session.add_all([feira, reuniao])
    db.session.add(CompartilhamentoDeCategoria(categoria_id=casa.id, grupo_id=grupo.id, permissao="visualizar"))
    db.session.commit()
    tarefa = criar_tarefa(feira, nome="Comprar frutas")
    secreta = criar_tarefa(reuniao, nome="Pauta secreta")

    class Cenario:
        pass

    c = Cenario()
    c.ana, c.bruno, c.carla = cliente, outro_cliente, carla
    c.grupo, c.casa, c.feira = grupo, casa, feira
    c.tarefa, c.secreta = tarefa, secreta
    return c


def definir(c, tarefa, pessoa_id, cliente=None):
    return (cliente or c.ana).post(
        "/tarefas/{}/responsavel".format(tarefa.id), data={"responsavel_id": pessoa_id}
    )


def test_cartao_mostra_o_icone_e_o_nome_do_proprietario(cenario):
    html = cartao(cenario.ana.get("/").get_data(as_text=True), "Comprar frutas")
    assert 'class="tarefa-pessoa tarefa-proprietario"' in html and 'data-dica="Ana"' in html
    assert '<svg class="avatar"' in html


def test_proprietario_ve_o_botao_a_esquerda_do_icone(cenario):
    html = cartao(cenario.ana.get("/").get_data(as_text=True), "Comprar frutas")
    assert 'data-dica="Adicionar Responsável"' in html
    assert html.index("data-escolher-responsavel") < html.index("tarefa-proprietario")


def test_video_nao_tem_proprietario_nem_responsavel(cenario):
    video = Tarefa(nome="Aula", tipo="video", projeto_id=cenario.feira.id, posicao=2)
    video.video = VideoDoYoutube(endereco="https://www.youtube.com/watch?v=jNQXAC9IVRw", codigo="jNQXAC9IVRw", titulo="Aula")
    db.session.add(video)
    db.session.commit()
    html = cartao(cenario.ana.get("/").get_data(as_text=True), "Aula")
    assert "tarefa-pessoas" not in html
    assert definir(cenario, video, cenario.bruno.usuario_id).status_code == 404


def test_caixa_lista_quem_ve_o_quadro_de_cada_categoria(cenario):
    html = cenario.ana.get("/").get_data(as_text=True)
    caixa = html[html.index('id="dialogo-responsavel"'):]
    caixa = caixa[:caixa.index("</dialog>")]
    da_casa = caixa[caixa.index('data-candidatos="{}"'.format(cenario.casa.id)):]
    da_casa = da_casa[:da_casa.index("</fieldset>")]
    assert "Ana (você)" in da_casa and "Bruno" in da_casa and "carla@" not in da_casa
    do_trabalho = caixa[caixa.index('data-candidatos="{}"'.format(cenario.secreta.projeto.categoria_id)):]
    do_trabalho = do_trabalho[:do_trabalho.index("</fieldset>")]
    assert "Bruno" not in do_trabalho and "Compartilhe a categoria" in do_trabalho


def test_proprietario_define_e_retira_o_responsavel(cenario):
    definir(cenario, cenario.tarefa, cenario.bruno.usuario_id)
    assert db.session.get(Tarefa, cenario.tarefa.id).responsavel_id == cenario.bruno.usuario_id
    html = cartao(cenario.ana.get("/").get_data(as_text=True), "Comprar frutas")
    assert 'data-dica="Responsável: Bruno"' in html

    definir(cenario, cenario.tarefa, cenario.ana.usuario_id)
    assert db.session.get(Tarefa, cenario.tarefa.id).responsavel_id is None


def test_responsavel_precisa_ter_acesso_ao_quadro(cenario):
    definir(cenario, cenario.tarefa, cenario.carla.usuario_id)
    definir(cenario, cenario.secreta, cenario.bruno.usuario_id)
    assert db.session.get(Tarefa, cenario.tarefa.id).responsavel_id is None
    assert db.session.get(Tarefa, cenario.secreta.id).responsavel_id is None


def test_so_o_proprietario_define_o_responsavel(cenario):
    CompartilhamentoDeCategoria.query.one().permissao = "editar"
    db.session.commit()
    resposta = definir(cenario, cenario.tarefa, cenario.bruno.usuario_id, cliente=cenario.bruno)
    assert resposta.status_code == 404
    html = cenario.bruno.get("/?categoria={}".format(cenario.casa.id)).get_data(as_text=True)
    assert "data-escolher-responsavel" not in html and 'id="dialogo-responsavel"' not in html


def test_membro_ve_o_responsavel_sem_poder_trocar(cenario):
    definir(cenario, cenario.tarefa, cenario.bruno.usuario_id)
    html = cartao(cenario.bruno.get("/?categoria={}".format(cenario.casa.id)).get_data(as_text=True), "Comprar frutas")
    assert '<span class="tarefa-pessoa tarefa-responsavel"' in html and 'data-dica="Responsável: Bruno"' in html


def atrasar(tarefa):
    tarefa = db.session.get(Tarefa, tarefa.id)
    tarefa.previsao_execucao = agora() - timedelta(hours=1)
    db.session.commit()


def test_responsavel_recebe_o_alerta_de_atraso(cenario):
    atrasar(cenario.tarefa)
    assert "Comprar frutas" not in cenario.bruno.get("/grupos").get_data(as_text=True)
    definir(cenario, cenario.tarefa, cenario.bruno.usuario_id)
    html = cenario.bruno.get("/grupos").get_data(as_text=True)
    alertas = html[html.index('id="menu-alertas"'):]
    alertas = alertas[:alertas.index("</div>")]
    assert "Comprar frutas" in alertas
    # O alerta abre o cartão na categoria compartilhada.
    assert "categoria={}".format(cenario.casa.id) in alertas
    assert "Comprar frutas" in cenario.ana.get("/grupos").get_data(as_text=True)


def test_quem_perde_o_acesso_deixa_de_ser_responsavel(cenario):
    atrasar(cenario.tarefa)
    definir(cenario, cenario.tarefa, cenario.bruno.usuario_id)
    cenario.grupo.membros.remove(usuario(cenario.bruno))
    db.session.commit()
    assert db.session.get(Tarefa, cenario.tarefa.id).responsavel_atual is None
    assert 'id="menu-alertas"' not in cenario.bruno.get("/grupos").get_data(as_text=True)
    html = cartao(cenario.ana.get("/").get_data(as_text=True), "Comprar frutas")
    assert 'data-dica="Adicionar Responsável"' in html


def test_excluir_o_usuario_tira_ele_dos_cartoes(cenario):
    usuario(cenario.ana).administrador = True
    db.session.commit()
    definir(cenario, cenario.tarefa, cenario.bruno.usuario_id)
    cenario.ana.post("/administracao/usuarios/{}/excluir".format(cenario.bruno.usuario_id))
    assert db.session.get(Usuario, cenario.bruno.usuario_id) is None
    assert db.session.get(Tarefa, cenario.tarefa.id).responsavel_id is None


def test_com_responsavel_o_proprietario_fica_em_cinza(cenario):
    html = cartao(cenario.ana.get("/").get_data(as_text=True), "Comprar frutas")
    assert 'class="tarefa-pessoas"' in html
    definir(cenario, cenario.tarefa, cenario.bruno.usuario_id)
    html = cartao(cenario.ana.get("/").get_data(as_text=True), "Comprar frutas")
    assert 'class="tarefa-pessoas com-responsavel"' in html
