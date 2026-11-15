"""Envio de WhatsApp com travas anti-ban: 1 destinatário, prévia por padrão, intervalo mínimo."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from gargula import config
from gargula.llm import USER_AGENT

INTERVALO_MINIMO = 60  # segundos entre envios


class ErroZap(Exception):
    pass


def normalizar_numero(bruto: str) -> str:
    """Só um número, com DDI. Lista de números é recusada de propósito."""
    if re.search(r"[,;\n]", bruto) or len(re.findall(r"\d{8,}", bruto.replace(" ", "").replace("-", ""))) > 1:
        raise ErroZap("um destinatário por vez: o Gárgula não faz disparo em lote")
    digitos = re.sub(r"\D", "", bruto)
    if len(digitos) in (10, 11):  # DDD + número, sem DDI: assume Brasil
        digitos = "55" + digitos
    if not 12 <= len(digitos) <= 15:
        raise ErroZap(f"número inválido: {bruto!r} (use DDI + DDD + número, ex.: 5548999990000)")
    return digitos


def _log():
    return config.pasta() / "zap_envios.json"


def segundos_para_liberar(agora: float | None = None) -> int:
    agora = time.time() if agora is None else agora
    try:
        ultimo = json.loads(_log().read_text(encoding="utf-8")).get("ultimo", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0
    return max(0, int(INTERVALO_MINIMO - (agora - ultimo)))


def registrar_envio(numero: str, via: str, agora: float | None = None) -> None:
    p = _log()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        dados = json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        dados = {}
    agora = time.time() if agora is None else agora
    historico = (dados.get("historico") or [])[-199:]
    # guarda só o final do número no histórico local
    historico.append({"quando": int(agora), "para": "…" + numero[-4:], "via": via})
    p.write_text(json.dumps({"ultimo": agora, "historico": historico}, indent=1), encoding="utf-8")


def montar_envio(via: str, numero: str, texto: str) -> tuple[str, dict, dict]:
    """(url, headers, corpo) para Evolution API v2 ou WhatsApp Cloud API."""
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if via == "evolution":
        url = config.obter("evolution.url")
        inst = config.obter("evolution.instancia")
        chave = config.obter("evolution.chave")
        if not (url and inst and chave):
            raise ErroZap("configure evolution.url, evolution.instancia e evolution.chave "
                          "(ou EVOLUTION_URL, EVOLUTION_INSTANCIA, EVOLUTION_API_KEY)")
        headers["apikey"] = chave
        return f"{url.rstrip('/')}/message/sendText/{inst}", headers, {"number": numero, "text": texto}
    if via == "cloud":
        token = config.obter("cloud.token")
        phone_id = config.obter("cloud.phone_id")
        versao = config.obter("meta.versao", "v23.0")
        if not (token and phone_id):
            raise ErroZap("configure cloud.token e cloud.phone_id (ou WHATSAPP_TOKEN, WHATSAPP_PHONE_ID)")
        headers["Authorization"] = f"Bearer {token}"
        corpo = {"messaging_product": "whatsapp", "to": numero, "type": "text",
                 "text": {"preview_url": False, "body": texto}}
        return f"https://graph.facebook.com/{versao}/{phone_id}/messages", headers, corpo
    raise ErroZap("via deve ser 'evolution' ou 'cloud'")


def enviar(via: str, numero: str, texto: str, timeout: float = 30) -> dict:
    espera = segundos_para_liberar()
    if espera:
        raise ErroZap(f"aguarde {espera}s: intervalo mínimo de {INTERVALO_MINIMO}s entre envios (anti-ban)")
    url, headers, corpo = montar_envio(via, numero, texto)
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resposta = json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 428):
            detalhe += " | número/instância desconectado: não reenvie em sequência nem gere QR em loop"
        raise ErroZap(f"HTTP {e.code}: {detalhe}") from None
    except urllib.error.URLError as e:
        raise ErroZap(f"não consegui conectar: {e.reason}") from None
    registrar_envio(numero, via)
    return resposta
