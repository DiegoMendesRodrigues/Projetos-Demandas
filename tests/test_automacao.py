# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
import threading
from datetime import datetime, timedelta

import pytest

import avisos
from extensions import db, mail
from models import (
    AvisoEnviado,
    Categoria,
    CompartilhamentoDeCategoria,
    GrupoDeUsuarios,
    Projeto,
    Tarefa,
    Usuario,
    VideoDoYoutube,
)

AGORA = datetime(2026, 11, 10, 9, 0)


def usuario(cliente):
    return db.session.get(Usuario, cliente.usuario_id)


@pytest.fixture
def email_configurado(app):
    app.config.update(MAIL_SERVER="smtp.exemplo.com", MAIL_DEFAULT_SENDER=("Projetos & Demandas", "nao-responda@exemplo.com"))


@pytest.fixture
def cenario(cliente, outro_cliente):
    """Ana tem a categoria Casa compartilhada com Bruno; o cartão Feira tem Bruno como responsável."""
    ana, bruno = usuario(cliente), usuario(outro_cliente)
    ana.nome, bruno.nome = "Ana", "Bruno"
    grupo = GrupoDeUsuarios(nome="Família", administrador_id=ana.id)
    grupo.membros.extend([ana, bruno])
    casa = Categoria(nome="Casa", usuario_id=ana.id)
    db.session.add_all([grupo, casa])
    db.session.flush()
    projeto = Projeto(nome="A fazer", usuario_id=ana.id, categoria_id=casa.id, posicao=0)
    db.session.add(projeto)
    db.session.flush()
    db.session.add(CompartilhamentoDeCategoria(categoria_id=casa.id, grupo_id=grupo.id, permissao="editar"))
    tarefa = Tarefa(nome="Feira", projeto_id=projeto.id, previsao_execucao=AGORA + timedelta(days=1), responsavel_id=bruno.id)
    db.session.add(tarefa)
    db.session.commit()
    return ana, bruno, projeto, tarefa


def enviar(momento=AGORA):
    with mail.record_messages() as enviadas:
        total = avisos.enviar_avisos(momento)
    assert total == len(enviadas)
    return enviadas


# ---------- Meu Perfil


def test_perfil_tem_a_automacao_com_os_valores_iniciais(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)
    assert '<h2 id="automacao-titulo">Automação</h2>' in html
    assert '<option selected value="responsavel_e_proprietario">Responsável e Proprietário do cartão</option>' in html
    assert '<option value="proprietario">Proprietário do cartão</option>' in html
    assert '<option selected value="2">2 dias</option>' in html
    assert html.index("3 dias") < html.index("2 dias") < html.index("1 dia<")
    assert html.index("Cor da Aplicação") < html.index("Automação</h2>")


def test_perfil_salva_a_automacao(cliente):
    cliente.post("/perfil", data={"nome": "Ana Souza", "aviso_destinatarios": "proprietario", "aviso_antecedencia": "3"})
    ana = usuario(cliente)
    assert (ana.aviso_destinatarios, ana.aviso_antecedencia) == ("proprietario", 3)


@pytest.mark.parametrize("campo, valor", [("aviso_destinatarios", "todos"), ("aviso_antecedencia", "5")])
def test_automacao_recusa_valores_fora_da_lista(cliente, campo, valor):
    html = cliente.post("/perfil", data={"nome": "Ana Souza", campo: valor}).get_data(as_text=True)
    assert "erro-campo" in html
    ana = usuario(cliente)
    assert (ana.aviso_destinatarios, ana.aviso_antecedencia) == ("responsavel_e_proprietario", 2)


def test_perfil_tem_cancelar_para_o_quadro_e_salvar(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)
    acoes = html[html.index('class="perfil-acoes"'):]
    assert '<a class="botao" href="/">Cancelar</a>' in acoes
    assert acoes.index("Cancelar") < acoes.index("Salvar")


def test_perfil_tem_duas_colunas(cliente):
    html = cliente.get("/perfil").get_data(as_text=True)
    colunas = html[html.index('class="perfil-colunas"'):html.index('class="perfil-acoes"')]
    esquerda, direita = colunas.split('class="perfil-coluna"')[1:]
    ordem = ["Resumo da semana", 'id="nome"', 'id="email"', 'id="telefone"', 'class="cores-da-aplicacao"']
    assert [esquerda.index(item) for item in ordem] == sorted(esquerda.index(item) for item in ordem)
    for item in ["data-enviar-foto", 'class="avatares"', 'class="automacao"']:
        assert item in direita and item not in esquerda


# ---------- Avisos por e-mail


def test_aviso_de_vencimento_vai_ao_proprietario_e_ao_responsavel(cenario, email_configurado):
    ana, bruno, _, _ = cenario
    enviadas = enviar()
    assert sorted(m.recipients[0] for m in enviadas) == sorted([ana.email, bruno.email])
    assert enviadas[0].subject == "Projetos & Demandas: “Feira” vence em breve"
    assert "vence em 11/11/2026 às 09:00" in enviadas[0].body
    assert "Responsável: Bruno" in enviadas[0].html


def test_aviso_nao_se_repete(cenario, email_configurado):
    enviar()
    assert enviar() == []
    assert AvisoEnviado.query.count() == 2


def test_nova_previsao_gera_novo_aviso(cenario, email_configurado):
    _, _, _, tarefa = cenario
    enviar()
    tarefa.previsao_execucao = AGORA + timedelta(hours=30)
    db.session.commit()
    assert len(enviar()) == 2


def test_so_o_proprietario_quando_escolhido(cenario, email_configurado):
    ana, _, _, _ = cenario
    ana.aviso_destinatarios = "proprietario"
    db.session.commit()
    assert [m.recipients[0] for m in enviar()] == [ana.email]


def test_respeita_a_antecedencia_do_proprietario(cenario, email_configurado):
    ana, _, _, tarefa = cenario
    tarefa.previsao_execucao = AGORA + timedelta(days=2, hours=1)
    ana.aviso_antecedencia = 2
    db.session.commit()
    assert enviar() == []
    ana.aviso_antecedencia = 3
    db.session.commit()
    assert len(enviar()) == 2


def test_cartao_atrasado_gera_aviso(cenario, email_configurado):
    _, _, _, tarefa = cenario
    tarefa.previsao_execucao = AGORA - timedelta(hours=2)
    db.session.commit()
    enviadas = enviar()
    assert len(enviadas) == 2
    assert enviadas[0].subject == "Projetos & Demandas: “Feira” está atrasada"


def test_atraso_antigo_nao_gera_aviso(cenario, email_configurado):
    _, _, _, tarefa = cenario
    tarefa.previsao_execucao = AGORA - timedelta(days=3)
    db.session.commit()
    assert enviar() == []


@pytest.mark.parametrize("mudanca", ["concluida", "projeto_concluido", "sem_previsao"])
def test_cartoes_que_nao_geram_aviso(cenario, email_configurado, mudanca):
    _, _, projeto, tarefa = cenario
    if mudanca == "concluida":
        tarefa.concluida_em = AGORA
    elif mudanca == "projeto_concluido":
        projeto.concluida = True
    else:
        tarefa.previsao_execucao = None
    db.session.commit()
    assert enviar() == []


def test_video_nao_gera_aviso(cenario, email_configurado):
    _, _, projeto, tarefa = cenario
    db.session.delete(tarefa)
    video = Tarefa(nome="Aula", tipo="video", projeto_id=projeto.id, previsao_execucao=AGORA + timedelta(hours=5))
    video.video = VideoDoYoutube(endereco="https://www.youtube.com/watch?v=jNQXAC9IVRw", codigo="jNQXAC9IVRw", titulo="Aula")
    db.session.add(video)
    db.session.commit()
    assert enviar() == []


def test_responsavel_sem_acesso_nao_recebe(cenario, email_configurado):
    ana, bruno, _, _ = cenario
    grupo = GrupoDeUsuarios.query.one()
    grupo.membros.remove(bruno)
    db.session.commit()
    assert [m.recipients[0] for m in enviar()] == [ana.email]


def test_sem_email_configurado_nada_e_enviado(cenario):
    assert enviar() == []
    assert AvisoEnviado.query.count() == 0


def test_falha_no_envio_nao_registra_e_tenta_de_novo(cenario, email_configurado, monkeypatch):
    def falhar(mensagem):
        raise OSError("SMTP fora do ar")

    monkeypatch.setattr(mail, "send", falhar)
    assert avisos.enviar_avisos(AGORA) == 0
    assert AvisoEnviado.query.count() == 0
    monkeypatch.undo()
    assert len(enviar()) == 2


def test_excluir_o_cartao_apaga_os_registros_de_aviso(cenario, email_configurado):
    _, _, _, tarefa = cenario
    enviar()
    db.session.delete(tarefa)
    db.session.commit()
    assert AvisoEnviado.query.count() == 0


# ---------- Alerta do cabeçalho


def test_alerta_do_responsavel_segue_a_automacao_do_proprietario(cenario, outro_cliente):
    ana, _, _, tarefa = cenario
    tarefa.previsao_execucao = datetime(2020, 1, 1, 8, 0)
    db.session.commit()
    assert 'id="menu-alertas"' in outro_cliente.get("/grupos").get_data(as_text=True)
    ana.aviso_destinatarios = "proprietario"
    db.session.commit()
    assert 'id="menu-alertas"' not in outro_cliente.get("/grupos").get_data(as_text=True)


# ---------- Tarefa periódica


def test_tarefa_periodica_roda_os_avisos(app, monkeypatch):
    rodou = threading.Event()
    monkeypatch.setattr(avisos, "enviar_avisos", lambda momento: rodou.set())
    app.config.update(AVISOS_PRIMEIRA_EXECUCAO=0, AVISOS_INTERVALO=3600)
    tarefa = avisos.iniciar_avisos(app, lambda: AGORA)
    assert rodou.wait(5) and tarefa.daemon


def test_previa_da_cor_roda_fora_do_quadro():
    """O app.js para em `if (!quadro)`; a prévia da Cor da Aplicação precisa vir antes."""
    with open("static/js/app.js", encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    assert codigo.index("[data-escolher-tema]") < codigo.index("if (!quadro)")


def test_nome_com_quebra_de_linha_nao_impede_o_aviso(cenario, email_configurado):
    _, _, _, tarefa = cenario
    tarefa.nome = "Feira\r\nBcc: todos@exemplo.com"
    db.session.commit()

    enviadas = enviar()

    assert len(enviadas) == 2
    assert enviadas[0].subject == "Projetos & Demandas: “Feira Bcc: todos@exemplo.com” vence em breve"
