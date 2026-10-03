/*
 * LOT Store design studio.
 * Saved format (unchanged for existing drafts): { version, views: { <mockupViewId>: [object, ...] } }
 * Object: { type, x, y, w, h, scale, rotation, color, opacity, text, font, size, bold, italic, src, flipX, points, lineWidth }
 * x/y are the object's centre on the 900 x 900 canvas; w/h are its unscaled size.
 */
(function () {
  "use strict";
  var root = document.getElementById("studio");
  if (!root) { return; }

  var SIZE = 900;
  var SWATCHES = ["#111111", "#ffffff", "#cdab4b", "#008751", "#c62828", "#1e3a8a", "#6b21a8", "#f97316", "#ec4899", "#64748b"];
  var canvas = document.getElementById("design-canvas");
  var ctx = canvas.getContext("2d");
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".ds-view"));
  var authed = root.getAttribute("data-authed") === "1";
  var csrf = (document.cookie.split("; ").filter(function (c) { return c.indexOf("csrftoken=") === 0; })[0] || "").split("=")[1] || "";
  var saved = JSON.parse(document.getElementById("saved-design").textContent || "{}") || {};
  var savedQty = JSON.parse(document.getElementById("saved-quantities").textContent || "{}") || {};
  var $ = function (id) { return document.getElementById(id); };

  var views = (saved && saved.views) || {};
  var active = tabs.length ? tabs[0].getAttribute("data-id") : null;
  var selected = -1;
  var mode = null;          // move | scale | rotate | draw
  var dragStart = null;
  var drawing = false;
  var previewMode = false;
  var guides = { v: false, h: false };
  var history = [], future = [];
  var backgrounds = {}, imageCache = {};
  var color = "#111111";
  var saveTimer = null, saveState = "saved", lastPreviewAt = 0, sliderActive = false;

  /* ---------- Setup ---------- */
  tabs.forEach(function (tab) {
    var id = tab.getAttribute("data-id");
    var img = new Image();
    img.onload = draw;
    img.src = tab.getAttribute("data-image");
    backgrounds[id] = img;
    if (!Array.isArray(views[id])) { views[id] = []; }
    // Older drafts stored freehand points in absolute canvas coordinates.
    views[id].forEach(function (o) {
      if (o.type === "path" && !o.rel && Array.isArray(o.points)) {
        o.points = o.points.map(function (p) { return { x: p.x - o.x, y: p.y - o.y }; });
        o.rel = true;
      }
    });
    tab.addEventListener("click", function () { setView(id); });
  });

  function setView(id) {
    active = id;
    selected = -1;
    tabs.forEach(function (t) {
      var on = t.getAttribute("data-id") === id;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on ? "true" : "false");
    });
    refresh();
  }

  function tab() { return tabs.filter(function (t) { return t.getAttribute("data-id") === active; })[0]; }
  function area() {
    var t = tab();
    return { x: +t.getAttribute("data-x"), y: +t.getAttribute("data-y"), w: +t.getAttribute("data-w"), h: +t.getAttribute("data-h") };
  }
  function objects() { return views[active] || (views[active] = []); }
  function current() { return selected >= 0 ? objects()[selected] : null; }
  function unit() { return SIZE / Math.max(canvas.getBoundingClientRect().width, 1); } // canvas units per screen pixel

  /* ---------- Geometry ---------- */
  function measure(o) {
    if (o.type === "text") {
      ctx.save();
      ctx.font = fontOf(o);
      var lines = String(o.text || "Your text").split("\n");
      o.w = Math.max.apply(null, lines.map(function (l) { return ctx.measureText(l || " ").width; })) + 8;
      o.h = lines.length * (o.size || 48) * 1.2;
      ctx.restore();
    } else if (o.type === "path" && o.points && o.points.length) {
      var xs = o.points.map(function (p) { return p.x; }), ys = o.points.map(function (p) { return p.y; });
      o.w = Math.max(20, (Math.max.apply(null, xs) - Math.min.apply(null, xs)) * 2 + (o.lineWidth || 6));
      o.h = Math.max(20, (Math.max.apply(null, ys) - Math.min.apply(null, ys)) * 2 + (o.lineWidth || 6));
    }
  }
  function fontOf(o) {
    return (o.italic ? "italic " : "") + (o.bold ? "700 " : "400 ") + (o.size || 48) + "px " + (o.font || "Poppins") + ", sans-serif";
  }
  function toLocal(o, p) {
    var r = -(o.rotation || 0) * Math.PI / 180, s = o.scale || 1;
    var dx = p.x - o.x, dy = p.y - o.y;
    return { x: (dx * Math.cos(r) - dy * Math.sin(r)) / s, y: (dx * Math.sin(r) + dy * Math.cos(r)) / s };
  }
  function toWorld(o, lx, ly) {
    var r = (o.rotation || 0) * Math.PI / 180, s = o.scale || 1;
    return { x: o.x + (lx * s) * Math.cos(r) - (ly * s) * Math.sin(r), y: o.y + (lx * s) * Math.sin(r) + (ly * s) * Math.cos(r) };
  }
  function corners(o) {
    var w = (o.w || 120) / 2, h = (o.h || 120) / 2;
    return [toWorld(o, -w, -h), toWorld(o, w, -h), toWorld(o, w, h), toWorld(o, -w, h)];
  }
  function rotateHandle(o) {
    var lift = 34 * unit() / (o.scale || 1);
    return toWorld(o, 0, -(o.h || 120) / 2 - lift);
  }
  function hit(p) {
    for (var i = objects().length - 1; i >= 0; i--) {
      var o = objects()[i], l = toLocal(o, p), pad = 6 * unit();
      if (Math.abs(l.x) <= (o.w || 120) / 2 + pad && Math.abs(l.y) <= (o.h || 120) / 2 + pad) { return i; }
    }
    return -1;
  }
  function near(a, b, r) { return Math.hypot(a.x - b.x, a.y - b.y) <= r; }
  function clampCentre(o) {
    var a = area();
    o.x = Math.max(a.x, Math.min(a.x + a.w, o.x));
    o.y = Math.max(a.y, Math.min(a.y + a.h, o.y));
  }
  function outside(o) {
    var a = area();
    return corners(o).some(function (c) { return c.x < a.x - 1 || c.x > a.x + a.w + 1 || c.y < a.y - 1 || c.y > a.y + a.h + 1; });
  }

  /* ---------- Rendering ---------- */
  function shapePath(c, o) {
    var w = o.w, h = o.h;
    c.beginPath();
    if (o.type === "rect") { c.rect(-w / 2, -h / 2, w, h); }
    else if (o.type === "circle") { c.ellipse(0, 0, w / 2, h / 2, 0, 0, Math.PI * 2); }
    else if (o.type === "triangle") { c.moveTo(0, -h / 2); c.lineTo(w / 2, h / 2); c.lineTo(-w / 2, h / 2); c.closePath(); }
    else if (o.type === "star") {
      for (var i = 0; i < 10; i++) {
        var rad = i % 2 ? 0.42 : 1, ang = -Math.PI / 2 + i * Math.PI / 5;
        c.lineTo(Math.cos(ang) * w / 2 * rad, Math.sin(ang) * h / 2 * rad);
      }
      c.closePath();
    } else if (o.type === "heart") {
      c.moveTo(0, h * 0.35);
      c.bezierCurveTo(-w * 0.55, -h * 0.05, -w * 0.35, -h * 0.55, 0, -h * 0.22);
      c.bezierCurveTo(w * 0.35, -h * 0.55, w * 0.55, -h * 0.05, 0, h * 0.35);
      c.closePath();
    } else if (o.type === "cross") {
      var bw = w * 0.26;
      c.rect(-bw / 2, -h / 2, bw, h);
      c.rect(-w / 2, -h * 0.22 - h * 0.11, w, h * 0.22);
    }
  }

  function paint(c, o) {
    c.save();
    c.globalAlpha = o.opacity == null ? 1 : o.opacity;
    c.translate(o.x, o.y);
    c.rotate((o.rotation || 0) * Math.PI / 180);
    c.scale((o.scale || 1) * (o.flipX ? -1 : 1), o.scale || 1);
    c.fillStyle = o.color || "#111";
    c.strokeStyle = o.color || "#111";
    if (o.type === "text") {
      c.font = fontOf(o);
      c.textAlign = "center";
      c.textBaseline = "middle";
      var lines = String(o.text || "Your text").split("\n"), lh = (o.size || 48) * 1.2;
      lines.forEach(function (line, i) { c.fillText(line, 0, (i - (lines.length - 1) / 2) * lh); });
    } else if (o.type === "image") {
      var img = getImage(o.src);
      if (img.complete && img.naturalWidth) { c.drawImage(img, -o.w / 2, -o.h / 2, o.w, o.h); }
    } else if (o.type === "path") {
      c.lineWidth = o.lineWidth || 6;
      c.lineCap = "round";
      c.lineJoin = "round";
      c.beginPath();
      (o.points || []).forEach(function (p, n) { if (n) { c.lineTo(p.x, p.y); } else { c.moveTo(p.x, p.y); } });
      c.stroke();
    } else {
      shapePath(c, o);
      c.fill();
    }
    c.restore();
  }

  function render(c, viewId, withGuides) {
    var a = areaFor(viewId);
    c.clearRect(0, 0, SIZE, SIZE);
    var bg = backgrounds[viewId];
    if (bg && bg.complete && bg.naturalWidth) { c.drawImage(bg, 0, 0, SIZE, SIZE); }
    c.save();
    c.beginPath();
    c.rect(a.x, a.y, a.w, a.h);
    c.clip();
    (views[viewId] || []).forEach(function (o) { paint(c, o); });
    c.restore();
    if (!withGuides) { return; }
    var u = unit();
    if (mode === "move" || mode === "scale" || mode === "rotate" || drawing) {
      // Dim everything outside the print area while editing.
      c.save();
      c.fillStyle = "rgba(20,21,28,0.28)";
      c.beginPath();
      c.rect(0, 0, SIZE, SIZE);
      c.rect(a.x, a.y, a.w, a.h);
      c.fill("evenodd");
      c.restore();
    }
    c.save();
    c.strokeStyle = "rgba(205,171,75,0.95)";
    c.lineWidth = 2 * u;
    c.setLineDash([8 * u, 6 * u]);
    c.strokeRect(a.x, a.y, a.w, a.h);
    c.setLineDash([]);
    c.font = "600 " + Math.round(11 * u) + "px Poppins, sans-serif";
    c.fillStyle = "rgba(205,171,75,0.95)";
    c.fillText("PRINT AREA", a.x + 4 * u, a.y - 6 * u);
    if (guides.v) { line(c, a.x + a.w / 2, a.y, a.x + a.w / 2, a.y + a.h, u); }
    if (guides.h) { line(c, a.x, a.y + a.h / 2, a.x + a.w, a.y + a.h / 2, u); }
    c.restore();
  }
  function line(c, x1, y1, x2, y2, u) {
    c.save();
    c.strokeStyle = "#ec4899";
    c.lineWidth = 1.5 * u;
    c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();
    c.restore();
  }
  function areaFor(viewId) {
    var t = tabs.filter(function (x) { return x.getAttribute("data-id") === viewId; })[0];
    return { x: +t.getAttribute("data-x"), y: +t.getAttribute("data-y"), w: +t.getAttribute("data-w"), h: +t.getAttribute("data-h") };
  }

  function draw() {
    if (!active) { return; }
    objects().forEach(measure);
    render(ctx, active, !previewMode);
    var o = current();
    if (o && !previewMode && !drawing) {
      var u = unit(), cs = corners(o), rh = rotateHandle(o), top = toWorld(o, 0, -(o.h || 120) / 2);
      ctx.save();
      ctx.strokeStyle = "#cdab4b";
      ctx.lineWidth = 1.5 * u;
      ctx.beginPath();
      cs.forEach(function (p, i) { if (i) { ctx.lineTo(p.x, p.y); } else { ctx.moveTo(p.x, p.y); } });
      ctx.closePath();
      ctx.stroke();
      ctx.beginPath(); ctx.moveTo(top.x, top.y); ctx.lineTo(rh.x, rh.y); ctx.stroke();
      cs.forEach(function (p) {
        ctx.fillStyle = "#fff";
        ctx.beginPath(); ctx.arc(p.x, p.y, 7 * u, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      });
      ctx.fillStyle = "#cdab4b";
      ctx.beginPath(); ctx.arc(rh.x, rh.y, 8 * u, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "#1f2128"; ctx.lineWidth = 1.6 * u;
      ctx.beginPath(); ctx.arc(rh.x, rh.y, 3.5 * u, -Math.PI * 0.9, Math.PI * 0.6); ctx.stroke();
      ctx.restore();
    }
    $("area-warn").hidden = !(o && outside(o));
    $("empty-hint").hidden = objects().length > 0 || drawing;
    tabs.forEach(function (t) {
      var n = (views[t.getAttribute("data-id")] || []).length, badge = t.querySelector(".ds-view__count");
      if (badge) { badge.textContent = n; badge.hidden = !n; }
    });
  }

  function getImage(src) {
    if (!imageCache[src]) {
      var img = new Image();
      img.onload = draw;
      img.src = src;
      imageCache[src] = img;
    }
    return imageCache[src];
  }

  /* ---------- History and saving ---------- */
  function snapshot() {
    history.push(JSON.stringify(views));
    if (history.length > 80) { history.shift(); }
    future = [];
    updateHistoryButtons();
  }
  function updateHistoryButtons() {
    $("undo").disabled = !history.length;
    $("redo").disabled = !future.length;
  }
  function changed() {
    setSaveState("unsaved");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () { save(false); }, 1200);
  }
  function setSaveState(state) {
    saveState = state;
    var el = $("save-state"), label = el.querySelector("span");
    el.setAttribute("data-state", state);
    label.textContent = {
      saved: "All changes saved", unsaved: "Unsaved changes", saving: "Saving...",
      error: "Couldn't save. Retrying", offline: "Offline. Will retry"
    }[state];
  }
  function previewImage() {
    var off = document.createElement("canvas");
    off.width = SIZE; off.height = SIZE;
    var first = tabs.filter(function (t) { return (views[t.getAttribute("data-id")] || []).length; })[0] || tabs[0];
    render(off.getContext("2d"), first.getAttribute("data-id"), false);
    try { return off.toDataURL("image/jpeg", 0.85); } catch (e) { return null; }
  }
  function payload(withPreview) {
    var quantities = {};
    document.querySelectorAll(".size-qty").forEach(function (el) { if (+el.value > 0) { quantities[el.getAttribute("data-size")] = +el.value; } });
    var data = { design: { version: 2, views: views }, size_quantities: quantities };
    var variant = $("variant"), note = $("note");
    data.variant = variant ? variant.value : root.getAttribute("data-variant") || "";
    data.note = note ? note.value : root.getAttribute("data-note") || "";
    if (!$("variant")) { data.size_quantities = savedQty; }
    if (withPreview) { data.preview = previewImage(); }
    return data;
  }
  function save(force) {
    clearTimeout(saveTimer);
    var now = Date.now();
    // The preview image is the heavy part of a save, so send it at most every 20 seconds.
    var withPreview = force || now - lastPreviewAt > 20000;
    setSaveState("saving");
    return fetch(root.getAttribute("data-save-url"), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(payload(withPreview)),
      credentials: "same-origin"
    }).then(function (res) {
      if (!res.ok) { throw new Error("save failed"); }
      if (withPreview) { lastPreviewAt = now; }
      setSaveState("saved");
    }).catch(function () {
      setSaveState(navigator.onLine === false ? "offline" : "error");
      saveTimer = setTimeout(function () { save(false); }, 5000);
    });
  }
  window.addEventListener("beforeunload", function (e) {
    if (saveState !== "saved") { e.preventDefault(); e.returnValue = ""; }
  });

  /* ---------- Adding things ---------- */
  function add(type, extra) {
    snapshot();
    var a = area();
    var o = Object.assign({ type: type, x: a.x + a.w / 2, y: a.y + a.h / 2, w: 140, h: 140, color: color, scale: 1, rotation: 0, opacity: 1 }, extra || {});
    if (type === "text") { o.size = o.size || 56; o.font = o.font || "Poppins"; o.bold = o.bold !== false; }
    measure(o);
    if (type === "text") {
      // Long phrases start small enough to fit the print area.
      var fit = Math.min(1, (a.w * 0.85) / o.w);
      if (fit < 1) { o.scale = Math.max(0.2, fit); }
    }
    objects().push(o);
    selected = objects().length - 1;
    closeSheet();
    refresh();
    changed();
    pulse();
  }
  function pulse() {
    var stage = $("stage");
    stage.classList.remove("is-pulsing"); void stage.offsetWidth; stage.classList.add("is-pulsing");
  }

  // Text
  $("text-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var value = $("text-input").value.trim();
    if (!value) { $("text-input").focus(); return; }
    add("text", { text: value.slice(0, 120) });
    $("text-input").value = "";
  });
  document.querySelectorAll("[data-phrase]").forEach(function (b) {
    b.addEventListener("click", function () { add("text", { text: b.getAttribute("data-phrase") }); });
  });

  // Shapes
  document.querySelectorAll("[data-shape]").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = b.getAttribute("data-shape");
      var dims = { cross: [120, 170], rect: [180, 120], circle: [150, 150], triangle: [160, 140], star: [160, 160], heart: [160, 150] }[t] || [140, 140];
      add(t, { w: dims[0], h: dims[1] });
    });
  });

  // Uploads (button, drop zone and dropping straight onto the canvas)
  function uploadFile(file) {
    if (!file) { return; }
    if (!/^image\/(png|jpeg|webp)$/.test(file.type)) { toast("Please use a PNG, JPG or WebP image.", true); return; }
    if (file.size > 8 * 1024 * 1024) { toast("That image is over 8 MB. Please choose a smaller one.", true); return; }
    var bar = $("upload-progress"), fill = bar.querySelector("span");
    bar.hidden = false; fill.style.width = "5%";
    var fd = new FormData();
    fd.append("image", file);
    var xhr = new XMLHttpRequest();
    xhr.open("POST", root.getAttribute("data-asset-url"));
    xhr.setRequestHeader("X-CSRFToken", csrf);
    xhr.upload.onprogress = function (e) { if (e.lengthComputable) { fill.style.width = Math.max(5, e.loaded / e.total * 100) + "%"; } };
    xhr.onload = function () {
      bar.hidden = true;
      var data = {};
      try { data = JSON.parse(xhr.responseText); } catch (err) {}
      if (xhr.status !== 200) { toast(data.error || "Upload failed. Please try again.", true); return; }
      addAssetThumb(data.url, true);
      placeImage(data.url);
    };
    xhr.onerror = function () { bar.hidden = true; toast("Upload failed. Check your connection.", true); };
    xhr.send(fd);
  }
  function placeImage(url) {
    var img = getImage(url);
    function go() {
      var a = area(), ratio = Math.min((a.w * 0.7) / img.naturalWidth, (a.h * 0.7) / img.naturalHeight, 1);
      add("image", { src: url, w: img.naturalWidth * ratio, h: img.naturalHeight * ratio });
    }
    if (img.complete && img.naturalWidth) { go(); } else { img.addEventListener("load", go, { once: true }); }
  }
  function addAssetThumb(url, prepend) {
    var list = $("asset-list"), empty = $("assets-empty");
    if (empty) { empty.remove(); }
    var b = document.createElement("button");
    b.type = "button";
    b.className = "ds-asset";
    b.setAttribute("data-src", url);
    b.setAttribute("aria-label", "Add this image again");
    b.innerHTML = '<img src="' + url.replace(/"/g, "") + '" alt="">';
    b.addEventListener("click", function () { placeImage(url); });
    if (prepend) { list.insertBefore(b, list.firstChild); } else { list.appendChild(b); }
  }
  document.querySelectorAll(".ds-asset").forEach(function (b) {
    b.addEventListener("click", function () { placeImage(b.getAttribute("data-src")); });
  });
  $("image-upload").addEventListener("change", function (e) { uploadFile(e.target.files[0]); e.target.value = ""; });
  [$("drop-zone"), $("stage")].forEach(function (zone) {
    zone.addEventListener("dragover", function (e) { e.preventDefault(); root.classList.add("is-dropping"); });
    zone.addEventListener("dragleave", function () { root.classList.remove("is-dropping"); });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      root.classList.remove("is-dropping");
      uploadFile(e.dataTransfer.files && e.dataTransfer.files[0]);
    });
  });

  // Freehand drawing
  function setDrawing(on) {
    drawing = on;
    selected = on ? -1 : selected;
    root.classList.toggle("is-drawing", on);
    $("draw-toggle").innerHTML = on ? '<i class="fa fa-check"></i> Done drawing' : '<i class="fa fa-pencil"></i> Start drawing';
    $("draw-toggle").classList.toggle("lot-btn-secondary", on);
    if (on) { closeSheet(); }
    refresh();
  }
  $("draw-toggle").addEventListener("click", function () { setDrawing(!drawing); });
  $("draw-done").addEventListener("click", function () { setDrawing(false); });

  /* ---------- Pointer interaction ---------- */
  function point(e) {
    var r = canvas.getBoundingClientRect();
    return { x: (e.clientX - r.left) * SIZE / r.width, y: (e.clientY - r.top) * SIZE / r.height };
  }
  canvas.addEventListener("pointerdown", function (e) {
    var p = point(e), u = unit();
    canvas.setPointerCapture(e.pointerId);
    if (drawing) {
      snapshot();
      objects().push({ type: "path", x: p.x, y: p.y, w: 20, h: 20, color: color, lineWidth: +$("brush-size").value, points: [{ x: 0, y: 0 }], rel: true, scale: 1, rotation: 0, opacity: 1 });
      selected = objects().length - 1;
      mode = "draw";
      return;
    }
    var o = current();
    if (o && near(p, rotateHandle(o), 16 * u)) {
      snapshot(); mode = "rotate";
      dragStart = { angle: Math.atan2(p.y - o.y, p.x - o.x) * 180 / Math.PI - (o.rotation || 0) };
    } else if (o && corners(o).some(function (c) { return near(p, c, 16 * u); })) {
      snapshot(); mode = "scale";
      dragStart = { dist: Math.max(Math.hypot(p.x - o.x, p.y - o.y), 1), scale: o.scale || 1 };
    } else {
      selected = hit(p);
      if (selected >= 0) {
        snapshot(); mode = "move";
        dragStart = { x: p.x, y: p.y };
      } else {
        mode = null;
      }
      refresh();
    }
  });
  canvas.addEventListener("pointermove", function (e) {
    var p = point(e), u = unit(), o = current();
    if (!mode) {
      // Helpful cursors when hovering handles and items.
      var cursor = drawing ? "crosshair" : "default";
      if (!drawing && o && near(p, rotateHandle(o), 16 * u)) { cursor = "grab"; }
      else if (!drawing && o && corners(o).some(function (c) { return near(p, c, 16 * u); })) { cursor = "nwse-resize"; }
      else if (!drawing && hit(p) >= 0) { cursor = "move"; }
      canvas.style.cursor = cursor;
      return;
    }
    if (!o) { return; }
    if (mode === "draw") {
      o.points.push({ x: p.x - o.x, y: p.y - o.y });
    } else if (mode === "move") {
      o.x += p.x - dragStart.x;
      o.y += p.y - dragStart.y;
      dragStart = { x: p.x, y: p.y };
      clampCentre(o);
      var a = area(), snap = 10 * u;
      guides.v = Math.abs(o.x - (a.x + a.w / 2)) < snap;
      guides.h = Math.abs(o.y - (a.y + a.h / 2)) < snap;
      if (guides.v) { o.x = a.x + a.w / 2; }
      if (guides.h) { o.y = a.y + a.h / 2; }
    } else if (mode === "scale") {
      o.scale = Math.max(0.1, Math.min(8, dragStart.scale * Math.hypot(p.x - o.x, p.y - o.y) / dragStart.dist));
    } else if (mode === "rotate") {
      var deg = Math.atan2(p.y - o.y, p.x - o.x) * 180 / Math.PI - dragStart.angle;
      deg = ((deg + 540) % 360) - 180;
      // Snap to 0 / 45 / 90 degrees when close.
      var nearest = Math.round(deg / 45) * 45;
      o.rotation = Math.abs(deg - nearest) < 4 ? nearest : Math.round(deg);
    }
    draw();
    syncProps();
  });
  function endPointer() {
    if (!mode) { return; }
    if (mode === "draw") {
      var o = current();
      if (o && o.points.length < 2) { objects().pop(); }
      selected = -1;
    }
    mode = null;
    guides = { v: false, h: false };
    refresh();
    changed();
  }
  canvas.addEventListener("pointerup", endPointer);
  canvas.addEventListener("pointercancel", endPointer);
  canvas.addEventListener("dblclick", function (e) {
    var i = hit(point(e));
    if (i >= 0 && objects()[i].type === "text") { selected = i; refresh(); $("prop-text").focus(); $("prop-text").select(); }
  });

  /* ---------- Properties panel ---------- */
  var TYPE_NAMES = { text: "Text", image: "Image", path: "Drawing", rect: "Square", circle: "Circle", triangle: "Triangle", star: "Star", heart: "Heart", cross: "Cross" };
  var TYPE_ICONS = { text: "fa-font", image: "fa-image", path: "fa-pencil", rect: "fa-square", circle: "fa-circle", triangle: "fa-play", star: "fa-star", heart: "fa-heart", cross: "fa-plus" };

  function buildSwatches() {
    var box = $("swatches");
    SWATCHES.forEach(function (hex) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "ds-swatch";
      b.style.background = hex;
      b.setAttribute("data-color", hex);
      b.setAttribute("aria-label", "Colour " + hex);
      b.addEventListener("click", function () { setColor(hex); });
      box.appendChild(b);
    });
    var custom = document.createElement("label");
    custom.className = "ds-swatch ds-swatch--custom";
    custom.setAttribute("aria-label", "Custom colour");
    custom.innerHTML = '<i class="fa fa-eyedropper"></i><input type="color" id="custom-color" value="#111111">';
    box.appendChild(custom);
    $("custom-color").addEventListener("input", function (e) { setColor(e.target.value, true); });
    $("custom-color").addEventListener("change", function () { sliderActive = false; });
    document.querySelectorAll("[data-brush-color]").forEach(function (b) {
      b.addEventListener("click", function () { setColor(b.getAttribute("data-brush-color")); });
    });
  }
  function setColor(hex, continuous) {
    color = hex;
    var o = current();
    if (o && o.type !== "image") {
      if (!continuous || !sliderActive) { snapshot(); sliderActive = !!continuous; }
      o.color = hex;
      draw();
      changed();
    }
    markSwatch();
  }
  function markSwatch() {
    var c = (current() && current().color) || color;
    document.querySelectorAll(".ds-swatch[data-color], [data-brush-color]").forEach(function (s) {
      s.classList.toggle("is-active", (s.getAttribute("data-color") || s.getAttribute("data-brush-color")) === c);
    });
  }

  var lastShown = null;
  function isPhone() { return window.matchMedia("(max-width: 900px)").matches; }
  // Keep the product visible above the bottom sheet on phones.
  function revealCanvas() {
    var top = $("stage").getBoundingClientRect().top + window.scrollY;
    var headerH = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--header-h"), 10) || 80;
    window.scrollTo({ top: Math.max(0, top - headerH - 8), behavior: "smooth" });
  }

  function syncProps() {
    var o = current(), empty = $("props-empty"), edit = $("props-edit");
    root.classList.toggle("has-selection", !!o);
    empty.hidden = !!o;
    edit.hidden = !o;
    if (!o) { lastShown = null; return; }
    // Phones show one sheet at a time: the selected item's options replace the tool sheet.
    if (isPhone()) {
      closeSheet();
      if (o !== lastShown) { revealCanvas(); }
    }
    lastShown = o;
    $("props-title").innerHTML = '<i class="fa ' + (TYPE_ICONS[o.type] || "fa-square") + '"></i> ' + (TYPE_NAMES[o.type] || "Item");
    edit.querySelectorAll("[data-for]").forEach(function (f) {
      f.hidden = f.getAttribute("data-for").split(" ").indexOf(o.type === "text" ? "text" : o.type === "image" ? "image" : o.type === "path" ? "path" : "shape") === -1;
    });
    if (document.activeElement !== $("prop-text")) { $("prop-text").value = o.text || ""; }
    $("prop-font").value = o.font || "Poppins";
    $("prop-bold").classList.toggle("is-active", !!o.bold);
    $("prop-italic").classList.toggle("is-active", !!o.italic);
    $("prop-size").value = Math.round((o.scale || 1) * 100);
    $("size-out").textContent = Math.round((o.scale || 1) * 100) + "%";
    $("prop-rotation").value = Math.round(o.rotation || 0);
    $("rotation-out").textContent = Math.round(o.rotation || 0) + "°";
    $("prop-opacity").value = Math.round((o.opacity == null ? 1 : o.opacity) * 100);
    $("opacity-out").textContent = Math.round((o.opacity == null ? 1 : o.opacity) * 100) + "%";
    markSwatch();
  }
  function editProp(fn) {
    var o = current();
    if (!o) { return; }
    if (!sliderActive) { snapshot(); sliderActive = true; }
    fn(o);
    measure(o);
    draw();
    syncProps();
    changed();
  }
  function endEdit() { sliderActive = false; layers(); }
  [["prop-size", function (o, v) { o.scale = v / 100; }], ["prop-rotation", function (o, v) { o.rotation = v; }], ["prop-opacity", function (o, v) { o.opacity = v / 100; }]].forEach(function (pair) {
    var el = $(pair[0]);
    el.addEventListener("input", function () { editProp(function (o) { pair[1](o, +el.value); }); });
    el.addEventListener("change", endEdit);
  });
  $("prop-text").addEventListener("input", function (e) { editProp(function (o) { o.text = e.target.value.slice(0, 120) || " "; }); });
  $("prop-text").addEventListener("change", endEdit);
  $("prop-font").addEventListener("change", function (e) {
    var font = e.target.value;
    loadFont(font).then(function () { editProp(function (o) { o.font = font; }); endEdit(); });
  });
  $("prop-bold").addEventListener("click", function () { editProp(function (o) { o.bold = !o.bold; }); endEdit(); });
  $("prop-italic").addEventListener("click", function () { editProp(function (o) { o.italic = !o.italic; }); endEdit(); });

  function loadFont(font) {
    if (!document.fonts || !document.fonts.load) { return Promise.resolve(); }
    return document.fonts.load("700 48px \"" + font + "\"").catch(function () {});
  }

  // Item actions
  function act(name) {
    var o = current();
    if (!o) { return; }
    var list = objects(), a = area();
    if (name === "delete") { snapshot(); list.splice(selected, 1); selected = -1; }
    else if (name === "duplicate") {
      snapshot();
      var copy = JSON.parse(JSON.stringify(o));
      copy.x += 24; copy.y += 24; clampCentre(copy);
      list.push(copy); selected = list.length - 1;
    }
    else if (name === "forward" && selected < list.length - 1) { snapshot(); list.splice(selected + 1, 0, list.splice(selected, 1)[0]); selected++; }
    else if (name === "backward" && selected > 0) { snapshot(); list.splice(selected - 1, 0, list.splice(selected, 1)[0]); selected--; }
    else if (name === "center") { snapshot(); o.x = a.x + a.w / 2; o.y = a.y + a.h / 2; }
    else if (name === "flip") { snapshot(); o.flipX = !o.flipX; }
    else if (name === "fit") {
      snapshot();
      measure(o);
      o.scale = Math.max(0.1, Math.min((a.w * 0.9) / o.w, (a.h * 0.9) / o.h));
      o.rotation = 0; o.x = a.x + a.w / 2; o.y = a.y + a.h / 2;
    }
    else { return; }
    refresh();
    changed();
  }
  document.querySelectorAll("[data-act]").forEach(function (b) {
    b.addEventListener("click", function () { act(b.getAttribute("data-act")); });
  });
  $("deselect").addEventListener("click", function () { selected = -1; refresh(); });

  /* ---------- Layers ---------- */
  function layers() {
    var box = $("layer-list"), list = objects();
    box.innerHTML = "";
    $("layers-empty").hidden = list.length > 0;
    list.slice().reverse().forEach(function (o, rev) {
      var i = list.length - 1 - rev;
      var li = document.createElement("li");
      li.className = "ds-layer" + (i === selected ? " is-active" : "");
      var label = o.type === "text" ? String(o.text || "").replace(/\s+/g, " ").slice(0, 28) : (TYPE_NAMES[o.type] || o.type);
      li.innerHTML =
        '<button type="button" class="ds-layer__main"><span class="ds-layer__icon">' +
        (o.type === "image" ? '<img src="' + String(o.src).replace(/"/g, "") + '" alt="">' : '<i class="fa ' + (TYPE_ICONS[o.type] || "fa-square") + '" style="color:' + (o.color || "#111") + '"></i>') +
        "</span><span></span></button>" +
        '<button type="button" class="ds-layer__btn" data-move="up" aria-label="Move up"><i class="fa fa-chevron-up"></i></button>' +
        '<button type="button" class="ds-layer__btn" data-move="down" aria-label="Move down"><i class="fa fa-chevron-down"></i></button>' +
        '<button type="button" class="ds-layer__btn ds-layer__btn--danger" data-move="delete" aria-label="Delete"><i class="fa fa-trash"></i></button>';
      li.querySelector(".ds-layer__main span:last-child").textContent = label;
      li.querySelector(".ds-layer__main").addEventListener("click", function () { selected = i; refresh(); });
      li.querySelectorAll("[data-move]").forEach(function (b) {
        b.addEventListener("click", function () {
          selected = i;
          act({ up: "forward", down: "backward", delete: "delete" }[b.getAttribute("data-move")]);
        });
      });
      box.appendChild(li);
    });
  }

  function refresh() { draw(); layers(); syncProps(); updateHistoryButtons(); }

  /* ---------- Undo / redo / preview / zoom ---------- */
  function undo() {
    if (!history.length) { return; }
    future.push(JSON.stringify(views));
    views = JSON.parse(history.pop());
    selected = -1; refresh(); changed();
  }
  function redo() {
    if (!future.length) { return; }
    history.push(JSON.stringify(views));
    views = JSON.parse(future.pop());
    selected = -1; refresh(); changed();
  }
  $("undo").addEventListener("click", undo);
  $("redo").addEventListener("click", redo);
  $("preview-toggle").addEventListener("click", function () {
    previewMode = !previewMode;
    this.setAttribute("aria-pressed", previewMode ? "true" : "false");
    root.classList.toggle("is-preview", previewMode);
    if (previewMode) { selected = -1; }
    refresh();
  });

  var zoom = 100;
  function setZoom(z) {
    zoom = Math.max(50, Math.min(200, z));
    $("stage").style.width = "min(100%, " + Math.round(zoom * 6.4) + "px)";
    if (zoom > 100) { $("stage").style.width = Math.round(zoom * 6.4) + "px"; }
    $("zoom-label").textContent = zoom + "%";
    draw();
  }
  $("zoom-in").addEventListener("click", function () { setZoom(zoom + 25); });
  $("zoom-out").addEventListener("click", function () { setZoom(zoom - 25); });
  $("zoom-fit").addEventListener("click", function () { setZoom(100); });
  window.addEventListener("resize", draw);

  /* ---------- Tool panels (side panel on desktop, bottom sheet on phones) ---------- */
  var railButtons = document.querySelectorAll(".ds-rail [data-panel]");
  function openPanel(name) {
    railButtons.forEach(function (b) {
      var on = b.getAttribute("data-panel") === name;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    document.querySelectorAll(".ds-pane").forEach(function (p) { p.classList.toggle("is-active", p.getAttribute("data-pane") === name); });
    root.classList.add("is-sheet-open");
    if (name === "layers") { layers(); }
    if (isPhone()) { revealCanvas(); }
  }
  function closeSheet() { root.classList.remove("is-sheet-open"); }
  railButtons.forEach(function (b) {
    b.addEventListener("click", function () {
      var name = b.getAttribute("data-panel");
      if (root.classList.contains("is-sheet-open") && b.classList.contains("is-active") && window.matchMedia("(max-width: 900px)").matches) { closeSheet(); return; }
      if (name !== "draw" && drawing) { setDrawing(false); }
      openPanel(name);
      if (name === "text") { setTimeout(function () { $("text-input").focus(); }, 150); }
    });
  });
  document.querySelectorAll("[data-open-panel]").forEach(function (b) {
    b.addEventListener("click", function () { openPanel(b.getAttribute("data-open-panel")); });
  });
  document.querySelectorAll("[data-close-sheet]").forEach(function (b) { b.addEventListener("click", closeSheet); });

  /* ---------- Keyboard ---------- */
  window.addEventListener("keydown", function (e) {
    var typing = /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);
    var key = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && key === "z") { e.preventDefault(); if (e.shiftKey) { redo(); } else { undo(); } return; }
    if ((e.ctrlKey || e.metaKey) && key === "y") { e.preventDefault(); redo(); return; }
    if (typing) { return; }
    if ((e.ctrlKey || e.metaKey) && key === "d") { e.preventDefault(); act("duplicate"); return; }
    if (e.key === "Delete" || e.key === "Backspace") { if (current()) { e.preventDefault(); act("delete"); } return; }
    if (e.key === "Escape") { if (drawing) { setDrawing(false); } else { selected = -1; closeSheet(); refresh(); } return; }
    var o = current();
    if (o && /^Arrow/.test(e.key)) {
      e.preventDefault();
      var step = e.shiftKey ? 10 : 2;
      if (!sliderActive) { snapshot(); sliderActive = true; }
      if (e.key === "ArrowLeft") { o.x -= step; } if (e.key === "ArrowRight") { o.x += step; }
      if (e.key === "ArrowUp") { o.y -= step; } if (e.key === "ArrowDown") { o.y += step; }
      clampCentre(o); draw(); changed();
    }
  });
  window.addEventListener("keyup", function (e) { if (/^Arrow/.test(e.key)) { sliderActive = false; } });

  /* ---------- First-visit guide ---------- */
  var coach = $("coach"), steps = coach ? coach.querySelectorAll(".ds-coach__step") : [], stepIndex = 0;
  function showStep(i) {
    stepIndex = i;
    steps.forEach(function (s, n) { s.hidden = n !== i; });
    coach.querySelectorAll(".ds-coach__dots span").forEach(function (d, n) { d.classList.toggle("is-active", n === i); });
    $("coach-next").textContent = i === steps.length - 1 ? "Start designing" : "Next";
  }
  function closeCoach() { coach.hidden = true; try { localStorage.setItem("lot-ds-coach", "1"); } catch (e) {} }
  if (coach) {
    $("coach-next").addEventListener("click", function () { if (stepIndex < steps.length - 1) { showStep(stepIndex + 1); } else { closeCoach(); } });
    $("coach-skip").addEventListener("click", closeCoach);
    $("help-btn").addEventListener("click", function () { coach.hidden = false; showStep(0); });
    var seen = false;
    try { seen = localStorage.getItem("lot-ds-coach") === "1"; } catch (e) {}
    if (!seen) { coach.hidden = false; showStep(0); }
  }

  /* ---------- Submit for a quote ---------- */
  var dialog = $("submit-dialog");
  function totalQty() {
    var err = $("submit-error");
    if (err) { err.hidden = true; }
    var total = 0;
    document.querySelectorAll(".size-qty").forEach(function (el) { total += Math.max(0, +el.value || 0); });
    var out = $("qty-total");
    if (out) { out.textContent = total; }
    return total;
  }
  document.querySelectorAll(".size-qty").forEach(function (el) {
    el.value = savedQty[el.getAttribute("data-size")] || 0;
    el.addEventListener("input", function () { totalQty(); changed(); });
  });
  document.querySelectorAll("[data-qty-step]").forEach(function (b) {
    b.addEventListener("click", function () {
      var input = b.parentElement.querySelector(".size-qty");
      input.value = Math.max(0, Math.min(10000, (+input.value || 0) + +b.getAttribute("data-qty-step")));
      totalQty(); changed();
    });
  });
  totalQty();
  ["variant", "note"].forEach(function (id) { if ($(id)) { $(id).addEventListener("input", changed); } });

  $("open-submit").addEventListener("click", function () {
    var count = Object.keys(views).reduce(function (n, k) { return n + (views[k] || []).length; }, 0);
    if (!count) {
      toast("Add some artwork or text first.", true);
      openPanel("upload");
      return;
    }
    selected = -1; refresh();
    var thumbs = $("submit-previews");
    if (thumbs) {
      thumbs.innerHTML = "";
      tabs.forEach(function (t) {
        var id = t.getAttribute("data-id");
        if (!(views[id] || []).length) { return; }
        var off = document.createElement("canvas");
        off.width = SIZE; off.height = SIZE;
        render(off.getContext("2d"), id, false);
        var fig = document.createElement("figure");
        var img = document.createElement("img");
        try { img.src = off.toDataURL("image/jpeg", 0.7); } catch (e) {}
        img.alt = t.getAttribute("data-name") + " preview";
        var cap = document.createElement("figcaption");
        cap.textContent = t.getAttribute("data-name");
        fig.appendChild(img); fig.appendChild(cap);
        thumbs.appendChild(fig);
      });
    }
    save(true);
    if (dialog.showModal) { dialog.showModal(); } else { dialog.setAttribute("open", ""); }
  });
  document.querySelectorAll("[data-close-dialog]").forEach(function (b) { b.addEventListener("click", function () { dialog.close(); }); });
  if ($("rights")) { $("rights").addEventListener("change", function () { $("submit-error").hidden = true; }); }
  var form = $("submit-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var err = $("submit-error");
      var total = totalQty();
      if (!total) { err.textContent = "Enter how many you need for at least one size."; err.hidden = false; return; }
      if (!$("rights").checked) { err.textContent = "Please confirm you have the right to use this artwork."; err.hidden = false; return; }
      err.hidden = true;
      var btn = $("submit-final");
      btn.disabled = true;
      btn.classList.add("is-loading");
      save(true).then(function () { saveState = "saved"; form.submit(); });
    });
  }

  function toast(msg, isError) {
    if (window.LOT && window.LOT.toast) { window.LOT.toast(msg, { type: isError ? "error" : "ok" }); } else { window.alert(msg); }
  }

  /* ---------- Start ---------- */
  buildSwatches();
  if (document.fonts && document.fonts.ready) { document.fonts.ready.then(draw); }
  setSaveState("saved");
  root.classList.add("is-ready");
  refresh();
  if (!authed) { root.setAttribute("data-guest", "1"); }
})();
