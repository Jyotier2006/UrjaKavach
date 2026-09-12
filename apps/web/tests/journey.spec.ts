import {test,expect} from '@playwright/test';
import path from 'node:path';
const shots=path.resolve(__dirname,'../../../..','artifacts/qa');
test('detect → investigate → plan → technician → evidence',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');await expect(page.getByRole('heading',{name:'A clearer view. A healthier fleet.'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Open T-03',exact:true})).toBeVisible();
 await expect(page.locator('canvas').first()).toBeVisible();await page.waitForTimeout(1600);
 await page.screenshot({path:path.join(shots,'fleet-desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'Start guided demo'}).click();await expect(page.getByText('Guided demo · 1 of 7')).toBeVisible();
 await page.getByRole('button',{name:'Next step',exact:true}).click();
 await expect(page.getByText('Signals most associated with this deviation',{exact:false}).first()).toBeVisible();
 await page.getByRole('button',{name:'Close guided demo'}).click();
 await expect(page.getByRole('button',{name:'Reveal outcome',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Reveal outcome',exact:true}).click();
 await page.screenshot({path:path.join(shots,'investigation-desktop.png'),fullPage:true});
 await page.goto('/maintenance/');await expect(page.getByRole('button',{name:'Optimize schedule'})).toBeVisible();
 await page.getByRole('button',{name:'Remove one crew'}).click();
 await expect(page.getByLabel('Available crew count')).toHaveText('1');
 await page.getByRole('button',{name:'Optimize schedule'}).click();
 await expect(page.getByText('Precomputed CP-SAT plan loaded.')).toBeVisible();
 await page.screenshot({path:path.join(shots,'planner-desktop.png'),fullPage:true});
 await page.getByRole('button',{name:'Create work orders',exact:true}).click();
 await page.goto('/tech/');await page.locator('.work-card').filter({hasText:'T-03'}).first().click();
 await page.getByRole('button',{name:'Accept job',exact:true}).click();
 const checks=page.locator('.checklist input');for(let i=0;i<await checks.count();i++)await checks.nth(i).check();
 await page.getByLabel('Findings and handover notes').fill('Demo inspection recorded. Review required before return to service.');
 await page.getByRole('button',{name:'Save notes',exact:true}).click();
 await page.getByRole('button',{name:'Submit for review',exact:true}).click();
 await page.getByRole('button',{name:'Complete demo review',exact:true}).click();
 await expect(page.getByText('Work completed',{exact:true})).toBeVisible();
 await page.reload();await page.getByLabel('Work order filter').selectOption('Completed');
 await expect(page.locator('.work-card').filter({hasText:'T-03'})).toBeVisible();
 await page.goto('/performance/');await expect(page.getByText('No fabricated benchmark results')).toBeVisible();
 expect(errors).toEqual([]);
});

test('all pages render on a phone with no horizontal page overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 const pages=['/','/investigate/','/maintenance/','/solar/','/tech/','/performance/','/manager/','/assumptions/','/about/'];
 for(const url of pages){await page.goto(url);await expect(page.locator('h1')).toBeVisible();await expect(page.locator('.loading')).toHaveCount(0);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),url).toBe(true);if(['/','/tech/','/solar/'].includes(url))await page.screenshot({path:path.join(shots,`mobile-${url==='/'?'fleet':url.split('/')[1]}.png`),fullPage:true});}
 await page.getByRole('button',{name:'Open navigation',exact:true}).click();await expect(page.getByRole('navigation',{name:'Main navigation'})).toBeVisible();await page.getByRole('button',{name:'Close navigation',exact:true}).first().click();
});

test('offline reload and navigation retain the bundled workflow',async({page,context})=>{
 await page.goto('/');await expect(page.locator('canvas').first()).toBeVisible();
 await page.evaluate(async()=>{await navigator.serviceWorker.ready;});
 await expect.poll(()=>page.evaluate(()=>Boolean(navigator.serviceWorker.controller))).toBe(true);
 await page.getByRole('button',{name:'Try offline mode',exact:true}).click();
 await expect(page.getByText('Offline demo data',{exact:true})).toBeVisible();
 await context.setOffline(true);
 await page.reload();await expect(page.locator('h1')).toHaveText('A clearer view. A healthier fleet.');
 await page.goto('/maintenance/');await expect(page.getByRole('button',{name:'Optimize schedule'})).toBeVisible();
 await page.getByRole('button',{name:'Remove one crew'}).click();await page.getByRole('button',{name:'Optimize schedule'}).click();
 await expect(page.getByText('Precomputed CP-SAT plan loaded.')).toBeVisible();
 await page.getByRole('link',{name:'Solar operations',exact:true}).click();await expect(page.locator('h1')).toHaveText('Every panel has potential.');
 await page.goto('/tech/?view=inspection');await expect(page.getByLabel('Upload infrared module image')).toBeAttached();
 await page.getByText('Try a generated illustration').click();await page.locator('.sample-picker button').first().click();
 await expect(page.getByRole('button',{name:'Save inspection to work order',exact:true})).toBeEnabled();
 await context.setOffline(false);
});
