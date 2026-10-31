// Uses a fresh isolated preview with 9°C fixture weather, never a real collection.
const {chromium}=require('C:/Users/Sebas/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.SILLAGE_REVIEW_URL||'http://127.0.0.1:8015/');
 await page.locator('#name-label').waitFor();await page.locator('[name=name]').first().fill('Review');await page.locator('[name=email]').fill('priorities@example.com');await page.locator('[name=password]').fill('review-password');await page.locator('#auth-submit').click();await page.locator('#shell:not([hidden])').waitFor();
 await page.evaluate(async()=>{const {csrf}=await(await fetch('/api/session')).json();for(const [name,rating,longevity] of [['Favorite',5,2],['Long lasting',2,12]])await fetch('/api/collection',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({brand:'UI fixture',name,rating,longevity,attributes:{projection:50}})})});
 await page.reload();await page.locator('.hero-card').waitFor();
 const historyCount=await page.evaluate(async()=>(await(await fetch('/api/history')).json()).recommendations.length);
 await page.locator('nav [data-page=settings]').click();await page.locator('.priority-result').first().waitFor();
 await page.locator('.priority-result').first().locator('summary').first().click();assert.match(await page.locator('.priority-result').first().innerText(),/Excluded/);
 await page.screenshot({path:'artifacts/priorities-desktop.png',fullPage:true});
 async function only(key){await page.evaluate(key=>{for(const check of document.querySelectorAll('[name^=priority_enabled_]'))check.checked=check.name==='priority_enabled_'+key;document.querySelector('[name=priority_'+key+']').value='10';document.querySelector('[name=priority_'+key+']').dispatchEvent(new Event('input',{bubbles:true}))},key)}
 await only('preference');await page.waitForFunction(()=>document.querySelector('.priority-result h3')?.textContent==='Favorite');
 await only('longevity');await page.waitForFunction(()=>document.querySelector('.priority-result h3')?.textContent==='Long lasting');
 const after=await page.evaluate(async()=>(await(await fetch('/api/history')).json()).recommendations.length);assert.equal(after,historyCount);
 await page.getByRole('button',{name:'Weather first',exact:true}).click();assert.equal(await page.locator('[name=priority_temperature]').inputValue(),'10');
 await only('preference');await page.waitForFunction(()=>document.querySelector('.priority-result h3')?.textContent==='Favorite');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'artifacts/priorities-mobile.png',fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.getByRole('button',{name:'Save these priorities',exact:true}).click();await page.locator('#priority-save-status').filter({hasText:'Priorities saved'}).waitFor();
 const prefs=await page.evaluate(async()=>(await(await fetch('/api/session')).json()).user.preferences);assert.equal(prefs.importance.preference,10);assert.equal(prefs.importance.temperature,0);
 await page.locator('nav [data-page=collection]').click();const favorite=page.locator('.collection-card').filter({has:page.getByRole('heading',{name:'Favorite',exact:true})});await favorite.getByRole('button',{name:'Edit',exact:true}).click();await page.locator('#fragrance-form [name=min_temperature]').fill('12');await page.locator('#fragrance-form button[type=submit]').click();await page.waitForFunction(()=>!document.querySelector('#editor').open);
 await page.locator('nav [data-page=home]').click();await page.locator('.hero-card').waitFor();assert.equal(await page.locator('.hero-info h2').innerText(),'Long lasting');
 await page.locator('nav [data-page=collection]').click();await page.getByRole('button',{name:'Compare all',exact:true}).click();await page.locator('.comparison-item').filter({has:page.getByRole('heading',{name:'Favorite',exact:true})}).getByRole('button').click();await page.locator('.judgement-limits').waitFor();assert.match(await page.locator('.judgement-limits').innerText(),/12°C/);await page.screenshot({path:'artifacts/judging-boundary-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS: live ranking changes, presets, real shares, no journal writes, saved priorities, mobile layout, personal boundary override.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
