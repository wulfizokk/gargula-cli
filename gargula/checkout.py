"""Reconciliação de Atribuição: cruza métricas do Meta Ads com vendas reais de checkout.

Suporta relatórios de checkout (Kiwify, Hotmart, Eduzz, Braip, Yampi, Shopify, Stripe, Asaas
ou qualquer CSV com colunas de status, valor e UTMs).
Calcula o ROAS Real (faturamento que de fato caiu na conta vs gasto no Meta Ads).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


STATUS_PAGO = {
    "aprovada", "aprovado", "pago", "paga", "paid", "complete", "completa",
    "finalizada", "confirmada", "active", "ativa", "settled"
}
STATUS_PENDENTE = {
    "aguardando", "aguardando pagamento", "pending", "gerado", "waiting_payment", "autorizado"
}
STATUS_CANCELADO = {
    "reembolsado", "reembolsada", "refunded", "estornado", "estornada",
    "cancelado", "cancelada", "recusado", "recusada", "chargeback", "expirado", "expirada"
}


def _normalizar(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", (s or "").lower().strip()).strip("_")


def _num(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace("$", "").replace(" ", "")
    if not s:
        return 0.0
    # Trata formato brasileiro 1.234,56 vs americano 1,234.56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def carregar_vendas(caminho_ou_texto: str) -> list[dict]:
    p = Path(caminho_ou_texto)
    if p.is_file():
        texto = p.read_text(encoding="utf-8-sig")
    else:
        texto = caminho_ou_texto

    if texto.strip().startswith("[") or texto.strip().startswith("{"):
        dados = json.loads(texto)
        return dados if isinstance(dados, list) else dados.get("data", [dados])

    linhas = list(csv.DictReader(texto.splitlines()))
    return linhas


def _achar_campo(linha: dict, candidatos: list[str]) -> str | None:
    norm_map = {_normalizar(k): k for k in linha.keys()}
    for c in candidatos:
        nc = _normalizar(c)
        if nc in norm_map:
            return linha[norm_map[nc]]
        for k_norm, k_orig in norm_map.items():
            if nc in k_norm:
                return linha[k_orig]
    return None


def identificar_transacao(linha: dict) -> dict:
    """Extrai status, valor e campanha de uma linha de qualquer checkout."""
    st_raw = _achar_campo(linha, [
        "status", "estado", "status_da_transacao", "situacao", "transaction_status", "payment_status"
    ]) or "aprovado"
    st = _normalizar(st_raw)

    palavras = set(st.split("_"))
    if any(p in st for p in STATUS_PENDENTE):
        status_final = "pendente"
    elif any(p in st for p in STATUS_CANCELADO):
        status_final = "cancelado"
    elif (palavras & STATUS_PAGO) or any(p in st for p in ("aprovad", "confirmad", "finalizad", "paid", "settled")):
        status_final = "pago"
    else:
        status_final = "pago"  # default se não identificar status negativo

    valor_raw = _achar_campo(linha, [
        "valor_liquido", "liquido", "net_amount", "valor_total", "valor", "preco", "amount", "total"
    ])
    valor = _num(valor_raw)

    campanha = _achar_campo(linha, [
        "utm_campaign", "campaign", "campanha", "sck", "src", "utm_content", "origem"
    ]) or "(direto/sem utm)"

    return {
        "status": status_final,
        "valor": round(valor, 2),
        "campanha": campanha.strip(),
        "original": linha
    }


def reconciliar(ads_resumos: list[dict], checkout_linhas: list[dict]) -> dict:
    """Cruza o gasto das campanhas do Meta Ads com as vendas reais registradas no checkout."""
    transacoes = [identificar_transacao(l) for l in checkout_linhas]

    # Agrupa vendas por campanha
    por_campanha: dict[str, dict] = {}
    for t in transacoes:
        c = t["campanha"].lower()
        if c not in por_campanha:
            por_campanha[c] = {"pagas": 0, "pendentes": 0, "canceladas": 0, "receita_real": 0.0}
        st = t["status"]
        if st == "pago":
            por_campanha[c]["pagas"] += 1
            por_campanha[c]["receita_real"] += t["valor"]
        elif st == "pendente":
            por_campanha[c]["pendentes"] += 1
        elif st == "cancelado":
            por_campanha[c]["canceladas"] += 1

    linhas_reconciliadas = []
    gasto_total = 0.0
    receita_real_total = 0.0
    compras_meta_total = 0
    pagas_total = 0

    for ad in ads_resumos:
        nome_ad = ad.get("nome", "")
        nome_lower = nome_ad.lower()
        gasto = ad.get("gasto", 0.0)
        compras_meta = ad.get("compras", 0)
        receita_meta = ad.get("receita", 0.0)

        # Procura correspondência de nome no checkout (exato ou substring)
        vendas = {"pagas": 0, "pendentes": 0, "canceladas": 0, "receita_real": 0.0}
        for c_nome, dados in por_campanha.items():
            if c_nome in nome_lower or nome_lower in c_nome or _normalizar(c_nome) in _normalizar(nome_lower):
                vendas["pagas"] += dados["pagas"]
                vendas["pendentes"] += dados["pendentes"]
                vendas["canceladas"] += dados["canceladas"]
                vendas["receita_real"] += dados["receita_real"]

        receita_real = round(vendas["receita_real"], 2)
        roas_meta = ad.get("roas")
        roas_real = round(receita_real / gasto, 2) if gasto > 0 and receita_real > 0 else 0.0
        lucro_real = round(receita_real - gasto, 2)

        # Diagnóstico de veredito
        if gasto > 0:
            if roas_real >= 1.8:
                veredito = "ESCALAR (LUCRO REAL)"
            elif roas_real >= 1.0:
                veredito = "MANTER (NO AZUL)"
            elif roas_meta and roas_meta >= 1.2 and roas_real < 1.0:
                veredito = "ALERTA (BOLETO/PIX FANTASMA)"
            else:
                veredito = "CORTAR (PREJUÍZO)"
        else:
            veredito = "SEM GASTO"

        linhas_reconciliadas.append({
            "nome": nome_ad,
            "gasto": gasto,
            "meta_compras": compras_meta,
            "meta_receita": receita_meta,
            "meta_roas": roas_meta,
            "real_pagas": vendas["pagas"],
            "real_pendentes": vendas["pendentes"],
            "real_receita": receita_real,
            "real_roas": roas_real,
            "lucro_real": lucro_real,
            "veredito": veredito,
        })

        gasto_total += gasto
        receita_real_total += receita_real
        compras_meta_total += compras_meta
        pagas_total += vendas["pagas"]

    return {
        "campanhas": linhas_reconciliadas,
        "totais": {
            "gasto_total": round(gasto_total, 2),
            "receita_real_total": round(receita_real_total, 2),
            "lucro_real_total": round(receita_real_total - gasto_total, 2),
            "roas_real_global": round(receita_real_total / gasto_total, 2) if gasto_total > 0 else 0.0,
            "compras_meta_total": compras_meta_total,
            "pagas_checkout_total": pagas_total,
        }
    }


def _brl(v) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_tabela(resultado: dict) -> str:
    camps = resultado.get("campanhas", [])
    tot = resultado.get("totais", {})

    cols = [
        ("Campanha", "nome"),
        ("Gasto Meta", "gasto"),
        ("Meta Compras", "meta_compras"),
        ("Real Pagas", "real_pagas"),
        ("Real Pend.", "real_pendentes"),
        ("Receita Real", "real_receita"),
        ("ROAS Meta", "meta_roas"),
        ("ROAS Real", "real_roas"),
        ("Lucro Real", "lucro_real"),
        ("Veredito", "veredito"),
    ]

    def fmt(r, k):
        v = r[k]
        if k in ("gasto", "real_receita", "lucro_real"):
            return _brl(v)
        if k == "nome":
            return str(v)[:28]
        if k in ("meta_roas", "real_roas"):
            return "—" if not v else f"{v:.2f}x".replace(".", ",")
        return str(v)

    corpo = [[fmt(r, k) for _, k in cols] for r in camps]
    larg = [max(len(t), *(len(l[i]) for l in corpo)) if corpo else len(t) for i, (t, _) in enumerate(cols)]
    sep = "  "
    out = [
        sep.join(t.ljust(larg[i]) for i, (t, _) in enumerate(cols)),
        sep.join("─" * w for w in larg)
    ]
    for l in corpo:
        out.append(sep.join(c.ljust(larg[i]) if i in (0, len(cols) - 1) else c.rjust(larg[i]) for i, c in enumerate(l)))

    resumo_final = (
        f"\nRESUMO GERAL DO COFRE:\n"
        f"  • Gasto Total em Ads:  {_brl(tot.get('gasto_total'))}\n"
        f"  • Receita Real Paga:   {_brl(tot.get('receita_real_total'))}\n"
        f"  • Lucro Líquido Real:  {_brl(tot.get('lucro_real_total'))}\n"
        f"  • ROAS Real Efetivo:   {tot.get('roas_real_global', 0.0):.2f}x\n"
        f"  • Vendas: {tot.get('pagas_checkout_total')} pagas no checkout vs {tot.get('compras_meta_total')} registradas no Meta"
    )
    out.append(resumo_final)
    return "\n".join(out)
