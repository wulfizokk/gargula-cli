"""Brand & Offer DNA: o cérebro da marca, avatar, oferta e filtro anti-slop.

Guarda os arquivos de identidade em ~/.gargula/dna/:
- avatar.md: dores reais, desejos, nível de consciência, gírias e vocabulário do cliente.
- oferta.md: promessa principal, mecanismo único, bônus, garantia, ancoragem e preços.
- marca.md: tom de voz, arquétipo, posicionamento e regras de estilo.
- anti_slop.md: palavras banidas e clichês de IA proibidos.
"""

from __future__ import annotations

import os
from pathlib import Path

from gargula import config

CATEGORIAS = ("avatar", "oferta", "marca", "anti_slop")

ANTI_SLOP_PADRAO = """# Filtro Anti-Slop (Clichês de IA Proibidos)

Nunca use expressões genéricas e vazias de IA em nenhuma copy, anúncio ou mensagem:
- "no mundo acelerado de hoje"
- "mergulhe fundo" / "mergulhar de cabeça"
- "transforme sua jornada" / "embarque nesta jornada"
- "revolucione seu negócio" / "revolucionário" (sem mecanismo concreto)
- "divisor de águas" / "game changer"
- "alavanque seus resultados"
- "neste guia abrangente" / "este artigo completo"
- "é importante lembrar que" / "vale ressaltar que"
- "em um mercado cada vez mais competitivo"
- "descubra os segredos de"
- "desvende o poder"
- "sem mais delongas"
- "orquestrar uma sinfonia de"
- "não perca essa oportunidade única" (sem escassez real)

Regra de ouro: substitua adjetivos vazios por fatos, números, prazos, mecanismos e exemplos concretos.
"""

TEMPLATES = {
    "avatar": """# Avatar e Público-Alvo

## Dores Viscerais (o que tira o sono dele às 2h da manhã)
- Frustração com métodos genéricos que não trazem retorno prático.
- Medo de queimar dinheiro em anúncios sem saber onde está errando.
- Cansaço de ferramentas complexas e assinaturas caras.

## Desejos Concretos (o que ele quer ver acontecendo)
- Fechar vendas todos os dias com previsibilidade.
- Saber o ROAS real sem depender de achismos.
- Atendimento rápido no WhatsApp sem risco de perder o chip.

## Vocabulário Real e Gírias do Nicho
- Termos: ROAS, CPA, criativo, checkout, escala, conversão, lead, esteira, VSL.
- Frases comuns: "tá caro", "vou ver com meu sócio", "o Meta tá comendo meu orçamento".
""",
    "oferta": """# Estrutura da Oferta

## Promessa Principal
- O que o produto entrega de forma mensurável e em quanto tempo.

## Mecanismo Único (Por que funciona quando os outros falharam?)
- O método ou diferencial proprietário por trás do resultado.

## Entregáveis e Formato
- Produto principal, acesso, suporte, atualizações.

## Ancoragem de Preço e Condições
- Preço normal, preço promocional, parcelamento.

## Garantia e Bônus
- Garantia incondicional (ex.: 7, 15 ou 30 dias).
- Bônus que eliminam a próxima dor do cliente.
""",
    "marca": """# Tom de Voz e Posicionamento

## Tom de Voz
- Direto ao ponto, pragmático, sem enrolação.
- Confiante, técnico e parceiro do operador de vendas.

## Posicionamento
- Construído para quem vende de verdade na trincheira, não para acadêmicos de marketing.
""",
    "anti_slop": ANTI_SLOP_PADRAO,
}


def pasta_dna() -> Path:
    cfg = config.carregar()
    caminho_cfg = cfg.get("dna_pasta") or os.environ.get("GARGULA_DNA_PASTA")
    if caminho_cfg:
        p = Path(os.path.expanduser(caminho_cfg))
    else:
        p = config.pasta() / "dna"
    p.mkdir(parents=True, exist_ok=True)
    return p


def arquivo(categoria: str) -> Path:
    cat = categoria.lower().replace("-", "_")
    if cat not in CATEGORIAS:
        raise ValueError(f"categoria inválida: {categoria}. Use uma de: {', '.join(CATEGORIAS)}")
    return pasta_dna() / f"{cat}.md"


def obter(categoria: str) -> str:
    p = arquivo(categoria)
    if not p.is_file():
        # Se for anti_slop e não existir arquivo, retorna o padrão
        if categoria == "anti_slop":
            return ANTI_SLOP_PADRAO
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def salvar(categoria: str, conteudo: str) -> Path:
    p = arquivo(categoria)
    p.write_text(conteudo.strip() + "\n", encoding="utf-8")
    return p


def inicializar_templates():
    """Garante que os arquivos padrão existam na pasta do DNA se estiver vazia."""
    pasta = pasta_dna()
    for cat, conteudo in TEMPLATES.items():
        f = pasta / f"{cat}.md"
        if not f.is_file():
            f.write_text(conteudo, encoding="utf-8")


def listar() -> dict[str, str]:
    itens = {}
    for cat in CATEGORIAS:
        txt = obter(cat)
        itens[cat] = txt
    return itens


def formatar_contexto() -> str:
    """Retorna o bloco completo de DNA para ser injetado nos prompts das LLMs."""
    blocos = []
    for cat in ("marca", "avatar", "oferta", "anti_slop"):
        txt = obter(cat)
        if txt:
            titulo = {
                "marca": "Brand DNA (Tom de Voz e Posicionamento)",
                "avatar": "Avatar DNA (Público, Dores e Vocabulário Real)",
                "oferta": "Offer DNA (Promessa, Mecanismo e Condições)",
                "anti_slop": "Regras Anti-Slop (Termos Proibidos de IA)",
            }.get(cat, cat.title())
            blocos.append(f"### {titulo}\n\n{txt}")
    if not blocos:
        return f"### Regras Anti-Slop\n\n{ANTI_SLOP_PADRAO}"
    return "\n\n## DNA da Marca, Oferta e Filtro Anti-Slop\n\n" + "\n\n".join(blocos)

