"""Piloto automático: roteiro com Gemini (grátis), login do YouTube (OAuth) e envio de vídeos.

Nada aqui guarda segredo em texto puro: o app passa as chaves já lidas do
cofre do Windows. Este módulo só conversa com as APIs do Google.
"""
import json
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

GEMINI = 'https://generativelanguage.googleapis.com/v1beta'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
SCOPES = 'https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube'
_MODEL = {}


# ------------------------------------------------------------------ Gemini

def gemini_model(key):
    """Escolhe o modelo 'flash' mais novo disponível para a chave (os nomes mudam com o tempo)."""
    if key in _MODEL:
        return _MODEL[key]
    try:
        r = requests.get(f'{GEMINI}/models', params={'pageSize': 200}, headers={'x-goog-api-key': key}, timeout=20)
        r.raise_for_status()
        names = [m['name'].split('/', 1)[1] for m in r.json().get('models', [])
                 if 'generateContent' in m.get('supportedGenerationMethods', [])]
    except (requests.RequestException, ValueError, KeyError):
        names = []
    good = [n for n in names if 'flash' in n and not re.search(r'lite|image|tts|audio|live|exp|preview|thinking', n)]
    def version(n):
        nums = re.findall(r'\d+(?:\.\d+)?', n)
        return tuple(float(x) for x in nums[:2]) if nums else (0,)
    pick = sorted(good, key=version)[-1] if good else 'gemini-2.5-flash'
    _MODEL[key] = pick
    return pick


def gemini_json(prompt, key, retries=2):
    """Pede ao Gemini um JSON e devolve o objeto já validado como JSON."""
    model = gemini_model(key)
    body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0.8}}
    last = ''
    for attempt in range(retries + 1):
        try:
            r = requests.post(f'{GEMINI}/models/{model}:generateContent', json=body, headers={'x-goog-api-key': key}, timeout=180)
        except requests.RequestException as exc:
            last = f'Falha de conexão com o Gemini: {exc}'
            time.sleep(5)
            continue
        if r.status_code == 429:
            last = 'Limite grátis do Gemini atingido por agora. Tente mais tarde.'
            time.sleep(20)
            continue
        if not r.ok:
            try:
                msg = r.json()['error']['message']
            except Exception:
                msg = r.text[:300]
            raise ValueError(f'Gemini recusou o pedido: {msg[:300]}')
        try:
            text = ''.join(p.get('text', '') for p in r.json()['candidates'][0]['content']['parts'])
            text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
            return json.loads(text)
        except (KeyError, IndexError, ValueError):
            last = 'O Gemini devolveu um roteiro incompleto.'
    raise ValueError(last or 'Não foi possível gerar o roteiro.')


# ------------------------------------------------------------------ Groq (grátis, sem cartão)
GROQ = 'https://api.groq.com/openai/v1'
GROQ_PREFERRED = ('openai/gpt-oss-120b', 'llama-3.3-70b-versatile', 'moonshotai/kimi-k2-instruct', 'openai/gpt-oss-20b')


def groq_model(key):
    if ('groq', key) in _MODEL:
        return _MODEL[('groq', key)]
    try:
        r = requests.get(f'{GROQ}/models', headers={'Authorization': f'Bearer {key}'}, timeout=20)
        r.raise_for_status()
        ids = [m['id'] for m in r.json().get('data', []) if m.get('active', True)]
    except (requests.RequestException, ValueError, KeyError):
        ids = []
    pick = next((m for m in GROQ_PREFERRED if m in ids), None)
    if not pick:
        text_models = [m for m in ids if not re.search(r'whisper|tts|guard|vision|embed|audio', m)]
        pick = sorted(text_models, key=lambda m: [int(x) for x in re.findall(r'(\d+)b', m)] or [0])[-1] if text_models else GROQ_PREFERRED[0]
    _MODEL[('groq', key)] = pick
    return pick


def groq_json(prompt, key, retries=2):
    model = groq_model(key)
    body = {'model': model, 'temperature': 0.8, 'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': 'Você é roteirista de YouTube. Responda somente com JSON válido.'},
                         {'role': 'user', 'content': prompt}]}
    last = ''
    for attempt in range(retries + 1):
        try:
            r = requests.post(f'{GROQ}/chat/completions', json=body, headers={'Authorization': f'Bearer {key}'}, timeout=180)
        except requests.RequestException as exc:
            last = f'Falha de conexão com o Groq: {exc}'
            time.sleep(5)
            continue
        if r.status_code == 429:
            last = 'Limite grátis do Groq atingido por agora. Tente mais tarde.'
            time.sleep(30)
            continue
        if not r.ok:
            try:
                msg = r.json()['error']['message']
            except Exception:
                msg = r.text[:300]
            raise ValueError(f'Groq recusou o pedido: {msg[:300]}')
        try:
            text = r.json()['choices'][0]['message']['content']
            return json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip()))
        except (KeyError, IndexError, ValueError):
            last = 'O Groq devolveu um roteiro incompleto.'
    raise ValueError(last or 'Não foi possível gerar o roteiro.')


def script_json(prompt, keys):
    """Usa a IA que tiver chave: Groq primeiro (grátis), depois Gemini. Se uma falhar, tenta a outra."""
    errors = []
    for name, fn in (('groq', groq_json), ('gemini', gemini_json)):
        if keys.get(name):
            try:
                return fn(prompt, keys[name])
            except ValueError as exc:
                errors.append(str(exc))
    if not errors:
        raise ValueError('Falta uma chave de IA para o roteiro: Groq (grátis em console.groq.com/keys) ou Gemini.')
    raise ValueError(' | '.join(errors))


# ------------------------------------------------------------------ OAuth do YouTube

def client_info(path):
    """Lê o arquivo client_secret_*.json baixado do Google Cloud (tipo 'App para computador')."""
    data = json.loads(Path(path).read_text('utf-8'))
    info = data.get('installed') or data.get('web')
    if not info or not info.get('client_id'):
        raise ValueError('Arquivo inválido. Baixe o JSON do ID do cliente OAuth do tipo "App para computador".')
    return {'client_id': info['client_id'], 'client_secret': info.get('client_secret', '')}


def auth_link(client, redirect, state):
    return AUTH_URL + '?' + urlencode({'client_id': client['client_id'], 'redirect_uri': redirect, 'response_type': 'code',
                                       'scope': SCOPES, 'access_type': 'offline', 'prompt': 'consent select_account',
                                       'include_granted_scopes': 'true', 'state': state})


def exchange_code(client, code, redirect):
    r = requests.post(TOKEN_URL, data={'code': code, 'client_id': client['client_id'], 'client_secret': client['client_secret'],
                                       'redirect_uri': redirect, 'grant_type': 'authorization_code'}, timeout=30)
    if not r.ok:
        raise ValueError('O Google recusou a autorização: ' + r.text[:300])
    data = r.json()
    if not data.get('refresh_token'):
        raise ValueError('O Google não devolveu a autorização permanente. Remova o acesso em myaccount.google.com/permissions e conecte de novo.')
    return data


def access_token(client, refresh):
    r = requests.post(TOKEN_URL, data={'client_id': client['client_id'], 'client_secret': client['client_secret'],
                                       'refresh_token': refresh, 'grant_type': 'refresh_token'}, timeout=30)
    if not r.ok:
        raise ValueError('A conexão com o YouTube expirou. Clique em "Conectar ao YouTube" de novo.')
    return r.json()['access_token']


def my_channel(token):
    r = requests.get('https://www.googleapis.com/youtube/v3/channels', params={'part': 'snippet', 'mine': 'true'},
                     headers={'Authorization': f'Bearer {token}'}, timeout=30)
    r.raise_for_status()
    items = r.json().get('items', [])
    if not items:
        raise ValueError('Essa conta Google ainda não tem um canal no YouTube. Crie o canal e conecte de novo.')
    return {'id': items[0]['id'], 'title': items[0]['snippet']['title']}


# ------------------------------------------------------------------ envio

CATEGORY = {'ciencia': '28', 'historia': '27', 'financas': '27', 'mente': '27', 'plantas': '26', 'culinaria': '26', 'pets': '15'}


def upload_video(token, video_path, meta, privacy='private', publish_at=''):
    """Envio retomável do MP4. Devolve o id do vídeo e o status que o YouTube aplicou."""
    status = {'privacyStatus': privacy, 'selfDeclaredMadeForKids': False, 'embeddable': True}
    if publish_at and privacy == 'private':
        status['publishAt'] = publish_at  # agenda: privado até a data, depois público
    body = {'snippet': {'title': meta['title'][:100], 'description': meta['description'][:4900], 'tags': meta.get('tags', [])[:30],
                        'categoryId': meta.get('category', '27'), 'defaultLanguage': 'pt-BR', 'defaultAudioLanguage': 'pt-BR'},
            'status': status}
    size = Path(video_path).stat().st_size
    start = requests.post('https://www.googleapis.com/upload/youtube/v3/videos', params={'uploadType': 'resumable', 'part': 'snippet,status'},
                          headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=UTF-8',
                                   'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(size)},
                          data=json.dumps(body), timeout=60)
    if not start.ok:
        raise ValueError('O YouTube recusou o envio: ' + _error(start))
    location = start.headers['Location']
    with open(video_path, 'rb') as fh:
        done = requests.put(location, data=fh, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'video/mp4'}, timeout=3600)
    if not done.ok:
        raise ValueError('O envio do vídeo falhou: ' + _error(done))
    data = done.json()
    return {'id': data['id'], 'privacy': data.get('status', {}).get('privacyStatus', privacy), 'url': 'https://youtu.be/' + data['id']}


def set_thumbnail(token, video_id, image_path):
    with open(image_path, 'rb') as fh:
        r = requests.post('https://www.googleapis.com/upload/youtube/v3/thumbnails/set', params={'videoId': video_id},
                          headers={'Authorization': f'Bearer {token}', 'Content-Type': 'image/jpeg'}, data=fh, timeout=120)
    if not r.ok:
        return 'Thumbnail não aplicada (o canal precisa ter o telefone verificado no YouTube): ' + _error(r)
    return ''


def apply_branding(token, channel_id, banner_path, about, keywords=''):
    """Banner e descrição do canal. A foto de perfil a API do YouTube não permite trocar."""
    with open(banner_path, 'rb') as fh:
        r = requests.post('https://www.googleapis.com/upload/youtube/v3/channelBanners/insert',
                          headers={'Authorization': f'Bearer {token}', 'Content-Type': 'image/jpeg'}, data=fh, timeout=120)
    if not r.ok:
        raise ValueError('O YouTube recusou o banner: ' + _error(r))
    banner_url = r.json()['url']
    cur = requests.get('https://www.googleapis.com/youtube/v3/channels', params={'part': 'brandingSettings', 'id': channel_id},
                       headers={'Authorization': f'Bearer {token}'}, timeout=30).json()['items'][0]['brandingSettings']
    cur.setdefault('channel', {})['description'] = about[:1000]
    if keywords:
        cur['channel']['keywords'] = keywords[:500]
    cur.setdefault('image', {})['bannerExternalUrl'] = banner_url
    u = requests.put('https://www.googleapis.com/youtube/v3/channels', params={'part': 'brandingSettings'},
                     headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
                     data=json.dumps({'id': channel_id, 'brandingSettings': cur}), timeout=60)
    if not u.ok:
        raise ValueError('O YouTube recusou a descrição/banner: ' + _error(u))


def _error(response):
    try:
        e = response.json()['error']
        reason = (e.get('errors') or [{}])[0].get('reason', '')
        hints = {'quotaExceeded': 'cota diária do YouTube esgotada (um envio gasta cerca de 1.600 das 10.000 unidades).',
                 'uploadLimitExceeded': 'limite de envios do canal atingido por hoje.',
                 'forbidden': 'sem permissão; conecte o canal de novo.'}
        return hints.get(reason) or e.get('message', '')[:300]
    except Exception:
        return response.text[:300]


def new_state():
    return secrets.token_urlsafe(16)
