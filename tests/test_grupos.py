# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import pytest

from extensions import db
from icones_grupo import ICONES_GRUPO, icone_grupo
from models import CORES_PROJETO, GrupoDeUsuarios, Usuario

DADOS = {
    "nome": "Brigada",
    "descricao": "Equipe de resposta",
    "cor": CORES_PROJETO[3][0],
    "icone": "chama",
    "ingresso": "administrador",
}


def criar_grupo(cliente, **alteracoes):
    resposta = cliente.post("/grupos/novo", data={**DADOS, **alteracoes})
    assert resposta.status_code == 302
    return GrupoDeUsuarios.query.order_by(GrupoDeUsuarios.id.desc()).first()


def usuario(cliente):
    return db.session.get(Usuario, cliente.usuario_id)


def test_cem_icones_em_onze_categorias():
    assert len(ICONES_GRUPO) == 100
    assert len({chave for chave, _, _ in ICONES_GRUPO}) == 100
    assert len({categoria for _, _, categoria in ICONES_GRUPO}) == 11
    assert "<svg" in icone_grupo("chama")


def test_cabecalho_tem_o_icone_de_grupos(cliente):
    assert 'href="/grupos"' in cliente.get("/").get_data(as_text=True)


def test_grupos_exigem_login(app):
    assert app.test_client().get("/grupos").status_code == 302


def test_criar_grupo_torna_o_criador_administrador_e_membro(cliente):
    grupo = criar_grupo(cliente)

    assert grupo.administrador_id == cliente.usuario_id
    assert [m.id for m in grupo.membros] == [cliente.usuario_id]
    assert (grupo.nome, grupo.icone, grupo.ingresso) == ("Brigada", "chama", "administrador")


@pytest.mark.parametrize(
    "alteracao",
    [
        {"nome": ""},
        {"nome": "x" * 101},
        {"cor": "#000000"},
        {"icone": "inexistente"},
        {"ingresso": "qualquer"},
    ],
)
def test_criar_grupo_recusa_dados_invalidos(cliente, alteracao):
    resposta = cliente.post("/grupos/novo", data={**DADOS, **alteracao})

    assert resposta.status_code == 200
    assert GrupoDeUsuarios.query.count() == 0


def test_listagem_mostra_nome_e_quantidade(cliente, outro_cliente):
    criar_grupo(cliente)
    html = outro_cliente.get("/grupos").get_data(as_text=True)

    assert "Brigada" in html
    # Quem não é membro não vê os membros do grupo.
    assert "Visualizar Membros" not in html
    assert "/editar" not in html and "data-excluir" not in html
    assert "Visualizar Membros" in cliente.get("/grupos").get_data(as_text=True)


def test_listagem_ordenada_pelo_nome_e_reordenavel(cliente):
    for nome in ("Bravo", "alfa", "Charlie"):
        criar_grupo(cliente, nome=nome)

    def nomes(consulta=""):
        html = cliente.get("/grupos" + consulta).get_data(as_text=True)
        return sorted(("alfa", "Bravo", "Charlie"), key=html.index)

    assert nomes() == ["alfa", "Bravo", "Charlie"]
    assert nomes("?ordem=nome&sentido=desc") == ["Charlie", "Bravo", "alfa"]


def test_listagem_ordenada_pela_quantidade_de_usuarios(cliente, outro_cliente):
    criar_grupo(cliente, nome="Pequeno")
    grande = criar_grupo(cliente, nome="Grande")
    grande.membros.append(usuario(outro_cliente))
    db.session.commit()

    html = cliente.get("/grupos?ordem=usuarios&sentido=desc").get_data(as_text=True)

    assert html.index("Grande") < html.index("Pequeno")


def test_ordem_invalida_usa_o_nome(cliente):
    criar_grupo(cliente)

    assert cliente.get("/grupos?ordem=senha").status_code == 200


def test_so_o_administrador_altera_e_exclui(cliente, outro_cliente):
    grupo = criar_grupo(cliente)

    assert outro_cliente.get("/grupos/{}/editar".format(grupo.id)).status_code == 403
    assert outro_cliente.post("/grupos/{}/editar".format(grupo.id), data=DADOS).status_code == 403
    assert outro_cliente.post("/grupos/{}/excluir".format(grupo.id)).status_code == 403
    assert db.session.get(GrupoDeUsuarios, grupo.id) is not None


def test_administrador_altera_o_grupo(cliente):
    grupo = criar_grupo(cliente)
    resposta = cliente.post(
        "/grupos/{}/editar".format(grupo.id),
        data={**DADOS, "nome": "Novo", "icone": "escudo", "ingresso": "qualquer_usuario"},
    )

    assert resposta.status_code == 302
    db.session.refresh(grupo)
    assert (grupo.nome, grupo.icone, grupo.ingresso) == ("Novo", "escudo", "qualquer_usuario")


def test_administrador_exclui_o_grupo(cliente):
    grupo = criar_grupo(cliente)
    cliente.post("/grupos/{}/excluir".format(grupo.id))

    assert GrupoDeUsuarios.query.count() == 0


def test_ingressar_so_quando_qualquer_usuario_pode(cliente, outro_cliente):
    fechado = criar_grupo(cliente)
    aberto = criar_grupo(cliente, ingresso="qualquer_usuario")

    assert outro_cliente.post("/grupos/{}/ingressar".format(fechado.id)).status_code == 403
    assert outro_cliente.post("/grupos/{}/ingressar".format(aberto.id)).status_code == 302
    assert aberto.tem_membro(usuario(outro_cliente))
    assert not fechado.tem_membro(usuario(outro_cliente))


def test_botao_ingressar_aparece_so_para_quem_nao_e_membro(cliente, outro_cliente):
    criar_grupo(cliente, ingresso="qualquer_usuario")

    assert "Ingressar" in outro_cliente.get("/grupos").get_data(as_text=True)
    assert "Ingressar" not in cliente.get("/grupos").get_data(as_text=True)


def test_apenas_administrador_adiciona(cliente, outro_cliente, criar_cliente):
    grupo = criar_grupo(cliente)
    terceiro = criar_cliente("carla@exemplo.com")
    grupo.membros.append(usuario(outro_cliente))
    db.session.commit()

    assert outro_cliente.get("/grupos/{}/adicionar".format(grupo.id)).status_code == 403
    url = "/grupos/{}/adicionar/{}".format(grupo.id, terceiro.usuario_id)
    assert outro_cliente.post(url).status_code == 403
    assert cliente.post(url).status_code == 302
    assert grupo.tem_membro(usuario(terceiro))


def test_membros_adicionam_quando_o_grupo_permite(cliente, outro_cliente, criar_cliente):
    grupo = criar_grupo(cliente, ingresso="qualquer_membro")
    terceiro = criar_cliente("carla@exemplo.com")
    url = "/grupos/{}/adicionar/{}".format(grupo.id, terceiro.usuario_id)

    assert outro_cliente.post(url).status_code == 403
    grupo.membros.append(usuario(outro_cliente))
    db.session.commit()
    assert outro_cliente.post(url).status_code == 302
    assert grupo.tem_membro(usuario(terceiro))


def test_adicionar_nao_aparece_quando_qualquer_usuario_ingressa(cliente):
    grupo = criar_grupo(cliente, ingresso="qualquer_usuario")

    assert cliente.get("/grupos/{}/adicionar".format(grupo.id)).status_code == 403
    assert "Adicionar Membros" not in cliente.get("/grupos").get_data(as_text=True)


def test_adicionar_membros_busca_so_pelo_email_completo(cliente, criar_cliente):
    grupo = criar_grupo(cliente)
    for email, nome in (("z@exemplo.com", "Zélia Souza"), ("a@exemplo.com", "Ana Lima")):
        criar_cliente(email)
        Usuario.query.filter_by(email=email).one().nome = nome
    db.session.commit()
    endereco = "/grupos/{}/adicionar".format(grupo.id)

    # Sem a busca, nenhuma conta é listada.
    html = cliente.get(endereco).get_data(as_text=True)
    assert "Zélia Souza" not in html and "Ana Lima" not in html
    assert "Busque pelo e-mail para encontrar a pessoa." in html

    # Parte do nome ou do e-mail não encontra ninguém.
    for parcial in ("souza", "exemplo.com", "z@"):
        html = cliente.get(endereco + "?busca=" + parcial).get_data(as_text=True)
        assert '<td data-rotulo="E-mail">z@exemplo.com</td>' not in html and '<td data-rotulo="E-mail">a@exemplo.com</td>' not in html

    # O e-mail completo, sem diferenciar maiúsculas, encontra só aquela pessoa.
    html = cliente.get(endereco + "?busca=Z@Exemplo.com").get_data(as_text=True)
    assert '<td data-rotulo="E-mail">z@exemplo.com</td>' in html and '<td data-rotulo="E-mail">a@exemplo.com</td>' not in html

    # Quem já é membro não aparece.
    html = cliente.get(endereco + "?busca=ana@exemplo.com").get_data(as_text=True)
    assert '<td data-rotulo="E-mail">ana@exemplo.com</td>' not in html
    assert "já é membro do grupo" in html


def test_visualizar_membros_mostra_nome_e_email(cliente, outro_cliente):
    grupo = criar_grupo(cliente, ingresso="qualquer_usuario")
    usuario(cliente).nome = "Ana Souza"
    db.session.commit()
    endereco = "/grupos/{}/membros".format(grupo.id)

    # Quem não participa do grupo não vê os nomes e os e-mails dos membros.
    assert outro_cliente.get(endereco).status_code == 403

    outro_cliente.post("/grupos/{}/ingressar".format(grupo.id))
    html = outro_cliente.get(endereco).get_data(as_text=True)

    assert "Ana Souza" in html and "ana@exemplo.com" in html


def test_grupo_inexistente_retorna_404(cliente):
    assert cliente.get("/grupos/999/membros").status_code == 404


def test_excluir_usuario_remove_seus_grupos_e_participacoes(cliente, outro_cliente):
    grupo = criar_grupo(cliente, ingresso="qualquer_usuario")
    outro_cliente.post("/grupos/{}/ingressar".format(grupo.id))
    segundo = criar_grupo(outro_cliente, nome="Do Bruno")

    db.session.delete(usuario(outro_cliente))
    db.session.commit()

    assert db.session.get(GrupoDeUsuarios, segundo.id) is None
    db.session.refresh(grupo)
    assert [m.id for m in grupo.membros] == [cliente.usuario_id]


def test_administrador_do_sistema_nao_administra_grupo_de_outro(cliente, outro_cliente):
    grupo = criar_grupo(cliente)
    usuario(outro_cliente).administrador = True
    db.session.commit()

    assert outro_cliente.get("/grupos/{}/editar".format(grupo.id)).status_code == 403
    assert outro_cliente.post("/grupos/{}/excluir".format(grupo.id)).status_code == 403
    assert outro_cliente.get("/grupos/{}/adicionar".format(grupo.id)).status_code == 403
    assert "/editar" not in outro_cliente.get("/grupos").get_data(as_text=True)


def test_quem_cria_e_o_administrador_mesmo_sem_ser_administrador_do_sistema(cliente):
    assert not usuario(cliente).administrador
    grupo = criar_grupo(cliente)
    html = cliente.get("/grupos/{}/membros".format(grupo.id)).get_data(as_text=True)

    assert grupo.administrador_id == cliente.usuario_id
    assert "Administrador do grupo (quem o criou): ana@exemplo.com" in html
    assert cliente.get("/grupos/{}/editar".format(grupo.id)).status_code == 200


def test_administrador_exclui_membro_do_grupo(cliente, outro_cliente):
    grupo = criar_grupo(cliente)
    grupo.membros.append(usuario(outro_cliente))
    db.session.commit()

    html = cliente.get("/grupos/{}/membros".format(grupo.id)).get_data(as_text=True)
    url = "/grupos/{}/membros/{}/excluir".format(grupo.id, outro_cliente.usuario_id)
    assert 'data-url-excluir="{}"'.format(url) in html
    assert cliente.post(url).status_code == 302

    db.session.refresh(grupo)
    assert [m.id for m in grupo.membros] == [cliente.usuario_id]
    assert db.session.get(Usuario, outro_cliente.usuario_id) is not None  # só sai do grupo


def test_membro_comum_nao_exclui_nem_ve_o_botao(cliente, outro_cliente, criar_cliente):
    grupo = criar_grupo(cliente, ingresso="qualquer_membro")
    terceiro = criar_cliente("carla@exemplo.com")
    grupo.membros.extend([usuario(outro_cliente), usuario(terceiro)])
    db.session.commit()

    assert "data-excluir" not in outro_cliente.get("/grupos/{}/membros".format(grupo.id)).get_data(as_text=True)
    resposta = outro_cliente.post("/grupos/{}/membros/{}/excluir".format(grupo.id, terceiro.usuario_id))
    assert resposta.status_code == 403
    db.session.refresh(grupo)
    assert grupo.tem_membro(usuario(terceiro))


def test_administrador_nao_pode_ser_excluido_do_grupo(cliente):
    grupo = criar_grupo(cliente)

    html = cliente.get("/grupos/{}/membros".format(grupo.id)).get_data(as_text=True)
    assert "O administrador não pode ser excluído" in html and "disabled" in html
    cliente.post("/grupos/{}/membros/{}/excluir".format(grupo.id, cliente.usuario_id))

    db.session.refresh(grupo)
    assert grupo.tem_membro(usuario(cliente))


def test_membro_excluido_perde_a_categoria_compartilhada(cliente, outro_cliente):
    from models import Categoria, CompartilhamentoDeCategoria

    grupo = criar_grupo(cliente)
    grupo.membros.append(usuario(outro_cliente))
    casa = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add(casa)
    db.session.flush()
    db.session.add(CompartilhamentoDeCategoria(categoria_id=casa.id, grupo_id=grupo.id, permissao="editar"))
    db.session.commit()
    assert outro_cliente.get("/?categoria={}".format(casa.id)).status_code == 200

    cliente.post("/grupos/{}/membros/{}/excluir".format(grupo.id, outro_cliente.usuario_id))

    assert outro_cliente.get("/?categoria={}".format(casa.id)).status_code == 404
