# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import io

import pytest
from PIL import Image
from sqlalchemy import inspect

from extensions import db
from foto_do_perfil import LADO_DA_FOTO, TAMANHO_MAXIMO_DA_FOTO, FotoInvalida, preparar_foto
from models import AVATAR_FOTO, AVATAR_PADRAO, Categoria, GrupoDeUsuarios, Projeto, Tarefa, Usuario


def png(lado=LADO_DA_FOTO, cor=(200, 30, 30, 255), formato="PNG"):
    saida = io.BytesIO()
    Image.new("RGBA" if formato == "PNG" else "RGB", (lado, lado), cor[:4] if formato == "PNG" else cor[:3]).save(
        saida, format=formato
    )
    return saida.getvalue()


def enviar_foto(cliente, conteudo=None):
    return cliente.post(
        "/api/perfil/foto",
        data={"foto": (io.BytesIO(png() if conteudo is None else conteudo), "foto.png")},
        content_type="multipart/form-data",
    )


def arquivos(app):
    pasta = app.config["ANEXOS_DIR"]
    return sorted(caminho.name for caminho in pasta.iterdir()) if pasta.exists() else []


# ---------- Recorte (foto_do_perfil.py)


def test_preparar_foto_deixa_transparente_fora_do_circulo():
    imagem = Image.open(io.BytesIO(preparar_foto(png())))

    assert imagem.format == "PNG" and imagem.size == (300, 300) and imagem.mode == "RGBA"
    assert imagem.getpixel((0, 0))[3] == 0
    assert imagem.getpixel((299, 299))[3] == 0
    assert imagem.getpixel((150, 150)) == (200, 30, 30, 255)
    # Logo dentro da borda do círculo, ainda opaco.
    assert imagem.getpixel((150, 5))[3] == 255


@pytest.mark.parametrize("conteudo", [
    b"", b"texto", b"<svg onload=alert(1)>", png(lado=299), png(lado=301), png(formato="JPEG"),
    b"\x89PNG\r\n\x1a\n" + b"0" * 50,
])
def test_preparar_foto_recusa_o_que_nao_e_o_recorte(conteudo):
    with pytest.raises(FotoInvalida):
        preparar_foto(conteudo)


def test_preparar_foto_recusa_arquivo_grande():
    with pytest.raises(FotoInvalida):
        preparar_foto(png() + b"0" * TAMANHO_MAXIMO_DA_FOTO)


# ---------- Rotas


def test_enviar_foto_grava_png_e_passa_a_ser_o_icone(app, cliente):
    resposta = enviar_foto(cliente)

    usuario = db.session.get(Usuario, cliente.usuario_id)
    assert resposta.status_code == 200
    assert resposta.get_json()["url"] == "/fotos/{}".format(usuario.foto)
    assert usuario.avatar == AVATAR_FOTO
    assert usuario.foto.startswith("foto-") and usuario.foto.endswith(".png")
    assert arquivos(app) == [usuario.foto]
    gravada = Image.open(app.config["ANEXOS_DIR"] / usuario.foto)
    assert gravada.size == (300, 300) and gravada.getpixel((0, 0))[3] == 0


def test_nova_foto_apaga_a_anterior(app, cliente):
    enviar_foto(cliente)
    primeira = db.session.get(Usuario, cliente.usuario_id).foto

    enviar_foto(cliente, png(cor=(0, 0, 255, 255)))

    segunda = db.session.get(Usuario, cliente.usuario_id).foto
    assert segunda != primeira
    assert arquivos(app) == [segunda]


def test_cada_usuario_tem_um_nome_aleatorio(cliente, outro_cliente):
    enviar_foto(cliente)
    enviar_foto(outro_cliente)

    assert db.session.get(Usuario, cliente.usuario_id).foto != db.session.get(Usuario, outro_cliente.usuario_id).foto


def test_enviar_foto_recusa_imagem_invalida(app, cliente):
    resposta = enviar_foto(cliente, png(lado=400))

    assert resposta.status_code == 400
    assert resposta.get_json()["erro"] == "Envie a foto pela caixa Ajustar minha imagem do perfil."
    usuario = db.session.get(Usuario, cliente.usuario_id)
    assert usuario.foto == "" and usuario.avatar == AVATAR_PADRAO
    assert arquivos(app) == []


def test_enviar_foto_sem_arquivo_e_recusado(cliente):
    assert cliente.post("/api/perfil/foto").status_code == 400


def test_enviar_foto_exige_login(app):
    assert app.test_client().post("/api/perfil/foto").status_code in (302, 401)


def test_ver_foto(cliente, outro_cliente):
    url = enviar_foto(cliente).get_json()["url"]

    resposta = outro_cliente.get(url)

    assert resposta.status_code == 200
    assert resposta.mimetype == "image/png"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"


def test_ver_foto_inexistente_e_404(cliente):
    assert cliente.get("/fotos/foto-inexistente.png").status_code == 404
    assert cliente.get("/fotos/..%2Fteste.db").status_code == 404


def test_ver_foto_exige_login(app, cliente):
    url = enviar_foto(cliente).get_json()["url"]

    assert app.test_client().get(url).status_code in (302, 401)


# ---------- Meu Perfil


def test_perfil_tem_enviar_minha_foto_abaixo_do_titulo_icone(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)

    assert "Enviar minha foto" in html
    assert html.index('<h2 id="icone-titulo">Ícone</h2>') < html.index("data-enviar-foto") < html.index('class="avatares-opcoes"')
    assert '<fieldset class="avatares" aria-labelledby="icone-titulo">' in html
    assert 'accept="image/*"' in html
    assert "Ajustar minha imagem do perfil" in html
    assert "Utilizar dessa forma" in html


def test_sem_foto_a_opcao_fica_escondida(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)
    opcao = html[html.index("data-opcao-da-foto"):]
    opcao = opcao[:opcao.index(">")]

    assert "hidden" in opcao


def test_foto_e_o_primeiro_icone_da_lista(cliente):
    url = enviar_foto(cliente).get_json()["url"]

    html = cliente.get("/perfil").get_data(as_text=True)
    lista = html[html.index('class="avatares-opcoes"'):]
    primeiro = lista[:lista.index("</label>")]

    assert 'value="foto"' in primeiro and 'src="{}"'.format(url) in primeiro
    assert "checked" in primeiro and "hidden" not in primeiro


def test_trocar_para_um_desenho_mantem_a_foto_na_lista(cliente):
    enviar_foto(cliente)

    cliente.post("/perfil", data={"nome": "Ana Souza", "avatar": "feminino-curto"})

    usuario = db.session.get(Usuario, cliente.usuario_id)
    assert usuario.avatar == "feminino-curto" and usuario.foto
    cliente.post("/perfil", data={"nome": "Ana Souza", "avatar": AVATAR_FOTO})
    assert db.session.get(Usuario, cliente.usuario_id).avatar == AVATAR_FOTO


def test_escolher_foto_sem_ter_foto_e_ignorado(cliente):
    cliente.post("/perfil", data={"nome": "Ana Souza", "avatar": AVATAR_FOTO})

    assert db.session.get(Usuario, cliente.usuario_id).avatar == AVATAR_PADRAO


# ---------- A foto em todo o sistema


def test_foto_aparece_no_cabecalho(cliente):
    url = enviar_foto(cliente).get_json()["url"]

    html = cliente.get("/meu-dia").get_data(as_text=True)
    botao = html[html.index("botao-usuario"):]
    botao = botao[:botao.index("</button>")]

    assert '<img class="avatar avatar-foto" src="{}"'.format(url) in botao


def test_desenho_continua_sem_foto_escolhida(cliente):
    enviar_foto(cliente)
    cliente.post("/perfil", data={"nome": "Ana Souza", "avatar": "feminino-curto"})

    html = cliente.get("/meu-dia").get_data(as_text=True)
    botao = html[html.index("botao-usuario"):]
    botao = botao[:botao.index("</button>")]

    assert "avatar-foto" not in botao and '<svg class="avatar"' in botao


def test_foto_aparece_no_cartao_e_nos_membros_do_grupo(app, cliente):
    url = enviar_foto(cliente).get_json()["url"]
    categoria = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add(categoria)
    db.session.flush()
    projeto = Projeto(nome="A fazer", usuario_id=cliente.usuario_id, categoria_id=categoria.id, posicao=0)
    db.session.add(projeto)
    db.session.flush()
    db.session.add(Tarefa(nome="Feira", projeto_id=projeto.id, posicao=0))
    db.session.commit()

    quadro = cliente.get("/").get_data(as_text=True)
    assert quadro.count('src="{}"'.format(url)) >= 2  # o cabeçalho e o proprietário do cartão

    ana = db.session.get(Usuario, cliente.usuario_id)
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=ana.id)
    grupo.membros.append(ana)
    db.session.add(grupo)
    db.session.commit()
    membros = cliente.get("/grupos/{}/membros".format(grupo.id)).get_data(as_text=True)
    tabela = membros[membros.index("<tbody>"):]
    assert 'src="{}"'.format(url) in tabela


def test_excluir_usuario_apaga_a_foto(app, cliente, outro_cliente):
    enviar_foto(outro_cliente)
    assert arquivos(app)
    db.session.get(Usuario, cliente.usuario_id).administrador = True
    db.session.commit()

    cliente.post("/administracao/usuarios/{}/excluir".format(outro_cliente.usuario_id))

    assert db.session.get(Usuario, outro_cliente.usuario_id) is None
    assert arquivos(app) == []


def test_coluna_foto_existe(app):
    colunas = {coluna["name"] for coluna in inspect(db.engine).get_columns("usuario")}

    assert "foto" in colunas
