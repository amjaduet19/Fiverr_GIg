const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = __dirname;

// ---------- Shared brand system ----------
const CSS = `
  * { margin:0; padding:0; box-sizing:border-box; }
  html,body { width:1280px; height:769px; }
  .card{
    position:relative; width:1280px; height:769px; overflow:hidden;
    font-family:'Liberation Sans','DejaVu Sans',Arial,sans-serif;
    color:#fff;
    background:
      radial-gradient(1200px 700px at 78% -10%, #1B3E76 0%, rgba(27,62,118,0) 55%),
      radial-gradient(900px 900px at 8% 120%, #123A6B 0%, rgba(18,58,107,0) 60%),
      linear-gradient(135deg,#0A1B34 0%,#0B2144 55%,#081428 100%);
  }
  /* rising performance chart motif */
  .chart{ position:absolute; inset:0; opacity:.14; }
  .grid{ position:absolute; inset:0; opacity:.06;
    background-image:linear-gradient(#fff 1px,transparent 1px),linear-gradient(90deg,#fff 1px,transparent 1px);
    background-size:64px 64px; }
  .accentbar{ position:absolute; top:0; left:0; width:14px; height:100%;
    background:linear-gradient(180deg,#2F7BFF,#38D9C4); }
  .pad{ position:absolute; inset:0; padding:66px 74px; }

  .brandrow{ display:flex; align-items:center; gap:16px; }
  .logo{ width:56px; height:56px; border-radius:14px; flex:0 0 auto;
    background:linear-gradient(135deg,#2F7BFF,#38D9C4); display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:30px; color:#06132a; box-shadow:0 8px 24px rgba(47,123,255,.45); }
  .brandname{ font-size:24px; font-weight:800; letter-spacing:1.5px; }
  .brandsub{ font-size:14px; letter-spacing:3px; color:#8FA8CE; font-weight:700; text-transform:uppercase; margin-top:2px;}

  .eyebrow{ display:inline-block; font-size:19px; font-weight:800; letter-spacing:3px;
    color:#38D9C4; text-transform:uppercase; }
  .h1{ font-weight:800; line-height:1.02; letter-spacing:-1px; text-transform:uppercase; }
  .muted{ color:#B7C7E4; }

  .trust{ display:inline-flex; align-items:center; gap:14px; padding:12px 22px; border-radius:999px;
    background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.16); backdrop-filter:blur(4px);
    font-weight:800; font-size:20px; letter-spacing:.5px; }
  .stars{ color:#FFC24B; letter-spacing:2px; font-size:20px; }
  .toprated{ background:linear-gradient(135deg,#FFB020,#FF7A00); color:#2a1400; padding:6px 14px; border-radius:8px;
    font-size:15px; font-weight:800; letter-spacing:1px; text-transform:uppercase; }
  .dot{ width:6px;height:6px;border-radius:50%;background:#5B7099; }

  .platforms{ display:flex; gap:14px; align-items:center; }
  .pill{ height:52px; padding:0 20px; border-radius:12px; display:flex; align-items:center; gap:10px;
    background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.14); font-weight:700; font-size:18px; }

  /* photo slot */
  .photo{ position:absolute; right:70px; bottom:0; width:430px; height:660px;
    display:flex; align-items:flex-end; justify-content:center; }
  .photo .halo{ position:absolute; bottom:60px; width:400px; height:400px; border-radius:50%;
    background:radial-gradient(circle,#2F7BFF66 0%,rgba(47,123,255,0) 70%); }
  .photo .frame{ position:relative; width:360px; height:600px; border-radius:24px 24px 0 0;
    background:linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,.02));
    border:2px dashed rgba(255,255,255,.28); border-bottom:none;
    display:flex; flex-direction:column; align-items:center; justify-content:center; gap:18px; }
  .photo .sil{ width:150px; height:150px; opacity:.55; }
  .photo .cap{ font-size:16px; letter-spacing:2px; color:#9FB4D8; font-weight:800; text-transform:uppercase; text-align:center; line-height:1.5;}

  .deliv{ display:flex; align-items:center; gap:20px; margin-top:26px; }
  .ic{ width:60px; height:60px; border-radius:14px; flex:0 0 auto; display:flex; align-items:center; justify-content:center;
    background:linear-gradient(135deg,rgba(47,123,255,.9),rgba(56,217,196,.85)); box-shadow:0 6px 18px rgba(47,123,255,.35);}
  .deliv .t{ font-size:27px; font-weight:800; }
  .deliv .s{ font-size:17px; color:#AFC0DE; margin-top:2px; }

  .stat{ background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14); border-radius:18px;
    padding:24px 20px; text-align:center; }
  .stat .big{ font-size:52px; font-weight:800; background:linear-gradient(135deg,#38D9C4,#2F7BFF);
    -webkit-background-clip:text; background-clip:text; color:transparent; line-height:1; }
  .stat .lab{ font-size:16px; color:#B7C7E4; font-weight:700; margin-top:8px; letter-spacing:.5px; }

  .proc{ display:flex; align-items:center; gap:12px; }
  .step{ padding:12px 18px; border-radius:10px; background:rgba(255,255,255,.07);
    border:1px solid rgba(255,255,255,.14); font-weight:800; font-size:18px; letter-spacing:.5px; }
  .arrow{ color:#38D9C4; font-size:24px; font-weight:800; }
`;

const CHART = `<svg class="chart" viewBox="0 0 1280 769" preserveAspectRatio="none">
  <defs><linearGradient id="g" x1="0" y1="1" x2="0" y2="0">
    <stop offset="0" stop-color="#2F7BFF" stop-opacity="0"/>
    <stop offset="1" stop-color="#38D9C4" stop-opacity="1"/></linearGradient></defs>
  <polyline points="0,690 180,650 360,560 540,600 720,430 900,470 1080,250 1280,120"
    fill="none" stroke="url(#g)" stroke-width="6"/>
  <polygon points="0,690 180,650 360,560 540,600 720,430 900,470 1080,250 1280,120 1280,769 0,769" fill="url(#g)" opacity="0.25"/>
</svg>`;

const SIL = `<svg class="sil" viewBox="0 0 24 24" fill="#9FB4D8"><path d="M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5Zm0 2c-4.4 0-9 2.2-9 5.5V22h18v-2.5C21 16.2 16.4 14 12 14Z"/></svg>`;

const CHECK = `<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#06152e" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5 9.5 18 20 6.5"/></svg>`;

function trustBar(){
  return `<div class="trust"><span class="toprated">Top Rated</span>
    <span class="stars">★★★★★</span><span>4.9</span>
    <span class="dot"></span><span>76 Reviews</span></div>`;
}
function brand(){
  return `<div class="brandrow"><div class="logo">A</div>
    <div><div class="brandname">AMJAD ALI</div><div class="brandsub">Meta Ads Specialist</div></div></div>`;
}
function photoSlot(){
  return `<div class="photo"><div class="halo"></div>
    <div class="frame">${SIL}<div class="cap">Your Photo<br>Goes Here</div></div></div>`;
}

// ---------- Image 1: HERO ----------
const img1 = `<div class="card"><div class="grid"></div>${CHART}<div class="accentbar"></div>
  <div class="pad">
    ${brand()}
    <div style="margin-top:64px;max-width:760px;">
      <span class="eyebrow">Facebook &amp; Instagram Ads</span>
      <div class="h1" style="font-size:78px;margin-top:16px;">Meta Ads That<br>Drive Real <span style="color:#38D9C4;">Sales</span></div>
      <div class="muted" style="font-size:26px;font-weight:600;margin-top:22px;max-width:640px;">
        Campaign setup, laser targeting, retargeting &amp; scaling — built to lower cost and grow ROAS.</div>
      <div style="margin-top:34px;">${trustBar()}</div>
      <div class="platforms" style="margin-top:30px;">
        <div class="pill">Facebook</div><div class="pill">Instagram</div><div class="pill">Meta Business</div>
      </div>
    </div>
    ${photoSlot()}
  </div></div>`;

// ---------- Image 2: WHAT YOU GET ----------
const items = [
  ['Ad Account &amp; Business Manager Setup','Pixel, domains &amp; conversions API configured right'],
  ['Audience Research &amp; Targeting','Data-driven audiences that reach real buyers'],
  ['High-Converting Ad Creatives','Scroll-stopping copy &amp; creative direction'],
  ['Retargeting &amp; Funnel Setup','Win back visitors and turn them into customers'],
  ['Scaling &amp; Clear Reporting','Weekly optimisation and easy-to-read results'],
];
const img2 = `<div class="card"><div class="grid"></div>${CHART}<div class="accentbar"></div>
  <div class="pad">
    <div style="display:flex;justify-content:space-between;align-items:center;">
      ${brand()} ${trustBar()}
    </div>
    <div class="h1" style="font-size:52px;margin-top:34px;">What You <span style="color:#38D9C4;">Get</span></div>
    <div style="margin-top:10px;">
      ${items.map(([t,s])=>`<div class="deliv"><div class="ic">${CHECK}</div>
        <div><div class="t">${t}</div><div class="s">${s}</div></div></div>`).join('')}
    </div>
  </div></div>`;

// ---------- Image 3: WHY ME ----------
const img3 = `<div class="card"><div class="grid"></div>${CHART}<div class="accentbar"></div>
  <div class="pad">
    ${brand()}
    <div class="h1" style="font-size:56px;margin-top:40px;max-width:720px;">Why Businesses<br>Choose <span style="color:#38D9C4;">My Ads</span></div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:22px;max-width:820px;margin-top:40px;">
      <div class="stat"><div class="big">4.9★</div><div class="lab">Average Rating</div></div>
      <div class="stat"><div class="big">76</div><div class="lab">5-Star Reviews</div></div>
      <div class="stat"><div class="big">Top</div><div class="lab">Rated Seller</div></div>
    </div>
    <div style="margin-top:44px;">
      <div class="brandsub" style="margin-bottom:14px;">A Proven Process</div>
      <div class="proc">
        <div class="step">Audit</div><span class="arrow">→</span>
        <div class="step">Setup</div><span class="arrow">→</span>
        <div class="step">Launch</div><span class="arrow">→</span>
        <div class="step">Optimise</div><span class="arrow">→</span>
        <div class="step">Scale</div>
      </div>
    </div>
    ${photoSlot()}
  </div></div>`;

const pages = [
  ['gig1-hero.png', img1],
  ['gig2-what-you-get.png', img2],
  ['gig3-why-me.png', img3],
];

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--no-sandbox','--force-color-profile=srgb'],
  });
  const page = await browser.newPage({ viewport: { width:1280, height:769 }, deviceScaleFactor:2 });
  for (const [file, body] of pages){
    const html = `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${body}</body></html>`;
    await page.setContent(html, { waitUntil:'networkidle' });
    await page.screenshot({ path: path.join(OUT,file), clip:{x:0,y:0,width:1280,height:769} });
    console.log('rendered', file);
  }
  await browser.close();
})();
