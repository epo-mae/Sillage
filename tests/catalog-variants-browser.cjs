// UI fixtures intentionally describe variants, not real catalog claims.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844}}), requests=[],errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(process.env.SILLAGE_REVIEW_URL||'http://127.0.0.1:8009/');
 await page.locator('#auth:not([hidden])').waitFor();
 if(await page.locator('#name-label').isVisible())await page.locator('[name=name]').first().fill('Reviewer');await page.locator('[name=email]').fill('variants@example.com');await page.locator('[name=password]').fill('review-password');await page.locator('#auth-submit').click();await page.locator('#shell:not([hidden])').waitFor();
 await page.route('**/api/catalog/search?*',async route=>{
   const params=new URL(route.request().url()).searchParams;requests.push(Object.fromEntries(params));
   const pageNumber=Number(params.get('page'));const filtered=params.get('gender');
   const count=filtered?2:pageNumber===1?10:2;
   await route.fulfill({json:{catalog:{name:'fragella',label:'UI fixture catalog',ready:true,evaluation:false,attribution_url:'https://api.fragella.com'},has_more:!filtered&&pageNumber===1,page:pageNumber,results:Array.from({length:count},(_,i)=>({provider:'fragella',external_id:'fixture-'+(pageNumber*10+i),brand:'Fixture Lattafa',name:'Fakhar fixture '+(pageNumber*10+i),gender:filtered?'men':'unisex',year:2021+i,concentration:i%2?'Parfum':'Eau de Parfum',community_rating:{},note_pyramid:{top:[{name:'Apple'},{name:'Ginger'}]}}))}});
 });
 await page.locator('[data-action=add]').first().click();await page.locator('#catalog-query').fill('Fakhar Black');
 await page.waitForFunction(()=>document.querySelectorAll('.catalog-result').length===10);
 assert.equal(await page.locator('#catalog-more').isVisible(),true);
 await page.locator('#catalog-more').click();await page.waitForFunction(()=>document.querySelectorAll('.catalog-result').length===12);
 assert.equal(await page.locator('#catalog-more').isVisible(),false);
 await page.locator('#catalog-brand').fill('Fixture Lattafa');await page.locator('#catalog-gender').selectOption('men,unisex');
 await page.waitForFunction(()=>document.querySelectorAll('.catalog-result').length===2);
 assert.equal(requests.at(-1).brand,'Fixture Lattafa');assert.equal(requests.at(-1).gender,'men,unisex');assert.equal(requests.at(-1).page,'1');
 await page.locator('#catalog-family-hint [data-catalog-query]').click();
 await page.waitForFunction(()=>document.querySelector('#catalog-query').value==='Fakhar');
 assert.equal(await page.locator('#catalog-brand').inputValue(),'Fixture Lattafa');
 await page.screenshot({path:'artifacts/catalog-version-filters-mobile.png',fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'artifacts/catalog-version-filters-desktop.png',fullPage:true});
 await page.locator('[data-catalog-action=manual]').click();
 assert.equal(await page.locator('#fragrance-form [name=name]').inputValue(),'Fakhar');
 assert.equal(await page.locator('#fragrance-form [name=brand]').inputValue(),'Fixture Lattafa');
 assert.deepEqual(errors,[]);console.log('PASS: paginated results, brand and gender filters, family search, manual prefill, mobile and desktop.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
