# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from datetime import datetime, timedelta

import pytest

import inatividade
import seguranca
from extensions import db, mail
from inatividade import (
    ASSUNTO_DO_AVISO,
    cuidar_das_contas_inativas,
    enviar_avisos_de_exclusao,
    excluir_contas_inativas,
)
from models import (
    Anexo,
    Categoria,
    Imagem,
    PlanoDeUsuario,
    Projeto,
    Tarefa,
    Usuario,
    agora_em_sao_paulo,
)

ACESSO = datetime(2026, 11, 1, 9, 0)


def usuario(cliente):
    return db.session.get(Usuario, cliente.usuario_id)


@pytest.fixture
def email_configurado(app):
    app.config.update(MAIL_SERVER="smtp.exemplo.com", MAIL_DEFAULT_SENDER=("Projetos & Demandas", "nao-responda@exemplo.com"))


@pytest.fixture
def ana(cliente):
    """Ana, no plano de 15 dias, com o último acesso em ACESSO."""
    plano = PlanoDeUsuario(nome="Quinze", armazenamento_mb=10, dias_de_inatividade=15)
    db.session.add(plano)
    conta = usuario(cliente)
    conta.nome = "Ana"
    conta.plano = plano
    conta.ultimo_acesso = ACESSO
    db.session.commit()
    return conta.id


def existe(usuario_id):
    db.session.expire_all()
    return db.session.get(Usuario, usuario_id) is not None


# ---------- Último acesso


def test_login_grava_o_ultimo_acesso(criar_cliente):
    antes = agora_em_sao_paulo() - timedelta(seconds=1)
    cliente = criar_cliente("carla@exemplo.com")

    assert usuario(cliente).ultimo_acesso >= antes


def test_conta_nova_ja_nasce_com_o_ultimo_acesso(app):
    from extensions import security

    conta = security.datastore.create_user(email="nova@exemplo.com", password="x")
    db.session.commit()

    assert conta.ultimo_acesso is not None


def test_uso_do_sistema_atualiza_o_ultimo_acesso(cliente):
    conta = usuario(cliente)
    conta.ultimo_acesso = agora_em_sao_paulo() - timedelta(minutes=10)
    db.session.commit()

    cliente.get("/")

    db.session.expire_all()
    assert agora_em_sao_paulo() - usuario(cliente).ultimo_acesso < timedelta(minutes=1)


def test_acessos_seguidos_nao_gravam_a_cada_pedido(cliente):
    momento = agora_em_sao_paulo() - timedelta(minutes=2)
    conta = usuario(cliente)
    conta.ultimo_acesso = momento
    db.session.commit()

    cliente.get("/")

    db.session.expire_all()
    assert usuario(cliente).ultimo_acesso == momento


def test_consulta_automatica_da_versao_nao_conta_como_uso(cliente):
    momento = agora_em_sao_paulo() - timedelta(days=3)
    conta = usuario(cliente)
    conta.ultimo_acesso = momento
    db.session.commit()

    cliente.get("/api/quadro/versao")

    db.session.expire_all()
    assert usuario(cliente).ultimo_acesso == momento


def test_uso_do_sistema_apaga_o_aviso_de_exclusao(cliente):
    conta = usuario(cliente)
    conta.ultimo_acesso = agora_em_sao_paulo() - timedelta(minutes=1)
    conta.aviso_de_exclusao_em = agora_em_sao_paulo() - timedelta(days=1)
    db.session.commit()

    cliente.get("/")

    db.session.expire_all()
    assert usuario(cliente).aviso_de_exclusao_em is None


def test_marcar_acesso_respeita_o_intervalo(cliente):
    conta = usuario(cliente)
    conta.ultimo_acesso = ACESSO
    db.session.commit()

    assert seguranca.marcar_acesso(conta, ACESSO + timedelta(minutes=4)) is False
    assert seguranca.marcar_acesso(conta, ACESSO + timedelta(minutes=5)) is True
    assert conta.ultimo_acesso == ACESSO + timedelta(minutes=5)
    assert seguranca.marcar_acesso(conta, ACESSO + timedelta(minutes=6), sempre=True) is True


def test_visitante_nao_grava_acesso(app):
    cliente = app.test_client()
    assert cliente.get("/projetos-e-demandas").status_code == 200


# ---------- Exclusão


def test_conta_dentro_do_prazo_continua(ana):
    assert excluir_contas_inativas(ACESSO + timedelta(days=15)) == 0
    assert existe(ana)


def test_conta_que_passa_do_prazo_e_excluida(ana):
    assert excluir_contas_inativas(ACESSO + timedelta(days=15, minutes=1)) == 1
    assert not existe(ana)


def test_exemplo_da_ana_dezesseis_dias(ana):
    cuidar_das_contas_inativas(ACESSO + timedelta(days=16))
    assert not existe(ana)


def test_administrador_nunca_e_excluido(ana):
    db.session.get(Usuario, ana).administrador = True
    db.session.commit()

    assert excluir_contas_inativas(ACESSO + timedelta(days=400)) == 0
    assert existe(ana)


def test_plano_ilimitado_nunca_exclui(ana):
    db.session.get(Usuario, ana).plano.dias_de_inatividade = None
    db.session.commit()

    assert excluir_contas_inativas(ACESSO + timedelta(days=400)) == 0
    assert existe(ana)


def test_conta_sem_ultimo_acesso_comeca_a_contar_agora(ana):
    momento = ACESSO + timedelta(days=100)
    db.session.get(Usuario, ana).ultimo_acesso = None
    db.session.commit()

    assert excluir_contas_inativas(momento) == 0
    db.session.expire_all()
    assert db.session.get(Usuario, ana).ultimo_acesso == momento


def test_exclusao_apaga_dados_arquivos_e_imagens(app, ana):
    pasta = app.config["ANEXOS_DIR"]
    pasta.mkdir(parents=True, exist_ok=True)
    categoria = Categoria(nome="Casa", usuario_id=ana)
    projeto = Projeto(nome="A fazer", usuario_id=ana, categoria=categoria)
    tarefa = Tarefa(nome="Feira", projeto=projeto)
    db.session.add_all([
        categoria,
        projeto,
        tarefa,
        Anexo(nome="a.txt", arquivo="a" * 32, tamanho=1, tarefa=tarefa),
        Imagem(arquivo="b" * 32, tipo="image/png", usuario_id=ana),
    ])
    db.session.get(Usuario, ana).foto = "foto-" + "c" * 32 + ".png"
    db.session.commit()
    for codigo in ("a" * 32, "b" * 32, "foto-" + "c" * 32 + ".png"):
        (pasta / codigo).write_bytes(b"x")

    excluir_contas_inativas(ACESSO + timedelta(days=16))

    assert not existe(ana)
    assert Projeto.query.count() == Categoria.query.count() == Tarefa.query.count() == 0
    assert Anexo.query.count() == Imagem.query.count() == 0
    assert list(pasta.iterdir()) == []


def test_falha_numa_conta_nao_para_as_demais(ana, outro_cliente, monkeypatch):
    bruno = usuario(outro_cliente)
    bruno.plano = db.session.get(Usuario, ana).plano
    bruno.ultimo_acesso = ACESSO
    db.session.commit()
    original = inatividade.apagar_conta

    def falhar_na_ana(conta):
        if conta.id == ana:
            raise RuntimeError("falha simulada")
        original(conta)

    monkeypatch.setattr(inatividade, "apagar_conta", falhar_na_ana)

    assert excluir_contas_inativas(ACESSO + timedelta(days=16)) == 1
    assert existe(ana)
    assert not existe(outro_cliente.usuario_id)


# ---------- Aviso por e-mail


def test_sem_email_configurado_nao_avisa(ana):
    assert enviar_avisos_de_exclusao(ACESSO + timedelta(days=14)) == 0


def test_aviso_sai_tres_dias_antes(ana, email_configurado):
    with mail.record_messages() as enviados:
        assert enviar_avisos_de_exclusao(ACESSO + timedelta(days=11, hours=23)) == 0
        assert enviar_avisos_de_exclusao(ACESSO + timedelta(days=12)) == 1
        assert enviar_avisos_de_exclusao(ACESSO + timedelta(days=13)) == 0

    assert len(enviados) == 1
    mensagem = enviados[0]
    assert mensagem.subject == ASSUNTO_DO_AVISO
    assert "\n" not in mensagem.subject
    assert mensagem.recipients == ["ana@exemplo.com"]
    assert "16/11/2026 às 09:00" in mensagem.body
    assert "16/11/2026 às 09:00" in mensagem.html
    assert "15 dias" in mensagem.body
    db.session.expire_all()
    assert db.session.get(Usuario, ana).aviso_de_exclusao_em == ACESSO + timedelta(days=12)


def test_com_email_a_exclusao_espera_o_aviso(ana, email_configurado):
    # A tarefa periódica ficou parada: no primeiro dia depois do prazo, só sai o aviso.
    atrasado = ACESSO + timedelta(days=20)
    with mail.record_messages() as enviados:
        cuidar_das_contas_inativas(atrasado)
    assert len(enviados) == 1
    assert "24/11/2026 às 09:00" in enviados[0].body
    assert existe(ana)

    assert excluir_contas_inativas(atrasado + timedelta(days=2, hours=23)) == 0
    assert existe(ana)
    assert excluir_contas_inativas(atrasado + timedelta(days=3)) == 1
    assert not existe(ana)


def test_com_email_exclui_no_fim_do_prazo_depois_do_aviso(ana, email_configurado):
    with mail.record_messages():
        cuidar_das_contas_inativas(ACESSO + timedelta(days=12))
    cuidar_das_contas_inativas(ACESSO + timedelta(days=15))
    assert existe(ana)

    cuidar_das_contas_inativas(ACESSO + timedelta(days=15, minutes=1))
    assert not existe(ana)


def test_falha_no_envio_segura_a_exclusao(ana, email_configurado, monkeypatch):
    def falhar(_mensagem):
        raise OSError("SMTP fora do ar")

    monkeypatch.setattr(mail, "send", falhar)

    assert cuidar_das_contas_inativas(ACESSO + timedelta(days=30)) == 0
    assert existe(ana)
    assert db.session.get(Usuario, ana).aviso_de_exclusao_em is None


def test_voltar_a_usar_o_sistema_cancela_a_exclusao(cliente, ana, email_configurado):
    with mail.record_messages():
        enviar_avisos_de_exclusao(ACESSO + timedelta(days=12))
    conta = db.session.get(Usuario, ana)
    seguranca.marcar_acesso(conta, ACESSO + timedelta(days=13))

    assert conta.aviso_de_exclusao_em is None
    assert excluir_contas_inativas(ACESSO + timedelta(days=16)) == 0
    assert existe(ana)


def test_a_limpeza_periodica_cuida_das_contas_inativas(ana, monkeypatch):
    import app as aplicacao

    vistos = []
    monkeypatch.setattr(aplicacao, "apagar_imagens_pendentes", lambda momento: vistos.append("imagens"))
    monkeypatch.setattr(aplicacao, "cuidar_das_contas_inativas", lambda momento: vistos.append(momento))

    aplicacao.tarefas_de_limpeza(ACESSO)

    assert vistos == ["imagens", ACESSO]
