'use strict';
const pairName=r=>`${r.first.name} + ${r.second.name}`;
const pairApplication=r=>`${r.first_sprays} ${r.first_sprays===1?'spray':'sprays'} of ${r.first.name}, then ${r.second_sprays} of ${r.second.name}`;
function layeringContext(c){
 const parts=[];
 if(c.daypart&&c.daypart!=='unknown')parts.push(title(c.daypart));
 if(c.temperature!=null)parts.push(temperature(c.temperature));
 if(c.feels_like!=null)parts.push('Feels like '+temperature(c.feels_like));
 if(c.humidity!=null)parts.push(Math.round(c.humidity)+'% humidity');
 if(c.wind!=null)parts.push(Math.round(c.wind)+' km/h wind');
 if(c.precipitation!=null)parts.push(c.precipitation>0?'Wet conditions':'Dry conditions');
 if(c.occasion&&c.occasion!=='unknown')parts.push(title(c.occasion));
 if(c.environment&&c.environment!=='unknown')parts.push(title(c.environment));
 return parts.join(' · ')||'Unknown context is excluded.';
}
document.body.insertAdjacentHTML('beforeend','<dialog id="layering-dialog" aria-labelledby="layering-title"><div id="layering-content"></div></dialog><dialog id="pair-feedback-dialog" aria-labelledby="pair-feedback-title"><div id="pair-feedback-content"></div></dialog>');

function layeringSuggestion(rec){
 const option=rec.layering_option;if(!option)return '';
 const r=option.recipe;
 return `<section class="layering-suggestion" aria-label="Optional layering suggestion"><p class="eyebrow">OPTIONAL · BASED ON YOUR PAIRED WEARS</p><h3>${esc(pairName(r))}</h3><p>${esc(option.reason)}</p><p class="fine">${esc(layeringContext(rec.context))}</p><p class="muted">${esc(pairApplication(r))}. Keep the same order and amounts you tested.</p><p class="fine">Both score well on the known individual factors. This is your recorded preference, not a predicted blend score. Unknown conditions are excluded.</p><div class="inline-actions">${rec.mode==='now'?`<button class="primary" data-layer-action="wear-recommended" data-id="${r.id}" ${state.worn.has(rec.id)?'disabled':''}>${state.worn.has(rec.id)?'Wear recorded':'Wear the pair'}</button><button class="secondary" data-action="wear" data-id="${rec.candidates[0].fragrance.id}" ${state.worn.has(rec.id)?'disabled':''}>Wear ${esc(rec.candidates[0].fragrance.name)} alone</button>`:'<p class="muted">Planning ahead · switch to Wear now to log.</p>'}<button class="text-button" data-action="layerings">Your layering recipes</button></div></section>`;
}

async function openLayerings(){
 const d=$('#layering-dialog');
 $('#layering-content').innerHTML=detailHeader('SMALL EXPERIMENTS','Layering')+'<p class="muted" role="status">Loading your recipes…</p>';
 $('#layering-content h2').id='layering-title';if(!d.open)d.showModal();
 try{
   if(state.collection.length)await ensureComparison();
   const data=await api('/layerings');state.layers=data.recipes;state.layerWears=data.wears;
   renderLayerings();
 }catch(e){$('#layering-content').innerHTML=detailHeader('LAYERING','Couldn’t load recipes')+`<p class="error" role="alert">${esc(e.message)}</p><button class="secondary" data-action="layerings">Try again</button>`}
}

function renderLayerings(){
 const choices=state.collection.map(f=>`<option value="${f.id}">${esc(f.brand)} — ${esc(f.name)}</option>`).join('');
 const ideas=state.rec?.layering_experiments||[];
 $('#layering-content').innerHTML=detailHeader('YOUR COLLECTION, TOGETHER','Layering')+`<p class="muted">Single fragrances remain the default. Save a recipe, try it, and record whether it was better than either fragrance alone.</p><details class="layering-rules"><summary>When does a pair appear on Today?</summary><p class="fine">At least three positive wears on three different days in similar weather and time of day. At least 80% of matching reviews must say better together, rate it 4/5 or above, and describe the strength as just right. A new negative review pauses suggestions. Both bottles must individually fit the current context; known observed duration must cover your plans. If the best single fragrance is outside the pair, it needs at least three comparable reviews and a rating at least 0.5 below the pair. No combined fit score is invented.</p></details><div class="section-heading"><h3>Saved recipes</h3><span>${state.layers.length} RECIPES</span></div>${state.layers.map(r=>{const reviewed=state.layerWears.filter(w=>w.layering_id===r.id&&w.feedback).length;return `<article class="layering-recipe"><h3>${esc(pairName(r))}</h3><p>${esc(pairApplication(r))}</p>${r.notes?`<p class="muted">${esc(r.notes)}</p>`:''}<p class="fine">${reviewed?'Reviewed '+reviewed+' times':'Untried · no pairing evidence yet'}${state.rec?.layering_option?.recipe.id===r.id?' · Supported in the current context':''}${!r.available?' · One of these fragrances was removed from your collection':''}</p><div class="inline-actions"><button class="secondary" data-layer-action="wear-experiment" data-id="${r.id}" ${r.available?'':'disabled'}>Log pair wear now</button><button class="text-button danger" data-layer-action="remove" data-id="${r.id}">Remove recipe</button></div></article>`}).join('')||'<p class="muted">No saved recipes yet.</p>'}<div class="section-heading"><h3>Ideas to test</h3><span>EXPERIMENTS, NOT RECOMMENDATIONS</span></div>${ideas.map(i=>{const a=state.collection.find(f=>f.id===i.first_id),b=state.collection.find(f=>f.id===i.second_id);return a&&b?`<article class="layering-recipe"><h3>${esc(a.name)} + ${esc(b.name)}</h3><p class="muted">${esc(i.reason)}</p><button class="text-button" data-layer-action="prefill" data-first="${a.id}" data-second="${b.id}">Set up a test recipe</button></article>`:''}).join('')||'<p class="muted">No clear test ideas from the available scent data. You can save your own combination below.</p>'}<div class="section-heading"><h3>Save a recipe</h3></div>${state.collection.length<2?'<p class="muted">Add at least two fragrances to save a combination.</p>':`<form id="layering-form"><div class="form-grid"><label>Apply first<select name="first_id">${choices}</select></label><label>Sprays of the first<input name="first_sprays" type="number" min="1" max="5" step="1" value="1" required></label><label>Then apply<select name="second_id">${choices}</select></label><label>Sprays of the second<input name="second_sprays" type="number" min="1" max="5" step="1" value="1" required></label></div><label>Why do you want to try it? (optional)<textarea name="notes" rows="2" maxlength="1000" placeholder="What are you hoping this adds?"></textarea></label><p class="fine">The starting amounts are editable test amounts, not a recommendation. A different order or ratio is a different recipe.</p><p class="error" id="layering-error" role="alert"></p><button class="primary">Save test recipe</button></form>`}`;
 $('#layering-content h2').id='layering-title';$('#layering-content h2').tabIndex=-1;$('#layering-content h2').focus({preventScroll:true});$('#layering-dialog').scrollTop=0;const form=$('#layering-form');if(form)form.elements.second_id.selectedIndex=1;
}

function layeringJournal(){
 return `<div class="section-heading"><h3>Layered wears</h3><button class="text-button" data-action="layerings">Explore layering</button></div>${state.layerWears.map(w=>`<article class="journal-item"><div><p class="brand">LAYERED WEAR · ${w.snapshot.recommended?'SUGGESTED RECIPE':'EXPERIMENT'}</p><h3>${esc(pairName(w.snapshot.recipe))}</h3><p class="fine">${esc(pairApplication(w.snapshot.recipe))}</p><small>${temperature(w.snapshot.context.temperature)} · ${esc(title(w.snapshot.context.daypart))}${w.feedback?' · '+w.feedback.rating+'/5 · '+esc(w.feedback.comparison):''}</small></div><div class="journal-date">${esc(date(w.created_at))}<div><button class="secondary" data-layer-action="feedback" data-id="${w.id}">${w.feedback?'Edit pair feedback':'How was the combination?'}</button></div></div></article>`).join('')||'<p class="muted">No layered wears recorded. Experiments stay separate from single-fragrance feedback.</p>'}`;
}

function pairFeedback(id){
 const w=state.layerWears.find(w=>w.id===Number(id));if(!w)return;
 $('#pair-feedback-content').innerHTML=detailHeader('PAIRED WEAR','How did they work together?')+`<p>${esc(pairName(w.snapshot.recipe))}</p><p class="fine">${esc(pairApplication(w.snapshot.recipe))}</p><form id="pair-feedback-form"><input name="id" type="hidden" value="${w.id}"><label>Compared with either fragrance alone<select name="comparison" required><option value="">Choose an outcome</option><option value="better together">Better together than either alone</option><option value="prefer alone">I prefer wearing them alone</option><option value="unsure">Not sure yet</option></select></label><label>Enjoyment (1–5)<input name="rating" type="number" min="1" max="5" step=".5" required></label><label>Combined strength<select name="strength" required><option value="">Choose the combined strength</option><option value="perfect">Just right</option><option value="too strong">Too strong</option><option value="too weak">Too weak</option></select></label><label>Observed longevity (hours, optional)<input name="longevity" type="number" min=".5" max="48" step=".5"></label><label>Notes<textarea name="note" rows="2" maxlength="2000"></textarea></label><p id="pair-feedback-error" class="error" role="alert"></p><button class="primary">Save pair feedback</button></form>`;
 if(w.feedback)for(const [k,v]of Object.entries(w.feedback))if($('#pair-feedback-form').elements[k])$('#pair-feedback-form').elements[k].value=v??'';
 $('#pair-feedback-content h2').id='pair-feedback-title';$('#pair-feedback-dialog').showModal();$('#pair-feedback-dialog').scrollTop=0;
}

document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-layer-action]');if(!button)return;
 const action=button.dataset.layerAction,id=Number(button.dataset.id);
 try{
  if(action==='prefill'){const form=$('#layering-form');form.elements.first_id.value=button.dataset.first;form.elements.second_id.value=button.dataset.second;form.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});form.elements.first_id.focus({preventScroll:true});return}
  if(action==='feedback'){pairFeedback(id);return}
  if(action==='remove'){if(!confirm('Remove this recipe? Its wear history will stay in your journal.'))return;button.disabled=true;await api('/layerings/'+id,'DELETE',{});await refreshData();renderLayerings();return}
  if(action==='wear-experiment'||action==='wear-recommended'){
    button.disabled=true;button.dataset.requestId||=crypto.randomUUID();
    await api('/layerings/'+id+'/wears','POST',{request_id:button.dataset.requestId,...(action==='wear-recommended'?{recommendation_id:state.rec.id}:{})});
    if($('#layering-dialog').open)$('#layering-dialog').close();
    if(action==='wear-recommended'){await hydrate();if(state.page==='home')renderHome()}else await refreshData();toast('Layered wear recorded. Add pair feedback in your journal.');
  }
 }catch(e){const error=$('#layering-error');if($('#layering-dialog').open&&error)error.textContent=e.message;else toast(e.message);button.disabled=false}
});

document.addEventListener('submit',async event=>{
 if(event.target.getAttribute('id')==='layering-form'){
   event.preventDefault();const form=event.target,button=form.querySelector('button.primary');button.disabled=true;
   const data=Object.fromEntries(new FormData(form));for(const k of ['first_id','second_id','first_sprays','second_sprays'])data[k]=Number(data[k]);
   try{await api('/layerings','POST',data);await refreshData();renderLayerings();toast('Test recipe saved. It is not yet a recommendation.')}catch(e){$('#layering-error').textContent=e.message;button.disabled=false}
 }
 if(event.target.getAttribute('id')==='pair-feedback-form'){
   event.preventDefault();const data=Object.fromEntries(new FormData(event.target)),button=event.target.querySelector('button.primary');button.disabled=true;
   try{await api('/layering-wears/'+data.id+'/feedback','POST',data);$('#pair-feedback-dialog').close();await refreshData();toast('Pair feedback saved.')}catch(e){$('#pair-feedback-error').textContent=e.message;button.disabled=false}
 }
});
