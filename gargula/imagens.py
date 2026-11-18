"""Deteccao e codificacao de imagens arrastadas/coladas no chat."""

from __future__ import annotations

import base64
import mimetypes
import os
import re
from pathlib import Path

from gargula import contexto

# Extensoes suportadas pelas APIs de visao
_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
LIMITE_BYTES = 10 * 1024 * 1024  # 10 MB por imagem (evita estourar API/RAM)

# Regex que pega caminhos de arquivo com essas extensoes
# Aceita com ou sem aspas, caminhos Windows (C:\...) e Unix
_RE_PATH = re.compile(
    r"""(?:(?:"([^"]+\.(?:png|jpg|jpeg|webp|gif))")|"""        # entre aspas duplas
    r"""(?:'([^']+\.(?:png|jpg|jpeg|webp|gif))')|"""           # entre aspas simples
    r"""((?:[A-Za-z]:[\\/]|[\\/]|\.{0,2}[\\/])\S+\.(?:png|jpg|jpeg|webp|gif)))""",  # sem aspas
    re.IGNORECASE,
)


def _mime(caminho: str) -> str:
    tipo, _ = mimetypes.guess_type(caminho)
    return tipo or "image/png"


def extrair_imagens(texto: str, avisos: list[str] | None = None) -> tuple[str, list[dict]]:
    """Extrai caminhos de imagem do texto do usuario.

    Retorna (texto_limpo, lista_de_imagens).
    Cada imagem: {"caminho": str, "nome": str, "mime": str, "base64": str, "kb": int}.
    """
    imagens: list[dict] = []
    encontrados: list[str] = []
    vistos: set[Path] = set()

    for m in _RE_PATH.finditer(texto):
        caminho_bruto = m.group(1) or m.group(2) or m.group(3)
        caminho = os.path.expanduser(caminho_bruto.strip())
        p = Path(caminho)
        if not p.is_file():
            continue
        try:
            resolvido = p.resolve()
        except OSError:
            continue
        if resolvido.suffix.lower() not in _EXT:
            continue
        if contexto.bloqueado(resolvido):
            if avisos is not None:
                avisos.append(f"imagem bloqueada por pasta protegida: {p.name}")
            continue
        if resolvido in vistos:
            encontrados.append(m.group(0))
            continue
        try:
            tamanho = resolvido.stat().st_size
            if tamanho > LIMITE_BYTES:
                if avisos is not None:
                    avisos.append(f"{p.name} excede {LIMITE_BYTES // (1024 * 1024)} MB e foi ignorada")
                continue
            dados = resolvido.read_bytes()
        except (OSError, PermissionError):
            continue
        vistos.add(resolvido)
        imagens.append({
            "caminho": str(resolvido),
            "nome": resolvido.name,
            "mime": _mime(str(resolvido)),
            "base64": base64.b64encode(dados).decode("ascii"),
            "kb": max(1, len(dados) // 1024) if dados else 0,
        })
        encontrados.append(m.group(0))

    # Remove os caminhos do texto para ficar limpo
    texto_limpo = texto
    for trecho in encontrados:
        texto_limpo = texto_limpo.replace(trecho, "").strip()
    if imagens and not texto_limpo:
        texto_limpo = "analise esta imagem"

    return texto_limpo, imagens

