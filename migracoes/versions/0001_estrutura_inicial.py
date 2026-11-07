# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Estrutura inicial: as tabelas como estavam ao adotar o Alembic.

Revisão: 0001
Anterior: nenhuma
Criada em: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa
import tipos_do_banco
from sqlalchemy.dialects import mssql
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects import oracle

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('configuracao_email',
    sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('servidor', sa.String(length=200), nullable=False),
    sa.Column('porta', sa.Integer(), nullable=False),
    sa.Column('usar_tls', sa.Boolean(), nullable=False),
    sa.Column('usuario', tipos_do_banco.TextoVazio(length=200), nullable=False),
    sa.Column('senha', tipos_do_banco.TextoVazio(length=500), nullable=False),
    sa.Column('email_envio', sa.String(length=200), nullable=False),
    sa.Column('nome_envio', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('desafio_captcha',
    sa.Column('token', sa.String(length=32), nullable=False),
    sa.Column('resposta_hash', sa.String(length=64), nullable=False),
    sa.Column('criado_em', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mariadb').with_variant(mssql.DATETIME2(), 'mssql').with_variant(mysql.DATETIME(fsp=6), 'mysql').with_variant(oracle.TIMESTAMP(), 'oracle'), nullable=False),
    sa.PrimaryKeyConstraint('token')
    )
    with op.batch_alter_table('desafio_captcha', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_desafio_captcha_criado_em'), ['criado_em'], unique=False)

    op.create_table('papel',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('plano_de_usuario',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('nome', sa.String(length=100), nullable=False),
    sa.Column('armazenamento_mb', sa.Integer(), nullable=False),
    sa.Column('categorias', sa.Integer(), nullable=True),
    sa.Column('projetos', sa.Integer(), nullable=True),
    sa.Column('atividades', sa.Integer(), nullable=True),
    sa.Column('listas_de_tarefas', sa.Integer(), nullable=True),
    sa.Column('videos', sa.Integer(), nullable=True),
    sa.Column('padrao', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nome')
    )
    op.create_table('usuario',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('nome', tipos_do_banco.TextoVazio(length=120), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password', sa.String(length=255), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('fs_uniquifier', sa.String(length=64), nullable=False),
    sa.Column('tema', sa.String(length=20), nullable=False),
    sa.Column('mostrar_ocultas', sa.Boolean(), nullable=False),
    sa.Column('avatar', sa.String(length=40), nullable=False),
    sa.Column('foto', tipos_do_banco.TextoVazio(length=64), nullable=False),
    sa.Column('administrador', sa.Boolean(), nullable=False),
    sa.Column('plano_id', sa.Integer(), nullable=True),
    sa.Column('telefone', tipos_do_banco.TextoVazio(length=15), nullable=False),
    sa.Column('aviso_destinatarios', sa.String(length=30), nullable=False),
    sa.Column('aviso_antecedencia', sa.Integer(), nullable=False),
    sa.Column('trocar_senha', sa.Boolean(), nullable=False),
    sa.Column('confirmed_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mariadb').with_variant(mssql.DATETIME2(), 'mssql').with_variant(mysql.DATETIME(fsp=6), 'mysql').with_variant(oracle.TIMESTAMP(), 'oracle'), nullable=True),
    sa.ForeignKeyConstraint(['plano_id'], ['plano_de_usuario.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('fs_uniquifier')
    )
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuario_plano_id'), ['plano_id'], unique=False)

    op.create_table('categoria',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('nome', sa.String(length=80), nullable=False),
    sa.Column('icone', sa.String(length=30), nullable=False),
    sa.Column('fundo', sa.String(length=20), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('categoria', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_categoria_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('grupo_de_usuarios',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('nome', sa.String(length=100), nullable=False),
    sa.Column('descricao', tipos_do_banco.TextoLongoVazio(), nullable=False),
    sa.Column('cor', sa.String(length=7), nullable=False),
    sa.Column('icone', sa.String(length=30), nullable=False),
    sa.Column('ingresso', sa.String(length=20), nullable=False),
    sa.Column('administrador_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['administrador_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('grupo_de_usuarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_grupo_de_usuarios_administrador_id'), ['administrador_id'], unique=False)

    op.create_table('usuarios_papeis',
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('papel_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['papel_id'], ['papel.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('usuario_id', 'papel_id')
    )
    op.create_table('compartilhamento_de_categoria',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('categoria_id', sa.Integer(), nullable=False),
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('permissao', sa.String(length=20), nullable=False),
    sa.ForeignKeyConstraint(['categoria_id'], ['categoria.id'], ),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupo_de_usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('categoria_id', 'grupo_id')
    )
    with op.batch_alter_table('compartilhamento_de_categoria', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_compartilhamento_de_categoria_categoria_id'), ['categoria_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_compartilhamento_de_categoria_grupo_id'), ['grupo_id'], unique=False)

    op.create_table('membros_dos_grupos',
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupo_de_usuarios.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('grupo_id', 'usuario_id')
    )
    op.create_table('projeto',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('nome', sa.String(length=80), nullable=False),
    sa.Column('cor', sa.String(length=7), nullable=False),
    sa.Column('posicao', sa.Integer(), nullable=False),
    sa.Column('concluida', sa.Boolean(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('categoria_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['categoria_id'], ['categoria.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('projeto', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_projeto_categoria_id'), ['categoria_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_projeto_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('tarefa',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('nome', sa.String(length=120), nullable=False),
    sa.Column('prioridade', sa.String(length=10), nullable=False),
    sa.Column('previsao_execucao', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mariadb').with_variant(mssql.DATETIME2(), 'mssql').with_variant(mysql.DATETIME(fsp=6), 'mysql').with_variant(oracle.TIMESTAMP(), 'oracle'), nullable=True),
    sa.Column('descricao_html', tipos_do_banco.TextoLongoVazio(), nullable=False),
    sa.Column('local', tipos_do_banco.TextoVazio(length=120), nullable=False),
    sa.Column('oculta', sa.Boolean(), nullable=False),
    sa.Column('posicao', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('secoes', tipos_do_banco.TextoVazio(length=60), nullable=False),
    sa.Column('concluida_em', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mariadb').with_variant(mssql.DATETIME2(), 'mssql').with_variant(mysql.DATETIME(fsp=6), 'mysql').with_variant(oracle.TIMESTAMP(), 'oracle'), nullable=True),
    sa.Column('projeto_id', sa.Integer(), nullable=False),
    sa.Column('responsavel_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['projeto_id'], ['projeto.id'], ),
    sa.ForeignKeyConstraint(['responsavel_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tarefa', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tarefa_projeto_id'), ['projeto_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tarefa_responsavel_id'), ['responsavel_id'], unique=False)

    op.create_table('anexo',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('nome', sa.String(length=255), nullable=False),
    sa.Column('arquivo', sa.String(length=32), nullable=False),
    sa.Column('tamanho', sa.Integer(), nullable=False),
    sa.Column('tarefa_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefa.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('arquivo')
    )
    with op.batch_alter_table('anexo', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_anexo_tarefa_id'), ['tarefa_id'], unique=False)

    op.create_table('aviso_enviado',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('tarefa_id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=10), nullable=False),
    sa.Column('previsao', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mariadb').with_variant(mssql.DATETIME2(), 'mssql').with_variant(mysql.DATETIME(fsp=6), 'mysql').with_variant(oracle.TIMESTAMP(), 'oracle'), nullable=False),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefa.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tarefa_id', 'usuario_id', 'tipo', 'previsao')
    )
    with op.batch_alter_table('aviso_enviado', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_aviso_enviado_tarefa_id'), ['tarefa_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_aviso_enviado_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('evento_da_tarefa',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('tarefa_id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('detalhe', tipos_do_banco.TextoVazio(length=200), nullable=False),
    sa.Column('texto', tipos_do_banco.TextoLongoVazio(), nullable=False),
    sa.Column('momento', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mariadb').with_variant(mssql.DATETIME2(), 'mssql').with_variant(mysql.DATETIME(fsp=6), 'mysql').with_variant(oracle.TIMESTAMP(), 'oracle'), nullable=False),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefa.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('evento_da_tarefa', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evento_da_tarefa_tarefa_id'), ['tarefa_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_evento_da_tarefa_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('imagem',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('arquivo', sa.String(length=32), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tarefa_id', sa.Integer(), nullable=True),
    sa.Column('tamanho', sa.Integer(), nullable=False),
    sa.Column('criado_em', sa.DateTime().with_variant(mysql.DATETIME(fsp=6), 'mariadb').with_variant(mssql.DATETIME2(), 'mssql').with_variant(mysql.DATETIME(fsp=6), 'mysql').with_variant(oracle.TIMESTAMP(), 'oracle'), nullable=True),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefa.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('arquivo')
    )
    with op.batch_alter_table('imagem', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_imagem_tarefa_id'), ['tarefa_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_imagem_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('item_da_tarefa',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('texto', sa.String(length=255), nullable=False),
    sa.Column('concluido', sa.Boolean(), nullable=False),
    sa.Column('posicao', sa.Integer(), nullable=False),
    sa.Column('tarefa_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefa.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('item_da_tarefa', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_item_da_tarefa_tarefa_id'), ['tarefa_id'], unique=False)

    op.create_table('marcacao',
    sa.Column('id', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('texto', sa.String(length=40), nullable=False),
    sa.Column('posicao', sa.Integer(), nullable=False),
    sa.Column('tarefa_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefa.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('marcacao', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_marcacao_tarefa_id'), ['tarefa_id'], unique=False)

    op.create_table('video_do_youtube',
    sa.Column('tarefa_id', sa.Integer(), nullable=False),
    sa.Column('endereco', sa.String(length=400), nullable=False),
    sa.Column('plataforma', sa.String(length=10), nullable=False),
    sa.Column('codigo', sa.String(length=40), nullable=False),
    sa.Column('endereco_da_miniatura', tipos_do_banco.TextoVazio(length=300), nullable=False),
    sa.Column('autor', tipos_do_banco.TextoVazio(length=100), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('descricao', tipos_do_banco.TextoLongoVazio(), nullable=False),
    sa.Column('duracao', tipos_do_banco.TextoVazio(length=20), nullable=False),
    sa.Column('publicado_em', sa.Date(), nullable=True),
    sa.Column('informacoes_adicionais', tipos_do_banco.TextoLongoVazio(), nullable=False),
    sa.Column('simplificado', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['tarefa_id'], ['tarefa.id'], ),
    sa.PrimaryKeyConstraint('tarefa_id')
    )


def downgrade():
    op.drop_table('video_do_youtube')
    with op.batch_alter_table('marcacao', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_marcacao_tarefa_id'))

    op.drop_table('marcacao')
    with op.batch_alter_table('item_da_tarefa', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_item_da_tarefa_tarefa_id'))

    op.drop_table('item_da_tarefa')
    with op.batch_alter_table('imagem', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_imagem_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_imagem_tarefa_id'))

    op.drop_table('imagem')
    with op.batch_alter_table('evento_da_tarefa', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_evento_da_tarefa_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_evento_da_tarefa_tarefa_id'))

    op.drop_table('evento_da_tarefa')
    with op.batch_alter_table('aviso_enviado', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_aviso_enviado_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_aviso_enviado_tarefa_id'))

    op.drop_table('aviso_enviado')
    with op.batch_alter_table('anexo', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_anexo_tarefa_id'))

    op.drop_table('anexo')
    with op.batch_alter_table('tarefa', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tarefa_responsavel_id'))
        batch_op.drop_index(batch_op.f('ix_tarefa_projeto_id'))

    op.drop_table('tarefa')
    with op.batch_alter_table('projeto', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_projeto_usuario_id'))
        batch_op.drop_index(batch_op.f('ix_projeto_categoria_id'))

    op.drop_table('projeto')
    op.drop_table('membros_dos_grupos')
    with op.batch_alter_table('compartilhamento_de_categoria', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_compartilhamento_de_categoria_grupo_id'))
        batch_op.drop_index(batch_op.f('ix_compartilhamento_de_categoria_categoria_id'))

    op.drop_table('compartilhamento_de_categoria')
    op.drop_table('usuarios_papeis')
    with op.batch_alter_table('grupo_de_usuarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_grupo_de_usuarios_administrador_id'))

    op.drop_table('grupo_de_usuarios')
    with op.batch_alter_table('categoria', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_categoria_usuario_id'))

    op.drop_table('categoria')
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuario_plano_id'))

    op.drop_table('usuario')
    op.drop_table('plano_de_usuario')
    op.drop_table('papel')
    with op.batch_alter_table('desafio_captcha', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_desafio_captcha_criado_em'))

    op.drop_table('desafio_captcha')
    op.drop_table('configuracao_email')
