[![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)](https://developer.mozilla.org/pt-BR/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css&logoColor=white)](https://developer.mozilla.org/pt-BR/docs/Web/CSS)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)](https://developer.mozilla.org/pt-BR/docs/Web/JavaScript)
[![Flask 3](https://img.shields.io/badge/Flask-3-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite3](https://img.shields.io/badge/SQLite3-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Pillow](https://img.shields.io/badge/Pillow-3776AB?logo=python&logoColor=white)](https://python-pillow.github.io/)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-499848?logo=gunicorn&logoColor=white)](https://gunicorn.org/)
[![Nginx](https://img.shields.io/badge/Nginx-009639?logo=nginx&logoColor=white)](https://nginx.org/)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-3.0-4baaaa.svg)](CODE_OF_CONDUCT.md)

# Projetos & Demandas

## Sobre Projetos & Demandas

Projetos & Demandas é uma solução on-line para a gestão de projetos e demandas. Cada usuário tem sua própria conta e organiza as demandas em projetos, e os projetos em categorias.

Com o sistema, é possível:

- Arrastar as demandas entre os projetos, no computador e no celular.
- Definir a Prioridade, Previsão de Execução, Local e a Descrição com o texto formatado e imagens.
- Anexar até 3 arquivos em cada demanda.
- Ocultar demandas e exibí-las novamente quando precisar.
- Acompanhar as demandas atrasadas através de alertas do cabeçalho.
- Escolher a cor da interface entre Azul, Cinza, Laranja, Verde e Vermelho.
- Criar listas de tarefas, com itens que podem ser marcados, reordenados e colocados em ordem alfabética.
- Guardar vídeos do YouTube nos projetos, com o título, o autor, a duração, a descrição e o player do vídeo.
- Concluir demandas, que deixam de gerar alertas de atraso.
- Ver no Meu Dia as demandas atrasadas, as de hoje, as de amanhã e as dos próximos dias, de todas as categorias.
- Acompanhar o progresso de cada lista de tarefas e o resumo da semana no Meu Perfil.
- Ver as demandas num Calendário, por mês ou por semana, e arrastá-las para outro dia.
- Dar a cada categoria um fundo para o quadro, entre 10 opções de cores suaves.
- Trabalhar no modo foco, só com os projetos na tela, e usar atalhos do teclado (tecla ?).
- Pesquisar os cartões do quadro pelo nome, local, descrição, tarefas, marcações e dados dos vídeos.
- Adicionar marcações (tags) às demandas, listas de tarefas e vídeos.
- Ver o proprietário de cada cartão e escolher um responsável entre as pessoas com acesso à categoria.
- Ver o histórico de cada cartão (quem criou, alterou, moveu, concluiu ou trocou o responsável) e deixar comentários.
- Instalar o sistema como aplicativo no celular ou no computador, com atalhos para o Meu Dia e o Calendário.
- Receber por e-mail os avisos dos cartões próximos do vencimento e atrasados, com a antecedência escolhida no Meu Perfil.
- Criar grupos de usuários e compartilhar categorias com eles, para visualização ou edição.
- Ver no quadro compartilhado, sem recarregar a página, as mudanças feitas pelas outras pessoas.
- Proteger o login e a recuperação de senha com um CAPTCHA de imagem, gerado no próprio servidor.
- Administrar os usuários, os planos de usuários, com o espaço para anexos e os limites de cada plano, e as configurações de envio de e-mails.

## Tecnologias Utilizadas

- **Linguagens:** Python 3.13, HTML5, CSS3 e JavaScript.
- **Framework web:** Flask, com os modelos Jinja2 e o Werkzeug.
- **Banco de dados:** SQLite3 (padrão), MariaDB, MySQL, PostgreSQL, Oracle ou Microsoft SQL Server, com SQLAlchemy, Flask-SQLAlchemy e as migrações do Alembic.
- **Drivers dos bancos:** PyMySQL (MariaDB e MySQL), psycopg (PostgreSQL), python-oracledb (Oracle) e pyodbc com o Microsoft ODBC Driver (SQL Server).
- **Autenticação e segurança:** Flask-Login, Flask-Security-Too (senhas com Argon2), zxcvbn (força da senha), nh3 (limpeza do HTML da descrição), cryptography (senha do e-mail cifrada) e captcha (CAPTCHA de imagem gerado no próprio servidor).
- **Formulários:** Flask-WTF, WTForms e email-validator.
- **E-mails:** Flask-Mail.
- **Idioma e fuso horário:** Flask-Babel e tzdata (horário de São Paulo).
- **Imagens:** Pillow (foto do perfil e CAPTCHA).
- **Interface:** JavaScript puro, sem frameworks, com Pointer Events (arrastar no computador e no celular), Canvas (ajuste da foto do perfil), Service Worker e Web App Manifest (aplicativo instalável, PWA).
- **Vídeos:** páginas públicas do YouTube e o oEmbed do Vimeo, sem chave de API.
- **Produção:** Gunicorn, Nginx com HTTPS (Certbot ou certificado próprio), systemd e cópias de segurança cifradas com o GnuPG, no Debian 13.
- **Testes:** pytest.

## Como Instalar

As instruções para os ambientes de desenvolvimento e de produção estão no arquivo [INSTALL.md](INSTALL.md).

## Perguntas Frequentes (FAQ)

### Quem pode utilizar esse software?

Todos podem utilizar, desde que tenham as tecnologias necessárias instaladas no computador.

### Quem pode contribuir?

Qualquer desenvolvedor pode contribuir, seguindo o código de conduta descrito no arquivo [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

### Qual a senha inicial do Projetos & Demandas?

O usuário inicial é `administrador@demandas.aplicativoia.online`, com a senha `Admin@2026`. A conta é criada na primeira execução do sistema. Troque essa senha no primeiro acesso, em Alterar a Senha. Em produção, siga o arquivo [INSTALL.md](INSTALL.md), que define uma senha própria.

## Autor

[Diego Mendes Rodrigues](https://www.linkedin.com/in/diegomendesrodrigues/)

## Licença

Este projeto é distribuído sob a licença GNU General Public License (GNU GPL). Consulte o arquivo [LICENSE.md](LICENSE.md).

## Telas do Projetos & Demandas

![Quadro](static/img/manual/quadro.webp)

O quadro da categoria Trabalho, com os projetos Pendentes, Em Execução, Paradas e Concluídas. Cada projeto é uma coluna, e as demandas são arrastadas entre eles.

<br>

![Editar categoria](static/img/manual/categoria.webp)

A caixa da categoria, com o nome, um dos 24 ícones e um dos 10 fundos para o quadro.

<br>

![Editar projeto](static/img/manual/projeto.webp)

A caixa do projeto, com o nome, a categoria, uma das 12 cores e a opção Projeto concluído.

<br>

![Menu de criação](static/img/manual/menu-criar.webp)

O botão + de cada projeto abre o menu com os quatro tipos de cartão: Contexto, Demanda, Lista de Tarefas e Vídeo.

<br>

![Editar demanda](static/img/manual/demanda.webp)

A caixa da demanda, com a Prioridade, a Previsão de Execução, o Local e as marcações à esquerda e o editor da Descrição, com texto formatado e imagens, à direita.

<br>

![Lista de tarefas](static/img/manual/lista-de-tarefas.webp)

A lista de tarefas Mercado, com os itens marcados e desmarcados, que podem ser reordenados e colocados em ordem alfabética.

<br>

![Cartão de contexto](static/img/manual/contexto.webp)

O cartão de contexto, com as seções escolhidas pelo usuário: a descrição, a lista de tarefas e o vídeo ficam em abas, à direita.

<br>

![Vídeo](static/img/manual/video.webp)

A caixa do vídeo, com o título, o autor, a data de publicação, a duração e a descrição à esquerda e o player à direita.

<br>

![Quadro de vídeos](static/img/manual/quadro-videos.webp)

A categoria Videoteca, com os vídeos do YouTube e do Vimeo organizados por assunto.

<br>

![Pesquisar](static/img/manual/pesquisa.webp)

O quadro filtrado pela pesquisa "fornecedores": só os cartões encontrados ficam na tela, e o × encerra a pesquisa.

<br>

![Histórico](static/img/manual/historico.webp)

O histórico da demanda Verificar os Fornecedores, com quem criou, alterou, moveu e concluiu o cartão, e o campo para deixar um comentário.

<br>

![Meu Dia](static/img/manual/meu-dia.webp)

O Meu Dia, com as demandas atrasadas, as de hoje, as de amanhã e as dos próximos dias, de todas as categorias.

<br>

![Calendário do mês](static/img/manual/calendario.webp)

O Calendário do mês, com as demandas em cada dia. Arrastar um cartão para outro dia muda a previsão.

<br>

![Calendário da semana](static/img/manual/calendario-semana.webp)

A visão por semana do Calendário, com mais espaço para cada dia.

<br>

![Grupos](static/img/manual/grupos.webp)

A página Grupos, com os grupos de usuários usados para compartilhar categorias.

<br>

![Compartilhar](static/img/manual/compartilhar.webp)

O compartilhamento da categoria Pessoal com os grupos, para visualização ou edição.

<br>

![Meu Perfil](static/img/manual/perfil.webp)

O Meu Perfil, com o resumo da semana, os dados da conta, a cor da aplicação, o ícone ou a foto e a automação dos avisos por e-mail.

<br>

![Atalhos do teclado](static/img/manual/atalhos.webp)

A caixa com os atalhos do teclado, aberta pela tecla ?.

<br>

<img src="static/img/manual/celular-quadro.webp" alt="Quadro no celular" width="300">

O quadro no celular, com as categorias numa faixa que rola para os lados.

<br>

<img src="static/img/manual/celular-meu-dia.webp" alt="Meu Dia no celular" width="300">

O Meu Dia no celular.

<br>

<img src="static/img/manual/celular-demanda.webp" alt="Demanda no celular" width="300">

A caixa da demanda no celular, ocupando a tela inteira.
