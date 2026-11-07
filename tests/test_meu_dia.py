# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from extensions import db
from models import (
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    Projeto,
    Tarefa,
    Usuario,
)
from routes import data_por_extenso

# Sexta-feira, 6 de novembro de 2026, às 10h.
AGORA = datetime(2026, 11, 6, 10, 0)


def pagina(cliente):
    with patch("routes.agora", return_value=AGORA):
        return cliente.get("/meu-dia").get_data(as_text=True)


def grupo(html, chave):
    """O trecho do grupo, ou None se ele não aparece."""
    marcador = f'class="meu-dia-grupo meu-dia-{chave}"'
    if marcador not in html:
        return None
    trecho = html[html.index(marcador):]
    return trecho[:trecho.index("</section>")]


@pytest.fixture
def projeto(cliente):
    casa = Categoria(nome="Casa", usuario_id=cliente.usuario_id)
    db.session.add(casa)
    db.session.flush()
    projeto = Projeto(nome="A fazer", usuario_id=cliente.usuario_id, categoria_id=casa.id, posicao=0)
    db.session.add(projeto)
    db.session.commit()
    return projeto


def cartao(projeto, nome, previsao, **campos):
    tarefa = Tarefa(nome=nome, projeto_id=projeto.id, previsao_execucao=previsao, **campos)
    db.session.add(tarefa)
    db.session.commit()
    return tarefa


def test_data_por_extenso():
    assert data_por_extenso(date(2026, 11, 6)) == "sexta-feira, 6 de novembro"
    assert data_por_extenso(date(2026, 3, 1)) == "domingo, 1 de março"


def test_meu_dia_exige_login(app):
    resposta = app.test_client().get("/meu-dia")
    assert resposta.status_code in (302, 401)


def test_separa_os_cartoes_por_data(cliente, projeto):
    cartao(projeto, "Pagar a conta", AGORA - timedelta(days=2))
    cartao(projeto, "Reunião", AGORA.replace(hour=15))
    cartao(projeto, "Dentista", AGORA + timedelta(days=1))
    cartao(projeto, "Viagem", AGORA + timedelta(days=5))
    cartao(projeto, "Muito longe", AGORA + timedelta(days=9))
    cartao(projeto, "Sem data", None)
    html = pagina(cliente)

    assert "Pagar a conta" in grupo(html, "atrasadas") and "04/11 10:00" in grupo(html, "atrasadas")
    assert "Reunião" in grupo(html, "hoje") and ">15:00<" in grupo(html, "hoje")
    assert "Dentista" in grupo(html, "amanha")
    assert "Viagem" in grupo(html, "proximos") and "11/11 10:00" in grupo(html, "proximos")
    assert "Muito longe" not in html and "Sem data" not in html
    assert "Sexta-feira, 6 de novembro" in html


def test_hoje_mais_cedo_conta_como_atrasada(cliente, projeto):
    cartao(projeto, "Café", AGORA.replace(hour=8))
    html = pagina(cliente)
    assert "Café" in grupo(html, "atrasadas")
    assert grupo(html, "hoje") is None


def test_limite_inclui_o_setimo_dia_inteiro(cliente, projeto):
    cartao(projeto, "Último dia", datetime(2026, 11, 13, 23, 59))
    cartao(projeto, "Oitavo dia", datetime(2026, 11, 14, 0, 0))
    html = pagina(cliente)
    assert "Último dia" in html and "Oitavo dia" not in html


@pytest.mark.parametrize("ajuste", ["concluida", "video", "projeto_concluido"])
def test_ficam_de_fora(cliente, projeto, ajuste):
    campos = {"concluida_em": AGORA} if ajuste == "concluida" else {"tipo": "video"} if ajuste == "video" else {}
    cartao(projeto, "Fora", AGORA + timedelta(hours=2), **campos)
    if ajuste == "projeto_concluido":
        projeto.concluida = True
        db.session.commit()
    assert "Fora" not in pagina(cliente)


def test_oculta_aparece_marcada(cliente, projeto):
    cartao(projeto, "Escondida", AGORA + timedelta(hours=2), oculta=True)
    hoje = grupo(pagina(cliente), "hoje")
    assert "Escondida" in hoje and "meu-dia-oculta" in hoje


def test_sem_cartoes_mostra_o_vazio(cliente):
    html = pagina(cliente)
    assert "Nada previsto para os próximos dias" in html
    assert "meu-dia-grupo" not in html


def test_link_abre_o_cartao_no_quadro(cliente, projeto):
    tarefa = cartao(projeto, "Reunião", AGORA + timedelta(hours=3))
    assert f'href="/?tarefa={tarefa.id}"' in pagina(cliente)


def test_cartoes_de_outro_usuario_nao_aparecem(cliente, outro_cliente, projeto):
    outra = Projeto(nome="Dele", usuario_id=outro_cliente.usuario_id, posicao=0)
    db.session.add(outra)
    db.session.commit()
    cartao(outra, "Segredo", AGORA + timedelta(hours=1))
    assert "Segredo" not in pagina(cliente)


@pytest.fixture
def compartilhado(cliente, outro_cliente):
    """Bruno (outro_cliente) é dono de Obra, compartilhada com o grupo dele e de Ana (cliente)."""
    ana = db.session.get(Usuario, cliente.usuario_id)
    bruno = db.session.get(Usuario, outro_cliente.usuario_id)
    bruno.nome = "Bruno"
    grupo_ = GrupoDeUsuarios(nome="Equipe", administrador_id=bruno.id)
    grupo_.membros.extend([ana, bruno])
    obra = Categoria(nome="Obra", usuario_id=bruno.id)
    db.session.add_all([grupo_, obra])
    db.session.flush()
    projeto = Projeto(nome="Etapas", usuario_id=bruno.id, categoria_id=obra.id, posicao=0)
    db.session.add(projeto)
    db.session.add(CompartilhamentoDeCategoria(categoria_id=obra.id, grupo_id=grupo_.id, permissao="editar"))
    db.session.commit()
    return ana, bruno, grupo_, obra, projeto


def test_responsavel_ve_o_cartao_compartilhado(cliente, compartilhado):
    ana, bruno, _, obra, projeto = compartilhado
    tarefa = cartao(projeto, "Pintura", AGORA + timedelta(days=1), responsavel_id=ana.id)
    cartao(projeto, "Elétrica", AGORA + timedelta(days=1))
    bruno.aviso_destinatarios = "proprietario"  # A escolha da Automação não vale para o Meu Dia.
    db.session.commit()
    amanha = grupo(pagina(cliente), "amanha")

    assert "Pintura" in amanha and "Elétrica" not in amanha
    assert f'href="/?tarefa={tarefa.id}&amp;categoria={obra.id}"' in amanha
    assert "Proprietário: Bruno" in amanha


def test_responsavel_que_perdeu_o_acesso_nao_ve(cliente, compartilhado):
    ana, _, grupo_, _, projeto = compartilhado
    cartao(projeto, "Pintura", AGORA + timedelta(days=1), responsavel_id=ana.id)
    grupo_.membros.remove(ana)
    db.session.commit()
    assert "Pintura" not in pagina(cliente)


def test_lateral_do_quadro_tem_o_meu_dia(cliente):
    lateral = cliente.get("/").get_data(as_text=True).split("</aside>")[0]
    assert 'href="/meu-dia"' in lateral and "data-meu-dia" in lateral
    assert lateral.index("Meu Dia") < lateral.index(">Todas<")


def test_atalho_d_abre_o_meu_dia(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert "<kbd>D</kbd></dt><dd>Abrir o Meu Dia" in html
    with open("static/js/app.js", encoding="utf-8") as arquivo:
        assert '"[data-meu-dia]"' in arquivo.read()
