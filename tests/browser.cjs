// Run with SILLAGE_PLAYWRIGHT set to a local Playwright package path when needed.
const { chromium }=require(process.env.SILLAGE_PLAYWRIGHT||'playwright');
const { spawn }=require('child_process');
const fs=require('fs');const path=require('path');const assert=require('assert');
const root=path.resolve(__dirname,'..'), database=path.join(root,'data','browser-test.db');
const server=spawn(path.join(root,'.venv','Scripts','python.exe'),['run.py'],{cwd:root,env:{...process.env,SILLAGE_PORT:'8001',SILLAGE_DATABASE:database,SILLAGE_FRAGRANCE_PROVIDER:'sample'},stdio:'pipe',windowsHide:true});
const output=path.join(root,'artifacts');fs.mkdirSync(output,{recursive:true});
(async()=>{let browser;
 try{
  for(let i=0;i<30;i++){try{if((await fetch('http://127.0.0.1:8001/api/session')).ok)break}catch{}await new Promise(r=>setTimeout(r,200))}
  browser=await chromium.launch({headless:true,channel:process.env.SILLAGE_BROWSER||'msedge'});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8001');await page.getByRole('heading',{name:'Make yourself at home.'}).waitFor();await page.screenshot({path:path.join(output,'welcome-desktop.png'),fullPage:true});
  await page.getByLabel('Your name').fill('Example Tester');await page.getByLabel('Email',{exact:true}).fill('browser-'+Date.now()+'@example.test');await page.getByLabel('Password',{exact:false}).fill('browser-test-password');await page.getByRole('button',{name:'Create your account'}).click();
  await page.getByRole('heading',{name:'Meet your collection.'}).waitFor();
  await page.getByRole('button',{name:'Add your first fragrance'}).click();
  await page.getByRole('button',{name:'Can’t find it? Add manually',exact:false}).click();
  await page.getByLabel('Brand',{exact:true}).fill('Fictional Studio');await page.getByLabel('Fragrance name',{exact:true}).fill('Test Cedar');await page.getByText('Optional details & metadata overrides',{exact:false}).click();await page.getByLabel('Longevity estimate (hours)').fill('7');await page.getByRole('dialog').getByLabel('Personal rating (1–5)').fill('4');
  await page.getByText('Scent & performance attributes',{exact:false}).click();await page.getByLabel('Warmth',{exact:true}).fill('60');await page.getByLabel('Freshness',{exact:true}).fill('45');await page.getByLabel('Projection',{exact:true}).fill('40');await page.getByLabel('Casual',{exact:true}).check();
  await page.getByRole('button',{name:'Save fragrance'}).click();await page.getByRole('heading',{name:'Test Cedar',exact:true}).waitFor();
  await page.getByRole('button',{name:'Why this one?'}).click();await page.getByRole('heading',{name:/Why .*%/}).waitFor();await page.getByRole('dialog').getByRole('button',{name:'Close',exact:true}).click();
  await page.getByRole('button',{name:'Wear this fragrance',exact:false}).click();await page.getByRole('button',{name:'Wear recorded'}).waitFor();
  await page.getByRole('button',{name:'Wear journal',exact:false}).click();await page.getByRole('button',{name:'How did it wear?'}).click();await page.getByLabel('How long did it last? (hours)').fill('8');await page.getByRole('button',{name:'Save reflection'}).click();await page.getByRole('button',{name:'Edit reflection'}).waitFor();
  await page.getByRole('button',{name:'My collection',exact:false}).click();await page.getByRole('button',{name:'View fragrance'}).click();await page.getByRole('button',{name:'Edit details'}).click();await page.getByLabel('Fragrance name',{exact:true}).fill('Test Cedar Edited');await page.getByRole('button',{name:'Save fragrance'}).click();await page.getByRole('heading',{name:'Test Cedar Edited'}).waitFor();
  await page.getByRole('button',{name:'Preferences',exact:false}).click();await page.getByLabel('Location label').fill('Auckland');await page.getByLabel('Latitude',{exact:true}).fill('-36.85');await page.getByLabel('Longitude',{exact:true}).fill('174.76');await page.getByRole('button',{name:'Save preferences'}).click();await page.getByRole('heading',{name:'Make it personal.'}).waitFor();
  await page.getByRole('button',{name:'For you'}).click();await page.getByRole('heading',{name:'Test Cedar Edited',exact:true}).waitFor({timeout:20000});await page.screenshot({path:path.join(output,'recommendation-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'recommendation-mobile.png'),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Mobile layout overflows');
  await page.getByRole('button',{name:'Preferences',exact:false}).click();await page.getByRole('button',{name:'Sign out'}).click();await page.getByRole('button',{name:'Already have an account? Sign in'}).waitFor();assert.deepStrictEqual(errors,[]);console.log('Browser checks passed: registration, add/edit fragrance, score detail, wear, feedback, settings, logout, desktop and mobile.');
 }finally{if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1});
