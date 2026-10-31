'use strict';
const judgingFactors={
 temperature:['Temperature','Suitability for measured and feels-like temperature.'],
 weather:['Weather','Warm-weather humidity and known outdoor wind or rain.'],
 occasion:['Occasion','Fit for your plans, when the occasion is known.'],
 environment:['Environment','Whether projection suits the known setting.'],
 time:['Time of day','Known morning, afternoon, evening or night suitability.'],
 season:['Season','Source seasonal suitability; temperature limits still apply.'],
 projection:['Presence match','How close projection is to your preferred presence.'],
 longevity:['Longevity','Whether expected duration covers your planned wear.'],
 preference:['Personal preference','Your personal rating and bounded favorite boost.'],
 history:['Feedback','Known personal feedback or a known community rating.'],
 rotation:['Variety','Give recently unworn bottles a chance. Capped at 4% of the score.']
};
const priorityPresets={balanced:{temperature:9,weather:5,occasion:7,environment:7,time:5,season:3,projection:6,longevity:6,preference:6,history:4,rotation:3},weather:{temperature:10,weather:9,occasion:5,environment:5,time:4,season:3,projection:5,longevity:5,preference:4,history:3,rotation:2},variety:{temperature:9,weather:5,occasion:6,environment:6,time:5,season:3,projection:5,longevity:6,preference:4,history:4,rotation:10}};
const priorityPreview={sequence:0,controller:null,timer:null,token:null,baseline:null,saved:null};
function importanceForWeights(weights){const max=Math.max(...Object.values(weights),1);return Object.fromEntries(Object.keys(judgingFactors).map(k=>[k,weights[k]>0?Math.max(1,Math.round(weights[k]/max*100)/10):0]))}
function humanReason(reason){return String(reason).replace(/(\d+(?:\.\d+)?)\/100/g,(_,v)=>fitLabel(Number(v)))}
function actualShares(c){
 if(c.shares)return c.shares;
 const weights=c.weights||{},total=Object.values(weights).reduce((a,b)=>a+b,0),rotation=total?Math.min(.04,(weights.rotation||0)/total):0,rest=total-(weights.rotation||0);
 return Object.fromEntries(Object.keys(weights).map(k=>[k,100*(k==='rotation'?rotation:rest?weights[k]/rest*(1-rotation):0)]));
}
function judgementPanel(c,rec){
 const importance=rec.importance||importanceForWeights(rec.weights||prefs().weights),shares=actualShares(c);
 return `<div class="judging-table"><table class="score-table"><thead><tr><th>Factor</th><th>Importance</th><th>Share of score</th><th>Fit</th></tr></thead><tbody>${Object.entries(judgingFactors).map(([key,[label]])=>{
   const present=c.components[key]!=null,on=(rec.weights?.[key]??0)>0;
   return `<tr><th scope="row">${label}</th><td>${on?Number(importance[key]).toFixed(1).replace(/\.0$/,'')+'/10':'Off'}</td><td>${!on?'Off':!present?'Excluded':(shares[key]||0).toFixed(1)+'%'}</td><td>${present&&on?fitLabel(c.components[key]):'Not used'}</td></tr>`;
 }).join('')}</tbody></table></div><p class="fine">Shares are specific to this fragrance: unknown factors are excluded and the rest are reweighted. Fit and information quality are different measures.</p>${c.penalties.length?`<div class="judgement-limits"><h3>Limits and deductions</h3>${c.penalties.map(p=>`<p>${esc(humanReason(p.reason))} <span class="muted">${p.amount?'−'+(p.amount/10).toFixed(1)+' score points':''}</span></p>`).join('')}</div>`:''}${Object.keys(c.omitted||{}).length?`<details><summary>What wasn’t assessed?</summary>${Object.entries(c.omitted).map(([k,reason])=>`<p class="fine"><strong>${judgingFactors[k]?.[0]||esc(k)}</strong>: ${esc(reason)}</p>`).join('')}</details>`:''}`;
}
function prioritiesPanel(){
 const values=prefs().importance||importanceForWeights(prefs().weights);
 return `<div class="section-heading"><h3>Your priorities</h3><span>IMPORTANCE ≠ FIT</span></div><p class="muted">Set importance from 1 to 10, or turn a factor off. These are relative priorities, not percentages. Unknown factors are left out automatically. Personal boundaries always apply. Temperature mismatch limits apply while Temperature is enabled.</p><div class="inline-actions priority-presets"><button type="button" class="secondary" data-priority-preset="balanced">Balanced</button><button type="button" class="secondary" data-priority-preset="weather">Weather first</button><button type="button" class="secondary" data-priority-preset="variety">More variety</button><button type="button" class="text-button" data-priority-preset="reset">Reset defaults</button></div><div class="priority-layout"><div class="priority-controls"><div id="priority-winner" aria-live="polite">Loading preview…</div>${Object.entries(judgingFactors).map(([key,[label,description]])=>`<div class="priority-control"><div><label class="check"><input type="checkbox" name="priority_enabled_${key}" ${values[key]>0?'checked':''} aria-label="Use ${label}">${label}</label><output id="priority-output-${key}" for="priority-${key}">${values[key]>0?Number(values[key]).toFixed(1).replace(/\.0$/,'')+'/10':'Off'}</output></div><input id="priority-${key}" name="priority_${key}" type="range" min="1" max="10" step=".1" value="${values[key]||5}" ${values[key]>0?'':'disabled'} aria-label="${label} importance"><p>${description}</p></div>`).join('')}</div><section class="priority-preview" aria-label="Live ranking preview"><h3>What changes?</h3><p class="fine">Uses a fixed context and your saved settings. Moving sliders does not save priorities or create journal entries.</p><p id="priority-context" class="fine"></p><p id="priority-status" role="status" aria-live="polite">Loading preview…</p><div id="priority-results"></div></section></div><div class="inline-actions"><button type="button" class="primary" id="save-priorities">Save these priorities</button><span id="priority-save-status" class="fine">Changes are not saved until you choose Save.</span></div>`;
}
function readImportance(){return Object.fromEntries(Object.keys(judgingFactors).map(k=>[k,$(`[name=priority_enabled_${k}]`).checked?Number($(`[name=priority_${k}]`).value):0]))}
function initPriorities(){
 priorityPreview.sequence++;priorityPreview.controller?.abort();priorityPreview.token=null;priorityPreview.baseline=null;priorityPreview.saved=readImportance();updatePriorityControls();requestPriorityPreview();
}
function updatePriorityControls(){
 for(const k of Object.keys(judgingFactors)){const enabled=$(`[name=priority_enabled_${k}]`).checked,input=$(`[name=priority_${k}]`);input.disabled=!enabled;$('#priority-output-'+k).textContent=enabled?Number(input.value).toFixed(1).replace(/\.0$/,'')+'/10':'Off'}
 $('#priority-save-status').textContent=JSON.stringify(readImportance())===JSON.stringify(priorityPreview.saved)?'Current saved priorities.':'Previewing unsaved priorities.';
}
function setPriorities(values){for(const k of Object.keys(judgingFactors)){$(`[name=priority_enabled_${k}]`).checked=values[k]>0;$(`[name=priority_${k}]`).value=values[k]||5}updatePriorityControls();queuePriorityPreview()}
function resetPriorities(){setPriorities(importanceForWeights(state.defaults.weights))}
function queuePriorityPreview(){clearTimeout(priorityPreview.timer);priorityPreview.sequence++;priorityPreview.controller?.abort();priorityPreview.timer=setTimeout(requestPriorityPreview,250)}
async function requestPriorityPreview(){
 if(state.page!=='settings'||!$('#priority-results'))return;
 const sequence=++priorityPreview.sequence;priorityPreview.controller?.abort();const controller=new AbortController();priorityPreview.controller=controller;
 $('#priority-status').textContent='Updating preview…';
 try{
  const result=await api('/recommendations/preview','POST',{importance:readImportance(),...(priorityPreview.token?{preview_token:priorityPreview.token}:state.rec&&Date.now()-state.rec.loadedAt<3600000?{recommendation_id:state.rec.id}:{})},{signal:controller.signal});
  if(sequence!==priorityPreview.sequence||state.page!=='settings')return;
  priorityPreview.token=result.preview_token;const best=result.candidates[0];$('#priority-winner').textContent=best&&!best.excluded&&best.score!=null?'Preview · '+best.fragrance.name+' · '+fitLabel(best.score):'Preview · no eligible scored fragrance';
  if(!priorityPreview.baseline)priorityPreview.baseline=new Map(result.candidates.map((c,i)=>[c.fragrance.id,i]));
  $('#priority-context').textContent=`${title(result.context.daypart)} · ${temperature(result.context.temperature)} · ${title(result.context.occasion)} · ${result.context.duration} hours`;
  $('#priority-status').textContent=result.candidates.length?'Live preview updated.':'Add fragrances to see a ranking preview.';
  $('#priority-results').innerHTML=result.candidates.map((c,i)=>{const before=priorityPreview.baseline.get(c.fragrance.id),change=before==null?0:before-i;return `<article class="priority-result"><p class="brand">${i+1}. ${esc(c.fragrance.brand)} ${change?`<span>${change>0?'↑':'↓'} ${Math.abs(change)}</span>`:''}</p><h3>${esc(c.fragrance.name)}</h3><p>${c.excluded?'Excluded by your boundary':fitDescription(c.score)} · <span class="muted">${confidenceLabel(c)}</span></p><p class="fine">${esc(humanReason(c.explanation))}</p><details><summary>Why this rank?</summary>${judgementPanel(c,result)}</details></article>`}).join('');
 }catch(e){if(e.name==='AbortError'||sequence!==priorityPreview.sequence||state.page!=='settings')return;$('#priority-status').textContent=e.message;$('#priority-winner').textContent=e.message;$('#priority-results').replaceChildren()}
}
document.addEventListener('input',e=>{if(e.target.name==='projection_display'){$('#presence-value').textContent=Number(e.target.value).toFixed(1)+'/10';return}if(e.target.name==='variety_display'){$('#variety-value').textContent=Number(e.target.value).toFixed(1)+'/10';return}if(!e.target.name?.startsWith('priority_'))return;updatePriorityControls();queuePriorityPreview()});
document.addEventListener('change',e=>{if(!e.target.name?.startsWith('priority_enabled_'))return;updatePriorityControls();queuePriorityPreview()});
document.addEventListener('click',async e=>{
 const preset=e.target.closest('[data-priority-preset]');if(preset){if(preset.dataset.priorityPreset==='reset')resetPriorities();else setPriorities(priorityPresets[preset.dataset.priorityPreset]);return}
 if(e.target.id==='save-priorities'){
  e.target.disabled=true;
  try{const importance=readImportance(),result=await api('/profile','PATCH',{preferences:{importance}});state.user=result.user;state.rec=null;priorityPreview.saved=importance;$('#priority-save-status').textContent='Priorities saved.';toast('Priorities saved. Other preferences are unchanged.')}catch(error){$('#priority-save-status').textContent=error.message}finally{e.target.disabled=false}
 }
});
