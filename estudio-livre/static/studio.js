const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name=studio-token]').content;
const safe = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
let state, selected, noticeTimer;
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
}
async function saveTemplate(asNew){
  const form=$('moldForm');
  if(!form.reportValidity())return;
  const d=Object.fromEntries(new FormData(form));
  if(!asNew)d.id=$('editMold').value;
  const result=await api('/api/templates',d);
  await refresh();$('editMold').value=result.id;templateForm();notify('Molde salvo.');
}
$('moldForm').onsubmit=action(async e=>{e.preventDefault();await saveTemplate(false);});
$('editMold').onchange=templateForm;
bind('duplicate',()=>saveTemplate(true));
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
  const result=await api('/api/prompt',{reference:$('baseRef').value.trim(),idea:$('idea').value,template_id:$('activeMold').value});
  $('prompt').value=result.prompt;$('promptBox').hidden=false;
});
bind('copy',async()=>{await navigator.clipboard.writeText($('prompt').value);notify('Prompt copiado.');});
const example={title:'Por que a Lua muda de forma?',thumbnail_text:'Uma Lua, muitas fases',description:'Um passeio pelas fases da Lua.',tags:['Lua','astronomia'],scenes:[{text:'A Lua parece mudar de forma ao longo do mês. O Sol ilumina cerca de metade dela o tempo todo.',caption:'Uma metade iluminada',visual:'Lua ao lado da Terra'},{text:'Conforme a Lua gira ao redor da Terra, vemos porções diferentes dessa metade iluminada. É assim que surgem as fases.',caption:'O nosso ponto de vista muda',visual:'Diagrama da órbita lunar'}]};
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
    const medium=document.createElement('label');medium.innerHTML='Sem referência, usar <select data-key="media"><option value="auto">Escolha automática</option><option value="video">Clipe de vídeo</option><option value="imagem">Imagem</option><option value="animacao">Animação gráfica (texto e números)</option></select>';medium.querySelector('select').value=s.media||'auto';el.append(medium);
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
function showResults(list,query){
  const grid=$('results');
  grid.replaceChildren();
  $('count').textContent=query+' · '+list.length+' resultados';
  if(!list.length)grid.textContent='Nenhum vídeo encontrado para este período.';
  for(const r of list){
    const card=document.createElement('article');
    card.className='video-card';
    const ratio=r.score==null?'—':r.score.toLocaleString('pt-BR')+'×';
    card.innerHTML='<div class="metrics"><b title="Visualizações por inscrito">'+safe(ratio)+'</b><span>'+safe(r.subscribers==null?'—':number.format(r.subscribers))+' inscritos</span><span>'+safe(number.format(r.views))+' views</span></div><a class="preview" target="_blank" rel="noreferrer"><img loading="lazy" alt=""></a><h3></h3><small></small><button>Modelar vídeo</button>';
    const link=card.querySelector('a');
    link.href='https://www.youtube.com/watch?v='+encodeURIComponent(r.id);
    link.setAttribute('aria-label','Assistir a '+r.title);
    card.querySelector('img').src='https://i.ytimg.com/vi/'+encodeURIComponent(r.id)+'/mqdefault.jpg';
    card.querySelector('h3').textContent=r.title;
    card.querySelector('small').textContent=r.channel+' · '+new Date(r.published).toLocaleDateString('pt-BR');
    card.querySelector('button').onclick=()=>{$('idea').value=r.title;$('baseRef').value=link.href;$('modelInfo').textContent='';page('editor');window.scrollTo(0,0);};
    grid.append(card);
  }
}
$('hunt').onsubmit=action(async e=>{
  e.preventDefault();
  const query=$('query').value.trim();
  if(!query||!$('days').reportValidity())return;
  $('search').disabled=true;
  $('search').textContent='Buscando…';
  try {
    const list=await api('/api/research',{query,key:$('key').value,mode:$('mode').value,days:$('days').value,language:$('lang').value});
    showResults(list,query);
    localStorage.setItem('studio.last',JSON.stringify({list,query,mode:$('mode').value,days:$('days').value,lang:$('lang').value}));
  }finally{$('search').disabled=false;$('search').textContent='Caçar';}
});
bind('filter',()=>{$('filters').hidden=!$('filters').hidden;$('filter').setAttribute('aria-expanded',String(!$('filters').hidden));});
bind('theme',()=>{
  const next=document.documentElement.dataset.theme==='light'?'dark':'light';
  document.documentElement.dataset.theme=next;localStorage.setItem('studio.theme',next);
});
document.documentElement.dataset.theme=localStorage.getItem('studio.theme')||'dark';
$('notes').value=localStorage.getItem('studio.notes')||'';
$('notes').oninput=()=>{localStorage.setItem('studio.notes',$('notes').value);$('noteStatus').textContent='Anotações salvas';};
function showMoldCards(){
  const box=$('moldCards');box.replaceChildren();
  for(const t of state.templates){
    const card=document.createElement('button');card.className='mold-card';card.setAttribute('aria-pressed',String(t.id===$('editMold').value));
    const mark=document.createElement('i');mark.style.background=t.accent;mark.textContent=(t.channel||t.name||'M').charAt(0).toUpperCase();
    const name=document.createElement('strong');name.textContent=t.name;
    card.append(mark,name);card.onclick=()=>{$('editMold').value=t.id;templateForm();};
    box.append(card);
  }
}
async function init(){
  page('research');await refresh();
  if(!state.projects.length)notify('Dica: em Roteiro, clique em “Experimentar com exemplo” e depois em “Salvar roteiro”.');
  try{
    const cached=JSON.parse(localStorage.getItem('studio.last'));
    if(cached){$('query').value=cached.query;$('mode').value=cached.mode;$('days').value=cached.days;$('lang').value=cached.lang;showResults(cached.list,cached.query);}
  }catch{localStorage.removeItem('studio.last');}
  const system=await api('/api/system');for(const v of system.voices)$('voice').add(new Option(v.name+' · '+v.culture,v.name));
  showKeys();templateForm();$('engine').textContent=(system.ffmpeg?'Renderização local disponível.':'FFmpeg ausente. Feche e abra Iniciar.cmd para instalar.')+' Dados em: '+system.data;
  setInterval(async()=>{if(!state?.jobs?.some(j=>['queued','running'].includes(j.status)))return;try{const data=await api('/api/state');state.jobs=data.jobs;showJobs();}catch(e){notify(e.message);}},2500);
}
init().catch(e=>notify(e.message));
