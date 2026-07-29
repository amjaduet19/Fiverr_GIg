const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const OUT = __dirname;
const PHOTO = 'data:image/png;base64,' + fs.readFileSync(path.join(OUT,'person.png')).toString('base64');

// ---------- Bright brand system ----------
const CSS = `
  *{margin:0;padding:0;box-sizing:border-box;}
  html,body{width:1280px;height:769px;}
  .card{position:relative;width:1280px;height:769px;overflow:hidden;
    font-family:'Liberation Sans','DejaVu Sans',Arial,sans-serif;color:#0E2A4E;
    background:linear-gradient(135deg,#FFFFFF 0%,#EAF2FF 60%,#DCEAFF 100%);}
  .grid{position:absolute;inset:0;opacity:.5;
    background-image:linear-gradient(#2563EB0d 1px,transparent 1px),linear-gradient(90deg,#2563EB0d 1px,transparent 1px);
    background-size:60px 60px;}
  .chart{position:absolute;left:0;bottom:0;width:820px;height:520px;opacity:.10;}

  /* right color panel with diagonal edge + person */
  .panel{position:absolute;top:0;right:0;width:560px;height:100%;
    background:linear-gradient(160deg,#2F6BFF 0%,#1E50E6 55%,#1B3Fc8 100%);
    clip-path:polygon(20% 0,100% 0,100% 100%,0% 100%);}
  .panel .blob{position:absolute;right:-60px;top:-60px;width:360px;height:360px;border-radius:50%;
    background:radial-gradient(circle,#FFFFFF22,transparent 70%);}
  .panel .blob2{position:absolute;right:120px;bottom:80px;width:220px;height:220px;border-radius:50%;
    background:radial-gradient(circle,#FF7A2E44,transparent 70%);}
  .person{position:absolute;right:6px;bottom:0;height:742px;width:auto;z-index:3;
    filter:drop-shadow(0 20px 34px rgba(9,30,70,.35));}
  .ring{position:absolute;right:70px;bottom:60px;width:430px;height:430px;border-radius:50%;
    border:2px dashed #FFFFFF55;z-index:2;}
  .pfade{position:absolute;right:0;bottom:0;width:560px;height:150px;z-index:4;pointer-events:none;
    background:linear-gradient(0deg,#1B3FC8 0%,#1E50E6 35%,rgba(30,80,230,0) 100%);
    clip-path:polygon(20% 0,100% 0,100% 100%,0% 100%);}

  .pad{position:absolute;inset:0;padding:60px 70px;z-index:4;}
  .brandrow{display:flex;align-items:center;gap:15px;}
  .logo{width:54px;height:54px;border-radius:14px;flex:0 0 auto;display:flex;align-items:center;justify-content:center;
    background:linear-gradient(135deg,#2F6BFF,#FF7A2E);color:#fff;font-weight:800;font-size:29px;
    box-shadow:0 8px 20px rgba(47,107,255,.35);}
  .bn{font-size:23px;font-weight:800;letter-spacing:1px;color:#0E2A4E;}
  .bs{font-size:13px;letter-spacing:3px;color:#2F6BFF;font-weight:800;text-transform:uppercase;margin-top:2px;}

  .eyebrow{display:inline-block;font-size:18px;font-weight:800;letter-spacing:3px;color:#FF7A2E;text-transform:uppercase;}
  .h1{font-weight:800;line-height:1.02;letter-spacing:-1px;text-transform:uppercase;color:#0E2A4E;}
  .accent{color:#2F6BFF;}
  .accent2{color:#FF7A2E;}
  .muted{color:#54648A;}

  .trust{display:inline-flex;align-items:center;gap:13px;padding:13px 22px;border-radius:14px;background:#fff;
    box-shadow:0 12px 30px rgba(20,50,110,.14);font-weight:800;font-size:19px;color:#0E2A4E;}
  .toprated{background:linear-gradient(135deg,#FF9A2E,#FF6A1F);color:#fff;padding:6px 13px;border-radius:8px;
    font-size:14px;font-weight:800;letter-spacing:1px;text-transform:uppercase;}
  .stars{color:#FFB020;letter-spacing:2px;}
  .dot{width:6px;height:6px;border-radius:50%;background:#B9C6DE;}

  .pill{height:50px;padding:0 20px;border-radius:12px;display:flex;align-items:center;background:#fff;
    box-shadow:0 8px 20px rgba(20,50,110,.10);font-weight:700;font-size:17px;color:#1B2E52;}

  .deliv{display:flex;align-items:center;gap:20px;margin-top:24px;}
  .ic{width:58px;height:58px;border-radius:14px;flex:0 0 auto;display:flex;align-items:center;justify-content:center;
    background:linear-gradient(135deg,#2F6BFF,#5AA0FF);box-shadow:0 8px 18px rgba(47,107,255,.30);}
  .deliv .t{font-size:26px;font-weight:800;color:#0E2A4E;}
  .deliv .s{font-size:16px;color:#5B6B88;margin-top:2px;}

  .stat{background:#fff;border-radius:18px;padding:22px 18px;text-align:center;
    box-shadow:0 12px 30px rgba(20,50,110,.12);}
  .stat .big{font-size:50px;font-weight:800;color:#2F6BFF;line-height:1;}
  .stat .lab{font-size:15px;color:#54648A;font-weight:700;margin-top:8px;}

  .step{padding:11px 17px;border-radius:10px;background:#fff;box-shadow:0 8px 18px rgba(20,50,110,.10);
    font-weight:800;font-size:17px;color:#1B2E52;}
  .arrow{color:#FF7A2E;font-size:22px;font-weight:800;}
`;

const CHART = `<svg class="chart" viewBox="0 0 820 520" preserveAspectRatio="none">
  <defs><linearGradient id="g" x1="0" y1="1" x2="1" y2="0">
    <stop offset="0" stop-color="#2F6BFF"/><stop offset="1" stop-color="#00C2A8"/></linearGradient></defs>
  <polyline points="0,470 130,430 260,360 390,395 520,250 650,290 820,80" fill="none" stroke="url(#g)" stroke-width="7"/>
  <polygon points="0,470 130,430 260,360 390,395 520,250 650,290 820,80 820,520 0,520" fill="url(#g)" opacity="0.25"/>
</svg>`;
const CHECK = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9.5 18 20 6.5"/></svg>`;

const brand = ()=>`<div class="brandrow"><div class="logo">A</div><div><div class="bn">AMJAD ALI</div><div class="bs">Meta Ads Specialist</div></div></div>`;
const trust = ()=>`<div class="trust"><span class="toprated">Top Rated</span><span class="stars">★★★★★</span><span>4.9</span><span class="dot"></span><span>76 Reviews</span></div>`;
const panel = ()=>`<div class="panel"><div class="blob"></div><div class="blob2"></div></div><div class="ring"></div><img class="person" src="${PHOTO}"><div class="pfade"></div>`;

// Image 1 — HERO
const img1 = `<div class="card"><div class="grid"></div>${CHART}${panel()}
  <div class="pad">
    ${brand()}
    <div style="margin-top:66px;max-width:640px;">
      <span class="eyebrow">Facebook &amp; Instagram Ads</span>
      <div class="h1" style="font-size:70px;margin-top:14px;">Meta Ads That<br>Drive Real <span class="accent2">Sales</span></div>
      <div class="muted" style="font-size:24px;font-weight:600;margin-top:20px;max-width:540px;">
        Campaign setup, laser targeting, retargeting &amp; scaling — built to cut cost and grow ROAS.</div>
      <div style="margin-top:30px;">${trust()}</div>
      <div style="display:flex;gap:13px;margin-top:24px;">
        <div class="pill">Facebook</div><div class="pill">Instagram</div><div class="pill">Meta Business</div>
      </div>
    </div>
  </div></div>`;

// Image 2 — WHAT YOU GET
const items=[
  ['Ad Account &amp; Business Manager Setup','Pixel, domains &amp; Conversions API done right'],
  ['Audience Research &amp; Targeting','Data-driven audiences that reach real buyers'],
  ['High-Converting Ad Creatives','Scroll-stopping copy &amp; creative direction'],
  ['Retargeting &amp; Funnel Building','Win back visitors and turn them into customers'],
  ['Scaling &amp; Clear Reporting','Weekly optimisation and easy-to-read results'],
];
const img2 = `<div class="card"><div class="grid"></div>${CHART}${panel()}
  <div class="pad">
    ${brand()}
    <div class="h1" style="font-size:46px;margin-top:26px;">What You <span class="accent">Get</span></div>
    <div style="margin-top:6px;">
      ${items.map(([t,s])=>`<div class="deliv"><div class="ic">${CHECK}</div><div><div class="t">${t}</div><div class="s">${s}</div></div></div>`).join('')}
    </div>
  </div></div>`;

// Image 3 — WHY ME
const img3 = `<div class="card"><div class="grid"></div>${CHART}${panel()}
  <div class="pad">
    ${brand()}
    <div class="h1" style="font-size:50px;margin-top:34px;max-width:600px;">Why Businesses<br>Choose <span class="accent">My Ads</span></div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;max-width:590px;margin-top:34px;">
      <div class="stat"><div class="big">4.9★</div><div class="lab">Average Rating</div></div>
      <div class="stat"><div class="big">76</div><div class="lab">5-Star Reviews</div></div>
      <div class="stat"><div class="big">Top</div><div class="lab">Rated Seller</div></div>
    </div>
    <div style="margin-top:40px;">
      <div class="bs" style="margin-bottom:12px;">A Proven Process</div>
      <div style="display:flex;align-items:center;gap:10px;">
        <div class="step">Audit</div><span class="arrow">→</span>
        <div class="step">Setup</div><span class="arrow">→</span>
        <div class="step">Launch</div><span class="arrow">→</span>
        <div class="step">Optimise</div><span class="arrow">→</span>
        <div class="step">Scale</div>
      </div>
    </div>
  </div></div>`;

const pages=[['gig1-hero.png',img1],['gig2-what-you-get.png',img2],['gig3-why-me.png',img3]];
(async()=>{
  const browser=await chromium.launch({executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',args:['--no-sandbox','--force-color-profile=srgb']});
  const page=await browser.newPage({viewport:{width:1280,height:769},deviceScaleFactor:2});
  for(const [f,b] of pages){
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${b}</body></html>`,{waitUntil:'networkidle'});
    await page.screenshot({path:path.join(OUT,f),clip:{x:0,y:0,width:1280,height:769}});
    console.log('rendered',f);
  }
  await browser.close();
})();
