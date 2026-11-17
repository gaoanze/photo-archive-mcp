# -*- coding: utf-8 -*-
"""生成单文件勾选网页：数据内联进 JS，缩略图走相对路径，可本地 file:// 打开。

设计约束（Windows / file:// 环境）：
- file:// 页面不能 fetch 本地 JSON，所以照片元数据必须内联进 ``<script>``。
- 缩略图用相对路径 ``thumbs/``，与生成的 HTML 同目录。
- 单文件自包含，不依赖外部 CDN 与构建工具。

交互能力：大图预览、勾选状态导入/导出、两类收藏标记（入论文 / 仅留档）、
框选多选、按日期/相册/可解码/有无标签/大小筛选、相似聚类分组。
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional


def build_html(records: List[Dict[str, object]],
               html_path: str,
               title: str = "实验照片挑选台",
               tag_suggestions: Optional[List[str]] = None,
               experiment: str = "") -> str:
    os.makedirs(os.path.dirname(os.path.abspath(html_path)), exist_ok=True)
    # 只保留网页需要的字段，减小内联体积
    slim = [{
        "name": r["name"],
        "date": r.get("date", ""),
        "album": r.get("album", ""),
        "thumb": r.get("thumb", ""),
        "size": r.get("size"),
        "wh": r.get("wh"),
        "decoded": r.get("decoded", True),
        "tag": r.get("tag", ""),
        "cluster": r.get("cluster", ""),
        "suggest": r.get("suggest", ""),
    } for r in records]
    data_json = json.dumps(slim, ensure_ascii=False)
    tags_json = json.dumps(tag_suggestions or [], ensure_ascii=False)
    exp_json = json.dumps(experiment or "", ensure_ascii=False)

    html = (_TEMPLATE
            .replace("__TITLE__", title)
            .replace("__DATA__", data_json)
            .replace("__TAGS__", tags_json)
            .replace("__EXP__", exp_json))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return html_path


_TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{--bg:#f6f7f9;--card:#fff;--line:#e5e8ee;--txt:#1c2330;--muted:#6b7280;--accent:#2563a8;--accent-soft:#e8f1fa;--gold:#b8860b;--gold-soft:#fbf3df;}
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--txt)}
  header{position:sticky;top:0;z-index:10;background:var(--card);border-bottom:1px solid var(--line);padding:12px 16px}
  h1{font-size:16px;margin:0 0 8px}
  .bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
  .bar input[type=search]{flex:1;min-width:160px;padding:7px 10px;border:1px solid var(--line);border-radius:8px}
  select,.bar button{padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;cursor:pointer}
  .bar button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
  .stats{font-size:12px;color:var(--muted);margin-left:auto}
  main{padding:16px;display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px;position:relative}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;display:flex;flex-direction:column;position:relative}
  .card img{width:100%;height:112px;object-fit:cover;background:#eee;cursor:zoom-in}
  .card .ph{width:100%;height:112px;display:flex;align-items:center;justify-content:center;color:#bbb;font-size:24px}
  .card .meta{padding:8px;font-size:12px}
  .card .meta .nm{word-break:break-all;color:var(--muted)}
  .card .meta .dt{font-weight:600;margin-bottom:2px}
  .card .meta .sz{color:var(--muted)}
  .card .chk{display:flex;gap:6px;align-items:center;padding:0 8px 8px;font-size:12px;flex-wrap:wrap}
  .card.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
  .card.flag-paper{outline:2px solid var(--gold);outline-offset:-2px}
  .group{grid-column:1/-1;margin:8px 0 0;font-size:13px;font-weight:700;color:var(--muted)}
  .badge{display:inline-block;padding:1px 6px;border-radius:6px;font-size:11px}
  .badge.paper{background:var(--gold-soft);color:var(--gold)}
  .badge.archive{background:var(--accent-soft);color:var(--accent)}
  footer{padding:16px;color:var(--muted);font-size:12px}
  /* 大图预览 */
  .overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.78);z-index:30;align-items:center;justify-content:center;padding:24px}
  .overlay.show{display:flex}
  .overlay img{max-width:90%;max-height:84vh;border-radius:8px}
  .overlay .cap{position:absolute;bottom:16px;left:0;right:0;text-align:center;color:#fff;font-size:13px}
  /* 框选 */
  #rubber{position:absolute;border:1px dashed var(--accent);background:rgba(37,99,168,.12);display:none;z-index:5}
  .fileinput{display:none}
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="bar">
    <input type="search" id="q" placeholder="搜索文件名 / 标签…">
    <select id="dateFilter"><option value="">全部日期</option></select>
    <select id="albumFilter"><option value="">全部相册</option></select>
    <select id="statusFilter">
      <option value="">全部状态</option>
      <option value="checked">已勾选</option>
      <option value="unchecked">未勾选</option>
      <option value="paper">标记入论文</option>
      <option value="archive">标记仅留档</option>
    </select>
    <select id="decodedFilter">
      <option value="">可解码/损坏不限</option>
      <option value="ok">仅可解码</option>
      <option value="broken">仅损坏</option>
    </select>
    <select id="sizeFilter">
      <option value="">大小不限</option>
      <option value="lt200k">&lt;200KB</option>
      <option value="200k1m">200KB–1MB</option>
      <option value="gt1m">&gt;1MB</option>
    </select>
    <label><input type="checkbox" id="clusterMode"> 按相似聚类分组</label>
    <input type="text" id="expInput" placeholder="实验名（可选）" style="padding:7px 10px;border:1px solid var(--line);border-radius:8px;min-width:140px">
    <button id="selAll">当前筛选全选</button>
    <button id="clearAll">清空勾选</button>
    <button id="export">导出勾选清单</button>
    <button id="import">导入勾选清单</button>
    <input type="file" id="importFile" class="fileinput" accept="application/json">
    <span class="stats" id="stats"></span>
  </div>
</header>
<main id="grid"></main>
<footer>勾选/标记保存在浏览器本地；可导出 JSON 后再导入恢复；点缩略图放大预览。框选：在空白处按住拖动可批量勾选当前筛选结果。</footer>

<div class="overlay" id="overlay">
  <img id="ovImg" alt="">
  <div class="cap" id="ovCap"></div>
</div>
<div id="rubber"></div>

<script>
const RAW = __DATA__;
const TAG_SUGGEST = __TAGS__;
const DEFAULT_EXP = __EXP__;
// 先声明 DOM 助手，下面初始化默认实验名时要用；顺序别改
const $ = id => document.getElementById(id);
const grid = $("grid"), q = $("q"), dateF = $("dateFilter"), albumF = $("albumFilter");

// state: name -> {checked:bool, flag:""|"paper"|"archive", tag:""}
const state = {};
RAW.forEach(r => state[r.name] = {checked:false, flag:"", tag:r.tag||r.suggest||""});
$("expInput").value = DEFAULT_EXP;

function tagOptions(cur){
  const opts = ["", ...TAG_SUGGEST];
  if(cur && !opts.includes(cur)) opts.push(cur);
  return opts.map(o=>`<option value="${o}" ${o===cur?"selected":""}>${o||"（未设标签）"}</option>`).join("");
}

function humanSize(b){if(!b)return "—";const u=["B","KB","MB","GB"];let i=0;while(b>=1024&&i<3){b/=1024;i++;}return b.toFixed(1)+u[i];}
function uniq(arr){return [...new Set(arr)].filter(Boolean).sort();}
uniq(RAW.map(r=>r.date)).forEach(d=>dateF.add(new Option(d,d)));
uniq(RAW.map(r=>r.album)).forEach(a=>albumF.add(new Option(a,a)));

function sizeMatch(b, f){
  if(!f) return true; b=b||0;
  if(f==="lt200k") return b<200*1024;
  if(f==="200k1m") return b>=200*1024 && b<=1024*1024;
  if(f==="gt1m") return b>1024*1024;
  return true;
}

function filtered(){
  const t = q.value.trim().toLowerCase();
  const sf = $("statusFilter").value, df = $("decodedFilter").value, sfz = $("sizeFilter").value;
  return RAW.filter(r => {
    const s = state[r.name];
    if(dateF.value && r.date!==dateF.value) return false;
    if(albumF.value && r.album!==albumF.value) return false;
    if(t && !(r.name.toLowerCase().includes(t) || (s.tag||"").toLowerCase().includes(t))) return false;
    if(sf==="checked" && !s.checked) return false;
    if(sf==="unchecked" && s.checked) return false;
    if(sf==="paper" && s.flag!=="paper") return false;
    if(sf==="archive" && s.flag!=="archive") return false;
    if(df==="ok" && r.decoded===false) return false;
    if(df==="broken" && r.decoded!==false) return false;
    if(!sizeMatch(r.size, sfz)) return false;
    return true;
  });
}

function groupKey(r){
  if($("clusterMode").checked && r.cluster) return "相似簇：" + r.cluster;
  return r.date;
}

function render(){
  grid.innerHTML="";
  const rows = filtered();
  let lastKey="";
  rows.forEach(r=>{
    const key=groupKey(r);
    if(key!==lastKey){lastKey=key;const g=document.createElement("div");g.className="group";g.textContent=key;grid.appendChild(g);}
    const s=state[r.name];
    const card=document.createElement("div");
    card.className="card"+(s.checked?" on":"")+(s.flag==="paper"?" flag-paper":"");
    const img = r.thumb ? `<img src="thumbs/${r.thumb}" alt="">` : `<div class="ph">▢</div>`;
    const flagBadge = s.flag==="paper" ? `<span class="badge paper">入论文</span>` : s.flag==="archive" ? `<span class="badge archive">仅留档</span>` : "";
    card.innerHTML=`${img}<div class="meta">
      <div class="dt">${r.date} ${flagBadge}</div>
      <div class="nm">${r.name}</div>
      <div class="nm">${r.album||""} · ${r.wh||"—"} · ${humanSize(r.size)}</div>
      ${r.decoded===false?'<div class="nm" style="color:#c0392b">损坏/无法解码</div>':""}
      <select class="tagSel" title="标签">${tagOptions(s.tag)}</select>
    </div>
      <div class="chk">
        <label><input type="checkbox" ${s.checked?"checked":""}> 勾选</label>
        <button class="flag" data-f="paper" title="标记入论文">论文</button>
        <button class="flag" data-f="archive" title="标记仅留档">留档</button>
      </div>`;
    const cb=card.querySelector("input[type=checkbox]");
    cb.addEventListener("change",()=>{s.checked=cb.checked;render();});
    card.querySelectorAll(".flag").forEach(btn=>btn.addEventListener("click",()=>{
      s.flag = s.flag===btn.dataset.f ? "" : btn.dataset.f; render();
    }));
    const tagSel=card.querySelector(".tagSel");
    tagSel.addEventListener("change",()=>{s.tag=tagSel.value;});
    if(r.thumb){card.querySelector("img").addEventListener("click",()=>openOverlay(r));}
    grid.appendChild(card);
  });
  const n=Object.values(state).filter(s=>s.checked).length;
  const p=Object.values(state).filter(s=>s.flag==="paper").length;
  $("stats").textContent=`已勾选 ${n} / ${RAW.length}　入论文 ${p}`;
}

function openOverlay(r){
  $("ovImg").src="thumbs/"+r.thumb;
  $("ovCap").textContent=`${r.name}　${r.date}　${r.album||""}　${r.wh||""}`;
  $("overlay").classList.add("show");
}
$("overlay").addEventListener("click",()=>$("overlay").classList.remove("show"));

$("selAll").onclick=()=>{filtered().forEach(r=>state[r.name].checked=true);render();};
$("clearAll").onclick=()=>{RAW.forEach(r=>{state[r.name].checked=false;state[r.name].flag="";});render();};
[q,dateF,albumF].forEach(el=>el.addEventListener("input",render));
["statusFilter","decodedFilter","sizeFilter","clusterMode"].forEach(id=>$(id).addEventListener("change",render));

function exportPayload(){
  const sel=RAW.filter(r=>state[r.name].checked);
  const experiment=$("expInput").value.trim();
  const byDate={};
  sel.forEach(r=>{const s=state[r.name];(byDate[r.date]=byDate[r.date]||[]).push({
    name:r.name,album:r.album,thumb:r.thumb,tag:s.tag,flag:s.flag,
    suggest:r.suggest,experiment});});
  const groups=Object.keys(byDate).sort().map(d=>({date:d,photos:byDate[d]}));
  // 同时导出全量勾选/标记状态，便于下次导入恢复
  const full=Object.fromEntries(RAW.map(r=>[r.name,state[r.name]]));
  return {experiment,total:sel.length,groups,state:full};
}

$("export").onclick=()=>{
  const payload=exportPayload();
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:"application/json"});
  const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="勾选照片清单.json";a.click();
};

$("import").onclick=()=>$("importFile").click();
$("importFile").addEventListener("change",e=>{
  const f=e.target.files[0];if(!f)return;
  const reader=new FileReader();
  reader.onload=()=>{
    try{
      const data=JSON.parse(reader.result);
      if(data.experiment) $("expInput").value=data.experiment;
      if(data.state){Object.entries(data.state).forEach(([k,v])=>{if(state[k])state[k]={...state[k],...v};});}
      else if(data.groups){ // 兼容旧版清单：只恢复勾选
        data.groups.forEach(g=>(g.photos||[]).forEach(p=>{if(state[p.name])state[p.name].checked=true;}));
      }
      render();
    }catch(err){alert("导入失败："+err.message);}
    e.target.value="";
  };
  reader.readAsText(f,"utf-8");
});

// 框选多选
let dragStart=null;
grid.addEventListener("mousedown",e=>{
  if(e.target.closest(".card")) return;
  dragStart={x:e.clientX,y:e.clientY};
  const rub=$("rubber");rub.style.display="block";rub.style.left=e.clientX+"px";rub.style.top=e.clientY+"px";rub.style.width="0";rub.style.height="0";
});
grid.addEventListener("mousemove",e=>{
  if(!dragStart) return;
  const rub=$("rubber");
  const x=Math.min(dragStart.x,e.clientX), y=Math.min(dragStart.y,e.clientY);
  rub.style.left=x+"px";rub.style.top=y+"px";rub.style.width=Math.abs(e.clientX-dragStart.x)+"px";rub.style.height=Math.abs(e.clientY-dragStart.y)+"px";
});
grid.addEventListener("mouseup",e=>{
  if(!dragStart) return;
  const rub=$("rubber");rub.style.display="none";
  const rect=rub.getBoundingClientRect();
  // 框选范围内卡片对应记录勾选
  grid.querySelectorAll(".card").forEach(card=>{
    const b=card.getBoundingClientRect();
    if(b.left<rect.right&&b.right>rect.left&&b.top<rect.bottom&&b.bottom>rect.top){
      const cb=card.querySelector("input[type=checkbox]"); if(cb) cb.checked=true;
      const nm=card.querySelector(".meta .nm")?.textContent;
      const rec=RAW.find(r=>r.name===nm); if(rec) state[rec.name].checked=true;
    }
  });
  dragStart=null;render();
});

render();
</script>
</body>
</html>
"""
