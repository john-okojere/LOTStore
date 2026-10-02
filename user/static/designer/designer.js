(function () {
  "use strict";
  const root = document.getElementById("studio");
  if (!root) return;
  const canvas = document.getElementById("design-canvas"), ctx = canvas.getContext("2d");
  const tabs = [...document.querySelectorAll(".view-tab")];
  const csrf = document.cookie.split("; ").find(v => v.startsWith("csrftoken="))?.split("=")[1] || "";
  const saved = JSON.parse(document.getElementById("saved-design").textContent || "{}"), savedQty = JSON.parse(document.getElementById("saved-quantities").textContent || "{}");
  let views = saved.views || {}, active = tabs[0]?.dataset.id, selected = -1, dragging = false, drawing = false, last = null, timer = null;
  let history = [], future = [], backgrounds = {}, imageCache = {};
  tabs.forEach(tab => {
    const img = new Image(); img.crossOrigin = "anonymous"; img.onload = draw; img.src = tab.dataset.image; backgrounds[tab.dataset.id] = img;
    views[tab.dataset.id] ||= [];
    tab.onclick = () => { active = tab.dataset.id; selected = -1; tabs.forEach(t => t.classList.toggle("active", t === tab)); draw(); layers(); };
  });
  document.querySelectorAll(".size-qty").forEach(el => el.value = savedQty[el.dataset.size] || 0);
  function tab() { return tabs.find(t => t.dataset.id === active); }
  function area() { const t=tab(); return {x:+t.dataset.x,y:+t.dataset.y,w:+t.dataset.w,h:+t.dataset.h}; }
  function objects() { return views[active] || (views[active] = []); }
  function snapshot() { history.push(JSON.stringify(views)); if(history.length>60) history.shift(); future=[]; dirty(); }
  function dirty() { document.getElementById("save-state").textContent="Unsaved changes"; clearTimeout(timer); timer=setTimeout(save,1500); }
  function getImage(src) { if(!imageCache[src]) { const i=new Image(); i.crossOrigin="anonymous"; i.onload=draw; i.src=src; imageCache[src]=i; } return imageCache[src]; }
  function bounds(o) { const s=o.scale||1,w=(o.w||120)*s,h=(o.h||120)*s; return {x:o.x-w/2,y:o.y-h/2,w,h}; }
  function clamp(o) { const a=area(),b=bounds(o); o.x=Math.max(a.x+b.w/2,Math.min(a.x+a.w-b.w/2,o.x));o.y=Math.max(a.y+b.h/2,Math.min(a.y+a.h-b.h/2,o.y)); }
  function paintObject(o, index) {
    ctx.save();ctx.translate(o.x,o.y);ctx.rotate((o.rotation||0)*Math.PI/180);ctx.scale(o.scale||1,o.scale||1);ctx.fillStyle=o.color||"#111";ctx.strokeStyle=o.color||"#111";ctx.lineWidth=5;
    if(o.type==="text"){ctx.font=`${o.size||48}px Poppins, sans-serif`;ctx.textAlign="center";ctx.textBaseline="middle";ctx.fillText(o.text||"Your text",0,0);o.w=ctx.measureText(o.text||"Your text").width;o.h=o.size||48;}
    else if(o.type==="rect")ctx.fillRect(-o.w/2,-o.h/2,o.w,o.h);
    else if(o.type==="circle"){ctx.beginPath();ctx.arc(0,0,o.w/2,0,Math.PI*2);ctx.fill();}
    else if(o.type==="image"){const i=getImage(o.src);if(i.complete)ctx.drawImage(i,-o.w/2,-o.h/2,o.w,o.h);}
    else if(o.type==="path"){ctx.beginPath();(o.points||[]).forEach((p,n)=>n?ctx.lineTo(p.x-o.x,p.y-o.y):ctx.moveTo(p.x-o.x,p.y-o.y));ctx.stroke();}
    if(index===selected){const b={w:(o.w||120),h:(o.h||120)};ctx.strokeStyle="#d2a626";ctx.lineWidth=3/(o.scale||1);ctx.setLineDash([8,5]);ctx.strokeRect(-b.w/2,-b.h/2,b.w,b.h);}
    ctx.restore();
  }
  function draw(){ctx.clearRect(0,0,900,900);const bg=backgrounds[active];if(bg?.complete)ctx.drawImage(bg,0,0,900,900);const a=area();ctx.save();ctx.beginPath();ctx.rect(a.x,a.y,a.w,a.h);ctx.clip();objects().forEach(paintObject);ctx.restore();ctx.strokeStyle="#d2a626";ctx.lineWidth=3;ctx.setLineDash([10,8]);ctx.strokeRect(a.x,a.y,a.w,a.h);}
  function layers(){const box=document.getElementById("layer-list");box.innerHTML="";objects().slice().reverse().forEach((o,rev)=>{const i=objects().length-1-rev,b=document.createElement("button");b.type="button";b.className="layer-button"+(i===selected?" active":"");b.textContent=o.type==="text"?o.text:o.type;b.onclick=()=>{selected=i;sync();draw();layers()};box.appendChild(b);});}
  function add(type, extra={}){snapshot();const a=area(),o={type,x:a.x+a.w/2,y:a.y+a.h/2,w:140,h:140,color:document.getElementById("object-color").value,size:48,scale:1,rotation:0,...extra};objects().push(o);selected=objects().length-1;clamp(o);draw();layers();}
  function point(e){const r=canvas.getBoundingClientRect(),touch=e.touches?.[0]||e;return{x:(touch.clientX-r.left)*900/r.width,y:(touch.clientY-r.top)*900/r.height};}
  function hit(p){for(let i=objects().length-1;i>=0;i--){const b=bounds(objects()[i]);if(p.x>=b.x&&p.x<=b.x+b.w&&p.y>=b.y&&p.y<=b.y+b.h)return i;}return -1;}
  canvas.addEventListener("pointerdown",e=>{const p=point(e);if(drawing){snapshot();objects().push({type:"path",x:p.x,y:p.y,w:120,h:120,color:document.getElementById("object-color").value,points:[p],scale:1,rotation:0});selected=objects().length-1;dragging=true;return;}selected=hit(p);if(selected>=0){snapshot();last=p;dragging=true;canvas.setPointerCapture(e.pointerId);}draw();layers();});
  canvas.addEventListener("pointermove",e=>{if(!dragging||selected<0)return;const p=point(e),o=objects()[selected];if(drawing){o.points.push(p);o.x=o.points.reduce((s,q)=>s+q.x,0)/o.points.length;o.y=o.points.reduce((s,q)=>s+q.y,0)/o.points.length;}else{o.x+=p.x-last.x;o.y+=p.y-last.y;last=p;clamp(o);}draw();});
  canvas.addEventListener("pointerup",()=>{dragging=false;dirty();});
  document.querySelectorAll("[data-add]").forEach(b=>b.onclick=()=>{if(b.dataset.add==="draw"){drawing=!drawing;b.classList.toggle("active",drawing);canvas.style.cursor=drawing?"crosshair":"default";}else if(b.dataset.add==="text"){const text=prompt("Enter your text","Your text");if(text)add("text",{text:text.slice(0,120),w:200,h:48});}else add(b.dataset.add);});
  document.getElementById("image-upload").onchange=async e=>{const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append("image",f);const res=await fetch(root.dataset.assetUrl,{method:"POST",headers:{"X-CSRFToken":csrf},body:fd}),data=await res.json();if(!res.ok)return alert(data.error);const img=getImage(data.url);img.onload=()=>{const ratio=Math.min(260/img.width,260/img.height,1);add("image",{src:data.url,w:img.width*ratio,h:img.height*ratio});};};
  function updateSelected(fn){if(selected<0)return;snapshot();fn(objects()[selected]);clamp(objects()[selected]);draw();layers();}
  document.getElementById("object-color").oninput=e=>updateSelected(o=>o.color=e.target.value);
  document.getElementById("object-size").oninput=e=>updateSelected(o=>o.type==="text"?o.size=+e.target.value:o.scale=+e.target.value/48);
  document.getElementById("object-rotation").oninput=e=>updateSelected(o=>o.rotation=+e.target.value);
  document.getElementById("remove").onclick=()=>{if(selected<0)return;snapshot();objects().splice(selected,1);selected=-1;draw();layers();};
  document.getElementById("duplicate").onclick=()=>{if(selected>=0)add(objects()[selected].type,{...JSON.parse(JSON.stringify(objects()[selected])),x:objects()[selected].x+20,y:objects()[selected].y+20});};
  document.getElementById("layer-up").onclick=()=>{if(selected<0||selected===objects().length-1)return;snapshot();[objects()[selected],objects()[selected+1]]=[objects()[selected+1],objects()[selected]];selected++;draw();layers();};
  document.getElementById("layer-down").onclick=()=>{if(selected<=0)return;snapshot();[objects()[selected],objects()[selected-1]]=[objects()[selected-1],objects()[selected]];selected--;draw();layers();};
  document.getElementById("undo").onclick=()=>{if(!history.length)return;future.push(JSON.stringify(views));views=JSON.parse(history.pop());selected=-1;draw();layers();dirty();};
  document.getElementById("redo").onclick=()=>{if(!future.length)return;history.push(JSON.stringify(views));views=JSON.parse(future.pop());selected=-1;draw();layers();dirty();};
  document.getElementById("zoom").oninput=e=>document.querySelector(".canvas-stage").style.width=e.target.value+"%";
  function sync(){if(selected<0)return;const o=objects()[selected];document.getElementById("object-color").value=o.color||"#111111";document.getElementById("object-rotation").value=o.rotation||0;}
  function payload(){const old=selected;selected=-1;draw();const preview=canvas.toDataURL("image/png",.9);selected=old;draw();const quantities={};document.querySelectorAll(".size-qty").forEach(e=>{if(+e.value>0)quantities[e.dataset.size]=+e.value;});return{design:{version:1,views},preview,size_quantities:quantities,variant:document.getElementById("variant").value,note:document.getElementById("note").value};}
  async function save(){document.getElementById("save-state").textContent="Saving…";try{const res=await fetch(root.dataset.saveUrl,{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":csrf},body:JSON.stringify(payload())}),data=await res.json();document.getElementById("save-state").textContent=res.ok?"Saved":"Could not save";if(!res.ok)console.error(data);}catch(e){document.getElementById("save-state").textContent="Offline — changes not saved";}}
  document.getElementById("save-btn").onclick=save;const dialog=document.getElementById("submit-dialog");document.getElementById("open-submit").onclick=async()=>{await save();dialog.showModal();};document.querySelector(".dialog-close").onclick=()=>dialog.close();dialog.querySelector("form").addEventListener("submit",async e=>{const count=[...document.querySelectorAll(".size-qty")].reduce((s,n)=>s+(+n.value||0),0);if(!count){e.preventDefault();alert("Enter a quantity for at least one size.");return;}await save();});
  window.addEventListener("keydown",e=>{if((e.key==="Delete"||e.key==="Backspace")&&!/INPUT|TEXTAREA/.test(e.target.tagName)){e.preventDefault();document.getElementById("remove").click();}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="z"){e.preventDefault();(e.shiftKey?document.getElementById("redo"):document.getElementById("undo")).click();}});
  draw();layers();
})();
