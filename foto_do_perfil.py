# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Foto do perfil: a imagem recortada no navegador é conferida e gravada de novo pelo servidor."""
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, UnidentifiedImageError

# A caixa Ajustar minha imagem do perfil tem 400 x 400 px e um círculo de 150 px de raio:
# o que está dentro dele vira a foto, de 300 x 300 px.
LADO_DA_FOTO = 300
TAMANHO_MAXIMO_DA_FOTO = 1024 * 1024
# A borda do círculo é desenhada maior e reduzida, para não ficar serrilhada.
AMPLIACAO_DA_BORDA = 4


class FotoInvalida(ValueError):
    pass


def mascara_circular():
    lado = LADO_DA_FOTO * AMPLIACAO_DA_BORDA
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).ellipse((0, 0, lado - 1, lado - 1), fill=255)
    return mascara.resize((LADO_DA_FOTO, LADO_DA_FOTO), Image.LANCZOS)


def preparar_foto(conteudo):
    """Devolve o PNG regravado, com o fundo fora do círculo transparente.

    Aceita só um PNG de 300 x 300 px, como o que o navegador gera. A imagem é lida e gravada
    de novo, o que descarta qualquer dado extra do arquivo enviado."""
    if not conteudo or len(conteudo) > TAMANHO_MAXIMO_DA_FOTO:
        raise FotoInvalida("A foto ajustada passa do tamanho permitido.")
    try:
        imagem = Image.open(BytesIO(conteudo))
        # O tamanho vem do cabeçalho: é conferido antes de a imagem ser descompactada.
        if imagem.format != "PNG" or imagem.size != (LADO_DA_FOTO, LADO_DA_FOTO):
            raise FotoInvalida("Envie a foto pela caixa Ajustar minha imagem do perfil.")
        imagem = imagem.convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as erro:
        raise FotoInvalida("Não foi possível ler a imagem enviada.") from erro

    alfa = ImageChops.multiply(imagem.getchannel("A"), mascara_circular())
    imagem.putalpha(alfa)
    saida = BytesIO()
    imagem.save(saida, format="PNG", optimize=True)
    return saida.getvalue()
