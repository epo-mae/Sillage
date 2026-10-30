// Isolated browser review. Uses a separate preview database on port 8001.
const {chromium}=require('C:/Users/Sebas/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}), errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8001/');
 await page.locator('#auth:not([hidden])').waitFor();
 await page.screenshot({path:'artifacts/editorial-welcome.png',fullPage:true});
 await page.locator('[name=name]').first().fill('Alex');
 await page.locator('[name=email]').fill(`review-${Date.now()}@example.com`);
 await page.locator('[name=password]').fill('review-only-password');
 await page.locator('#auth-submit').click();
 await page.locator('#shell:not([hidden])').waitFor();
 await page.evaluate(async()=>{
   const session=await (await fetch('/api/session')).json();
   const headers={'Content-Type':'application/json','X-CSRF-Token':session.csrf};
   const post=(path,data)=>fetch('/api'+path,{method:'POST',headers,body:JSON.stringify(data)}).then(r=>r.json());
   for(const query of ['Sauvage','Black Opium','Terre']){
     const result=await (await fetch('/api/catalog/search?q='+query)).json();
     const items=result.results||result.fragrances||[];
     if(items.length) await post('/collection/from-catalog',{external_id:items[0].external_id,provider:items[0].provider});
   }
   if(!(await (await fetch('/api/collection')).json()).collection.length){
     for(const [brand,name] of [['Review Studio','Cedar No. 4'],['Review Studio','Amber Archive'],['Review Studio','Morning Citrus']])await post('/collection',{brand,name,source:'UI review fixture',family:'Woody',concentration:'EDP',attributes:{freshness:65,warmth:40,projection:45},longevity:7});
   }
 });
 await page.reload();
 await page.locator('.hero-card').waitFor();
 for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});
   for(const view of ['home','collection','journal','settings']){
     await page.locator('nav [data-page='+view+']').click();
     await page.waitForTimeout(180);
     const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
     if(overflow)errors.push(`${view} overflows at ${width}`);
     await page.screenshot({path:`artifacts/editorial-${view}-${width}.png`,fullPage:true});
   }
 }
 await page.locator('nav [data-page=collection]').click();
 await page.locator('[data-action=add]').first().click();
 await page.locator('#catalog-dialog').waitFor({state:'visible'});
 await page.locator('#catalog-query').fill('Sauvage');
 await page.waitForTimeout(800);
 await page.screenshot({path:'artifacts/editorial-search-mobile.png',fullPage:true});
 console.log(JSON.stringify({errors}));
 await browser.close();
 if(errors.length)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
