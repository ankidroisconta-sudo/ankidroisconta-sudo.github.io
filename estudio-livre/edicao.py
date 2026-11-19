"""Edição dinâmica para qualquer tema.

- vários cortes por cena (um plano novo a cada ~3,5 s);
- fotos ganham zoom e panorâmica (efeito Ken Burns), vídeos ganham trecho aleatório;
- transições suaves entre planos e correção de cor leve;
- legenda animada palavra por palavra na cor do molde;
- trilha ambiente gerada aqui mesmo (sem direitos autorais) que abaixa quando a voz fala.
"""
import math
import os
import random
import re
import subprocess
import wave
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

import acervo
import motion
from midia import queries as fallback_queries

SHOT = 3.6      # duração média de cada plano (s)
FADE = 0.3      # transição entre planos (s)
GAP = 0.35      # respiro entre cenas (s)
TAIL = 0.8      # final do vídeo (s)
FPS = 30
GRADE = 'eq=contrast=1.05:saturation=1.12:gamma=0.98,vignette=angle=PI/7'
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def ff(args, cwd=None, timeout=3600):
    p = subprocess.run([str(a) for a in args], capture_output=True, cwd=cwd, timeout=timeout, creationflags=NO_WINDOW)
    if p.returncode:
        raise RuntimeError('FFmpeg: ' + p.stderr.decode('utf8', 'replace')[-700:])
    return p.stdout.decode('utf8', 'replace')


def media_seconds(path):
    out = ff(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


# ------------------------------------------------------------------ planos

def prepare_still(src, size, dest):
    """Foto em 2x a resolução final (zoom sem serrilhado). Fotos com proporção muito
    diferente ficam inteiras sobre um fundo desfocado da própria foto."""
    w, h = size
    scale = 2 if max(w, h) <= 1280 else 1.5
    W, H = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
    ratio = (im.width / im.height) / (w / h)
    if 0.72 < ratio < 1.4:
        canvas = ImageOps.fit(im, (W, H), Image.LANCZOS)
    else:
        canvas = ImageEnhance.Brightness(ImageOps.fit(im, (W, H)).filter(ImageFilter.GaussianBlur(45))).enhance(0.45)
        fg = ImageOps.contain(im, (int(W * 0.94), int(H * 0.94)), Image.LANCZOS)
        canvas.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    canvas.save(dest, quality=92)
    return dest


def still_shot(src, size, seconds, seed, out):
    w, h = size
    n = max(2, round(seconds * FPS))
    rng = random.Random(seed)
    move = rng.choice(('in', 'out', 'left', 'right', 'in', 'up'))
    a = rng.uniform(0.10, 0.16)
    cx, cy = 'iw/2-(iw/zoom/2)', 'ih/2-(ih/zoom/2)'
    if move == 'in':
        z, x, y = f'1+{a:.3f}*on/{n}', cx, cy
    elif move == 'out':
        z, x, y = f'{1 + a:.3f}-{a:.3f}*on/{n}', cx, cy
    elif move == 'left':
        z, x, y = '1.12', f'(iw-iw/zoom)*(1-on/{n})', cy
    elif move == 'right':
        z, x, y = '1.12', f'(iw-iw/zoom)*on/{n}', cy
    else:
        z, x, y = '1.12', cx, f'(ih-ih/zoom)*(1-on/{n})'
    vf = f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={w}x{h}:fps={FPS},{GRADE},setsar=1,format=yuv420p"
    ff(['ffmpeg', '-y', '-v', 'error', '-i', src, '-vf', vf, '-frames:v', n, '-an',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', out])


def video_shot(src, size, seconds, seed, out):
    w, h = size
    total = media_seconds(src)
    rng = random.Random(seed)
    start = 0.0
    if total > seconds + 1.2:
        lo = min(max(0.6, total * 0.12), total - seconds - 0.2)
        hi = max(lo, min(total - seconds - 0.2, total * 0.85 - seconds))
        start = rng.uniform(lo, hi)
    vf = (f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},'
          f'fps={FPS},{GRADE},setsar=1,format=yuv420p')
    ff(['ffmpeg', '-y', '-v', 'error', '-ss', f'{start:.2f}', '-stream_loop', '-1', '-i', src, '-t', f'{seconds:.3f}',
        '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', out])


def join(files, visible, folder, name, last_extended):
    """Une planos com dissolve. Cada arquivo, menos o último, tem FADE a mais."""
    if len(files) == 1:
        return files[0]
    if len(files) > 24:  # em grupos, para não abrir dezenas de vídeos ao mesmo tempo
        groups, gvis = [], []
        for g in range(0, len(files), 24):
            part_last = g + 24 < len(files) or last_extended
            groups.append(join(files[g:g + 24], visible[g:g + 24], folder, f'{name}-g{g // 24}', part_last))
            gvis.append(sum(visible[g:g + 24]))
        return join(groups, gvis, folder, name, last_extended)
    inputs, chain, label, offset = [], [], '0:v', 0.0
    for i, f in enumerate(files):
        inputs += ['-i', Path(f).name]
    for k in range(1, len(files)):
        offset += visible[k - 1]
        nxt = f'v{k}'
        chain.append(f'[{label}][{k}:v]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[{nxt}]')
        label = nxt
    out = folder / f'{name}.mp4'
    ff(['ffmpeg', '-y', '-v', 'error', *inputs, '-filter_complex', ';'.join(chain), '-map', f'[{label}]',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out.name], cwd=folder)
    return out


# ------------------------------------------------------------------ legenda

def ass_time(t):
    cs = max(0, round(t * 100))
    return f'{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}'


def captions(scenes, starts, durations, size, accent, path):
    w, h = size
    vertical = h > w
    fs = round((w * 0.095) if vertical else (h * 0.085))
    margin_v = round(h * (0.26 if vertical else 0.09))
    bgr = accent[5:7] + accent[3:5] + accent[1:3]
    lines = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {w}', f'PlayResY: {h}', 'WrapStyle: 0',
             'ScaledBorderAndShadow: yes', '', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, '
             'Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             f'Style: Main,Arial Black,{fs},&H00{bgr.upper()},&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,'
             f'{max(3, fs // 9)},{max(2, fs // 16)},2,{round(w * .08)},{round(w * .08)},{margin_v},1',
             '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    per_line = 3 if vertical else 4
    for scene, start, spoken in zip(scenes, starts, durations):
        words = scene['text'].split()
        if not words:
            continue
        chunks, cur = [], []
        for word in words:
            cur.append(word)
            if len(cur) >= per_line or len(' '.join(cur)) > (18 if vertical else 26) or re.search(r'[.!?;:,]$', word):
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        weight = [sum(len(x) + 2 for x in c) for c in chunks]
        t = start
        for chunk, wgt in zip(chunks, weight):
            span = spoken * wgt / sum(weight)
            karaoke = ''
            for word in chunk:
                cs = max(1, round(span * 100 * (len(word) + 2) / wgt))
                safe = word.replace('{', '(').replace('}', ')').replace('\\', '/')
                karaoke += f'{{\\k{cs}}}{safe} '
            effect = '{\\fad(40,40)\\fscx88\\fscy88\\t(0,110,\\fscx100\\fscy100)}'
            lines.append(f'Dialogue: 0,{ass_time(t)},{ass_time(t + span)},Main,,0,0,0,,{effect}{karaoke.strip()}')
            t += span
    path.write_text('\n'.join(lines) + '\n', 'utf-8')


# ------------------------------------------------------------------ áudio

CHORDS = ((110.0, 130.81, 164.81), (87.31, 110.0, 130.81), (130.81, 164.81, 196.0), (98.0, 123.47, 146.83))


def music_expression():
    """Pad ambiente (Lá menor, Fá, Dó, Sol) com duas vozes que se revezam sem estalos."""
    def voice(shift):
        tt = f'(t+{shift})'
        idx = f'floor(mod({tt},32)/8)'
        notes = []
        for n in range(3):
            f = (f'if(eq({idx},0),{CHORDS[0][n]},if(eq({idx},1),{CHORDS[1][n]},'
                 f'if(eq({idx},2),{CHORDS[2][n]},{CHORDS[3][n]})))')
            notes.append(f'sin(2*PI*{f}*t)+0.35*sin(4*PI*{f}*t)+0.12*sin(6*PI*{f}*t)')
        env = f'pow(sin(PI*mod({tt},8)/8),2)'
        return f'{env}*({"+".join(notes)})'
    return f'0.09*({voice(0)}+{voice(4)})'


def soundtrack(narration, seconds, folder, with_music, effects=None):
    out = folder / 'trilha.m4a'
    if not with_music:
        if effects:
            ff(['ffmpeg', '-y', '-v', 'error', '-i', narration, '-i', effects, '-filter_complex',
                '[0:a]aresample=48000,aformat=channel_layouts=stereo[v];[1:a]volume=0.35[e];[v][e]amix=inputs=2:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=11[a]',
                '-map', '[a]', '-t', f'{seconds:.3f}', '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', out])
        else:
            ff(['ffmpeg', '-y', '-v', 'error', '-i', narration, '-af', 'loudnorm=I=-15:TP=-1.5:LRA=11', '-ar', '48000',
                '-c:a', 'aac', '-b:a', '192k', out])
        return out
    expr = music_expression()
    graph = (f"aevalsrc='{expr}':s=48000:d={seconds:.2f},lowpass=f=1400,"
             "aecho=0.8:0.55:280|470:0.22|0.15,volume=0.55,"
             f"afade=t=in:d=1.5,afade=t=out:st={max(0, seconds - 2.5):.2f}:d=2.5[m];"
             "[0:a]aresample=48000,asplit=2[v][sc];"
             "[m][sc]sidechaincompress=threshold=0.015:ratio=7:attack=30:release=500[md];"
             + ("[1:a]volume=0.35[e];[v][md][e]amix=inputs=3:normalize=0" if effects else "[v][md]amix=inputs=2:normalize=0")
             + ",loudnorm=I=-15:TP=-1.5:LRA=11[a]")
    extra = ['-i', effects] if effects else []
    ff(['ffmpeg', '-y', '-v', 'error', '-i', narration, *extra, '-filter_complex', graph, '-map', '[a]', '-t', f'{seconds:.3f}',
        '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', out])
    return out


def narration_track(wavs, lengths, path):
    """Junta as falas, cada uma seguida de silêncio até completar a duração da cena."""
    with wave.open(str(wavs[0])) as first:
        params = first.getparams()
    with wave.open(str(path), 'wb') as dst:
        dst.setparams(params)
        for wav, length in zip(wavs, lengths):
            with wave.open(str(wav)) as src:
                data = src.readframes(src.getnframes())
                frames = src.getnframes()
            dst.writeframes(data)
            missing = max(0, round(length * params.framerate) - frames)
            dst.writeframes(b'\x00' * missing * params.sampwidth * params.nchannels)


# ------------------------------------------------------------------ montagem

def scene_queries(scene, title):
    raw = [q.strip() for q in re.split(r'[,;|/\n]', scene.get('visual', '')) if len(q.strip()) > 2]
    found = list(dict.fromkeys(raw))
    for q in fallback_queries(scene, title):
        if q not in found:
            found.append(q)
    found = found[:5]
    # Buscas mais amplas (uma palavra) entram por último, para nunca ficar sem imagem.
    for q in list(found):
        for word in acervo.words(q):
            if len(word) > 3 and word not in found:
                found.append(word)
    return found[:9] or [title]


def montar(p, t, folder, wavs, durations, size, data_dir, card, progress):
    """Monta o vídeo final. Devolve (início de cada cena, duração total, créditos, capa)."""
    vertical = size[1] > size[0]
    lengths = [d + GAP for d in durations]
    lengths[-1] = durations[-1] + TAIL
    starts = [sum(lengths[:i]) for i in range(len(lengths))]
    total = sum(lengths)

    # 1. plano de cortes: cada cena vira 1..N planos de ~3,5 s com leve variação de ritmo
    plan = []
    rng = random.Random(p.get('id', 'x'))
    for i, length in enumerate(lengths):
        n = max(1, round(length / SHOT))
        weights = [rng.uniform(0.85, 1.15) for _ in range(n)]
        for k, wgt in enumerate(weights):
            plan.append(dict(scene=i, k=k, seconds=length * wgt / sum(weights)))

    used, files, visible, log, cover = set(), [], [], [], None
    events = [(s, 'whoosh') for s in starts[1:]]
    pools = {}
    blocked = set()
    downloaded = {}
    for n, shot in enumerate(plan):
        i = shot['scene']
        scene = p['scenes'][i]
        progress(40 + int(45 * n / len(plan)), f'Plano {n + 1}/{len(plan)} · cena {i + 1}')
        seconds = shot['seconds'] + (FADE if n < len(plan) - 1 else 0)
        out = folder / f'parte-{n:04}.mp4'
        source, kind, credit = None, None, None

        animated = scene.get('media') == 'animacao' or (shot['k'] == 0 and motion.find_number(scene.get('caption', '')))
        if animated:
            try:
                motion.render(scene, size, seconds, t.get('accent', '#ffd84d'), t.get('channel', ''), n, out)
                kind, credit = 'animacao', {'fonte': 'Animação gerada no Estúdio Livre'}
                if motion.find_number(scene.get('caption', '') + ' ' + scene.get('text', '')):
                    events.append((sum(visible) + 0.5, 'pop'))
                files.append(out)
                visible.append(shot['seconds'])
                log.append(dict(plano=n + 1, cena=i + 1, inicio=round(sum(visible[:-1]), 2), fim=round(sum(visible), 2), tipo=kind, **credit))
                continue
            except Exception:
                pass
        attached = scene.get('video') or scene.get('image')
        if attached and shot['k'] == 0 and (data_dir / 'assets' / attached).is_file():
            source = data_dir / 'assets' / attached
            kind = 'video' if source.suffix.lower() in ('.mp4', '.mov', '.webm', '.mkv') else 'imagem'
            credit = {'fonte': 'Arquivo anexado à cena'}
        if source is None:
            if i not in pools:
                pool = []
                need = sum(1 for s in plan if s['scene'] == i) + 2
                prefer = scene.get('media', 'auto')
                kinds = [False] if prefer == 'imagem' else [True, False]
                for want_video in kinds:  # vídeos primeiro, fotos sempre como reserva
                    found = 0
                    for q in scene_queries(scene, p['title']):
                        if found >= need:
                            break
                        new = acervo.search(q, vertical, want_video, used | {c['origin'] for c in pool})
                        pool += new
                        found += len(new)
                pools[i] = pool
            while pools[i] and source is None:
                cand = pools[i].pop(0)
                host = urlsplit(cand.get('url') or cand.get('manifest') or cand['origin']).hostname
                if host in blocked:
                    continue
                try:
                    got = acervo.fetch(cand, folder / f'midia-{n:04}')
                    if cand['kind'] == 'video' and (media_seconds(got) < 1.5 or acervo.chroma_or_blank(got)):
                        continue
                    source, kind, credit = got, cand['kind'], cand['credit']
                    used.add(cand['origin'])
                    downloaded.setdefault(i, []).append((source, kind, credit))
                except Exception as exc:
                    if '429' in str(exc) or '403' in str(exc):
                        blocked.add(host)  # acervo limitando downloads: tenta os outros
                    continue
        if source is None and downloaded.get(i):  # reaproveita mídia desta cena com outro movimento
            source, kind, credit = downloaded[i][n % len(downloaded[i])]
        if source is None:  # nada encontrado: cena animada gerada por código
            try:
                motion.render(scene, size, seconds, t.get('accent', '#ffd84d'), t.get('channel', ''), n, out)
                files.append(out)
                visible.append(shot['seconds'])
                log.append(dict(plano=n + 1, cena=i + 1, inicio=round(sum(visible[:-1]), 2), fim=round(sum(visible), 2),
                                tipo='animacao', fonte='Animação gerada no Estúdio Livre'))
                continue
            except Exception:
                source = folder / f'cartao-{n:04}.jpg'
                card(source, scene, size)
                kind, credit = 'imagem', {'fonte': 'Cartão gráfico do Estúdio Livre'}
        try:
            if kind == 'video':
                video_shot(source, size, seconds, n, out)
            else:
                still = prepare_still(source, size, folder / f'quadro-{n:04}.jpg')
                still_shot(still, size, seconds, n, out)
        except Exception as exc:
            source = folder / f'cartao-{n:04}.jpg'
            card(source, scene, size)
            kind, credit = 'imagem', {'fonte': 'Cartão gráfico do Estúdio Livre', 'observação': str(exc)[:160]}
            still_shot(prepare_still(source, size, folder / f'quadro-{n:04}.jpg'), size, seconds, n, out)
        if cover is None and credit.get('fonte') != 'Cartão gráfico do Estúdio Livre':
            cover = folder / 'capa-base.jpg'
            if kind == 'imagem':
                Image.open(source).convert('RGB').save(cover, quality=94)
            else:
                ff(['ffmpeg', '-y', '-v', 'error', '-ss', '1', '-i', source, '-frames:v', '1', cover])
        files.append(out)
        visible.append(shot['seconds'])
        log.append(dict(plano=n + 1, cena=i + 1, inicio=round(sum(visible[:-1]), 2), fim=round(sum(visible), 2), tipo=kind, **credit))

    progress(86, 'Unindo os planos com transições')
    timeline = join(files, visible, folder, 'montagem', False)

    progress(90, 'Legendas animadas, trilha e mixagem')
    narration = folder / 'narracao.wav'
    narration_track(wavs, lengths, narration)
    effects = motion.effects_track(events, total, folder / 'efeitos.wav') if t.get('effects', 'sim') != 'nao' else None
    audio = soundtrack(narration, total, folder, t.get('music', 'ambiente') != 'nenhuma', effects)
    vf = 'null'
    if t.get('captions', 'dinamica') != 'nenhuma':
        captions(p['scenes'], starts, durations, size, t.get('accent', '#b6ef62'), folder / 'legenda.ass')
        vf = 'ass=legenda.ass'
    ff(['ffmpeg', '-y', '-v', 'error', '-i', Path(timeline).name, '-i', audio.name, '-map', '0:v:0', '-map', '1:a:0',
        '-vf', vf, '-t', f'{total:.3f}', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
        '-c:a', 'copy', '-movflags', '+faststart', 'video.mp4'], cwd=folder)
    if cover is not None and not cover.is_file():
        cover = None
    return starts, total, log, cover
