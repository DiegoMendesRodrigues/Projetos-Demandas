# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
"""Os 100 ícones dos Grupos de Usuários. Cada um é desenhado em uma grade de 24 x 24."""
from markupsafe import Markup

CATEGORIAS_DE_ICONE_GRUPO = [
    "Bombeiros",
    "Geral",
    "Governo",
    "Hidrografia",
    "Meio Ambiente",
    "Mineração",
    "Segurança",
    "Setas",
    "Tecnologia",
    "Urbanos",
    "Outros",
]

# chave: (rótulo, categoria, desenho)
_ICONES = {
    # Bombeiros
    "chama": ("Chama", "Bombeiros", '<path d="M12 3c1 4 5 6 5 11a5 5 0 0 1-10 0c0-3 2-4 3-7 1 1 2 2 2 4 1-2 1-5 0-8z"></path>'),
    "hidrante": ("Hidrante", "Bombeiros", '<path d="M8 21v-9a4 4 0 0 1 8 0v9M6 21h12M5 12h14M12 8V5M10 5h4"></path>'),
    "extintor": ("Extintor", "Bombeiros", '<path d="M9 8h6v13H9zM12 8V5h4l2-2M9 12h6"></path>'),
    "capacete": ("Capacete", "Bombeiros", '<path d="M4 16a8 8 0 0 1 16 0zM2 16h20M12 8V5M9 8.500V6.500"></path>'),
    "mangueira": ("Mangueira", "Bombeiros", '<circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="5"></circle><circle cx="12" cy="12" r="1.500"></circle>'),
    "escada": ("Escada", "Bombeiros", '<path d="M7 3v18M17 3v18M7 7h10M7 12h10M7 17h10"></path>'),
    "sirene": ("Sirene", "Bombeiros", '<path d="M6 18v-6a6 6 0 0 1 12 0v6M4 18h16M12 2v2M4 6l1.500 1.500M20 6l-1.500 1.500"></path>'),
    "machado": ("Machado", "Bombeiros", '<path d="M5 21L15 8M12 5l5-2 3 3-2 5-6-6z"></path>'),
    "caminhao": ("Caminhão", "Bombeiros", '<path d="M2 6h12v10H2zM14 9h4l4 4v3h-8"></path><circle cx="6" cy="18" r="2"></circle><circle cx="17" cy="18" r="2"></circle>'),
    # Geral
    "pessoas": ("Pessoas", "Geral", '<circle cx="9" cy="8" r="3.500"></circle><path d="M3 20a6 6 0 0 1 12 0M16 4.800a3.500 3.500 0 0 1 0 6.400M18 14.500a6 6 0 0 1 3 5.500"></path>'),
    "estrela": ("Estrela", "Geral", '<path d="M12 3l2.800 5.800 6.200.9-4.500 4.400 1.100 6.300L12 17l-5.600 3.400 1.100-6.300L3 9.700l6.200-.9z"></path>'),
    "coracao": ("Coração", "Geral", '<path d="M12 20s-8-5-8-11a4.500 4.500 0 0 1 8-2.800A4.500 4.500 0 0 1 20 9c0 6-8 11-8 11z"></path>'),
    "bandeira": ("Bandeira", "Geral", '<path d="M5 21V4M5 4h12l-2 4 2 4H5"></path>'),
    "casa": ("Casa", "Geral", '<path d="M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6"></path>'),
    "relogio": ("Relógio", "Geral", '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>'),
    "lupa": ("Lupa", "Geral", '<circle cx="11" cy="11" r="6"></circle><path d="M16 16l5 5"></path>'),
    "pino": ("Local", "Geral", '<path d="M12 21s7-6.200 7-11.500a7 7 0 0 0-14 0C5 14.800 12 21 12 21z"></path><circle cx="12" cy="9.500" r="2.500"></circle>'),
    "livro": ("Livro", "Geral", '<path d="M5 3h14v18H6a2 2 0 0 1-2-2V4a1 1 0 0 1 1-1zM4 18a2 2 0 0 1 2-2h13"></path>'),
    "mensagem": ("Mensagem", "Geral", '<path d="M4 5h16v11H9l-5 4z"></path>'),
    # Governo
    "predio-publico": ("Prédio público", "Governo", '<path d="M3 9l9-6 9 6zM5 9v9M9 9v9M15 9v9M19 9v9M3 21h18"></path>'),
    "balanca": ("Balança", "Governo", '<path d="M12 3v18M7 21h10M4 7h16M4 7l-2 7a3 3 0 0 0 6 0zM20 7l-2 7a3 3 0 0 0 6 0z"></path>'),
    "urna": ("Urna", "Governo", '<path d="M4 12h16v8H4zM8 12l1-4h6l1 4M10 16h4M11 3l1 5"></path>'),
    "documento": ("Documento", "Governo", '<path d="M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6"></path>'),
    "selo": ("Selo", "Governo", '<circle cx="12" cy="9" r="6"></circle><path d="M8.500 14L7 21l5-3 5 3-1.500-7"></path>'),
    "brasao": ("Brasão", "Governo", '<path d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z"></path><path d="M12 8l1.200 2.500 2.800.4-2 2 .5 2.800L12 14.200 9.500 15.700l.5-2.800-2-2 2.800-.4z"></path>'),
    "moeda": ("Moeda", "Governo", '<circle cx="12" cy="12" r="9"></circle><path d="M15 9.500C14.500 8.300 13.400 7.500 12 7.500c-1.700 0-3 .9-3 2.300s1.300 1.900 3 2.200 3 .8 3 2.200-1.300 2.300-3 2.300c-1.400 0-2.500-.8-3-2M12 5.500v13"></path>'),
    "microfone": ("Microfone", "Governo", '<rect x="9" y="3" width="6" height="11" rx="3"></rect><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"></path>'),
    "carimbo": ("Carimbo", "Governo", '<path d="M10 3h4v7l3 3v3H7v-3l3-3zM5 21h14"></path>'),
    # Hidrografia
    "gota": ("Gota", "Hidrografia", '<path d="M12 3s6 6.500 6 11a6 6 0 0 1-12 0c0-4.500 6-11 6-11z"></path>'),
    "onda": ("Onda", "Hidrografia", '<path d="M2 9c2.500-3 5-3 7.500 0s5 3 7.500 0l5 0M2 15c2.500-3 5-3 7.500 0s5 3 7.500 0l5 0"></path>'),
    "rio": ("Rio", "Hidrografia", '<path d="M3 4c6 0 3 6 9 6s3 6 9 6M3 12c6 0 3 6 9 6s3 3 9 3"></path>'),
    "barco": ("Barco", "Hidrografia", '<path d="M3 15h18l-3 5H6zM12 3v12M12 4l6 8h-6"></path>'),
    "ancora": ("Âncora", "Hidrografia", '<circle cx="12" cy="5" r="2"></circle><path d="M12 7v14M8 11h8M4 14a8 8 0 0 0 16 0"></path>'),
    "chuva": ("Chuva", "Hidrografia", '<path d="M7 15a4 4 0 0 1 .5-8 5 5 0 0 1 9.500 1.500A3.500 3.500 0 0 1 17 15zM8 18l-1 3M12 18l-1 3M16 18l-1 3"></path>'),
    "represa": ("Represa", "Hidrografia", '<path d="M3 5h18v3L18 21H6L3 8zM6 12h12M7 16h10"></path>'),
    "peixe": ("Peixe", "Hidrografia", '<path d="M3 12c3-5 9-6 14-1l4-3v8l-4-3c-5 5-11 4-14-1z"></path><circle cx="8" cy="11" r=".7"></circle>'),
    "poco": ("Poço", "Hidrografia", '<path d="M5 21v-8h14v8M3 13h18M7 13V6h10v7M12 6V3M9 3h6"></path>'),
    # Meio Ambiente
    "arvore": ("Árvore", "Meio Ambiente", '<path d="M12 21v-6M12 15a6 6 0 0 1-4-10.500 4 4 0 0 1 8 0A6 6 0 0 1 12 15z"></path>'),
    "folha": ("Folha", "Meio Ambiente", '<path d="M5 19C5 10 10 5 20 4c0 10-5 15-14 15zM5 19l8-8"></path>'),
    "planta": ("Planta", "Meio Ambiente", '<path d="M12 21V11M12 11c0-4 3-7 8-7 0 5-3 8-8 7zM12 15c0-3-2-5-6-5 0 4 2 6 6 5z"></path>'),
    "reciclagem": ("Reciclagem", "Meio Ambiente", '<path d="M8 4l3 5H5zM16 20l-3-5h6zM4 14l3 5M20 10l-3-5M9 19h4M15 5h-4"></path>'),
    "sol": ("Sol", "Meio Ambiente", '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"></path>'),
    "vento": ("Vento", "Meio Ambiente", '<path d="M3 9h10a3 3 0 1 0-3-3M3 15h14a3 3 0 1 1-3 3M3 12h6"></path>'),
    "flor": ("Flor", "Meio Ambiente", '<circle cx="12" cy="10" r="2"></circle><circle cx="12" cy="5" r="2.500"></circle><circle cx="17" cy="10" r="2.500"></circle><circle cx="7" cy="10" r="2.500"></circle><path d="M12 12.500V21M12 18l4-3"></path>'),
    "passaro": ("Pássaro", "Meio Ambiente", '<path d="M3 15c3 0 5-2 6-5 1 3 4 4 7 3l5-2-5-4c-3-2-6-1-7 1l-6 7zM9 10l-1 7"></path>'),
    "terra": ("Terra", "Meio Ambiente", '<circle cx="12" cy="12" r="9"></circle><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"></path>'),
    # Mineração
    "picareta": ("Picareta", "Mineração", '<path d="M4 8c4-5 12-5 16 0-5-2-11-2-16 0zM12 6L7 21"></path>'),
    "diamante": ("Diamante", "Mineração", '<path d="M6 4h12l4 6-10 11L2 10zM2 10h20M9 4l-2 6 5 11 5-11-2-6"></path>'),
    "pedra": ("Pedra", "Mineração", '<path d="M3 17l3-8 5-4 6 2 4 6-2 5-8 2zM6 9l5 3 6-4M11 12l1 7"></path>'),
    "vagoneta": ("Vagoneta", "Mineração", '<path d="M3 8h18l-2 8H5z"></path><circle cx="8" cy="19" r="1.500"></circle><circle cx="16" cy="19" r="1.500"></circle><path d="M8 5l2 3M16 5l-2 3"></path>'),
    "lanterna": ("Lanterna", "Mineração", '<path d="M9 3h6l1 5H8zM8 8h8v6l-2 7h-4l-2-7zM12 11v3"></path>'),
    "montanha": ("Montanha", "Mineração", '<path d="M2 20l7-13 4 7 3-4 6 10zM7 11l2 2 2-2"></path>'),
    "tunel": ("Túnel", "Mineração", '<path d="M3 21V11a9 9 0 0 1 18 0v10M8 21v-6a4 4 0 0 1 8 0v6M3 21h18"></path>'),
    "pa": ("Pá", "Mineração", '<path d="M14 4l6 6M12 6l6 6-6 3-3-3zM9 15l-5 5"></path>'),
    "cristal": ("Cristal", "Mineração", '<path d="M12 2l4 5v10l-4 5-4-5V7zM8 7h8M12 2v20"></path>'),
    # Segurança
    "escudo": ("Escudo", "Segurança", '<path d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z"></path>'),
    "cadeado": ("Cadeado", "Segurança", '<rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V8a4 4 0 0 1 8 0v3M12 15v2"></path>'),
    "cadeado-aberto": ("Cadeado aberto", "Segurança", '<rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V8a4 4 0 0 1 7.500-2M12 15v2"></path>'),
    "camera": ("Câmera", "Segurança", '<path d="M3 8h4l2-3h6l2 3h4v12H3z"></path><circle cx="12" cy="13" r="3.500"></circle>'),
    "olho": ("Vigilância", "Segurança", '<path d="M2 12s3.600-7 10-7 10 7 10 7-3.600 7-10 7-10-7-10-7z"></path><circle cx="12" cy="12" r="3"></circle>'),
    "alerta": ("Alerta", "Segurança", '<path d="M12 3l10 18H2zM12 10v5M12 18h.01"></path>'),
    "distintivo": ("Distintivo", "Segurança", '<path d="M12 2l3 3 4-.5.500 4 3 3-3 3-.500 4-4-.500-3 3-3-3-4 .500-.500-4-3-3 3-3 .500-4 4 .500z"></path><circle cx="12" cy="12" r="3"></circle>'),
    "cerca": ("Cerca", "Segurança", '<path d="M4 21V8l2-3 2 3v13M10 21V8l2-3 2 3v13M16 21V8l2-3 2 3v13M2 12h20M2 17h20"></path>'),
    "cofre": ("Cofre", "Segurança", '<rect x="3" y="4" width="18" height="16" rx="2"></rect><circle cx="12" cy="12" r="4"></circle><path d="M12 12l2-2M7 20v1M17 20v1"></path>'),
    # Setas
    "seta-cima": ("Seta para cima", "Setas", '<path d="M12 20V5M6 11l6-6 6 6"></path>'),
    "seta-baixo": ("Seta para baixo", "Setas", '<path d="M12 4v15M6 13l6 6 6-6"></path>'),
    "seta-esquerda": ("Seta para a esquerda", "Setas", '<path d="M20 12H5M11 6l-6 6 6 6"></path>'),
    "seta-direita": ("Seta para a direita", "Setas", '<path d="M4 12h15M13 6l6 6-6 6"></path>'),
    "seta-ciclo": ("Atualizar", "Setas", '<path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5"></path>'),
    "seta-expandir": ("Expandir", "Setas", '<path d="M14 4h6v6M20 4l-7 7M10 20H4v-6M4 20l7-7"></path>'),
    "seta-trocar": ("Trocar", "Setas", '<path d="M4 8h15M15 4l4 4-4 4M20 16H5M9 12l-4 4 4 4"></path>'),
    "seta-retorno": ("Retornar", "Setas", '<path d="M9 5L4 10l5 5M4 10h10a6 6 0 0 1 0 12h-3"></path>'),
    "seta-diagonal": ("Seta na diagonal", "Setas", '<path d="M6 18L18 6M9 6h9v9"></path>'),
    # Tecnologia
    "computador": ("Computador", "Tecnologia", '<rect x="3" y="4" width="18" height="12" rx="2"></rect><path d="M8 20h8M12 16v4"></path>'),
    "celular": ("Celular", "Tecnologia", '<rect x="7" y="2" width="10" height="20" rx="2"></rect><path d="M11 18h2"></path>'),
    "chip": ("Chip", "Tecnologia", '<rect x="6" y="6" width="12" height="12" rx="1"></rect><rect x="10" y="10" width="4" height="4"></rect><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"></path>'),
    "nuvem": ("Nuvem", "Tecnologia", '<path d="M7 18a4.500 4.500 0 0 1-.5-9 6 6 0 0 1 11.500 1.500A3.800 3.800 0 0 1 17.500 18z"></path>'),
    "banco-de-dados": ("Banco de dados", "Tecnologia", '<ellipse cx="12" cy="5.500" rx="8" ry="2.500"></ellipse><path d="M4 5.500v13c0 1.400 3.600 2.500 8 2.500s8-1.100 8-2.500v-13M4 12c0 1.400 3.600 2.500 8 2.500s8-1.100 8-2.500"></path>'),
    "codigo": ("Código", "Tecnologia", '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"></path>'),
    "wifi": ("Wi-Fi", "Tecnologia", '<path d="M2 9a15 15 0 0 1 20 0M5 13a10 10 0 0 1 14 0M8.500 16.500a5 5 0 0 1 7 0M12 20h.01"></path>'),
    "servidor": ("Servidor", "Tecnologia", '<rect x="3" y="3" width="18" height="7" rx="1"></rect><rect x="3" y="14" width="18" height="7" rx="1"></rect><path d="M7 6.500h.01M7 17.500h.01M11 6.500h6M11 17.500h6"></path>'),
    "engrenagem": ("Engrenagem", "Tecnologia", '<circle cx="12" cy="12" r="3"></circle><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"></path>'),
    # Urbanos
    "predio": ("Prédio", "Urbanos", '<path d="M5 21V3h10v18M15 9h4v12M3 21h18M8 7h4M8 11h4M8 15h4"></path>'),
    "semaforo": ("Semáforo", "Urbanos", '<rect x="8" y="2" width="8" height="20" rx="3"></rect><circle cx="12" cy="7" r="1.500"></circle><circle cx="12" cy="12" r="1.500"></circle><circle cx="12" cy="17" r="1.500"></circle>'),
    "onibus": ("Ônibus", "Urbanos", '<rect x="4" y="3" width="16" height="15" rx="2"></rect><path d="M4 11h16M7 18v3M17 18v3M8 15h.01M16 15h.01"></path>'),
    "ponte": ("Ponte", "Urbanos", '<path d="M2 17h20M5 17V9M19 17V9M5 9c4 6 10 6 14 0M9 14v3M12 15v2M15 14v3"></path>'),
    "poste": ("Poste", "Urbanos", '<path d="M12 21V6M9 21h6M12 6a5 5 0 0 1 7 0M19 6v3M17 9h4"></path>'),
    "bicicleta": ("Bicicleta", "Urbanos", '<circle cx="6" cy="16" r="4"></circle><circle cx="18" cy="16" r="4"></circle><path d="M6 16l4-8h5l3 8M10 8L9 5H7M13 12H8"></path>'),
    "loja": ("Loja", "Urbanos", '<path d="M3 9l2-5h14l2 5zM4 9v12h16V9M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0M10 21v-6h4v6"></path>'),
    "hospital": ("Hospital", "Urbanos", '<rect x="4" y="4" width="16" height="17" rx="2"></rect><path d="M12 8v7M8.500 11.500h7"></path>'),
    "banco-de-praca": ("Parque", "Urbanos", '<path d="M4 10h16M5 10v5h14v-5M7 15v5M17 15v5M6 6h12v4"></path>'),
    # Outros
    "caixa": ("Caixa", "Outros", '<path d="M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10"></path>'),
    "ferramenta": ("Ferramenta", "Outros", '<path d="M14 7a4.500 4.500 0 0 1 6-1.500L17 8.500l2 2 3-3A4.500 4.500 0 0 1 16 13L8 21a2.100 2.100 0 0 1-3-3l8-8a4.500 4.500 0 0 1 1-3z"></path>'),
    "lampada": ("Lâmpada", "Outros", '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.500c.7.7 1 1.500 1 2.500h6c0-1 .3-1.800 1-2.500A6 6 0 0 0 12 3z"></path>'),
    "trofeu": ("Troféu", "Outros", '<path d="M7 4h10v6a5 5 0 0 1-10 0zM7 6H3c0 4 2 5 4 5M17 6h4c0 4-2 5-4 5M12 15v4M8 21h8"></path>'),
    "foguete": ("Foguete", "Outros", '<path d="M12 2c4 3 5 8 4 13H8c-1-5 0-10 4-13zM8 15l-3 4 4-1M16 15l3 4-4-1M12 18v3"></path><circle cx="12" cy="9" r="1.500"></circle>'),
    "balao": ("Balão", "Outros", '<path d="M12 2a6 6 0 0 1 6 6c0 4-4 7-6 8-2-1-6-4-6-8a6 6 0 0 1 6-6zM12 16v2M10 22l2-4 2 4"></path>'),
    "bussola": ("Bússola", "Outros", '<circle cx="12" cy="12" r="9"></circle><path d="M15.500 8.500l-2 5-5 2 2-5z"></path>'),
    "ima": ("Ímã", "Outros", '<path d="M5 3v9a7 7 0 0 0 14 0V3h-4v9a3 3 0 0 1-6 0V3zM5 7h4M15 7h4"></path>'),
    "interrogacao": ("Interrogação", "Outros", '<circle cx="12" cy="12" r="9"></circle><path d="M9.500 9.500a2.500 2.500 0 1 1 3.500 2.300c-.7.400-1 1-1 1.700M12 17h.01"></path>'),
}

# (chave, rótulo, categoria), na ordem das categorias.
ICONES_GRUPO = [
    (chave, rotulo, categoria)
    for categoria in CATEGORIAS_DE_ICONE_GRUPO
    for chave, (rotulo, categoria_do_icone, _) in _ICONES.items()
    if categoria_do_icone == categoria
]
ICONE_GRUPO_PADRAO = "pessoas"


def icone_grupo(chave):
    desenho = _ICONES.get(chave, _ICONES[ICONE_GRUPO_PADRAO])[2]
    return Markup(
        '<svg class="icone" viewBox="0 0 24 24" aria-hidden="true">{}</svg>'.format(desenho)
    )
