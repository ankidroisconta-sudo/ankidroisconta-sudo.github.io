"""Identidade de um canal novo: nome, textos, foto de perfil e banner.

Tudo gerado aqui mesmo, sem IA paga: o nicho vem do vídeo e do canal de
inspiração, e as cores/ícones vêm do tema do nicho (vendas.THEMES).
"""
import hashlib
import math
import random

from PIL import Image, ImageDraw, ImageFilter

import vendas
from midia import load_font

NAMES = {
    'ciencia': ['Universo em Escala', 'Cosmos Explicado', 'Além das Estrelas', 'Órbita Curiosa', 'Mapa do Universo', 'Ciência em Escala'],
    'historia': ['Por Trás da História', 'Arquivo Curioso', 'História Esquecida', 'Relíquias do Tempo', 'O Porquê da História', 'Crônicas Estranhas'],
    'financas': ['Bolso Inteligente', 'Dinheiro sem Mistério', 'Conta no Azul', 'Finanças de Verdade', 'Cofre Aberto', 'Sai do Vermelho'],
    'plantas': ['Varanda Verde', 'Horta no Vaso', 'Raiz e Folha', 'Jardim Pequeno', 'Pomar de Varanda'],
    'pets': ['Patas e Fatos', 'Mundo Pet Real', 'Faro Curioso', 'Rabo Abanando', 'Pet Explicado'],
    'mente': ['Mente em Ordem', 'Estoico Moderno', 'Pensar Melhor', 'Calma Prática', 'Cabeça Leve'],
    'culinaria': ['Panela Esperta', 'Receita Sem Erro', 'Cozinha Rápida', 'Sabor de Casa', 'Fogão Curioso'],
    '': ['Curioso Demais', 'Fato Escondido', 'Mundo Explicado', 'Isso Explica Tudo', 'Ponto Curioso'],
}

NICHES = {
    'ciencia': 'Ciência e espaço explicados de forma visual',
    'historia': 'Curiosidades e mistérios da história',
    'financas': 'Dinheiro, dívidas e finanças do dia a dia',
    'plantas': 'Horta, plantas e pomar em vasos',
    'pets': 'Comportamento, raças e cuidados com pets',
    'mente': 'Psicologia, estoicismo e mente tranquila',
    'culinaria': 'Receitas práticas e truques de cozinha',
    '': 'Curiosidades e conhecimento',
}

TONE = {
    'ciencia': 'Tom de assombro e escala: comparações concretas (tamanhos, distâncias, tempos) que o público consegue imaginar.',
    'historia': 'Tom de investigação: abrir com o fato estranho, explicar o porquê e fechar com uma consequência surpreendente.',
    'financas': 'Tom de amigo que entende do assunto: direto, sem julgamento, sempre citando a regra ou a lei.',
    'plantas': 'Tom prático e calmo: passo a passo, materiais baratos e erros comuns.',
    'pets': 'Tom carinhoso e informativo, baseado em comportamento animal e orientação veterinária.',
    'mente': 'Tom sereno e reflexivo, com exemplos do cotidiano e uma ação prática no final.',
    'culinaria': 'Tom animado e rápido: ingredientes, tempo e o truque que faz a diferença.',
    '': 'Tom curioso e claro, com gancho forte e explicação simples.',
}


def theme_of(text):
    return vendas.theme_key(text)


PATTERNS = ['Mundo {T}', '{T} Explicado', '{T} em Foco', 'Por Dentro {de} {T}', 'Curiosidades {de} {T}', '{T} sem Segredo', 'Tudo Sobre {T}']
PALETTE = ['#ff7a45', '#36c5f0', '#b388ff', '#ffb000', '#00c2a8', '#ff4f8b', '#7bd389', '#5b8cff']


def _de(topic):
    """'de' com o artigo certo quando o tema é uma palavra conhecida (ex.: 'dos Carros')."""
    t = topic.lower()
    if t.endswith('s') and not t.endswith('ss'):
        return 'das' if t.endswith('as') else 'dos'
    return 'da' if t.endswith('a') else 'do'


def topic_names(topic):
    t = ' '.join(w.capitalize() if len(w) > 2 else w for w in topic.split()[:3])
    plural = t.lower().endswith('s')
    return [p.replace('{T} Explicado', '{T} Explicados' if plural else '{T} Explicado').replace('{T}', t).replace('{de}', _de(t)) for p in PATTERNS]


def suggest_name(key, taken, seed, skip=0, topic=''):
    bank = (list(NAMES[key]) if key in NAMES and key else []) + (topic_names(topic) if topic else []) or NAMES['']
    taken = {t.lower() for t in taken}
    start = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(bank)
    free = [bank[(start + i) % len(bank)] for i in range(len(bank)) if bank[(start + i) % len(bank)].lower() not in taken]
    if not free:
        return f'{bank[start]} {len(taken) + 1}'
    return free[skip % len(free)]


def channel_plan(video, source, taken, skip=0, topic=''):
    """Monta o canal a partir do vídeo escolhido e do canal de inspiração. Serve para qualquer tema:
    nichos conhecidos ganham nomes e cores sob medida; os demais usam o próprio tema (topic, em português)."""
    corpus = ' '.join([video.get('title', ''), ' '.join(video.get('tags') or []), video.get('description', ''),
                       source.get('title', ''), source.get('description', ''), source.get('keywords', '')])
    key = theme_of(corpus)
    theme = vendas.theme_for(corpus)
    seed = source.get('id') or video.get('channel_id') or video.get('title', '')
    name = suggest_name(key, taken, seed, skip, '' if key else topic)
    if not key:  # tema fora da lista: cor própria, estável para o mesmo canal de inspiração
        theme['accent'] = PALETTE[int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(PALETTE)]
    seconds = int(video.get('seconds') or 0)
    short = 0 < seconds <= 180
    minutes = round(max(0.3, seconds / 60), 1) if seconds else (0.75 if short else 10)
    niche = NICHES[key] if key else (f'Tudo sobre {topic.lower()}: curiosidades, explicações e novidades' if topic else NICHES[''])
    src = source.get('title') or video.get('channel', '')
    instructions = (f"{TONE.get(key, TONE[''])} Canal inspirado no estilo de \"{src}\" (sem copiar falas, títulos ou thumbnails): "
                    + ('Shorts verticais com gancho nos 2 primeiros segundos e um fato surpreendente por cena.' if short else
                       f'vídeos longos de cerca de {round(minutes)} minutos, com capítulos claros, gancho nos primeiros 10 segundos e uma pergunta respondida só no final.')
                    + ' Público brasileiro: exemplos, unidades e referências do Brasil.')
    about = (f"{name}: {niche.lower()}. "
             + ('Vídeos curtos, toda semana, com um fato que você não sabia.' if short else 'Vídeos novos toda semana, explicados do zero e sem enrolação.')
             + ' Ative o sininho para não perder o próximo.')
    return {
        'name': name, 'channel': name, 'niche': niche, 'language': 'Português brasileiro', 'instructions': instructions,
        'minutes': min(60, minutes), 'format': 'vertical' if short else 'horizontal', 'resolution': 1080,
        'accent': theme['accent'], 'captions': 'dinamica', 'music': 'ambiente', 'voice': '',
        'about': about, 'footer': f"Inscreva-se no {name} para mais {niche.lower()}.", 'theme': key or 'geral',
        'source': {'channel_id': source.get('id') or video.get('channel_id', ''), 'title': src,
                   'video_title': video.get('title', ''), 'video_url': video.get('url', '')},
    }


# ------------------------------------------------------------------ imagens

def _bg(size, accent, mode, seed):
    import numpy as np
    w, h = size
    rng = random.Random(seed)
    acc = vendas.rgb(accent)
    base = np.array((12, 13, 18) if mode == 'dark' else (246, 241, 231), float)
    glow = Image.new('RGB', size, (0, 0, 0))
    d = ImageDraw.Draw(glow)
    for strength in (.75, .45, .3):
        r = int(min(w, h) * rng.uniform(.35, .6))
        cx, cy = rng.uniform(.1, .9) * w, rng.uniform(.1, .9) * h
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(int(c * strength) for c in acc))
    g = np.asarray(glow.filter(ImageFilter.GaussianBlur(min(w, h) // 5)), float) / 255
    if mode == 'dark':
        arr = base + g * 255
    else:  # fundo claro: a luz do tema tinge levemente o papel
        arr = base * (1 - .35 * g.max(axis=2, keepdims=True)) + np.array(acc, float) * .35 * g.max(axis=2, keepdims=True)
    im = Image.fromarray(np.clip(arr, 0, 255).astype('uint8'))
    d = ImageDraw.Draw(im)
    dots = (255, 255, 255) if mode == 'dark' else tuple(int(c * .6) for c in acc)
    for _ in range(int(w * h / 9000)):
        x, y = rng.randrange(w), rng.randrange(h)
        rr = rng.choice((1, 1, 1, 2))
        a = rng.randint(60, 200) / 255
        under = im.getpixel((x, y))
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=tuple(int(c * a + u * (1 - a)) for c, u in zip(dots, under)))
    return im


def _fit(draw, text, max_w, start, bold=True):
    size = start
    while size > 12:
        f = load_font(size, bold)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return load_font(12, bold)


def avatar(path, name, accent, mode, seed=''):
    """Foto de perfil 800x800 (o YouTube recorta em círculo): monograma na cor do canal."""
    S = 800
    im = _bg((S, S), accent, mode, seed or name)
    d = ImageDraw.Draw(im)
    acc = vendas.rgb(accent)
    ring = int(S * .44)
    d.ellipse((S / 2 - ring, S / 2 - ring, S / 2 + ring, S / 2 + ring), outline=acc, width=14)
    words = [w for w in name.replace('-', ' ').split() if w[0].isalnum() and w.lower() not in ('de', 'da', 'do', 'das', 'dos', 'e', 'em', 'no', 'na', 'o', 'a', 'sem')]
    mono = ''.join(w[0].upper() for w in words[:2]) or name[:1].upper()
    f = _fit(d, mono, S * .62, 380)
    ink = (245, 242, 235) if mode == 'dark' else (24, 22, 20)
    d.text((S / 2, S / 2 + 10), mono, font=f, fill=ink, anchor='mm')
    im.save(path, quality=95)


def banner(path, name, tagline, accent, mode, seed=''):
    """Banner 2560x1440. O texto fica na área segura central (1546x423) que aparece em todos os aparelhos."""
    W, H = 2560, 1440
    im = _bg((W, H), accent, mode, (seed or name) + 'b')
    d = ImageDraw.Draw(im)
    acc = vendas.rgb(accent)
    safe_w, safe_h = 1546, 423
    x0, y0 = (W - safe_w) // 2, (H - safe_h) // 2
    ink = (245, 242, 235) if mode == 'dark' else (24, 22, 20)
    f = _fit(d, name.upper(), safe_w - 80, 190)
    d.text((W / 2, y0 + safe_h * .42), name.upper(), font=f, fill=ink, anchor='mm')
    bar_w = min(safe_w * .5, d.textlength(name.upper(), font=f) * .35)
    d.rounded_rectangle((W / 2 - bar_w / 2, y0 + safe_h * .66, W / 2 + bar_w / 2, y0 + safe_h * .66 + 12), 6, fill=acc)
    t = _fit(d, tagline, safe_w - 120, 58, False)
    d.text((W / 2, y0 + safe_h * .84), tagline, font=t, fill=tuple(int(c * .85) for c in ink), anchor='mm')
    im.save(path, quality=93)
