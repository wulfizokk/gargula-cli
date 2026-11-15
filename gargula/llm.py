"""Cliente único para várias LLMs (Anthropic, OpenAI e compatíveis, Gemini) só com stdlib."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Iterable

from gargula import __version__

USER_AGENT = f"gargula-cli/{__version__}"
MAX_TOKENS = 4096


class ErroLLM(Exception):
    pass


def montar_requisicao(tipo: str, base: str, chave: str | None, modelo: str,
                      sistema: str, mensagens: list[dict], stream: bool = True):
    """Retorna (url, headers, corpo) no formato de cada API.

    mensagens: [{"role": "user"|"assistant", "content": "..."}]
    """
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if tipo == "anthropic":
        headers["x-api-key"] = chave or ""
        headers["anthropic-version"] = "2023-06-01"
        corpo = {"model": modelo, "max_tokens": MAX_TOKENS, "system": sistema,
                 "messages": mensagens, "stream": stream}
        return f"{base}/messages", headers, corpo
    if tipo == "gemini":
        headers["x-goog-api-key"] = chave or ""
        contents = [{"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [{"text": m["content"]}]} for m in mensagens]
        corpo = {"systemInstruction": {"parts": [{"text": sistema}]}, "contents": contents}
        acao = "streamGenerateContent?alt=sse" if stream else "generateContent"
        return f"{base}/models/{modelo}:{acao}", headers, corpo
    if tipo == "openai":
        if chave:
            headers["Authorization"] = f"Bearer {chave}"
        headers["X-Title"] = "Gargula CLI"  # usado pelo OpenRouter, ignorado pelos demais
        corpo = {"model": modelo, "stream": stream,
                 "messages": [{"role": "system", "content": sistema}] + mensagens}
        return f"{base}/chat/completions", headers, corpo
    raise ErroLLM(f"tipo de API desconhecido: {tipo}")


def texto_do_evento(tipo: str, dados: dict) -> str:
    """Pedaço de texto de um evento SSE já decodificado."""
    if tipo == "anthropic":
        if dados.get("type") == "content_block_delta":
            d = dados.get("delta", {})
            if d.get("type") == "text_delta":
                return d.get("text", "")
        if dados.get("type") == "error":
            raise ErroLLM(dados.get("error", {}).get("message", "erro da API"))
        return ""
    if tipo == "gemini":
        partes = []
        for c in dados.get("candidates", [])[:1]:
            for p in c.get("content", {}).get("parts", []):
                partes.append(p.get("text", ""))
        return "".join(partes)
    # openai e compatíveis
    if "error" in dados:
        raise ErroLLM(str(dados["error"].get("message", dados["error"])))
    escolhas = dados.get("choices") or []
    if not escolhas:
        return ""
    return (escolhas[0].get("delta") or {}).get("content") or ""


def texto_da_resposta(tipo: str, dados: dict) -> str:
    """Texto de uma resposta completa (sem stream)."""
    if tipo == "anthropic":
        return "".join(b.get("text", "") for b in dados.get("content", []) if b.get("type") == "text")
    if tipo == "gemini":
        return texto_do_evento("gemini", dados)
    escolhas = dados.get("choices") or [{}]
    return (escolhas[0].get("message") or {}).get("content") or ""


def ler_sse(linhas: Iterable[bytes]):
    """Gera os payloads JSON de um fluxo Server-Sent Events."""
    for bruta in linhas:
        linha = bruta.decode("utf-8", "replace").strip()
        if not linha.startswith("data:"):
            continue
        payload = linha[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            yield json.loads(payload)
        except json.JSONDecodeError:
            continue


def _mensagem_de_erro(e: urllib.error.HTTPError) -> str:
    try:
        corpo = json.loads(e.read().decode("utf-8", "replace"))
        err = corpo.get("error", corpo)
        if isinstance(err, list):
            err = err[0] if err else {}
        msg = err.get("message") if isinstance(err, dict) else str(err)
    except Exception:
        msg = e.reason
    dica = {401: " (chave de API inválida ou ausente)", 403: " (sem permissão para este modelo)",
            404: " (modelo ou endereço não encontrado)", 429: " (limite de uso atingido)"}.get(e.code, "")
    return f"HTTP {e.code}{dica}: {str(msg)[:300]}"


def conversar(llm: dict, sistema: str, mensagens: list[dict], stream: bool = True,
              ao_pedaco: Callable[[str], None] | None = None, timeout: float = 120) -> str:
    """Envia a conversa e devolve o texto completo; chama ao_pedaco a cada trecho."""
    # ollama e servidores compatíveis locais podem rodar sem chave
    if not llm.get("chave") and llm["provedor"] not in ("ollama", "compativel"):
        onde = f"defina {llm['env']} ou rode: gargula config set chave.{llm['provedor']} <chave>"
        raise ErroLLM(f"sem chave de API para {llm['provedor']}: {onde}")
    if not llm.get("base"):
        raise ErroLLM("provedor 'compativel' precisa de base_url: gargula config set base_url.compativel https://...")
    if not llm.get("modelo"):
        raise ErroLLM("modelo não definido: use --modelo ou gargula config set modelo <nome>")
    url, headers, corpo = montar_requisicao(llm["tipo"], llm["base"], llm.get("chave"),
                                            llm["modelo"], sistema, mensagens, stream)
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if not stream:
                texto = texto_da_resposta(llm["tipo"], json.loads(resp.read().decode("utf-8")))
                if ao_pedaco:
                    ao_pedaco(texto)
                return texto
            partes = []
            for evento in ler_sse(resp):
                pedaco = texto_do_evento(llm["tipo"], evento)
                if pedaco:
                    partes.append(pedaco)
                    if ao_pedaco:
                        ao_pedaco(pedaco)
            return "".join(partes)
    except urllib.error.HTTPError as e:
        raise ErroLLM(_mensagem_de_erro(e)) from None
    except urllib.error.URLError as e:
        raise ErroLLM(f"não consegui conectar em {llm['base']}: {e.reason}") from None
    except TimeoutError:
        raise ErroLLM("a API demorou demais para responder") from None
