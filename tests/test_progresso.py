# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Barra de progresso das listas de tarefas e Resumo da semana do Meu Perfil."""
import re
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from extensions import db
from models import (
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    ItemDaTarefa,
    Projeto,
    Tarefa,
    Usuario,
)

# Sexta-feira, 6 de novembro de 2026: a semana começou no domingo, dia 1.
AGORA = datetime(2026, 11, 6, 10, 0)


@pytest.fixture
def projeto(cliente):
    projeto = Projeto(nome="A fazer", usuario_id=cliente.usuario_id, posicao=0)
    db.session.add(projeto)
    db.session.commit()
    return projeto


def lista_de_tarefas(projeto, feitos, total):
    tarefa = Tarefa(nome="Mudança", projeto_id=projeto.id, tipo="lista_de_tarefas")
    tarefa.itens = [ItemDaTarefa(texto=f"Item {numero}", concluido=numero < feitos, posicao=numero) for numero in range(total)]
    db.session.add(tarefa)
    db.session.commit()
    return tarefa


def progresso(html):
    encontrado = re.search(r'<div class="tarefa-progresso[^>]*>.*?</div>', html, re.S)
    return encontrado.group(0) if encontrado else None


# ---------- Barra de progresso


def test_cartao_mostra_o_progresso(cliente, projeto):
    lista_de_tarefas(projeto, feitos=2, total=6)
    barra = progresso(cliente.get("/").get_data(as_text=True))
    assert 'aria-valuenow="2"' in barra and 'aria-valuemax="6"' in barra
    assert 'style="width: 33%"' in barra
    assert ">2/6<" in barra
    assert "tarefa-progresso-completo" not in barra


def test_progresso_completo_muda_de_cor(cliente, projeto):
    lista_de_tarefas(projeto, feitos=3, total=3)
    barra = progresso(cliente.get("/").get_data(as_text=True))
    assert "tarefa-progresso-completo" in barra and 'style="width: 100%"' in barra


def test_sem_itens_nao_ha_barra(cliente, projeto):
    lista_de_tarefas(projeto, feitos=0, total=0)
    db.session.add(Tarefa(nome="Comum", projeto_id=projeto.id))
    db.session.commit()
    assert progresso(cliente.get("/").get_data(as_text=True)) is None


def test_barra_conta_todas_as_tarefas_e_nao_so_as_tres_do_cartao(cliente, projeto):
    lista_de_tarefas(projeto, feitos=5, total=8)
    html = cliente.get("/").get_data(as_text=True)
    assert ">5/8<" in progresso(html)
    assert "+ 5 tarefas" in html


# ---------- Resumo da semana


def resumo(cliente):
    with patch("routes.agora", return_value=AGORA):
        html = cliente.get("/perfil").get_data(as_text=True)
    secao = html[html.index('class="resumo-semana"'):]
    secao = secao[:secao.index("</section>")]
    return dict(re.findall(r"<dt>([^<]+)</dt>\s*<dd>(\d+)</dd>", secao))


def cartao(projeto, **campos):
    tarefa = Tarefa(nome="X", projeto_id=projeto.id, **campos)
    db.session.add(tarefa)
    db.session.commit()
    return tarefa


def test_resumo_conta_as_concluidas_por_semana(cliente, projeto):
    cartao(projeto, concluida_em=datetime(2026, 11, 1, 0, 0))  # Domingo: já é desta semana.
    cartao(projeto, concluida_em=datetime(2026, 11, 5, 18, 0))
    cartao(projeto, concluida_em=datetime(2026, 10, 31, 23, 59))  # Sábado: semana passada.
    cartao(projeto, concluida_em=datetime(2026, 10, 20, 9, 0))  # Mais antiga: não conta.
    numeros = resumo(cliente)
    assert numeros["Concluídas nesta semana"] == "2"
    assert numeros["Na semana passada"] == "1"


def test_resumo_conta_atrasadas_e_proximas(cliente, projeto):
    cartao(projeto, previsao_execucao=AGORA - timedelta(days=3))
    cartao(projeto, previsao_execucao=AGORA + timedelta(hours=5))
    cartao(projeto, previsao_execucao=AGORA + timedelta(days=6))
    cartao(projeto, previsao_execucao=AGORA + timedelta(days=20))
    cartao(projeto, previsao_execucao=AGORA - timedelta(days=1), concluida_em=AGORA - timedelta(hours=1))
    numeros = resumo(cliente)
    assert numeros["Atrasadas"] == "1"
    assert numeros["Previstas para 7 dias"] == "2"
    assert numeros["Concluídas nesta semana"] == "1"


def test_resumo_vazio(cliente):
    assert set(resumo(cliente).values()) == {"0"}


def test_atrasadas_ficam_em_destaque(cliente, projeto):
    cartao(projeto, previsao_execucao=AGORA - timedelta(days=1))
    with patch("routes.agora", return_value=AGORA):
        html = cliente.get("/perfil").get_data(as_text=True)
    assert re.search(r'<div class="resumo-alerta">\s*<dt>Atrasadas</dt>', html)


def test_resumo_nao_conta_o_de_outro_usuario(cliente, outro_cliente):
    outra = Projeto(nome="Dele", usuario_id=outro_cliente.usuario_id, posicao=0)
    db.session.add(outra)
    db.session.commit()
    cartao(outra, concluida_em=AGORA - timedelta(hours=1))
    assert resumo(cliente)["Concluídas nesta semana"] == "0"


def test_resumo_conta_o_cartao_de_que_e_responsavel(cliente, outro_cliente):
    ana = db.session.get(Usuario, cliente.usuario_id)
    bruno = db.session.get(Usuario, outro_cliente.usuario_id)
    grupo = GrupoDeUsuarios(nome="Equipe", administrador_id=bruno.id)
    grupo.membros.extend([ana, bruno])
    obra = Categoria(nome="Obra", usuario_id=bruno.id)
    db.session.add_all([grupo, obra])
    db.session.flush()
    etapas = Projeto(nome="Etapas", usuario_id=bruno.id, categoria_id=obra.id, posicao=0)
    db.session.add(etapas)
    db.session.add(CompartilhamentoDeCategoria(categoria_id=obra.id, grupo_id=grupo.id, permissao="editar"))
    db.session.commit()
    cartao(etapas, concluida_em=AGORA - timedelta(hours=1), responsavel_id=ana.id)
    cartao(etapas, concluida_em=AGORA - timedelta(hours=1))
    assert resumo(cliente)["Concluídas nesta semana"] == "1"
    # Sem acesso à categoria, o cartão deixa de contar.
    grupo.membros.remove(ana)
    db.session.commit()
    assert resumo(cliente)["Concluídas nesta semana"] == "0"


def test_resumo_vem_antes_do_formulario(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)
    assert html.index("Resumo da semana") < html.index('<label for="nome">')
