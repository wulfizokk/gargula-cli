"""Creative Factory: gerador de ganchos virais, roteiros de alta retenção e pacotes para Meta Ads."""

from __future__ import annotations

import sys
from gargula import prompts
from gargula.llm import responder


PROMPT_GANCHOS = """Gere 10 ganchos (hooks) de alta conversão para vídeos de anúncios (Reels / TikTok / Shorts).
Cada gancho deve prender a atenção nos primeiros 3 segundos e usar vocabulário visceral, sem clichês de IA.

Estrutura das 10 variações:
1. 🥊 QUEBRA DE PADRÃO (2 variações): desmente um mito comum do nicho de cara.
2. 👁️ CURIOSIDADE VISCERAL (2 variações): abre um loop mental impossível de ignorar.
3. 🔥 DOR CRUA (2 variações): descreve exatamente o que o avatar sente e odeia passar.
4. 🏴‍☠️ INIMIGO COMUM (2 variações): coloca a culpa em um método ultrapassado ou sistema falho.
5. ⚡ REVELAÇÃO DE MECANISMO (2 variações): mostra a causa raiz do resultado.

Para cada gancho, inclua:
- O texto falado (exata primeira frase).
- A indicação de ação visual / enquadramento (ex.: close no rosto, corte seco, apontando para a tela).
"""

PROMPT_ROTEIRO = """Escreva o roteiro completo de um anúncio em vídeo de alta conversão (30 a 60 segundos).

Estrutura obrigatória segundo a metodologia de Resposta Direta:
- [00:00 - 00:03] GANCHO VISUAL + VERBAL: corte rápido, frase que interrompe o feed.
- [00:04 - 00:15] AGITAÇÃO DA DOR: conecte com o dia a dia real do público.
- [00:16 - 00:35] O MECANISMO ÚNICO: explique por que os outros métodos falham e como este funciona.
- [00:36 - 00:50] A PROVA / DEMONSTRAÇÃO: fato concreto, lógica irrefutável ou resultado prático.
- [00:51 - 00:60] CHAMADA PARA AÇÃO (CTA) E ESCASSEZ: instrução exata de onde clicar e benefício imediato.

Divida em duas colunas ou blocos: [ÁUDIO / FALA] e [VÍDEO / B-ROLL / CORTE].
"""

PROMPT_PACOTE = """Crie um pacote completo de criativos pronto para subir no Gerenciador do Meta Ads.

Entregue:
1. 📝 3 VARIAÇÕES DE TEXTO PRINCIPAL (COPY):
   - Variação A: Direta ao Ponto (curta, foco na dor e mecanismo).
   - Variação B: Storytelling / Quebra de Crença (média, foco em identificação).
   - Variação C: Prova & Lógica (foco em especificidade e números).

2. 🎯 5 HEADLINES (TÍTULOS DO ANÚNCIO):
   - Curtas, impactantes (máximo 45 caracteres).

3. 🏷️ 3 DESCRIÇÕES (FEED):
   - Reforço de garantia, bônus ou prova social.

4. 🔗 SUGESTÃO DE PARÂMETROS UTM:
   - Exemplo de URL parametrizada com utm_source, utm_medium, utm_campaign e utm_content.
"""


def gerar_ganchos(llm: dict, produto: str, publico: str | None = None, extra: str | None = None, ao_pedaco=None):
    if not ao_pedaco:
        ao_pedaco = lambda p: (sys.stdout.write(p), sys.stdout.flush())

    campos = [f"- Produto: {produto}"]
    if publico:
        campos.append(f"- Público-Alvo: {publico}")
    if extra:
        campos.append(f"- Detalhes extras: {extra}")

    pedido = f"{PROMPT_GANCHOS}\n\nDados da Oferta:\n" + "\n".join(campos)
    sistema = prompts.sistema("criativos")
    msgs = [{"role": "user", "content": pedido}]
    return responder(llm, sistema, msgs, ao_pedaco=ao_pedaco)


def gerar_roteiro(llm: dict, produto: str, publico: str | None = None, formato: str = "reels", extra: str | None = None, ao_pedaco=None):
    if not ao_pedaco:
        ao_pedaco = lambda p: (sys.stdout.write(p), sys.stdout.flush())

    campos = [f"- Produto: {produto}", f"- Formato: {formato}"]
    if publico:
        campos.append(f"- Público-Alvo: {publico}")
    if extra:
        campos.append(f"- Detalhes extras: {extra}")

    pedido = f"{PROMPT_ROTEIRO}\n\nDados da Oferta:\n" + "\n".join(campos)
    sistema = prompts.sistema("criativos")
    msgs = [{"role": "user", "content": pedido}]
    return responder(llm, sistema, msgs, ao_pedaco=ao_pedaco)


def gerar_pacote(llm: dict, produto: str, publico: str | None = None, preco: str | None = None, extra: str | None = None, ao_pedaco=None):
    if not ao_pedaco:
        ao_pedaco = lambda p: (sys.stdout.write(p), sys.stdout.flush())

    campos = [f"- Produto: {produto}"]
    if publico:
        campos.append(f"- Público-Alvo: {publico}")
    if preco:
        campos.append(f"- Preço/Condições: {preco}")
    if extra:
        campos.append(f"- Detalhes extras: {extra}")

    pedido = f"{PROMPT_PACOTE}\n\nDados da Oferta:\n" + "\n".join(campos)
    sistema = prompts.sistema("criativos")
    msgs = [{"role": "user", "content": pedido}]
    return responder(llm, sistema, msgs, ao_pedaco=ao_pedaco)

