"""Cores, mascote e banner do Gárgula."""

from __future__ import annotations

import os
import sys

# Paleta roxa (RGB)
PALETA = {
    "D": (91, 33, 182),    # asas, roxo escuro
    "P": (139, 92, 246),   # corpo, roxo
    "L": (196, 181, 253),  # barriga/focinho, lilás
    "E": (245, 243, 255),  # olhos brilhando
}
ROXO = PALETA["P"]
LILAS = PALETA["L"]
CINZA = (148, 148, 160)

# Gárgula agachado, asas abertas, garras no topo do quadro.
# Cada linha = 1 pixel; duas linhas viram uma linha do terminal (meio-bloco).
MASCOTE = [
    "...P................P...",
    "...PP..............PP...",
    "....PP..PPPPPPPP..PP....",
    ".....PPPPPPPPPPPPPP.....",
    "D....PPPEEPPPPEEPPP....D",
    "DD...PPPPPPPPPPPPPP...DD",
    "DDD...PPPPLLLLPPPP...DDD",
    "DDDD...PPPPPPPPPP...DDDD",
    ".DDDDPPPPLLLLLLPPPPDDDD.",
    "..DDDPPPPLLLLLLPPPPDDD..",
    "...DDPPPLLLLLLLLPPPDD...",
    "....D.PPPPPPPPPPPP.D....",
    "......PPP.PPPP.PPP......",
    ".....P.P.P....P.P.P.....",
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


def desenhar(sprite=MASCOTE, cor: bool = True) -> list[str]:
    """Converte a grade de pixels em linhas de meio-bloco (▀ ▄ █)."""
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
    info = f"provedor: {provedor} · modelo: {modelo}"
    info2 = f"modo: {modo}"
    dica = "/ajuda para comandos · /sair para sair"

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


def erro(msg: str) -> None:
    print(pintar("✖ ", (248, 113, 113), cor=usa_cor(sys.stderr)) + msg, file=sys.stderr)


def aviso(msg: str) -> None:
    print(pintar("! ", (251, 191, 36), cor=usa_cor(sys.stderr)) + msg, file=sys.stderr)


def ok(msg: str) -> None:
    print(pintar("✔ ", (74, 222, 128)) + msg)
