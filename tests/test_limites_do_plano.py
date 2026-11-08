# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import json

import pytest

import youtube
from extensions import db
from models import (
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    Projeto,
    PlanoDeUsuario,
    Tarefa,
    Usuario,
)

DADOS_DO_PLANO = {
    "nome": "Básico", "armazenamento_mb": "10", "categorias": "10", "projetos": "10",
    "atividades": "50", "listas_de_tarefas": "50", "videos": "50", "dias_de_inatividade": "",
}


def usuario(cliente):
    return db.session.get(Usuario, cliente.usuario_id)


def limitar(cliente, **limites):
    """Coloca o usuário num plano com os limites dados; os demais ficam Ilimitadas."""
    plano = PlanoDeUsuario(nome="Limitado {}".format(cliente.usuario_id), armazenamento_mb=10, **limites)
    db.session.add(plano)
    usuario(cliente).plano = plano
    db.session.commit()
    return plano


def mensagens(cliente):
    with cliente.session_transaction() as sessao:
        return [texto for _, texto in sessao.get("_flashes", [])]


@pytest.fixture
def administrador(cliente):
    usuario(cliente).administrador = True
    db.session.commit()
    return cliente


@pytest.fixture
def youtube_falso(monkeypatch):
    def pagina(codigo):
        detalhes = {"videoId": codigo, "title": "Vídeo", "author": "Autor", "lengthSeconds": "10"}
        return "ytInitialPlayerResponse = {};".format(json.dumps({"videoDetails": detalhes}))

    monkeypatch.setattr(youtube, "baixar_pagina", pagina)


def nova_atividade(cliente, projeto, tipo="atividade", nome="Nova"):
    return cliente.post("/tarefas", data={"nome": nome, "prioridade": "baixa", "projeto_id": projeto.id, "tipo": tipo})


def test_limite_de_categorias(cliente, criar_categoria):
    limitar(cliente, categorias=1)
    criar_categoria(cliente.usuario_id)

    cliente.post("/categorias", data={"nome": "Outra", "icone": "etiqueta"})

    assert Categoria.query.filter_by(usuario_id=cliente.usuario_id).count() == 1
    assert "O seu plano permite até 1 categorias." in mensagens(cliente)


def test_limite_de_projetos(cliente, criar_categoria, criar_projeto):
    limitar(cliente, projetos=1)
    categoria = criar_categoria(cliente.usuario_id)
    criar_projeto(cliente.usuario_id)

    cliente.post("/projetos", data={"nome": "Outra", "cor": "#1a6fe0", "categoria_id": categoria.id})

    assert Projeto.query.count() == 1
    assert "O seu plano permite até 1 projetos." in mensagens(cliente)


@pytest.mark.parametrize("tipo, limite, rotulo", [
    ("atividade", "atividades", "demandas"),
    ("lista_de_tarefas", "listas_de_tarefas", "listas de tarefas"),
])
def test_limite_de_atividades_e_listas_de_tarefas(cliente, criar_projeto, tipo, limite, rotulo):
    limitar(cliente, **{limite: 2})
    projeto = criar_projeto(cliente.usuario_id)
    for numero in range(2):
        nova_atividade(cliente, projeto, tipo, "Item {}".format(numero))

    nova_atividade(cliente, projeto, tipo, "Terceiro")

    assert Tarefa.query.filter_by(tipo=tipo).count() == 2
    assert "O seu plano permite até 2 {}.".format(rotulo) in mensagens(cliente)


def test_cada_tipo_tem_o_seu_limite(cliente, criar_projeto):
    limitar(cliente, atividades=1, listas_de_tarefas=5)
    projeto = criar_projeto(cliente.usuario_id)
    nova_atividade(cliente, projeto)

    nova_atividade(cliente, projeto, "lista_de_tarefas")

    assert Tarefa.query.filter_by(tipo="lista_de_tarefas").count() == 1


def test_limite_de_videos(cliente, criar_projeto, youtube_falso):
    limitar(cliente, videos=1)
    projeto = criar_projeto(cliente.usuario_id)
    endereco = "https://youtu.be/jNQXAC9IVRw"
    assert cliente.post("/api/videos", json={"projeto_id": projeto.id, "endereco": endereco}).status_code == 201

    resposta = cliente.post("/api/videos", json={"projeto_id": projeto.id, "endereco": endereco})

    assert resposta.status_code == 422
    assert resposta.get_json()["erro"] == "O seu plano permite até 1 vídeos."
    assert Tarefa.query.filter_by(tipo="video").count() == 1


def test_ocultas_e_concluidas_tambem_contam(cliente, criar_projeto, criar_tarefa):
    limitar(cliente, atividades=1)
    projeto = criar_projeto(cliente.usuario_id)
    tarefa = criar_tarefa(projeto)
    tarefa.oculta = True
    db.session.commit()

    nova_atividade(cliente, projeto)

    assert Tarefa.query.count() == 1


def test_ilimitadas_nao_bloqueia(cliente, criar_projeto):
    limitar(cliente)
    projeto = criar_projeto(cliente.usuario_id)
    for numero in range(3):
        nova_atividade(cliente, projeto, nome="Item {}".format(numero))

    assert Tarefa.query.count() == 3


def test_limite_e_por_usuario(cliente, outro_cliente, criar_projeto):
    limitar(cliente, atividades=1)
    nova_atividade(cliente, criar_projeto(cliente.usuario_id))

    nova_atividade(outro_cliente, criar_projeto(outro_cliente.usuario_id))

    assert Tarefa.query.count() == 2


def test_rebaixar_o_plano_nao_apaga_nada(cliente, criar_projeto, criar_tarefa):
    projeto = criar_projeto(cliente.usuario_id)
    for numero in range(3):
        criar_tarefa(projeto, nome="Item {}".format(numero))

    limitar(cliente, atividades=1)
    nova_atividade(cliente, projeto)

    assert Tarefa.query.count() == 3


def test_na_categoria_compartilhada_vale_o_plano_do_dono(cliente, outro_cliente):
    limitar(cliente, atividades=1)
    casa = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=cliente.usuario_id)
    grupo.membros.extend([usuario(cliente), usuario(outro_cliente)])
    db.session.add_all([casa, grupo])
    db.session.flush()
    projeto = Projeto(nome="Feira", usuario_id=cliente.usuario_id, categoria_id=casa.id)
    db.session.add_all([projeto, CompartilhamentoDeCategoria(categoria_id=casa.id, grupo_id=grupo.id, permissao="editar")])
    db.session.commit()
    usuario(cliente).nome = "Ana Souza"
    db.session.commit()
    nova_atividade(cliente, projeto)

    nova_atividade(outro_cliente, projeto, nome="Do Bruno")

    assert Tarefa.query.count() == 1
    assert "O plano de Ana Souza permite até 1 demandas." in mensagens(outro_cliente)


def test_formulario_do_plano_tem_a_opcao_de_padrao(administrador):
    html = administrador.get("/administracao/planos/novo").get_data(as_text=True)

    assert 'name="padrao"' in html and "Plano padrão para novas contas" in html


def test_marcar_um_plano_como_padrao_desmarca_o_anterior(administrador):
    antigo = PlanoDeUsuario.query.filter_by(padrao=True).one()

    administrador.post("/administracao/planos/novo", data={**DADOS_DO_PLANO, "padrao": "y"})

    db.session.expire_all()
    assert [plano.nome for plano in PlanoDeUsuario.query.filter_by(padrao=True)] == ["Básico"]
    assert db.session.get(PlanoDeUsuario, antigo.id).padrao is False


def test_nao_desmarca_o_unico_plano_padrao(administrador):
    padrao = PlanoDeUsuario.query.filter_by(padrao=True).one()

    resposta = administrador.post(
        "/administracao/planos/{}/editar".format(padrao.id),
        data={**DADOS_DO_PLANO, "nome": padrao.nome, "armazenamento_mb": "10"},
    )

    assert "Para desmarcar, marque outro plano como padrão." in resposta.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(PlanoDeUsuario, padrao.id).padrao is True


def test_nao_exclui_plano_com_usuarios(administrador, outro_cliente):
    plano = limitar(outro_cliente)

    html = administrador.get("/administracao/planos").get_data(as_text=True)
    linha = html.split("<td>{}".format(plano.nome))[1].split("</tr>")[0]
    assert "disabled" in linha and "Este plano tem usuários" in linha

    administrador.post("/administracao/planos/{}/excluir".format(plano.id))
    assert db.session.get(PlanoDeUsuario, plano.id) is not None
    assert "Este plano tem usuários: mude o plano deles antes de excluí-lo." in mensagens(administrador)


def test_nao_exclui_o_plano_padrao(administrador):
    padrao = PlanoDeUsuario.query.filter_by(padrao=True).one()
    for conta in Usuario.query:
        conta.plano = None
    db.session.commit()

    administrador.post("/administracao/planos/{}/excluir".format(padrao.id))

    assert db.session.get(PlanoDeUsuario, padrao.id) is not None
    assert any("plano padrão não pode ser excluído" in texto for texto in mensagens(administrador))


def test_listagem_marca_o_plano_padrao(administrador):
    html = administrador.get("/administracao/planos").get_data(as_text=True)

    assert '<td>Iniciante <span class="selo-padrao">Padrão</span></td>' in html
    assert '<td class="tabela-capacidades" data-rotulo="Capacidades">10 MB / * / * / * / * / * / *</td>' in html


def test_rodape_mostra_o_nome_do_plano(cliente):
    limitar(cliente)

    lateral = cliente.get("/").get_data(as_text=True).split('<aside class="lateral"')[1].split("</aside>")[0]

    assert "Limitado {}: 0 MB de 10 MB".format(cliente.usuario_id) in lateral
