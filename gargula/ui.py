"""Cores, mascote e componentes visuais do Gárgula."""

from __future__ import annotations

import os
import re
import sys
import threading
import time

# Paleta roxa (RGB)
PALETA = {
    "D": (91, 33, 182),    # asas/costas, roxo escuro
    "P": (139, 92, 246),   # corpo, roxo
    "L": (196, 181, 253),  # garras/peito, lilás
    "E": (245, 243, 255),  # olho brilhando, branco
    "C": (100, 116, 139),  # cornija/pedra, slate cinza
    "B": (71, 85, 105),    # fachada/prédio, slate escuro
}
ROXO = PALETA["P"]
LILAS = PALETA["L"]
CINZA = (148, 148, 160)
VERDE = (74, 222, 128)
PEDRA = PALETA["C"]

# Gárgula de perfil sentado na cornija de um edifício (estilo Batman vigilante).
# Cada linha = 1 pixel; duas linhas viram uma linha do terminal (meio-bloco).
MASCOTE = [
    "....PP.....D....",
    "...PEPP...DDD...",
    "..PPPPPDDDDDD...",
    ".PPPPPDDDDDDD...",
    "LLPPPPPDDDDDD...",
    ".LL.PPPDDDDD....",
    "CCCCCCCCCCCCCCCC",
    ".CCCCCCCCCCCCCC.",
    "..BBBB....BBBB..",
    "..BBBB....BBBB..",
]


def preparar_terminal() -> None:
    """UTF-8 na saída e sequências ANSI ligadas no Windows."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if os.name == "nt":
        try:
            import ctypes

            k32 = ctypes.windll.kernel32
            for num in (-11, -12):
                h = k32.GetStdHandle(num)
                modo = ctypes.c_uint32()
                if k32.GetConsoleMode(h, ctypes.byref(modo)):
                    k32.SetConsoleMode(h, modo.value | 0x0004)
        except Exception:
            pass


def usa_cor(fluxo=None) -> bool:
    fluxo = fluxo or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(fluxo, "isatty") and fluxo.isatty()


def _fg(rgb):
    return "\x1b[38;2;%d;%d;%dm" % rgb


def _bg(rgb):
    return "\x1b[48;2;%d;%d;%dm" % rgb


RESET = "\x1b[0m"


def pintar(texto: str, rgb=ROXO, negrito: bool = False, cor: bool | None = None) -> str:
    if cor is None:
        cor = usa_cor()
    if not cor:
        return texto
    return ("\x1b[1m" if negrito else "") + _fg(rgb) + texto + RESET


def desenhar(sprite: list[str] | None = None, cor: bool = True) -> list[str]:
    """Converte a grade de pixels em linhas de meio-bloco (▀ ▄ █)."""
    if sprite is None:
        sprite = MASCOTE
    largura = max(len(l) for l in sprite)
    linhas = [l.ljust(largura, ".") for l in sprite]
    if len(linhas) % 2:
        linhas.append("." * largura)
    saida = []
    for i in range(0, len(linhas), 2):
        cima, baixo = linhas[i], linhas[i + 1]
        partes = []
        for a, b in zip(cima, baixo):
            if not cor:
                # sem cor os olhos viram buracos para continuarem visíveis
                a = "." if a == "E" else a
                b = "." if b == "E" else b
                if a != "." and b != ".":
                    partes.append("█")
                elif a != ".":
                    partes.append("▀")
                elif b != ".":
                    partes.append("▄")
                else:
                    partes.append(" ")
                continue
            ca, cb = PALETA.get(a), PALETA.get(b)
            if ca and cb:
                if ca == cb:
                    partes.append(_fg(ca) + "█" + RESET)
                else:
                    partes.append(_fg(ca) + _bg(cb) + "▀" + RESET)
            elif ca:
                partes.append(_fg(ca) + "▀" + RESET)
            elif cb:
                partes.append(_fg(cb) + "▄" + RESET)
            else:
                partes.append(" ")
        saida.append("".join(partes).rstrip() if not cor else "".join(partes))
    return saida


def banner(versao: str, provedor: str, modelo: str, modo: str, cor: bool | None = None) -> str:
    """Quadro de boas-vindas com o Gárgula sentado em cima."""
    if cor is None:
        cor = usa_cor()
    largura = 58  # largura interna do quadro
    sprite = desenhar(cor=cor)
    larg_sprite = len(MASCOTE[0])
    recuo = " " * (1 + (largura - larg_sprite) // 2)

    def linha(txt_cru: str, txt_cor: str | None = None) -> str:
        espaco = " " * max(0, largura - 2 - len(txt_cru))
        borda = pintar("│", ROXO, cor=cor)
        return f"{borda}  {txt_cor if txt_cor is not None else txt_cru}{espaco}{borda}"

    titulo_cru = f"Gárgula CLI  v{versao}"
    titulo = pintar("Gárgula CLI", ROXO, negrito=True, cor=cor) + pintar(f"  v{versao}", CINZA, cor=cor)
    sub = "copiloto de marketing, vendas, WhatsApp e Meta Ads"
    info = f"{provedor} / {modelo}"
    info2 = f"modo {modo}"
    dica = "/ajuda · Ctrl+C interrompe · /sair"

    out = [recuo + l for l in sprite]
    out.append(pintar("╭" + "─" * largura + "╮", ROXO, cor=cor))
    out.append(linha(titulo_cru, titulo))
    out.append(linha(sub, pintar(sub, LILAS, cor=cor)))
    out.append(linha(""))
    out.append(linha(info[: largura - 2], pintar(info[: largura - 2], CINZA, cor=cor)))
    out.append(linha(info2, pintar(info2, CINZA, cor=cor)))
    out.append(linha(dica, pintar(dica, CINZA, cor=cor)))
    out.append(pintar("╰" + "─" * largura + "╯", ROXO, cor=cor))
    return "\n".join(out)


def _inline_markdown(texto: str, cor: bool) -> str:
    """Renderiza o subconjunto de Markdown que mais aparece nas respostas."""
    texto = re.sub(r"\[([^]]+)]\(([^)]+)\)", r"\1 (\2)", texto)

    def codigo(m: re.Match) -> str:
        conteudo = m.group(1)
        return pintar(conteudo, LILAS, cor=cor)

    def forte(m: re.Match) -> str:
        conteudo = m.group(1)
        if not cor:
            return conteudo
        return "\x1b[1m" + conteudo + RESET

    texto = re.sub(r"`([^`]+)`", codigo, texto)
    texto = re.sub(r"\*\*([^*]+)\*\*", forte, texto)
    texto = re.sub(r"__([^_]+)__", forte, texto)
    return texto


def formatar_markdown(texto: str, cor: bool | None = None) -> str:
    """Transforma Markdown simples em texto de terminal limpo e hierárquico."""
    if cor is None:
        cor = usa_cor()
    linhas: list[str] = []
    em_codigo = False
    for bruta in texto.strip().splitlines():
        linha = bruta.rstrip()
        if linha.lstrip().startswith("```"):
            em_codigo = not em_codigo
            continue
        if em_codigo:
            linhas.append(pintar("  " + linha, CINZA, cor=cor))
            continue
        if not linha.strip():
            linhas.append("")
            continue

        cabecalho = re.match(r"^\s{0,3}#{1,6}\s+(.+)$", linha)
        if cabecalho:
            titulo = _inline_markdown(cabecalho.group(1), cor)
            linhas.append(pintar(titulo, LILAS, negrito=True, cor=cor))
            continue

        item = re.match(r"^(\s*)[-*]\s+(.+)$", linha)
        if item:
            recuo = item.group(1)
            bala = pintar("•", ROXO, negrito=True, cor=cor)
            linhas.append(f"{recuo}{bala} {_inline_markdown(item.group(2), cor)}")
            continue

        citado = re.match(r"^\s*>\s?(.*)$", linha)
        if citado:
            barra = pintar("│", ROXO, cor=cor)
            linhas.append(f"{barra} {pintar(citado.group(1), CINZA, cor=cor)}")
            continue

        linhas.append(_inline_markdown(linha, cor))
    return "\n".join(linhas)


def resposta(texto: str, cor: bool | None = None) -> None:
    """Imprime uma resposta com identidade e Markdown adequado ao terminal."""
    if cor is None:
        cor = usa_cor()
    marca = pintar("●", ROXO, negrito=True, cor=cor)
    nome = pintar("Gárgula", LILAS, negrito=True, cor=cor)
    print(f"{marca} {nome}")
    corpo = formatar_markdown(texto, cor=cor)
    if corpo:
        print("\n".join("  " + linha if linha else "" for linha in corpo.splitlines()))


class Pensando:
    """Indicador animado e descartável enquanto a primeira resposta é montada."""

    FRASES = (
        (0.0, "Lendo o contexto…"),
        (2.5, "Pensando na melhor resposta…"),
        (7.0, "Organizando os próximos passos…"),
    )
    QUADROS = ("·  ", "•  ", "•• ", "•••", " ••", "  •")

    def __init__(self, cor: bool | None = None):
        self.cor = usa_cor() if cor is None else cor
        self.animar = self.cor and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        self._fim = threading.Event()
        self._thread: threading.Thread | None = None
        self._inicio = 0.0

    def _frase(self) -> str:
        decorrido = time.monotonic() - self._inicio
        atual = self.FRASES[0][1]
        for limite, frase in self.FRASES:
            if decorrido >= limite:
                atual = frase
        return atual

    def _desenhar(self) -> None:
        i = 0
        while not self._fim.wait(0.12):
            quadro = self.QUADROS[i % len(self.QUADROS)]
            status = pintar(f"✦ {self._frase()} {quadro}", CINZA, cor=self.cor)
            sys.stdout.write("\r\x1b[2K" + status)
            sys.stdout.flush()
            i += 1

    def __enter__(self):
        self._inicio = time.monotonic()
        if self.animar:
            self._thread = threading.Thread(target=self._desenhar, daemon=True)
            self._thread.start()
        else:
            print("✦ Pensando…")
        return self

    def parar(self) -> None:
        self._fim.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if self.animar:
            sys.stdout.write("\r\x1b[2K")
            sys.stdout.flush()

    def __exit__(self, *_):
        self.parar()


def pensando(cor: bool | None = None) -> Pensando:
    return Pensando(cor=cor)


def erro(msg: str) -> None:
    print(pintar("✖ ", (248, 113, 113), cor=usa_cor(sys.stderr)) + msg, file=sys.stderr)


def aviso(msg: str) -> None:
    print(pintar("! ", (251, 191, 36), cor=usa_cor(sys.stderr)) + msg, file=sys.stderr)


def ok(msg: str) -> None:
    print(pintar("✔ ", VERDE) + msg)
