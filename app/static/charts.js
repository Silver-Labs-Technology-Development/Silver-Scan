/* Original source-backed market charts for Silver Scan.
   No invented points, and no imported copies of provider chart graphics. */
const NS='http://www.w3.org/2000/svg';
function node(tag,attrs={}){
  const el=document.createElementNS(NS,tag);
  for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));
  return el;
}
const good=v=>typeof v==='number'&&Number.isFinite(v);
function txt(x,y,value,attrs={}){
  const el=node('text',{x,y,...attrs});el.textContent=value;return el;
}
function compact(n){return Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2}).format(n);}
export function sparkline(data,delta=null){
  const series=Array.isArray(data)?data.filter(good):[];
  if(series.length<2){const span=document.createElement('span');span.className='muted';span.textContent='No chart data';return span;}
  const min=Math.min(...series),max=Math.max(...series),range=max-min||1;
  const svg=node('svg',{viewBox:'0 0 124 38',class:'sparkline',role:'img','aria-label':'Seven-day price sparkline'});
  const pts=series.map((v,i)=>String((1+i*122/(series.length-1)).toFixed(1))+','+String((35-(v-min)*32/range).toFixed(1))).join(' ');
  svg.append(node('polyline',{points:pts,fill:'none',stroke:good(delta)&&delta<0?'var(--red)':'var(--green)','stroke-width':2.3,'stroke-linejoin':'round'}));
  return svg;
}
export function timeSeries(raw,opts={}){
  const pts=(Array.isArray(raw)?raw:[]).filter(p=>Array.isArray(p)&&p.length===2&&good(p[0])&&good(p[1])).sort((a,b)=>a[0]-b[0]);
  const wrap=document.createElement('div');wrap.className='chart-component';
  if(pts.length<2){wrap.textContent='Historical chart unavailable from provider';return wrap;}
  const w=800,h=255,l=77,r=18,t=16,b=34;
  let min=Math.min(...pts.map(p=>p[1])),max=Math.max(...pts.map(p=>p[1]));
  const padding=(max-min||Math.abs(max)||1)*.08;
  min=Math.max(0,min-padding);max+=padding;
  const xmin=pts[0][0],xmax=pts[pts.length-1][0],xr=xmax-xmin||1,yr=max-min||1;
  const px=stamp=>l+(stamp-xmin)/xr*(w-l-r);
  const py=value=>t+(max-value)/yr*(h-t-b);
  const svg=node('svg',{viewBox:'0 0 '+w+' '+h,role:'img','aria-label':opts.label||'Market time series',tabindex:0});
  for(let i=0;i<=4;i++){
    const val=min+(max-min)*i/4,y=py(val);
    svg.append(node('line',{x1:l,x2:w-r,y1:y,y2:y,stroke:'var(--line)'}));
    const label=opts.kind==='sentiment'?String(Math.round(val)):'$'+compact(val);
    svg.append(txt(l-11,y+4,label,{'font-size':11,'text-anchor':'end',fill:'var(--muted)'}));
  }
  const coords=pts.map(([time,value])=>[px(time),py(value)]);
  const line='M'+coords.map(p=>p[0].toFixed(2)+' '+p[1].toFixed(2)).join(' L');
  const first=coords[0],last=coords[coords.length-1];
  const area=line+' L'+last[0].toFixed(2)+' '+(h-b)+' L'+first[0].toFixed(2)+' '+(h-b)+' Z';
  svg.append(node('path',{d:area,fill:'var(--brand)',opacity:'.09'}));
  svg.append(node('path',{d:line,fill:'none',stroke:'var(--brand)','stroke-width':2.8,'stroke-linecap':'round','stroke-linejoin':'round'}));
  for(let i=0;i<=4;i++){
    const stamp=xmin+(xmax-xmin)*i/4;
    svg.append(txt(px(stamp),h-10,new Date(stamp).toLocaleDateString(undefined,{month:'short',day:'numeric'}),{'font-size':11,'text-anchor':'middle',fill:'var(--muted)'}));
  }
  const guide=node('line',{y1:t,y2:h-b,stroke:'var(--brand)','stroke-dasharray':'4 4',visibility:'hidden'});
  const focus=node('circle',{r:5,fill:'var(--brand)',stroke:'var(--panel)','stroke-width':2,visibility:'hidden'});
  svg.append(guide,focus);
  const details=document.createElement('p');details.className='chart-tooltip';details.textContent='Hover or use arrow keys to inspect observations';
  let active=pts.length-1;
  const update=index=>{
    active=index;
    const p=pts[index],coord=coords[index];
    guide.setAttribute('x1',coord[0]);guide.setAttribute('x2',coord[0]);guide.setAttribute('visibility','visible');
    focus.setAttribute('cx',coord[0]);focus.setAttribute('cy',coord[1]);focus.setAttribute('visibility','visible');
    const value=opts.kind==='sentiment'?String(p[1]):new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:8}).format(p[1]);
    details.textContent=new Date(p[0]).toLocaleString()+' · '+value;
  };
  svg.addEventListener('pointermove',event=>{
    const rect=svg.getBoundingClientRect();
    if(!rect.width)return;
    const x=(event.clientX-rect.left)*w/rect.width;
    update(coords.reduce((best,p,i)=>Math.abs(p[0]-x)<Math.abs(coords[best][0]-x)?i:best,0));
  });
  svg.addEventListener('pointerleave',()=>{guide.setAttribute('visibility','hidden');focus.setAttribute('visibility','hidden');});
  svg.addEventListener('focus',()=>update(active));
  svg.addEventListener('keydown',event=>{
    if(event.key!=='ArrowLeft'&&event.key!=='ArrowRight')return;
    event.preventDefault();update(Math.max(0,Math.min(pts.length-1,active+(event.key==='ArrowLeft'?-1:1))));
  });
  wrap.append(svg,details);
  return wrap;
}
export function dominanceRing(btc,eth){
  const container=document.createElement('div');container.className='dominance-graphic';
  if(!good(btc)||!good(eth)){container.textContent='Dominance data unavailable';return container;}
  const a=Math.max(0,Math.min(100,btc)),b=Math.max(0,Math.min(100-a,eth));
  const ring=document.createElement('div');ring.className='dominance-ring';
  ring.style.background='conic-gradient(var(--brand) 0 '+a+'%, var(--gold) '+a+'% '+(a+b)+'%, var(--line) '+(a+b)+'% 100%)';
  const center=document.createElement('div');center.className='dominance-ring-center';
  const fig=document.createElement('strong');fig.textContent=a.toFixed(1)+'%';
  const name=document.createElement('span');name.textContent='Bitcoin';center.append(fig,name);ring.append(center);
  const legend=document.createElement('div');legend.className='dominance-legend';
  for(const [label,value,cls] of [['BTC',a,'btc'],['ETH',b,'eth'],['Other',100-a-b,'other']]){
    const row=document.createElement('div');row.className='dominance-legend-item';
    const dot=document.createElement('i');dot.className='legend-dot '+cls;
    const n=document.createElement('span');n.textContent=label;
    const v=document.createElement('strong');v.textContent=value.toFixed(1)+'%';
    row.append(dot,n,v);legend.append(row);
  }
  container.append(ring,legend);
  return container;
}
export function sentimentGauge(score,label){
  const out=document.createElement('div');out.className='sentiment-graphic';
  if(!good(score)||score<0||score>100){out.textContent='Sentiment unavailable';return out;}
  const track=document.createElement('div');track.className='sentiment-track';
  track.style.background='conic-gradient(from 270deg,#de645b 0% 18%,#eaa960 18% 40%,#e6c878 40% 58%,#9bca87 58% 78%,#299d75 78% 100%)';
  const pointer=document.createElement('div');pointer.className='sentiment-pointer';
  pointer.style.left=String(Math.max(0,Math.min(100,score)))+'%';
  track.append(pointer);
  const val=document.createElement('strong');val.className='sentiment-score';val.textContent=String(score);
  const classification=document.createElement('span');classification.className='sentiment-class';classification.textContent=label||'Unclassified';
  const ends=document.createElement('div');ends.className='sentiment-ends';
  const fear=document.createElement('span');fear.textContent='Extreme fear';
  const greed=document.createElement('span');greed.textContent='Extreme greed';
  ends.append(fear,greed);out.append(val,classification,track,ends);
  return out;
}
