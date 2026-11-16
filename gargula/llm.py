"""Cliente único para várias LLMs (Anthropic, OpenAI e compatíveis, Gemini), com streaming e ferramentas.

Formato interno do histórico (neutro, convertido para cada API):
  {"role": "user", "content": "texto"}
  {"role": "assistant", "content": "texto", "chamadas": [{"id", "nome", "args"}], "bruto": [...]}
  {"role": "ferramenta", "resultados": [{"id", "nome", "conteudo", "erro": bool}]}
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable, Iterable

from gargula import __version__

USER_AGENT = f"gargula-cli/{__version__}"


def max_tokens() -> int:
    try:
        from gargula import config
        return int(os.environ.get("GARGULA_MAX_TOKENS") or config.carregar().get("max_tokens") or 4096)
    except (ValueError, TypeError):
        return 4096


class ErroLLM(Exception):
    pass


# ---------- conversão do histórico ----------

def _blocos_imagem_anthropic(imagens: list[dict]) -> list[dict]:
    """Converte imagens internas em blocos Anthropic vision."""
    return [{"type": "image", "source": {"type": "base64", "media_type": img["mime"], "data": img["base64"]}}
            for img in imagens]


def _blocos_imagem_openai(imagens: list[dict]) -> list[dict]:
    """Converte imagens internas em blocos OpenAI vision."""
    return [{"type": "image_url", "image_url": {"url": f"data:{img['mime']};base64,{img['base64']}"}}
            for img in imagens]


def _partes_imagem_gemini(imagens: list[dict]) -> list[dict]:
    """Converte imagens internas em parts Gemini vision."""
    return [{"inline_data": {"mime_type": img["mime"], "data": img["base64"]}}
            for img in imagens]


def _msgs_anthropic(mensagens: list[dict]) -> list[dict]:
    out = []
    for m in mensagens:
        if m["role"] == "user":
            imgs = m.get("imagens")
            if imgs:
                blocos = _blocos_imagem_anthropic(imgs) + [{"type": "text", "text": m["content"]}]
                out.append({"role": "user", "content": blocos})
            else:
                out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            blocos = [{"type": "text", "text": m["content"]}] if m.get("content") else []
            blocos += [{"type": "tool_use", "id": c["id"], "name": c["nome"], "input": c["args"]}
                       for c in m.get("chamadas") or []]
            out.append({"role": "assistant", "content": blocos or [{"type": "text", "text": "…"}]})
        elif m["role"] == "ferramenta":
            out.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": r["id"], "content": r["conteudo"],
                 "is_error": bool(r.get("erro"))} for r in m["resultados"]]})
    return out


def _msgs_openai(mensagens: list[dict]) -> list[dict]:
    out = []
    for m in mensagens:
        if m["role"] == "user":
            imgs = m.get("imagens")
            if imgs:
                blocos = _blocos_imagem_openai(imgs) + [{"type": "text", "text": m["content"]}]
                out.append({"role": "user", "content": blocos})
            else:
                out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            d = {"role": "assistant", "content": m.get("content") or None}
            if m.get("chamadas"):
                d["tool_calls"] = [{"id": c["id"], "type": "function",
                                    "function": {"name": c["nome"], "arguments": json.dumps(c["args"], ensure_ascii=False)}}
                                   for c in m["chamadas"]]
            elif d["content"] is None:
                d["content"] = "…"
            out.append(d)
        elif m["role"] == "ferramenta":
            out += [{"role": "tool", "tool_call_id": r["id"], "content": r["conteudo"]} for r in m["resultados"]]
    return out


def _msgs_gemini(mensagens: list[dict]) -> list[dict]:
    out = []
    for m in mensagens:
        if m["role"] == "user":
            imgs = m.get("imagens")
            if imgs:
                partes = _partes_imagem_gemini(imgs) + [{"text": m["content"]}]
                out.append({"role": "user", "parts": partes})
            else:
                out.append({"role": "user", "parts": [{"text": m["content"]}]})
        elif m["role"] == "assistant":
            # partes originais preservam o thoughtSignature exigido pelo Gemini com ferramentas
            partes = m.get("bruto") or (
                ([{"text": m["content"]}] if m.get("content") else [])
                + [{"functionCall": {"name": c["nome"], "args": c["args"]}} for c in m.get("chamadas") or []])
            out.append({"role": "model", "parts": partes or [{"text": "…"}]})
        elif m["role"] == "ferramenta":
            out.append({"role": "user", "parts": [
                {"functionResponse": {"name": r["nome"], "response": {"resultado": r["conteudo"]}}}
                for r in m["resultados"]]})
    return out


def montar_requisicao(tipo: str, base: str, chave: str | None, modelo: str, sistema: str,
                      mensagens: list[dict], stream: bool = True, ferramentas: list[dict] | None = None):
    """Retorna (url, headers, corpo). ferramentas: [{"nome", "descricao", "parametros"}]."""
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    ferramentas = ferramentas or []
    if tipo == "anthropic":
        headers["x-api-key"] = chave or ""
        headers["anthropic-version"] = "2023-06-01"
        corpo = {"model": modelo, "max_tokens": max_tokens(), "stream": stream,
                 # cache do prompt de sistema (+ ferramentas): bem mais barato em conversas longas
                 "system": [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}],
                 "messages": _msgs_anthropic(mensagens)}
        if ferramentas:
            corpo["tools"] = [{"name": f["nome"], "description": f["descricao"], "input_schema": f["parametros"]}
                              for f in ferramentas]
        return f"{base}/messages", headers, corpo
    if tipo == "gemini":
        headers["x-goog-api-key"] = chave or ""
        corpo = {"systemInstruction": {"parts": [{"text": sistema}]}, "contents": _msgs_gemini(mensagens),
                 "generationConfig": {"maxOutputTokens": max(max_tokens(), 8192)}}
        if ferramentas:
            corpo["tools"] = [{"functionDeclarations": [
                {"name": f["nome"], "description": f["descricao"], "parameters": f["parametros"]} for f in ferramentas]}]
        acao = "streamGenerateContent?alt=sse" if stream else "generateContent"
        return f"{base}/models/{modelo}:{acao}", headers, corpo
    if tipo == "openai":
        if chave:
            headers["Authorization"] = f"Bearer {chave}"
        headers["X-Title"] = "Gargula CLI"  # usado pelo OpenRouter, ignorado pelos demais
        # sem max_tokens o OpenRouter reserva o máximo do modelo e recusa por falta de crédito
        corpo = {"model": modelo, "stream": stream, "max_tokens": max_tokens(),
                 "messages": [{"role": "system", "content": sistema}] + _msgs_openai(mensagens)}
        if ferramentas:
            corpo["tools"] = [{"type": "function", "function": {
                "name": f["nome"], "description": f["descricao"], "parameters": f["parametros"]}} for f in ferramentas]
        return f"{base}/chat/completions", headers, corpo
    raise ErroLLM(f"tipo de API desconhecido: {tipo}")


# ---------- leitura do stream ----------

def _args(bruto) -> dict:
    if isinstance(bruto, dict):
        return bruto
    try:
        v = json.loads(bruto or "{}")
        return v if isinstance(v, dict) else {"valor": v}
    except json.JSONDecodeError:
        return {"_json_invalido": bruto}


class Acumulador:
    """Junta texto e chamadas de ferramenta vindos em pedaços, no formato de cada API."""

    def __init__(self, tipo: str, ao_pedaco: Callable[[str], None] | None = None):
        self.tipo, self.ao_pedaco = tipo, ao_pedaco
        self.texto: list[str] = []
        self.blocos: dict[int, dict] = {}   # anthropic/openai: índice -> chamada em construção
        self.bruto: list[dict] = []         # gemini: partes originais
        self.parada = None

    def _txt(self, t: str):
        if t:
            self.texto.append(t)
            if self.ao_pedaco:
                self.ao_pedaco(t)

    def evento(self, d: dict):
        if self.tipo == "anthropic":
            tipo = d.get("type")
            if tipo == "content_block_start":
                b = d.get("content_block", {})
                if b.get("type") == "tool_use":
                    self.blocos[d.get("index", 0)] = {"id": b.get("id"), "nome": b.get("name"), "json": ""}
            elif tipo == "content_block_delta":
                delta = d.get("delta", {})
                if delta.get("type") == "text_delta":
                    self._txt(delta.get("text", ""))
                elif delta.get("type") == "input_json_delta" and d.get("index", 0) in self.blocos:
                    self.blocos[d.get("index", 0)]["json"] += delta.get("partial_json", "")
            elif tipo == "message_delta":
                self.parada = d.get("delta", {}).get("stop_reason") or self.parada
            elif tipo == "error":
                raise ErroLLM(d.get("error", {}).get("message", "erro da API"))
        elif self.tipo == "gemini":
            if "error" in d:
                raise ErroLLM(str(d["error"].get("message", d["error"])))
            for c in d.get("candidates", [])[:1]:
                for p in c.get("content", {}).get("parts", []):
                    if p.get("thought"):
                        continue
                    self.bruto.append(p)
                    if "text" in p:
                        self._txt(p["text"])
                    if "functionCall" in p:
                        n = len(self.blocos)
                        fc = p["functionCall"]
                        self.blocos[n] = {"id": f"g{n}", "nome": fc.get("name"), "json": fc.get("args") or {}}
                self.parada = c.get("finishReason") or self.parada
        else:
            if "error" in d:
                e = d["error"]
                raise ErroLLM(str(e.get("message", e)) if isinstance(e, dict) else str(e))
            for ch in (d.get("choices") or [])[:1]:
                delta = ch.get("delta") or ch.get("message") or {}
                self._txt(delta.get("content") or "")
                for tc in delta.get("tool_calls") or []:
                    i = tc.get("index", len(self.blocos))
                    b = self.blocos.setdefault(i, {"id": None, "nome": None, "json": ""})
                    if tc.get("id"):
                        b["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        b["nome"] = fn["name"]
                    args = fn.get("arguments")
                    if isinstance(args, dict):
                        b["json"] = args
                    elif args:
                        b["json"] = (b["json"] if isinstance(b["json"], str) else "") + args
                self.parada = ch.get("finish_reason") or self.parada

    def resultado(self) -> dict:
        chamadas = [{"id": b["id"] or f"c{i}", "nome": b["nome"], "args": _args(b["json"])}
                    for i, b in sorted(self.blocos.items()) if b.get("nome")]
        return {"texto": "".join(self.texto), "chamadas": chamadas,
                "bruto": self.bruto if self.tipo == "gemini" else None, "parada": self.parada}


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
        err = corpo[0] if isinstance(corpo, list) and corpo else corpo
        err = err.get("error", err) if isinstance(err, dict) else err
        msg = err.get("message") if isinstance(err, dict) else str(err)
    except Exception:
        msg = e.reason
    dica = {401: " (chave de API inválida ou ausente)", 403: " (sem permissão para este modelo)",
            404: " (modelo ou endereço não encontrado)", 429: " (limite de uso atingido)"}.get(e.code, "")
    if "anthropic-workspace-id" in str(msg):
        dica += " → defina ANTHROPIC_WORKSPACE_ID ou rode: gargula config set anthropic.workspace <id>"
    return f"HTTP {e.code}{dica}: {str(msg)[:400]}"


def conversar(llm: dict, sistema: str, mensagens: list[dict], ferramentas: list[dict] | None = None,
              ao_pedaco: Callable[[str], None] | None = None, stream: bool = True,
              timeout: float = 300) -> dict:
    """Uma rodada com a LLM. Devolve {"texto", "chamadas", "bruto", "parada"}."""
    # ollama e servidores compatíveis locais podem rodar sem chave
    if not llm.get("chave") and llm["provedor"] not in ("ollama", "compativel"):
        onde = f"defina {llm['env']} ou rode: gargula config set chave.{llm['provedor']} <chave>"
        raise ErroLLM(f"sem chave de API para {llm['provedor']}: {onde}")
    if not llm.get("base"):
        raise ErroLLM("provedor 'compativel' precisa de base_url: gargula config set base_url.compativel https://...")
    if not llm.get("modelo"):
        raise ErroLLM("modelo não definido: use --modelo ou gargula config set modelo <nome>")
    url, headers, corpo = montar_requisicao(llm["tipo"], llm["base"], llm.get("chave"), llm["modelo"],
                                            sistema, mensagens, stream, ferramentas)
    if llm["tipo"] == "anthropic" and llm.get("workspace"):
        headers["anthropic-workspace-id"] = llm["workspace"]
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), headers=headers, method="POST")
    acc = Acumulador(llm["tipo"], ao_pedaco)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if stream:
                for evento in ler_sse(resp):
                    acc.evento(evento)
            else:
                dados = json.loads(resp.read().decode("utf-8"))
                if llm["tipo"] == "anthropic":
                    for i, b in enumerate(dados.get("content", [])):
                        if b.get("type") == "text":
                            acc._txt(b.get("text", ""))
                        elif b.get("type") == "tool_use":
                            acc.blocos[i] = {"id": b["id"], "nome": b["name"], "json": b.get("input") or {}}
                    acc.parada = dados.get("stop_reason")
                else:
                    acc.evento(dados)
    except urllib.error.HTTPError as e:
        raise ErroLLM(_mensagem_de_erro(e)) from None
    except urllib.error.URLError as e:
        raise ErroLLM(f"não consegui conectar em {llm['base']}: {e.reason}") from None
    except TimeoutError:
        raise ErroLLM("a API demorou demais para responder") from None
    return acc.resultado()


def responder(llm: dict, sistema: str, mensagens: list[dict], ao_pedaco=None) -> str:
    """Atalho sem ferramentas: só o texto."""
    return conversar(llm, sistema, mensagens, None, ao_pedaco)["texto"]
