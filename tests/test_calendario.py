# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import re
from datetime import date, datetime
from unittest.mock import patch

import pytest

from extensions import db
from models import Categoria, CompartilhamentoDeCategoria, GrupoDeUsuarios, Projeto, Tarefa, Usuario
from routes import inicio_da_semana, periodo_do_calendario, titulo_da_semana

# Sexta-feira, 6 de novembro de 2026.
AGORA = datetime(2026, 11, 6, 10, 0)


def pagina(cliente, consulta=""):
    with patch("routes.agora", return_value=AGORA):
        return cliente.get("/calendario" + consulta).get_data(as_text=True)


def dia(html, iso):
    trecho = html[html.index(f'data-data="{iso}"'):]
    return trecho[:trecho.index("</section>")]


def mover(cliente, tarefa, data):
    with patch("routes.agora", return_value=AGORA):
        return cliente.post(f"/api/tarefas/{tarefa.id}/previsao", json={"data": data})


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


# ---------- Datas


def test_semana_comeca_no_domingo():
    assert inicio_da_semana(date(2026, 11, 6)) == date(2026, 11, 1)
    assert inicio_da_semana(date(2026, 11, 1)) == date(2026, 11, 1)


def test_periodo_do_mes_cobre_semanas_inteiras():
    inicio, fim, anterior, proximo, titulo = periodo_do_calendario("mes", date(2026, 11, 6))
    assert (inicio, fim) == (date(2026, 11, 1), date(2026, 12, 5))
    assert (anterior, proximo, titulo) == (date(2026, 10, 1), date(2026, 12, 1), "Novembro de 2026")


def test_periodo_da_semana():
    inicio, fim, anterior, proximo, titulo = periodo_do_calendario("semana", date(2026, 12, 2))
    assert (inicio, fim, anterior, proximo) == (
        date(2026, 11, 29), date(2026, 12, 5), date(2026, 11, 22), date(2026, 12, 6)
    )
    assert titulo == "29 de novembro a 5 de dezembro de 2026"


def test_titulo_da_semana_na_virada_do_ano():
    assert titulo_da_semana(date(2026, 12, 27), date(2027, 1, 2)) == "27 de dezembro de 2026 a 2 de janeiro de 2027"
    assert titulo_da_semana(date(2026, 11, 1), date(2026, 11, 7)) == "1 a 7 de novembro de 2026"


# ---------- Página


def test_calendario_exige_login(app):
    assert app.test_client().get("/calendario").status_code in (302, 401)


def test_mes_mostra_os_cartoes_nos_dias(cliente, projeto):
    cartao(projeto, "Dentista", datetime(2026, 11, 12, 14, 30))
    cartao(projeto, "Natal", datetime(2026, 12, 25, 9, 0))
    html = pagina(cliente)
    assert "<span>Novembro de 2026</span>" in html
    assert "Dentista" in dia(html, "2026-11-12") and ">14:30<" in dia(html, "2026-11-12")
    assert "Natal" not in html
    assert html.count('<section class="calendario-dia') == 35


def test_hoje_e_dias_de_outro_mes_ficam_marcados(cliente):
    html = pagina(cliente)
    secoes = re.findall(r'<section class="([^"]*)" data-data="([\d-]+)"', html)
    classes = {data: classe.split() for classe, data in secoes}
    assert "calendario-hoje" in classes["2026-11-06"]
    assert "calendario-fora-do-mes" in classes["2026-12-01"]
    assert "calendario-fora-do-mes" not in classes["2026-11-30"]


def test_semana_mostra_sete_dias(cliente, projeto):
    cartao(projeto, "Feira", datetime(2026, 11, 7, 8, 0))
    html = pagina(cliente, "?visao=semana&data=2026-11-04")
    assert html.count('<section class="calendario-dia') == 7
    assert "Feira" in dia(html, "2026-11-07")
    assert 'href="/calendario?visao=semana&amp;data=2026-11-08"' in html


@pytest.mark.parametrize("consulta", ["?visao=ano", "?data=ontem", "?data=2026-13-40"])
def test_parametros_invalidos_voltam_ao_mes_atual(cliente, consulta):
    assert "<span>Novembro de 2026</span>" in pagina(cliente, consulta)


@pytest.mark.parametrize("campos", [{"concluida_em": AGORA}, {"tipo": "video"}])
def test_concluidas_e_videos_ficam_de_fora(cliente, projeto, campos):
    cartao(projeto, "Fora", datetime(2026, 11, 12, 9, 0), **campos)
    assert "Fora" not in pagina(cliente)


def test_atrasado_fica_marcado_e_oculto_tem_o_icone(cliente, projeto):
    cartao(projeto, "Conta", datetime(2026, 11, 3, 9, 0), oculta=True)
    trecho = dia(pagina(cliente), "2026-11-03")
    assert "calendario-vencida" in trecho and "calendario-oculta" in trecho


def test_cartao_do_dono_pode_ser_arrastado(cliente, projeto):
    tarefa = cartao(projeto, "Dentista", datetime(2026, 11, 12, 14, 30))
    trecho = dia(pagina(cliente), "2026-11-12")
    assert f'data-url-previsao="/api/tarefas/{tarefa.id}/previsao"' in trecho
    assert f'href="/?tarefa={tarefa.id}"' in trecho


def test_lateral_e_atalho_do_calendario(cliente):
    html = cliente.get("/").get_data(as_text=True)
    lateral = html.split("</aside>")[0]
    assert 'href="/calendario"' in lateral
    assert lateral.index("Meu Dia") < lateral.index("Calendário") < lateral.index(">Todas<")
    assert "<kbd>C</kbd></dt><dd>Abrir o Calendário" in html


# ---------- Mudar a previsão


def test_mudar_o_dia_mantem_o_horario(cliente, projeto):
    tarefa = cartao(projeto, "Dentista", datetime(2026, 11, 12, 14, 30))
    resposta = mover(cliente, tarefa, "2026-11-20")
    assert resposta.get_json() == {"previsao": "20/11/2026 14:30", "vencida": False}
    assert db.session.get(Tarefa, tarefa.id).previsao_execucao == datetime(2026, 11, 20, 14, 30)


def test_mudar_para_o_passado_avisa_que_venceu(cliente, projeto):
    tarefa = cartao(projeto, "Dentista", datetime(2026, 11, 12, 14, 30))
    assert mover(cliente, tarefa, "2026-11-02").get_json()["vencida"] is True


@pytest.mark.parametrize("corpo", [None, {}, {"data": "amanhã"}, {"data": 5}])
def test_data_invalida(cliente, projeto, corpo):
    tarefa = cartao(projeto, "Dentista", datetime(2026, 11, 12, 14, 30))
    resposta = cliente.post(f"/api/tarefas/{tarefa.id}/previsao", json=corpo)
    assert resposta.status_code == 400
    assert db.session.get(Tarefa, tarefa.id).previsao_execucao == datetime(2026, 11, 12, 14, 30)


def test_sem_previsao_nao_muda(cliente, projeto):
    tarefa = cartao(projeto, "X", None)
    assert mover(cliente, tarefa, "2026-11-20").status_code == 404


def test_video_nao_muda(cliente, projeto):
    tarefa = cartao(projeto, "X", datetime(2026, 11, 12, 9, 0), tipo="video")
    assert mover(cliente, tarefa, "2026-11-20").status_code == 404


def test_outro_usuario_nao_muda(cliente, outro_cliente, projeto):
    tarefa = cartao(projeto, "Dentista", datetime(2026, 11, 12, 14, 30))
    assert mover(outro_cliente, tarefa, "2026-11-20").status_code == 404


@pytest.mark.parametrize("permissao, pode", [("visualizar", False), ("editar", True)])
def test_responsavel_em_categoria_compartilhada(cliente, outro_cliente, permissao, pode):
    """Bruno (outro_cliente) é dono de Obra; Ana (cliente) é a responsável pelo cartão."""
    ana = db.session.get(Usuario, cliente.usuario_id)
    bruno = db.session.get(Usuario, outro_cliente.usuario_id)
    grupo = GrupoDeUsuarios(nome="Equipe", administrador_id=bruno.id)
    grupo.membros.extend([ana, bruno])
    obra = Categoria(nome="Obra", usuario_id=bruno.id)
    db.session.add_all([grupo, obra])
    db.session.flush()
    projeto = Projeto(nome="Etapas", usuario_id=bruno.id, categoria_id=obra.id, posicao=0)
    db.session.add(projeto)
    db.session.add(CompartilhamentoDeCategoria(categoria_id=obra.id, grupo_id=grupo.id, permissao=permissao))
    db.session.commit()
    tarefa = cartao(projeto, "Pintura", datetime(2026, 11, 12, 9, 0), responsavel_id=ana.id)

    trecho = dia(pagina(cliente), "2026-11-12")
    assert "Pintura" in trecho
    assert ("data-url-previsao" in trecho) is pode
    assert f'href="/?tarefa={tarefa.id}&amp;categoria={obra.id}"' in trecho
    assert mover(cliente, tarefa, "2026-11-13").status_code == (200 if pode else 404)


def test_arrasto_do_calendario_vem_antes_da_parada_do_quadro():
    with open("static/js/app.js", encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    assert codigo.index('getElementById("calendario")') < codigo.index("if (!quadro)")
    assert 'pointerType === "touch" && !evento.target.closest(".calendario-alca")' in codigo
