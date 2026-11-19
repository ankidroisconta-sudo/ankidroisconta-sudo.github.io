"""Ilustração de cenas e síntese local de narração."""
import hashlib
import html
import io
import math
import os
import random
import re
import wave
from functools import lru_cache
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps

HEADERS = {'User-Agent': 'EstudioLivre/1.0 (local video editor)'}
VOICE = 'pt_BR-faber-medium'
VOICE_ROOT = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/'
HTTP = 'https://commons.wikimedia.org/w/api.php'
FONT_CANDIDATES = {
    True: ('C:/Windows/Fonts/segoeuib.ttf', 'C:/Windows/Fonts/arialbd.ttf',
           '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
    False: ('C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/arial.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf'),
}

@lru_cache(maxsize=256)
def load_font(size, bold=True):
    """Fonte do sistema com alternativas, para nunca quebrar a renderização."""
    for path in FONT_CANDIDATES[bool(bold)]:
        if Path(path).is_file():
            try: return ImageFont.truetype(path, size)
            except OSError: continue
    return ImageFont.load_default(size=size)

def app_folder():
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_DATA_HOME') or str(Path.home()/'.local'/'share')
    return Path(base)/'EstudioLivre'

WORDS = set('uma uns das dos da do de um e com em o a os as por para como sobre que imagem foto fotografia mostre vista close plano fundo cena estilo realista cinematic shot of the an and in showing com foco diagrama lado essa esse esta este porque seu sua são se ao nos na no'.split())

@lru_cache(maxsize=1)
def neural_voice():
    from piper import PiperVoice
    folder = app_folder()/'vozes'
    folder.mkdir(parents=True, exist_ok=True)
    for suffix in ('.onnx.json', '.onnx'):
        path = folder/(VOICE+suffix)
        if not path.is_file():
            temporary = path.with_suffix(path.suffix+'.part')
            with requests.get(VOICE_ROOT+path.name, stream=True, timeout=(10, 90)) as response:
                response.raise_for_status()
                with temporary.open('wb') as handle:
                    for chunk in response.iter_content(512*1024):
                        handle.write(chunk)
            if temporary.stat().st_size < 1024: raise ValueError('Download da voz incompleto.')
            temporary.replace(path)
    return PiperVoice.load(folder/(VOICE+'.onnx'))

def narrate(text, target):
    voice = neural_voice()
    with wave.open(str(target), 'wb') as output:
        voice.synthesize_wav(text, output)
    with wave.open(str(target)) as check:
        if check.getnframes() == 0: raise ValueError('A voz neural não gerou áudio.')

def terms(text):
    return [word for word in re.findall(r"[^\W\d_]+", text.lower()) if len(word)>2 and word not in WORDS]

def queries(scene, title):
    visual = terms(scene.get('visual', ''))
    topic = terms(title)
    body = terms(scene['text'])
    if 'lua' in (topic+visual) and ('fases' in body or 'ilumina' in body):
        yield 'quarter moon lunar surface'
    candidates = [visual[:6], visual[:3], (topic[:1]+(visual or body)[1:3]), topic[:3], (visual or topic or body)[:1]]
    yield from dict.fromkeys(' '.join(words) for words in candidates if words)

def plain(text):
    return html.unescape(re.sub('<[^>]+>', '', text)).strip()

def find_photo(scene, title, target, used):
    for query in queries(scene,title):
        params=dict(action='query',format='json',generator='search',gsrsearch=query+' filetype:bitmap',
                    gsrnamespace=6,gsrlimit=10,prop='imageinfo',iiprop='url|size|extmetadata|mime',iiurlwidth=1280,
                    iiextmetadatafilter='Artist|LicenseShortName|LicenseUrl')
        try:
            response=requests.get(HTTP,params=params,headers=HEADERS,timeout=(6,15))
            response.raise_for_status()
            pages=response.json().get('query',{}).get('pages',{}).values()
        except (requests.RequestException,ValueError):
            continue
        for page in sorted(pages,key=lambda p:p.get('index',100)):
            info=page.get('imageinfo',[{}])[0]
            metadata=info.get('extmetadata',{})
            license_name=metadata.get('LicenseShortName',{}).get('value','')
            if not re.fullmatch(r'(?:Public domain|CC0(?: 1.0)?|CC BY(?:-SA)? [\d.]+)',license_name,re.I):
                continue
            if info.get('mime') not in ('image/jpeg','image/png','image/webp') or max(info.get('width',0),info.get('height',0))<650: continue
            origin=info['descriptionurl']
            if origin in used: continue
            author=plain(metadata.get('Artist',{}).get('value',''))
            if 'BY' in license_name.upper() and not author: continue
            for url in dict.fromkeys([info.get('thumburl'),info.get('url')]):
                if not url: continue
                try:
                    with requests.get(url,stream=True,headers=HEADERS,timeout=(6,12)) as r:
                        r.raise_for_status()
                        data=bytearray()
                        for part in r.iter_content(128*1024):
                            data.extend(part)
                            if len(data)>16*1024*1024: raise ValueError('Imagem muito grande')
                    with Image.open(io.BytesIO(data)) as src:
                        if src.width*src.height>48_000_000: continue
                        im=ImageOps.exif_transpose(src).convert('RGB')
                        im.thumbnail((2560,2560))
                        im.save(target,quality=94)
                except (requests.RequestException,OSError,ValueError,Image.DecompressionBombError):
                    continue
                used.add(origin)
                return {'obra':page['title'].removeprefix('File:'),'autor':author,'licença':license_name,
                        'licença_url':metadata.get('LicenseUrl',{}).get('value',''),'fonte':origin,
                        'edição':'Recorte, texto sobreposto e movimento de câmera'}
    raise ValueError('Nenhuma imagem reutilizável encontrada. Verifique a internet ou ajuste a referência visual desta cena.')

def phases(target, size):
    w,h=size
    im=Image.new('RGB',size,'#081526')
    d=ImageDraw.Draw(im)
    rng=random.Random(19)
    for _ in range(280):
        x,y=rng.randrange(w),rng.randrange(h)
        c=rng.randrange(45,125);d.point((x,y), fill=(c,c,c+20))
    vertical=h>w
    radius=int(min(w,h)*(.135 if not vertical else .175))
    names=['Nova','Quarto crescente','Cheia','Quarto minguante']
    ft=load_font(max(17,int(min(w,h)*.03)),False)
    for n,angle in enumerate([math.pi,math.pi/2,0,-math.pi/2]):
        cx=w*(.18+.213*n) if not vertical else w*(.28+.44*(n%2))
        cy=h*.39 if not vertical else h*(.22+.32*(n//2))
        for y in range(-radius,radius+1):
            for x in range(-radius,radius+1):
                z2=1-(x*x+y*y)/radius**2
                if z2<0:continue
                light=max(0,x/radius*math.sin(angle)+math.sqrt(z2)*math.cos(angle))
                c=int(27+(185+rng.randint(-12,12))*light**.48)
                d.point((int(cx)+x,int(cy)+y),fill=(c,c,min(255,c+5)))
        d.text((cx,cy+radius+15),names[n],font=ft,fill='#f3f3ee',anchor='mt')
    im.save(target,quality=96)

def illustrate(scene, title, target, size, used):
    text=(scene.get('visual','')+' '+scene['text']).lower()
    if 'lua' in (text+' '+title.lower()) and ('diagrama' in text or 'esquema' in text) and ('fase' in text or 'órbita lunar' in text):
        phases(target,size)
        return {'obra':'As quatro fases principais da Lua','fonte':'Ilustração produzida no Estúdio Livre'}
    return find_photo(scene,title,target,used)

