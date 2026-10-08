'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="app-token"]').content;
let state = null;
let pending = false;
let exiting = false;
let confirmationId = null;
const activePhases = ['running', 'confirmation', 'stopping','diagnostic'];
const phases = {diagnostic:'Navegador aberto para diagnóstico',idle:'Aguardando planilha', validated:'Planilha validada', running:'Em execução', confirmation:'Confirmar ajuizamento', stopping:'Parada solicitada', stopped:'Interrompido', finished:'Lote encerrado', failed:'Execução interrompida'};
function notice(message) { $('notice').textContent = message || ''; $('notice').hidden = !message; }
async function api(path, body) {
  const options = {method: body === undefined ? 'GET' : 'POST', headers:{'X-App-Token':token}};
  if (body !== undefined) { options.headers['Content-Type']='application/json'; options.body=JSON.stringify(body); }
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'A operação não foi concluída.');
  return data;
}
function text(tag, value, cls) { const node=document.createElement(tag); node.textContent=value; if(cls) node.className=cls; return node; }
function controls() {
  const busy = exiting || pending || (state && activePhases.includes(state.phase));
  for(const id of ['path','choose','validate','user','password','mode','limit','diagnostic']) $(id).disabled=busy;
  $('start').disabled=busy || !state || !state.rows.some(r=>r.eligible) || $('path').value.trim()!==state.path;
  $('stop').disabled=pending || !state || !['running','confirmation','diagnostic'].includes(state.phase);
  $('stop').textContent=state?.phase==='diagnostic' ? 'Encerrar diagnóstico' : 'Interromper execução';
  $('exit').disabled=busy || exiting;
  $('confirm').disabled=pending || !state || state.phase!=='confirmation';
}
function render(data) {
  state=data;
  if(activePhases.includes(data.phase)) $('path').value=data.path;
  const eligible=data.rows.filter(r=>r.eligible);
  const done=eligible.filter(r=>['Concluído','Erro','Verificar protocolo'].includes(r.status));
  const processed=done.filter(r=>r.attempted);
  $('phase').textContent=phases[data.phase] || data.phase;
  const total=['idle','validated'].includes(data.phase) ? Math.min(data.total, Number($('limit').value) || 50) : data.total;
  $('total').textContent=total;
  $('completed').textContent=processed.filter(r=>r.status==='Concluído').length;
  $('errors').textContent=processed.filter(r=>['Erro','Verificar protocolo'].includes(r.status)).length;
  $('progress').max=Math.max(1,total); $('progress').value=processed.length;
  $('progress-count').textContent=total ? `${processed.length} / ${total}` : '';
  $('progress-label').textContent=data.current ? `Registro ${data.current}` : 'Pronto para começar';
  $('stage').textContent=data.stage || (data.phase==='validated' ? 'Confira a validação dos registros' : 'Selecione uma planilha');
  $('message').textContent=data.message || '';
  $('activity-icon').textContent=activePhases.includes(data.phase) ? '↻' : '○';
  $('row-count').textContent=`${data.rows.length} registro${data.rows.length===1?'':'s'}`;
  confirmationId=data.confirmation?.id || null;
  $('confirmation').hidden=data.phase!=='confirmation';
  if(data.confirmation) $('confirmation-title').textContent=`Ajuizar registro ${data.confirmation.record}`;
  const rows=$('rows'); rows.replaceChildren();
  if(!data.rows.length) { const tr=document.createElement('tr'); const td=text('td','Nenhum registro preenchido. Complete a planilha de trabalho.','empty'); td.colSpan=4; tr.append(td); rows.append(tr); }
  for(const row of data.rows) {
    const tr=document.createElement('tr');
    const id=document.createElement('td'); id.append(text('strong',row.id),text('small',row.class));
    const status=document.createElement('td');
    let badge=''; if(row.status==='Concluído') badge='success'; else if(row.status==='Erro') badge='error'; else if(row.status==='Em execução') badge='running'; else if(['Verificar protocolo','Em execução'].includes(row.status)) badge='review';
    status.append(text('span',row.status,'badge '+badge));
    if(!row.eligible) status.append(text('small','Não será reprocessado'));
    else if(row.in_batch===false) status.append(text('small','Fora deste lote'));
    const result=document.createElement('td'); result.append(text('strong',row.process || '—')); if(row.judge) result.append(text('small',row.judge));
    const notes=document.createElement('td'); if(row.stage) notes.append(text('strong',row.stage)); notes.append(text('small',row.error || (row.eligible && row.valid ? 'Entrada validada' : '')));
    tr.append(id,status,result,notes); rows.append(tr);
  }
  $('logs').replaceChildren();
  for(const line of data.logs.length ? data.logs : ['Nenhuma atividade registrada.']) $('logs').append(text('li',line));
  controls();
}
async function action(callback) {
  if(pending) return;
  pending=true; notice(''); controls();
  try { await callback(); if(!exiting) render(await api('/api/state')); }
  catch(error) { notice(error.message); }
  finally { pending=false; controls(); }
}
$('choose').addEventListener('click',()=>action(async()=>{ const data=await api('/api/select',{}); if(data.path) { const validated=await api('/api/validate',{path:data.path}); $('path').value=validated.path; } }));
$('validate').addEventListener('click',()=>action(async()=>{ if(!$('path').value.trim()) throw new Error('Escolha a planilha primeiro.'); const validated=await api('/api/validate',{path:$('path').value.trim()}); $('path').value=validated.path; }));
$('path').addEventListener('input',controls);
$('limit').addEventListener('input',()=>{if(state) render(state);});
$('mode').addEventListener('change',()=>{ $('mode-hint').textContent=$('mode').value==='manual' ? 'O robô aguarda sua confirmação nesta tela antes de ajuizar.' : 'Cada registro será ajuizado automaticamente, sem uma confirmação individual.'; });
$('setup-form').addEventListener('submit',event=>{
  event.preventDefault();
  const password=$('password').value;
  $('password').value='';
  action(async()=>{ await api('/api/start',{path:$('path').value.trim(),user:$('user').value.trim(),password,automatic:$('mode').value==='automatic',limit:Number($('limit').value),diagnostic:$('diagnostic').checked}); });
});
$('confirm').addEventListener('click',()=>{ const id=confirmationId; action(()=>api('/api/confirm',{confirmation_id:id})); });
$('stop').addEventListener('click',()=>action(()=>api('/api/stop',{})));
$('exit').addEventListener('click',()=>action(async()=>{
  await api('/api/exit',{});
  exiting=true;
  $('stage').textContent='Programa encerrado';
  $('message').textContent='Você pode fechar esta aba. Para abrir novamente, execute o programa.';
  $('phase').textContent='Encerrado';
}));
async function poll() {
  if(exiting) return;
  try { if(!pending) render(await api('/api/state')); }
  catch(error) { notice('Não foi possível conectar à interface local. Mantenha o programa aberto e atualize esta página.'); }
  finally { if(!exiting) setTimeout(poll,1000); }
}
poll();
