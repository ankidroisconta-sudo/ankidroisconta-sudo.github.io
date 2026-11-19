"""Página de vendas do e-book de cada canal.

Estrutura pensada para quem chega pelo comentário fixado no celular:
capa + promessa + preço, faixa com os capítulos, "por dentro", trechos,
sumário numerado, dúvidas e chamada final com garantia.
Tudo num único index.html (mais a capa), pronto para subir em qualquer hospedagem.
"""
import html
import io
import json
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from midia import load_font

EXAMPLE = {
    'ebook_name': 'Nome do e-book',
    'price': '27,90',
    'installments': 'ou 6x de R$ 5,24',
    'checkout': 'https://link-do-seu-checkout',
    'hero_title': 'Uma frase curta que resume a promessa.',
    'hero_text': 'Duas linhas explicando o que a pessoa recebe e por que é simples.',
    'cta': 'QUERO O E-BOOK',
    'inside_kicker': 'POR DENTRO',
    'inside_title': 'CADA CAPÍTULO, O MESMO *CAMINHO.*',
    'inside_text': 'Como cada capítulo é organizado e quanto tempo leva para ler.',
    'steps': [{'title': 'Passo', 'text': 'O que a pessoa encontra nesta parte.'}],
    'samples_title': 'LEIA UM *TRECHO.*',
    'samples': [{'title': 'Título do trecho', 'text': 'Um parágrafo real do e-book.'}],
    'list_kicker': 'O CONTEÚDO',
    'list_title': 'OS *10* CAPÍTULOS.',
    'list_text': 'Uma frase sobre o conjunto.',
    'items': [{'title': 'Capítulo', 'subtitle': 'Do que ele trata'}],
    'faq': [{'q': 'Como recebo o e-book?', 'a': 'Logo após a confirmação do pagamento, por e-mail.'}],
    'final_title': 'DEPOIS DESTE LIVRO, VOCÊ *NUNCA MAIS* ...',
    'final_text': 'Pagamento único, e o e-book é seu para sempre.',
    'guarantee_days': 7,
}


def prompt(channel, niche, video_titles):
    ex = json.dumps(EXAMPLE, ensure_ascii=False, indent=1)
    vids = '; '.join(video_titles[:15]) or 'ainda sem vídeos'
    return f"""Crie o texto de uma página de vendas para o e-book do canal do YouTube "{channel}" (nicho: {niche}).
Vídeos do canal: {vids}.
O e-book deve ser o aprofundamento natural desses vídeos. Público: brasileiros que chegam pelo comentário fixado, no celular.
Regras: português do Brasil, frases curtas, nada de promessas exageradas, de resultados garantidos ou de números inventados sobre o e-book (páginas, alunos, depoimentos).
Use *asteriscos* em volta das palavras que devem ficar em destaque na cor do canal (só nos títulos).
Inclua de 3 a 5 steps, de 3 a 6 samples (trechos realmente úteis), de 8 a 30 items e de 4 a 6 faq.
Retorne SOMENTE um objeto JSON válido neste formato, sem markdown:
{ex}"""


def clean(d):
    out = {}
    for k, v in EXAMPLE.items():
        val = d.get(k, v)
        if isinstance(v, list):
            if not isinstance(val, list):
                raise ValueError(f'"{k}" precisa ser uma lista.')
            keys = list(v[0].keys())
            out[k] = [{kk: str(x.get(kk, ''))[:1500] for kk in keys} for x in val if isinstance(x, dict)][:60]
        elif isinstance(v, int):
            out[k] = max(0, min(90, int(val or 0)))
        else:
            out[k] = str(val or '')[:2000]
    if out['checkout'] and not re.fullmatch(r'https?://[^\s<>"]+', out['checkout']):
        raise ValueError('O link do checkout precisa começar com https://')
    return out


def mark(text):
    """Escapa o texto e troca *destaque* por <span class=hl>."""
    return re.sub(r'\*(.+?)\*', r'<span class="hl">\1</span>', html.escape(text))


# ------------------------------------------------------------------ temas por nicho
ICONS = {
    'wallet': 'M3 7h15a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H3z M3 7l3-4h10l2 4 M16 14h2',
    'card': 'M2 6h20v12H2z M2 10h20 M6 15h4',
    'chart': 'M3 3v18h18 M7 15l4-4 3 3 5-6',
    'coin': 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M15 8.5h-4a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4H9 M12 6v2 M12 16.5v1.5',
    'message': 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z',
    'leaf': 'M5 21c0-9 6-15 16-16-1 10-7 16-16 16z M5 21l8-8',
    'sprout': 'M12 22V12 M12 12C12 7 8 5 4 5c0 4 3 7 8 7z M12 10c0-4 3-6 7-6 0 4-3 6-7 6z',
    'sun': 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z M12 1v3 M12 20v3 M4.2 4.2l2.1 2.1 M17.7 17.7l2.1 2.1 M1 12h3 M20 12h3 M4.2 19.8l2.1-2.1 M17.7 6.3l2.1-2.1',
    'drop': 'M12 2s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13z',
    'paw': 'M12 13c-3 0-6 3-6 6 0 2 2 3 6 3s6-1 6-3c0-3-3-6-6-6z M5 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M19 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M9 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M15 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
    'heart': 'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z',
    'brain': 'M9 3a3 3 0 0 0-3 3 3 3 0 0 0-3 3c0 1.5.8 2.5 2 3-1 1-1 3 0 4a3 3 0 0 0 3 3h1V3z M15 3a3 3 0 0 1 3 3 3 3 0 0 1 3 3c0 1.5-.8 2.5-2 3 1 1 1 3 0 4a3 3 0 0 1-3 3h-1V3z',
    'eye': 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
    'scroll': 'M8 3h10a3 3 0 0 1 3 3v1h-4 M8 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-1H11v1a3 3 0 0 1-3 3 M9 9h6 M9 13h6',
    'flame': 'M12 22c4 0 7-3 7-7 0-5-5-8-5-13-3 2-5 5-5 8-1-1-2-2-2-4-2 2-2 5-2 9 0 4 3 7 7 7z',
    'clock': 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M12 6v6l4 2',
    'book': 'M4 4h6a3 3 0 0 1 3 3v14a2 2 0 0 0-2-2H4z M20 4h-4a3 3 0 0 0-3 3 M20 4v15h-7',
    'check': 'M20 6L9 17l-5-5',
    'bolt': 'M13 2L3 14h8l-1 8 10-12h-8z',
    'star': 'M12 2l3 7h7l-5.5 4.5L18.5 21 12 16.5 5.5 21l2-7.5L2 9h7z',
}

THEMES = {
    'financas': dict(words='dívida divida dinheiro cartão cartao finan invest crédito credito renda nome limpo serasa salário economia orçamento poupar', mode='dark',
                     accent='#2bd673', head='impact', glyph='$', icons=['wallet', 'card', 'chart', 'coin', 'message']),
    'plantas': dict(words='horta jardim planta vaso pomar cultivo semente flor orgân', mode='light', accent='#3f8f3a', head='serif', glyph='✿',
                    icons=['sprout', 'leaf', 'sun', 'drop', 'check']),
    'pets': dict(words='cão cao cachorro gato pet adestr filhote raça', mode='light', accent='#e0782b', head='impact', glyph='●',
                 icons=['paw', 'heart', 'clock', 'check', 'star']),
    'mente': dict(words='estoic ansied psicolog mente hábito habito produtiv foco medit emocional', mode='dark', accent='#8ab4ff', head='serif', glyph='·',
                  icons=['brain', 'eye', 'clock', 'bolt', 'book']),
    'historia': dict(words='históri histori arte pintur mistéri misteri mitolog segredo enigma antig', mode='dark', accent='#e02424', head='impact', glyph='✶',
                     icons=['eye', 'scroll', 'book', 'flame', 'star']),
    'culinaria': dict(words='receita air fryer cozinha culinár doce bolo comida', mode='light', accent='#d9481c', head='impact', glyph='✱',
                      icons=['flame', 'clock', 'check', 'book', 'heart']),
}
DEFAULT_THEME = dict(mode='dark', accent='#ffd84d', head='impact', glyph='★', icons=['book', 'check', 'bolt', 'star', 'clock'])


def theme_for(text, accent=None):
    text = text.lower()
    best, score = DEFAULT_THEME, 0
    for t in THEMES.values():
        n = sum(w in text for w in t['words'].split())
        if n > score:
            best, score = t, n
    out = dict(best)
    if accent and accent.lower() != '#ffd84d':  # a cor escolhida no canal manda
        out['accent'] = accent
    return out


def icon(name, size=28):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="{ICONS[name]}"/></svg>')


def rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, k):
    return '#%02x%02x%02x' % tuple(round(x * (1 - k) + y * k) for x, y in zip(rgb(a), rgb(b)))


def palette(theme):
    acc = theme['accent']
    if theme['mode'] == 'light':
        return dict(bg=mix('#f7f2e8', acc, .04), panel=mix('#fffdf7', acc, .03), line=mix('#e4dccb', acc, .1), text='#1c1a17',
                    muted='#655f55', cta_bg=acc, cta_fg='#ffffff', band_fg='#ffffff')
    return dict(bg=mix('#0f0f0f', acc, .05), panel=mix('#181818', acc, .06), line=mix('#2a2a2a', acc, .12), text='#f2ece2',
                muted='#aaa297', cta_bg='#f2ece2', cta_fg='#121212', band_fg='#111111')


def cover(path, title, channel, accent, subtitle='', mode='dark'):
    """Capa de livro com a cor e o modo (claro/escuro) do tema do canal."""
    W, H = 900, 1200
    base = '#141414' if mode == 'dark' else '#f3ecdd'
    ink = (235, 228, 216) if mode == 'dark' else (40, 36, 30)
    book = Image.new('RGB', (W, H), base)
    d = ImageDraw.Draw(book)
    acc = rgb(accent)
    for i, y in enumerate(range(140, 1000, 172)):
        k = 0.55 + 0.45 * (i % 2)
        shade = tuple(int(c * k + (255 if mode == 'light' else 0) * (1 - k) * .5) for c in acc)
        d.rectangle((0, y, W, y + 150), fill=shade)
    small = load_font(26, False)
    d.text((W // 2 + 20, 70), f'— {channel.upper()} —', font=small, fill=ink, anchor='mm')
    size = 120
    while size > 40:
        font = load_font(size)
        lines, line = [], ''
        for w in title.split():
            t = (line + ' ' + w).strip()
            if line and d.textlength(t, font=font) > W - 160:
                lines.append(line); line = w
            else:
                line = t
        lines.append(line)
        if len(lines) * size * 1.1 < 520 and max(d.textlength(x, font=font) for x in lines) <= W - 170:
            break
        size -= 6
    y = (H - len(lines) * size * 1.1) / 2
    d.rectangle((60, int(y - 40), W - 40, int(y + len(lines) * size * 1.1 + 30)), fill=base)
    for ln in lines:
        d.text((W // 2 + 20, y), ln, font=font, fill=acc, anchor='ma')
        y += size * 1.1
    if subtitle:
        d.text((W // 2 + 20, H - 80), subtitle[:60], font=small, fill=ink, anchor='mm')
    spine = Image.new('RGB', (46, H))
    sd = ImageDraw.Draw(spine)
    for x in range(46):
        v = 1 - abs(x - 30) / 30
        c = tuple(int(ch * (0.35 + 0.25 * v)) for ch in (rgb(base) if mode == 'light' else (60, 60, 60)))
        sd.line((x, 0, x, H), fill=c)
    book.paste(spine, (0, 0))
    bg = '#111111' if mode == 'dark' else mix('#f7f2e8', accent, .04)
    canvas = Image.new('RGB', (1100, 1400), bg)
    shadow = Image.new('L', (1100, 1400), 0)
    ImageDraw.Draw(shadow).rectangle((120, 130, 120 + W, 130 + H), fill=230 if mode == 'dark' else 120)
    canvas.paste((0, 0, 0), mask=shadow.filter(ImageFilter.GaussianBlur(45)))
    canvas.paste(book, (100, 100))
    canvas.save(path, quality=90)


CSS = """
:root{--bg:{{BG}};--panel:{{PANEL}};--line:{{LINE}};--text:{{TEXT}};--muted:{{MUTED}};--acc:{{ACC}};--cta-bg:{{CTABG}};--cta-fg:{{CTAFG}};--band-fg:{{BANDFG}};
--fs:clamp(16px,.94rem + .3vw,19px);--h2:clamp(40px,8vw + 12px,92px);--price:clamp(64px,16vw + 20px,140px);--gut:clamp(18px,5vw,40px)}
*{box-sizing:border-box}html{scroll-behavior:smooth;-webkit-text-size-adjust:100%;overflow-x:hidden}body{overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--text);font:400 var(--fs)/1.6 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:auto;padding:0 var(--gut)}section{padding:clamp(56px,9vw,110px) 0;border-top:1px solid var(--line)}section:first-of-type{border:0}
.kicker{color:var(--acc);letter-spacing:.3em;font-size:clamp(12px,.7rem + .2vw,14px);font-weight:700;text-transform:uppercase;margin:0 0 10px}
h2{font-family:{{HEADFONT}};line-height:{{HEADLH}};margin:0 0 18px;font-weight:{{HEADW}};font-size:var(--h2);{{TRANSFORM}};letter-spacing:{{HEADLS}};max-width:16ch}
.hl{color:var(--acc)}.serif{font-family:Fraunces,Georgia,serif;font-size:clamp(30px,4vw + 14px,58px);line-height:1.12;margin:26px 0 14px;font-weight:500}
p{color:var(--muted);margin:0 0 16px;max-width:62ch}.hero{padding-top:clamp(20px,4vw,60px)}.hero img{display:block;width:min(400px,84%);height:auto;margin:0 auto}
.cta{display:flex;justify-content:center;align-items:center;gap:10px;text-align:center;background:var(--cta-bg);color:var(--cta-fg);font-weight:800;letter-spacing:.12em;text-decoration:none;
padding:clamp(18px,3vw,24px) 16px;margin:26px 0 22px;text-transform:uppercase;font-size:clamp(15px,.8rem + .4vw,18px);border-radius:{{RADIUS}};transition:transform .15s,filter .15s}
.cta:hover{filter:brightness(1.06)}.cta:active{transform:scale(.98)}
.meta{letter-spacing:.22em;font-size:clamp(12px,.7rem + .2vw,14px);color:var(--muted);text-transform:uppercase}
.price{font-family:Anton,Impact,sans-serif;color:var(--acc);font-size:var(--price);line-height:1;{{GLOW}}}
.band{background:var(--acc);color:var(--band-fg);transform:rotate(-2deg);margin:clamp(24px,5vw,56px) -20px;overflow:hidden;white-space:nowrap;padding:clamp(10px,2vw,16px) 0}
.band div{display:inline-block;font-family:Anton,Impact,sans-serif;font-size:clamp(24px,4vw + 8px,44px);text-transform:uppercase;animation:roll 45s linear infinite}
@keyframes roll{to{transform:translateX(-50%)}}@media(prefers-reduced-motion:reduce){.band div{animation:none}}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:14px;margin-top:26px}
.step{background:var(--panel);border:1px solid var(--line);padding:clamp(16px,2.5vw,24px);border-radius:{{RADIUS}}}.step .ico{color:var(--acc);display:flex;justify-content:space-between;align-items:center}
.step .ico b{font-family:Anton,Impact,sans-serif;font-size:22px;font-weight:400;color:var(--muted)}.step strong{display:block;margin:12px 0 6px;font-size:1.05em}.step p{font-size:.9em;margin:0}
.sample{background:var(--panel);border:1px solid var(--line);padding:clamp(22px,4vw,40px);border-radius:{{RADIUS}};max-width:760px}.sample small{letter-spacing:.22em;color:var(--muted);text-transform:uppercase}
.sample h3{font-family:Fraunces,Georgia,serif;font-weight:500;font-size:clamp(26px,2.5vw + 14px,38px);line-height:1.15;margin:6px 0 10px}
.nav{display:flex;gap:10px;align-items:center;border-top:1px solid var(--line);margin-top:20px;padding-top:18px}
.nav button{width:52px;height:52px;background:none;border:1px solid var(--line);color:var(--text);font-size:20px;cursor:pointer;border-radius:{{RADIUS}}}.nav span{margin-left:auto;color:var(--muted)}
ol{list-style:none;padding:0;margin:36px 0 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));column-gap:48px}
ol li{display:flex;gap:18px;border-bottom:1px solid var(--line);padding:16px 0}ol li b{font-family:Anton,Impact,sans-serif;color:var(--acc);font-size:clamp(26px,2vw + 14px,34px);font-weight:400;min-width:46px;line-height:1.1}
ol li span{display:block;color:var(--muted);font-size:.88em}
details{border-bottom:1px solid var(--line);padding:clamp(18px,3vw,24px) 0;max-width:820px}summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;gap:16px;font-size:clamp(17px,.9rem + .5vw,21px)}
summary::-webkit-details-marker{display:none}summary:after{content:'+';color:var(--acc);font-size:1.4em;line-height:1}details[open] summary:after{content:'–'}details p{margin:12px 0 0}
.final{text-align:center}.final .wrap>*{margin-left:auto;margin-right:auto}.final h2{max-width:18ch}.final .cta{max-width:560px}
.guarantee{display:flex;gap:12px;align-items:center;justify-content:center;color:var(--muted)}.guarantee svg{flex:none;color:var(--acc)}
footer{color:var(--muted);opacity:.75;font-size:13px;text-align:center;padding:40px 20px 60px;border-top:1px solid var(--line)}
@media(min-width:900px){.hero .wrap{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:56px;align-items:center}.hero img{width:100%}.hero .serif{margin-top:0}}
"""


def styles(theme):
    pal = palette(theme)
    serif = theme['head'] == 'serif'
    css = CSS
    for k, v in {'BG': pal['bg'], 'PANEL': pal['panel'], 'LINE': pal['line'], 'TEXT': pal['text'], 'MUTED': pal['muted'], 'ACC': theme['accent'],
                 'CTABG': pal['cta_bg'], 'CTAFG': pal['cta_fg'], 'BANDFG': pal['band_fg'],
                 'HEADFONT': 'Fraunces,Georgia,serif' if serif else 'Anton,Impact,sans-serif', 'HEADLH': '1.05' if serif else '.98',
                 'HEADW': '600' if serif else '400', 'TRANSFORM': 'text-transform:none' if serif else 'text-transform:uppercase',
                 'HEADLS': '-.02em' if serif else '0', 'RADIUS': '14px' if theme['mode'] == 'light' else '0',
                 'GLOW': 'text-shadow:0 0 28px color-mix(in srgb,var(--acc) 50%,transparent)' if theme['mode'] == 'dark' else 'text-shadow:none'}.items():
        css = css.replace('{{' + k + '}}', v)
    return css


JS = """
const s=[...document.querySelectorAll('.sample-item')];let i=0;
function show(n){if(!s.length)return;i=(n+s.length)%s.length;s.forEach((e,k)=>e.hidden=k!==i);document.getElementById('pos').textContent='Trecho '+(i+1)+' de '+s.length;}
document.getElementById('prev')?.addEventListener('click',()=>show(i-1));document.getElementById('next')?.addEventListener('click',()=>show(i+1));show(0);
"""


def page(data, channel, accent, niche=''):
    d = data
    e = html.escape
    th = theme_for(' '.join([niche, channel, d['ebook_name'], d['hero_text']]), accent)
    buy = e(d['checkout'] or '#')
    price = e(d['price'])
    glyph = f' {th["glyph"]} '
    names = glyph.join(e(x['title']) for x in d['items'][:14]) or e(d['ebook_name'])
    icons = th['icons']
    steps = ''.join(f'<div class="step"><div class="ico">{icon(icons[k % len(icons)])}<b>{k + 1:02}</b></div><strong>{e(x["title"])}</strong><p>{e(x["text"])}</p></div>'
                    for k, x in enumerate(d['steps']))
    samples = ''.join(f'<div class="sample-item"><small>Trecho {k + 1} de {len(d["samples"])}</small><h3>{e(x["title"])}</h3><p>{e(x["text"])}</p></div>'
                      for k, x in enumerate(d['samples']))
    items = ''.join(f'<li><b>{k + 1:02}</b><div>{e(x["title"])}<span>{e(x["subtitle"])}</span></div></li>' for k, x in enumerate(d['items']))
    faq = ''.join(f'<details><summary>{e(x["q"])}</summary><p>{e(x["a"])}</p></details>' for x in d['faq'])
    shield = ('<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"/>'
              '<path d="M8.5 12l2.5 2.5 4.5-5"/></svg>')
    cta = f'<a class="cta" href="{buy}">{icon(icons[0], 22)}{e(d["cta"])}</a>'
    buy_block = f'{cta}<div class="meta">E-book em PDF · acesso imediato</div><div class="price">R$ {price}</div><p>{e(d["installments"])}</p>'
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{e(d['ebook_name'])} · {e(channel)}</title><meta name="description" content="{e(d['hero_text'])}"><meta name="theme-color" content="{palette(th)['bg']}">
<meta property="og:title" content="{e(d['ebook_name'])}"><meta property="og:description" content="{e(d['hero_text'])}"><meta property="og:image" content="capa.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;700;800&display=swap">
<style>{styles(th)}</style></head><body>
<section class="hero"><div class="wrap"><img src="capa.jpg" alt="Capa do e-book {e(d['ebook_name'])}" width="1100" height="1400">
<div><h1 class="serif">{e(d['hero_title'])}</h1><p>{e(d['hero_text'])}</p>{buy_block}</div></div></section>
<div class="band" aria-hidden="true"><div>{names}{glyph}{names}{glyph}</div></div>
<section><div class="wrap"><p class="kicker">{e(d['inside_kicker'])}</p><h2>{mark(d['inside_title'])}</h2><p>{e(d['inside_text'])}</p><div class="steps">{steps}</div></div></section>
{f'<section><div class="wrap"><p class="kicker">Experimente</p><h2>{mark(d["samples_title"])}</h2><div class="sample">{samples}<div class="nav"><button id="prev" aria-label="Trecho anterior">‹</button><button id="next" aria-label="Próximo trecho">›</button><span id="pos"></span></div></div></div></section>' if samples else ''}
<section><div class="wrap"><p class="kicker">{e(d['list_kicker'])}</p><h2>{mark(d['list_title'])}</h2><p>{e(d['list_text'])}</p><ol>{items}</ol></div></section>
{f'<section><div class="wrap"><p class="kicker">Dúvidas</p><h2>Antes de <span class="hl">comprar.</span></h2>{faq}</div></section>' if faq else ''}
<section class="final"><div class="wrap"><h2>{mark(d['final_title'])}</h2><p>{e(d['final_text'])}</p><p class="meta">Por apenas</p>
<div class="price">R$ {price}</div><p>{e(d['installments'])} · acesso imediato ao PDF</p>{cta}
{f'<p class="guarantee">{shield}Garantia de {d["guarantee_days"]} dias: se não gostar, seu dinheiro volta.</p>' if d['guarantee_days'] else ''}</div></section>
<footer>{e(channel)} · {e(d['ebook_name'])}<br>Conteúdo educativo. Os resultados dependem de cada pessoa.</footer>
<script>{JS}</script></body></html>"""


def build(folder, data, channel, accent, niche=''):
    folder.mkdir(parents=True, exist_ok=True)
    th = theme_for(' '.join([niche, channel, data['ebook_name'], data['hero_text']]), accent)
    if not (folder / 'capa-enviada.jpg').is_file():
        n = len(data['items'])
        cover(folder / 'capa.jpg', data['ebook_name'], channel, th['accent'], f'{n} capítulos · guia prático' if n else '', th['mode'])
    else:
        (folder / 'capa.jpg').write_bytes((folder / 'capa-enviada.jpg').read_bytes())
    (folder / 'index.html').write_text(page(data, channel, accent, niche), 'utf-8')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(folder / 'index.html', 'index.html')
        z.write(folder / 'capa.jpg', 'capa.jpg')
    (folder / 'site.zip').write_bytes(out.getvalue())
