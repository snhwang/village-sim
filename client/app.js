// Hearthwick map viewer. Live mode follows the running village over a
// websocket. Replay mode plays back a saved run from its frames and events.
"use strict";

const PLACE_COLORS = {
  home: "#d8b48c", well: "#9cc3e6", market: "#f3d38a", inn: "#e3a47c",
  shrine: "#d5c6ee", schoolyard: "#efe2a2", mill: "#c8b699", fields: "#b5d487",
  watchpost: "#b3a592", road: "#d9caa4", forest: "#6f9d61",
};
const STAGE_COLORS = { child: "#e9a324", apprentice: "#4f9a55", adult: "#3b73b9", elder: "#8458b8" };
const ACTIVITY_GLYPH = { rest: "z", work: "⚒", talk: "…", play: "✦", follow: "»" };
const BUBBLE_TICKS = 8;

const $ = (id) => document.getElementById(id);
const canvas = $("map");
const ctx = canvas.getContext("2d");

const S = {
  mode: null, world: null, roster: {}, selected: null,
  frame: null, prev: {}, frameAt: 0, interval: 500,
  decisions: {}, convs: {}, utterances: [],
  running: true, speed: 2,
  ws: null,
  frames: [], events: [], eventCursor: 0, replayIndex: 0, replayTimer: null,
  bg: null, tile: 16, ox: 0, oy: 0,
  detailKey: "",
};

// ---------------------------------------------------------------------------
// Formatting helpers

function fmtClock(clock) {
  if (!clock) return "…";
  const h = Math.floor(clock.hour), m = Math.round((clock.hour - h) * 60);
  const hh = String(h).padStart(2, "0"), mm = String(m).padStart(2, "0");
  return `Year ${clock.year} · Day ${clock.day} · ${hh}:${mm} (${clock.part})`;
}

function tickTime(t) {
  const minutes = 6 * 60 + t * 10;
  const day = Math.floor(minutes / 1440), m = minutes % 1440;
  return `d${day} ${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "onclick") node.addEventListener("click", v);
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}

const nameOf = (id) => (S.roster[id] ? S.roster[id].name : id);

// ---------------------------------------------------------------------------
// Events

function applyEvent(e, { feed = true } = {}) {
  switch (e.type) {
    case "roster":
      for (const c of e.characters) S.roster[c.id] = c;
      renderRoster();
      break;
    case "decision":
      S.decisions[e.character] = e;
      break;
    case "conversation_start":
      S.convs[e.conversation] = e;
      if (feed) addFeed(e);
      break;
    case "utterance":
      S.utterances.push(e);
      if (S.utterances.length > 400) S.utterances.splice(0, 100);
      if (feed) addFeed(e);
      break;
    case "conversation_end":
      delete S.convs[e.conversation];
      break;
  }
}

function addFeed(e) {
  const list = $("feed");
  const who = (id) => el("span", { class: "who", onclick: () => select(id) }, nameOf(id));
  let li;
  if (e.type === "utterance") {
    li = el("li", {}, el("span", { class: "when" }, tickTime(e.t)), who(e.speaker), ": ", e.text);
  } else {
    li = el("li", {}, el("span", { class: "when" }, tickTime(e.t)),
      who(e.participants[0]), " talks with ", who(e.participants[1]),
      el("span", { class: "topic" }, ` · ${e.topic}`));
  }
  list.prepend(li);
  while (list.children.length > 200) list.lastChild.remove();
}

// ---------------------------------------------------------------------------
// Frames

function setFrame(frame, animate = true) {
  const prev = {};
  if (S.frame && animate) for (const c of S.frame.c) prev[c[0]] = [c[1], c[2]];
  S.prev = prev;
  S.frame = frame;
  S.frameAt = performance.now();
  S.interval = 1000 / Math.max(S.speed, 0.1);
  $("clock").textContent = fmtClock(frame.clock);
  renderDetail();
}

// ---------------------------------------------------------------------------
// Drawing

function resize() {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (!S.world) return;
  S.tile = Math.max(6, Math.floor(Math.min(w / S.world.width, h / S.world.height)));
  S.ox = Math.floor((w - S.tile * S.world.width) / 2);
  S.oy = Math.floor((h - S.tile * S.world.height) / 2);
  S.bg = drawBackground(Math.round(w * dpr), Math.round(h * dpr), dpr);
}

function drawBackground(pw, ph, dpr) {
  const off = document.createElement("canvas");
  off.width = pw; off.height = ph;
  const g = off.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  const T = S.tile, W = S.world;
  const X = (x) => S.ox + x * T, Y = (y) => S.oy + y * T;

  g.fillStyle = "#cfe0b2";
  g.fillRect(X(0), Y(0), W.width * T, W.height * T);
  g.strokeStyle = "rgba(0,0,0,0.035)";
  for (let x = 0; x <= W.width; x++) { g.beginPath(); g.moveTo(X(x), Y(0)); g.lineTo(X(x), Y(W.height)); g.stroke(); }
  for (let y = 0; y <= W.height; y++) { g.beginPath(); g.moveTo(X(0), Y(y)); g.lineTo(X(W.width), Y(y)); g.stroke(); }

  for (const b of W.blocked) {
    const [x, y, w, h] = b.rect;
    g.fillStyle = "#79aed3";
    g.fillRect(X(x), Y(y), w * T, h * T);
  }

  for (const p of W.places) {
    const [x, y, w, h] = p.rect;
    g.fillStyle = PLACE_COLORS[p.kind] || "#ddd";
    g.fillRect(X(x) + 1, Y(y) + 1, w * T - 2, h * T - 2);
    if (p.kind === "fields") {
      g.strokeStyle = "rgba(90,120,50,0.35)";
      for (let r = y + 0.5; r < y + h; r += 1) {
        g.beginPath(); g.moveTo(X(x) + 4, Y(r)); g.lineTo(X(x + w) - 4, Y(r)); g.stroke();
      }
    }
    if (p.kind === "forest") {
      g.fillStyle = "rgba(40,80,40,0.45)";
      for (let i = 0; i < w * h / 3; i++) {
        const tx = x + ((i * 7) % w) + 0.5, ty = y + ((i * 5) % h) + 0.5;
        g.beginPath(); g.arc(X(tx), Y(ty), T * 0.35, 0, Math.PI * 2); g.fill();
      }
    }
    g.strokeStyle = "rgba(60,45,30,0.35)";
    g.strokeRect(X(x) + 1, Y(y) + 1, w * T - 2, h * T - 2);
    g.fillStyle = "rgba(40,30,20,0.8)";
    g.font = `${Math.max(9, Math.round(T * 0.55))}px "Segoe UI", sans-serif`;
    const label = p.kind === "home" ? p.name.replace(/'s house| house/, "").replace("the ", "") : p.name.replace(/^the /, "");
    g.fillText(label, X(x) + 3, Y(y) + Math.max(10, T * 0.7));
  }
  return off;
}

function positions(now) {
  const out = [];
  if (!S.frame) return out;
  const k = Math.min(1, (now - S.frameAt) / S.interval);
  const sharing = {};
  for (const c of S.frame.c) (sharing[`${c[1]},${c[2]}`] ||= []).push(c[0]);
  for (const c of S.frame.c) {
    const [id, x, y, act, stage] = c;
    const p = S.prev[id];
    let px = p ? p[0] + (x - p[0]) * k : x;
    let py = p ? p[1] + (y - p[1]) * k : y;
    // Fan out villagers standing on the same tile so both stay readable.
    const group = sharing[`${x},${y}`];
    if (group.length > 1) {
      const i = group.indexOf(id), angle = (2 * Math.PI * i) / group.length;
      px += 0.45 * Math.cos(angle);
      py += 0.45 * Math.sin(angle);
    }
    out.push({ id, x: px, y: py, act, stage });
  }
  return out;
}

function draw(now) {
  const w = canvas.clientWidth, h = canvas.clientHeight;
  ctx.clearRect(0, 0, w, h);
  if (S.bg) {
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(S.bg, 0, 0); ctx.restore();
  }
  const T = S.tile;
  const px = (x) => S.ox + (x + 0.5) * T, py = (y) => S.oy + (y + 0.5) * T;
  const chars = positions(now);
  const tick = S.frame ? S.frame.t : 0;

  for (const c of chars) {
    const cx = px(c.x), cy = py(c.y), r = T * 0.46;
    if (c.id === S.selected) {
      ctx.beginPath(); ctx.arc(cx, cy, r + 4, 0, Math.PI * 2);
      ctx.strokeStyle = "#b4552d"; ctx.lineWidth = 3; ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = STAGE_COLORS[c.stage] || "#777"; ctx.fill();
    ctx.lineWidth = 1.5; ctx.strokeStyle = "#fff"; ctx.stroke();
    ctx.fillStyle = "#fff";
    ctx.font = `bold ${Math.round(T * 0.55)}px "Segoe UI", sans-serif`;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(nameOf(c.id)[0], cx, cy + 0.5);
    ctx.fillStyle = "rgba(30,25,20,0.9)";
    ctx.font = `${Math.max(9, Math.round(T * 0.5))}px "Segoe UI", sans-serif`;
    ctx.fillText(nameOf(c.id), cx, cy + r + Math.max(8, T * 0.45));
    const glyph = ACTIVITY_GLYPH[c.act];
    if (glyph) {
      ctx.font = `bold ${Math.round(T * 0.5)}px "Segoe UI", sans-serif`;
      ctx.fillStyle = "rgba(30,25,20,0.85)";
      ctx.fillText(glyph, cx + r, cy - r);
    }
  }

  // Speech bubbles: latest recent line per speaker, or a marker for silent talk.
  const latest = {};
  for (const u of S.utterances) if (tick - u.t <= BUBBLE_TICKS && u.t <= tick) latest[u.speaker] = u;
  const inConv = new Set();
  for (const conv of Object.values(S.convs)) for (const p of conv.participants) inConv.add(p);
  ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  for (const c of chars) {
    const u = latest[c.id];
    const text = u ? u.text : (inConv.has(c.id) && c.act === "talk" ? "…" : null);
    if (text) bubble(px(c.x), py(c.y) - T * 0.7, text, T);
  }
  requestAnimationFrame(draw);
}

function bubble(x, y, text, T) {
  const size = Math.max(10, Math.round(T * 0.55));
  ctx.font = `${size}px "Segoe UI", sans-serif`;
  const maxW = T * 11;
  const words = text.split(" "), lines = [];
  let line = "";
  for (const w of words) {
    const test = line ? line + " " + w : w;
    if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
  }
  if (line) lines.push(line);
  const shown = lines.slice(0, 3);
  if (lines.length > 3) shown[2] += " …";
  const lh = size * 1.25;
  const bw = Math.max(...shown.map((l) => ctx.measureText(l).width)) + 12;
  const bh = shown.length * lh + 8;
  const bx = Math.min(Math.max(4, x - bw / 2), canvas.clientWidth - bw - 4);
  const by = Math.max(4, y - bh);
  ctx.fillStyle = "rgba(255,253,246,0.95)";
  ctx.strokeStyle = "rgba(60,45,30,0.5)";
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.roundRect(bx, by, bw, bh, 6); ctx.fill(); ctx.stroke();
  ctx.fillStyle = "#2b2620";
  shown.forEach((l, i) => ctx.fillText(l, bx + 6, by + 4 + size + i * lh));
}

canvas.addEventListener("click", (ev) => {
  const rect = canvas.getBoundingClientRect();
  const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
  let best = null, bestD = Infinity;
  for (const c of positions(performance.now())) {
    const dx = S.ox + (c.x + 0.5) * S.tile - mx, dy = S.oy + (c.y + 0.5) * S.tile - my;
    const d = Math.hypot(dx, dy);
    if (d < bestD) { bestD = d; best = c.id; }
  }
  if (best && bestD < S.tile * 1.2) select(best);
});

// ---------------------------------------------------------------------------
// Panel

function selectFromUrl() {
  const id = new URL(location.href).searchParams.get("select");
  if (id && S.roster[id]) select(id);
}

function select(id) {
  S.selected = id;
  S.detailKey = "";
  renderRoster();
  renderDetail();
}

function renderRoster() {
  const box = $("roster");
  box.replaceChildren(...Object.values(S.roster).map((c) =>
    el("button", { class: c.id === S.selected ? "selected" : "", onclick: () => select(c.id), type: "button" },
      el("i", { class: `dot ${c.stage}` }), c.name)));
}

function renderDetail() {
  const id = S.selected;
  if (!id || !S.roster[id]) return;
  const c = S.roster[id];
  const d = S.decisions[id];
  const fc = S.frame ? S.frame.c.find((x) => x[0] === id) : null;
  const key = JSON.stringify([id, d && d.t, fc && fc.slice(3)]);
  if (key === S.detailKey) return;
  S.detailKey = key;

  const family = [];
  for (const p of c.parents || []) family.push(`child of ${nameOf(p)}`);
  if (c.partner) family.push(`married to ${nameOf(c.partner)}`);
  if (c.mentor) family.push(`apprenticed to ${nameOf(c.mentor)}`);

  const box = $("detail");
  const nodes = [
    el("h2", {}, c.name),
    el("p", { class: "sub" },
      [fc ? `${fc[4]}, age ${fc[5].toFixed(1)}` : c.stage, c.role, ...family].filter(Boolean).join(" · ")),
    el("div", { class: "chips" }, ...Object.entries(c.temperament).map(([k, v]) => el("span", { class: "chip", title: k }, v))),
    el("p", { class: "persona" }, c.persona),
    el("h3", {}, "Now"),
    el("p", {}, fc ? fc[3] : "…"),
  ];
  if (d) {
    nodes.push(
      el("h3", {}, `Last decision · ${tickTime(d.t)}`),
      el("p", { class: "query" }, d.query),
      el("div", { class: "chips" }, ...d.tags.map((t) => el("span", { class: "chip gate" }, t))),
      el("h3", {}, "Retrieved instructions"),
      el("ul", { class: "retrieved" }, ...d.retrieved.map((r) =>
        el("li", { class: r.id === d.chosen ? "chosen" : (r.actionable ? "" : "passive") },
          el("span", {}, r.id), el("span", {}, r.score.toFixed(3))))),
      el("p", { class: "actions" }, d.actions.length
        ? d.actions.map((a) => `${a.kind}(${Object.entries(a.data).map(([k, v]) => `${k}=${v}`).join(", ")})`).join("  →  ")
        : "no action"),
    );
  }
  const lines = S.utterances.filter((u) => u.speaker === id).slice(-5).reverse();
  if (lines.length) {
    nodes.push(el("h3", {}, "Recent lines"), ...lines.map((u) => el("p", {}, `“${u.text}”`)));
  }
  box.replaceChildren(...nodes);
}

// ---------------------------------------------------------------------------
// Live mode

function startLive() {
  stopReplay();
  S.mode = "live";
  $("scrub-wrap").hidden = true;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  S.ws = ws;
  ws.onmessage = (msg) => {
    const m = JSON.parse(msg.data);
    if (m.type === "hello") {
      resetState();
      for (const c of m.roster) S.roster[c.id] = c;
      S.decisions = { ...m.decisions };
      for (const e of m.recent) applyEvent(e);
      setControls(m.running, m.speed);
      $("clock").textContent = fmtClock(m.clock);
      $("status").textContent = statusText(m.meta);
      renderRoster();
      if (m.frame) setFrame(m.frame, false);
      selectFromUrl();
    } else if (m.type === "tick") {
      for (const e of m.events) applyEvent(e);
      setFrame(m.frame);
    } else if (m.type === "events") {
      for (const e of m.events) applyEvent(e);
    } else if (m.type === "control") {
      setControls(m.running, m.speed);
    } else if (m.type === "no_live") {
      $("status").textContent = "No live village. Choose a saved run.";
    }
  };
  ws.onclose = () => { if (S.mode === "live") $("status").textContent = "Disconnected"; };
}

function statusText(meta) {
  const model = meta && meta.speech_model ? meta.speech_model.model : "no speech model";
  return `${meta ? meta.run_id : ""} · ${model}`;
}

function send(cmd) { if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify(cmd)); }

// ---------------------------------------------------------------------------
// Replay mode

async function startReplay(runId) {
  if (S.ws) { S.mode = null; S.ws.close(); S.ws = null; }
  stopReplay();
  S.mode = "replay";
  $("status").textContent = "Loading…";
  const data = await (await fetch(`/api/runs/${encodeURIComponent(runId)}`)).json();
  S.frames = data.frames;
  S.events = data.events;
  $("status").textContent = statusText(data.meta);
  const scrub = $("scrub");
  scrub.max = Math.max(0, S.frames.length - 1);
  $("scrub-wrap").hidden = false;
  seek(0);
  selectFromUrl();
  setControls(true, S.speed);
  scheduleReplay();
}

function resetState() {
  S.decisions = {}; S.convs = {}; S.utterances = []; S.frame = null; S.prev = {};
  S.detailKey = "";
  $("feed").replaceChildren();
}

function seek(index) {
  if (!S.frames.length) return;
  index = Math.max(0, Math.min(S.frames.length - 1, index));
  const target = S.frames[index].t;
  const backwards = !S.frame || target < S.frame.t;
  if (backwards) { resetState(); S.eventCursor = 0; }
  const jump = Math.abs(index - S.replayIndex) > 1;
  while (S.eventCursor < S.events.length && S.events[S.eventCursor].t <= target) {
    applyEvent(S.events[S.eventCursor], { feed: true });
    S.eventCursor++;
  }
  S.replayIndex = index;
  $("scrub").value = index;
  setFrame(S.frames[index], !jump && !backwards);
}

function scheduleReplay() {
  stopReplay();
  if (S.mode !== "replay" || !S.running) return;
  S.replayTimer = setInterval(() => {
    if (S.replayIndex >= S.frames.length - 1) { setControls(false, S.speed); stopReplay(); return; }
    seek(S.replayIndex + 1);
  }, 1000 / S.speed);
}

function stopReplay() {
  if (S.replayTimer) clearInterval(S.replayTimer);
  S.replayTimer = null;
}

$("scrub").addEventListener("input", (e) => seek(Number(e.target.value)));

// ---------------------------------------------------------------------------
// Controls

function setControls(running, speed) {
  S.running = running;
  S.speed = speed;
  $("play").textContent = running ? "Pause" : "Play";
  $("speed").value = speed;
  $("speed-value").textContent = speed;
}

$("play").addEventListener("click", () => {
  if (S.mode === "live") send({ cmd: S.running ? "pause" : "resume" });
  else { setControls(!S.running, S.speed); scheduleReplay(); }
});

$("speed").addEventListener("change", (e) => {
  const v = Number(e.target.value);
  if (S.mode === "live") send({ cmd: "speed", value: v });
  else { setControls(S.running, v); scheduleReplay(); }
});
$("speed").addEventListener("input", (e) => { $("speed-value").textContent = e.target.value; });

$("source").addEventListener("change", (e) => {
  const v = e.target.value;
  const url = new URL(location.href);
  if (v === "__live__") { url.searchParams.delete("run"); startLive(); }
  else { url.searchParams.set("run", v); startReplay(v); }
  history.replaceState(null, "", url);
});

async function init() {
  S.world = await (await fetch("/api/world")).json();
  const live = await (await fetch("/api/live")).json();
  const runs = await (await fetch("/api/runs")).json();
  const source = $("source");
  if (live.live) source.append(el("option", { value: "__live__" }, "Live village"));
  for (const r of runs) {
    if (live.live && r.run_id === live.run_id) continue;
    source.append(el("option", { value: r.run_id }, `Replay ${r.run_id}`));
  }
  resize();
  window.addEventListener("resize", resize);
  requestAnimationFrame(draw);

  const wanted = new URL(location.href).searchParams.get("run");
  if (wanted && runs.some((r) => r.run_id === wanted)) { source.value = wanted; startReplay(wanted); }
  else if (live.live) { source.value = "__live__"; startLive(); }
  else if (runs.length) { source.value = runs[0].run_id; startReplay(runs[0].run_id); }
  else $("status").textContent = "No live village and no saved runs.";
}

init();
