"""War Room & Auditor de CRO Pré-Tráfego: submete páginas de vendas e ofertas a stress-test rigoroso.

Simula 3 personas impiedosas:
1. O Cético Agressivo (desconfiança, prova social fraca, risco).
2. O Impaciente dos 5 Segundos (clareza da promessa acima da dobra, CTA confuso).
3. O Racional Econômico (ancoragem, mecanismo único vs alternativas gratuitas).
"""

from __future__ import annotations

import sys
from pathlib import Path

from gargula import ferramentas, prompts, ui
from gargula.llm import responder


PROMPT_STRESS_TEST = """Você é o auditor-chefe da War Room de CRO (Conversion Rate Optimization) do Gárgula.
Sua missão é salvar o empreendedor de queimar dinheiro com tráfego pago em uma página fraca.

Analise o conteúdo da Landing Page / Oferta abaixo submetendo-a a um STRESS TEST impiedoso com 3 personas:

1. 🕵️‍♂️ O CÉTICO IMPLACÁVEL:
   - Aponta onde a promessa soa boa demais para ser verdade.
   - Caça falta de CNPJ, falta de rosto, depoimentos fáceis de forjar ou garantias vagas.

2. ⏱️ O IMPACIENTE DOS 5 SEGUNDOS:
   - Avalia a primeira dobra: nos primeiros 5 segundos um usuário comum entende O QUE É, PARA QUEM É e O QUE GANHA?
   - Aponta blocos de texto maçantes e falta de contraste no botão de ação (CTA).

3. ⚖️ O RACIONAL ECONÔMICO:
   - Pergunta: "Por que pagar isso se tem de graça no YouTube ou ChatGPT?"
   - Desmonta o mecanismo único: ele é proprietário e lógico ou é só um nome bonito para o óbvio?

Estrutura da Resposta:
1. 📊 PLACAR DE PRONTIDÃO DE TRÁFEGO (0 a 100):
   - Clareza da Promessa Acima da Dobra (0-25)
   - Mecanismo Único & Prova Concreta (0-25)
   - Oferta, Bônus & Ancoragem (0-25)
   - Redução de Risco, Garantia & CTA (0-25)
   - NOTA FINAL: [X]/100 e Veredito: [LIBERADO PARA TRÁFEGO] ou [PARE: VAI QUEIMAR DINHEIRO]

2. 🚨 OS 3 VAZAMENTOS CRÍTICOS DE CONVERSÃO (onde o lead vai desistir e fechar a aba).

3. 🛠️ PRESCRIÇÃO CIRÚRGICA DE CORREÇÃO:
   - Nova Headline recomendada (pronta para copiar).
   - Nova Sub-headline recomendada.
   - Ajuste de texto do Botão de CTA e da Seção de Garantia.

Regra: Seja cirúrgico, sem elogios vazios, sem clichês de IA.
"""


def extrair_conteudo(url: str | None = None, arquivo: str | None = None, texto_direto: str | None = None) -> str:
    if texto_direto and texto_direto.strip():
        return texto_direto.strip()
    if arquivo:
        p = Path(arquivo)
        if not p.is_file():
            raise FileNotFoundError(f"arquivo não encontrado: {arquivo}")
        return p.read_text(encoding="utf-8-sig")
    if url:
        return ferramentas.ler_url(url)
    raise ValueError("informe --url, --arquivo ou envie o texto via pipe")


def auditar(llm: dict, conteudo: str, ao_pedaco=None):
    if not ao_pedaco:
        ao_pedaco = lambda p: (sys.stdout.write(p), sys.stdout.flush())

    sistema = prompts.sistema("cro")
    pedido = (f"{PROMPT_STRESS_TEST}\n\n"
              f"--- CONTEÚDO DA PÁGINA / OFERTA ---\n\n"
              f"{conteudo[:30_000]}")

    msgs = [{"role": "user", "content": pedido}]
    return responder(llm, sistema, msgs, ao_pedaco=ao_pedaco)

