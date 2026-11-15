"""Configuração: flag > variável de ambiente > ~/.gargula/config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path

# tipo = formato da API. "openai" cobre qualquer API compatível com OpenAI.
# Os modelos padrão mudam com o tempo: troque com --modelo ou `gargula config set modelo ...`.
PROVEDORES: dict[str, dict] = {
    "anthropic": {"tipo": "anthropic", "base": "https://api.anthropic.com/v1",
                  "env": "ANTHROPIC_API_KEY", "modelo": "claude-sonnet-5-5"},
    "openai": {"tipo": "openai", "base": "https://api.openai.com/v1",
               "env": "OPENAI_API_KEY", "modelo": "gpt-4o-mini"},
    "gemini": {"tipo": "gemini", "base": "https://generativelanguage.googleapis.com/v1beta",
               "env": "GEMINI_API_KEY", "modelo": "gemini-2.5-flash"},
    "groq": {"tipo": "openai", "base": "https://api.groq.com/openai/v1",
             "env": "GROQ_API_KEY", "modelo": "llama-3.3-70b-versatile"},
    "openrouter": {"tipo": "openai", "base": "https://openrouter.ai/api/v1",
                   "env": "OPENROUTER_API_KEY", "modelo": "openrouter/auto"},
    "deepseek": {"tipo": "openai", "base": "https://api.deepseek.com/v1",
                 "env": "DEEPSEEK_API_KEY", "modelo": "deepseek-chat"},
    "ollama": {"tipo": "openai", "base": "http://localhost:11434/v1",
               "env": None, "modelo": "llama3.1"},
    "compativel": {"tipo": "openai", "base": None,
                   "env": "GARGULA_API_KEY", "modelo": None},
}

# chave de config -> variável de ambiente equivalente
ENV_EXTRA = {
    "evolution.url": "EVOLUTION_URL",
    "evolution.instancia": "EVOLUTION_INSTANCIA",
    "evolution.chave": "EVOLUTION_API_KEY",
    "cloud.token": "WHATSAPP_TOKEN",
    "cloud.phone_id": "WHATSAPP_PHONE_ID",
    "meta.token": "META_ACCESS_TOKEN",
    "meta.conta": "META_AD_ACCOUNT",
    "meta.versao": "META_GRAPH_VERSION",
}

SECRETAS = ("chave.", "evolution.chave", "cloud.token", "meta.token")


def pasta() -> Path:
    return Path(os.environ.get("GARGULA_HOME") or Path.home() / ".gargula")


def arquivo() -> Path:
    return pasta() / "config.json"


def carregar() -> dict:
    try:
        return json.loads(arquivo().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def salvar(cfg: dict) -> None:
    p = arquivo()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def definir(chave: str, valor: str) -> None:
    cfg = carregar()
    cfg[chave] = valor
    salvar(cfg)


def remover(chave: str) -> bool:
    cfg = carregar()
    if chave in cfg:
        del cfg[chave]
        salvar(cfg)
        return True
    return False


def e_secreta(chave: str) -> bool:
    return any(chave == s or (s.endswith(".") and chave.startswith(s)) for s in SECRETAS)


def mascarar(valor: str) -> str:
    if not valor:
        return ""
    return "••••" + valor[-4:] if len(valor) > 8 else "••••"


def obter(chave: str, padrao=None, cfg: dict | None = None):
    env = ENV_EXTRA.get(chave)
    if env and os.environ.get(env):
        return os.environ[env]
    cfg = carregar() if cfg is None else cfg
    return cfg.get(chave, padrao)


def resolver_llm(provedor: str | None = None, modelo: str | None = None,
                 base_url: str | None = None) -> dict:
    """Junta provedor, modelo, base e chave de API para uma chamada."""
    cfg = carregar()
    nome = provedor or os.environ.get("GARGULA_PROVEDOR") or cfg.get("provedor") or "anthropic"
    if nome not in PROVEDORES:
        raise ValueError(f"provedor desconhecido: {nome}. Use um de: {', '.join(PROVEDORES)}")
    p = PROVEDORES[nome]
    # "modelo" genérico só vale para o provedor salvo; senão cada um usa o próprio padrão
    modelo_salvo = cfg.get(f"modelo.{nome}") or (
        cfg.get("modelo") if cfg.get("provedor", "anthropic") == nome else None)
    modelo_final = modelo or os.environ.get("GARGULA_MODELO") or modelo_salvo or p["modelo"]
    base = (base_url or os.environ.get("GARGULA_BASE_URL")
            or cfg.get(f"base_url.{nome}") or p["base"])
    chave = (os.environ.get(p["env"]) if p["env"] else None) or cfg.get(f"chave.{nome}")
    return {"provedor": nome, "tipo": p["tipo"], "base": (base or "").rstrip("/"),
            "modelo": modelo_final, "chave": chave, "env": p["env"]}
