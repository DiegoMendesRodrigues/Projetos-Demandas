# Instalação do Projetos & Demandas

Este guia descreve a instalação no **Debian 13 "trixie"**, a versão estável atual do Debian, nos seguintes ambientes:

- [Ambiente de Desenvolvimento](#ambiente-de-desenvolvimento): para alterar o código e rodar os testes.
- [Ambiente de Produção](#ambiente-de-produção): para os usuários acessarem o sistema com HTTPS.
- [Outros bancos de dados](#outros-bancos-de-dados): MariaDB, MySQL, PostgreSQL, Oracle ou Microsoft SQL Server no lugar do SQLite.

O Debian 13 traz o Python 3.13, a versão usada pelo projeto.

Todos os comandos usam um usuário com acesso ao `sudo`. Por padrão, os dados do sistema ficam em SQLite, então não é necessário instalar um servidor de banco de dados. Para usar outro banco, siga também a seção [Outros bancos de dados](#outros-bancos-de-dados).

## Ambiente de Desenvolvimento

### 1. Instalar os pacotes

```bash
sudo apt update
sudo apt install -y python3 python3-venv
```

### 2. Copiar o projeto

Coloque os arquivos do projeto em uma pasta do seu usuário, por exemplo `~/projetos-demandas`, e entre nela:

```bash
cd ~/projetos-demandas
```

### 3. Criar o ambiente virtual e instalar as dependências

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

### 4. Iniciar a aplicação

```bash
.venv/bin/python app.py
```

O sistema fica disponível em <http://localhost:8002>. Na primeira execução são criados o banco `database/projetos_demandas.db`, as chaves em `database/segredos.json` e a conta inicial, cujo usuário e senha estão no [README.md](README.md). Também é possível criar outras contas pela tela de cadastro. O login e o Esqueci minha senha pedem, além da senha, o código da imagem exibida na tela.

A aplicação aceita conexões de qualquer IP na porta 8002. Use esse servidor apenas em uma rede de confiança: ele é o servidor de desenvolvimento do Flask e não serve para produção.

### 5. Rodar os testes

```bash
.venv/bin/python -m pytest -x
```

Para rodar um único teste:

```bash
.venv/bin/python -m pytest -x tests/test_tarefas.py::test_excluir_tarefa
```

Os testes usam um SQLite novo a cada teste. Para rodá-los em outro banco, informe em `URL_DO_BANCO_DE_TESTE` o endereço SQLAlchemy de um banco **criado só para isso**, porque as tabelas dele são apagadas a cada teste. Os testes das migrações antigas, que só existem no SQLite, são pulados:

```bash
URL_DO_BANCO_DE_TESTE="postgresql+psycopg://teste:senha@localhost/projetos_demandas_teste" .venv/bin/python -m pytest -x
```

### 6. Habilitar o envio de e-mails (opcional)

O envio de e-mails é configurado só pela aplicação. Entre como administrador e abra Administração > Configurações. Preencha o servidor SMTP, a porta, o uso de TLS, o usuário, a senha, o e-mail e o nome usados no envio. Os dados ficam no banco de dados, e os e-mails saem com esse nome e esse e-mail no campo De.

Na porta 465, a conexão é cifrada desde o início; nas portas 25, 587 e 2525, a opção Utilizar TLS ativa o STARTTLS.

Enquanto a tela não for salva, nenhum e-mail é enviado: o Esqueci minha senha continua na tela de login e responde com a mesma mensagem, mas as instruções não saem, e o administrador não consegue usar o Redefinir a senha de Administração > Usuários. Depois do primeiro salvamento, reinicie a aplicação para ativar a confirmação do e-mail de quem se cadastra; as alterações seguintes valem sem reiniciar.

Com o envio configurado, a própria aplicação manda os avisos de vencimento da área Automação do Meu Perfil: a primeira verificação acontece um minuto depois de iniciar, e as seguintes, a cada 10 minutos. Sem a configuração, nenhum aviso é enviado.

## Ambiente de Produção

A instalação usa o Gunicorn como servidor da aplicação, o systemd para mantê-lo em execução e o Nginx como proxy reverso com HTTPS.

```text
Navegador -> Nginx (portas 80 e 443) -> Gunicorn (127.0.0.1:8002) -> banco de dados (SQLite ou outro) e userfiles/
```

O servidor pode ter qualquer IP e não precisa de domínio: o passo 8 descreve as duas formas de acesso.

### 1. Instalar os pacotes

```bash
sudo apt update
sudo apt install -y python3 python3-venv nginx certbot python3-certbot-nginx openssl sqlite3 rsync ufw
```

### 2. Criar o usuário do serviço

A aplicação roda com um usuário próprio, sem acesso de login:

```bash
sudo adduser --system --group --no-create-home --home /opt/projetos-demandas projetos-demandas
```

### 3. Copiar o projeto

A partir da máquina de desenvolvimento, envie os arquivos sem levar o ambiente virtual, os dados locais e os arquivos temporários:

```bash
rsync -av --exclude .venv --exclude .claude --exclude .pytest_cache --exclude __pycache__ --exclude database --exclude userfiles --exclude CLAUDE.zip ./ usuario@servidor:/tmp/projetos-demandas/
```

No servidor, mova os arquivos para `/opt` e dê ao serviço permissão de escrita apenas nas pastas de dados:

```bash
sudo mv /tmp/projetos-demandas /opt/projetos-demandas
sudo mkdir -p /opt/projetos-demandas/database /opt/projetos-demandas/userfiles
sudo chown -R root:root /opt/projetos-demandas
sudo chown -R projetos-demandas:projetos-demandas /opt/projetos-demandas/database /opt/projetos-demandas/userfiles
sudo chmod 750 /opt/projetos-demandas/database /opt/projetos-demandas/userfiles
```

### 4. Criar o ambiente virtual

O Gunicorn não faz parte do `requirements.txt` porque só é usado em produção:

```bash
sudo python3 -m venv /opt/projetos-demandas/.venv
sudo /opt/projetos-demandas/.venv/bin/python -m pip install -r /opt/projetos-demandas/requirements.txt gunicorn
```

Com outro banco de dados, instale também o driver dele e prepare o servidor do banco antes do passo 6, como descrito em [Outros bancos de dados](#outros-bancos-de-dados).

### 5. Configurar as chaves e os e-mails

Crie o arquivo de ambiente com as chaves e a senha da conta inicial, todas aleatórias:

```bash
sudo sh -c 'umask 027; { echo "SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")"; echo "SECURITY_PASSWORD_SALT=$(python3 -c "import secrets; print(secrets.token_hex(16))")"; echo "CONTA_INICIAL_SENHA=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")"; echo "PROXY_CONFIAVEL=1"; } > /etc/projetos-demandas.env'
sudo chgrp projetos-demandas /etc/projetos-demandas.env
```

Faça isso antes de iniciar o serviço pela primeira vez. Sem `CONTA_INICIAL_SENHA`, a conta inicial é criada com a senha padrão publicada no [README.md](README.md), e qualquer pessoa conseguiria entrar nela.

Guarde esse arquivo em local seguro e não altere as chaves depois de criar as contas: trocar `SECURITY_PASSWORD_SALT` faz todas as senhas deixarem de funcionar, e trocar `SECRET_KEY` encerra as sessões abertas e apaga a senha do e-mail, que fica cifrada no banco com essa chave e precisa ser informada de novo em Administração > Configurações.

`PROXY_CONFIAVEL=1` faz o sistema ler o IP do visitante e o HTTPS dos cabeçalhos enviados pelo Nginx. Sem ele, o limite de tentativas contaria todos os visitantes como um só, com o IP do próprio Nginx. Use-o só com o Gunicorn atendendo em `127.0.0.1`, como no serviço abaixo: acessado diretamente, qualquer pessoa poderia falsificar esses cabeçalhos.

Os e-mails não são configurados neste arquivo: depois de instalar, use a tela Administração > Configurações, descrita no ambiente de desenvolvimento, e reinicie o serviço depois do primeiro salvamento, para ativar a confirmação do e-mail.

### 6. Criar o serviço do systemd

Crie o arquivo `/etc/systemd/system/projetos-demandas.service`:

```ini
[Unit]
Description=Projetos & Demandas
After=network.target

[Service]
User=projetos-demandas
Group=projetos-demandas
WorkingDirectory=/opt/projetos-demandas
EnvironmentFile=/etc/projetos-demandas.env
ExecStart=/opt/projetos-demandas/.venv/bin/gunicorn --workers 1 --threads 4 --timeout 120 --bind 127.0.0.1:8002 "app:create_app()"
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/opt/projetos-demandas/database /opt/projetos-demandas/userfiles
# O banco, as chaves e os arquivos enviados são criados só para o usuário do serviço.
UMask=0077

[Install]
WantedBy=multi-user.target
```

Mantenha `--workers 1`. No SQLite, cada processo executa as atualizações do banco ao iniciar, e vários processos fariam isso ao mesmo tempo no mesmo arquivo. Com qualquer banco, o limite de tentativas e os avisos por e-mail ficam dentro do processo: com vários, cada um teria os seus contadores e enviaria os mesmos avisos. As threads atendem às requisições simultâneas.

Com outro banco de dados, a pasta `database/` guarda só o `segredos.json` (quando as chaves não estão no arquivo de ambiente), e o `ReadWritePaths` pode continuar igual.

Inicie o serviço:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now projetos-demandas
sudo systemctl status projetos-demandas
```

### 7. Liberar o firewall

Libere o SSH antes de ativar o firewall, para não perder o acesso ao servidor:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 8. Configurar o Nginx e o HTTPS

O HTTPS é obrigatório, porque os cookies de sessão só trafegam por ele. Siga a opção A se o servidor tiver um domínio, ou a opção B para acessá-lo pelo IP.

#### Opção A: servidor com domínio

Aponte o domínio para o servidor. Nos exemplos, troque `projetos.exemplo.com` pelo seu domínio.

Crie o arquivo `/etc/nginx/sites-available/projetos-demandas`:

```nginx
server {
    listen 80;
    server_name projetos.exemplo.com;

    # Três arquivos de 10 MB mais os demais campos do formulário.
    client_max_body_size 32m;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;

        # Os cookies de sessão só podem trafegar por HTTPS.
        proxy_cookie_flags ~ secure;
    }
}

# Pedidos com outro nome no Host (ou só o IP) são descartados, sem chegar ao sistema.
server {
    listen 80 default_server;
    listen 443 ssl default_server;
    server_name _;
    ssl_reject_handshake on;
    return 444;
}
```

Os cabeçalhos de segurança, inclusive o HSTS, que obriga o navegador a usar sempre o HTTPS, são enviados pela própria aplicação: com `PROXY_CONFIAVEL=1`, ela sabe quando a página foi aberta por HTTPS. Não é preciso acrescentá-los no Nginx.

Informe o domínio ao sistema. Os links dos e-mails, como o de criar uma nova senha, usam o endereço do pedido: com `HOSTS_PERMITIDOS`, um pedido com outro endereço é recusado e não pode desviar esses links para outro site.

```bash
echo "HOSTS_PERMITIDOS=projetos.exemplo.com" | sudo tee -a /etc/projetos-demandas.env
sudo systemctl restart projetos-demandas
```

Ative o site:

```bash
sudo ln -s /etc/nginx/sites-available/projetos-demandas /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Emita o certificado. O Certbot ajusta o site do Nginx e renova o certificado automaticamente:

```bash
sudo certbot --nginx -d projetos.exemplo.com
```

#### Opção B: servidor acessado pelo IP

O sistema não depende de um IP específico: esta opção aceita o endereço que o servidor tiver. Como o Certbot desta instalação emite certificados para domínios, o certificado aqui é autoassinado.

Descubra o IP do servidor. Se ele estiver atrás de NAT ou em uma nuvem, `hostname -I` mostra o IP interno: nesse caso, defina `IP` com o IP que os usuários vão acessar.

```bash
IP=$(hostname -I | awk '{print $1}')
echo "$IP"
```

Gere o certificado para esse IP:

```bash
sudo openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=$IP" -addext "subjectAltName=IP:$IP" -keyout /etc/ssl/private/projetos-demandas.key -out /etc/ssl/certs/projetos-demandas.crt
sudo chmod 600 /etc/ssl/private/projetos-demandas.key
```

Crie o arquivo `/etc/nginx/sites-available/projetos-demandas`. O `server_name _` faz o Nginx responder em qualquer IP do servidor:

```nginx
server {
    listen 80 default_server;
    server_name _;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl default_server;
    server_name _;

    ssl_certificate /etc/ssl/certs/projetos-demandas.crt;
    ssl_certificate_key /etc/ssl/private/projetos-demandas.key;

    # Três arquivos de 10 MB mais os demais campos do formulário.
    client_max_body_size 32m;

    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;

        # Os cookies de sessão só podem trafegar por HTTPS.
        proxy_cookie_flags ~ secure;
    }
}
```

Os cabeçalhos de segurança, inclusive o HSTS, que obriga o navegador a usar sempre o HTTPS, são enviados pela própria aplicação: com `PROXY_CONFIAVEL=1`, ela sabe quando a página foi aberta por HTTPS. Não é preciso acrescentá-los no Nginx.

Ative o site:

```bash
sudo ln -s /etc/nginx/sites-available/projetos-demandas /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Informe o IP ao sistema. Os links dos e-mails, como o de criar uma nova senha, usam o endereço do pedido: com `HOSTS_PERMITIDOS`, um pedido com outro endereço é recusado e não pode desviar esses links para outro site.

```bash
echo "HOSTS_PERMITIDOS=$IP" | sudo tee -a /etc/projetos-demandas.env
sudo systemctl restart projetos-demandas
```

Na primeira visita, o navegador avisa que o certificado não é confiável, porque ele foi gerado no próprio servidor. Cada usuário precisa aceitar o aviso uma vez para continuar. Se o IP mudar, gere o certificado de novo com o novo IP e troque o `HOSTS_PERMITIDOS` em `/etc/projetos-demandas.env`; o restante da configuração continua igual.

### 9. Conferir a instalação

Consulte a senha da conta inicial:

```bash
sudo grep CONTA_INICIAL_SENHA /etc/projetos-demandas.env
```

Acesse o domínio ou o IP do servidor com `https://` e entre com o usuário `administrador@demandas.aplicativoia.online` e essa senha. O login só funciona depois do passo anterior, porque os cookies exigem HTTPS.

No primeiro login, o sistema exige a troca da senha da conta inicial: até lá, só a tela Alterar a Senha fica acessível. Depois, remova a linha `CONTA_INICIAL_SENHA` do arquivo de ambiente, que é usada apenas na criação da conta.

Para acompanhar os registros do serviço:

```bash
sudo journalctl -u projetos-demandas -f
```

### Cuidados em produção

- **Cadastro aberto:** qualquer pessoa que acesse o endereço pode criar uma conta. Para impedir novos cadastros, altere `SECURITY_REGISTERABLE` para `False` em `config.py` depois de criar as contas necessárias e reinicie o serviço.
- **Conta inicial:** ela é a conta administradora, com acesso ao menu Administração (Usuários, Planos de Usuários e Configurações), mas sem acesso aos projetos dos outros usuários.
- **Planos de Usuários:** toda conta nova, inclusive as criadas pela tela de cadastro, recebe o plano marcado como padrão. Revise em Administração > Planos de Usuários o espaço e os limites desse plano antes de liberar o acesso.
- **Vídeos do YouTube:** para buscar as informações dos vídeos, o servidor precisa acessar a internet. Se a saída do servidor for bloqueada, essa função mostra uma mensagem de erro e o restante do sistema continua funcionando. Nos servidores de datacenter, o YouTube costuma responder com a verificação "confirme que você não é um robô" no lugar da página do vídeo. Sem a chave da API (abaixo), o sistema usa então o oEmbed público do YouTube, que traz só o título e o autor, e o vídeo é gravado sem a descrição, a data de publicação e a duração. O motivo de cada falha fica nos registros do serviço (`sudo journalctl -u projetos-demandas | grep YouTube`). Para conferir a saída do servidor para o YouTube:

  ```bash
  curl -sS -o /dev/null -w "%{http_code}\n" "https://www.youtube.com/oembed?url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DjNQXAC9IVRw&format=json"
  curl -sS -A "Mozilla/5.0" "https://www.youtube.com/watch?v=jNQXAC9IVRw" | grep -o '"playabilityStatus":{"status":"[A-Z_]*"' | head -1
  ```

  O primeiro deve mostrar `200`, e o segundo, `"status":"OK"`; `LOGIN_REQUIRED` é a verificação de robô. Sem resposta nenhuma, a saída do servidor para a internet está bloqueada (firewall do provedor, DNS ou IPv6).
- **Chave da API do YouTube:** com ela, as informações vêm da YouTube Data API v3, sem a verificação de robô, com a descrição, a data e a duração. A chave é gratuita, e a cota padrão (10.000 unidades por dia; cada vídeo usa 1) sobra para este uso. Para criá-la:
  1. Em <https://console.cloud.google.com>, crie um projeto (ou escolha um).
  2. Em **APIs e serviços > Biblioteca**, procure **YouTube Data API v3** e clique em **Ativar**.
  3. Em **APIs e serviços > Credenciais**, clique em **Criar credenciais > Chave de API** e copie a chave.
  4. Na chave criada, em **Restrições de API**, escolha **Restringir chave** e marque só a **YouTube Data API v3**. Em **Restrições de aplicativos**, use **Endereços IP** com o IP de saída do servidor (`curl -4 ifconfig.me`), e não **Sites (referenciadores HTTP)**, porque quem chama a API é o servidor, não o navegador.
  5. No sistema, em **Administração > Configurações > Vídeos do YouTube**, informe a chave e clique em **Salvar a chave**. Ela é conferida no Google antes de ser salva e fica no banco cifrada, como a senha do e-mail. Não é preciso reiniciar o serviço.

  Os vídeos gravados só com o título e o autor recebem os dados que faltam pelo botão **Atualizar as informações** de cada um. Se a chave parar de funcionar (removida, sem cota no dia), o sistema volta a usar a página e o oEmbed, e o motivo aparece nos registros do serviço.
- **Avisos por e-mail:** os avisos de vencimento saem de uma tarefa que roda dentro da própria aplicação, por isso o Gunicorn continua com um único processo. Para desligá-los, altere `AVISOS_ATIVOS` para `False` em `config.py` e reinicie o serviço.
- **CAPTCHA:** o login, o cadastro e o Esqueci minha senha pedem o código de uma imagem gerada no próprio servidor, sem serviço externo. Para desligá-lo, altere `CAPTCHA_ATIVO` para `False` em `config.py` e reinicie o serviço.
- **Confirmação do e-mail:** com o envio de e-mails configurado em Administração > Configurações (e o serviço reiniciado depois do primeiro salvamento), quem se cadastra recebe um link e só entra depois de confirmar o e-mail. As contas criadas pelo administrador e as que já existiam contam como confirmadas.
- **Esqueci minha senha:** o link fica na tela de login, à direita do Criar conta, e pede só o e-mail e o código da imagem. A resposta é sempre a mesma, com ou sem conta para o e-mail, e as instruções saem em segundo plano, para a demora ou um erro do servidor SMTP não revelarem quem tem conta. Cada conta recebe até 3 e-mails de nova senha por hora. Sem o envio de e-mails configurado, nada é enviado, e o aviso fica nos registros do serviço (`sudo journalctl -u projetos-demandas | grep "Esqueci minha senha"`).
- **Redefinir a senha:** em Administração > Usuários, o ícone da chave, à esquerda do Editar, gera uma nova senha e a envia por e-mail à pessoa, com o endereço de acesso e o usuário. Exige o envio de e-mails configurado; se o envio falhar, a senha antiga continua valendo. A redefinição encerra as sessões abertas da pessoa, que cria uma senha própria no primeiro acesso.
- **Senhas:** as senhas novas têm pelo menos 10 caracteres e não podem ser fáceis de adivinhar. As senhas já cadastradas continuam valendo até serem trocadas.
- **Limite de tentativas:** o login, o cadastro, a recuperação de senha, a imagem do CAPTCHA, a busca de vídeos e o envio de arquivos têm um limite de requisições por IP ou por usuário (`LIMITES` em `seguranca.py`). Os contadores ficam na memória do processo e recomeçam quando o serviço é reiniciado. Para desligá-lo, altere `LIMITES_ATIVOS` para `False` em `config.py` e reinicie o serviço.
- **Aplicativo instalável:** no celular e no computador, o sistema pode ser instalado como aplicativo (menu do usuário > Instalar o aplicativo, no Chrome e no Edge, ou Compartilhar > Adicionar à Tela de Início, no iPhone). Isso exige HTTPS com um certificado válido: com o certificado autoassinado do servidor acessado pelo IP, o navegador não instala o aplicativo nem guarda os arquivos para abrir mais rápido, e o restante do sistema continua funcionando.
- **Limite de arquivos:** o espaço total de cada usuário vem do plano dele, mas o tamanho de cada envio vem de `config.py`. Se `LIMITE_ANEXOS` ou `TAMANHO_MAXIMO_ANEXO` forem alterados em `config.py`, ajuste também `client_max_body_size` no Nginx.

### Cópia de segurança

Os dados ficam em dois lugares, e a cópia precisa incluir os dois: o banco e a pasta `userfiles/`, que guarda os anexos, as imagens das descrições e as fotos dos perfis. Os comandos abaixo são do SQLite; com outro banco, troque a linha do `sqlite3` pela cópia descrita em [Cópia de segurança dos outros bancos](#cópia-de-segurança-dos-outros-bancos).

As cópias têm os dados de todos os usuários. Por isso, a pasta fica acessível só ao `root`, os arquivos são criados sem leitura para os demais usuários do servidor (`umask 077`) e a cópia é cifrada com o `gpg` antes de sair do servidor. Instale o `gpg` e crie a frase secreta da cifragem, uma vez só:

```bash
sudo apt install -y gnupg
sudo install -d -m 700 /var/backups/projetos-demandas
sudo sh -c 'umask 077; python3 -c "import secrets; print(secrets.token_urlsafe(32))" > /root/.backup-projetos-demandas'
```

Guarde essa frase também fora do servidor: sem ela, as cópias não podem ser abertas.

Para cada cópia:

```bash
sudo sh -c '
umask 077
cd /var/backups/projetos-demandas
DATA=$(date +%F)
sqlite3 /opt/projetos-demandas/database/projetos_demandas.db ".backup banco-$DATA.db"
tar -czf projetos-demandas-$DATA.tar.gz banco-$DATA.db -C /opt/projetos-demandas userfiles
gpg --batch --yes --pinentry-mode loopback --passphrase-file /root/.backup-projetos-demandas --symmetric --cipher-algo AES256 -o projetos-demandas-$DATA.tar.gz.gpg projetos-demandas-$DATA.tar.gz
rm -f banco-$DATA.db projetos-demandas-$DATA.tar.gz
'
```

Fica só o arquivo `projetos-demandas-AAAA-MM-DD.tar.gz.gpg`. Para restaurar, decifre-o com a mesma frase:

```bash
sudo gpg --batch --pinentry-mode loopback --passphrase-file /root/.backup-projetos-demandas -d projetos-demandas-AAAA-MM-DD.tar.gz.gpg | tar -xz
```

Guarde as cópias cifradas e o arquivo `/etc/projetos-demandas.env` fora do servidor, em locais diferentes: o arquivo de ambiente tem a `SECRET_KEY`, que decifra a senha do e-mail gravada no banco.

### Atualização do sistema

Faça uma cópia de segurança, pare o serviço e envie os arquivos novos com o mesmo `rsync` do passo 3. No servidor, atualize a pasta sem tocar nos dados:

```bash
sudo systemctl stop projetos-demandas
sudo rsync -a --chown=root:root --exclude .venv --exclude database --exclude userfiles /tmp/projetos-demandas/ /opt/projetos-demandas/
sudo /opt/projetos-demandas/.venv/bin/python -m pip install -r /opt/projetos-demandas/requirements.txt gunicorn
sudo systemctl start projetos-demandas
```

No SQLite, as alterações no banco são aplicadas automaticamente quando o serviço inicia. Nos outros bancos, aplique-as com o usuário dono antes do `systemctl start`, como em [Atualização com outro banco](#atualização-com-outro-banco). Quem usa o aplicativo instalado recebe o CSS e o JavaScript novos a partir da segunda vez que abre o sistema depois da atualização.

## Outros bancos de dados

O SQLite é o padrão e não precisa de configuração. O sistema também funciona com:

| Banco | Versão mínima | `BANCO_TIPO` | Driver (`pip install -r`) | Porta padrão |
|---|---|---|---|---|
| MariaDB | 10.6 | `mariadb` | `requirements-mariadb.txt` | 3306 |
| MySQL | 8.0 | `mysql` | `requirements-mysql.txt` | 3306 |
| PostgreSQL | 13 | `postgresql` | `requirements-postgresql.txt` | 5432 |
| Oracle | 19c | `oracle` | `requirements-oracle.txt` | 1521 |
| Microsoft SQL Server | 2019 | `mssql` | `requirements-mssql.txt` | 1433 |

O banco é escolhido só pelas variáveis abaixo, no arquivo de ambiente do serviço (`/etc/projetos-demandas.env`), e nunca pela interface. A tela Administração > Configurações mostra o banco em uso, sem a senha, e avisa quando a conexão com um servidor de outra máquina não é cifrada ou não confere o certificado.

| Variável | Uso |
|---|---|
| `BANCO_TIPO` | `sqlite` (padrão), `mariadb`, `mysql`, `postgresql`, `oracle` ou `mssql`. |
| `BANCO_ARQUIVO` | Só no SQLite: outro arquivo no lugar de `database/projetos_demandas.db`. |
| `BANCO_SERVIDOR` | Nome ou IP do servidor do banco. |
| `BANCO_PORTA` | Opcional: sem ela, vale a porta padrão do banco. |
| `BANCO_NOME` | Nome do banco. No Oracle, o nome do serviço (o PDB). |
| `BANCO_USUARIO` | Usuário da aplicação, que só lê e grava os dados. |
| `BANCO_SENHA_ARQUIVO` | Arquivo com a senha do usuário da aplicação. |
| `BANCO_USUARIO_DONO` | Usuário dono das tabelas, que as cria e altera. |
| `BANCO_SENHA_DONO_ARQUIVO` | Arquivo com a senha do dono. |
| `BANCO_TLS` | `verificar` (padrão para servidor de outra máquina), `exigir` ou `desligado` (padrão para `localhost` e `127.0.0.1`). |
| `BANCO_TLS_CA` | Arquivo com o certificado da autoridade que assinou o certificado do banco. |
| `BANCO_DRIVER_ODBC` | Só no SQL Server: o driver ODBC instalado (padrão `ODBC Driver 18 for SQL Server`). |
| `BANCO_ESQUEMA` | Só no Oracle: o esquema das tabelas, quando não é o do `BANCO_USUARIO_DONO`. |
| `BANCO_ATUALIZAR_AO_INICIAR` | `1` para aplicar as migrações ao iniciar também fora do SQLite (não recomendado: exige que o usuário da aplicação possa alterar as tabelas). |

`BANCO_SENHA` e `BANCO_SENHA_DONO` também são aceitas, com a senha direto na variável, mas os arquivos são preferíveis: assim a senha não fica no arquivo de ambiente.

### Segurança

- **Dois usuários no banco.** O **dono** cria e altera as tabelas e só é usado pelo comando `flask banco atualizar`, rodado pelo administrador. O usuário da **aplicação**, usado pelo serviço, só lê, inclui, altera e exclui linhas: uma falha na aplicação não consegue apagar nem alterar as tabelas. O `flask banco verificar` avisa quando o usuário da aplicação consegue criar tabelas.
- **Senhas fora do arquivo de ambiente.** A senha da aplicação fica num arquivo legível só pelo serviço, e a do dono, num arquivo legível só pelo `root`, que o serviço nem consegue ler.
- **Conexão cifrada.** Com o banco em outra máquina, use `BANCO_TLS=verificar`: a conexão é cifrada e o certificado do servidor é conferido (a autoridade e o nome), o que impede que alguém na rede se passe pelo banco. `exigir` cifra sem conferir o certificado e só protege contra quem apenas escuta a rede. `desligado` serve só para o banco na mesma máquina, ouvindo em `127.0.0.1`.
- **Rede.** O servidor do banco não deve ficar acessível pela internet: libere a porta só para o IP do servidor da aplicação e, no próprio banco, aceite os usuários só a partir desse IP.
- **Texto em UTF-8.** O banco precisa guardar o texto em UTF-8 (`utf8mb4` no MariaDB e no MySQL, `UTF8` no PostgreSQL, `AL32UTF8` no Oracle e uma ordenação `_UTF8` no SQL Server), senão os acentos e os emojis se perdem. O `flask banco atualizar` se recusa a criar as tabelas sem isso.
- **Cópias de segurança cifradas**, como as do SQLite: veja [Cópia de segurança dos outros bancos](#cópia-de-segurança-dos-outros-bancos).

### 1. Instalar o driver

Com o ambiente virtual do passo 4 da produção, instale o driver do banco escolhido (o exemplo é do PostgreSQL):

```bash
sudo /opt/projetos-demandas/.venv/bin/python -m pip install -r /opt/projetos-demandas/requirements-postgresql.txt
```

O driver do Oracle (`oracledb`) funciona no modo *thin*, sem o Oracle Client. O do SQL Server (`pyodbc`) precisa do Microsoft ODBC Driver 18, instalado pelo repositório da Microsoft:

```bash
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
curl -fsSL "https://packages.microsoft.com/config/debian/$(. /etc/os-release; echo "$VERSION_ID")/prod.list" | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt update
sudo ACCEPT_EULA=Y apt install -y msodbcsql18 unixodbc
```

Se a Microsoft ainda não publicar o repositório do Debian 13, troque `$(. /etc/os-release; echo "$VERSION_ID")` por `12` e confira se o arquivo baixado aponta para `packages.microsoft.com`.

### 2. Criar o banco e os usuários

Gere duas senhas fortes, uma para cada usuário, e use-as nos comandos abaixo no lugar de `SENHA_DO_DONO` e `SENHA_DA_APLICACAO`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

Nos exemplos, `10.0.0.5` é o IP do servidor da aplicação.

#### MariaDB e MySQL

No servidor do banco, como administrador (`sudo mariadb` ou `sudo mysql`):

```sql
CREATE DATABASE projetos_demandas CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pd_dono'@'10.0.0.5' IDENTIFIED BY 'SENHA_DO_DONO' REQUIRE SSL;
GRANT ALL PRIVILEGES ON projetos_demandas.* TO 'pd_dono'@'10.0.0.5';
CREATE USER 'pd_app'@'10.0.0.5' IDENTIFIED BY 'SENHA_DA_APLICACAO' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE ON projetos_demandas.* TO 'pd_app'@'10.0.0.5';
```

No MySQL 8, a ordenação `utf8mb4_0900_ai_ci` também serve. O `REQUIRE SSL` recusa as conexões sem cifra e exige o TLS ligado no servidor (`ssl_cert` e `ssl_key` no MariaDB; no MySQL 8, ligado por padrão). Para o `BANCO_TLS=verificar`, o certificado do servidor precisa ter o nome usado em `BANCO_SERVIDOR` e ser assinado por uma autoridade conhecida (`BANCO_TLS_CA`): o certificado gerado automaticamente pelo MySQL só funciona com `exigir`. No `my.cnf`, ponha em `bind-address` o IP da rede interna, e não `0.0.0.0`.

#### PostgreSQL

No servidor do banco (`sudo -u postgres psql`):

```sql
CREATE ROLE pd_dono LOGIN PASSWORD 'SENHA_DO_DONO';
CREATE ROLE pd_app LOGIN PASSWORD 'SENHA_DA_APLICACAO';
CREATE DATABASE projetos_demandas OWNER pd_dono ENCODING 'UTF8' TEMPLATE template0;
REVOKE CONNECT ON DATABASE projetos_demandas FROM PUBLIC;
GRANT CONNECT ON DATABASE projetos_demandas TO pd_dono, pd_app;
\c projetos_demandas
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO pd_dono;
GRANT USAGE ON SCHEMA public TO pd_app;
ALTER DEFAULT PRIVILEGES FOR ROLE pd_dono IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pd_app;
ALTER DEFAULT PRIVILEGES FOR ROLE pd_dono IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO pd_app;
```

O `ALTER DEFAULT PRIVILEGES` dá ao usuário da aplicação o acesso às tabelas que o dono criar depois, também nas atualizações. No `postgresql.conf`, ligue `ssl = on` (com `ssl_cert_file` e `ssl_key_file`), mantenha `password_encryption = scram-sha-256` e ponha em `listen_addresses` só o IP da rede interna. No `pg_hba.conf`, aceite os dois usuários só com TLS e só do servidor da aplicação:

```text
hostssl projetos_demandas pd_dono,pd_app 10.0.0.5/32 scram-sha-256
```

#### Oracle

Conectado ao PDB como administrador (`sqlplus / as sysdba` e `ALTER SESSION SET CONTAINER = NOME_DO_PDB;`). O banco precisa do conjunto de caracteres `AL32UTF8`, o padrão das versões atuais:

```sql
CREATE USER pd_dono IDENTIFIED BY "SENHA_DO_DONO" DEFAULT TABLESPACE users QUOTA UNLIMITED ON users;
GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE TO pd_dono;
CREATE USER pd_app IDENTIFIED BY "SENHA_DA_APLICACAO";
GRANT CREATE SESSION TO pd_app;
```

No Oracle, cada usuário tem o próprio esquema: o sistema faz o usuário da aplicação usar as tabelas do esquema do dono (`ALTER SESSION SET CURRENT_SCHEMA`), e o `flask banco atualizar` dá a ele, tabela a tabela, o acesso de leitura e gravação. Para a conexão cifrada (`tcps`), o listener precisa de uma porta TCPS com certificado, informada em `BANCO_PORTA` (costuma ser a 2484); com `BANCO_TLS=verificar`, o nome do certificado também é conferido.

#### Microsoft SQL Server

O banco precisa de uma ordenação UTF-8, que existe a partir do SQL Server 2019. Como administrador (`sqlcmd`):

```sql
CREATE DATABASE projetos_demandas COLLATE Latin1_General_100_CI_AS_SC_UTF8;
GO
CREATE LOGIN pd_dono WITH PASSWORD = 'SENHA_DO_DONO', CHECK_POLICY = ON;
CREATE LOGIN pd_app WITH PASSWORD = 'SENHA_DA_APLICACAO', CHECK_POLICY = ON;
GO
USE projetos_demandas;
CREATE USER pd_dono FOR LOGIN pd_dono WITH DEFAULT_SCHEMA = dbo;
ALTER ROLE db_ddladmin ADD MEMBER pd_dono;
ALTER ROLE db_datareader ADD MEMBER pd_dono;
ALTER ROLE db_datawriter ADD MEMBER pd_dono;
CREATE USER pd_app FOR LOGIN pd_app WITH DEFAULT_SCHEMA = dbo;
ALTER ROLE db_datareader ADD MEMBER pd_app;
ALTER ROLE db_datawriter ADD MEMBER pd_app;
GO
```

Para o `BANCO_TLS=verificar`, o SQL Server precisa de um certificado com o nome usado em `BANCO_SERVIDOR`, assinado por uma autoridade instalada no servidor da aplicação (em `/usr/local/share/ca-certificates/`, seguido de `sudo update-ca-certificates`) ou indicado em `BANCO_TLS_CA` (ODBC Driver 18.1 ou mais novo). Ligue também o *Force Encryption* do servidor, para ele recusar as conexões sem cifra.

### 3. Configurar o sistema

No servidor da aplicação, guarde as senhas em arquivos: a da aplicação legível pelo serviço, e a do dono só pelo `root`. O `read -rs` lê a senha sem mostrá-la e sem gravá-la no histórico do shell:

```bash
sudo install -d -m 750 -o root -g projetos-demandas /etc/projetos-demandas
read -rs -p "Senha da aplicação: " SENHA; echo
printf "%s" "$SENHA" | sudo install -m 640 -o root -g projetos-demandas /dev/stdin /etc/projetos-demandas/banco.senha
read -rs -p "Senha do dono: " SENHA; echo
printf "%s" "$SENHA" | sudo install -m 600 -o root -g root /dev/stdin /etc/projetos-demandas/banco-dono.senha
unset SENHA
```

Acrescente ao `/etc/projetos-demandas.env` (exemplo do PostgreSQL; copie para `/etc/projetos-demandas/ca-do-banco.pem` o certificado da autoridade do banco):

```text
BANCO_TIPO=postgresql
BANCO_SERVIDOR=banco.exemplo.com
BANCO_NOME=projetos_demandas
BANCO_USUARIO=pd_app
BANCO_SENHA_ARQUIVO=/etc/projetos-demandas/banco.senha
BANCO_USUARIO_DONO=pd_dono
BANCO_SENHA_DONO_ARQUIVO=/etc/projetos-demandas/banco-dono.senha
BANCO_TLS=verificar
BANCO_TLS_CA=/etc/projetos-demandas/ca-do-banco.pem
```

Com o banco na mesma máquina, use `BANCO_SERVIDOR=127.0.0.1`, e o TLS fica desligado por padrão. O `ProtectSystem=strict` do serviço deixa o `/etc` só para leitura, o que basta para ler esses arquivos.

### 4. Criar as tabelas e conferir

Os comandos `flask banco` leem o mesmo arquivo de ambiente do serviço. O `atualizar` usa o usuário dono, por isso roda como `root`, que lê a senha dele; o `verificar` roda com o usuário do serviço, que é quem a aplicação usa:

```bash
sudo sh -c 'set -a; . /etc/projetos-demandas.env; set +a; cd /opt/projetos-demandas && .venv/bin/flask --app app banco atualizar'
sudo -u projetos-demandas sh -c 'set -a; . /etc/projetos-demandas.env; set +a; cd /opt/projetos-demandas && .venv/bin/flask --app app banco verificar'
```

O `verificar` mostra o banco, a versão do servidor, a codificação, se a conexão está cifrada e se as tabelas estão na última versão, e avisa quando o usuário da aplicação pode alterar as tabelas. Depois, siga com o passo 6 da produção. Ao iniciar num banco novo, o sistema cria o plano padrão e a conta inicial.

Enquanto as tabelas não forem criadas ou atualizadas, o sistema responde "Sistema em manutenção" (código 503) em todas as páginas.

### Migração de uma instalação em SQLite

1. Faça uma cópia de segurança e pare o serviço: `sudo systemctl stop projetos-demandas`.
2. Prepare o banco novo com os passos 1 a 4 acima, sem iniciar o serviço.
3. Copie os dados. O banco de destino precisa estar vazio, ou só com o plano padrão e a conta inicial, que são substituídos; o SQLite precisa estar na última versão, o que acontece sempre que o sistema o abre:

   ```bash
   sudo sh -c 'set -a; . /etc/projetos-demandas.env; set +a; cd /opt/projetos-demandas && .venv/bin/flask --app app banco copiar --de sqlite:////opt/projetos-demandas/database/projetos_demandas.db'
   ```

   O comando confere, no fim, a quantidade de linhas de cada tabela. A pasta `userfiles/` continua no mesmo lugar; ao trocar também de servidor da aplicação, copie-a com o `rsync`.
4. Inicie o serviço e confira o sistema. Guarde o arquivo SQLite antigo, cifrado e fora do servidor, até ter certeza de que tudo foi copiado, e depois apague-o.

O mesmo comando copia entre dois bancos quaisquer: `--de` recebe o endereço SQLAlchemy da origem, como `postgresql+psycopg://usuario@servidor/banco`. Não ponha a senha nesse endereço, porque a linha de comando aparece na lista de processos: no PostgreSQL, use o arquivo `~/.pgpass`.

### Atualização com outro banco

Nos bancos em servidor, o sistema não altera as tabelas ao iniciar. Na [atualização do sistema](#atualização-do-sistema), faça a cópia de segurança do banco e, depois do `pip install` e antes do `systemctl start`, rode:

```bash
sudo /opt/projetos-demandas/.venv/bin/python -m pip install -r /opt/projetos-demandas/requirements-postgresql.txt
sudo sh -c 'set -a; . /etc/projetos-demandas.env; set +a; cd /opt/projetos-demandas && .venv/bin/flask --app app banco atualizar'
```

### Cópia de segurança dos outros bancos

Troque a linha do `sqlite3` da [cópia de segurança](#cópia-de-segurança) pelo comando do banco, que grava o arquivo `banco-$DATA` cifrado depois com o `gpg`, junto com a pasta `userfiles/` (ajuste o nome do arquivo no `tar` e no `rm`):

| Banco | Comando |
|---|---|
| MariaDB | `mariadb-dump --single-transaction --routines projetos_demandas > banco-$DATA.sql` |
| MySQL | `mysqldump --single-transaction --routines projetos_demandas > banco-$DATA.sql` |
| PostgreSQL | `pg_dump -Fc -d projetos_demandas -f banco-$DATA.dump` |
| Oracle | `expdp pd_dono SCHEMAS=pd_dono DIRECTORY=DATA_PUMP_DIR DUMPFILE=banco-$DATA.dmp` (o arquivo fica na pasta do `DATA_PUMP_DIR`, no servidor do banco) |
| SQL Server | `BACKUP DATABASE projetos_demandas TO DISK = '/var/opt/mssql/backup/banco.bak' WITH ENCRYPTION (ALGORITHM = AES_256, SERVER CERTIFICATE = CertificadoDoBackup)`, no servidor do banco |

Faça as cópias com um usuário só de leitura (no MariaDB e no MySQL, com `SELECT`, `SHOW VIEW`, `LOCK TABLES` e `EVENT`), com a senha num arquivo de opções legível só pelo `root` (`~/.my.cnf`, `~/.pgpass`), e nunca na linha de comando. Teste a restauração de vez em quando, num banco separado.

### Testado

O SQLite e o SQL Server (2025, no LocalDB do Windows, com a ordenação UTF-8) rodaram a suíte de testes inteira; a cópia de um SQLite real para o SQL Server conferiu todas as linhas. Para o MariaDB, o MySQL, o PostgreSQL e o Oracle, os testes conferem as tabelas geradas, a conexão e as opções de TLS, sem um servidor real: antes de usar um deles em produção, rode a suíte nele com `URL_DO_BANCO_DE_TESTE`.
