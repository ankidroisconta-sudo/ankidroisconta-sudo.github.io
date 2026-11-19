"""Cenas de motion graphics geradas por código (sem banco de imagens).

Serve para qualquer tema: tipografia animada com a frase da cena, números
que contam na tela (ex.: "300 toneladas") e fundo com luzes em movimento
na cor do molde. Também gera os efeitos sonoros (whoosh e pop).
"""
import math
import os
import random
import re
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from midia import load_font

FPS = 30
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
NUMBER = re.compile(r'(\d{1,3}(?:[.\s]\d{3})+|\d+(?:,\d+)?)\s*(%|por cento|milhões|milhão|bilhões|bilhão|mil|'
                    r'[a-záéíóúâêôãõç]+)?', re.I)


def hex_rgb(value):
    value = value.lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def ease(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def background(size, accent, seed):
    """Fundo escuro com degradê e duas luzes desfocadas, maior que o quadro para poder deslizar."""
    w, h = size
    W, H = int(w * 1.25), int(h * 1.25)
    rng = random.Random(seed)
    top = np.array([10, 14, 22], float)
    bottom = np.array([4, 6, 10], float)
    ramp = np.linspace(0, 1, H)[:, None, None]
    base = (top * (1 - ramp) + bottom * ramp) * np.ones((H, W, 3))
    im = Image.fromarray(base.astype(np.uint8))
    glow = Image.new('RGB', (W, H), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    a = hex_rgb(accent)
    for color, k in ((a, 0.55), ((60, 110, 255), 0.35)):
        r = int(min(W, H) * rng.uniform(0.28, 0.4))
        cx, cy = rng.uniform(0.15, 0.85) * W, rng.uniform(0.15, 0.85) * H
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(int(c * k) for c in color))
    glow = glow.filter(ImageFilter.GaussianBlur(min(W, H) // 7))
    im = Image.fromarray(np.clip(np.asarray(im, float) + np.asarray(glow, float), 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    step = max(40, w // 16)
    for x in range(0, W, step):
        d.line((x, 0, x, H), fill=(26, 32, 44), width=1)
    for y in range(0, H, step):
        d.line((0, y, W, y), fill=(26, 32, 44), width=1)
    return im


def wrap(draw, text, font, width):
    lines, line = [], ''
    for word in text.split():
        test = (line + ' ' + word).strip()
        if line and draw.textlength(test, font=font) > width:
            lines.append(line)
            line = word
        else:
            line = test
    if line:
        lines.append(line)
    return lines


def headline(scene):
    text = (scene.get('caption') or '').strip()
    if not text:
        sentence = re.split(r'(?<=[.!?])\s+', scene.get('text', '').strip())[0]
        text = ' '.join(sentence.split()[:9])
    return text.rstrip('.')


SKIP_UNITS = set('o a os as e de do da dos das em no na que pelo pela por para com um uma ao é foi'.split())


def find_number(text):
    for m in NUMBER.finditer(text):
        raw = m.group(1)
        value = float(raw.replace('.', '').replace(' ', '').replace(',', '.'))
        unit = (m.group(2) or '').strip()
        if unit.lower() in SKIP_UNITS:
            unit = ''
        if re.fullmatch(r'1[0-9]{3}|20[0-9]{2}', raw):
            return raw, value, unit, True  # ano: mostra sem contar e sem separador de milhar
        if value >= 2 or '%' in unit:
            return raw, value, unit, False
    return None


def render(scene, size, seconds, accent, channel, seed, out):
    w, h = size
    frames = max(2, round(seconds * FPS))
    bg = background(size, accent, seed)
    acc = hex_rgb(accent)
    vertical = h > w
    title = headline(scene)
    number = find_number(scene.get('caption', '') + ' ' + scene.get('text', ''))
    probe = ImageDraw.Draw(bg)
    margin = int(w * 0.08)
    fs = int((w * 0.085) if vertical else (h * 0.095))
    font = load_font(fs)
    while fs > 24:
        lines = wrap(probe, title, font, w - 2 * margin)
        if len(lines) <= (5 if vertical else 3):
            break
        fs -= 4
        font = load_font(fs)
    small = load_font(max(18, int(fs * 0.36)), False)
    big = load_font(int(fs * 2.1))
    line_h = int(fs * 1.18)
    block = len(lines) * line_h
    total_h = block + (int(fs * 2.1 * 1.25) + int(h * 0.04) if number else 0)
    y0 = max(int(h * 0.16), (h - total_h) // 2 - int(h * 0.07))
    words = [(i, word) for i, line in enumerate(lines) for word in line.split()]

    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(FPS), '-i', '-',
           '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
    try:
        for f in range(frames):
            t = f / FPS
            drift = f / frames
            ox = int((bg.width - w) * (0.15 + 0.7 * drift))
            oy = int((bg.height - h) * 0.5)
            frame = bg.crop((ox, oy, ox + w, oy + h))
            d = ImageDraw.Draw(frame)
            if channel:
                d.text((margin, int(h * 0.07)), channel.upper(), font=small, fill=(150, 160, 175))
            # barra de destaque cresce
            bar = int((w * 0.12) * ease(t / 0.5))
            d.rounded_rectangle((margin, y0 - int(fs * 0.45), margin + max(6, bar), y0 - int(fs * 0.3)), 4, fill=acc)
            # palavras entram uma a uma, subindo
            x_by_line = {}
            for n, (li, word) in enumerate(words):
                start = 0.15 + n * 0.11
                k = ease((t - start) / 0.35)
                if k <= 0:
                    x_by_line[li] = x_by_line.get(li, margin) + d.textlength(word + ' ', font=font)
                    continue
                x = x_by_line.get(li, margin)
                y = y0 + li * line_h + int((1 - k) * fs * 0.6)
                shade = int(255 * k)
                d.text((x, y), word, font=font, fill=(shade, shade, shade))
                x_by_line[li] = x + d.textlength(word + ' ', font=font)
            if number:
                raw, value, unit, year = number
                k = ease((t - 0.5) / 1.4)
                if k > 0:
                    shown = value * k
                    decimals = 1 if ',' in raw else 0
                    txt = raw if year else f'{shown:,.{decimals}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
                    ny = y0 + block + int(h * 0.04)
                    d.text((margin, ny), txt, font=big, fill=acc)
                    if unit:
                        ux = margin + d.textlength(txt + ' ', font=big)
                        d.text((ux, ny + int(fs * 1.25)), unit, font=font, fill=(235, 235, 235))
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        if proc.wait():
            raise RuntimeError(proc.stderr.read().decode('utf8', 'replace')[-500:])
    finally:
        if proc.poll() is None:
            proc.kill()


# ------------------------------------------------------------------ efeitos sonoros

RATE = 48000


def whoosh(seconds=0.7, seed=1):
    rng = np.random.default_rng(seed)
    n = int(RATE * seconds)
    noise = rng.standard_normal(n)
    # ruído filtrado com varredura de frequência (passa-faixa simples por média móvel dupla)
    out = np.zeros(n)
    t = np.linspace(0, 1, n)
    for width, gain in ((40, 1.0), (12, 0.5)):
        kernel = np.ones(width) / width
        out += gain * (noise - np.convolve(noise, kernel, 'same'))
    env = np.sin(np.pi * np.clip(t * 1.15, 0, 1)) ** 2
    pan = 0.5 + 0.5 * np.sin(np.pi * (t - 0.5))
    mono = out * env
    mono /= max(1e-9, np.abs(mono).max())
    return np.stack([mono * (1 - pan * 0.6), mono * (0.4 + pan * 0.6)], 1) * 0.5


def pop(seed=2):
    n = int(RATE * 0.12)
    t = np.arange(n) / RATE
    tone = np.sin(2 * np.pi * (900 - 2500 * t) * t) * np.exp(-t * 45)
    return np.stack([tone, tone], 1) * 0.35


def effects_track(events, seconds, path):
    """events: lista de (tempo, 'whoosh'|'pop')."""
    track = np.zeros((int(RATE * seconds) + RATE, 2))
    for k, (at, kind) in enumerate(events):
        clip = whoosh(seed=k) if kind == 'whoosh' else pop()
        start = max(0, int(RATE * (at - (0.35 if kind == 'whoosh' else 0))))
        end = min(len(track), start + len(clip))
        track[start:end] += clip[:end - start]
    track = np.clip(track[:int(RATE * seconds)], -1, 1)
    with wave.open(str(path), 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes((track * 32767).astype('<i2').tobytes())
    return path
