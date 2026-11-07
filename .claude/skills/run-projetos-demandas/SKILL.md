---
name: run-projetos-demandas
description: Run, start, launch, smoke-test or drive the Projetos & Demandas Flask app (quadro, vídeos, Usuários, Planos, Grupos) past the login CAPTCHA, using a seeded temporary database on port 8011. Use to confirm a change works in the real running app, not just in pytest.
---

# Rodar o Projetos & Demandas

App Flask (Python 3.13, SQLite). O login real exige um CAPTCHA de imagem, que um agente não deve resolver, então o caminho do agente é o `driver.py` desta pasta: ele sobe uma cópia do app com **banco temporário, `CAPTCHA_ATIVO = False` e contas de teste**, e a dirige por HTTP (cookies + token CSRF). Os caminhos abaixo são relativos à raiz do projeto. Testado no Windows 11, no Git Bash.

## Pré-requisitos

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

## Caminho do agente: o driver

Smoke completo (sobe na porta 8011, entra como administrador, abre quadro, Simplificar de um vídeo, Usuários, Planos e Grupos, e para o servidor). Código de saída 0 = tudo OK:

```bash
timeout 90 .venv/Scripts/python .claude/skills/run-projetos-demandas/driver.py smoke 2>/dev/null
```

Saída esperada: uma linha `OK   ...` por conferência. Para testar algo novo, acrescente uma conferência em `smoke()` (use `nav.get`, `nav.post` e `csrf(html)`; todo POST precisa de `csrf_token`) e semeie os dados em `servir()`.

Para abrir no navegador (painel do app ou `preview_start`), só suba o servidor semeado:

```bash
.venv/Scripts/python .claude/skills/run-projetos-demandas/driver.py serve
```

Entre em <http://127.0.0.1:8011/login> com `admin@exemplo.com` (administrador) ou `ana@exemplo.com`, senha `Teste-Driver-1`. A categoria Casa, da Zélia, é compartilhada com o grupo Família (Zélia e Ana) para Visualizar. O banco fica numa pasta `projetos-demandas-driver-*` do diretório temporário. No Windows, parar o servidor não a apaga; o próximo `serve` ou `smoke` apaga as que sobraram.

## Caminho humano

```bash
.venv/Scripts/python app.py
```

App real na porta 8002, com o banco `database/projetos_demandas.db` e o CAPTCHA ligado: quem entra precisa digitar o código da imagem. Python alterado exige reiniciar; templates e CSS não.

## Testes

```bash
.venv/Scripts/python -m pytest -q
```

Cerca de 740 testes, uns 4 minutos: rode em segundo plano (passa do limite de 2 min do Bash).

## Pegadinhas

- **Não dirija a porta 8002 com as contas de teste.** Elas só existem no banco temporário da 8011. Com duas abas abertas, confira a URL da aba antes de preencher o login.
- O login usa os campos `email` e `password` e redireciona para `/`; todo POST precisa do `csrf_token` da página.
- O driver passa `use_reloader=False` porque semeia o banco no próprio processo do servidor: um reloader rodaria a semeadura duas vezes.
- Miniaturas e dados de vídeo vêm do YouTube; o driver grava o `VideoDoYoutube` direto, sem rede. Sem internet, as miniaturas aparecem em branco no navegador, o que é esperado.
- O console do Windows não usa UTF-8: o driver chama `sys.stdout.reconfigure(encoding="utf-8")` para os acentos saírem certos.
- `/administracao/*` dá 403 a quem não é administrador; use `admin@exemplo.com`.
