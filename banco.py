# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Escolha do banco de dados pelas variáveis de ambiente.

O padrão é o SQLite, no arquivo database/projetos_demandas.db. Os outros bancos são escolhidos
só pelo ambiente (o arquivo de ambiente do serviço, no INSTALL.md), nunca pela interface: quem
mudasse o banco pela tela poderia apontar o sistema para um servidor qualquer. A senha vem de
um arquivo (BANCO_SENHA_ARQUIVO), para não aparecer na lista de processos nem nos logs.

Este módulo não importa a aplicação: config.py o usa antes de ela existir.
"""
import os
import re
import ssl
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import URL, make_url

TIPOS_DE_BANCO = {
    "sqlite": "SQLite",
    "mariadb": "MariaDB",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "oracle": "Oracle",
    "mssql": "Microsoft SQL Server",
}
PORTAS_PADRAO = {"mariadb": 3306, "mysql": 3306, "postgresql": 5432, "oracle": 1521, "mssql": 1433}
DRIVERS = {
    "mariadb": "mariadb+pymysql",
    "mysql": "mysql+pymysql",
    "postgresql": "postgresql+psycopg",
    "oracle": "oracle+oracledb",
    "mssql": "mssql+pyodbc",
}
# Quem instala o driver de cada banco: pip install -r requirements-<tipo>.txt
PACOTES_DOS_DRIVERS = {
    "mariadb": "pymysql", "mysql": "pymysql", "postgresql": "psycopg", "oracle": "oracledb", "mssql": "pyodbc",
}
DRIVER_ODBC_PADRAO = "ODBC Driver 18 for SQL Server"

# verificar: conexão cifrada e o certificado do servidor conferido (nome e autoridade).
# exigir: conexão cifrada, sem conferir o certificado (só contra quem apenas escuta a rede).
# desligado: sem cifra, aceitável só quando o banco está na mesma máquina.
MODOS_DE_TLS = {
    "verificar": "Cifrada, com o certificado do servidor conferido",
    "exigir": "Cifrada, sem conferir o certificado do servidor",
    "desligado": "Sem cifra",
}
SERVIDORES_LOCAIS = {"localhost", "127.0.0.1", "::1"}
# Nome de usuário (esquema) do Oracle sem aspas: vai direto no ALTER SESSION.
ESQUEMA_VALIDO = re.compile(r"[A-Za-z][A-Za-z0-9_$#]{0,127}")

# Uma conexão parada por mais de uma hora é refeita: os servidores encerram as conexões ociosas
# (o wait_timeout do MySQL, por exemplo), e o pre_ping confere a conexão antes de usá-la.
OPCOES_DO_MOTOR_EM_SERVIDOR = {"pool_pre_ping": True, "pool_recycle": 3600}


class ErroNaConfiguracaoDoBanco(ValueError):
    """Uma variável BANCO_* com um valor que não pode ser usado."""


@dataclass
class ConfiguracaoDoBanco:
    tipo: str
    url: URL
    opcoes_do_motor: dict = field(default_factory=dict)
    tls: str = "desligado"
    servidor: str = ""
    nome: str = ""
    usuario: str = ""
    # Oracle: o esquema do dono, onde ficam as tabelas que o usuário da aplicação acessa.
    esquema: str = ""

    @property
    def nome_do_tipo(self):
        return TIPOS_DE_BANCO[self.tipo]

    @property
    def em_servidor(self):
        return self.tipo != "sqlite"

    @property
    def endereco_sem_senha(self):
        return self.url.render_as_string(hide_password=True)

    def descricao(self):
        """O que a tela de Configurações mostra ao administrador (sem a senha)."""
        if not self.em_servidor:
            return {"tipo": self.nome_do_tipo, "servidor": "", "nome": self.nome, "usuario": "", "tls": ""}
        return {
            "tipo": self.nome_do_tipo,
            "servidor": self.servidor,
            "nome": self.nome,
            "usuario": self.usuario or "Autenticação do Windows",
            "tls": MODOS_DE_TLS[self.tls],
        }

    def aviso_de_tls(self):
        """Um aviso quando a conexão com um servidor de outra máquina não é cifrada ou conferida."""
        if not self.em_servidor or servidor_local(self.servidor):
            return ""
        if self.tls == "desligado":
            return "A conexão com o banco de dados não é cifrada: a senha e os dados passam abertos pela rede."
        if self.tls == "exigir":
            return (
                "O certificado do banco de dados não é conferido: alguém na rede pode se passar pelo "
                "servidor. Use BANCO_TLS=verificar."
            )
        return ""


def servidor_local(servidor):
    servidor = (servidor or "").strip().lower()
    return servidor in SERVIDORES_LOCAIS or servidor.startswith("(localdb)")


def ler_senha(ambiente, variavel_do_arquivo, variavel_direta):
    """A senha vem do arquivo indicado (preferível) ou, na falta dele, da variável direta."""
    caminho = ambiente.get(variavel_do_arquivo, "").strip()
    if caminho:
        try:
            return Path(caminho).read_text(encoding="utf-8").strip("\r\n")
        except OSError as erro:
            raise ErroNaConfiguracaoDoBanco(
                "Não foi possível ler {} ({}): {}".format(variavel_do_arquivo, caminho, erro.strerror)
            ) from erro
    return ambiente.get(variavel_direta, "")


def contexto_tls(modo, autoridade):
    """O SSLContext usado pelo MySQL, MariaDB e Oracle."""
    contexto = ssl.create_default_context(cafile=autoridade or None)
    # O Python 3.13 liga a verificação estrita do X.509, que recusa certificados válidos de
    # muitas autoridades internas; a cadeia e o nome continuam conferidos.
    contexto.verify_flags &= ~ssl.VERIFY_X509_STRICT
    if modo == "exigir":
        contexto.check_hostname = False
        contexto.verify_mode = ssl.CERT_NONE
    return contexto


def _tls_do_ambiente(ambiente, servidor):
    modo = ambiente.get("BANCO_TLS", "").strip().lower()
    if not modo:
        modo = "desligado" if servidor_local(servidor) else "verificar"
    if modo not in MODOS_DE_TLS:
        raise ErroNaConfiguracaoDoBanco(
            "BANCO_TLS deve ser {}.".format(", ".join(MODOS_DE_TLS))
        )
    autoridade = ambiente.get("BANCO_TLS_CA", "").strip()
    if autoridade and not Path(autoridade).is_file():
        raise ErroNaConfiguracaoDoBanco("O arquivo de BANCO_TLS_CA não existe: {}".format(autoridade))
    return modo, autoridade


def _porta(ambiente, tipo):
    texto = ambiente.get("BANCO_PORTA", "").strip()
    if not texto:
        return PORTAS_PADRAO[tipo]
    if not texto.isdigit() or not 0 < int(texto) < 65536:
        raise ErroNaConfiguracaoDoBanco("BANCO_PORTA deve ser um número entre 1 e 65535.")
    return int(texto)


def _sqlite(ambiente, arquivo_padrao):
    arquivo = Path(ambiente.get("BANCO_ARQUIVO", "").strip() or arquivo_padrao)
    return ConfiguracaoDoBanco(
        tipo="sqlite",
        url=URL.create("sqlite", database=arquivo.as_posix()),
        nome=arquivo.name,
    )


def montar_conexao(tipo, servidor, porta, nome, usuario, senha, tls, autoridade, driver_odbc=DRIVER_ODBC_PADRAO):
    """A URL e as opções de conexão de um banco em servidor."""
    argumentos = {}
    consulta = {}
    host = servidor
    database = nome
    porta_da_url = porta

    if tipo in ("mariadb", "mysql"):
        # utf8mb4: o "utf8" do MySQL guarda só 3 bytes por caractere e perde os emojis.
        consulta["charset"] = "utf8mb4"
        if tls != "desligado":
            argumentos["ssl"] = contexto_tls(tls, autoridade)
    elif tipo == "postgresql":
        argumentos["sslmode"] = {"verificar": "verify-full", "exigir": "require", "desligado": "disable"}[tls]
        if tls == "verificar":
            # "system": as autoridades do sistema operacional, quando não há um arquivo próprio.
            argumentos["sslrootcert"] = autoridade or "system"
    elif tipo == "oracle":
        protocolo = "tcp" if tls == "desligado" else "tcps"
        # O endereço vai inteiro no dsn (Easy Connect): host, porta e o nome do serviço.
        argumentos["dsn"] = "{}://{}:{}/{}".format(protocolo, servidor, porta, nome)
        if tls != "desligado":
            argumentos["ssl_context"] = contexto_tls(tls, autoridade)
            argumentos["ssl_server_dn_match"] = tls == "verificar"
        host = database = porta_da_url = None
    elif tipo == "mssql":
        consulta["driver"] = driver_odbc
        # LongAsMax: o VARCHAR(max) vai inteiro, sem o limite de 4000 caracteres dos parâmetros.
        consulta["LongAsMax"] = "Yes"
        consulta["Encrypt"] = "no" if tls == "desligado" else "yes"
        consulta["TrustServerCertificate"] = "yes" if tls == "exigir" else "no"
        if tls == "verificar" and autoridade:
            # ODBC Driver 18.1 ou mais novo: o certificado esperado do servidor.
            consulta["ServerCertificate"] = autoridade
        if not usuario:
            consulta["Trusted_Connection"] = "yes"
        if servidor_local(servidor) and servidor.lower().startswith("(localdb)"):
            porta_da_url = None
    else:
        raise ErroNaConfiguracaoDoBanco("Tipo de banco desconhecido: {}".format(tipo))

    url = URL.create(
        DRIVERS[tipo],
        username=usuario or None,
        password=senha or None,
        host=host,
        port=porta_da_url,
        database=database,
        query=consulta,
    )
    return url, argumentos


def ler_configuracao(ambiente=None, arquivo_padrao="database/projetos_demandas.db", dono=False):
    """A configuração do banco a partir do ambiente.

    Com dono=True, usa o usuário dono das tabelas (BANCO_USUARIO_DONO), que pode criá-las e
    alterá-las: só o comando flask banco atualizar precisa dele.
    """
    ambiente = os.environ if ambiente is None else ambiente
    tipo = ambiente.get("BANCO_TIPO", "").strip().lower() or "sqlite"
    if tipo not in TIPOS_DE_BANCO:
        raise ErroNaConfiguracaoDoBanco(
            "BANCO_TIPO deve ser {}.".format(", ".join(TIPOS_DE_BANCO))
        )
    if tipo == "sqlite":
        return _sqlite(ambiente, arquivo_padrao)

    servidor = ambiente.get("BANCO_SERVIDOR", "").strip()
    nome = ambiente.get("BANCO_NOME", "").strip()
    if not servidor or not nome:
        raise ErroNaConfiguracaoDoBanco("Informe BANCO_SERVIDOR e BANCO_NOME.")
    usuario = ambiente.get("BANCO_USUARIO", "").strip()
    senha = ler_senha(ambiente, "BANCO_SENHA_ARQUIVO", "BANCO_SENHA")
    if dono and ambiente.get("BANCO_USUARIO_DONO", "").strip():
        usuario = ambiente["BANCO_USUARIO_DONO"].strip()
        senha = ler_senha(ambiente, "BANCO_SENHA_DONO_ARQUIVO", "BANCO_SENHA_DONO")
    if not usuario and tipo != "mssql":
        raise ErroNaConfiguracaoDoBanco("Informe BANCO_USUARIO.")
    porta = _porta(ambiente, tipo)
    tls, autoridade = _tls_do_ambiente(ambiente, servidor)
    driver_odbc = ambiente.get("BANCO_DRIVER_ODBC", "").strip() or DRIVER_ODBC_PADRAO

    esquema = ""
    if tipo == "oracle":
        # No Oracle, cada usuário tem o próprio esquema: o da aplicação usa as tabelas do dono.
        esquema = ambiente.get("BANCO_ESQUEMA", "").strip() or ambiente.get("BANCO_USUARIO_DONO", "").strip()
        if esquema.upper() == usuario.upper():
            esquema = ""
        if esquema and not ESQUEMA_VALIDO.fullmatch(esquema):
            raise ErroNaConfiguracaoDoBanco("BANCO_ESQUEMA (ou BANCO_USUARIO_DONO) não é um nome válido do Oracle.")

    url, argumentos = montar_conexao(tipo, servidor, porta, nome, usuario, senha, tls, autoridade, driver_odbc)
    opcoes = dict(OPCOES_DO_MOTOR_EM_SERVIDOR)
    if argumentos:
        opcoes["connect_args"] = argumentos
    return ConfiguracaoDoBanco(
        tipo=tipo, url=url, opcoes_do_motor=opcoes, tls=tls, servidor=servidor, nome=nome, usuario=usuario,
        esquema=esquema,
    )


def preparar_motor(motor, configuracao):
    """No Oracle, cada conexão do usuário da aplicação passa a usar o esquema do dono.

    O ouvinte entra antes dos do SQLAlchemy (insert=True): o esquema já vale quando o dialeto
    descobre o esquema padrão, na primeira conexão.
    """
    if motor.dialect.name != "oracle" or not configuracao.esquema:
        return
    comando = "ALTER SESSION SET CURRENT_SCHEMA = {}".format(configuracao.esquema.upper())

    @event.listens_for(motor, "connect", insert=True)
    def usar_o_esquema_do_dono(conexao, _registro):
        cursor = conexao.cursor()
        try:
            cursor.execute(comando)
        finally:
            cursor.close()


def atualizar_ao_iniciar(ambiente=None, tipo="sqlite"):
    """Se o sistema aplica as migrações ao iniciar: no SQLite sim; nos servidores, só pedindo,
    porque o usuário da aplicação não deve poder alterar as tabelas."""
    ambiente = os.environ if ambiente is None else ambiente
    valor = ambiente.get("BANCO_ATUALIZAR_AO_INICIAR", "").strip()
    if not valor:
        return tipo == "sqlite"
    return valor == "1"


def tipo_da_url(url):
    """O tipo (chave de TIPOS_DE_BANCO) de uma URL do SQLAlchemy."""
    dialeto = make_url(url).get_backend_name()
    return dialeto if dialeto in TIPOS_DE_BANCO else ""
