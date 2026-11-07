# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import io

import pytest

from extensions import db
from models import (
    Anexo,
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    Imagem,
    Projeto,
    Tarefa,
    Usuario,
)


def usuario(cliente):
    return db.session.get(Usuario, cliente.usuario_id)


@pytest.fixture
def cenario(cliente, outro_cliente, criar_cliente, criar_tarefa):
    """Ana compartilha a categoria Casa; Bruno está no grupo dela, Carla não."""
    carla = criar_cliente("carla@exemplo.com")
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=cliente.usuario_id)
    grupo.membros.extend([usuario(cliente), usuario(outro_cliente)])
    casa = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    trabalho = Categoria(nome="Trabalho", usuario_id=cliente.usuario_id)
    db.session.add_all([grupo, casa, trabalho])
    db.session.flush()
    feira = Projeto(nome="Feira", usuario_id=cliente.usuario_id, categoria_id=casa.id, posicao=0)
    reforma = Projeto(nome="Reforma", usuario_id=cliente.usuario_id, categoria_id=casa.id, posicao=1)
    reuniao = Projeto(nome="Reuniões", usuario_id=cliente.usuario_id, categoria_id=trabalho.id, posicao=2)
    db.session.add_all([feira, reforma, reuniao])
    db.session.commit()
    tarefa = criar_tarefa(feira, nome="Comprar frutas")
    secreta = criar_tarefa(reuniao, nome="Pauta secreta")

    class Cenario:
        pass

    c = Cenario()
    c.ana, c.bruno, c.carla = cliente, outro_cliente, carla
    c.grupo, c.casa, c.trabalho = grupo, casa, trabalho
    c.feira, c.reforma, c.reuniao = feira, reforma, reuniao
    c.tarefa, c.secreta = tarefa, secreta
    return c


def compartilhar(c, permissao):
    resposta = c.ana.post(
        "/categorias/{}/compartilhar".format(c.casa.id), data={"grupo-{}".format(c.grupo.id): permissao}
    )
    assert resposta.status_code == 302
    return resposta


def editar(cliente, tarefa, **campos):
    dados = {"nome": tarefa.nome, "prioridade": "baixa", "projeto_id": tarefa.projeto_id, "tipo": "atividade"}
    dados.update(campos)
    return cliente.post("/tarefas/{}/editar".format(tarefa.id), data=dados)


def test_botao_compartilhar_aparece_so_na_categoria_do_dono(cenario):
    c = cenario

    assert '<span class="rotulo-do-botao">Compartilhar</span></a>' in c.ana.get("/?categoria={}".format(c.casa.id)).get_data(as_text=True)
    assert '<span class="rotulo-do-botao">Compartilhar</span></a>' not in c.ana.get("/").get_data(as_text=True)


def test_tela_compartilhar_lista_os_grupos_do_usuario(cenario):
    c = cenario
    outro = GrupoDeUsuarios(nome="Clube", administrador_id=c.carla.usuario_id)
    outro.membros.append(usuario(c.carla))
    db.session.add(outro)
    db.session.commit()

    html = c.ana.get("/categorias/{}/compartilhar".format(c.casa.id)).get_data(as_text=True)

    assert "Família" in html and 'name="grupo-{}"'.format(c.grupo.id) in html
    assert "Clube" not in html
    assert ">Visualizar</option>" in html and ">Editar</option>" in html


def test_so_o_dono_compartilha(cenario):
    c = cenario
    url = "/categorias/{}/compartilhar".format(c.casa.id)

    assert c.bruno.get(url).status_code == 404
    assert c.bruno.post(url, data={"grupo-{}".format(c.grupo.id): "editar"}).status_code == 404
    assert CompartilhamentoDeCategoria.query.count() == 0


def test_salvar_cria_altera_e_remove_o_compartilhamento(cenario):
    c = cenario

    compartilhar(c, "visualizar")
    assert CompartilhamentoDeCategoria.query.one().permissao == "visualizar"
    compartilhar(c, "editar")
    assert CompartilhamentoDeCategoria.query.one().permissao == "editar"
    compartilhar(c, "")
    assert CompartilhamentoDeCategoria.query.count() == 0


def test_permissao_invalida_nao_compartilha(cenario):
    compartilhar(cenario, "administrar")

    assert CompartilhamentoDeCategoria.query.count() == 0


def test_grupo_de_que_o_usuario_nao_participa_e_ignorado(cenario):
    c = cenario
    outro = GrupoDeUsuarios(nome="Clube", administrador_id=c.carla.usuario_id)
    outro.membros.append(usuario(c.carla))
    db.session.add(outro)
    db.session.commit()

    c.ana.post("/categorias/{}/compartilhar".format(c.casa.id), data={"grupo-{}".format(outro.id): "editar"})

    assert CompartilhamentoDeCategoria.query.count() == 0


def test_membro_ve_a_categoria_na_lateral_e_os_projetos_dele(cenario):
    c = cenario
    compartilhar(c, "visualizar")

    lateral = c.bruno.get("/").get_data(as_text=True).split("</aside>")[0]
    assert "Compartilhadas comigo" in lateral and "?categoria={}".format(c.casa.id) in lateral

    html = c.bruno.get("/?categoria={}".format(c.casa.id)).get_data(as_text=True)
    assert "Feira" in html and "Reforma" in html and "Comprar frutas" in html
    assert "Reuniões" not in html and "Pauta secreta" not in html


def test_quem_nao_esta_no_grupo_nao_ve_a_categoria(cenario):
    c = cenario
    compartilhar(c, "editar")

    assert "Compartilhadas comigo" not in c.carla.get("/").get_data(as_text=True)
    assert c.carla.get("/?categoria={}".format(c.casa.id)).status_code == 404
    assert editar(c.carla, c.tarefa, nome="Invadida").status_code == 404


def test_categoria_nao_compartilhada_continua_isolada(cenario):
    c = cenario
    compartilhar(c, "editar")

    assert c.bruno.get("/?categoria={}".format(c.trabalho.id)).status_code == 404
    assert editar(c.bruno, c.secreta, nome="Alterada").status_code == 404


def test_visualizar_nao_mostra_controles_de_edicao(cenario):
    c = cenario
    compartilhar(c, "visualizar")

    html = c.bruno.get("/?categoria={}".format(c.casa.id)).get_data(as_text=True)

    assert 'data-permissao="visualizar"' in html
    assert "Apenas visualizar" in html
    for controle in ("data-nova-tarefa", "data-editar-projeto", "data-novo-projeto", "tarefa-alca", "projeto-alca", "botao-concluir"):
        assert controle not in html.split("<dialog")[0], controle


def test_visualizar_nao_permite_alterar(cenario):
    c = cenario
    compartilhar(c, "visualizar")
    t = c.tarefa

    assert editar(c.bruno, t, nome="Alterada").status_code == 404
    assert c.bruno.post("/tarefas/{}/concluir".format(t.id)).status_code == 404
    assert c.bruno.post("/tarefas/{}/ocultar".format(t.id)).status_code == 404
    assert c.bruno.post("/api/tarefas/{}/mover".format(t.id), json={"projeto_id": c.reforma.id, "posicao": 0}).status_code == 404
    novo = c.bruno.post("/tarefas", data={"nome": "Nova", "prioridade": "baixa", "projeto_id": c.feira.id, "tipo": "atividade"})
    assert novo.status_code == 302
    db.session.expire_all()
    assert db.session.get(Tarefa, t.id).nome == "Comprar frutas"
    assert Tarefa.query.filter_by(nome="Nova").count() == 0


def test_editar_permite_alterar_criar_concluir_ocultar_e_mover(cenario):
    c = cenario
    compartilhar(c, "editar")
    t = c.tarefa

    assert editar(c.bruno, t, nome="Comprar bananas").status_code == 302
    c.bruno.post("/tarefas/{}/concluir".format(t.id))
    c.bruno.post("/tarefas/{}/ocultar".format(t.id))
    resposta = c.bruno.post("/api/tarefas/{}/mover".format(t.id), json={"projeto_id": c.reforma.id, "posicao": 0})
    assert resposta.status_code == 200
    c.bruno.post("/tarefas", data={"nome": "Lâmpadas", "prioridade": "alta", "projeto_id": c.reforma.id, "tipo": "atividade"})

    db.session.expire_all()
    alterada = db.session.get(Tarefa, t.id)
    assert alterada.nome == "Comprar bananas"
    assert alterada.concluida_em is not None
    assert alterada.projeto_id == c.reforma.id
    assert Tarefa.query.filter_by(nome="Lâmpadas").one().projeto.usuario_id == c.ana.usuario_id


def test_editar_nao_permite_excluir(cenario):
    c = cenario
    compartilhar(c, "editar")

    html = c.bruno.get("/?categoria={}".format(c.casa.id)).get_data(as_text=True).split("<dialog")[0]
    assert "Excluir demanda" not in html and "data-editar-projeto" not in html
    assert c.bruno.post("/tarefas/{}/excluir".format(c.tarefa.id)).status_code == 404
    assert c.bruno.post("/projetos/{}/excluir".format(c.feira.id)).status_code == 404
    assert c.bruno.post("/projetos/{}/editar".format(c.feira.id), data={"nome": "X"}).status_code == 404
    assert db.session.get(Tarefa, c.tarefa.id) is not None


def test_editar_nao_move_para_fora_da_categoria(cenario, criar_projeto):
    c = cenario
    compartilhar(c, "editar")
    propria = criar_projeto(c.bruno.usuario_id, "Minha")

    for destino in (propria, c.reuniao):
        resposta = c.bruno.post("/api/tarefas/{}/mover".format(c.tarefa.id), json={"projeto_id": destino.id, "posicao": 0})
        assert resposta.status_code == 404
    assert db.session.get(Tarefa, c.tarefa.id).projeto_id == c.feira.id


def test_dono_continua_movendo_para_as_seus_projetos(cenario):
    c = cenario
    compartilhar(c, "editar")

    resposta = c.ana.post("/api/tarefas/{}/mover".format(c.tarefa.id), json={"projeto_id": c.reuniao.id, "posicao": 0})

    assert resposta.status_code == 200


def test_anexos_ocupam_o_espaco_do_dono(cenario):
    c = cenario
    compartilhar(c, "editar")

    dados = {"nome": c.tarefa.nome, "prioridade": "baixa", "projeto_id": c.feira.id, "tipo": "atividade",
             "anexos": (io.BytesIO(b"conteudo"), "nota.txt")}
    c.bruno.post("/tarefas/{}/editar".format(c.tarefa.id), data=dados, content_type="multipart/form-data")

    anexo = Anexo.query.one()
    assert anexo.tarefa.projeto.usuario_id == c.ana.usuario_id
    html = c.bruno.get("/?categoria={}".format(c.casa.id)).get_data(as_text=True)
    assert 'data-espaco-usado="{}"'.format(anexo.tamanho) in html


def test_visualizar_baixa_os_anexos_mas_nao_renomeia(cenario):
    c = cenario
    anexo = Anexo(nome="planta.pdf", arquivo="b" * 32, tamanho=4, tarefa_id=c.tarefa.id)
    db.session.add(anexo)
    db.session.commit()
    (c.ana.application.config["ANEXOS_DIR"] / anexo.arquivo).write_bytes(b"pdf!")
    compartilhar(c, "visualizar")

    assert c.bruno.get("/anexos/{}/baixar".format(anexo.id)).status_code == 200
    assert c.carla.get("/anexos/{}/baixar".format(anexo.id)).status_code == 404
    assert c.bruno.post("/anexos/{}/renomear".format(anexo.id), data={"nome": "x"}).status_code == 404
    assert c.bruno.post("/anexos/{}/excluir".format(anexo.id)).status_code == 404


def test_membro_ve_as_imagens_da_descricao(cenario):
    c = cenario
    imagem = Imagem(arquivo="c" * 32, tipo="image/png", usuario_id=c.ana.usuario_id, tarefa_id=c.tarefa.id)
    db.session.add(imagem)
    db.session.commit()
    (c.ana.application.config["ANEXOS_DIR"] / imagem.arquivo).write_bytes(b"\x89PNG\r\n\x1a\n")

    assert c.bruno.get("/imagens/{}".format(imagem.arquivo)).status_code == 404
    compartilhar(c, "visualizar")
    assert c.bruno.get("/imagens/{}".format(imagem.arquivo)).status_code == 200


def test_imagem_enviada_por_quem_edita_passa_a_ser_do_dono(cenario):
    c = cenario
    compartilhar(c, "editar")
    imagem = Imagem(arquivo="d" * 32, tipo="image/png", usuario_id=c.bruno.usuario_id)
    db.session.add(imagem)
    db.session.commit()

    editar(c.bruno, c.tarefa, descricao='<img src="/imagens/{}">'.format(imagem.arquivo))

    db.session.expire_all()
    salva = Imagem.query.one()
    assert (salva.tarefa_id, salva.usuario_id) == (c.tarefa.id, c.ana.usuario_id)


def test_excluir_grupo_ou_categoria_remove_o_compartilhamento(cenario):
    c = cenario
    compartilhar(c, "editar")
    db.session.delete(c.grupo)
    db.session.commit()
    assert CompartilhamentoDeCategoria.query.count() == 0

    vazia = Categoria(nome="Vazia", usuario_id=c.ana.usuario_id)
    outro = GrupoDeUsuarios(nome="Outro", administrador_id=c.ana.usuario_id)
    outro.membros.append(usuario(c.ana))
    db.session.add_all([vazia, outro])
    db.session.flush()
    vazia.compartilhamentos.append(CompartilhamentoDeCategoria(grupo_id=outro.id, permissao="visualizar"))
    db.session.commit()
    c.ana.post("/categorias/{}/excluir".format(vazia.id))
    assert CompartilhamentoDeCategoria.query.count() == 0


def test_editar_prevalece_quando_dois_grupos_compartilham(cenario):
    c = cenario
    outro = GrupoDeUsuarios(nome="Vizinhos", administrador_id=c.ana.usuario_id)
    outro.membros.extend([usuario(c.ana), usuario(c.bruno)])
    db.session.add(outro)
    db.session.commit()
    c.ana.post(
        "/categorias/{}/compartilhar".format(c.casa.id),
        data={"grupo-{}".format(c.grupo.id): "visualizar", "grupo-{}".format(outro.id): "editar"},
    )

    assert c.casa.permissao_de(usuario(c.bruno)) == "editar"
    assert editar(c.bruno, c.tarefa, nome="Pelo outro grupo").status_code == 302


def test_quadro_da_categoria_mostra_os_grupos_e_o_modo(cenario):
    c = cenario
    url = "/?categoria={}".format(c.casa.id)
    assert 'class="compartilhamentos"' not in c.ana.get(url).get_data(as_text=True)

    vizinhos = GrupoDeUsuarios(nome="Vizinhos", administrador_id=c.ana.usuario_id)
    vizinhos.membros.append(usuario(c.ana))
    db.session.add(vizinhos)
    db.session.commit()
    c.ana.post(
        "/categorias/{}/compartilhar".format(c.casa.id),
        data={"grupo-{}".format(c.grupo.id): "editar", "grupo-{}".format(vizinhos.id): "visualizar"},
    )

    caixa = c.ana.get(url).get_data(as_text=True).split('<ul class="compartilhamentos"')[1].split("</ul>")[0]
    familia, vizinhos_item = caixa.split("<li")[1:]
    assert ">Família<" in familia and 'compartilhamento-editar">Edição<' in familia
    assert ">Vizinhos<" in vizinhos_item and 'compartilhamento-visualizar">Visualização<' in vizinhos_item
    assert "Os membros do grupo <strong>Família</strong> podem editar" in familia
    assert "Os membros do grupo <strong>Vizinhos</strong> podem apenas visualizar" in vizinhos_item
    # Quem recebe a categoria não vê com quem mais ela foi compartilhada.
    assert 'class="compartilhamentos"' not in c.bruno.get(url).get_data(as_text=True)
