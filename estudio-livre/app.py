"""Estúdio Livre: produção local, sem API paga de IA."""
import copy
import io
import json
import os
import queue
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
import wave
import zipfile
import edicao
import vendas
import modelagem as model
from midia import illustrate, load_font, narrate
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request, send_from_directory
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('STUDIO_DATA', ROOT / 'dados')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
STATE = DATA / 'estado.json'
LOCK = threading.RLock()
TASKS = queue.Queue()
TOKEN = secrets.token_urlsafe(32)
WINDOWS = os.name == 'nt'
NO_WINDOW = 0x08000000 if WINDOWS else 0
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
DEFAULT_TEMPLATE = {'id': 'documental', 'name': 'Documental claro', 'channel': 'Meu canal',
    'niche': 'Curiosidades e conhecimento', 'language': 'Português brasileiro',
    'instructions': 'Tom curioso, explicações claras e fatos verificáveis. Gancho inicial curto. Conclusão útil. Evitar promessas e repetição.',
    'minutes': 2, 'format': 'horizontal', 'resolution': 1080, 'voice': '', 'accent': '#ffd84d',
    'captions': 'dinamica', 'music': 'ambiente'}
SHORTS_TEMPLATE = dict(DEFAULT_TEMPLATE, id='shorts', name='Shorts vertical', minutes=0.75, format='vertical',
    instructions='Gancho nos 2 primeiros segundos. Frases curtas e diretas. Um fato surpreendente por cena. Final que conecta com o começo.')

def load_state():
    fresh = {'templates': [copy.deepcopy(DEFAULT_TEMPLATE), copy.deepcopy(SHORTS_TEMPLATE)], 'projects': [], 'jobs': []}
    if not STATE.exists(): return fresh
    try:
        data = json.loads(STATE.read_text('utf-8'))
    except (OSError, ValueError):
        STATE.replace(STATE.with_name(f'estado-corrompido-{int(time.time())}.json'))
        return fresh
    for key in fresh: data.setdefault(key, fresh[key])
    if not data['templates']: data['templates'] = fresh['templates']
    if not any(t.get('format') == 'vertical' for t in data['templates']): data['templates'].append(copy.deepcopy(SHORTS_TEMPLATE))
    return data
state = load_state()

def persist():
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(STATE)

with LOCK:
    for job in state['jobs']:
        if job['status'] in ('queued', 'running'):
            job.update(status='error', message='Produção interrompida ao fechar o aplicativo. Enfileire novamente.')
    persist()

def ident():
    return uuid.uuid4().hex

def find(kind, key):
    found = next((x for x in state[kind] if x['id'] == key), None)
    if not found:
        raise ValueError('Item não encontrado.')
    return found

def run(args, timeout=300):
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=timeout, creationflags=NO_WINDOW)
    if p.returncode:
        raise RuntimeError(p.stderr[-2200:] or p.stdout[-2200:] or 'Falha ao executar ferramenta local.')
    return p.stdout

@app.before_request
def local_only():
    if request.host.split(':')[0] not in ('127.0.0.1', 'localhost'):
        return jsonify(error='Acesso apenas local.'), 403
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('X-Studio-Token') != TOKEN:
        return jsonify(error='Reabra a página para atualizar a sessão local.'), 403

@app.errorhandler(Exception)
def error(exc):
    from werkzeug.exceptions import HTTPException
    code = exc.code if isinstance(exc, HTTPException) else 400
    return jsonify(error=str(exc)), code

@app.get('/')
def index():
    return render_template('index.html', token=TOKEN)

@app.get('/api/state')
def get_state():
    with LOCK:
        return jsonify(copy.deepcopy(state))

@app.get('/api/system')
def system():
    voices = []
    if WINDOWS:
      try:
        raw = run(['powershell.exe', '-NoProfile', '-Command',
          "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; @($s.GetInstalledVoices() | ForEach-Object { @{name=$_.VoiceInfo.Name; culture=$_.VoiceInfo.Culture.Name} }) | ConvertTo-Json -Compress; $s.Dispose()"])
        voices = json.loads(raw or '[]')
        if isinstance(voices, dict): voices = [voices]
      except Exception:
        voices = []
    return jsonify(ffmpeg=bool(shutil.which('ffmpeg') and shutil.which('ffprobe')), voices=voices, data=str(DATA))

def clean_template(d):
    result = {k: str(d.get(k, DEFAULT_TEMPLATE.get(k, '')))[:5000] for k in
              ('name', 'channel', 'niche', 'language', 'instructions', 'voice', 'ebook_name', 'ebook_pitch')}
    link = str(d.get('ebook_link', '')).strip()[:500]
    if link and not re.fullmatch(r'https?://[^\s<>"]+', link): raise ValueError('O link do e-book precisa começar com https://')
    result['ebook_link'] = link
    result['format'] = 'vertical' if d.get('format') == 'vertical' else 'horizontal'
    result['resolution'] = 1080 if int(d.get('resolution', 720)) == 1080 else 720
    result['minutes'] = max(0.2, min(60, float(d.get('minutes', 2))))
    result['captions'] = 'nenhuma' if d.get('captions') == 'nenhuma' else 'dinamica'
    result['music'] = 'nenhuma' if d.get('music') == 'nenhuma' else 'ambiente'
    result['accent'] = d.get('accent', '#ffd84d')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', result['accent']): raise ValueError('Cor inválida.')
    return result

@app.post('/api/templates')
def templates():
    d = request.get_json()
    item = clean_template(d)
    with LOCK:
        if d.get('id'):
            target = find('templates', d['id'])
            target.update(item)
        else:
            target = dict(item, id=ident())
            state['templates'].append(target)
        persist()
    return jsonify(target)

def clean_project(d, template_id):
    scenes = d.get('scenes', [])
    if not isinstance(scenes, list) or len(scenes) > 150: raise ValueError('Use até 150 cenas por vídeo.')
    out = []
    for s in scenes:
        if not isinstance(s, dict): raise ValueError('Cada cena deve ser um objeto JSON.')
        text = str(s.get('text', '')).strip()
        if not text or len(text) > 6000: raise ValueError('Cada cena precisa de texto com até 6.000 caracteres.')
        out.append({'text': text, 'caption': str(s.get('caption', ''))[:180],
                    'visual': str(s.get('visual', ''))[:2000], 'media': s.get('media') if s.get('media') in ('imagem','video','animacao') else 'auto', 'image': '', 'audio': '', 'video': ''})
    tags = d.get('tags', [])
    if isinstance(tags, str): tags = [s.strip() for s in tags.split(',') if s.strip()]
    return {'id': ident(), 'title': str(d.get('title', 'Vídeo sem título'))[:200],
        'description': str(d.get('description', ''))[:5000], 'tags': [str(t)[:100] for t in tags][:30],
        'thumbnail_text': str(d.get('thumbnail_text', d.get('title', 'Novo vídeo')))[:120],
        'reference': str(d.get('reference', ''))[:1500], 'template_id': template_id,
        'master': d.get('master') is True, 'scheduled': '', 'scenes': out, 'created': datetime.now(timezone.utc).isoformat()}

def sales_folder(tid):
    if not re.fullmatch(r'[\w-]{1,64}', tid): raise ValueError('Canal inválido.')
    return DATA / 'sites' / tid

def channel_videos(tid):
    ids = {p['id'] for p in state['projects'] if p['template_id'] == tid}
    return [j['title'] for j in state['jobs'] if j['status'] == 'done' and (j.get('template_id') == tid or j['project_id'] in ids)]

@app.post('/api/templates/<tid>/sales-prompt')
def sales_prompt(tid):
    with LOCK:
        t = find('templates', tid)
        return jsonify(prompt=vendas.prompt(t.get('channel') or t['name'], t.get('niche', ''), channel_videos(tid)))

@app.post('/api/templates/<tid>/sales')
def sales(tid):
    data = vendas.clean(request.get_json())
    with LOCK:
        t = find('templates', tid)
        t['sales'] = data
        if data['checkout'] and not t.get('ebook_link'): t['ebook_link'] = data['checkout']
        if not t.get('ebook_name'): t['ebook_name'] = data['ebook_name']
        persist()
        vendas.build(sales_folder(tid), data, t.get('channel') or t['name'], t.get('accent', '#ffd84d'), t.get('niche', ''))
    return jsonify(url=f'/canal/{tid}/pagina/')

@app.post('/api/templates/<tid>/sales-cover')
def sales_cover(tid):
    with LOCK:
        t = find('templates', tid)
        if not t.get('sales'): raise ValueError('Gere a página primeiro.')
        folder = sales_folder(tid); folder.mkdir(parents=True, exist_ok=True)
        picture = ImageOps.exif_transpose(Image.open(request.files['file'].stream)).convert('RGB')
        picture.thumbnail((1400, 1800)); picture.save(folder / 'capa-enviada.jpg', quality=92)
        vendas.build(folder, t['sales'], t.get('channel') or t['name'], t.get('accent', '#ffd84d'), t.get('niche', ''))
    return jsonify(ok=True)

@app.get('/canal/<tid>/pagina/')
@app.get('/canal/<tid>/pagina/<name>')
def sales_page(tid, name='index.html'):
    if name not in ('index.html', 'capa.jpg', 'site.zip'): return jsonify(error='Arquivo inválido.'), 404
    return send_from_directory(sales_folder(tid), name, as_attachment=name == 'site.zip')

@app.post('/api/projects')
def projects():
    d = request.get_json()
    with LOCK:
        find('templates', d['template_id'])
        items = d.get('items', [d])
        if not isinstance(items, list) or not 1 <= len(items) <= 50: raise ValueError('Importe de 1 a 50 vídeos por vez.')
        new = [clean_project(x, d['template_id']) for x in items]
        state['projects'].extend(new)
        persist()
    return jsonify(new)

@app.put('/api/projects/<pid>')
def update_project(pid):
    d = request.get_json()
    with LOCK:
        old = find('projects', pid)
        template_id = d.get('template_id', old['template_id'])
        find('templates', template_id)
        updated = clean_project(d, template_id)
        for idx, s in enumerate(updated['scenes']):
            if idx < len(old['scenes']):
                for key in ('image', 'audio','video'): s[key] = old['scenes'][idx].get(key, '')
        for key in ('title', 'description', 'tags', 'thumbnail_text', 'reference', 'master', 'template_id', 'scenes'):
            old[key] = updated[key]
        scheduled = str(d.get('scheduled', ''))
        if scheduled: datetime.fromisoformat(scheduled)
        old['scheduled'] = scheduled
        persist()
    return jsonify(old)

@app.delete('/api/projects/<pid>')
def delete_project(pid):
    with LOCK:
        find('projects', pid)
        state['projects'] = [p for p in state['projects'] if p['id'] != pid]
        persist()
    return jsonify(ok=True)

@app.post('/api/projects/<pid>/assets/<int:idx>/<kind>')
def asset(pid, idx, kind):
    if kind not in ('image', 'audio','video'): raise ValueError('Tipo de arquivo inválido.')
    with LOCK:
        project = find('projects', pid)
        if not 0 <= idx < len(project['scenes']): raise ValueError('Cena inválida.')
        folder = DATA / 'assets'
        folder.mkdir(exist_ok=True)
        uploaded = request.files['file']
        if kind == 'image':
            name = ident() + '.jpg'
            picture = ImageOps.exif_transpose(Image.open(uploaded.stream)).convert('RGB')
            picture.thumbnail((3840, 3840))
            picture.save(folder / name, quality=94)
        elif kind=='video':
            ext=Path(uploaded.filename).suffix.lower()
            if ext not in ('.mp4','.mov','.webm','.mkv'): raise ValueError('Envie MP4, MOV, MKV ou WebM.')
            name=ident()+ext
            uploaded.save(folder/name)
            model.probe(folder/name)
        else:
            ext = Path(uploaded.filename).suffix.lower()
            if ext not in ('.wav', '.mp3', '.m4a', '.ogg'): raise ValueError('Envie WAV, MP3, M4A ou OGG.')
            name = ident() + ext
            uploaded.save(folder / name)
        project['scenes'][idx][kind] = name
        persist()
    return jsonify(ok=True)

@app.post('/api/reference-file')
def reference_file():
    upload=request.files['file']
    ext=Path(upload.filename).suffix.lower()
    if ext not in ('.mp4','.webm','.mov','.mkv'):raise ValueError('Arquivo de referência inválido.')
    folder=DATA/'assets';folder.mkdir(exist_ok=True)
    path=folder/(ident()+ext)
    try:
        upload.save(path)
        model.probe(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return jsonify(reference='arquivo:'+path.name)

def reference_profile(ref):
    path=model.reference_path(ref,DATA)
    folder=DATA/'referencias';folder.mkdir(exist_ok=True)
    cached=folder/(path.stem+'-v2.json')
    if cached.exists():return path,json.loads(cached.read_text('utf8'))
    profile=model.analyze(path)
    tmp=cached.with_name(ident()+'.tmp');tmp.write_text(json.dumps(profile),'utf8');tmp.replace(cached)
    return path,profile

@app.post('/api/reference-plan')
def reference_plan():
    return jsonify(reference_profile(request.get_json()['reference'])[1])

@app.post('/api/prompt')
def prompt():
    d = request.get_json()
    with LOCK: t = copy.deepcopy(find('templates', d['template_id']))
    example = {'title': 'Título original', 'description': 'Descrição e fontes verificadas', 'tags': ['tema'],
               'thumbnail_text': 'Até seis palavras', 'scenes': [{'text': 'Narração completa desta cena.',
               'caption': 'Frase curta na tela', 'visual': 'city skyline at night, people walking street, aerial traffic'}]}
    guide='Divida a narração em cenas de 15 a 35 segundos.'
    minutes = t['minutes']
    model = d.get('inspiration') or {}
    inspiration = ''
    if model.get('title'):
        seconds = max(15, min(3600, int(model.get('seconds') or 0) or int(t['minutes'] * 60)))
        minutes = round(seconds / 60, 2)
        short = seconds <= 180
        guide = ('Formato Shorts vertical: gancho forte nos 2 primeiros segundos, frases curtas, cenas de 4 a 8 segundos, final que leva a assistir de novo.'
                 if short else 'Divida a narração em cenas de 10 a 30 segundos. Gancho forte nos primeiros 5 segundos e uma pergunta que só é respondida no final.')
        tags = ', '.join(str(x) for x in (model.get('tags') or [])[:12])
        inspiration = (f"\nVídeo viral usado como INSPIRAÇÃO (não copie): título '{str(model['title'])[:200]}', "
                       f"{seconds} segundos, cerca de {model.get('per_day', '?')} visualizações por dia"
                       + (f", tags: {tags}" if tags else '') + ". "
                       "Entenda por que o tema e o gancho atraem cliques e crie um vídeo ORIGINAL sobre o mesmo assunto: "
                       "outro título, outro ângulo, outros exemplos, outra ordem de ideias e frases próprias. "
                       "Não mencione o outro vídeo nem o outro canal. Traga algo que ele não traz (um dado novo, uma explicação melhor ou uma curiosidade extra).")
        if model.get('foreign'):
            inspiration += (" O vídeo de inspiração é de fora do Brasil e em outro idioma: NÃO traduza. Adapte o tema para o público brasileiro, "
                            "com exemplos, comparações, unidades (reais, quilômetros, °C) e referências que façam sentido no Brasil, "
                            "e confira se os fatos valem para cá.")
    if t.get('ebook_name'):
        inspiration += (f"\nO canal vende o e-book '{t['ebook_name']}'" + (f" ({t['ebook_pitch']})" if t.get('ebook_pitch') else '') +
                        ". O vídeo deve entregar valor real por si só e funcionar como uma amostra grátis do e-book. "
                        "Inclua uma chamada natural no meio (depois de um ponto alto, prometendo que o melhor ainda vem) e outra no final, "
                        "dizendo que o link está no comentário fixado. Não exagere nas promessas.")
    if d.get('reference'):
        _,profile=reference_profile(d['reference'])
        guide='Siga a ordem e os tempos do modelo. Duração total: '+str(round(profile['duracao'],2))+' segundos. Ignore a duração do molde do canal. Planos (segundos): '+json.dumps([(round(x['inicio'],2),round(x['fim'],2),x['tipo']) for x in profile['planos']],ensure_ascii=False)
    return jsonify(prompt=f'''Crie um roteiro ORIGINAL sobre: {str(d.get('idea', ''))[:4000]}.
Canal: {t['channel']}. Nicho: {t['niche']}. Idioma: {t['language']}.
Duração pretendida: {minutes} minutos, aproximadamente {round(minutes * 145)} palavras.{inspiration}
Orientações editoriais: {t['instructions']}
{guide} Não copie falas ou thumbnails de referências.
Não invente fatos, métricas ou fontes. Indique na descrição os fatos que ainda precisam de checagem.
Para cada cena escreva text (narração), caption (até 100 caracteres) e visual: 2 a 4 buscas curtas EM INGLÊS separadas por vírgula, cada uma descrevendo uma tomada diferente e concreta que existiria em banco de vídeos (ex.: 'chef cutting vegetables, steam rising from pan, close up spices'). Evite nomes próprios e conceitos abstratos no visual. Inclua media com valor video, imagem ou animacao (animacao = tipografia animada gerada por código, ideal para números, listas e conceitos abstratos; nesse caso coloque o número ou a ideia-chave no caption). Prefira video.
Crie também um título curioso e honesto (até 70 caracteres, sem clickbait enganoso), thumbnail_text com até 5 palavras e uma descrição com 2 a 3 frases e as fontes.
Retorne SOMENTE um objeto JSON válido neste formato, sem markdown:
{json.dumps(example, ensure_ascii=False)}''')

def youtube(endpoint, params, key):
    try:
        response = requests.get('https://www.googleapis.com/youtube/v3/' + endpoint,
                                params=params, headers={'X-Goog-Api-Key': key}, timeout=35)
    except requests.RequestException:
        raise ValueError('Falha de conexão com o YouTube. Confira a internet e tente novamente.') from None
    if not response.ok:
        # Não repassa URLs nem a chave; só o motivo informado pelo Google.
        try: reason = response.json()['error']['errors'][0].get('reason', '')
        except Exception: reason = ''
        hints = {'quotaExceeded': 'A cota grátis de hoje acabou. Ela renova à meia-noite do horário do Pacífico (por volta de 4h ou 5h no Brasil).',
                 'forbidden': 'A YouTube Data API v3 não está ativada no projeto desta chave, ou a chave está restrita a outra API. Ative em console.cloud.google.com/apis/library/youtube.googleapis.com.',
                 'accessNotConfigured': 'Ative a YouTube Data API v3 no projeto desta chave no Google Cloud.',
                 'keyInvalid': 'Chave inválida. Copie de novo em console.cloud.google.com/apis/credentials.',
                 'badRequest': 'Chave inválida ou consulta mal formada.'}
        raise ValueError('YouTube recusou a consulta. ' + hints.get(reason, f'Motivo: {reason or response.status_code}. Verifique a chave, a API ativada, as restrições e a cota.'))
    return response.json().get('items', [])

KEY_DIR = Path(os.environ.get('LOCALAPPDATA', DATA)) / 'EstudioLivre'
KEY_PATH = KEY_DIR / 'youtube.dpapi'
KEY_NAMES = ('youtube', 'pexels', 'pixabay')

def read_key(name):
    path = KEY_DIR / f'{name}.dpapi'
    return windows_secret(path.read_text('ascii'), decrypt=True) if WINDOWS and path.is_file() else ''

def windows_secret(value, decrypt=False):
    if not WINDOWS: raise ValueError('Salvar a chave criptografada só funciona no Windows. Cole a chave no campo a cada pesquisa.')
    operation = (
        "[Text.Encoding]::UTF8.GetString([Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($value),$null,'CurrentUser'))"
        if decrypt else
        "[Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect([Text.Encoding]::UTF8.GetBytes($value),$null,'CurrentUser'))"
    )
    result = subprocess.run(
        ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
         "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.Security; $value=[Console]::In.ReadToEnd();" + operation],
        input=value, capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW)
    if result.returncode or not result.stdout.strip():
        raise ValueError('O Windows não conseguiu acessar a credencial deste usuário.')
    return result.stdout.strip()

def stored_youtube_key():
    return windows_secret(KEY_PATH.read_text('ascii'), decrypt=True) if KEY_PATH.is_file() else ''

@app.get('/api/keys')
def list_keys():
    return jsonify({n: bool(os.environ.get(n.upper() + '_API_KEY') or (KEY_DIR / f'{n}.dpapi').is_file()) for n in KEY_NAMES})

@app.post('/api/youtube-key')
def store_youtube_key():
    d = request.get_json()
    name = d.get('name', 'youtube')
    if name not in KEY_NAMES: raise ValueError('Serviço desconhecido.')
    value = str(d.get('key', '')).strip()
    if not 20 <= len(value) <= 256 or not value.isascii() or not value.isprintable():
        raise ValueError('Chave inválida.')
    encrypted = windows_secret(value)
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK:
        target = KEY_DIR / f'{name}.dpapi'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(encrypted, 'ascii')
        temporary.replace(target)
    return jsonify(ok=True)

CACHE_TTL = 6 * 3600
SEARCH_CACHE = {}

def iso_seconds(value):
    m = re.fullmatch(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', value or '')
    if not m: return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se

def research_cached(params, run_query):
    """Guarda cada pesquisa por 6 horas (memória e disco) para economizar a cota grátis do YouTube."""
    key = json.dumps(params, sort_keys=True)
    path = DATA / 'pesquisas.json'
    if not SEARCH_CACHE and path.is_file():
        try: SEARCH_CACHE.update(json.loads(path.read_text('utf-8')))
        except ValueError: pass
    hit = SEARCH_CACHE.get(key)
    if hit and time.time() - hit['at'] < CACHE_TTL:
        return hit['results'], True
    results = run_query()
    SEARCH_CACHE[key] = {'at': time.time(), 'results': results}
    for k in [k for k, v in SEARCH_CACHE.items() if time.time() - v['at'] > CACHE_TTL]: SEARCH_CACHE.pop(k)
    with LOCK:
        tmp = path.with_suffix('.tmp'); tmp.write_text(json.dumps(SEARCH_CACHE, ensure_ascii=False), 'utf-8'); tmp.replace(path)
    return results, False

def enrich(videos, key):
    channel_ids = ','.join(set(x['snippet']['channelId'] for x in videos))
    channels = {}
    for i in range(0, len(channel_ids.split(',')), 50):
        part = ','.join(channel_ids.split(',')[i:i + 50])
        if part: channels.update({x['id']: x for x in youtube('channels', {'part': 'snippet,statistics', 'id': part}, key)})
    now = datetime.now(timezone.utc)
    out = []
    for v in videos:
        sn = v['snippet']; ch = channels.get(sn['channelId'], {})
        stat = ch.get('statistics', {}); vs = v.get('statistics', {})
        subs = None if stat.get('hiddenSubscriberCount') else int(stat.get('subscriberCount', 0))
        views = int(vs.get('viewCount', 0))
        published = datetime.fromisoformat(sn['publishedAt'].replace('Z', '+00:00'))
        age_days = max(1 / 24, (now - published).total_seconds() / 86400)
        seconds = iso_seconds(v.get('contentDetails', {}).get('duration'))
        likes = int(vs.get('likeCount', 0)); comments = int(vs.get('commentCount', 0))
        created = ch.get('snippet', {}).get('publishedAt', '')
        out.append({'id': v['id'], 'title': sn['title'], 'channel': sn['channelTitle'], 'channel_id': sn['channelId'],
            'views': views, 'subscribers': subs, 'score': round(views / subs, 2) if subs else None,
            'per_day': round(views / age_days), 'age_days': round(age_days, 1), 'seconds': seconds, 'short': 0 < seconds <= 180,
            'engagement': round(100 * (likes + comments) / views, 2) if views else 0,
            'published': sn['publishedAt'], 'channel_created': created,
            'channel_videos': int(stat.get('videoCount', 0) or 0),
            'tags': sn.get('tags', [])[:15], 'description': sn.get('description', '')[:400],
            'url': 'https://www.youtube.com/watch?v=' + v['id']})
    return out

@app.post('/api/research')
def research():
    d = request.get_json()
    key = str(d.get('key', '')).strip()
    if not key: key = stored_youtube_key() or os.environ.get('YOUTUBE_API_KEY', '')
    if not key: raise ValueError('Configure a chave do YouTube ou use a pesquisa manual.')
    mode = d.get('mode', 'videos') if d.get('mode') in ('videos', 'shorts', 'long', 'trending', 'channels') else 'videos'
    region = str(d.get('region', 'BR'))[:2].upper()
    if not re.fullmatch('[A-Z]{2}', region): region = 'BR'
    language = str(d.get('language', 'pt'))[:5]
    days = max(1, min(365, int(d.get('days', 30))))
    query = str(d.get('query', '')).strip()[:200]
    category = str(d.get('category', ''))
    if mode != 'trending' and not query: raise ValueError('Digite um nicho ou assunto.')
    params = dict(mode=mode, region=region, language=language, days=days, query=query, category=category)

    def run_query():
        if mode == 'trending':
            p = {'part': 'snippet,statistics,contentDetails', 'chart': 'mostPopular', 'regionCode': region, 'maxResults': 50}
            if re.fullmatch(r'\d{1,3}', category): p['videoCategoryId'] = category
            return enrich(youtube('videos', p, key), key)
        p = {'part': 'snippet', 'type': 'video', 'q': query, 'maxResults': 50, 'order': 'viewCount',
             'regionCode': region, 'relevanceLanguage': language,
             'publishedAfter': (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')}
        if mode == 'shorts': p['videoDuration'] = 'short'
        found = []
        for duration in (('medium', 'long') if mode == 'long' else (p.get('videoDuration'),)):
            if duration: p['videoDuration'] = duration
            found += [x['id']['videoId'] for x in youtube('search', p, key) if x.get('id', {}).get('videoId')]
        ids = list(dict.fromkeys(found))
        if not ids: return []
        videos = []
        for i in range(0, len(ids), 50):
            videos += youtube('videos', {'part': 'snippet,statistics,contentDetails', 'id': ','.join(ids[i:i + 50])}, key)
        return enrich(videos, key)

    results, cached = research_cached(params, run_query)
    months = max(1, min(120, int(d.get('channel_months', 12))))
    if mode == 'shorts':
        results = [r for r in results if r['short']]
    if mode == 'long':
        results = [r for r in results if r['seconds'] >= 480]
    # Remove resultados em escritas que não servem para adaptar (ex.: hindi), mesmo com região definida.
    results = [r for r in results if not re.search(r'[\u0900-\u0DFF\u0600-\u06FF\u0E00-\u0E7F]', r['title'])
               and not re.search(r'\b(hindi|urdu|bangla|tamil|telugu)\b', r['title'], re.I)]
    if mode == 'channels':
        limit = datetime.now(timezone.utc) - timedelta(days=30 * months)
        seen, unique = set(), []
        for r in sorted(results, key=lambda r: r['per_day'], reverse=True):
            created = r['channel_created']
            if created and datetime.fromisoformat(created.replace('Z', '+00:00')) >= limit and r['channel_id'] not in seen:
                unique.append(r); seen.add(r['channel_id'])
        results = unique
    try: max_subs = int(d.get('max_subs') or 0)
    except (TypeError, ValueError): max_subs = 0
    if max_subs > 0:  # canais pequenos: só quem mostra inscritos e está abaixo do limite
        results = [r for r in results if r['subscribers'] is not None and r['subscribers'] <= max_subs]
    order = d.get('sort', 'per_day')
    keyf = {'score': lambda r: r['score'] if r['score'] is not None else -1, 'views': lambda r: r['views'],
            'engagement': lambda r: r['engagement']}.get(order, lambda r: r['per_day'])
    results = sorted(results, key=keyf, reverse=True)
    return jsonify(results=results, cached=cached)

@app.post('/api/queue')
def enqueue():
    d = request.get_json()
    ids = d.get('ids', [])
    if not ids: raise ValueError('Selecione ao menos um vídeo.')
    if not shutil.which('ffmpeg'): raise ValueError('FFmpeg não encontrado. Veja o guia de instalação.')
    with LOCK:
        snapshots = []
        for pid in dict.fromkeys(ids):
            p = copy.deepcopy(find('projects', pid))
            if not p['scenes']: raise ValueError(f"Importe um roteiro em {p['title']} antes de produzir.")
            if any(j['project_id'] == pid and j['status'] in ('queued', 'running') for j in state['jobs']): continue
            t = copy.deepcopy(find('templates', p['template_id']))
            snapshots.append((p, t))
        jobs = []
        for p, t in snapshots:
            job = {'id': ident(), 'project_id': p['id'], 'template_id': t['id'], 'title': p['title'], 'status': 'queued',
                   'message': 'Na fila', 'progress': 0, 'created': datetime.now(timezone.utc).isoformat()}
            state['jobs'].append(job); jobs.append((job['id'], p, t))
        persist()
        for task in jobs: TASKS.put(task)
    return jsonify(ok=True, added=len(jobs))

@app.post('/api/jobs/<jid>/cancel')
def cancel(jid):
    with LOCK:
        j = find('jobs', jid)
        if j['status'] not in ('queued', 'running'): raise ValueError('Este trabalho já terminou.')
        j.update(status='cancelled', message='Cancelado. A etapa atual será encerrada antes de liberar a fila.')
        persist()
    return jsonify(ok=True)

@app.delete('/api/jobs/<jid>')
def delete_job(jid):
    with LOCK:
        j = find('jobs', jid)
        if j['status'] in ('queued', 'running'): raise ValueError('Cancele o trabalho antes de removê-lo.')
        state['jobs'] = [x for x in state['jobs'] if x['id'] != jid]
        persist()
    if re.fullmatch('[a-f0-9]{32}', jid): shutil.rmtree(DATA/'renders'/jid, ignore_errors=True)
    return jsonify(ok=True)

def progress(jid, amount, message):
    with LOCK:
        j = find('jobs', jid)
        if j['status'] == 'cancelled': raise InterruptedError('Cancelado')
        j.update(status='running', progress=amount, message=message)
        persist()

def font(size):
    return load_font(size)

def fit_text(draw, text, box_width, max_height, start_size):
    for size in range(start_size, 13, -2):
        ft = font(size); lines = []; line = ''
        # Split very long tokens to avoid overflowing imported captions.
        words = []
        for word in text.split():
            chunk = ''
            for letter in word:
                if chunk and draw.textlength(chunk + letter, font=ft) > box_width:
                    words.append(chunk); chunk = ''
                chunk += letter
            if chunk: words.append(chunk)
        for word in words:
            candidate = (line + ' ' + word).strip()
            if line and draw.textlength(candidate, font=ft) > box_width:
                lines.append(line); line = word
            else: line = candidate
        if line: lines.append(line)
        if len(lines) * int(size * 1.3) <= max_height: return lines, ft, int(size * 1.3)
    return lines, ft, int(size * 1.3)

def card(path, scene, title, size, accent, thumbnail=False, auto_picture=None, show_text=True):
    w, h = size
    source = auto_picture or DATA / 'assets' / scene.get('image', '')
    if source.is_file():
        with Image.open(source) as original:
            image = original.convert('RGB')
        im = ImageOps.fit(image, size)
        ratio = (image.width / image.height) / (w / h)
        if ratio < .87 or ratio > 1.15:
            im = ImageEnhance.Brightness(im.filter(ImageFilter.GaussianBlur(24))).enhance(.36)
            inset = ImageOps.contain(image, size)
            im.paste(inset, ((w-inset.width)//2,(h-inset.height)//2))
    else:
        im = Image.new('RGB', size, '#111e24')
        dd = ImageDraw.Draw(im)
        for y in range(h):
            dd.line((0, y, w, y), fill=(15 + int(9*y/h), 27 + int(14*y/h), 33 + int(18*y/h)))
        dd.ellipse((int(w*.45), -int(h*.4), int(w*1.3), int(h*.8)), outline=accent, width=max(2, w//400))
        dd.ellipse((-int(w*.4), int(h*.6), int(w*.4), int(h*1.3)), outline='#3b5360', width=2)
    im = im.convert('RGBA')
    shade = Image.new('RGBA', size)
    ds = ImageDraw.Draw(shade)
    for y in range(h): ds.line((0, y, w, y), fill=(0, 0, 0, int(205*(y/h)**3)))
    im = Image.alpha_composite(im, shade).convert('RGB')
    if not show_text:
        im.save(path, quality=95)
        return
    dd = ImageDraw.Draw(im)
    margin = int(w*.075)
    text = title if thumbnail else (scene.get('caption') or title)
    lines, ft, lineheight = fit_text(dd, text, w-2*margin, int(h*.45), int(w*(.066 if thumbnail else .052)))
    top = h - int(h*.11) - len(lines)*lineheight
    dd.rounded_rectangle((margin, top-26, margin+64, top-18), 4, fill=accent)
    for i, line in enumerate(lines): dd.text((margin, top+i*lineheight), line, font=ft, fill='white')
    im.save(path, quality=95)

def timestamp(seconds):
    ms = round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def pick_media(scene, kind, p, folder, used, shot, frame, n):
    """Escolhe a mídia do plano: anexo > clipe livre > foto livre > (falha → cartão)."""
    asset = scene.get('video' if kind == 'video' else 'image') or scene.get('image' if kind == 'video' else 'video')
    if asset and (DATA/'assets'/asset).is_file():
        is_video = Path(asset).suffix.lower() in ('.mp4', '.mov', '.webm', '.mkv')
        return DATA/'assets'/asset, {'fonte': 'Arquivo anexado à cena'}, 'video' if is_video else 'imagem'
    if kind == 'video':
        try:
            source, credit = model.stock_video(scene, p['title'], folder, used, shot['fim']-shot['inicio'])
            return source, credit, 'video'
        except Exception:
            pass  # sem clipe: tenta uma foto livre com movimento de câmera
    source = folder/f'visual-{n:04}.jpg'
    credit = illustrate(scene, p['title'], source, frame, used)
    return source, credit, 'imagem'

def render(jid, p, t):
    folder = DATA / 'renders' / jid
    folder.mkdir(parents=True, exist_ok=True)
    height = t['resolution']; width = height*16//9
    width += width % 2
    size = (height, width) if t['format'] == 'vertical' else (width, height)
    ffmpeg = shutil.which('ffmpeg')
    srt = []; offset = 0; chunks = []
    media_log = []; used = set(); cover = None
    ref=p.get('reference','').strip()
    if p.get('master') and not ref:raise ValueError('Selecione o vídeo-base para preservar a montagem.')
    profile=None
    if ref:
        progress(jid,0,'Analisando os cortes e o movimento da referência')
        ref_file,profile=reference_profile(ref)
    durations=[];speakers=[];voice_parts=[];spoken=[]
    for idx, scene in enumerate(p['scenes']):
        percent = round(idx/len(p['scenes'])*38)
        progress(jid, percent, f'Cena {idx+1}/{len(p["scenes"])} · gerando narração')
        wav = folder / f'audio-{idx:03}.wav'
        if scene.get('audio'):
            speaker = 'Áudio anexado'
            run([ffmpeg, '-y', '-i', str(DATA/'assets'/scene['audio']), '-vn', '-ar', '44100', '-ac', '1', str(wav)])
        else:
            neural = not t['voice'] and t.get('language','').lower().startswith(('portug','pt'))
            speaker = t['voice'] or 'Voz do Windows'
            if neural:
                try:
                    narrate(scene['text'],wav)
                    speaker = 'Piper · Faber (pt-BR)'
                except Exception:
                    neural = False
            if not neural:
                if not WINDOWS: raise ValueError('A voz neural não está disponível e a voz do Windows só funciona no Windows. Anexe um áudio à cena.')
                spec = folder / f'voz-{idx:03}.json'
                spec.write_text(json.dumps({'text': scene['text'], 'voice': t['voice']}, ensure_ascii=False), 'utf-8')
                run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT/'voz.ps1'),
                     '-InputFile', str(spec), '-OutputFile', str(wav)], timeout=900)
        speakers.append(speaker)
        with wave.open(str(wav)) as audio: duration = audio.getnframes()/audio.getframerate()
        if duration <= 0 or duration > 3600: raise ValueError('Duração de áudio inválida (máximo: 1 hora por cena).')
        standardized=folder/f'fala-{idx:03}.wav'
        run([ffmpeg,'-v','error','-y','-i',str(wav),'-af','loudnorm=I=-16:TP=-1.5:LRA=11','-ar','44100','-ac','1',str(standardized)])
        voice_parts.append(f"file '{standardized.name}'");spoken.append(standardized)
        durations.append(duration)
    total=sum(durations)
    if not ref:
        # Edição dinâmica: vários cortes por cena, movimento, transições, legenda animada e trilha.
        def fallback_card(path, scene, frame):
            card(path, scene, p['title'], frame, t['accent'], show_text=t.get('captions') == 'nenhuma')
        def step(amount, message): progress(jid, amount, message)
        starts, total, media_log, cover = edicao.montar(p, t, folder, spoken, durations, size, DATA, fallback_card, step)
        for i, s in enumerate(p['scenes']):
            srt.append(f'{i+1}\n{timestamp(starts[i])} --> {timestamp(starts[i]+durations[i])}\n{s["text"]}\n')
        for entry in media_log: entry['voz'] = speakers[entry['cena']-1]
        profile = dict(largura=size[0], altura=size[1], duracao=total, fps=edicao.FPS,
                       planos=[dict(inicio=e['inicio'], fim=e['fim'], tipo=e['tipo']) for e in media_log])
        return finish(jid, p, t, folder, srt, media_log, profile, cover, total)
    if not profile:
        shots=[];cursor=0
        for scene,duration in zip(p['scenes'],durations):
            kind=scene.get('media','auto')
            if kind=='auto':
                visual=scene.get('visual','').lower()
                kind='imagem' if scene.get('image') or any(k in visual for k in ('diagrama','mapa','retrato','fotografia','diagram','chart','documento','portrait','infogr')) else 'video'
                if scene.get('video'):kind='video'
            shots.append(dict(inicio=cursor,fim=cursor+duration,tipo=kind,quadro=[0,0,1,1]))
            cursor+=duration
        profile=dict(largura=size[0],altura=size[1],duracao=total,fps=30,planos=shots)
    target=profile['duracao'];ratio=total/target
    if ratio>1.65:raise ValueError(f'O roteiro falado tem {total:.1f}s para um modelo de {target:.1f}s. Encurte o texto para manter os cortes e uma voz natural.')
    # Small differences can be paced to the model. Short narrations leave breathing space.
    speed=max(1.0,ratio)
    for idx,duration in enumerate(durations):
        end=min(target,offset+duration/speed)
        srt.append(f'{idx+1}\n{timestamp(offset)} --> {timestamp(end)}\n{p["scenes"][idx]["text"]}\n')
        offset=end
    if p.get('master'):
        if not ref.startswith('arquivo:'):raise ValueError('Para preservar todos os quadros, envie o seu arquivo-base no editor.')
        timeline=ref_file
        media_log.append(dict(fonte='Montagem integral do arquivo-base',voz=', '.join(dict.fromkeys(speakers))))
    else:
        for n,shot in enumerate(profile['planos']):
            progress(jid,40+int(48*n/len(profile['planos'])),f"Plano {n+1}/{len(profile['planos'])} · {shot['tipo']}")
            elapsed=0;idx=len(durations)-1
            for k,dur in enumerate(durations):
                elapsed+=dur/speed
                if shot['inicio']+0.016<elapsed:idx=k;break
            if len(profile['planos'])==len(p['scenes']):idx=n
            scene=p['scenes'][idx];kind=shot['tipo']
            out=folder/f'parte-{n:04}.mp4'
            frame=(profile['largura'],profile['altura'])
            try:
                source,credit,kind=pick_media(scene,kind,p,folder,used,shot,frame,n)
                if cover is None:
                    cover=folder/'capa-base.jpg'
                    try:
                        if kind=='imagem':shutil.copyfile(source,cover)
                        else:run([ffmpeg,'-y','-v','error','-ss','1','-i',str(source),'-frames:v','1',str(cover)])
                    except Exception:cover=None
                if not ref and kind=='imagem':
                    picture=folder/f'cena-{n:04}.jpg'
                    card(picture,scene,p['title'],size,t['accent'],auto_picture=source)
                    source=picture
                model.make_shot(source,kind,shot,profile,out,t['channel'],scene.get('caption') or p['title'])
            except InterruptedError:raise
            except Exception as exc:
                # Último recurso: cartão gráfico gerado localmente, sem internet.
                try:
                    kind='imagem';source=folder/f'cartao-{n:04}.jpg'
                    card(source,scene,p['title'],frame,t['accent'])
                    credit={'fonte':'Cartão gráfico do Estúdio Livre','observação':'Mídia online indisponível: '+str(exc)[:200]}
                    model.make_shot(source,kind,shot,profile,out,t['channel'],scene.get('caption') or p['title'])
                except Exception as final:raise ValueError(f'Plano {n+1} ({shot["inicio"]:.1f}s–{shot["fim"]:.1f}s): {final}') from None
            chunks.append(f"file '{out.name}'")
            media_log.append(dict(plano=n+1,inicio=shot['inicio'],fim=shot['fim'],tipo=kind,voz=speakers[idx],**credit))
        concat=folder/'partes.txt';concat.write_text('\n'.join(chunks),'utf8')
        timeline=folder/'montagem.mp4'
        run([ffmpeg,'-y','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(timeline)],timeout=7200)
    progress(jid,93,'Sincronizando a narração com a montagem')
    voices=folder/'falas.txt';voices.write_text('\n'.join(voice_parts),'utf8')
    codec=run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name','-of','csv=p=0',str(timeline)]).strip()
    video_options=['-c:v','copy'] if codec in ('h264','hevc','av1') else ['-c:v','libx264','-crf','16','-preset','veryfast']
    run([ffmpeg,'-y','-i',str(timeline),'-f','concat','-safe','0','-i',str(voices),'-map','0:v:0','-map','1:a:0','-af',f'atempo={speed},apad','-t',str(target),*video_options,'-c:a','aac','-b:a','160k','-movflags','+faststart',str(folder/'video.mp4')],timeout=7200)
    if p.get('master'):
        cover=folder/'capa-base.jpg'
        run([ffmpeg,'-y','-v','error','-i',str(timeline),'-frames:v','1',str(cover)])
    if cover is not None and not Path(cover).is_file(): cover=None  # usa a imagem da cena 1 ou um cartão gráfico
    return finish(jid, p, t, folder, srt, media_log, profile, cover, target)

def finish(jid, p, t, folder, srt, media_log, profile, cover, offset):
    card(folder/'thumbnail.jpg',p['scenes'][0],p['thumbnail_text'],(1280,720),t['accent'],True,cover)
    (folder/'modelo.json').write_text(json.dumps(profile,indent=2,ensure_ascii=False),'utf8')
    (folder/'legendas.srt').write_text('\n'.join(srt), 'utf-8')
    (folder/'projeto.json').write_text(json.dumps({'project': p, 'template': t}, ensure_ascii=False, indent=2), 'utf-8')
    pinned = ''
    if t.get('ebook_name'):
        pinned = f"\nCOMENTÁRIO FIXADO\n📘 {t['ebook_name']}" + (f": {t['ebook_pitch']}" if t.get('ebook_pitch') else '') + (f"\n👉 {t['ebook_link']}" if t.get('ebook_link') else '\n👉 (coloque o link do e-book)') + "\n"
    (folder/'publicacao.txt').write_text(f"CANAL\n{t.get('channel') or t.get('name')}\n\nTÍTULO\n{p['title']}\n\nDESCRIÇÃO\n{p['description']}\n" + (f"\n{t['ebook_name']}: {t['ebook_link']}\n" if t.get('ebook_link') else '') + f"\nTAGS\n{', '.join(p['tags'])}\n{pinned}\nDATA PLANEJADA (não publicada automaticamente)\n{p['scheduled']}\n", 'utf-8')
    credits = '\n\n'.join('\n'.join(f'{k}: {v}' for k,v in entry.items() if v not in ('', None)) for entry in media_log)
    (folder/'creditos.txt').write_text(credits, 'utf-8')
    with (folder/'publicacao.txt').open('a',encoding='utf-8') as publication:
        publication.write('\nCRÉDITOS PARA A DESCRIÇÃO\n'+credits)
    with zipfile.ZipFile(folder/'pacote.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(folder/'creditos.txt','creditos.txt')
        bundle.write(folder/'modelo.json','modelo.json')
        for name in ('video.mp4', 'thumbnail.jpg', 'legendas.srt', 'projeto.json', 'publicacao.txt'):
            bundle.write(folder/name, name)
    progress(jid, 99, 'Concluindo')
    with LOCK:
        find('jobs', jid).update(status='done', progress=100, message=f'Pronto · {round(offset)} segundos', duration=offset)
        persist()
    cleanup(folder)

TEMPORARY = ('audio-*.wav', 'voz-*.json', 'cena-*.jpg', 'cartao-*.jpg', 'visual-*.jpg', 'parte-*.mp4', 'partes.txt', 'parte-*.png',
             'clipe-stock.mp4', 'montagem.mp4', 'fala-*.wav', 'falas.txt', 'capa-base.jpg')

def cleanup(folder):
    # Keep deliverables, remove generated intermediates only from this job's folder.
    for pattern in TEMPORARY + ('midia-*', 'quadro-*.jpg', 'montagem*.mp4', 'narracao.wav', 'trilha.m4a', 'legenda.ass', 'efeitos.wav'):
        for file in folder.glob(pattern):
            try: file.unlink()
            except OSError: pass

def worker():
    while True:
        jid, p, t = TASKS.get()
        try: render(jid, p, t)
        except InterruptedError: cleanup(DATA/'renders'/jid)
        except Exception as exc:
            with LOCK:
                try:
                    job = find('jobs', jid)
                    if job['status'] != 'cancelled': job.update(status='error', message=str(exc)[-2200:] or 'Falha inesperada.')
                    persist()
                except Exception: pass
            cleanup(DATA/'renders'/jid)
        finally: TASKS.task_done()

@app.get('/files/<jid>/<name>')
def files(jid, name):
    if not re.fullmatch('[a-f0-9]{32}', jid) or name not in ('video.mp4', 'thumbnail.jpg', 'legendas.srt', 'projeto.json', 'publicacao.txt', 'pacote.zip'):
        return jsonify(error='Arquivo inválido.'), 404
    return send_from_directory(DATA/'renders'/jid, name, as_attachment=request.args.get('download') == '1', conditional=True)

@app.get('/api/backup')
def backup():
    from flask import send_file
    out = io.BytesIO()
    with LOCK:
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('estado.json', json.dumps(state, ensure_ascii=False, indent=2))
            for file in (DATA/'assets').glob('*'): z.write(file, 'assets/'+file.name)
    out.seek(0)
    return send_file(out, mimetype='application/zip', as_attachment=True, download_name='backup-estudio.zip')

if __name__ == '__main__':
    threading.Thread(target=worker, daemon=True).start()
    port = int(os.environ.get('STUDIO_PORT', '8765'))
    print(f'Abra http://127.0.0.1:{port} — mantenha esta janela aberta durante a produção.', flush=True)
    app.run(host='127.0.0.1', port=port, debug=False, threaded=True)
