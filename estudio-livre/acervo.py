"""Busca de vídeos e fotos de qualquer tema em acervos com licença livre.

Ordem: Pexels e Pixabay (se houver chave gratuita), Wikimedia Commons,
NASA (só quando o resultado combina com a busca) e Internet Archive.
Cada função devolve candidatos; o download acontece depois, um por plano.
"""
import io
import os
import re
from pathlib import Path

import requests
from PIL import Image, ImageOps

from midia import HEADERS, HTTP, plain

FREE_LICENSE = re.compile(r'Public domain|CC0(?: 1\.0)?|CC BY(?:-SA)? [\d.]+', re.I)
STOP = set('the a an of and in on with for to at by from into over under showing shot view close up closeup footage video image photo'.split())


def words(query):
    return [w for w in re.findall(r'[^\W\d_]+', query.lower()) if len(w) > 2 and w not in STOP]


def relevant(title, query):
    """Aceita resultados de acervos genéricos só se o título combina com a busca."""
    title = title.lower()
    wanted = words(query)
    hits = sum(w[:5] in title for w in wanted)
    return bool(wanted) and hits >= (len(wanted) if len(wanted) <= 2 else -(-2 * len(wanted) // 3))


def secret(name):
    """Chave gratuita do usuário: variável de ambiente ou arquivo protegido do Windows."""
    value = os.environ.get(name.upper() + '_API_KEY', '').strip()
    if value:
        return value
    try:
        from app import read_key  # import tardio para evitar ciclo
        return read_key(name)
    except Exception:
        return ''


# ---------------------------------------------------------------- provedores

def pexels(query, vertical, want_video):
    key = secret('pexels')
    if not key:
        return []
    orientation = 'portrait' if vertical else 'landscape'
    if want_video:
        r = requests.get('https://api.pexels.com/videos/search', headers={'Authorization': key, **HEADERS},
                         params={'query': query, 'per_page': 15, 'orientation': orientation, 'size': 'medium'}, timeout=20)
        r.raise_for_status()
        out = []
        for v in r.json().get('videos', []):
            files = [f for f in v.get('video_files', []) if f.get('file_type') == 'video/mp4' and f.get('width')]
            files = [f for f in files if min(f['width'], f['height']) <= 1080] or files
            if not files:
                continue
            best = max(files, key=lambda f: f['width'] * f['height'])
            out.append(dict(kind='video', url=best['link'], duration=v.get('duration', 0), origin=v['url'],
                            credit=dict(obra=v['url'], autor=v.get('user', {}).get('name', ''), licença='Licença Pexels',
                                        fonte=v['url'])))
        return out
    r = requests.get('https://api.pexels.com/v1/search', headers={'Authorization': key, **HEADERS},
                     params={'query': query, 'per_page': 15, 'orientation': orientation}, timeout=20)
    r.raise_for_status()
    return [dict(kind='imagem', url=p['src']['large2x'], origin=p['url'],
                 credit=dict(obra=p.get('alt') or p['url'], autor=p.get('photographer', ''), licença='Licença Pexels', fonte=p['url']))
            for p in r.json().get('photos', [])]


def pixabay(query, vertical, want_video):
    key = secret('pixabay')
    if not key:
        return []
    if want_video:
        r = requests.get('https://pixabay.com/api/videos/', headers=HEADERS,
                         params={'key': key, 'q': query[:100], 'per_page': 15, 'safesearch': 'true'}, timeout=20)
        r.raise_for_status()
        out = []
        for h in r.json().get('hits', []):
            sizes = h.get('videos', {})
            pick = next((sizes[s] for s in ('large', 'medium', 'small') if sizes.get(s, {}).get('url')), None)
            if pick:
                out.append(dict(kind='video', url=pick['url'], duration=h.get('duration', 0), origin=h['pageURL'],
                                credit=dict(obra=h['pageURL'], autor=h.get('user', ''), licença='Licença Pixabay', fonte=h['pageURL'])))
        return out
    r = requests.get('https://pixabay.com/api/', headers=HEADERS,
                     params={'key': key, 'q': query[:100], 'per_page': 15, 'image_type': 'photo', 'safesearch': 'true',
                             'orientation': 'vertical' if vertical else 'horizontal'}, timeout=20)
    r.raise_for_status()
    return [dict(kind='imagem', url=h['largeImageURL'], origin=h['pageURL'],
                 credit=dict(obra=h['pageURL'], autor=h.get('user', ''), licença='Licença Pixabay', fonte=h['pageURL']))
            for h in r.json().get('hits', [])]


def wikimedia(query, vertical, want_video):
    kind = 'filetype:video' if want_video else 'filetype:bitmap'
    r = requests.get(HTTP, headers=HEADERS, timeout=20, params=dict(
        action='query', format='json', generator='search', gsrsearch=f'{query} {kind}', gsrnamespace=6, gsrlimit=15,
        prop='videoinfo', viprop='url|size|mime|extmetadata|derivatives', viurlwidth=1920,
        viextmetadatafilter='Artist|LicenseShortName|LicenseUrl'))
    r.raise_for_status()
    out = []
    for page in sorted(r.json().get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99)):
        info = (page.get('videoinfo') or page.get('imageinfo') or [{}])[0]
        meta = info.get('extmetadata', {})
        lic = meta.get('LicenseShortName', {}).get('value', '')
        author = plain(meta.get('Artist', {}).get('value', ''))
        if not FREE_LICENSE.fullmatch(lic) or ('BY' in lic.upper() and not author):
            continue
        mime = info.get('mime', '')
        if want_video:
            if not (mime.startswith('video/') or mime == 'application/ogg') or info.get('size', 0) > 200 * 1024 ** 2:
                continue
            if min(info.get('width', 0), info.get('height', 0)) < 360:
                continue
            # Prefere a versão leve (até 1080p) gerada pela própria Wikimedia.
            options = [d for d in info.get('derivatives', []) if d.get('height', 0) and d['height'] <= 1080
                       and ('webm' in d.get('type', '') or 'mp4' in d.get('type', ''))]
            url = max(options, key=lambda d: d['height'])['src'] if options else info['url']
        else:
            if mime not in ('image/jpeg', 'image/png', 'image/webp') or max(info.get('width', 0), info.get('height', 0)) < 900:
                continue
            url = info.get('thumburl') or info['url']
        out.append(dict(kind='video' if want_video else 'imagem', url=url, origin=info['descriptionurl'],
                        duration=float(info.get('duration') or 0),
                        credit=dict(obra=page['title'].removeprefix('File:'), autor=author, licença=lic,
                                    licença_url=meta.get('LicenseUrl', {}).get('value', ''), fonte=info['descriptionurl'])))
    return out


def nasa(query, vertical, want_video):
    if want_video:
        return []  # vídeos da NASA costumam ter apresentador, logos e textos; as fotos são limpas
    r = requests.get('https://images-api.nasa.gov/search', headers=HEADERS, timeout=20,
                     params={'q': query, 'media_type': 'video' if want_video else 'image', 'page_size': 25})
    r.raise_for_status()
    out = []
    for item in r.json().get('collection', {}).get('items', []):
        data = (item.get('data') or [{}])[0]
        title = data.get('title', '')
        if not relevant(title + ' ' + ' '.join(data.get('keywords', [])), query):
            continue
        nid = data.get('nasa_id', '')
        origin = 'https://images.nasa.gov/details/' + nid
        if want_video:
            out.append(dict(kind='video', manifest=item.get('href'), origin=origin, url='',
                            credit=dict(obra=title, autor=data.get('center', 'NASA'), licença='Domínio público (NASA)', fonte=origin)))
        else:
            link = next((l['href'] for l in item.get('links', []) if l.get('render') == 'image'), '')
            if link:
                out.append(dict(kind='imagem', url=link.replace('~thumb', '~large').replace('~medium', '~large'), origin=origin,
                                credit=dict(obra=title, autor=data.get('center', 'NASA'), licença='Domínio público (NASA)', fonte=origin)))
    return out


def archive(query, vertical, want_video):
    if not want_video:
        return []
    terms = words(query)
    if not terms:
        return []
    expression = 'mediatype:movies AND title:(' + ' AND '.join(terms[:3]) + ') AND licenseurl:[* TO *]'
    r = requests.get('https://archive.org/advancedsearch.php', headers=HEADERS, timeout=20,
                     params={'q': expression, 'fl[]': ['identifier', 'licenseurl', 'creator', 'title'], 'rows': 10, 'output': 'json'})
    r.raise_for_status()
    out = []
    for doc in r.json().get('response', {}).get('docs', []):
        lic = str(doc.get('licenseurl', ''))
        if not re.fullmatch(r'https?://creativecommons\.org/(licenses/(by|by-sa)/[\d.]+(/[-\w]+)?|publicdomain/(zero|mark)/1\.0)/?', lic):
            continue
        origin = 'https://archive.org/details/' + doc['identifier']
        out.append(dict(kind='video', archive=doc['identifier'], url='', origin=origin,
                        credit=dict(obra=doc.get('title', ''), autor=doc.get('creator', ''), licença_url=lic, fonte=origin)))
    return out


PROVIDERS = (pexels, pixabay, wikimedia, nasa, archive)


def search(query, vertical, want_video, used, limit=8):
    """Junta candidatos de todos os acervos, sem repetir o que já foi usado."""
    found = []
    for provider in PROVIDERS:  # consulta todos: se um acervo bloquear downloads, sobram os outros
        try:
            fresh = [c for c in provider(query, vertical, want_video)
                     if c['origin'] not in used and all(c['origin'] != f['origin'] for f in found)]
            found += fresh[:limit]
        except (requests.RequestException, ValueError, KeyError):
            continue
    return found


# ---------------------------------------------------------------- download

def _download(url, path, limit):
    with requests.get(url, headers=HEADERS, stream=True, timeout=(10, 60)) as r:
        r.raise_for_status()
        size = 0
        with path.open('wb') as out:
            for chunk in r.iter_content(512 * 1024):
                size += len(chunk)
                if size > limit:
                    raise ValueError('Arquivo grande demais.')
                out.write(chunk)


def fetch(candidate, path):
    """Baixa um candidato. Devolve o caminho salvo (vídeo .mp4/.webm ou foto .jpg)."""
    if candidate['kind'] == 'imagem':
        with requests.get(candidate['url'], headers=HEADERS, timeout=(10, 40)) as r:
            r.raise_for_status()
            if len(r.content) > 25 * 1024 ** 2:
                raise ValueError('Imagem grande demais.')
            with Image.open(io.BytesIO(r.content)) as src:
                im = ImageOps.exif_transpose(src).convert('RGB')
        im.thumbnail((3840, 3840))
        target = path.with_suffix('.jpg')
        im.save(target, quality=93)
        return target
    url = candidate.get('url')
    if candidate.get('manifest'):
        files = requests.get(candidate['manifest'], headers=HEADERS, timeout=20).json()
        mp4 = [f for f in files if f.endswith('.mp4')]
        url = next((f for tag in ('~medium.mp4', '~orig.mp4', '~large.mp4') for f in mp4 if f.endswith(tag)), mp4[0] if mp4 else '')
        url = url.replace('http://', 'https://')
    if candidate.get('archive'):
        meta = requests.get('https://archive.org/metadata/' + candidate['archive'], headers=HEADERS, timeout=20).json()
        files = [f for f in meta.get('files', []) if f['name'].lower().endswith('.mp4') and 0 < int(f.get('size') or 0) < 200 * 1024 ** 2]
        if files:
            url = 'https://archive.org/download/' + candidate['archive'] + '/' + requests.utils.quote(max(files, key=lambda f: int(f['size']))['name'])
    if not url:
        raise ValueError('Sem arquivo de vídeo.')
    target = path.with_suffix(Path(url.split('?')[0]).suffix.lower() if Path(url.split('?')[0]).suffix.lower() in ('.mp4', '.webm', '.ogv', '.mov') else '.mp4')
    _download(url, target, 200 * 1024 ** 2)
    candidate['credit'].setdefault('arquivo', url)
    return target
