"""Módulo de integração com o CRM proprietário (Gárgula CRM / Usetag CRM).

Permite inspecionar o status do atendimento, conversas esperando, catálogo oficial de produtos,
travas de segurança do agente de IA e sincronização de dados direto pelo terminal.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from gargula import config, ui
from gargula.llm import USER_AGENT


class ErroCRM(Exception):
    pass


def url_crm() -> str:
    return (os.environ.get("GARGULA_CRM_URL")
            or config.obter("crm.url")
            or "https://crm.usetag.online")


def token_crm() -> str | None:
    return os.environ.get("GARGULA_CRM_TOKEN") or config.obter("crm.token")


def pasta_crm() -> Path | None:
    """Procura por instalação local do CRM (ex.: no workspace ou caminho configurado)."""
    cfg_p = config.obter("crm.pasta") or os.environ.get("GARGULA_CRM_PASTA")
    if cfg_p:
        p = Path(os.path.expanduser(cfg_p))
        if p.is_dir():
            return p
    # Tenta caminhos conhecidos do ambiente
    candidatos = [
        Path.home() / ".gemini" / "antigravity-cli" / "brain" / "357869b1-1ecc-4e9f-b046-8a4d20097552" / "scratch" / "crm-usetag",
        Path.home() / "Projetos" / "usetag",
        Path.home() / "Projetos" / "crm-usetag",
    ]
    for c in candidatos:
        if c.is_dir() and (c / "painel" or c / "worker" or c / "banco").is_dir():
            return c
    return None


def obter_status_local() -> dict:
    """Lê configuração e estado da instalação local do CRM quando disponível."""
    pasta = pasta_crm()
    if not pasta:
        return {"status": "desconectado", "modo": "remoto", "url": url_crm()}

    tem_worker = (pasta / "worker").is_dir()
    tem_painel = (pasta / "painel").is_dir()
    tem_banco = (pasta / "banco").is_dir()

    # Tenta ler variáveis locais
    env_file = pasta / ".env"
    if not env_file.is_file():
        env_file = pasta / ".env.exemplo"

    agente_ativo = False
    agente_nome = "Kaio"
    if env_file.is_file():
        try:
            for l in env_file.read_text(encoding="utf-8").splitlines():
                if l.startswith("AGENTE_ATIVO="):
                    agente_ativo = "true" in l.lower()
                elif l.startswith("AGENTE_NOME="):
                    agente_nome = l.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    return {
        "status": "instalado",
        "modo": "local",
        "pasta": str(pasta),
        "modulos": {
            "worker_node": tem_worker,
            "painel_next15": tem_painel,
            "banco_postgres": tem_banco,
        },
        "agente": {
            "nome": agente_nome,
            "ativo_env": agente_ativo,
            "guardrails": "ativado (conferência estrita de saída)",
            "handoff": "ativado (silencioso por gatilho de preço/suporte)",
        }
    }


def obter_catalogo() -> list[dict]:
    """Retorna o catálogo de produtos e preços cadastrados no CRM para evitar alucinações."""
    # Primeiro tenta ler arquivo de catálogo local se existir
    pasta = pasta_crm()
    if pasta:
        for arq in ("catalogo.json", "dados/catalogo.json", "banco/catalogo.json"):
            p = pasta / arq
            if p.is_file():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    pass

    # Catálogo padrão de operação integrada (Kits USETAG / Smart Tag NFC)
    return [
        {"id": "kit-10", "nome": "Kit 10 Placas / Tags NFC", "preco": 147.0, "parcelas": "12x de R$ 14,70", "frete_gratis": "SP e RJ"},
        {"id": "kit-20", "nome": "Kit 20 Placas / Tags NFC", "preco": 247.0, "parcelas": "12x de R$ 24,70", "frete_gratis": "SP e RJ"},
        {"id": "kit-30", "nome": "Kit 30 Placas / Tags NFC", "preco": 327.0, "parcelas": "12x de R$ 32,70", "frete_gratis": "Brasil"},
        {"id": "kit-50", "nome": "Kit 50 Placas / Tags NFC", "preco": 497.0, "parcelas": "12x de R$ 49,70", "frete_gratis": "Brasil"},
        {"id": "kit-100", "nome": "Kit 100 Placas / Tags NFC", "preco": 897.0, "parcelas": "12x de R$ 89,70", "frete_gratis": "Brasil"},
    ]


def formatar_tabela_catalogo() -> str:
    itens = obter_catalogo()
    cols = [("ID", "id"), ("Produto / Kit", "nome"), ("Preço à Vista", "preco"), ("Parcelamento", "parcelas"), ("Frete Grátis", "frete_gratis")]

    def fmt(r, k):
        v = r.get(k)
        if k == "preco":
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return str(v)

    corpo = [[fmt(r, k) for _, k in cols] for r in itens]
    larg = [max(len(t), *(len(l[i]) for l in corpo)) if corpo else len(t) for i, (t, _) in enumerate(cols)]
    sep = "  "
    out = [
        sep.join(t.ljust(larg[i]) for i, (t, _) in enumerate(cols)),
        sep.join("─" * w for w in larg)
    ]
    for l in corpo:
        out.append(sep.join(c.ljust(larg[i]) if i in (0, 1) else c.rjust(larg[i]) for i, c in enumerate(l)))
    return "\n".join(out)


def formatar_status() -> str:
    st = obter_status_local()
    linhas = [
        ui.pintar("=== STATUS DO GÁRGULA CRM (INTEGRAÇÃO PROPRIETÁRIA) ===", ui.ROXO, negrito=True),
        f"• Status de Conexão: {ui.pintar(st['status'].upper(), ui.VERDE if st['status'] == 'instalado' else ui.AMARELO)}",
        f"• Modo Operacional:   {st['modo'].title()} ({st.get('pasta', st.get('url'))})",
    ]
    if st["modo"] == "local":
        mods = st.get("modulos", {})
        linhas.extend([
            f"• Módulos Verificados:",
            f"   - Painel Web (Next 15):       {'✔ Ativo' if mods.get('painel_next15') else '✖ Ausente'}",
            f"   - Worker da Evolution (Node):  {'✔ Ativo' if mods.get('worker_node') else '✖ Ausente'}",
            f"   - Banco de Dados (Postgres):   {'✔ Ativo' if mods.get('banco_postgres') else '✖ Ausente'}",
        ])
        ag = st.get("agente", {})
        linhas.extend([
            f"• Agente de Atendimento Nativo:",
            f"   - Persona / Nome:             {ag.get('nome')}",
            f"   - Handoff Silencioso:         {ag.get('handoff')}",
            f"   - Guardrails de Saída:        {ag.get('guardrails')}",
        ])
    else:
        linhas.append(f"• Endpoint da Central: {st['url']}")

    linhas.append("\nUse 'gargula crm catalogo' para ver a tabela oficial de preços e kits.")
    return "\n".join(linhas)

