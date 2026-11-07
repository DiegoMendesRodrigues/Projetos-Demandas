[![Python 3.13](https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
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
- **Framework web:** Flask.
- **Banco de dados:** SQLite3 com Flask-SQLAlchemy.
- **Autenticação e segurança:** Flask-Login, Flask-Security-Too, nh3 e captcha.
- **Formulários:** Flask-WTF.
- **E-mails:** Flask-Mail.
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
