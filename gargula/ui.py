"""Cores, mascote e componentes visuais do Gárgula."""

from __future__ import annotations

import os
import re
import sys
import threading
import time

# Paleta roxa (RGB), joia da fronte e olhos Mangekyou
PALETA = {
    "D": (91, 33, 182),    # roxo escuro, armadura
    "P": (139, 92, 246),   # roxo chakra Susanoo
    "L": (196, 181, 253),  # lilás garras/aura
    "W": (245, 243, 255),  # branco brilho da joia da testa
    "E": (245, 243, 255),  # branco brilho
    "R": (239, 68, 68),    # vermelho Mangekyou Sharingan
    "K": (20, 20, 25),     # pupila preta do Mangekyou
    "C": (100, 116, 139),  # cornija/pedra, slate cinza
    "B": (71, 85, 105),    # fachada/prédio, slate escuro
}
ROXO = PALETA["P"]
LILAS = PALETA["L"]
CINZA = (148, 148, 160)
VERDE = (74, 222, 128)
VERMELHO = PALETA["R"]
AMARELO = (251, 191, 36)
PEDRA = PALETA["C"]

# Máscara do Susanoo (capacete Kabuto fechado no topo com chifres, domo blindado,
# joia da fronte, olhos Mangekyou Sharingan vermelhos e garras peeking sobre o quadro).
# Cada linha = 1 pixel; duas linhas viram uma linha do terminal (meio-bloco).
MASCOTE = [
    ".P.....PPPPPPPPPPP.....P.",
    ".PP...PPPPPPPPPPPPP...PP.",
    ".PPPPPPPPPPPPPPPPPPPPPPP.",
    "PPPPPPPPPPPPPPPPPPPPPPPPP",
    "PPPPPPPP..PPWPP..PPPPPPPP",
    "PPPPPPPP..PPWPP..PPPPPPPP",
    "PPPP..RKRPPPPPPPRKR..PPPP",
    "PPP...RRRPPPPPPPRRR...PPP",
    "..........PPPPP..........",
    ".LLL......PPPPP......LLL.",
]


# Fumacinha de chakra do Susanoo saindo dos chifres
FUMACA_ESTATICA = (
    "    ~                 ~  ",
    "   °    ~   ·   ~    °   ",
)

FUMACA_QUADROS = (
    (
        "    ~                 ~  ",
        "   °    ~   ·   ~    °   ",
    ),
    (
        "   ·    °         °    · ",
        "    ~     ·   ·     ~    ",
    ),
    (
        "   °        ~        °   ",
        "  ·    ~    °    ~    ·  ",
    ),
    (
        "  ~     ·       ·     ~  ",
        "   °      ~   ~      °   ",
    ),
)


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


def desenhar(sprite: list[str] | None = None, cor: bool = True, paleta: dict | None = None) -> list[str]:
    """Converte a grade de pixels em linhas de meio-bloco (▀ ▄ █)."""
    if sprite is None:
        sprite = MASCOTE
    p = paleta or PALETA
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
                a = "." if a in ("E", "R", "K") else a
                b = "." if b in ("E", "R", "K") else b
                if a != "." and b != ".":
                    partes.append("█")
                elif a != ".":
                    partes.append("▀")
                elif b != ".":
                    partes.append("▄")
                else:
                    partes.append(" ")
                continue
            ca, cb = p.get(a), p.get(b)
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


def _caixa_banner(versao: str, provedor: str, modelo: str, modo: str, cor: bool, auto: bool) -> tuple[int, str, list[str]]:
    """Monta a moldura de boas-vindas sem duplicar código entre estático e animado."""
    largura = 58  # largura interna do quadro
    larg_sprite = len(MASCOTE[0])
    recuo = " " * (1 + (largura - larg_sprite) // 2)

    def linha(txt_cru: str, txt_cor: str | None = None) -> str:
        espaco = " " * max(0, largura - 2 - len(txt_cru))
        borda = pintar("│", ROXO, cor=cor)
        return f"{borda}  {txt_cor if txt_cor is not None else txt_cru}{espaco}{borda}"

    titulo_cru = f"Gárgula CLI  v{versao}"
    titulo = pintar("Gárgula CLI", ROXO, negrito=True, cor=cor) + pintar(f"  v{versao}", CINZA, cor=cor)
    sub = "copiloto de marketing, vendas, WhatsApp e Meta Ads"
    info = f"{provedor} / {modelo}"[: largura - 2]
    info2_cru = f"modo {modo}" + (" · [YOLO]" if auto else "")
    info2 = pintar(f"modo {modo}", CINZA, cor=cor) + (
        pintar(" · ", CINZA, cor=cor) + pintar("[YOLO]", AMARELO, negrito=True, cor=cor) if auto else ""
    )
    dica = "/ajuda · Ctrl+C interrompe · /sair"

    caixa = [
        pintar("╭" + "─" * largura + "╮", ROXO, cor=cor),
        linha(titulo_cru, titulo),
        linha(sub, pintar(sub, LILAS, cor=cor)),
        linha(""),
        linha(info, pintar(info, CINZA, cor=cor)),
        linha(info2_cru, info2),
        linha(dica, pintar(dica, CINZA, cor=cor)),
        pintar("╰" + "─" * largura + "╯", ROXO, cor=cor),
    ]
    return largura, recuo, caixa


def banner(versao: str, provedor: str, modelo: str, modo: str, cor: bool | None = None, auto: bool = False) -> str:
    """Quadro de boas-vindas com o Gárgula Susanoo e fumacinha de chakra saindo dos chifres."""
    if cor is None:
        cor = usa_cor()
    _, recuo, caixa = _caixa_banner(versao, provedor, modelo, modo, cor, auto)
    out = [recuo + pintar(s, LILAS, cor=cor) for s in FUMACA_ESTATICA]
    out.extend(recuo + l for l in desenhar(cor=cor))
    out.extend(caixa)
    return "\n".join(out)


def banner_animado(versao: str, provedor: str, modelo: str, modo: str, cor: bool | None = None, frames: int = 14, auto: bool = False) -> None:
    """Animação de despertar no terminal: pulso roxo e fumacinha de chakra subindo em tempo real."""
    import math

    if cor is None:
        cor = usa_cor()
    _, recuo, corpo_caixa = _caixa_banner(versao, provedor, modelo, modo, cor, auto)
    total_linhas = len(FUMACA_ESTATICA) + (len(MASCOTE) + 1) // 2 + len(corpo_caixa)

    def _lerp(c1, c2, t):
        return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

    fps = 12
    dt = 1.0 / fps

    try:
        for i in range(frames):
            angle = (i / frames) * 2 * math.pi
            pulse = 0.5 + 0.5 * math.sin(angle)
            eye_pulse = 0.5 + 0.5 * math.cos(angle * 1.5)

            c_p = _lerp((110, 45, 200), (175, 115, 255), pulse)
            c_l = _lerp((170, 130, 230), (220, 190, 255), pulse)
            c_w = _lerp((210, 210, 240), (255, 255, 255), pulse)
            c_r = _lerp((200, 30, 30), (255, 75, 75), eye_pulse)

            paleta_frame = dict(PALETA)
            paleta_frame["P"] = c_p
            paleta_frame["L"] = c_l
            paleta_frame["W"] = c_w
            paleta_frame["R"] = c_r

            smoke = FUMACA_QUADROS[i % len(FUMACA_QUADROS)]
            linhas_topo = [recuo + pintar(s, c_l, cor=cor) for s in smoke]
            sprite_linhas = desenhar(cor=cor, paleta=paleta_frame)
            linhas_topo.extend(recuo + l for l in sprite_linhas)

            todas = linhas_topo + corpo_caixa
            if i == 0:
                sys.stdout.write("\n".join(todas) + "\n")
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\x1b[{total_linhas}A")
                for l in todas:
                    sys.stdout.write("\r\x1b[2K" + l + "\n")
                sys.stdout.flush()
            time.sleep(dt)
    except KeyboardInterrupt:
        pass


def exibir_banner_inicial(versao: str, provedor: str, modelo: str, modo: str, cor: bool | None = None, auto: bool = False) -> None:
    """Exibe animação de despertar no terminal interativo ou banner estático em pipes/terminais estreitos."""
    import shutil

    if cor is None:
        cor = usa_cor()
    tam = shutil.get_terminal_size((80, 24))
    cabe_animacao = tam.columns >= 62 and tam.lines >= 17
    if cor and cabe_animacao and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        banner_animado(versao, provedor, modelo, modo, cor=cor, auto=auto)
    else:
        print(banner(versao, provedor, modelo, modo, cor=cor, auto=auto))


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
    """Spinner minimalista a prova de bala para Windows Terminal.

    Nao usa \\x1b[2K (bugado em wrap no WT), nao usa Unicode ambiguo.
    So \\r + texto + pad de espacos. Nunca ultrapassa a largura do terminal.
    """

    FRASES = (
        (0.0, "pensando"),
        (3.0, "quase la"),
        (8.0, "organizando"),
    )
    PULSO = (
        (124, 58, 237),
        (139, 92, 246),
        (167, 139, 250),
        (196, 160, 255),
        (167, 139, 250),
        (139, 92, 246),
    )
    DOTS = (" .  ", " .. ", " ...", "  ..", "   .", "    ")

    def __init__(self, cor: bool | None = None):
        self.cor = usa_cor() if cor is None else cor
        self.animar = self.cor and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        self._fim = threading.Event()
        self._thread: threading.Thread | None = None
        self._inicio = 0.0

    def _frase(self) -> str:
        t = time.monotonic() - self._inicio
        txt = self.FRASES[0][1]
        for lim, f in self.FRASES:
            if t >= lim:
                txt = f
        return txt

    def _desenhar(self) -> None:
        import shutil

        i = 0
        while not self._fim.wait(0.15):
            cols = shutil.get_terminal_size((80, 24)).columns
            safe = max(10, cols - 2)  # margem de seguranca
            c = self.PULSO[i % len(self.PULSO)]
            dots = self.DOTS[i % len(self.DOTS)]
            # Texto visivel puro (sem ANSI) para medir
            vis = f"  {self._frase()}{dots}"
            if len(vis) > safe:
                vis = vis[:safe]
            # Aplica cor
            colored = pintar(vis, c, cor=self.cor)
            # \r volta ao inicio, texto + espacos apaga residuo, \r final reposiciona
            pad = " " * max(0, safe - len(vis))
            sys.stdout.write(f"\r{colored}{pad}\r")
            sys.stdout.flush()
            i += 1

    def __enter__(self):
        self._inicio = time.monotonic()
        if self.animar:
            self._thread = threading.Thread(target=self._desenhar, daemon=True)
            self._thread.start()
        else:
            print("  pensando...")
        return self

    def parar(self) -> None:
        import shutil

        self._fim.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        if self.animar:
            cols = shutil.get_terminal_size((80, 24)).columns
            sys.stdout.write("\r" + " " * min(cols - 1, 60) + "\r")
            sys.stdout.flush()

    def __exit__(self, *_):
        self.parar()


def pensando(cor: bool | None = None) -> Pensando:
    return Pensando(cor=cor)


def ler_tecla() -> str:
    """Lê uma única tecla sem precisar de Enter (TTY only, stdlib puro)."""
    if not (hasattr(sys.stdin, "isatty") and sys.stdin.isatty()):
        try:
            return input().strip()[:1].lower()
        except EOFError:
            return ""
    try:
        if os.name == "nt":
            import msvcrt
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):  # tecla especial (setas, F1-F12)
                msvcrt.getwch()         # consumir segundo byte
                return ""
            if ch == "\x03":            # Ctrl+C
                raise KeyboardInterrupt
            return ch.lower()
        # Unix/macOS
        import tty
        import termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x1b":  # escape (setas etc)
            return ""
        return ch.lower()
    except (ImportError, OSError):
        try:
            return input().strip()[:1].lower()
        except EOFError:
            return ""


def erro(msg: str) -> None:
    print(pintar("✖ ", (248, 113, 113), cor=usa_cor(sys.stderr)) + msg, file=sys.stderr)


def aviso(msg: str) -> None:
    print(pintar("! ", (251, 191, 36), cor=usa_cor(sys.stderr)) + msg, file=sys.stderr)


def ok(msg: str) -> None:
    print(pintar("✔ ", VERDE) + msg)
