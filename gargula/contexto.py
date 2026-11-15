"""Contexto do usuário: GARGULA.md fixo, leitura de notas e busca numa pasta base (ex.: vault do Obsidian).

Pastas e arquivos de segredo nunca são lidos.
"""

from __future__ import annotations

import math
import os
import re
import time
import unicodedata
from pathlib import Path

from gargula import config

LIMITE_FIXO = 20_000      # caracteres por arquivo de contexto fixo
LIMITE_LER = 30_000       # caracteres por nota anexada
NOMES_INSTRUCOES = ("GARGULA.md", "AGENTS.md", "CLAUDE.md")
EXTENSOES = {".md", ".txt", ".csv", ".json", ".yaml", ".yml"}
PASTAS_IGNORADAS = {".git", ".obsidian", "node_modules", ".venv", "venv", "__pycache__", ".trash",
                    ".secrets", "secrets", ".ssh"}


class ErroContexto(Exception):
    pass


def bloqueado(p: Path) -> bool:
    """Segredos e pastas técnicas ficam de fora."""
    partes = {x.lower() for x in p.parts}
    if partes & PASTAS_IGNORADAS:
        return True
    nome = p.name.lower()
    return (nome.startswith(".env") or nome.endswith((".env", ".key", ".pem", ".p12", ".pfx"))
            or "secret" in nome or "credenc" in nome or "senha" in nome or "token" in nome)


def pasta_base() -> Path | None:
    b = os.environ.get("GARGULA_PASTA") or config.carregar().get("pasta_base")
    return Path(b) if b else None


def _cortar(texto: str, limite: int) -> str:
    if len(texto) <= limite:
        return texto
    return texto[:limite] + f"\n\n[… cortado: {len(texto) - limite} caracteres a mais]"


def arquivos_fixos() -> list[Path]:
    base = pasta_base()
    # instruções de projeto no padrão dos agentes de código (Claude Code, Codex, Hermes)
    candidatos = [config.pasta() / "GARGULA.md"]
    for pasta in ([Path.cwd()] + ([base] if base else [])):
        candidatos += [pasta / n for n in NOMES_INSTRUCOES]
    for item in (config.carregar().get("contexto") or "").split(";"):
        item = item.strip()
        if not item:
            continue
        p = Path(os.path.expanduser(item))
        if not p.is_absolute() and base:
            p = base / p
        candidatos.append(p)
    vistos, saida = set(), []
    for p in candidatos:
        try:
            r = p.resolve()
        except OSError:
            continue
        if r in vistos or not r.is_file() or bloqueado(r):
            continue
        vistos.add(r)
        saida.append(r)
    return saida


def texto_fixo() -> str:
    blocos = []
    for p in arquivos_fixos():
        try:
            blocos.append(f"### {p.name} ({p})\n\n" + _cortar(p.read_text(encoding="utf-8-sig"), LIMITE_FIXO))
        except (OSError, UnicodeDecodeError):
            continue
    if not blocos:
        return ""
    return "\n\n## Contexto do usuário (arquivos fixos)\n\n" + "\n\n".join(blocos)


def _iterar(base: Path):
    for raiz, pastas, nomes in os.walk(base):
        pastas[:] = [d for d in pastas if d.lower() not in PASTAS_IGNORADAS and not d.startswith(".")]
        for n in nomes:
            p = Path(raiz) / n
            if p.suffix.lower() in EXTENSOES and not bloqueado(p):
                yield p


def resolver(alvo: str) -> Path:
    """Caminho absoluto, relativo ao diretório atual, relativo à pasta base ou parte do nome da nota."""
    alvo = alvo.strip().strip('"').strip("'").removeprefix("[[").removesuffix("]]")
    base = pasta_base()
    tentativas = [Path(os.path.expanduser(alvo)), Path.cwd() / alvo]
    if base:
        tentativas.append(base / alvo)
    for t in list(tentativas):
        if not t.suffix:
            tentativas.append(t.with_suffix(".md"))
    for t in tentativas:
        if t.is_file():
            if bloqueado(t.resolve()):
                raise ErroContexto("arquivo protegido (segredo ou pasta técnica): não leio")
            return t.resolve()
    if base and base.is_dir():
        chave = alvo.lower().replace("\\", "/")
        achados = [p for p in _iterar(base) if chave in str(p.relative_to(base)).lower().replace("\\", "/")]
        if achados:
            return min(achados, key=lambda p: len(str(p)))
    raise ErroContexto(f"não achei {alvo!r}" + ("" if base else " (dica: gargula config set pasta_base <pasta>)"))


def ler(alvo: str) -> tuple[Path, str]:
    p = resolver(alvo)
    try:
        return p, _cortar(p.read_text(encoding="utf-8-sig"), LIMITE_LER)
    except UnicodeDecodeError:
        raise ErroContexto(f"{p.name} não é texto") from None


PARADAS = {"de", "da", "do", "das", "dos", "a", "o", "as", "os", "e", "em", "no", "na", "nos", "nas", "um",
           "uma", "para", "pra", "por", "com", "que", "qual", "quais", "como", "se", "ao", "the", "of", "and"}


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acento: 'Preço' e 'preco' viram a mesma coisa."""
    sem = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem if not unicodedata.combining(c))


def buscar(termo: str, k: int = 5, base: Path | None = None) -> list[dict]:
    """Ranqueia notas por cobertura das palavras, nome do arquivo e recência; arquivos gigantes pesam menos."""
    base = base or pasta_base()
    if not base or not base.is_dir():
        raise ErroContexto("defina a pasta de busca: gargula config set pasta_base <pasta>")
    palavras = [w for w in re.findall(r"\w+", _normalizar(termo)) if w not in PARADAS and len(w) > 1]
    if not palavras:
        raise ErroContexto("termo vazio")
    minimo = max(1, math.ceil(len(palavras) * 0.6))
    agora = time.time()
    resultados = []
    for p in _iterar(base):
        if p.suffix.lower() not in (".md", ".txt"):
            continue  # JSON/CSV costumam ser dumps enormes que poluem o ranking
        try:
            texto = p.read_text(encoding="utf-8-sig", errors="ignore")
            mtime = p.stat().st_mtime
        except OSError:
            continue
        norm = _normalizar(texto)
        rel = str(p.relative_to(base))
        nome = _normalizar(rel)
        contagens = {w: norm.count(w) for w in palavras}
        no_nome = sum(1 for w in palavras if w in nome)
        cobertura = sum(1 for w in palavras if contagens[w] or w in nome)
        if cobertura < minimo:
            continue
        pontos = cobertura * 10 + sum(min(c, 8) for c in contagens.values()) + no_nome * 15
        pontos /= 1 + max(0.0, math.log10(max(len(texto), 1) / 8000))
        if agora - mtime < 30 * 86400:
            pontos += 4
        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        melhores = sorted(((sum(1 for w in palavras if w in _normalizar(l)), i) for i, l in enumerate(linhas)),
                          reverse=True)[:3]
        trechos = [linhas[i][:240] for n, i in sorted(melhores, key=lambda x: x[1]) if n]
        resultados.append({"arquivo": rel, "pontos": round(pontos, 1), "trechos": trechos})
    resultados.sort(key=lambda r: -r["pontos"])
    return resultados[:k]


def formatar_busca(termo: str, resultados: list[dict]) -> str:
    if not resultados:
        return f"Busca por {termo!r}: nada encontrado."
    linhas = [f"Busca por {termo!r} ({len(resultados)} notas):"]
    for r in resultados:
        linhas.append(f"\n- {r['arquivo']}")
        linhas += [f"    > {t}" for t in r["trechos"]]
    return "\n".join(linhas)
