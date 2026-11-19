// Armazenamento do navegador opcional: alguns navegadores/extensões bloqueiam e isso não pode travar o estúdio.
const store={get(k){try{return localStorage.getItem(k);}catch{return null;}},set(k,v){try{localStorage.setItem(k,v);}catch{}},del(k){try{localStorage.removeItem(k);}catch{}}};
function reportError(msg){
  try{fetch('/api/client-error?m='+encodeURIComponent(String(msg).slice(0,500)));}catch{}
  const box=document.getElementById('notice');if(box){box.textContent='Erro na página: '+msg;box.hidden=false;box.style.background='#b42318';box.style.color='#fff';}
}
window.addEventListener('error',e=>reportError((e.message||'erro')+' @'+(e.lineno||'?')));
window.addEventListener('unhandledrejection',e=>reportError(e.reason?.message||String(e.reason)));
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name=studio-token]').content;
const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
let state, selected, noticeTimer, inspiration=null, lastForeign=false, lastSearch=null;
function notify(text) {
  $("notice").textContent = text;
  $("notice").hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => $("notice").hidden = true, 7000);
}
async function api(path, data, method) {
  const headers = {'X-Studio-Token':token};
  const options = {method:method || (data ? 'POST':'GET'), headers};
  if (data instanceof FormData) options.body = data;
  else if (data) {headers['Content-Type']='application/json'; options.body=JSON.stringify(data);}
  let response;
  try { response = await fetch(path,options); }
  catch { throw Error('O estúdio está fechado. Abra Iniciar.cmd novamente.'); }
  let result = {};
  try { result = await response.json(); }
  catch { if(response.status===413) throw Error('Arquivo acima de 100 MB.'); }
  if(!response.ok) throw Error(result.error || 'Falha na operação ('+response.status+')');
  return result;
}
function action(fn) {
  return async event => {
    const control = event?.currentTarget;
    if(control?.tagName === 'BUTTON') control.disabled=true;
    try { await fn(event); } catch(error) { notify(error.message); }
    finally { if(control?.tagName === 'BUTTON') control.disabled=false; }
  };
}
function bind(id, fn){$(id).onclick=action(fn);}
function page(name) {
  document.querySelectorAll('main > section').forEach(s=>s.hidden=s.id!==name);
  document.querySelectorAll('nav button').forEach(b=>b.setAttribute('aria-current',String(b.dataset.page===name)));
}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>page(b.dataset.page));
async function refresh(){
  state=await api('/api/state');
  for(const select of document.querySelectorAll('.mold')){
    const previous=select.value;
    select.replaceChildren(...state.templates.map(t=>new Option(t.name,t.id)));
    if(state.templates.some(t=>t.id===previous))select.value=previous;
  }
  const current=state.templates.find(t=>t.id===$('editMold').value);if(current){showMoldCards();showChannelVideos(current);}
  $('library').innerHTML=state.projects.length?'':'<p>Seus roteiros salvos aparecerão aqui.</p>';
  for(const p of [...state.projects].reverse()){
    const row=document.createElement('div');row.className='item';
    row.innerHTML='<strong>'+safe(p.title)+'</strong><p>'+p.scenes.length+' cenas</p><div class="row"><button>Editar roteiro</button><button class="danger">Excluir</button></div>';
    const [edit,remove]=row.querySelectorAll('button');
    edit.onclick=()=>editor(p.id);
    remove.onclick=action(async()=>{
      if(!confirm('Excluir o roteiro “'+p.title+'”?'))return;
      await api('/api/projects/'+p.id,null,'DELETE');
      if(selected===p.id){selected=null;$('details').hidden=true;}
      await refresh();notify('Roteiro excluído.');
    });
    $('library').append(row);
  }
  showJobs();
}
function templateForm(){
  showMoldCards();
  const t=state.templates.find(t=>t.id===$('editMold').value);
  for(const input of $('moldForm').elements)if(input.name)input.value=t[input.name] ?? input.options?.[0]?.value ?? '';
  showChannelVideos(t);
}
function jobTemplate(j){return j.template_id||state.projects.find(p=>p.id===j.project_id)?.template_id;}
function showSales(t){
  const has=!!t.sales, base='/canal/'+t.id+'/pagina/';
  $('salesOpen').hidden=$('salesZip').hidden=!has;$('salesOpen').href=base;$('salesZip').href=base+'site.zip';
  $('salesStatus').textContent=has?('Página pronta: '+t.sales.ebook_name+' · R$ '+t.sales.price+'. Para editar, cole um JSON novo e gere de novo.'):'Gere a página do e-book deste canal: capa, promessa, preço, capítulos, trechos, dúvidas e garantia.';
  $('salesJson').value=has?JSON.stringify(t.sales,null,1):'';
}
function currentChannel(){return state.templates.find(t=>t.id===$('editMold').value);}
bind('salesPrompt',async()=>{const r=await api('/api/templates/'+currentChannel().id+'/sales-prompt',{});$('salesPromptText').value=r.prompt;$('salesPromptBox').hidden=false;});
bind('salesCopy',async()=>{await navigator.clipboard.writeText($('salesPromptText').value);notify('Prompt copiado.');});
bind('salesBuild',async()=>{
  const raw=$('salesJson').value.trim().replace(/^\x60\x60\x60(?:json)?\s*/i,'').replace(/\s*\x60\x60\x60$/,'');
  let data;try{data=JSON.parse(raw);}catch{throw Error('JSON incompleto. Copie a resposta inteira do chat.');}
  const r=await api('/api/templates/'+currentChannel().id+'/sales',data);await refresh();notify('Página gerada.');window.open(r.url,'_blank');
});
$('salesCover').onchange=action(async e=>{if(!e.target.files.length)return;const f=new FormData();f.append('file',e.target.files[0]);await api('/api/templates/'+currentChannel().id+'/sales-cover',f);notify('Capa atualizada.');});
async function connectYouTube(t){
  const r=await api('/api/templates/'+t.id+'/youtube/connect',{});window.open(r.url,'_blank');
  notify('Na aba do Google: escolha o canal “'+t.name+'” e clique em Permitir.');
  const until=Date.now()+300000;const tick=setInterval(async()=>{await refresh();const nt=state.templates.find(x=>x.id===t.id);
    if(nt?.youtube_channel||Date.now()>until){clearInterval(tick);if(nt?.youtube_channel)notify('Canal conectado: '+nt.youtube_channel.title);}},4000);
}
function showBrand(t){
  const box=$('brandBox');box.replaceChildren();
  const cta=document.createElement('div');cta.className='yt-cta';
  if(t.youtube_channel){cta.innerHTML='<span>✅ Conectado ao YouTube: <b>'+safe(t.youtube_channel.title)+'</b></span>';}
  else{cta.innerHTML='<span>Este canal ainda não está ligado ao YouTube.</span><button class="primary">Conectar ao YouTube</button>';cta.querySelector('button').onclick=action(()=>connectYouTube(t));}
  box.append(cta);
  const base='/canal/'+t.id+'/marca/', v='?v='+encodeURIComponent(t.name);
  const imgs=document.createElement('div');imgs.className='brand-imgs';
  imgs.innerHTML='<img class="brand-avatar" alt="Foto de perfil do canal"><img class="brand-banner" alt="Banner do canal">';
  imgs.querySelector('.brand-avatar').src=base+'perfil.jpg'+v;imgs.querySelector('.brand-banner').src=base+'banner.jpg'+v;
  const info=document.createElement('div');
  const src=t.source?.title?'<p>Inspirado em: '+safe(t.source.title)+(t.source.video_title?' · vídeo “'+safe(t.source.video_title)+'”':'')+'</p>':'';
  info.innerHTML='<p><strong>'+safe(t.name)+'</strong> · '+safe(t.niche||'')+'</p>'+src+(t.about?'<label>Texto do “Sobre” do canal<textarea readonly rows="3">'+safe(t.about)+'</textarea></label>':'')+'<div class="row"><a href="'+base+'perfil.jpg?download=1">Baixar foto de perfil</a><a href="'+base+'banner.jpg?download=1">Baixar banner</a><button id="renameChannel">Sugerir outro nome</button></div>';
  box.append(imgs,info);
  $('renameChannel').onclick=action(async()=>{await api('/api/templates/'+t.id+'/rename',{});await refresh();notify('Novo nome sugerido.');});
}
async function showPilot(t){
  const box=$('pilotBox');if(!box)return;
  let keys={};try{keys=await api('/api/keys');}catch{}
  const ap=t.autopilot||{}, yt=t.youtube_channel;
  box.innerHTML=`
  <div class="steps-list">
   <div class="${keys.groq||keys.gemini?'ok':'todo'}"><b>1. Roteiro automático (IA grátis)</b> ${keys.groq?'· Groq salvo':''}${keys.gemini?' · Gemini salvo':''}
     <p><b>Groq</b> (grátis, sem cartão): entre em <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer">console.groq.com/keys ↗</a> com sua conta Google, clique em <i>Create API Key</i> e cole aqui.</p>
     <div class="row"><input type="password" id="groqKey" placeholder="Chave do Groq (começa com gsk_)"><button id="saveGroq">Salvar</button></div>
     <p>Ou Gemini, se a sua conta tiver o plano gratuito da API: <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey ↗</a></p>
     <div class="row"><input type="password" id="geminiKey" placeholder="Chave do Gemini"><button id="saveGemini">Salvar</button></div></div>
   <div class="${keys.oauth_client?'ok':'todo'}"><b>2. Permissão de envio (uma vez só)</b> ${keys.oauth_client?'· arquivo salvo':''}
     <p>No Google Cloud: Tela de consentimento OAuth (Externo, adicione seu e-mail como usuário de teste) → Credenciais → Criar ID do cliente OAuth → <b>App para computador</b> → baixar JSON. Envie o arquivo:</p>
     <input type="file" id="oauthFile" accept=".json,application/json"></div>
   <div class="${yt?'ok':'todo'}"><b>3. Conectar este canal ao YouTube</b> ${yt?'· conectado a “'+safe(yt.title)+'”':''}
     <p>Crie o canal no YouTube (ex.: “${safe(t.name)}”) e clique abaixo. Na tela do Google, escolha esse canal.</p>
     <div class="row"><button id="ytConnect">${yt?'Reconectar':'Conectar ao YouTube'}</button>${yt?'<button id="ytBranding">Aplicar banner e descrição no YouTube</button>':''}</div></div>
  </div>
  <h3>Agenda</h3>
  <div class="row">
   <label><input type="checkbox" id="apOn" ${ap.enabled?'checked':''} style="width:auto;display:inline"> Piloto automático ligado</label>
   <label>Vídeos por semana<input type="number" id="apWeek" min="1" max="14" value="${ap.per_week||3}"></label>
   <label>Produzir às<input type="time" id="apTime" value="${ap.time||'09:00'}"></label>
  </div>
  <div class="row">
   <label>Ao terminar<select id="apPrivacy">
     <option value="none">Só produzir (não enviar)</option><option value="private">Enviar como privado</option>
     <option value="scheduled">Enviar e agendar publicação</option><option value="unlisted">Enviar como não listado</option><option value="public">Enviar e publicar</option></select></label>
   <label>Publicar às (se agendado)<input type="time" id="apPublish" value="${ap.publish_time||'18:00'}"></label>
  </div>
  <div class="row"><button class="primary" id="apSave">Salvar agenda</button><button id="apRun">Produzir o próximo vídeo agora</button><button id="apTopics">Ver próximos temas virais</button></div>
  <p class="hint">O piloto só trabalha com o estúdio aberto e o computador ligado. Projetos de API não verificados pelo Google: o YouTube deixa o vídeo privado; publique pelo YouTube Studio.</p>
  <div id="apTopicList"></div>
  <h3>Diário do piloto</h3><div id="apLog">${(ap.log||[]).slice().reverse().map(l=>'<p class="'+(l.error?'err':'')+'">'+safe(l.at.replace('T',' '))+' · '+safe(l.text)+(l.url?' <a target="_blank" rel="noreferrer" href="'+safe(l.url)+'">abrir ↗</a>':'')+'</p>').join('')||'<p>Nada ainda.</p>'}</div>`;
  $('apPrivacy').value=ap.privacy||'private';
  bind('saveGemini',async()=>{await api('/api/youtube-key',{name:'gemini',key:$('geminiKey').value.trim()});notify('Chave do Gemini salva.');showPilot(t);});
  bind('saveGroq',async()=>{await api('/api/youtube-key',{name:'groq',key:$('groqKey').value.trim()});notify('Chave do Groq salva.');showPilot(t);});
  $('oauthFile').onchange=action(async e=>{if(!e.target.files.length)return;const f=new FormData();f.append('file',e.target.files[0]);await api('/api/oauth-client',f);notify('Arquivo de permissão salvo.');showPilot(t);});
  bind('ytConnect',()=>connectYouTube(t));
  if(yt)bind('ytBranding',async()=>{await api('/api/templates/'+t.id+'/youtube/branding',{});notify('Banner e descrição aplicados no YouTube. A foto de perfil troque no YouTube Studio.');});
  bind('apSave',async()=>{await api('/api/templates/'+t.id+'/autopilot',{enabled:$('apOn').checked,per_week:+$('apWeek').value,time:$('apTime').value,privacy:$('apPrivacy').value,publish_time:$('apPublish').value});await refresh();notify('Agenda salva.');});
  bind('apRun',async()=>{await api('/api/templates/'+t.id+'/run-now',{});notify('Piloto iniciado: tema, roteiro, vídeo e envio. Acompanhe no diário e em Produção.');setTimeout(refresh,4000);});
  bind('apTopics',async()=>{
    $('apTopicList').innerHTML='<p>Buscando temas virais do nicho…</p>';
    const r=await api('/api/templates/'+t.id+'/topics',{key:$('key').value,competition:true});
    const list=$('apTopicList');list.innerHTML='<p>Busca do nicho: “'+safe(r.query)+'”. Temas novos (sem repetir o que o canal já fez):</p>';
    for(const v of r.topics){const el=document.createElement('div');el.className='item';
      el.innerHTML='<strong></strong><p></p><div class="row"><a target="_blank" rel="noreferrer">ver original ↗</a><button>Gerar roteiro com este tema</button></div>';
      el.querySelector('strong').textContent=v.title;
      el.querySelector('p').textContent=Math.round(v.score||0)+'× · '+number.format(v.views)+' views · '+v.channel+' · '+v.origin+(v.comp?' · concorrência no Brasil '+v.comp.level:'');
      el.querySelector('a').href=v.url;
      el.querySelector('button').onclick=action(async()=>{notify('Escrevendo o roteiro com a IA…');const x=await api('/api/templates/'+t.id+'/script',{topic:v});await refresh();page('editor');editor(x.project.id);notify('Roteiro pronto. Revise e clique em Salvar e produzir.');});
      list.append(el);}
    if(!r.topics.length)list.innerHTML+='<p>Nenhum tema novo agora.</p>';
  });
}
function showChannelVideos(t){
  showBrand(t);
  showPilot(t);
  showSales(t);
  $('channelTitle').textContent='Vídeos do canal '+(t.channel||t.name);
  const box=$('channelVideos');box.replaceChildren();
  const done=state.jobs.filter(j=>j.status==='done'&&jobTemplate(j)===t.id).reverse();
  const pending=state.projects.filter(p=>p.template_id===t.id&&!state.jobs.some(j=>j.project_id===p.id&&j.status==='done'));
  if(!done.length&&!pending.length){box.innerHTML='<p>Nenhum vídeo neste canal ainda. Em Ideias, escolha um tema e crie o roteiro com este canal selecionado.</p>';return;}
  for(const j of done){
    const url='/files/'+j.id+'/', el=document.createElement('div');el.className='item';
    el.innerHTML='<strong>'+safe(j.title)+'</strong><p>'+safe(j.message)+'</p><video controls preload="none" poster="'+url+'thumbnail.jpg" src="'+url+'video.mp4"></video><div class="row"><a href="'+url+'pacote.zip?download=1">Baixar pacote</a><a href="'+url+'publicacao.txt" target="_blank">Título, descrição e comentário fixado</a></div>';
    const yt=document.createElement('div');yt.className='row';
    if(j.youtube){yt.innerHTML='<a target="_blank" rel="noreferrer">No YouTube ('+safe(j.youtube.privacy)+') ↗</a>'+(j.youtube.note?'<small>'+safe(j.youtube.note)+'</small>':'');yt.querySelector('a').href=j.youtube.url;}
    else if(t.youtube_channel){const b=document.createElement('button');b.textContent='Enviar ao YouTube (privado)';b.onclick=action(async()=>{notify('Enviando… pode levar alguns minutos.');const r=await api('/api/jobs/'+j.id+'/upload',{privacy:'private'});await refresh();notify('Enviado: '+r.result.url+(r.note?' · '+r.note:''));});yt.append(b);}
    el.append(yt);
    box.append(el);
  }
  for(const p of pending){
    const el=document.createElement('div');el.className='item';
    el.innerHTML='<strong>'+safe(p.title)+'</strong><p>Roteiro salvo · ainda não produzido</p><button>Abrir roteiro</button>';
    el.querySelector('button').onclick=()=>{page('editor');editor(p.id);};box.append(el);
  }
}
async function saveTemplate(asNew){
  const form=$('moldForm');
  if(!form.reportValidity())return;
  const d=Object.fromEntries(new FormData(form));
  if(!asNew)d.id=$('editMold').value;
  const result=await api('/api/templates',d);
  await refresh();$('editMold').value=result.id;templateForm();notify('Canal salvo.');
}
$('moldForm').onsubmit=action(async e=>{e.preventDefault();await saveTemplate(false);});
$('editMold').onchange=templateForm;
bind('duplicate',()=>saveTemplate(true));
bind('deleteChannel',async()=>{
  const t=currentChannel();if(!t)return;
  if(!confirm('Apagar o canal “'+t.name+'”? Isso não pode ser desfeito.'))return;
  const r=await fetch('/api/templates/'+t.id,{method:'DELETE',headers:{'X-Studio-Token':token}});
  let d={};try{d=await r.json();}catch{}
  if(r.status===409&&d.needs_all){
    if(!confirm(d.error+' Apagar o canal junto com todos os roteiros, vídeos, banner e página de vendas dele?'))return;
    await api('/api/templates/'+t.id+'?all=1',null,'DELETE');
  }else if(!r.ok)throw Error(d.error||'Não foi possível apagar.');
  $('editMold').value='';await refresh();$('editMold').value=state.templates[0]?.id||'';templateForm();notify('Canal apagado.');
});
async function sendRef(input){
  if(!input.files.length)return;
  const data=new FormData();data.append('file',input.files[0]);
  return (await api('/api/reference-file',data)).reference;
}
$('refUpload').onchange=action(async e=>{const ref=await sendRef(e.target);if(ref)$('baseRef').value=ref;});
bind('inspectModel',async()=>{
  $('modelInfo').textContent='Analisando a referência…';
  try{
    const m=await api('/api/reference-plan',{reference:$('baseRef').value.trim()});
    const moving=m.planos.filter(x=>x.tipo==='video').length;
    $('modelInfo').textContent=m.largura+' × '+m.altura+' · '+m.duracao.toFixed(1)+' s · '+moving+' planos em movimento · '+(m.planos.length-moving)+' planos estáticos';
  }catch(e){$('modelInfo').textContent='';throw e;}
});
bind('makePrompt',async()=>{
  if(!$('idea').value.trim())throw Error('Escreva sua ideia primeiro.');
  const result=await api('/api/prompt',{reference:$('baseRef').value.trim(),idea:$('idea').value,template_id:$('activeMold').value,inspiration});
  $('prompt').value=result.prompt;$('promptBox').hidden=false;
});
bind('copy',async()=>{await navigator.clipboard.writeText($('prompt').value);notify('Prompt copiado.');});
const example={title:'Por que a Lua muda de forma?',thumbnail_text:'Uma Lua, muitas fases',description:'Um passeio pelas fases da Lua.',tags:['Lua','astronomia'],scenes:[{text:'A Lua parece mudar de forma ao longo do mês. O Sol ilumina cerca de metade dela o tempo todo.',caption:'Uma metade iluminada',visual:'Lua ao lado da Terra'},{text:'Conforme a Lua gira ao redor da Terra, vemos porções diferentes dessa metade iluminada. É assim que surgem as fases.',caption:'O nosso ponto de vista muda',visual:'Diagrama da órbita lunar'}]};
$('idea').oninput=()=>{if(inspiration&&$('idea').value!==inspiration.title){inspiration=null;$('inspirationInfo').hidden=true;}};
bind('example',()=>{$('idea').value=example.title;$('script').value=JSON.stringify(example,null,2);});
function parseScript(){
  const raw=$('script').value.trim().replace(/^\x60\x60\x60(?:json)?\s*/i,'').replace(/\s*\x60\x60\x60$/,'').trim();
  if(!raw)throw Error('Insira um roteiro ou carregue o exemplo.');
  if(/^[\[{]/.test(raw)){
    let parsed;try{parsed=JSON.parse(raw);}catch{throw Error('JSON incompleto. Copie a resposta inteira do chat.');}
    const items=Array.isArray(parsed)?parsed:[parsed];
    if(items.some(x=>!x?.scenes?.length))throw Error('Cada roteiro precisa de uma lista scenes com narração.');
    return items;
  }
  return [{title:$('idea').value.trim()||raw.slice(0,65),scenes:raw.split(/\n\s*\n/).map(text=>({text,caption:text.slice(0,90)}))}];
}
bind('import',async()=>{
  const items=await api('/api/projects',{items:parseScript().map(x=>({...x,reference:$('baseRef').value.trim()||x.reference||''})),template_id:$('activeMold').value});
  await refresh();editor(items[0].id);notify('Roteiro salvo.');
});
function project(){return state.projects.find(p=>p.id===selected);}
function field(label, key, value, multiline=false){
  return '<label>'+label+(multiline?'<textarea data-key="'+key+'">'+safe(value)+'</textarea>':'<input data-key="'+key+'" value="'+safe(value)+'">')+'</label>';
}
function editor(id){
  selected=id; const p=project(), box=$('details');box.hidden=false;
  box.innerHTML='<h2>Editar roteiro</h2>'+field('Título','title',p.title)+field('Vídeo de referência','reference',p.reference)+'<label>Trocar por arquivo-base<input id="editRefFile" type="file" accept="video/*"></label><label><input type="checkbox" id="masterMode" style="width:auto;display:inline"> Preservar toda a montagem visual do meu arquivo e trocar a narração</label>'+field('Descrição','description',p.description,true)+field('Tags separadas por vírgula','tags',p.tags.join(', '))+field('Texto da thumbnail','thumbnail_text',p.thumbnail_text)+'<label>Molde deste vídeo<select id="projectMold"></select></label><label>Publicação planejada<input type="datetime-local" id="schedule"></label><div id="scenes"></div><div class="row"><button id="save">Salvar edição</button><button class="primary" id="produce">Salvar e produzir</button></div>';
  $('masterMode').checked=!!p.master;
  $('editRefFile').onchange=action(async e=>{const ref=await sendRef(e.target);if(ref)box.querySelector('[data-key=reference]').value=ref;});
  $('projectMold').replaceChildren(...state.templates.map(t=>new Option(t.name,t.id)));$('projectMold').value=p.template_id;$('schedule').value=p.scheduled;
  p.scenes.forEach((s,i)=>{
    const el=document.createElement('div');el.className='scene';
    el.innerHTML='<strong>Cena '+(i+1)+'</strong>'+field('Narração','text',s.text,true)+field('Texto na tela','caption',s.caption)+field('Referência visual','visual',s.visual)+'<div class="row"><label>Imagem para plano estático '+(s.image?'· anexada':'')+'<input type="file" accept="image/*" data-kind="image"></label><label>Narração automática · substituir '+(s.audio?'· anexado':'')+'<input type="file" accept=".wav,.m4a,.mp3,.ogg" data-kind="audio"></label></div>';
    const medium=document.createElement('label');medium.innerHTML='Sem referência, usar <select data-key="media"><option value="auto">Escolha automática</option><option value="video">Clipe de vídeo</option><option value="imagem">Imagem</option></select>';medium.querySelector('select').value=s.media||'auto';el.append(medium);
    const clip=document.createElement('label');clip.innerHTML='Clipe de vídeo '+(s.video?'· anexado':'· opcional')+'<input type="file" accept="video/*" data-kind="video">';el.append(clip);
    el.querySelectorAll('[type=file]').forEach(input=>input.onchange=action(async()=>{
      if(!input.files.length)return;
      const data=new FormData();data.append('file',input.files[0]);
      await api('/api/projects/'+id+'/assets/'+i+'/'+input.dataset.kind,data);
      const fresh=await api('/api/state');state.projects=fresh.projects;
      input.closest('label').firstChild.textContent+=' · anexado';notify('Arquivo anexado à cena.');
    }));$('scenes').append(el);
  });
  bind('save',async()=>{await saveEditor();notify('Edição salva.');});
  bind('produce',async()=>{await saveEditor();await enqueue([id]);});
  box.scrollIntoView({behavior:'smooth'});
}
async function saveEditor(){
  const p={...project(),master:$('masterMode').checked,template_id:$('projectMold').value,scheduled:$('schedule').value};
  $('details').querySelectorAll(':scope > label [data-key]').forEach(el=>p[el.dataset.key]=el.value);
  p.scenes=[...document.querySelectorAll('.scene')].map(el=>Object.fromEntries([...el.querySelectorAll('[data-key]')].map(i=>[i.dataset.key,i.value])));
  await api('/api/projects/'+selected,p,'PUT');await refresh();
}
async function enqueue(ids){const r=await api('/api/queue',{ids});await refresh();page('queue');window.scrollTo(0,0);notify(r.added+' vídeo(s) na fila.');}
bind('all',()=>enqueue(state.projects.filter(p=>p.scenes.length&&!state.jobs.some(j=>j.project_id===p.id&&['done','queued','running'].includes(j.status))).map(p=>p.id)));
function showJobs(){
  $('jobs').innerHTML=state.jobs.length?'':'<p>Salve um roteiro e clique em “Salvar e produzir” para começar.</p>';
  for(const j of [...state.jobs].reverse()){
    const el=document.createElement('div');el.className='item';const url='/files/'+j.id+'/';
    el.innerHTML='<strong>'+safe(j.title)+'</strong><p>'+safe(j.message)+'</p>';
    if(j.status==='done')el.innerHTML+='<video controls preload="none" poster="'+url+'thumbnail.jpg" src="'+url+'video.mp4"></video><a href="'+url+'pacote.zip?download=1">Baixar vídeo, thumbnail, legendas e metadados</a>';
    if(['queued','running'].includes(j.status)){
      el.innerHTML+='<progress max="100" value="'+j.progress+'"></progress><button>Cancelar</button>';
      el.querySelector('button').onclick=action(async()=>{await api('/api/jobs/'+j.id+'/cancel',{});await refresh();});
    } else {
      const tools=document.createElement('div');tools.className='row';
      if(['error','cancelled'].includes(j.status)&&state.projects.some(p=>p.id===j.project_id)){
        const retry=document.createElement('button');retry.textContent='Tentar novamente';
        retry.onclick=action(()=>enqueue([j.project_id]));tools.append(retry);
      }
      const remove=document.createElement('button');remove.textContent='Remover da lista';remove.className='danger';
      remove.onclick=action(async()=>{if(!confirm('Remover este trabalho e seus arquivos?'))return;await api('/api/jobs/'+j.id,null,'DELETE');await refresh();});
      tools.append(remove);el.append(tools);
    }
    if(j.status==='error')el.classList.add('failed');
    $('jobs').append(el);
  }
}
async function showKeys(){try{const k=await api('/api/keys');for(const n of ['pexels','pixabay'])$('k'+n).textContent=k[n]?'· salva':'';}catch{}}
for(const n of ['pexels','pixabay'])bind('save'+n[0].toUpperCase()+n.slice(1),async()=>{await api('/api/youtube-key',{name:n,key:$(n+'Key').value});$(n+'Key').value='';await showKeys();notify('Chave salva neste Windows.');});
bind('manual',()=>window.open('https://www.youtube.com/results?search_query='+encodeURIComponent($('query').value),'_blank','noopener'));
bind('storeKey',async()=>{
  await api('/api/youtube-key',{key:$('key').value});
  $('key').value='';
  notify('Chave salva no perfil do Windows.');
});
const number = new Intl.NumberFormat('pt-BR',{notation:'compact',maximumFractionDigits:1});
const clock=s=>{if(!s)return '—';const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=String(s%60).padStart(2,'0');return h?h+':'+String(m).padStart(2,'0')+':'+x:m+':'+x;};
async function useAsModel(r){
  inspiration={title:r.title,seconds:r.seconds,per_day:r.per_day,tags:r.tags||[],foreign:lastForeign};
  $('idea').value=r.title;$('baseRef').value='';$('modelInfo').textContent='';
  notify('Criando o canal inspirado em '+r.channel+'…');
  let made=null;
  try{made=await api('/api/channel-from-video',{video:r,key:$('key').value,query:$('query').value,search:lastSearch});await refresh();$('activeMold').value=made.template.id;}
  catch(e){notify(e.message);}
  $('inspirationInfo').hidden=false;
  $('inspirationInfo').textContent='Modelo: “'+r.title+'” · '+clock(r.seconds)+(r.short?' · Shorts':'')+' · '+number.format(r.per_day)+' views/dia.'+(inspiration.foreign?' Vídeo da gringa: o roteiro vai ADAPTAR o tema para o Brasil.':'')+' O roteiro será ORIGINAL sobre o mesmo tema. Clique em Preparar prompt.';
  if(made){const t=made.template;$('inspirationInfo').textContent+=' Canal '+(made.created?'criado':'já existente')+': “'+t.name+'” ('+t.niche+'), inspirado em '+((t.source||{}).title||r.channel)+'. Foto de perfil, banner e textos estão em Canais.';}
  page('editor');window.scrollTo(0,0);
}
let lastList=[];
function termBox(card,r,value,label){
  const box=card.querySelector('.comp');box.innerHTML='';
  const input=document.createElement('input');input.value=value||'';input.placeholder='tema em português';input.className='term';
  const btn=document.createElement('button');btn.textContent=label||'Checar';
  btn.onclick=action(async()=>{const c=await api('/api/competition',{query:input.value,key:$('key').value,region:'BR',viral:r.score||0});r.comp=c;r.opportunity=c.opportunity;paintCompetition(card,c,r);});
  box.append(input,btn);return box;
}
function paintCompetition(card,c,r){
  if(c.needs_term){const box=termBox(card,r,'');const m=document.createElement('small');m.textContent=c.message+' (em inglês: '+c.query+')';box.append(m);return;}
  const box=r?termBox(card,r,c.query,'Refazer'):card.querySelector('.comp');if(!r)box.innerHTML='';
  const tone=c.level==='Baixa'?'low':c.level==='Média'?'mid':'high';
  const tag=document.createElement('span');tag.className='lvl '+tone;tag.textContent='Concorrência '+c.level;
  const info=document.createElement('small');
  info.textContent='No Brasil: '+c.related+' vídeo(s) sobre o tema, '+c.strong+' forte(s)'+(c.opportunity!=null?' · Oportunidade '+c.opportunity+'/100':'');
  info.title=(c.top||[]).map(v=>v.title+' — '+v.channel+' ('+number.format(v.views)+' views)').join('\n');
  box.prepend(tag);box.append(info);
}
async function checkCompetition(r,card){
  const c=await api('/api/competition',{title:r.title,key:$('key').value,region:'BR',translate:true,viral:r.score||0});
  r.comp=c;r.opportunity=c.opportunity;paintCompetition(card,c,r);
  try{store.set('studio.last',JSON.stringify({list:lastList,query:$('query').value,mode:$('mode').value,days:$('days').value,lang:$('lang').value}));}catch{}
}
function paintPotential(card,p){
  const box=card.querySelector('.pot');box.innerHTML='';
  const tone=p.level==='Formato que se repete'?'low':p.level==='Promissor'?'mid':'high';
  const tag=document.createElement('span');tag.className='lvl '+tone;tag.textContent=p.level+(p.score!=null?' · '+p.score+'/100':'');
  const info=document.createElement('small');
  info.textContent=p.message||('Acertou '+p.hits+' de '+p.videos+' vídeos · mediana '+number.format(p.median)+' views · '+p.per_week+' vídeo(s)/semana · '+(p.trend>=1.2?'subindo':p.trend<=0.8?'caindo':'estável'));
  box.append(tag,info);
  if(p.best?.length>1){
    const det=document.createElement('details');const sum=document.createElement('summary');sum.textContent='Próximos temas da série ('+p.best.length+' que deram certo)';det.append(sum);
    for(const b of p.best){const a=document.createElement('a');a.href=b.url;a.target='_blank';a.rel='noreferrer';a.textContent=b.title+' · '+number.format(b.views);det.append(a);}
    box.append(det);
  }
}
async function checkPotential(r,card){
  const p=await api('/api/channel-potential',{channel_id:r.channel_id,key:$('key').value});
  r.pot=p;paintPotential(card,p);
}
async function checkTop(n){
  const cards=[...document.querySelectorAll('#results .video-card')].slice(0,n);
  for(const card of cards){const r=lastList[+card.dataset.idx];if(r&&!r.comp){try{await checkCompetition(r,card);}catch(e){notify(e.message);break;}}}
  if($('sort').value==='opportunity'){lastList.sort((a,b)=>(b.opportunity??-1)-(a.opportunity??-1));showResults(lastList,$('query').value);}
}
function showResults(list,query,cached){
  lastList=list;
  const grid=$('results');
  grid.replaceChildren();
  $('count').textContent=(query||'Em alta')+' · '+list.length+' resultados'+(cached?' · da memória (sem gastar cota)':'');
  if(list.length){const b=document.createElement('button');b.className='checkAll';b.textContent='Checar concorrência no Brasil dos 8 primeiros (≈ 8% da cota do dia)';b.onclick=action(()=>checkTop(8));grid.append(b);}
  if(!list.length)grid.textContent='Nenhum vídeo encontrado para este período.';
  for(const r of list){
    const card=document.createElement('article');
    card.className='video-card';
    const ratio=r.score==null?'—':Math.round(r.score).toLocaleString('pt-BR')+'×';
    card.dataset.idx=list.indexOf(r);
    card.innerHTML='<div class="metrics"><b title="Visualizações por dia">'+safe(number.format(r.per_day??0))+'/dia</b><span title="Views ÷ inscritos">'+safe(ratio)+'</span><span>'+safe(number.format(r.views))+' views</span><span>'+safe(r.subscribers==null?'—':number.format(r.subscribers))+' inscr.</span></div><a class="preview" target="_blank" rel="noreferrer"><img loading="lazy" alt=""><em></em></a><h3></h3><small></small><div class="comp"><span>Concorrência no Brasil: —</span><button class="compBtn">Checar</button></div><div class="pot"><span>Potencial do canal: —</span><button class="potBtn">Analisar</button></div><button class="make">Criar vídeo original neste tema</button>';
    const link=card.querySelector('a');
    link.href='https://www.youtube.com/watch?v='+encodeURIComponent(r.id);
    link.setAttribute('aria-label','Assistir a '+r.title);
    card.querySelector('img').src='https://i.ytimg.com/vi/'+encodeURIComponent(r.id)+'/mqdefault.jpg';
    card.querySelector('em').textContent=(r.short?'SHORTS · ':'')+clock(r.seconds);
    card.querySelector('h3').textContent=r.title;
    card.querySelector('small').textContent=r.channel+' · '+new Date(r.published).toLocaleDateString('pt-BR')+(r.engagement?' · '+r.engagement+'% engaj.':'');
    card.querySelector('.make').onclick=()=>useAsModel(r);
    card.querySelector('.compBtn').onclick=action(()=>checkCompetition(r,card));
    card.querySelector('.potBtn').onclick=action(()=>checkPotential(r,card));
    if(r.pot)paintPotential(card,r.pot);
    if(r.comp)paintCompetition(card,r.comp,r);
    grid.append(card);
  }
}
$('mode').addEventListener('change',()=>{$('query').placeholder=$('mode').value.startsWith('gringa')?'Digite em português ou inglês (ex.: curiosidades de história)…':'Caçar ideias sobre um nicho…';});
$('hunt').onsubmit=action(async e=>{
  e?.preventDefault?.();
  const query=$('query').value.trim();
  if(($('mode').value!=='trending'&&!query)){notify('Digite um nicho ou escolha “Em alta no país”.');return;}
  if(!$('days').reportValidity())return;
  $('search').disabled=true;
  $('search').textContent='Buscando…';
  try {
    const gringa=$('mode').value.startsWith('gringa');
    const small=['gringa_small','gringa_long'].includes($('mode').value);
    const mode=gringa?({gringa_shorts:'shorts',gringa_long:'long'}[$('mode').value]||'videos'):$('mode').value;
    const sort=small?'score':$('sort').value, maxSubs=small?($('maxSubs').value||100000):$('maxSubs').value;
    const region=gringa?'US':$('region').value, language=gringa?'en':$('lang').value;
    lastForeign=region!=='BR'&&region!=='PT';
    const r=await api('/api/research',{query,key:$('key').value,mode,days:$('days').value,language,region,sort,max_subs:maxSubs,category:$('category').value,channel_months:$('months').value});
    const list=r.results;
    lastSearch={query:r.query_used||query,region,language};
    showResults(list,query,r.cached);
    if(r.query_note)$('count').textContent+=' · '+r.query_note;
    if(r.niche)$('count').textContent+=' · '+r.niche.level+': '+r.niche.channels_winning+' canais diferentes acertando ('+r.niche.small_channels_winning+' pequenos)';
    try{store.set('studio.last',JSON.stringify({list,query,mode:$('mode').value,days:$('days').value,lang:$('lang').value}));}catch{}
  }finally{$('search').disabled=false;$('search').textContent='Caçar';}
});
bind('filter',()=>{$('filters').hidden=!$('filters').hidden;$('filter').setAttribute('aria-expanded',String(!$('filters').hidden));});
bind('theme',()=>{
  const next=document.documentElement.dataset.theme==='light'?'dark':'light';
  document.documentElement.dataset.theme=next;store.set('studio.theme',next);
});
document.documentElement.dataset.theme=store.get('studio.theme')||'dark';
$('notes').value=store.get('studio.notes')||'';
$('notes').oninput=()=>{store.set('studio.notes',$('notes').value);$('noteStatus').textContent='Anotações salvas';};
function showMoldCards(){
  const box=$('moldCards');box.replaceChildren();
  for(const t of state.templates){
    const card=document.createElement('button');card.className='mold-card';card.setAttribute('aria-pressed',String(t.id===$('editMold').value));
    const mark=document.createElement('i');mark.style.background=t.accent;mark.textContent=(t.channel||t.name||'M').charAt(0).toUpperCase();
    const name=document.createElement('strong');name.textContent=t.channel||t.name;
    const count=state.jobs.filter(j=>j.status==='done'&&jobTemplate(j)===t.id).length;
    const info=document.createElement('small');info.textContent=(t.niche||'')+' · '+(t.format==='vertical'?'Shorts':'Longo')+' · '+count+' vídeo(s)';
    card.append(mark,name,info);card.onclick=()=>{$('editMold').value=t.id;templateForm();};
    box.append(card);
  }
}
async function init(){
  page('research');await refresh();
  if(!state.projects.length)notify('Dica: em Roteiro, clique em “Experimentar com exemplo” e depois em “Salvar roteiro”.');
  try{
    const cached=JSON.parse(store.get('studio.last'));
    if(cached){$('query').value=cached.query;$('mode').value=cached.mode;$('days').value=cached.days;$('lang').value=cached.lang;showResults(cached.list,cached.query);}
  }catch{store.del('studio.last');}
  const system=await api('/api/system');for(const v of system.voices)$('voice').add(new Option(v.name+' · '+v.culture,v.name));
  showKeys();templateForm();$('engine').textContent=(system.ffmpeg?'Renderização local disponível.':'FFmpeg ausente. Feche e abra Iniciar.cmd para instalar.')+' Dados em: '+system.data;
  setInterval(async()=>{if(!state?.jobs?.some(j=>['queued','running'].includes(j.status)))return;try{const data=await api('/api/state');state.jobs=data.jobs;showJobs();}catch(e){notify(e.message);}},2500);
}
init().catch(e=>notify(e.message));
