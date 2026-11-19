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


def cover(path, title, channel, accent, subtitle=''):
    """Capa de livro em perspectiva com a cor do canal."""
    W, H = 900, 1200
    book = Image.new('RGB', (W, H), '#141414')
    d = ImageDraw.Draw(book)
    acc = tuple(int(accent[i:i + 2], 16) for i in (1, 3, 5))
    for i, y in enumerate(range(140, 1000, 172)):
        shade = tuple(int(c * (0.55 + 0.45 * ((i % 2)))) for c in acc)
        d.rectangle((0, y, W, y + 150), fill=shade)
    d.rectangle((0, 0, 46, H), fill='#0b0b0b')
    small = load_font(26, False)
    d.text((W // 2, 70), f'— {channel.upper()} —', font=small, fill=(220, 210, 200), anchor='mm')
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
        if len(lines) * size * 1.1 < 520:
            break
        size -= 6
    y = (H - len(lines) * size * 1.1) / 2
    box = (60, int(y - 40), W - 40, int(y + len(lines) * size * 1.1 + 30))
    d.rectangle(box, fill='#101010')
    for ln in lines:
        d.text((W // 2 + 20, y), ln, font=font, fill=acc, anchor='ma')
        y += size * 1.1
    if subtitle:
        d.text((W // 2 + 20, H - 80), subtitle[:60], font=small, fill=(230, 225, 215), anchor='mm')
    # lombada com brilho e sombra no fundo
    spine = Image.new('RGB', (46, H), '#0b0b0b')
    sd = ImageDraw.Draw(spine)
    for x in range(46):
        v = int(14 + 26 * (1 - abs(x - 30) / 30))
        sd.line((x, 0, x, H), fill=(v, v, v))
    book.paste(spine, (0, 0))
    canvas = Image.new('RGB', (1100, 1400), '#111111')
    shadow = Image.new('L', (1100, 1400), 0)
    ImageDraw.Draw(shadow).rectangle((120, 130, 120 + W, 130 + H), fill=230)
    canvas.paste((0, 0, 0), mask=shadow.filter(ImageFilter.GaussianBlur(45)))
    canvas.paste(book, (100, 100))
    canvas.save(path, quality=90)


CSS = """
:root{--bg:#111;--panel:#181818;--line:#2a2a2a;--text:#f2ece2;--muted:#a9a196;--acc:ACCENT}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font:17px/1.6 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:760px;margin:auto;padding:0 20px}section{padding:72px 0;border-top:1px solid var(--line)}section:first-of-type{border:0}
.kicker{color:var(--acc);letter-spacing:.32em;font-size:13px;font-weight:700;text-transform:uppercase;margin:0 0 10px}
h1,h2,.big{font-family:Anton,Impact,sans-serif;text-transform:uppercase;line-height:.98;margin:0 0 18px;font-weight:400}h2{font-size:clamp(44px,12vw,78px)}
.hl{color:var(--acc)}.serif{font-family:Fraunces,Georgia,serif;font-size:clamp(34px,8vw,52px);line-height:1.12;margin:26px 0 14px;font-weight:500;text-transform:none}
p{color:var(--muted);margin:0 0 16px}.hero{text-align:left;padding-top:28px}.hero img{display:block;width:min(400px,86%);height:auto;margin:0 auto}
.cta{display:block;text-align:center;background:var(--text);color:#111;font-weight:800;letter-spacing:.14em;text-decoration:none;padding:24px 16px;margin:26px 0 22px;text-transform:uppercase;font-size:17px;transition:transform .15s}.cta:active{transform:scale(.98)}
.meta{letter-spacing:.24em;font-size:13px;color:var(--muted);text-transform:uppercase}.price{font-family:Anton,Impact,sans-serif;color:var(--acc);font-size:clamp(72px,22vw,128px);line-height:1;text-shadow:0 0 28px color-mix(in srgb,var(--acc) 55%,transparent)}
.band{background:var(--acc);color:#111;transform:rotate(-2.5deg);margin:40px -20px;overflow:hidden;white-space:nowrap;padding:14px 0}
.band div{display:inline-block;font-family:Anton,Impact,sans-serif;font-size:34px;text-transform:uppercase;animation:roll 40s linear infinite}@keyframes roll{to{transform:translateX(-50%)}}
.steps{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:26px}.step{background:var(--panel);border:1px solid var(--line);padding:18px}.step b{display:block;font-family:Anton,Impact,sans-serif;color:var(--acc);font-size:30px;font-weight:400}.step strong{display:block;margin:6px 0}.step p{font-size:15px;margin:0}
.sample{background:var(--panel);border:1px solid var(--line);padding:28px 26px}.sample small{letter-spacing:.24em;color:var(--muted);text-transform:uppercase}.sample h3{font-family:Fraunces,Georgia,serif;font-weight:500;font-size:32px;margin:6px 0 10px}
.nav{display:flex;gap:10px;align-items:center;border-top:1px solid var(--line);margin-top:20px;padding-top:18px}.nav button{width:52px;height:52px;background:none;border:1px solid var(--line);color:var(--text);font-size:20px;cursor:pointer}.nav span{margin-left:auto;color:var(--muted)}
ol{list-style:none;padding:0;margin:36px 0 0}ol li{display:flex;gap:18px;border-bottom:1px solid var(--line);padding:16px 0}ol li b{font-family:Anton,Impact,sans-serif;color:var(--acc);font-size:30px;font-weight:400;min-width:44px;line-height:1.1}ol li span{display:block;color:var(--muted);font-size:15px}
details{border-bottom:1px solid var(--line);padding:22px 0}summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;font-size:19px}summary::-webkit-details-marker{display:none}summary:after{content:'+';color:var(--acc);font-size:26px;line-height:1}details[open] summary:after{content:'–'}details p{margin:12px 0 0}
.final{text-align:center}.final h2{font-size:clamp(46px,13vw,84px)}.guarantee{display:flex;gap:12px;align-items:center;justify-content:center;color:var(--muted);font-size:16px}
.guarantee svg{flex:none;color:var(--acc)}footer{color:#6f6a63;font-size:13px;text-align:center;padding:40px 20px 60px;border-top:1px solid var(--line)}
@media(min-width:700px){.steps{grid-template-columns:repeat(4,1fr)}}
"""

JS = """
const s=[...document.querySelectorAll('.sample-item')];let i=0;
function show(n){if(!s.length)return;i=(n+s.length)%s.length;s.forEach((e,k)=>e.hidden=k!==i);document.getElementById('pos').textContent='Trecho '+(i+1)+' de '+s.length;}
document.getElementById('prev')?.addEventListener('click',()=>show(i-1));document.getElementById('next')?.addEventListener('click',()=>show(i+1));show(0);
"""


def page(data, channel, accent):
    d = data
    e = html.escape
    buy = e(d['checkout'] or '#')
    price = e(d['price'])
    names = ' ★ '.join(e(x['title']) for x in d['items'][:14]) or e(d['ebook_name'])
    steps = ''.join(f'<div class="step"><b>{k + 1:02}</b><strong>{e(x["title"])}</strong><p>{e(x["text"])}</p></div>'
                    for k, x in enumerate(d['steps']))
    samples = ''.join(f'<div class="sample-item"><small>Trecho {k + 1} de {len(d["samples"])}</small><h3>{e(x["title"])}</h3><p>{e(x["text"])}</p></div>'
                      for k, x in enumerate(d['samples']))
    items = ''.join(f'<li><b>{k + 1:02}</b><div>{e(x["title"])}<span>{e(x["subtitle"])}</span></div></li>' for k, x in enumerate(d['items']))
    faq = ''.join(f'<details><summary>{e(x["q"])}</summary><p>{e(x["a"])}</p></details>' for x in d['faq'])
    shield = ('<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"/>'
              '<path d="M8.5 12l2.5 2.5 4.5-5"/></svg>')
    buy_block = (f'<a class="cta" href="{buy}">{e(d["cta"])}</a><div class="meta">E-book em PDF · acesso imediato</div>'
                 f'<div class="price">R$ {price}</div><p>{e(d["installments"])}</p>')
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(d['ebook_name'])} · {e(channel)}</title><meta name="description" content="{e(d['hero_text'])}">
<meta property="og:title" content="{e(d['ebook_name'])}"><meta property="og:description" content="{e(d['hero_text'])}"><meta property="og:image" content="capa.jpg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Fraunces:opsz,wght@9..144,500&family=Inter:wght@400;700;800&display=swap">
<style>{CSS.replace('ACCENT', e(accent))}</style></head><body>
<section class="hero"><div class="wrap"><img src="capa.jpg" alt="Capa do e-book {e(d['ebook_name'])}" width="1100" height="1400">
<h1 class="serif">{e(d['hero_title'])}</h1><p>{e(d['hero_text'])}</p>{buy_block}</div></section>
<div class="band" aria-hidden="true"><div>{names} ★ {names} ★ </div></div>
<section><div class="wrap"><p class="kicker">{e(d['inside_kicker'])}</p><h2>{mark(d['inside_title'])}</h2><p>{e(d['inside_text'])}</p><div class="steps">{steps}</div></div></section>
{f'<section><div class="wrap"><p class="kicker">Experimente</p><h2>{mark(d["samples_title"])}</h2><div class="sample">{samples}<div class="nav"><button id="prev" aria-label="Trecho anterior">‹</button><button id="next" aria-label="Próximo trecho">›</button><span id="pos"></span></div></div></div></section>' if samples else ''}
<section><div class="wrap"><p class="kicker">{e(d['list_kicker'])}</p><h2>{mark(d['list_title'])}</h2><p>{e(d['list_text'])}</p><ol>{items}</ol></div></section>
{f'<section><div class="wrap"><p class="kicker">Dúvidas</p><h2>ANTES DE <span class="hl">COMPRAR.</span></h2>{faq}</div></section>' if faq else ''}
<section class="final"><div class="wrap"><h2>{mark(d['final_title'])}</h2><p>{e(d['final_text'])}</p><p class="meta">Por apenas</p>
<div class="price">R$ {price}</div><p>{e(d['installments'])} · acesso imediato ao PDF</p><a class="cta" href="{buy}">{e(d['cta'])}</a>
{f'<p class="guarantee">{shield}Garantia de {d["guarantee_days"]} dias: se não gostar, seu dinheiro volta.</p>' if d['guarantee_days'] else ''}</div></section>
<footer>{e(channel)} · {e(d['ebook_name'])}<br>Conteúdo educativo. Os resultados dependem de cada pessoa.</footer>
<script>{JS}</script></body></html>"""


def build(folder, data, channel, accent):
    folder.mkdir(parents=True, exist_ok=True)
    if not (folder / 'capa-enviada.jpg').is_file():
        n = len(data['items'])
        cover(folder / 'capa.jpg', data['ebook_name'], channel, accent, f'{n} capítulos · guia prático' if n else '')
    else:
        (folder / 'capa.jpg').write_bytes((folder / 'capa-enviada.jpg').read_bytes())
    (folder / 'index.html').write_text(page(data, channel, accent), 'utf-8')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(folder / 'index.html', 'index.html')
        z.write(folder / 'capa.jpg', 'capa.jpg')
    (folder / 'site.zip').write_bytes(out.getvalue())
