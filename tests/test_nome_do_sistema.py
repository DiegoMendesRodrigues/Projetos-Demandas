# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""O nome antigo do sistema não aparece mais em nenhum arquivo do projeto."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Montados por partes, para este arquivo também não conter o nome antigo.
NOMES_ANTIGOS = (
    "Minhas" + " Atividades", "minhas" + "-atividades", "minhas" + "_atividades", "atividades" + ".aplicativoia",
)
EXTENSOES = {".py", ".html", ".txt", ".css", ".js", ".md", ".json", ".svg", ".ini"}
FORA = {".venv", ".pytest_cache", "database", "userfiles"}


def test_nome_antigo_nao_aparece_no_projeto():
    for caminho in RAIZ.rglob("*"):
        relativo = caminho.relative_to(RAIZ).as_posix()
        if not caminho.is_file() or caminho.suffix not in EXTENSOES:
            continue
        if relativo.split("/")[0] in FORA or "__pycache__" in relativo:
            continue
        texto = caminho.read_text(encoding="utf-8")
        for antigo in NOMES_ANTIGOS:
            assert antigo not in texto, (relativo, antigo)


def test_service_worker_apaga_so_os_proprios_caches():
    codigo = (RAIZ / "static/js/sw.js").read_text(encoding="utf-8")

    assert 'const PREFIXO_DO_CACHE = "projetos-demandas-";' in codigo
    assert "nome !== CACHE && nome.startsWith(PREFIXO_DO_CACHE)" in codigo
    assert "PREFIXOS_ANTIGOS" not in codigo


def test_migracoes_da_troca_de_nome_foram_removidas():
    import app as modulo_app
    import config

    for nome in ("renomear_arquivo_do_banco", "renomear_lista_para_projeto", "migrar_email_da_conta_inicial"):
        assert not hasattr(modulo_app, nome)
    for nome in ("ARQUIVO_DO_BANCO_ANTIGO", "EMAIL_ANTIGO_DA_CONTA_INICIAL"):
        assert not hasattr(config, nome)
