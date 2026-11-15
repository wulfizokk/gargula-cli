"""Leitura de métricas do Meta Ads (Graph API Insights). Só leitura: nada é alterado na conta."""

from __future__ import annotations

import csv
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from gargula import config
from gargula.llm import USER_AGENT

PERIODOS = ("today", "yesterday", "last_3d", "last_7d", "last_14d", "last_30d", "this_month", "last_month")
CAMPOS = ("campaign_name,adset_name,ad_name,spend,impressions,reach,clicks,ctr,cpc,cpm,"
          "actions,action_values,cost_per_action_type")
COMPRA = ("omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase")
LEAD = ("lead", "offsite_conversion.fb_pixel_lead", "onsite_conversion.lead_grouped")
CONVERSA = ("onsite_conversion.messaging_conversation_started_7d",)


class ErroAds(Exception):
    pass


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _acao(lista, tipos) -> float:
    """Primeiro tipo encontrado na ordem de preferência (evita somar a mesma compra 2x)."""
    por_tipo = {a.get("action_type"): _f(a.get("value")) for a in (lista or [])}
    for t in tipos:
        if t in por_tipo:
            return por_tipo[t]
    return 0.0


def resumir(linha: dict, nivel: str = "campaign") -> dict:
    nome = linha.get(f"{nivel}_name") or linha.get("nome") or linha.get("campaign_name") or "?"
    gasto = _f(linha.get("spend", linha.get("gasto")))
    compras = _acao(linha.get("actions"), COMPRA) or _f(linha.get("compras"))
    receita = _acao(linha.get("action_values"), COMPRA) or _f(linha.get("receita"))
    leads = _acao(linha.get("actions"), LEAD) or _f(linha.get("leads"))
    conversas = _acao(linha.get("actions"), CONVERSA) or _f(linha.get("conversas"))
    impressoes = _f(linha.get("impressions", linha.get("impressoes")))
    cliques = _f(linha.get("clicks", linha.get("cliques")))
    return {
        "nome": nome,
        "gasto": round(gasto, 2),
        "impressoes": int(impressoes),
        "cliques": int(cliques),
        "ctr": round(_f(linha.get("ctr")) or (cliques / impressoes * 100 if impressoes else 0), 2),
        "cpc": round(_f(linha.get("cpc")) or (gasto / cliques if cliques else 0), 2),
        "cpm": round(_f(linha.get("cpm")) or (gasto / impressoes * 1000 if impressoes else 0), 2),
        "compras": int(compras),
        "receita": round(receita, 2),
        "cpa": round(gasto / compras, 2) if compras else None,
        "roas": round(receita / gasto, 2) if gasto and receita else None,
        "leads": int(leads),
        "conversas": int(conversas),
    }


def buscar(conta: str | None = None, periodo: str = "last_7d", nivel: str = "campaign",
           max_paginas: int = 5, timeout: float = 30) -> list[dict]:
    token = config.obter("meta.token")
    conta = conta or config.obter("meta.conta")
    versao = config.obter("meta.versao", "v23.0")
    if not token:
        raise ErroAds("configure meta.token (ou META_ACCESS_TOKEN) com permissão ads_read")
    if not conta:
        raise ErroAds("informe --conta act_123... ou configure meta.conta")
    if not conta.startswith("act_"):
        conta = "act_" + conta
    if periodo not in PERIODOS:
        raise ErroAds(f"período inválido; use: {', '.join(PERIODOS)}")
    params = urllib.parse.urlencode({"level": nivel, "fields": CAMPOS,
                                     "date_preset": periodo, "limit": 100})
    url = f"https://graph.facebook.com/{versao}/{conta}/insights?{params}"
    # token no cabeçalho, nunca na URL (não vaza em log nem em mensagem de erro)
    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    linhas = []
    for _ in range(max_paginas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                dados = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", e.reason)
            except Exception:
                msg = e.reason
            raise ErroAds(f"Graph API HTTP {e.code}: {msg}") from None
        except urllib.error.URLError as e:
            raise ErroAds(f"não consegui conectar na Graph API: {e.reason}") from None
        linhas.extend(dados.get("data", []))
        proxima = dados.get("paging", {}).get("next")
        if not proxima:
            break
        # a URL "next" da Meta pode trazer o token; tiramos e seguimos pelo cabeçalho
        partes = urllib.parse.urlsplit(proxima)
        q = [(k, v) for k, v in urllib.parse.parse_qsl(partes.query) if k != "access_token"]
        url = urllib.parse.urlunsplit(partes._replace(query=urllib.parse.urlencode(q)))
    return linhas


def carregar_arquivo(caminho: str) -> list[dict]:
    """Métricas exportadas (JSON da Graph API, lista JSON ou CSV com cabeçalho)."""
    p = Path(caminho)
    texto = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".csv":
        return list(csv.DictReader(texto.splitlines()))
    dados = json.loads(texto)
    return dados.get("data", []) if isinstance(dados, dict) else dados


def _brl(v) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tabela(resumos: list[dict]) -> str:
    cols = [("Campanha", "nome"), ("Gasto", "gasto"), ("CTR%", "ctr"), ("CPC", "cpc"),
            ("CPM", "cpm"), ("Compras", "compras"), ("CPA", "cpa"), ("ROAS", "roas"),
            ("Leads", "leads"), ("Conversas", "conversas")]
    dinheiro = {"gasto", "cpc", "cpm", "cpa"}

    def fmt(r, k):
        v = r[k]
        if k in dinheiro:
            return _brl(v)
        if k == "nome":
            return str(v)[:34]
        return "—" if v is None else str(v).replace(".", ",")

    corpo = [[fmt(r, k) for _, k in cols] for r in resumos]
    total = sum(r["gasto"] for r in resumos)
    larg = [max(len(t), *(len(l[i]) for l in corpo)) if corpo else len(t) for i, (t, _) in enumerate(cols)]
    sep = "  "
    out = [sep.join(t.ljust(larg[i]) for i, (t, _) in enumerate(cols)),
           sep.join("─" * w for w in larg)]
    for l in corpo:
        out.append(sep.join(c.ljust(larg[i]) if i == 0 else c.rjust(larg[i]) for i, c in enumerate(l)))
    out.append(f"\n{len(resumos)} linha(s) · gasto total {_brl(total)}")
    return "\n".join(out)
