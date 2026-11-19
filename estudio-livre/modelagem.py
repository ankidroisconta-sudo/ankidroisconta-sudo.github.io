"""Análise de cortes e montagem com tempos definidos pela referência."""
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from midia import HEADERS, HTTP, load_font, plain, queries

ROOT = Path(__file__).resolve().parent


def execute(args, timeout=1800, binary=False):
    result = subprocess.run([str(a) for a in args], capture_output=True, timeout=timeout,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        raise ValueError('Falha no processamento de mídia: '+result.stderr.decode('utf8','replace')[-650:])
    return result.stdout if binary else result.stdout.decode('utf8','replace')


def probe(path):
    data=json.loads(execute(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_format','-of','json',path]))
    if not data.get('streams'): raise ValueError('O arquivo não contém vídeo.')
    s=data['streams'][0]
    width,height=int(s['width']),int(s['height'])
    if any(abs(float(t.get('rotation',0)))%180==90 for t in s.get('side_data_list',[])): width,height=height,width
    return width,height,float(s.get('duration') or data['format']['duration']),float(Fraction(s['avg_frame_rate'] or s['r_frame_rate']))


def reference_path(value, data):
    if re.fullmatch(r'arquivo:[a-f0-9]{32}\.(mp4|mkv|mov|webm)',value):
        file=data/'assets'/value.split(':')[1]
        if file.is_file():return file
        raise ValueError('Arquivo de referência ausente.')
    url=urlsplit(value)
    host=(url.hostname or '').lower()
    video_id=''
    if host in ('youtube.com','www.youtube.com','m.youtube.com'):
        video_id=parse_qs(url.query).get('v',[''])[0] if url.path=='/watch' else url.path.removeprefix('/shorts/')
    elif host=='youtu.be':video_id=url.path.strip('/')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{11}',video_id):raise ValueError('Use um link de vídeo do YouTube ou envie o arquivo de referência.')
    folder=data/'referencias';folder.mkdir(exist_ok=True)
    target=folder/(video_id+'.mp4')
    if not target.is_file():
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            pattern=str(Path(tmp)/'referencia.%(ext)s')
            execute([sys.executable,'-m','yt_dlp','--ignore-config','--no-playlist','--quiet','--no-warnings',
                     '-f','bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b[ext=mp4]/b','--remux-video','mp4',
                     '-o',pattern,'https://www.youtube.com/watch?v='+video_id],timeout=1800)
            found=sorted(Path(tmp).glob('referencia.*'))
            if not found:raise ValueError('Não foi possível baixar o vídeo do YouTube. Baixe-o e envie o arquivo pelo botão ao lado.')
            src=found[0]
            probe(src)
            if src.suffix.lower()!='.mp4':
                execute(['ffmpeg','-y','-v','error','-i',src,'-an','-c:v','libx264','-preset','veryfast','-crf','18',target])
            else:src.replace(target)
    return target


def analyze(path):
    w,h,duration,fps=probe(path)
    # Detect hard cuts at native frame timestamps. Measure intra-shot motion separately.
    lines=execute(['ffmpeg','-loglevel','error','-reinit_filter','0','-i',path,'-an','-vf',
        'scale=128:-2,format=yuv420p,scdet=threshold=8,metadata=mode=print:key=lavfi.scd.time:file=-','-f','null','-'])
    boundaries=[0.]
    for value in re.findall(r'lavfi.scd.time=([\d.]+)',lines):
        point=float(value)
        if boundaries[-1]+1/fps < point < duration-1/fps:boundaries.append(point)
    boundaries.append(duration)
    sw=64;sh=max(16,round(sw*h/w))
    raw=execute(['ffmpeg','-loglevel','error','-i',path,'-an','-vf',f'fps=3,scale={sw}:{sh},format=gray','-f','rawvideo','-'],binary=True)
    frames=np.frombuffer(raw,dtype=np.uint8).reshape((-1,sh,sw))
    shots=[]
    for start,end in zip(boundaries,boundaries[1:]):
        block=frames[math.ceil(start*3):max(math.ceil(start*3)+1,math.floor(end*3))]
        if not len(block):block=frames[-1:]
        if not len(block):raise ValueError('A referência é curta demais para medir o movimento.')
        sample=block[len(block)//2].astype(float)
        bg=float(np.median(sample[:max(1,sh//20),:]))
        # Identify a rectangular insert on a light editorial canvas.
        rect=[0.,0.,1.,1.]
        if bg>210:
            rows=np.mean(sample<bg-45,axis=1)>.74
            runs=re.findall('1+', ''.join('1' if v else '0' for v in rows))
            if runs:
                longest=max(runs,key=len); y=''.join('1' if v else '0' for v in rows).find(longest)
                if len(longest)>.28*sh and y>.10*sh:
                    cols=np.where(np.mean(sample[y:y+len(longest)]<bg-45,axis=0)>.62)[0]
                    if len(cols)>.5*sw:rect=[cols[0]/sw,y/sh,(cols[-1]+1)/sw,(y+len(longest))/sh]
        x0,y0,x1,y1=rect
        region=block[:,int(y0*sh):max(int(y0*sh)+1,int(y1*sh)),int(x0*sw):max(int(x0*sw)+1,int(x1*sw))]
        delta=np.mean(np.abs(np.diff(region.astype(np.int16),axis=0)),axis=(1,2)) if len(region)>1 else []
        kind='video' if len(delta)==0 or np.quantile(delta,.7)>.95 else 'imagem'
        shots.append(dict(inicio=start,fim=end,tipo=kind,quadro=list(map(float,rect))))
    return dict(largura=w,altura=h,fps=fps,duracao=duration,planos=shots)


def download(url,path):
    with requests.get(url,headers=HEADERS,stream=True,timeout=(8,35)) as r:
        r.raise_for_status()
        with path.open('wb') as out:
            for chunk in r.iter_content(256*1024):
                out.write(chunk)
                if out.tell()>250*1024**2:raise ValueError('Clipe acima de 250 MB.')


def archive_clip(scene,title,path,used,seconds):
    for query in queries(scene,title):
        words=re.findall(r'[^\W_]+',query)
        if not words:continue
        try:
            expression='mediatype:movies AND title:('+' AND '.join(words)+') AND licenseurl:[* TO *]'
            response=requests.get('https://archive.org/advancedsearch.php',params={'q':expression,'fl[]':['identifier','licenseurl','creator','title'],'rows':18,'output':'json'},headers=HEADERS,timeout=15)
            response.raise_for_status()
            docs=response.json()['response']['docs']
        except (KeyError,ValueError,requests.RequestException):continue
        for doc in docs:
            license_url=str(doc.get('licenseurl',''))
            if not re.fullmatch(r'https?://creativecommons\.org/(licenses/(by|by-sa)/[\d.]+(/[-\w]+)?|publicdomain/(zero|mark)/1\.0)/?',license_url):continue
            identifier=quote(doc['identifier'],safe='')
            origin='https://archive.org/details/'+identifier
            if origin in used or ('/licenses/' in license_url and not doc.get('creator')):continue
            try:
                meta=requests.get('https://archive.org/metadata/'+identifier,headers=HEADERS,timeout=15);meta.raise_for_status()
                files=[f for f in meta.json().get('files',[]) if f['name'].lower().endswith(('.mp4','.webm')) and 0<int(f.get('size') or 0)<250*1024**2]
                for f in sorted(files,key=lambda f:int(f['size'])):
                    media='https://archive.org/download/'+identifier+'/'+quote(f['name'])
                    download(media,path)
                    if probe(path)[2]+.05<min(seconds,4)*.6:continue
                    used.add(origin)
                    return path,dict(obra=doc['title'],autor=doc.get('creator',''),licença_url=license_url,fonte=origin,arquivo=media)
            except (OSError,ValueError,requests.RequestException):continue
    raise ValueError('Falta clipe reutilizável com duração suficiente. Ajuste as palavras da referência visual ou anexe um vídeo à cena.')


def stock_video(scene,title,folder,used,seconds):
    words=(scene.get('visual','')+' '+scene.get('text','')).lower()
    path=folder/'clipe-stock.mp4'
    nasa='https://svs.gsfc.nasa.gov/5319/'
    if re.search(r'\b(moon|lua|lunar)\b',words) and re.search(r'rota|gira|turntable',words):
        source='https://svs.gsfc.nasa.gov/vis/a000000/a005300/a005319/moon_turntable_720p30.mp4'
        cache=ROOT/'referencias'/'nasa-turntable-5319.mp4'
        cache.parent.mkdir(parents=True,exist_ok=True)
        if not cache.exists():
            download(source,path);probe(path);shutil.copyfile(path,cache)
        else:shutil.copyfile(cache,path)
        if probe(path)[2]>0:
            return path,dict(obra='Moon Essentials: Turntable',autor='Ernie Wright · NASA Scientific Visualization Studio',fonte=nasa,arquivo=source)
    for q in queries(scene,title):
        try:
            r=requests.get(HTTP,params=dict(action='query',format='json',generator='search',gsrnamespace=6,gsrlimit=12,
                gsrsearch=q+' filetype:video',prop='imageinfo',iiprop='url|mime|size|extmetadata',
                iiextmetadatafilter='Artist|LicenseShortName|LicenseUrl'),headers=HEADERS,timeout=15)
            r.raise_for_status();pages=r.json().get('query',{}).get('pages',{}).values()
        except requests.HTTPError as exc:
            if exc.response.status_code==429:break
            continue
        except (requests.RequestException,ValueError):continue
        for page in sorted(pages,key=lambda p:p.get('index',100)):
            info=page.get('imageinfo',[{}])[0];meta=info.get('extmetadata',{})
            license=meta.get('LicenseShortName',{}).get('value','')
            if not re.fullmatch(r'Public domain|CC0(?: 1.0)?|CC BY(?:-SA)? [\d.]+',license,re.I):continue
            if info.get('size',0)>250*1024**2 or not (info.get('mime','').startswith('video/') or info.get('mime')=='application/ogg' and info.get('width',0)>0):continue
            origin=info['descriptionurl'];author=plain(meta.get('Artist',{}).get('value',''))
            if origin in used or ('BY' in license and not author):continue
            try:
                download(info['url'],path)
                if probe(path)[2]+.05<min(seconds,4)*.6:continue
            except requests.HTTPError as exc:
                if exc.response.status_code==429:return archive_clip(scene,title,path,used,seconds)
                continue
            except (ValueError,OSError,requests.RequestException):continue
            used.add(origin)
            return path,dict(obra=page['title'],autor=author,licença=license,licença_url=meta.get('LicenseUrl',{}).get('value',''),fonte=origin)
    return archive_clip(scene,title,path,used,seconds)


def make_panel(path,size,rect,channel,text):
    w,h=size
    canvas=Image.new('RGB',size,'white');draw=ImageDraw.Draw(canvas)
    top=int(h*rect[1]);left=round(w*.06)
    for label,content,space,size_hint in [(True,channel,.28,.055),(False,text,.57,.061)]:
        if not content:continue
        for size_px in range(max(14,int(w*size_hint)),9,-1):
            font=load_font(size_px)
            lines=['']
            for word in content.split():
                if lines[-1] and draw.textlength(lines[-1]+' '+word,font=font)>w-2*left:lines.append('')
                lines[-1]=(lines[-1]+' '+word).strip()
            if len(lines)*size_px*1.22<top*space:break
        y=top*(.13 if label else .45)
        for line in lines:
            draw.text((left if label else w//2,y),line,font=font,fill='#141414',anchor='lt' if label else 'mt')
            y+=size_px*1.22
    canvas.save(path)


def make_shot(source,kind,shot,profile,dest,channel,text):
    w,h=profile['largura'],profile['altura']
    w-=w%2;h-=h%2
    fps=profile['fps']
    frames=max(1,round(shot['fim']*fps)-round(shot['inicio']*fps))
    args=['ffmpeg','-y','-v','error']
    if kind=='imagem':args+=['-loop','1','-framerate',str(fps)]
    else:args+=['-stream_loop','-1']  # clipes curtos repetem até preencher o plano
    args+=['-i',source]
    rect=shot['quadro'];x,y=round(rect[0]*w),round(rect[1]*h)
    iw=max(2,round((rect[2]-rect[0])*w/2)*2);ih=max(2,round((rect[3]-rect[1])*h/2)*2)
    scale=f'fps={fps},scale={iw}:{ih}:force_original_aspect_ratio=increase,crop={iw}:{ih},setsar=1'
    if rect!=[0,0,1,1]:
        canvas=dest.with_suffix('.png');make_panel(canvas,(w,h),rect,channel,text)
        args+=['-loop','1','-framerate',str(fps),'-i',canvas,'-filter_complex',f'[0:v]{scale}[insert];[1:v][insert]overlay={x}:{y}:shortest=1[v]','-map','[v]']
    else:args+=['-vf',scale]
    execute(args+['-an','-frames:v',frames,'-pix_fmt','yuv420p','-c:v','libx264','-preset','veryfast',dest])
    actual=probe(dest)[2]
    if actual+1.5/fps<frames/fps:raise ValueError('O clipe terminou antes do corte do modelo. Anexe um clipe mais longo.')

