"""Gera o GIF animado oficial do Gárgula CLI com o Susanoo pulsando em roxo e fumacinha saindo dos chifres."""
import os
import math
from PIL import Image, ImageDraw, ImageFont

MASCOTE_ROWS = [
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

def lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def create_gif(output_path, num_frames=32):
    W, H = 640, 440
    frames = []

    font_path = r"C:\Windows\Fonts\consola.ttf"
    font_mono = ImageFont.truetype(font_path, 13) if os.path.exists(font_path) else ImageFont.load_default()
    font_title = ImageFont.truetype(font_path, 12) if os.path.exists(font_path) else ImageFont.load_default()

    # Posições dos chifres de onde a fumaça sai (em coordenadas do grid):
    # col 1 (chifre esquerdo), col 12 (crista central), col 23 (chifre direito)
    # Configuração do pixel art:
    pixel_size = 8
    grid_w = len(MASCOTE_ROWS[0]) * pixel_size # 25 * 8 = 200
    grid_h = len(MASCOTE_ROWS) * pixel_size    # 10 * 8 = 80
    grid_x0 = (W - grid_w) // 2
    grid_y0 = 110

    # Partículas de fumaça (cada uma com sua fase e trajetória senoidal):
    # Geramos fumaça saindo do chifre esquerdo, central e direito
    emitters = [
        (grid_x0 + 1 * pixel_size + 4, grid_y0 + 2),  # Chifre esquerdo
        (grid_x0 + 12 * pixel_size + 4, grid_y0 + 14), # Crista do capacete
        (grid_x0 + 23 * pixel_size + 4, grid_y0 + 2), # Chifre direito
    ]

    for f in range(num_frames):
        # Frame progress [0..1]
        progress = f / num_frames
        angle = 2 * math.pi * progress

        # Pulso roxo respirando (roxinho piscando / breathing glow)
        # senoide suave: 0.0 a 1.0
        pulse = 0.5 + 0.5 * math.sin(angle)
        eye_pulse = 0.5 + 0.5 * math.cos(angle * 1.5)

        # Paleta dinâmica do frame:
        c_p = lerp((120, 50, 220), (175, 115, 255), pulse)  # Roxo chakra Susanoo
        c_d = lerp((70, 25, 140), (105, 45, 190), pulse)    # Roxo escuro armadura
        c_l = lerp((180, 140, 240), (225, 195, 255), pulse) # Lilás garras
        c_w = lerp((220, 220, 240), (255, 255, 255), pulse) # Joia branca
        c_r = lerp((220, 38, 38), (255, 68, 68), eye_pulse) # Olho vermelho Mangekyou
        c_k = (20, 20, 25)                                   # Pupila preta

        paleta_frame = {
            "P": c_p,
            "D": c_d,
            "L": c_l,
            "W": c_w,
            "R": c_r,
            "K": c_k,
        }

        # Cria a imagem base do frame
        img = Image.new("RGBA", (W, H), (14, 14, 20, 255))
        draw = ImageDraw.Draw(img)

        # 1. Janela de terminal (estilo moderno dark com borda sutil)
        draw.rounded_rectangle([15, 15, W - 15, H - 15], radius=14, fill=(18, 18, 28, 255), outline=(50, 42, 75, 255), width=2)

        # Botões de janela (vermelho, amarelo, verde)
        draw.ellipse([34, 30, 44, 40], fill=(239, 68, 68, 255))
        draw.ellipse([52, 30, 62, 40], fill=(245, 158, 11, 255))
        draw.ellipse([70, 30, 80, 40], fill=(34, 197, 94, 255))
        draw.text((95, 29), "gargula — revos terminal (susanoo)", font=font_title, fill=(130, 130, 155, 255))

        # 2. Fumacinha de chakra saindo dos chifres (desenhada atrás/acima do mascote)
        # Para loop perfeito: partículas se movem de baixo para cima e se repetem
        smoke_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        smoke_draw = ImageDraw.Draw(smoke_layer)

        for emitter_idx, (ex, ey) in enumerate(emitters):
            # Cria 5 camadas de partículas por emissor com offsets de tempo
            for p_idx in range(6):
                # tempo local da partícula (0 a 1 em loop)
                p_time = (progress + p_idx / 6.0 + emitter_idx * 0.33) % 1.0
                # A partícula sobe
                sy = ey - (p_time * 65)
                # Oscilação horizontal senoidal suave (ondulação da fumaça)
                drift_dir = -1 if emitter_idx == 0 else (1 if emitter_idx == 2 else 0)
                drift = drift_dir * (p_time * 18)
                sx = ex + drift + math.sin(p_time * 6.0 + emitter_idx) * 8

                # Raio cresce à medida que sobe
                radius = 3 + p_time * 9
                # Opacidade diminui à medida que sobe (fade out)
                alpha = int(140 * math.sin(p_time * math.pi))
                if alpha > 0 and sy > 45:
                    smoke_color = (*c_l[:3], alpha)
                    smoke_draw.ellipse([sx - radius, sy - radius, sx + radius, sy + radius], fill=smoke_color)

        img = Image.alpha_composite(img, smoke_layer)
        draw = ImageDraw.Draw(img)

        # 3. Desenho do Mascote (Susanoo Pixel Art)
        for r_idx, row in enumerate(MASCOTE_ROWS):
            for c_idx, ch in enumerate(row):
                if ch in paleta_frame:
                    px = grid_x0 + c_idx * pixel_size
                    py = grid_y0 + r_idx * pixel_size
                    color = paleta_frame[ch]
                    draw.rectangle([px, py, px + pixel_size - 1, py + pixel_size - 1], fill=color)

        # 4. Card da CLI logo abaixo das garras do Susanoo
        # As garras terminam em grid_y0 + grid_h (110 + 80 = 190)
        card_w = 460
        card_x0 = (W - card_w) // 2
        card_y0 = grid_y0 + grid_h - 4 # Encaixa perfeitamente sob as garras
        card_h = 190

        # Borda roxa da caixa da CLI
        borda_cor = c_p
        draw.rounded_rectangle([card_x0, card_y0, card_x0 + card_w, card_y0 + card_h], radius=8, outline=borda_cor, width=2)

        # Texto dentro do card
        tx = card_x0 + 20
        ty = card_y0 + 18
        draw.text((tx, ty), "Gárgula CLI", font=font_mono, fill=(167, 139, 250, 255))
        draw.text((tx + 95, ty), "v0.3.0", font=font_mono, fill=(140, 140, 155, 255))
        ty += 22
        draw.text((tx, ty), "copiloto de marketing, vendas, WhatsApp e Meta Ads", font=font_mono, fill=(196, 181, 253, 255))
        ty += 26
        draw.text((tx, ty), "anthropic / claude-sonnet-5-5", font=font_mono, fill=(140, 140, 155, 255))
        ty += 18
        draw.text((tx, ty), "modo geral", font=font_mono, fill=(140, 140, 155, 255))
        ty += 18
        draw.text((tx, ty), "/ajuda · Ctrl+C interrompe · /sair", font=font_mono, fill=(110, 110, 130, 255))
        ty += 28

        # Prompt interativo piscando (prompt cursor)
        prompt_pulse = 255 if (f % 16 < 8) else 80
        draw.text((tx, ty), "> [Gárgula online e vigilante]", font=font_mono, fill=(196, 181, 253, 255))
        draw.rectangle([tx + 225, ty + 2, tx + 233, ty + 15], fill=(167, 139, 250, prompt_pulse))

        # Converte para P (paleta otimizada para GIF)
        frame_p = img.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=128)
        frames.append(frame_p)

    # Salva o GIF animado
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=40, # 40ms = 25 fps
        loop=0,
        optimize=True
    )
    print(f"GIF salvo com sucesso em: {output_path} ({len(frames)} frames)")

if __name__ == "__main__":
    out_file = r"C:\Users\junio\Projetos\gargula-cli\assets\gargula.gif"
    create_gif(out_file, num_frames=32)
