import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
const require = createRequire(import.meta.url);
const {chromium} = require('../apps/dashboard/node_modules/playwright');
const directory = 'docs/audits/2026-10-28';
await mkdir(directory, {recursive: true});
const browser = await chromium.launch(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? {executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE} : {});
const page = await browser.newPage();
const base = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3187';
await page.goto(base + '/login');
await page.getByRole('button', {name: 'Use demo credentials'}).click();
await page.getByRole('button', {name: 'Sign in to workspace'}).click();
await page.getByRole('heading', {name: 'Overview', exact: true}).waitFor();
await page.getByText('Connecting to your workspace…').waitFor({state:'hidden'});
const results = [];
for (const viewport of [{width:1440,height:900},{width:1366,height:768},{width:1280,height:720},{width:1024,height:600},{width:390,height:844}]) {
 await page.setViewportSize(viewport);
 await page.goto(base + '/');
 await page.getByText('Connecting to your workspace…').waitFor({state:'hidden'});
 await page.evaluate(() => document.fonts.ready);
 const measurements = await page.evaluate(() => {
   const rect = selector => {const element=document.querySelector(selector), box=element.getBoundingClientRect(), style=getComputedStyle(element); return {top:box.top,bottom:box.bottom,left:box.left,right:box.right,height:box.height,clientHeight:element.clientHeight,scrollHeight:element.scrollHeight,overflowY:style.overflowY,fullyVisible:box.top>=0&&box.bottom<=innerHeight&&box.left>=0&&box.right<=innerWidth};};
   const rgba = color => (color.match(/[\d.]+/g)||[]).map(Number);
   const blend = (foreground, background) => {const alpha=foreground[3]??1;return foreground.slice(0,3).map((v,i)=>v*alpha+background[i]*(1-alpha));};
   const luminance = rgb => rgb.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
   const background = element => {const stack=[];for(let e=element;e;e=e.parentElement)stack.push(rgba(getComputedStyle(e).backgroundColor));return stack.reverse().reduce((bg,fg)=>fg.length?blend(fg,bg):bg,[255,255,255]);};
   const contrast=[];
   for(const e of document.querySelectorAll('main *, .sidebar *, .topbar *')) {
     if(![...e.childNodes].some(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim()))continue;
     const box=e.getBoundingClientRect(),s=getComputedStyle(e);
     if(!box.width||!box.height||s.visibility==='hidden'||s.display==='none'||e.closest('.logo'))continue;
     const bg=background(e),fg=blend(rgba(s.color),bg),a=luminance(fg),b=luminance(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
     const size=parseFloat(s.fontSize),large=size>=24||(size>=18.66&&parseInt(s.fontWeight)>=700),required=large?3:4.5;
     if(ratio<required)contrast.push({text:e.textContent.trim().slice(0,85),selector:e.tagName.toLowerCase()+'.'+[...e.classList].join('.'),color:s.color,background:bg.map(Math.round),size,ratio:Number(ratio.toFixed(2)),required});
   }
   return {sidebar:rect('.sidebar'),bottom:rect('.sidebar-bottom'),userMenu:rect('.user-menu'),signOut:rect('button[aria-label="Sign out"]'),documentOverflow:document.documentElement.scrollWidth>innerWidth,contrastFailures:contrast};
 });
 results.push({viewport,...measurements});
 await page.screenshot({path:`${directory}/overview-${viewport.width}x${viewport.height}.png`,fullPage:false});
}
await page.setViewportSize({width:1440,height:900});
for(const route of ['playground','plans','providers','customers','settings']) {
 await page.goto(base + '/' + route); await page.getByText('Connecting to your workspace…').waitFor({state:'hidden'});
 await page.screenshot({path:`${directory}/${route}.png`,fullPage:true});
}
await writeFile(`${directory}/ui-measurements.json`,JSON.stringify(results,null,2)+'\n');
console.log(JSON.stringify(results.map(r=>({viewport:r.viewport,signOutVisible:r.signOut.fullyVisible,signOutBottom:r.signOut.bottom,sidebarScrollHeight:r.sidebar.scrollHeight,sidebarHeight:r.sidebar.clientHeight,overflow:r.sidebar.overflowY,contrastFailures:r.contrastFailures.length,examples:r.contrastFailures.slice(0,5)})),null,2));
await browser.close();
