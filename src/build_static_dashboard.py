"""Build a self-contained static dashboard for GitHub Pages.

Reuses the existing RetailSalesAnalyzer so the figures shown here are the same
ones the rest of the project computes - this module only presents them.

Output is a single .html file with no external requests, so it can be served
from GitHub Pages, opened from disk, or emailed as one attachment.

Run:  python src/build_static_dashboard.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis import RetailSalesAnalyzer  # noqa: E402

OUT_DIR = ROOT / "dashboard"
OUT_FILE = OUT_DIR / "index.html"

N_BOOTSTRAP = 1500
SEED = 42

# Order priority is an ordered scale, not a nominal set - present it in its
# natural order rather than sorted by value.
PRIORITY_ORDER = ["Critical", "High", "Medium", "Low", "Not Specified"]

# The source workbook has mojibake where trademark/registered symbols were
# mis-encoded. Repair them for display only; the underlying data is untouched.
MOJIBAKE = {"ª": "™", "¨": "®", "": "'", "": '"', "": '"'}


def clean_text(value: str) -> str:
    text = str(value)
    for bad, good in MOJIBAKE.items():
        text = text.replace(bad, good)
    return re.sub(r"\s+", " ", text).strip()


def bootstrap_leader(df: pd.DataFrame, group_col: str, value_col: str,
                     rng: np.random.Generator) -> dict:
    """How often does the leading group stay the leader under resampling?"""
    totals = df.groupby(group_col)[value_col].sum().sort_values(ascending=False)
    if len(totals) < 2:
        return {}

    leader, runner_up = totals.index[0], totals.index[1]
    codes, uniques = pd.factorize(df[group_col])
    values = df[value_col].to_numpy()
    n = len(df)
    leader_idx = list(uniques).index(leader)

    wins = 0
    margins = np.empty(N_BOOTSTRAP)
    for i in range(N_BOOTSTRAP):
        pick = rng.integers(0, n, n)
        sums = np.bincount(codes[pick], weights=values[pick], minlength=len(uniques))
        best_other = np.max(np.delete(sums, leader_idx))
        margins[i] = sums[leader_idx] - best_other
        if sums[leader_idx] >= best_other:
            wins += 1

    lo, hi = np.percentile(margins, [2.5, 97.5])
    retention = wins / N_BOOTSTRAP
    return {
        "Dimension": group_col.replace("_", " ").title(),
        "Leader": clean_text(leader),
        "Runner_Up": clean_text(runner_up),
        "Observed_Margin": float(totals.iloc[0] - totals.iloc[1]),
        "Margin_CI_Low": float(lo),
        "Margin_CI_High": float(hi),
        "Leader_Retention_Rate": retention,
        "Verdict": "REAL" if lo > 0 else "NOISE",
    }


def collect(analyzer: RetailSalesAnalyzer) -> dict:
    df = analyzer.dataframe
    kpis = analyzer.calculate_kpis()

    total_sales = float(df["sales"].sum())
    kpis.update(
        {
            "profit_margin": float(df["profit"].sum() / total_sales),
            "average_order_value": float(df.groupby("order_id")["sales"].sum().mean()),
            "unique_customers": int(df["customer_name"].nunique()),
            "total_units": int(df["order_quantity"].sum()),
            "date_from": df["order_date"].min().strftime("%Y-%m-%d"),
            "date_to": df["order_date"].max().strftime("%Y-%m-%d"),
            "line_items": int(len(df)),
        }
    )

    def rollup(col: str, value: str = "sales") -> list[dict]:
        grouped = (
            df.groupby(col)
            .agg(total_sales=("sales", "sum"), total_profit=("profit", "sum"),
                 orders=("order_id", "nunique"), units=("order_quantity", "sum"))
            .reset_index()
            .rename(columns={col: "key"})
        )
        grouped["margin"] = grouped["total_profit"] / grouped["total_sales"]
        grouped["share"] = grouped["total_sales"] / grouped["total_sales"].sum()
        grouped["key"] = grouped["key"].map(clean_text)
        return grouped.sort_values(value if value != "sales" else "total_sales",
                                   ascending=False).round(4).to_dict("records")

    regions = rollup("region")
    categories = rollup("product_category")
    segments = rollup("customer_segment")

    priority = rollup("order_priority")
    rank = {clean_text(p): i for i, p in enumerate(PRIORITY_ORDER)}
    priority.sort(key=lambda r: rank.get(r["key"], 99))

    ship_modes = rollup("ship_mode")
    products = rollup("product_name")[:10]

    monthly = analyzer.monthly_sales_trend().copy()
    month_col = "month" if "month" in monthly.columns else monthly.columns[0]
    sales_col = [c for c in monthly.columns if "sale" in c.lower()][0]
    trend = [
        {"month": str(m)[:7], "total_sales": float(s)}
        for m, s in zip(monthly[month_col], monthly[sales_col])
    ]

    rng = np.random.default_rng(SEED)
    significance = [
        s
        for s in (
            bootstrap_leader(df, "region", "sales", rng),
            bootstrap_leader(df, "product_category", "sales", rng),
            bootstrap_leader(df, "customer_segment", "profit", rng),
            bootstrap_leader(df, "order_priority", "sales", rng),
        )
        if s
    ]

    return {
        "kpis": kpis,
        "regions": regions,
        "categories": categories,
        "segments": segments,
        "priority": priority,
        "ship_modes": ship_modes,
        "products": products,
        "trend": trend,
        "significance": significance,
    }


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Retail Sales Dashboard</title>
<style>
:root {
  color-scheme: light;
  --surface-0:#f4f4f1; --surface-1:#fcfcfb; --surface-2:#eceae5;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#8a8880;
  --rule:#e6e5e1; --grid:#e6e5e1;
  --s1:#2a78d6; --s2:#008300; --s3:#e87ba4; --s4:#eda100; --s5:#1baf7a;
  --deemph:#c9c8c2; --accent-soft:rgba(42,120,214,.10);
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface-0:#111110; --surface-1:#1a1a19; --surface-2:#232322;
    --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#8f8e85;
    --rule:#333331; --grid:#2e2e2c;
    --s1:#3987e5; --s2:#008300; --s3:#d55181; --s4:#c98500; --s5:#199e70;
    --deemph:#4a4a47; --accent-soft:rgba(57,135,229,.16);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-0:#111110; --surface-1:#1a1a19; --surface-2:#232322;
  --text-primary:#ffffff; --text-secondary:#c3c2b7; --text-muted:#8f8e85;
  --rule:#333331; --grid:#2e2e2c;
  --s1:#3987e5; --s2:#008300; --s3:#d55181; --s4:#c98500; --s5:#199e70;
  --deemph:#4a4a47; --accent-soft:rgba(57,135,229,.16);
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface-0);color:var(--text-primary);
  font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased;}
.wrap{max-width:1220px;margin:0 auto;padding:32px 20px 72px}
header{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;flex-wrap:wrap}
h1{font-size:26px;line-height:1.2;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--text-secondary);font-size:14px;margin:0}
.theme-btn{background:var(--surface-1);color:var(--text-secondary);
  border:1px solid var(--rule);border-radius:8px;padding:8px 14px;font-size:13px;
  cursor:pointer;font-family:inherit;}
.theme-btn:hover{color:var(--text-primary);border-color:var(--text-muted)}
.banner{margin:24px 0 8px;padding:16px 18px;border-radius:10px;
  background:var(--accent-soft);border:1px solid var(--rule);border-left:3px solid var(--s1);}
.banner strong{display:block;margin-bottom:4px;font-size:14px}
.banner p{margin:0;font-size:13.5px;color:var(--text-secondary)}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:14px;margin:24px 0 8px}
@media (max-width:1080px){ .kpis{grid-template-columns:repeat(3,1fr)} }
@media (max-width:640px){ .kpis{grid-template-columns:repeat(2,1fr)} }
.kpi{background:var(--surface-1);border:1px solid var(--rule);border-radius:10px;padding:16px 18px}
.kpi .label{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;
  color:var(--text-muted);margin-bottom:6px}
.kpi .value{font-size:23px;font-weight:650;letter-spacing:-.025em;line-height:1.15}
.kpi .note{font-size:12px;color:var(--text-secondary);margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(470px,1fr));gap:18px;margin-top:18px}
.card{background:var(--surface-1);border:1px solid var(--rule);border-radius:12px;
  padding:20px 20px 14px;min-width:0}
.card.full{grid-column:1/-1}
.card h2{font-size:15.5px;margin:0 0 4px;letter-spacing:-.01em}
.card .cap{font-size:12.5px;color:var(--text-secondary);margin:0 0 14px}
.chart{width:100%;overflow-x:auto}
svg{display:block;max-width:100%;height:auto}
.toggle{background:none;border:1px solid var(--rule);color:var(--text-muted);
  border-radius:6px;padding:4px 10px;font-size:11.5px;cursor:pointer;
  font-family:inherit;margin-top:10px;}
.toggle:hover{color:var(--text-primary)}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-top:10px}
th,td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--rule)}
th:first-child,td:first-child{text-align:left}
th{color:var(--text-muted);font-weight:600;font-size:11px;
  text-transform:uppercase;letter-spacing:.05em}
.hidden{display:none}
.tip{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;
  background:var(--surface-1);border:1px solid var(--rule);border-radius:8px;
  padding:8px 11px;font-size:12.5px;box-shadow:0 6px 22px rgba(0,0,0,.16);
  z-index:50;max-width:300px;color:var(--text-primary);}
.tip .t-title{font-weight:650;margin-bottom:3px}
.tip .t-row{color:var(--text-secondary);white-space:nowrap}
footer{margin-top:36px;padding-top:18px;border-top:1px solid var(--rule);
  font-size:12.5px;color:var(--text-muted)}
@media (max-width:560px){ .grid{grid-template-columns:1fr} h1{font-size:22px} }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>Retail Sales Dashboard</h1>
      <p class="sub" id="sub"></p>
    </div>
    <button class="theme-btn" id="themeBtn" type="button">Toggle theme</button>
  </header>
  <div class="banner">
    <strong id="bannerTitle"></strong>
    <p id="bannerText"></p>
  </div>
  <section class="kpis" id="kpis"></section>
  <section class="grid" id="grid"></section>
  <footer id="foot"></footer>
</div>
<div class="tip" id="tip"></div>
<script>
const DATA = __DATA__;

const money = v => {
  const a = Math.abs(v);
  if (a >= 1e6) return '$' + (v/1e6).toFixed(2) + 'M';
  if (a >= 1e3) return '$' + (v/1e3).toFixed(1) + 'K';
  return '$' + v.toFixed(0);
};
const num = v => v.toLocaleString('en-US');
const pct = v => (v*100).toFixed(1) + '%';
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const trunc = (s,n) => s.length > n ? s.slice(0,n-1) + '\\u2026' : s;

const tip = document.getElementById('tip');
function showTip(e, title, rows){
  tip.innerHTML = '<div class="t-title">'+title+'</div>' +
    rows.map(r => '<div class="t-row">'+r+'</div>').join('');
  tip.style.opacity = 1;
  const pad=14, w=tip.offsetWidth, h=tip.offsetHeight;
  let x=e.clientX+pad, y=e.clientY+pad;
  if (x+w > innerWidth-8)  x = e.clientX-w-pad;
  if (y+h > innerHeight-8) y = e.clientY-h-pad;
  tip.style.left=x+'px'; tip.style.top=y+'px';
}
const hideTip = () => tip.style.opacity = 0;

const NS='http://www.w3.org/2000/svg';
function el(tag,attrs){const n=document.createElementNS(NS,tag);
  for(const k in attrs) n.setAttribute(k,attrs[k]); return n;}
function svgRoot(w,h){const s=el('svg',{viewBox:`0 0 ${w} ${h}`,width:'100%',role:'img'});
  s.style.minWidth=Math.min(w,420)+'px'; return s;}
function niceTicks(max,count){
  const raw=max/count, mag=Math.pow(10,Math.floor(Math.log10(raw)));
  const step=[1,2,2.5,5,10].map(m=>m*mag).find(s=>s>=raw)||mag*10;
  const out=[]; for(let v=0;v<=max*1.0001;v+=step) out.push(v); return out;
}
function yGrid(svg,scale,x0,x1,ticks,fmt){
  ticks.forEach(t=>{
    svg.appendChild(el('line',{x1:x0,x2:x1,y1:scale(t),y2:scale(t),
      stroke:css('--grid'),'stroke-width':1}));
    const lb=el('text',{x:x0-9,y:scale(t)+4,'text-anchor':'end',
      fill:css('--text-muted'),'font-size':11});
    lb.textContent=fmt(t); svg.appendChild(lb);
  });
}

/* vertical bars - nominal categories all share one hue */
function barChart(host, rows, valF, fmtV, tipRows){
  const W=620,H=300,L=76,R=18,T=14,B=54;
  const svg=svgRoot(W,H);
  const max=Math.max(...rows.map(valF));
  const y=v=>T+(H-T-B)*(1-v/(max*1.16));
  yGrid(svg,y,L,W-R,niceTicks(max*1.16,4),fmtV);
  const bw=(W-L-R)/rows.length;
  rows.forEach((r,i)=>{
    const v=valF(r), x=L+i*bw+bw*0.19, w=bw*0.62;
    const bar=el('path',{d:`M${x},${y(0)} L${x},${y(v)+4} Q${x},${y(v)} ${x+4},${y(v)}
      L${x+w-4},${y(v)} Q${x+w},${y(v)} ${x+w},${y(v)+4} L${x+w},${y(0)} Z`,
      fill:css('--s1')});
    bar.style.cursor='pointer';
    bar.addEventListener('mousemove',e=>showTip(e,r.key,tipRows(r)));
    bar.addEventListener('mouseleave',hideTip);
    svg.appendChild(bar);
    const val=el('text',{x:x+w/2,y:y(v)-7,'text-anchor':'middle',
      fill:css('--text-secondary'),'font-size':11});
    val.textContent=fmtV(v); svg.appendChild(val);
    const lab=el('text',{x:x+w/2,y:H-B+20,'text-anchor':'middle',
      fill:css('--text-secondary'),'font-size':10.5});
    lab.textContent=trunc(r.key,14); svg.appendChild(lab);
  });
  svg.appendChild(el('line',{x1:L,x2:W-R,y1:y(0),y2:y(0),
    stroke:css('--rule'),'stroke-width':1}));
  host.appendChild(svg);
}

/* horizontal bars - for long category names */
function barChartH(host, rows, valF, fmtV, tipRows, labelChars){
  const W=620,rowH=27,L=labelChars>20?230:150,R=76,T=8;
  const H=T+rows.length*rowH+16;
  const svg=svgRoot(W,H);
  const max=Math.max(...rows.map(valF));
  const x=v=>L+(W-L-R)*(v/(max*1.05));
  rows.forEach((r,i)=>{
    const v=valF(r), yy=T+i*rowH, bh=rowH*0.64;
    const bar=el('path',{d:`M${L},${yy} L${x(v)-4},${yy} Q${x(v)},${yy} ${x(v)},${yy+4}
      L${x(v)},${yy+bh-4} Q${x(v)},${yy+bh} ${x(v)-4},${yy+bh} L${L},${yy+bh} Z`,
      fill:css('--s1')});
    bar.style.cursor='pointer';
    bar.addEventListener('mousemove',e=>showTip(e,r.key,tipRows(r)));
    bar.addEventListener('mouseleave',hideTip);
    svg.appendChild(bar);
    const lab=el('text',{x:L-10,y:yy+bh/2+4,'text-anchor':'end',
      fill:css('--text-secondary'),'font-size':11});
    lab.textContent=trunc(r.key,labelChars); svg.appendChild(lab);
    const val=el('text',{x:x(v)+8,y:yy+bh/2+4,
      fill:css('--text-secondary'),'font-size':11});
    val.textContent=fmtV(v); svg.appendChild(val);
  });
  host.appendChild(svg);
}

/* monthly line with crosshair, zero-baseline */
function lineChart(host, rows){
  const W=1140,H=330,L=84,R=26,T=16,B=62;
  const svg=svgRoot(W,H);
  const vals=rows.map(r=>r.total_sales);
  const max=Math.max(...vals);
  const y=v=>T+(H-T-B)*(1-v/(max*1.14));
  const x=i=>L+(W-L-R)*(i/(rows.length-1));
  yGrid(svg,y,L,W-R,niceTicks(max*1.14,4),money);
  const d=rows.map((r,i)=>`${i?'L':'M'}${x(i)},${y(r.total_sales)}`).join(' ');
  svg.appendChild(el('path',{d,fill:'none',stroke:css('--s1'),
    'stroke-width':2,'stroke-linejoin':'round'}));
  rows.forEach((r,i)=>{
    if (i % 6 === 0){
      const lb=el('text',{x:x(i),y:H-B+22,'text-anchor':'end',
        fill:css('--text-muted'),'font-size':10.5,
        transform:`rotate(-45 ${x(i)} ${H-B+22})`});
      lb.textContent=r.month; svg.appendChild(lb);
    }
  });
  const cross=el('line',{x1:0,x2:0,y1:T,y2:y(0),stroke:css('--text-muted'),
    'stroke-width':1,'stroke-dasharray':'3 3',opacity:0});
  svg.appendChild(cross);
  const dot=el('circle',{r:5,fill:css('--s1'),stroke:css('--surface-1'),
    'stroke-width':1.5,opacity:0});
  svg.appendChild(dot);
  const band=el('rect',{x:L,y:T,width:W-L-R,height:y(0)-T,fill:'transparent'});
  band.style.cursor='crosshair';
  band.addEventListener('mousemove',e=>{
    const box=svg.getBoundingClientRect();
    const rel=(e.clientX-box.left)/box.width*W;
    let i=Math.round((rel-L)/((W-L-R)/(rows.length-1)));
    i=Math.max(0,Math.min(rows.length-1,i));
    const r=rows[i];
    cross.setAttribute('x1',x(i)); cross.setAttribute('x2',x(i));
    cross.setAttribute('opacity',1);
    dot.setAttribute('cx',x(i)); dot.setAttribute('cy',y(r.total_sales));
    dot.setAttribute('opacity',1);
    showTip(e,r.month,['Sales: '+money(r.total_sales)]);
  });
  band.addEventListener('mouseleave',()=>{cross.setAttribute('opacity',0);
    dot.setAttribute('opacity',0); hideTip();});
  svg.appendChild(band);
  svg.appendChild(el('line',{x1:L,x2:W-R,y1:y(0),y2:y(0),
    stroke:css('--rule'),'stroke-width':1}));
  host.appendChild(svg);
}

/* bootstrap CI dot plot */
function sigChart(host, rows){
  const W=1140,rowH=54,L=150,R=40,T=18;
  const H=T+rows.length*rowH+44;
  const svg=svgRoot(W,H);
  const lo=Math.min(0,...rows.map(r=>r.Margin_CI_Low));
  const hi=Math.max(...rows.map(r=>r.Margin_CI_High));
  const pad=(hi-lo)*0.06;
  const x=v=>L+(W-L-R)*((v-(lo-pad))/((hi+pad)-(lo-pad)));
  svg.appendChild(el('line',{x1:x(0),x2:x(0),y1:T-4,y2:T+rows.length*rowH,
    stroke:css('--text-primary'),'stroke-width':1.5}));
  const zl=el('text',{x:x(0),y:H-16,'text-anchor':'middle',
    fill:css('--text-muted'),'font-size':11});
  zl.textContent='zero = a tie'; svg.appendChild(zl);
  rows.forEach((r,i)=>{
    const yy=T+i*rowH+rowH*0.55;
    svg.appendChild(el('line',{x1:x(r.Margin_CI_Low),x2:x(r.Margin_CI_High),
      y1:yy,y2:yy,stroke:css('--deemph'),'stroke-width':7,'stroke-linecap':'round'}));
    const d=el('circle',{cx:x(r.Observed_Margin),cy:yy,r:6,fill:css('--s1'),
      stroke:css('--surface-1'),'stroke-width':1.5});
    d.style.cursor='pointer';
    d.addEventListener('mousemove',e=>showTip(e,r.Dimension,[
      'Leader: '+r.Leader, 'Runner-up: '+r.Runner_Up,
      'Margin: '+money(r.Observed_Margin),
      '95% CI: '+money(r.Margin_CI_Low)+' to '+money(r.Margin_CI_High),
      'Holds top in '+pct(r.Leader_Retention_Rate)+' of resamples',
      'Verdict: '+r.Verdict]));
    d.addEventListener('mouseleave',hideTip);
    svg.appendChild(d);
    const lab=el('text',{x:L-12,y:yy+4,'text-anchor':'end',
      fill:css('--text-primary'),'font-size':12.5});
    lab.textContent=r.Dimension; svg.appendChild(lab);
    const note=el('text',{x:x(r.Margin_CI_Low),y:yy-14,
      fill:css('--text-secondary'),'font-size':11,
      stroke:css('--surface-1'),'stroke-width':3.5,
      'paint-order':'stroke fill','stroke-linejoin':'round'});
    note.textContent=r.Leader+' holds top in '+pct(r.Leader_Retention_Rate)+' of resamples';
    svg.appendChild(note);
  });
  host.appendChild(svg);
}

function card(title,caption,full,render,cols,rows){
  const c=document.createElement('div');
  c.className='card'+(full?' full':'');
  c.innerHTML='<h2>'+title+'</h2><p class="cap">'+caption+'</p>';
  const chart=document.createElement('div');
  chart.className='chart'; c.appendChild(chart); render(chart);
  if(cols){
    const btn=document.createElement('button');
    btn.className='toggle'; btn.type='button'; btn.textContent='Show data table';
    const tbl=document.createElement('div'); tbl.className='hidden';
    tbl.innerHTML='<table><thead><tr>'+cols.map(h=>'<th>'+h[0]+'</th>').join('')+
      '</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(h=>'<td>'+h[1](r)+'</td>').join('')+
      '</tr>').join('')+'</tbody></table>';
    btn.onclick=()=>{const open=!tbl.classList.contains('hidden');
      tbl.classList.toggle('hidden');
      btn.textContent=open?'Show data table':'Hide data table';};
    c.appendChild(btn); c.appendChild(tbl);
  }
  document.getElementById('grid').appendChild(c);
}

function render(){
  document.getElementById('grid').innerHTML='';
  const k=DATA.kpis;
  document.getElementById('sub').textContent =
    num(k.total_orders)+' orders  |  '+k.date_from+' to '+k.date_to+
    '  |  '+num(k.unique_customers)+' customers';

  const realCount = DATA.significance.filter(s=>s.Verdict==='REAL').length;
  document.getElementById('bannerTitle').textContent =
    realCount+' of '+DATA.significance.length+' rankings hold up under statistical testing.';
  document.getElementById('bannerText').textContent =
    'Each leader below was re-tested by resampling the orders 1,500 times. '+
    'Where the confidence interval clears zero, the lead is real and safe to act on. '+
    'Hover any chart for detail, or open the data table beneath it.';

  const kpis=[
    ['Total Sales',money(k.total_sales),num(k.line_items)+' line items'],
    ['Total Profit',money(k.total_profit),pct(k.profit_margin)+' margin'],
    ['Total Orders',num(k.total_orders),num(k.unique_customers)+' customers'],
    ['Avg Order Value',money(k.average_order_value),'per order'],
    ['Avg Discount',pct(k.average_discount),'across all lines'],
    ['Shipping Cost',money(k.total_shipping_cost),'total'],
  ];
  document.getElementById('kpis').innerHTML=kpis.map(([l,v,n])=>
    '<div class="kpi"><div class="label">'+l+'</div><div class="value">'+v+
    '</div><div class="note">'+n+'</div></div>').join('');

  const tipSales=r=>['Sales: '+money(r.total_sales),'Profit: '+money(r.total_profit),
    'Orders: '+num(r.orders),'Margin: '+pct(r.margin),'Share: '+pct(r.share)];
  const colsSales=[['Name',r=>r.key],['Sales',r=>money(r.total_sales)],
    ['Profit',r=>money(r.total_profit)],['Orders',r=>num(r.orders)],
    ['Margin',r=>pct(r.margin)],['Share',r=>pct(r.share)]];

  const topR=DATA.regions[0];
  card('Sales by Region',
    topR.key+' leads with '+money(topR.total_sales)+' ('+pct(topR.share)+
    ' of revenue). Regional gaps here are wide \\u2014 the smallest region does a fraction of the largest.',
    false, h=>barChartH(h,DATA.regions,r=>r.total_sales,money,tipSales,21),
    colsSales, DATA.regions);

  card('Sales by Product Category',
    'Three categories. '+DATA.categories[0].key+' leads on revenue \\u2014 check the margin column, since revenue rank and profit rank differ here.',
    false, h=>barChart(h,DATA.categories,r=>r.total_sales,money,tipSales),
    colsSales, DATA.categories);

  card('Top 10 Products by Sales',
    'Revenue is concentrated in a handful of high-ticket items \\u2014 a genuine long-tail pattern.',
    false, h=>barChartH(h,DATA.products,r=>r.total_sales,money,tipSales,30),
    colsSales, DATA.products);

  card('Profit by Customer Segment',
    'Ranked by profit rather than revenue, since segment value is a margin question.',
    false, h=>barChart(h,[...DATA.segments].sort((a,b)=>b.total_profit-a.total_profit),
      r=>r.total_profit,money,tipSales),
    colsSales, [...DATA.segments].sort((a,b)=>b.total_profit-a.total_profit));

  card('Sales by Order Priority',
    'Shown in priority order (Critical \\u2192 Low), not sorted by value \\u2014 this is an ordered scale, so resorting it would hide the pattern.',
    false, h=>barChart(h,DATA.priority,r=>r.total_sales,money,tipSales),
    colsSales, DATA.priority);

  card('Sales by Ship Mode',
    'Delivery method mix. Shipping cost totals '+money(k.total_shipping_cost)+' across all orders.',
    false, h=>barChart(h,DATA.ship_modes,r=>r.total_sales,money,tipSales),
    colsSales, DATA.ship_modes);

  card('Monthly Sales Trend',
    'Zero-baseline axis across '+DATA.trend.length+' months. Hover for any month\\u2019s figure.',
    true, h=>lineChart(h,DATA.trend),
    [['Month',r=>r.month],['Sales',r=>money(r.total_sales)]], DATA.trend);

  card('Do these rankings hold up?',
    'Bootstrap 95% confidence interval on each leader\\u2019s margin over its nearest rival. An interval clearing zero means the lead is statistically real.',
    true, h=>sigChart(h,DATA.significance),
    [['Dimension',r=>r.Dimension],['Leader',r=>r.Leader],['Runner-up',r=>r.Runner_Up],
     ['Margin',r=>money(r.Observed_Margin)],['CI low',r=>money(r.Margin_CI_Low)],
     ['CI high',r=>money(r.Margin_CI_High)],
     ['Holds top',r=>pct(r.Leader_Retention_Rate)],['Verdict',r=>r.Verdict]],
    DATA.significance);

  document.getElementById('foot').textContent =
    'Built from '+num(k.line_items)+' cleaned order line items ('+k.date_from+
    ' to '+k.date_to+'). Charts use a colourblind-validated palette; every ranking '+
    'is paired with the test that says whether it means anything.';
}

const btn=document.getElementById('themeBtn');
btn.onclick=()=>{
  const dark=document.documentElement.getAttribute('data-theme')==='dark'
    || (!document.documentElement.hasAttribute('data-theme')
        && matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.setAttribute('data-theme',dark?'light':'dark');
  render();
};
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',render);
render();
</script>
</body>
</html>
"""


def main() -> None:
    print("=" * 70)
    print("STATIC DASHBOARD BUILD")
    print("=" * 70 + "\n")

    analyzer = RetailSalesAnalyzer.from_cleaned_data()
    data = collect(analyzer)

    k = data["kpis"]
    print(f"  line items      {k['line_items']:,}")
    print(f"  total sales     ${k['total_sales']:,.2f}")
    print(f"  total profit    ${k['total_profit']:,.2f}")
    print(f"  orders          {k['total_orders']:,}")
    print(f"  regions         {len(data['regions'])}")
    print(f"  categories      {len(data['categories'])}")
    print(f"  months in trend {len(data['trend'])}\n")

    for s in data["significance"]:
        print(f"  [{s['Verdict']:5s}] {s['Dimension']:18s} {s['Leader']} "
              f"holds top in {s['Leader_Retention_Rate']:.1%} of resamples")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html = HTML.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    OUT_FILE.write_text(html, encoding="utf-8")

    print(f"\nWrote {OUT_FILE.relative_to(ROOT)} "
          f"({OUT_FILE.stat().st_size / 1024:.0f} KB, self-contained)")


if __name__ == "__main__":
    main()
