"""Deteccao e codificacao de imagens arrastadas/coladas no chat."""

from __future__ import annotations

import base64
import mimetypes
import os
import re
from pathlib import Path

# Extensoes suportadas pelas APIs de visao
_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

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


def extrair_imagens(texto: str) -> tuple[str, list[dict]]:
    """Extrai caminhos de imagem do texto do usuario.

    Retorna (texto_limpo, lista_de_imagens).
    Cada imagem: {"caminho": str, "nome": str, "mime": str, "base64": str, "kb": int}.
    """
    imagens: list[dict] = []
    encontrados: list[str] = []

    for m in _RE_PATH.finditer(texto):
        caminho_bruto = m.group(1) or m.group(2) or m.group(3)
        caminho = os.path.expanduser(caminho_bruto.strip())
        if not os.path.isfile(caminho):
            continue
        ext = Path(caminho).suffix.lower()
        if ext not in _EXT:
            continue
        try:
            dados = Path(caminho).read_bytes()
        except (OSError, PermissionError):
            continue
        imagens.append({
            "caminho": caminho,
            "nome": Path(caminho).name,
            "mime": _mime(caminho),
            "base64": base64.b64encode(dados).decode("ascii"),
            "kb": len(dados) // 1024,
        })
        encontrados.append(m.group(0))

    # Remove os caminhos do texto para ficar limpo
    texto_limpo = texto
    for trecho in encontrados:
        texto_limpo = texto_limpo.replace(trecho, "").strip()
    if not texto_limpo:
        texto_limpo = "analise esta imagem"

    return texto_limpo, imagens
