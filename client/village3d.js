// Hearthwick in 3D. Watches a run through /ws/follow, which reads the run's own
// log files, so the village keeps living whether or not this page is open.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { routeBetween, waterOf } from "/static/route.js";

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// Look

const ROLE_COLORS = {
  farmer: 0x6f9a3c, crafter: 0x9a6a3a, merchant: 0xc9a227, guard: 0x4b6f95,
  healer: 0xe8e2d4, storyteller: 0x7a55a8,
};
const STAGE_COLORS = { infant: 0xf2c38b, child: 0xe9a324, apprentice: 0x4f9a55, adult: 0x3b73b9, elder: 0x8458b8 };
const VISITOR_COLOR = 0xb5452b;   // a traveler's red cloak, so a stranger stands out
// A figure is 1.62 tall at scale 1. Villagers are drawn to the buildings'
// scale, a grown one about 0.52 tall, just under a cottage's door (0.55), so
// what they make is drawn to scale beside them (Scott, 2026-09-30).
const STAGE_SCALE = { infant: 0.13, child: 0.2, apprentice: 0.27, adult: 0.32, elder: 0.31 };
const SKIN = [0xf1c9a5, 0xe0ac7e, 0xc68a5b, 0x9c6a43, 0x6e4a2f];
const HAIR = [0x2b1e16, 0x5a3a22, 0x8c6a3f, 0xc9b27a, 0x9a9a9a];
// School is the work action at the schoolyard, for pupils and teachers alike,
// so it gets its own mark rather than looking like a day at the mill.
const GLYPH = { rest: "z", work: "⚒", school: "📖", talk: "…", warn: "!", play: "✦",
                follow: "»", avoid: "✕", clear: "🪓", fell: "🪓", build: "🔨",
                gather: "⛏", smelt: "🔥", fetch: "🛒", sell: "¤", fight_blight: "✂" };
const BUBBLE_SECONDS = 6;
const MAX_BUBBLES = 5;

const mat = (color, extra = {}) =>
  new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0, flatShading: true, ...extra });

function hash(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619);
  return h >>> 0;
}
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// State

const S = {
  world: null, W: 40, H: 30, places: [], wet: new Set(),
  roster: {}, people: {}, decisions: {}, frameRow: {},
  talk: {},          // villager id -> its conversation lines, oldest first
  liveVillage: false, chat: null, chatNote: "",   // talking to villagers (hearthwick serve)
  liveRunId: null, watching: null,   // the server's own village, and the run on screen
  selected: null, ws: null, run: "latest", start: "live", rate: 6,
  live: false, clock: null, hour: 12, weather: "clear",
  materials: {},     // how materials look
  building: null, buildingReport: null, buildingShown: "",   // the house going up
  waiting: [],       // couples waiting for a house, from the events, for runs whose frames lack it
  purses: {},        // villager id -> [coins, what its goods would fetch], from the frames each hour
  lastArrival: 0, interval: 400, bubbles: [],
};

// ---------------------------------------------------------------------------
// Renderer, camera, light

const container = $("scene");
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x9fd0ff, 60, 140);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 400);
camera.position.set(4, 19, 23);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.maxPolarAngle = 1.35;
controls.minDistance = 6;
controls.maxDistance = 110;

const hemi = new THREE.HemisphereLight(0xdfefff, 0x5a6b3a, 0.9);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff1d6, 1.6);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.bias = -0.0005;
scene.add(sun, sun.target);

const worldGroup = new THREE.Group();
const peopleGroup = new THREE.Group();
scene.add(worldGroup, peopleGroup);

const windowMat = mat(0x3a3a3a, { emissive: 0xffc46b, emissiveIntensity: 0 });
const millBlades = [];
let groundMat = null;
let groundBase = new THREE.Color(0x7fa65a);

function resize() {
  const w = container.clientWidth, h = container.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / Math.max(1, h);
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);

const toWorld = (x, y) => new THREE.Vector3(x + 0.5 - S.W / 2, 0, y + 0.5 - S.H / 2);

// ---------------------------------------------------------------------------
// The village

function clearGroup(group) {
  for (const child of [...group.children]) {
    group.remove(child);
    child.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
  }
}

function box(w, h, d, color, x, y, z, shadow = true) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), typeof color === "number" ? mat(color) : color);
  m.position.set(x, y, z);
  m.castShadow = shadow;
  m.receiveShadow = true;
  return m;
}

function house(cx, cz, size, wall, roof, storeys = 1) {
  const g = new THREE.Group();
  const h = 1.1 * storeys;
  g.add(box(size, h, size * 0.8, wall, 0, h / 2, 0));
  const r = new THREE.Mesh(new THREE.ConeGeometry(size * 0.78, 0.9, 4), mat(roof));
  r.position.y = h + 0.45;
  r.rotation.y = Math.PI / 4;
  r.scale.z = 0.8;
  r.castShadow = true;
  g.add(r);
  g.add(box(0.28, 0.55, 0.04, 0x4a3524, 0, 0.28, size * 0.4 + 0.02, false));
  for (let s = 0; s < storeys; s++) {
    for (const side of [-1, 1]) {
      const win = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.22, 0.04), windowMat);
      win.position.set(side * size * 0.28, 0.65 + s * 1.1, size * 0.4 + 0.02);
      g.add(win);
    }
  }
  g.position.set(cx, 0, cz);
  return g;
}

function tree(x, z, r, scale = 1) {
  const g = new THREE.Group();
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 0.5, 5), mat(0x6b4a2e));
  trunk.position.y = 0.25;
  const crown = new THREE.Mesh(new THREE.ConeGeometry(0.45 + r() * 0.2, 1.3 + r() * 0.5, 6),
                               mat(r() < 0.5 ? 0x3f6f3a : 0x4f7f3f));
  crown.position.y = 1.1;
  trunk.castShadow = crown.castShadow = true;
  g.add(trunk, crown);
  g.position.set(x, 0, z);
  g.scale.setScalar(scale);
  g.rotation.y = r() * Math.PI;
  return g;
}

function flat(rect, color, y = 0.01) {
  const [x, yy, w, h] = rect;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat(color));
  m.rotation.x = -Math.PI / 2;
  const c = toWorld(x + w / 2 - 0.5, yy + h / 2 - 0.5);
  m.position.set(c.x, y, c.z);
  m.receiveShadow = true;
  return m;
}

function placeCentre(rect) {
  const [x, y, w, h] = rect;
  return toWorld(x + w / 2 - 0.5, y + h / 2 - 0.5);
}

const BUILD = {
  home(p, r) {
    const [, , w, h] = p.rect;
    const c = placeCentre(p.rect);
    const walls = [0xe8dcc2, 0xd9c7a3, 0xefe6d3, 0xcdb99a][hash(p.id) % 4];
    const roofs = [0x9c4a32, 0x7a5a3a, 0x8a3f2c, 0x6d6a5e][hash(p.id + "r") % 4];
    return [flat(p.rect, 0xbda27a), house(c.x, c.z, Math.min(w, h) * 0.75, walls, roofs)];
  },
  inn(p) {
    const [, , w, h] = p.rect;
    const c = placeCentre(p.rect);
    const g = house(c.x, c.z, Math.min(w, h) * 0.8, 0xe3c39a, 0x6b3d28, 2);
    const sign = box(0.6, 0.35, 0.05, 0x8a5a2b, 0.9, 1.4, Math.min(w, h) * 0.34, false);
    g.add(sign);
    return [flat(p.rect, 0xc9a882), g];
  },
  well(p) {
    const c = placeCentre(p.rect);
    const g = new THREE.Group();
    const ring = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.6, 0.5, 10, 1, true), mat(0x8f8b83, { side: THREE.DoubleSide }));
    ring.position.y = 0.25;
    ring.castShadow = true;
    const water = new THREE.Mesh(new THREE.CircleGeometry(0.5, 10), mat(0x3d74a8));
    water.rotation.x = -Math.PI / 2;
    water.position.y = 0.3;
    g.add(ring, water, box(0.08, 1.2, 0.08, 0x6b4a2e, -0.5, 0.6, 0), box(0.08, 1.2, 0.08, 0x6b4a2e, 0.5, 0.6, 0));
    const roof = new THREE.Mesh(new THREE.ConeGeometry(0.8, 0.45, 4), mat(0x7a4b2e));
    roof.position.y = 1.4;
    roof.rotation.y = Math.PI / 4;
    roof.castShadow = true;
    g.add(roof);
    g.position.set(c.x, 0, c.z);
    return [flat(p.rect, 0xb9b3a2), g];
  },
  market(p, r) {
    const [x, y, w, h] = p.rect;
    const out = [flat(p.rect, 0xd6c49a)];
    const cloths = [0xc0392b, 0x2a78d6, 0xe0b62f, 0x1baf7a];
    for (let i = 0; i < 4; i++) {
      const c = toWorld(x + 0.8 + (i % 2) * (w - 2.6), y + 0.8 + Math.floor(i / 2) * (h - 2.6));
      const g = new THREE.Group();
      g.add(box(1.2, 0.5, 0.6, 0x8a5a2b, 0, 0.25, 0));
      for (const [px, pz] of [[-0.55, -0.3], [0.55, -0.3], [-0.55, 0.3], [0.55, 0.3]])
        g.add(box(0.06, 1.2, 0.06, 0x6b4a2e, px, 0.6, pz));
      g.add(box(1.4, 0.06, 0.8, cloths[i], 0, 1.22, 0));
      g.position.set(c.x + 0.4, 0, c.z + 0.4);
      out.push(g);
    }
    return out;
  },
  shrine(p) {
    const c = placeCentre(p.rect);
    const g = new THREE.Group();
    g.add(box(2.2, 0.2, 2.2, 0xcfc8d8, 0, 0.1, 0), box(1.7, 0.2, 1.7, 0xd9d2e2, 0, 0.3, 0));
    for (const [px, pz] of [[-0.65, -0.65], [0.65, -0.65], [-0.65, 0.65], [0.65, 0.65]])
      g.add(box(0.15, 1.2, 0.15, 0xefe9f5, px, 1, pz));
    const roof = new THREE.Mesh(new THREE.ConeGeometry(1.3, 0.7, 4), mat(0x8e7bb5));
    roof.position.y = 1.95;
    roof.rotation.y = Math.PI / 4;
    roof.castShadow = true;
    g.add(roof);
    g.position.set(c.x, 0, c.z);
    return [flat(p.rect, 0xd5cfe0), g];
  },
  schoolyard(p) {
    const [x, y, w, h] = p.rect;
    const c = toWorld(x + 0.9, y + 0.9);
    const out = [flat(p.rect, 0xd9c98e), house(c.x + 0.3, c.z + 0.3, 1.5, 0xf0e2b6, 0x4f7a8a)];
    for (let i = 0; i < w; i++) {
      const a = toWorld(x + i, y + h - 1);
      out.push(box(0.08, 0.5, 0.08, 0x8a6a42, a.x, 0.25, a.z + 0.45));
    }
    return out;
  },
  // A house going up: bare ground, corner posts, and a stack of timber.
  site(p) {
    const [x, y, w, h] = p.rect;
    const g = new THREE.Group();
    for (const [i, j] of [[0, 0], [w - 1, 0], [0, h - 1], [w - 1, h - 1]]) {
      const c = toWorld(x + i, y + j);
      g.add(box(0.12, 1.1, 0.12, 0x7a5a3a, c.x, 0.55, c.z));
    }
    const c = placeCentre(p.rect);
    for (let k = 0; k < 3; k++) g.add(box(0.9, 0.12, 0.14, 0x9a7650, c.x, 0.06 + k * 0.12, c.z + 0.18 * (k - 1)));
    return [flat(p.rect, 0xa8906a), g];
  },
  mill(p) {
    const c = placeCentre(p.rect);
    const g = new THREE.Group();
    const tower = new THREE.Mesh(new THREE.CylinderGeometry(0.7, 1, 3, 8), mat(0xd8cbb0));
    tower.position.y = 1.5;
    tower.castShadow = true;
    const cap = new THREE.Mesh(new THREE.ConeGeometry(0.85, 0.9, 8), mat(0x6d4a30));
    cap.position.y = 3.45;
    cap.castShadow = true;
    const hub = new THREE.Group();
    hub.position.set(0, 2.7, 0.8);
    for (let i = 0; i < 4; i++) {
      const blade = box(0.25, 2.2, 0.05, 0xefe6d0, 0, 1.1, 0);
      const arm = new THREE.Group();
      arm.add(blade);
      arm.rotation.z = (i * Math.PI) / 2;
      hub.add(arm);
    }
    millBlades.push(hub);
    g.add(tower, cap, hub);
    g.position.set(c.x, 0, c.z);
    return [flat(p.rect, 0xc2b08f), g];
  },
  fields(p) {
    const [x, y, w, h] = p.rect;
    const out = [flat(p.rect, 0x8a6a42)];
    for (let row = 0; row < h; row++) {
      const a = toWorld(x + w / 2 - 0.5, y + row);
      const crop = box(w - 0.4, 0.25, 0.35, 0x9bbf4a, a.x, 0.14, a.z, false);
      crop.castShadow = false;
      out.push(crop);
    }
    return out;
  },
  watchpost(p) {
    const c = placeCentre(p.rect);
    const g = new THREE.Group();
    for (const [px, pz] of [[-0.5, -0.5], [0.5, -0.5], [-0.5, 0.5], [0.5, 0.5]])
      g.add(box(0.12, 3, 0.12, 0x6b4a2e, px, 1.5, pz));
    g.add(box(1.4, 0.12, 1.4, 0x8a6a42, 0, 3, 0));
    const roof = new THREE.Mesh(new THREE.ConeGeometry(1.1, 0.7, 4), mat(0x5a3f2a));
    roof.position.y = 3.9;
    roof.rotation.y = Math.PI / 4;
    roof.castShadow = true;
    g.add(roof);
    g.position.set(c.x, 0, c.z);
    return [flat(p.rect, 0xb7a58a), g];
  },
  road(p) { return [flat(p.rect, 0xc9b58c, 0.012)]; },
  forest(p, r) {
    const [x, y, w, h] = p.rect;
    const out = [flat(p.rect, 0x5f8a4a)];
    const count = Math.max(4, Math.round(w * h * 0.35));
    for (let i = 0; i < count; i++) {
      const a = toWorld(x + r() * (w - 1), y + r() * (h - 1));
      out.push(tree(a.x, a.z, r, 1 + r() * 0.6));
    }
    return out;
  },
};

// ---------------------------------------------------------------------------
// Structures drawn from designs (hearthwick/designs.py, data/structures).
// A design is parts, joints and movements. Each part sits in a frame (its
// position and rotation) holding a pivot, which is what a joint moves, and the
// part's children hang from the pivot, so they move with it. A movement waits
// on the time of day or the weather. One that waits on a place's own trigger
// (whether anyone works there) stays still, since this edition's frames do not
// carry them (README).

const movers = [];
const materialCache = new Map();

function shade(name, key) {
  const m = S.materials[name] || {};
  const colours = m.colours || [m.colour ?? 0xcccccc];
  return colours[hash(`${key}:${name}`) % colours.length];
}

function partMaterial(name, key, open) {
  if (name === "glass") return windowMat;       // lit at night with every window
  const colour = shade(name, key);
  const id = `${colour}|${open ? 1 : 0}`;
  if (!materialCache.has(id)) {
    const extra = {};
    const m = S.materials[name] || {};
    if (m.roughness !== undefined) extra.roughness = m.roughness;
    if (open) extra.side = THREE.DoubleSide;
    materialCache.set(id, mat(colour, extra));
  }
  return materialCache.get(id);
}

function shapeGeometry(part) {
  const s = part.size;
  const sides = part.sides || 12;
  switch (part.shape) {
    case "box": return new THREE.BoxGeometry(s[0], s[1], s[2]);
    case "cylinder":
      return s.length === 3 ? new THREE.CylinderGeometry(s[0], s[1], s[2], sides, 1, !!part.open)
                            : new THREE.CylinderGeometry(s[0], s[0], s[1], sides, 1, !!part.open);
    case "cone": return new THREE.ConeGeometry(s[0], s[1], sides);
    case "sphere": return new THREE.SphereGeometry(s[0], 12, 8);
    case "wheel": {
      const g = new THREE.CylinderGeometry(s[0], s[0], s[1], part.sides || 16);
      g.rotateZ(Math.PI / 2);           // on its side, the axle along x
      return g;
    }
  }
  return new THREE.BoxGeometry(0.2, 0.2, 0.2);
}

function buildDesign(p, design) {
  const out = [];
  if (design.ground) out.push(flat(p.rect, shade(design.ground, p.id)));
  const [, , w, h] = p.rect;
  const [fw, fh] = design.footprint || [w, h];
  const root = new THREE.Group();
  const c = placeCentre(p.rect);
  root.position.set(c.x, 0, c.z);
  // The founders' designs are fitted to the places they draw.
  root.scale.setScalar(Math.min(w, h) / Math.min(fw, fh));
  const joints = Object.fromEntries((design.joints || []).map((j) => [j.part, j]));
  const children = {};
  for (const part of design.parts) (children[part.parent || ""] ||= []).push(part);
  const pivots = {};                    // part id -> a pivot for every copy of it

  const add = (part, into, parentAxis) => {
    const repeat = typeof part.repeat === "object" ? part.repeat : { count: part.repeat || 1 };
    const axis = repeat.axis || parentAxis || "y";
    for (let i = 0; i < repeat.count; i++) {
      const around = new THREE.Group();        // a repeat's copies, spaced round the axis
      around.rotation[axis] = (i * 2 * Math.PI) / repeat.count;
      const frame = new THREE.Group();
      frame.position.fromArray(part.at || [0, 0, 0]);
      const [rx, ry, rz] = (part.rotation || [0, 0, 0]).map((d) => (d * Math.PI) / 180);
      frame.rotation.set(rx, ry, rz);
      // A joint's pivot is where the part turns: the pivot group sits there,
      // and the part and its children are set back by as much, so a door
      // turns on its edge rather than its middle.
      const joint0 = joints[part.id];
      const at = joint0 && joint0.pivot ? joint0.pivot : [0, 0, 0];
      const pivot = new THREE.Group();
      pivot.position.fromArray(at);
      const body = new THREE.Group();
      body.position.set(-at[0], -at[1], -at[2]);
      const mesh = new THREE.Mesh(shapeGeometry(part), partMaterial(part.material, p.id, part.open));
      if (part.scale) mesh.scale.fromArray(part.scale);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      body.add(mesh);
      pivot.add(body);
      frame.add(pivot);
      around.add(frame);
      into.add(around);
      (pivots[part.id] ||= []).push(pivot);
      for (const child of children[part.id] || []) add(child, body, joint0 && joint0.axis);
    }
  };
  for (const part of children[""] || []) add(part, root, null);

  for (const movement of design.movements || []) {
    const joint = joints[movement.joint];
    if (!joint) continue;
    for (const pivot of pivots[movement.joint] || [])
      movers.push({ place: p.id, pivot, joint, movement, value: 0, speed: 0, phase: 0, level: 0 });
  }
  out.push(root);
  return out;
}

function triggered(when) {
  switch (when || "always") {
    case "always": return true;
    case "night": return !!S.clock && S.clock.part === "night";
    case "day": return !S.clock || S.clock.part !== "night";
    case "rain": return S.weather === "rain" || S.weather === "storm";
    case "storm": return S.weather === "storm";
    default: return false;     // a place's own trigger, which the frames do not carry
  }
}

// Every movement eases in and out rather than snapping, so a mill's sails
// wind up when the miller starts and run down when they stop.
function moveStructures(dt) {
  const ease = Math.min(1, dt * 1.5);
  for (const m of movers) {
    const on = triggered(m.movement.when);
    const mv = m.movement;
    const hinge = m.joint.kind === "hinge";
    const unit = hinge ? Math.PI / 180 : 1;
    if (mv.spin !== undefined) {
      m.speed += ((on ? (mv.spin * 2 * Math.PI) / 60 : 0) - m.speed) * ease;
      m.value += m.speed * dt;
    } else if (mv.swing || mv.slide) {
      const [a, b] = (mv.swing || mv.slide).map((v) => v * unit);
      m.level += ((on ? 1 : 0) - m.level) * ease;
      m.phase += dt / (mv.period || 2);
      m.value = a + m.level * (b - a) * (1 - Math.cos(2 * Math.PI * m.phase)) / 2;
    } else if (mv.open !== undefined) {
      const target = on ? mv.open * unit : 0;
      const step = (Math.abs(mv.open * unit) / (mv.seconds || 1)) * dt;
      m.value += Math.max(-step, Math.min(step, target - m.value));
    }
    if (hinge) m.pivot.rotation[m.joint.axis] = m.value;
    else if (m.joint.kind === "slider") {
      const base = m.joint.pivot || [0, 0, 0];
      m.pivot.position[m.joint.axis] = base["xyz".indexOf(m.joint.axis)] + m.value;
    }
  }
}

function buildWorld(world) {
  clearGroup(worldGroup);
  millBlades.length = 0;
  movers.length = 0;
  S.world = world;
  S.W = world.width;
  S.H = world.height;
  S.places = world.places;
  S.materials = world.materials || {};
  S.wet = waterOf(world);
  const r = rng(hash("hearthwick"));

  groundMat = mat(0x7fa65a);
  groundBase = new THREE.Color(0x7fa65a);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(S.W + 30, S.H + 30), groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  worldGroup.add(ground);

  // The stream, with a bridge or a ford wherever its rectangles leave a gap.
  const stream = world.blocked.filter((b) => b.kind === "stream").map((b) => b.rect)
    .sort((a, b) => a[1] - b[1]);
  for (const rect of stream) {
    const water = flat(rect, 0x3f7fb6, 0.02);
    water.material = mat(0x3f7fb6, { roughness: 0.3, transparent: true, opacity: 0.9 });
    worldGroup.add(water);
  }
  for (let i = 0; i + 1 < stream.length; i++) {
    const [x, y, w, h] = stream[i];
    const gapStart = y + h, gapEnd = stream[i + 1][1];
    if (gapEnd <= gapStart) continue;
    const c = toWorld(x + w / 2 - 0.5, (gapStart + gapEnd) / 2 - 0.5);
    for (let k = 0; k < 5; k++)
      worldGroup.add(box(w + 0.6, 0.12, (gapEnd - gapStart) / 5 - 0.04, 0x8a6a42,
                         c.x, 0.08, c.z - (gapEnd - gapStart) / 2 + (k + 0.5) * (gapEnd - gapStart) / 5));
  }

  // A place is drawn from its kind's design, and otherwise by the code below
  // (BUILD), which is what every place had before designs. A plot being built
  // on is drawn as a plot until the house is finished.
  const designs = world.designs || {}, kinds = world.design_kinds || {};
  for (const p of world.places) {
    const design = p.kind === "site" ? null : designs[kinds[p.kind]];
    const make = BUILD[p.kind];
    const parts = design ? buildDesign(p, design) : make ? make(p, r) : [flat(p.rect, 0xcccccc)];
    for (const part of parts) worldGroup.add(part);
  }

  // Trees around the edge of the village, clear of places and water.
  const taken = (x, y) => world.places.some((p) => x >= p.rect[0] - 1 && x < p.rect[0] + p.rect[2] + 1
                                               && y >= p.rect[1] - 1 && y < p.rect[1] + p.rect[3] + 1)
    || stream.some((s) => x >= s[0] - 1 && x < s[0] + s[2] + 1);
  for (let i = 0; i < 120; i++) {
    const x = Math.floor(r() * (S.W + 12)) - 6, y = Math.floor(r() * (S.H + 12)) - 6;
    const inside = x >= 0 && x < S.W && y >= 0 && y < S.H;
    if ((inside && (r() > 0.25 || taken(x, y))) || (!inside && r() > 0.7)) continue;
    const a = toWorld(x, y);
    worldGroup.add(tree(a.x, a.z, r, 0.8 + r() * 0.5));
  }

  const span = Math.max(S.W, S.H) * 0.75;
  Object.assign(sun.shadow.camera, { left: -span, right: span, top: span, bottom: -span, near: 1, far: 120 });
  sun.shadow.camera.updateProjectionMatrix();
  controls.target.set(0, 0, 0);
}

function placeAt(x, y) {
  return S.places.find((p) => x >= p.rect[0] && x < p.rect[0] + p.rect[2]
                            && y >= p.rect[1] && y < p.rect[1] + p.rect[3]);
}

// ---------------------------------------------------------------------------
// Sprites: names, what someone is doing, what they say

const textureCache = new Map();
// Sprites keep the same size on screen at any zoom (sizeAttenuation off), so a
// name or a line of speech stays readable from across the village. ``screen``
// is the height of one line as a share of the view.
function textSprite(text, { size = 40, color = "#1f1f1f", bg = "rgba(255,253,248,0.92)", maxWidth = 460,
                            screen = 0.03 } = {}) {
  const key = `${text}|${size}|${color}|${bg}|${maxWidth}`;
  let entry = textureCache.get(key);
  if (!entry) {
    const c = document.createElement("canvas");
    const g = c.getContext("2d");
    g.font = `${size}px system-ui, sans-serif`;
    const words = String(text).split(/\s+/), lines = [];
    let line = "";
    for (const w of words) {
      const test = line ? `${line} ${w}` : w;
      if (g.measureText(test).width > maxWidth && line) { lines.push(line); line = w; } else line = test;
    }
    if (line) lines.push(line);
    const width = Math.min(maxWidth, Math.max(...lines.map((l) => g.measureText(l).width))) + size * 0.8;
    const height = lines.length * size * 1.2 + size * 0.5;
    c.width = Math.ceil(width);
    c.height = Math.ceil(height);
    const g2 = c.getContext("2d");
    g2.font = `${size}px system-ui, sans-serif`;
    if (bg) {
      g2.fillStyle = bg;
      const rr = size * 0.4;
      g2.beginPath();
      g2.roundRect(0, 0, c.width, c.height, rr);
      g2.fill();
    }
    g2.fillStyle = color;
    g2.textBaseline = "top";
    lines.forEach((l, i) => g2.fillText(l, size * 0.4, size * 0.25 + i * size * 1.2));
    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    entry = { tex, aspect: c.width / c.height, lines: lines.length };
    if (textureCache.size > 400) textureCache.clear();
    textureCache.set(key, entry);
  }
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: entry.tex, depthWrite: false, depthTest: false, transparent: true, sizeAttenuation: false }));
  const h = screen * (entry.lines + 0.4);
  sprite.scale.set(h * entry.aspect, h, 1);
  sprite.center.set(0.5, 0);           // sit above the point, not across it
  sprite.renderOrder = 10;
  return sprite;
}

// ---------------------------------------------------------------------------
// Villagers

function makePerson(id, profile) {
  const r = rng(hash(id));
  const g = new THREE.Group();
  const body = new THREE.Group();
  const clothes = profile?.visitor ? VISITOR_COLOR
    : ROLE_COLORS[profile?.role] ?? STAGE_COLORS[profile?.stage] ?? 0x888888;
  const skin = SKIN[hash(id) % SKIN.length];
  const hair = HAIR[hash(id + "h") % HAIR.length];

  const legs = [-0.1, 0.1].map((dx) => {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.5, 0.14), mat(0x4a3f35));
    leg.geometry.translate(0, -0.25, 0);
    leg.position.set(dx, 0.5, 0);
    leg.castShadow = true;
    body.add(leg);
    return leg;
  });
  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.26, 0.62, 8), mat(clothes));
  torso.position.y = 0.8;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.17, 10, 8), mat(skin));
  head.position.y = 1.26;
  const cap = new THREE.Mesh(new THREE.SphereGeometry(0.18, 10, 6, 0, Math.PI * 2, 0, Math.PI / 2), mat(hair));
  cap.position.y = 1.28;
  const arms = [-0.28, 0.28].map((dx) => {
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.48, 0.12), mat(clothes));
    arm.geometry.translate(0, -0.22, 0);
    arm.position.set(dx, 1.05, 0);
    arm.castShadow = true;
    body.add(arm);
    return arm;
  });
  for (const m of [torso, head, cap]) { m.castShadow = true; body.add(m); }
  body.traverse((o) => { if (o.isMesh) o.userData.person = id; });
  g.add(body);

  const ring = new THREE.Mesh(new THREE.RingGeometry(0.35, 0.45, 24),
                              new THREE.MeshBasicMaterial({ color: 0x2a78d6, transparent: true, opacity: 0.9 }));
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.03;
  ring.visible = false;
  g.add(ring);

  const name = textSprite(profile?.name ?? id, { size: 34, screen: 0.022 });
  name.position.y = 1.55;
  name.userData.person = id;          // small as a villager is, its name can be clicked
  g.add(name);

  peopleGroup.add(g);
  return {
    id, group: g, body, legs, arms, ring, name, glyph: null, glyphText: "",
    from: new THREE.Vector3(), to: new THREE.Vector3(), at: 0, phase: r() * 10,
    stage: profile?.stage, activity: "idle", scale: STAGE_SCALE.adult,
  };
}

function setGlyph(p, activity) {
  const text = GLYPH[activity] || "";
  if (text === p.glyphText) return;
  if (p.glyph) { p.group.remove(p.glyph); p.glyph.material.dispose(); }
  p.glyph = null;
  p.glyphText = text;
  if (text) {
    p.glyph = textSprite(text, { size: 44, color: "#2b2a27", bg: "rgba(255,255,255,0.85)", screen: 0.022 });
    p.glyph.position.y = p.name.position.y;
    p.glyph.center.set(-0.2, 1.1);     // beside the name, not on top of it
    p.group.add(p.glyph);
  }
}

function applyFrame(frame, animate = true) {
  if (!frame || !S.world) return;
  const now = performance.now();
  if (S.lastArrival) {
    const gap = now - S.lastArrival;
    S.interval = Math.min(2500, Math.max(60, 0.7 * S.interval + 0.3 * gap));
  }
  S.lastArrival = now;
  S.clock = frame.clock;
  S.building = frame.b || null;
  if (frame.m) S.purses = frame.m;
  $("clock").textContent = fmtClock(frame.clock);

  const seen = new Set();
  for (const row of frame.c) {
    const [id, x, y, activity, stage] = row;
    seen.add(id);
    S.frameRow[id] = row;
    let p = S.people[id];
    if (!p) {
      p = S.people[id] = makePerson(id, S.roster[id] || { name: id, stage });
      p.group.position.copy(toWorld(x, y));
      p.from.copy(p.group.position);
    }
    // Walk the way the simulation could have: straight when that stays dry,
    // over the bridge or ford when a straight line would cross the stream.
    const tiles = animate && p.tile ? routeBetween(S.wet, S.W, S.H, p.tile, [x, y]) : [[x, y]];
    p.route = [(animate ? p.group.position : toWorld(x, y)).clone(), ...tiles.map(([tx, ty]) => toWorld(tx, ty))];
    p.lengths = [0];
    for (let i = 1; i < p.route.length; i++)
      p.lengths.push(p.lengths[i - 1] + p.route[i].distanceTo(p.route[i - 1]));
    p.tile = [x, y];
    p.from.copy(p.route[0]);
    p.to.copy(p.route[p.route.length - 1]);
    p.at = now;
    p.activity = activity;
    p.stage = stage;
    // Scale the figure, not its group, so a child's name and speech stay the
    // same size on screen as everyone else's.
    p.scale = STAGE_SCALE[stage] ?? STAGE_SCALE.adult;
    p.body.scale.setScalar(p.scale);
    p.ring.scale.setScalar(p.scale);
    p.name.position.y = 1.62 * p.scale + 0.05;
    if (p.glyph) p.glyph.position.y = p.name.position.y;
    const place = placeAt(x, y);
    // Asleep indoors: nobody sees them until morning.
    p.group.visible = !(activity === "rest" && place && place.kind === "home");
    setGlyph(p, activity === "work" && place && place.kind === "schoolyard" ? "school" : activity);
  }
  for (const [id, p] of Object.entries(S.people)) if (!seen.has(id)) p.group.visible = false;
  renderBuilding();
  if (S.selected) renderDetail();
}

// ---------------------------------------------------------------------------
// Sky, weather

const SKY = { night: new THREE.Color(0x0b1024), dawn: new THREE.Color(0xf2a65a), day: new THREE.Color(0x9fd0ff) };
const skyNow = new THREE.Color();

function updateSky() {
  const hour = S.clock ? S.clock.hour : 12;
  const e = Math.sin(((hour - 6) / 12) * Math.PI);         // sun elevation, below 0 at night
  const day = Math.max(0, Math.min(1, e * 2.2 + 0.1));
  const twilight = Math.max(0, 1 - Math.abs(e) * 4) * (e > -0.25 ? 1 : 0);
  skyNow.copy(SKY.night).lerp(SKY.day, day).lerp(SKY.dawn, twilight * 0.45);
  if (S.weather === "storm") skyNow.lerp(new THREE.Color(0x3a4048), 0.6);
  else if (S.weather === "rain") skyNow.lerp(new THREE.Color(0x7d8791), 0.45);
  scene.background = skyNow;
  scene.fog.color.copy(skyNow);

  const angle = ((hour - 6) / 12) * Math.PI;
  sun.position.set(Math.cos(angle) * 40, Math.max(3, Math.sin(angle) * 45), 18);
  const gloom = S.weather === "storm" ? 0.45 : S.weather === "rain" ? 0.7 : 1;
  sun.intensity = (0.15 + 1.6 * day) * gloom;
  sun.color.set(day > 0.3 ? 0xfff1d6 : 0x9fb3ff);
  hemi.intensity = (0.25 + 0.75 * day) * (0.6 + 0.4 * gloom);
  windowMat.emissiveIntensity = (1 - day) * 1.4;

  if (groundMat) {
    const g = groundBase.clone();
    if (S.weather === "frost") g.lerp(new THREE.Color(0xe8eef2), 0.55);
    else if (S.weather === "drought") g.lerp(new THREE.Color(0xc7b36a), 0.5);
    groundMat.color.copy(g);
  }
}

const RAIN = 5000;
const rainGeo = new THREE.BufferGeometry();
const rainPos = new Float32Array(RAIN * 3);
for (let i = 0; i < RAIN; i++) {
  rainPos[i * 3] = (Math.random() - 0.5) * 70;
  rainPos[i * 3 + 1] = Math.random() * 25;
  rainPos[i * 3 + 2] = (Math.random() - 0.5) * 60;
}
rainGeo.setAttribute("position", new THREE.BufferAttribute(rainPos, 3));
const rain = new THREE.Points(rainGeo, new THREE.PointsMaterial({ color: 0xaac4dd, size: 0.12, transparent: true, opacity: 0.75 }));
rain.visible = false;
scene.add(rain);
let lightning = 0;

function updateWeather(dt) {
  const wet = S.weather === "rain" || S.weather === "storm";
  rain.visible = wet;
  if (wet) {
    rainGeo.setDrawRange(0, S.weather === "storm" ? RAIN : RAIN * 0.45);
    const speed = S.weather === "storm" ? 30 : 18;
    for (let i = 0; i < RAIN; i++) {
      let y = rainPos[i * 3 + 1] - speed * dt;
      if (y < 0) y += 25;
      rainPos[i * 3 + 1] = y;
    }
    rainGeo.attributes.position.needsUpdate = true;
  }
  if (S.weather === "storm" && Math.random() < dt * 0.15) lightning = 0.25;
  if (lightning > 0) {
    lightning -= dt;
    hemi.intensity += 2.5 * Math.max(0, lightning) * 4;
  }
}

// ---------------------------------------------------------------------------
// Speech

function say(speaker, text) {
  const p = S.people[speaker];
  if (!p || !text) return;
  const short = text.length > 140 ? text.slice(0, 137) + "…" : text;
  // One bubble a speaker, and only the newest few, so a crowd stays legible.
  for (const b of S.bubbles) if (b.person === p) b.until = 0;
  while (S.bubbles.filter((b) => b.until > 0).length >= MAX_BUBBLES) {
    const oldest = S.bubbles.find((b) => b.until > 0);
    oldest.until = 0;
  }
  const sprite = textSprite(short, { size: 30, maxWidth: 520, screen: 0.024 });
  sprite.position.y = 1.62 * (p.scale ?? STAGE_SCALE.adult) + 0.4;
  p.group.add(sprite);
  S.bubbles.push({ sprite, person: p, until: performance.now() + BUBBLE_SECONDS * 1000 });
}

// ---------------------------------------------------------------------------
// Events and the feed

const nameOf = (id) => (S.roster[id] ? S.roster[id].name : id === "stranger" ? "Stranger" : id);
function tickTime(t) {
  const minutes = 6 * 60 + t * 10;
  const day = Math.floor(minutes / 1440), m = minutes % 1440;
  return `d${day} ${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}
// The granary, as the villagers see it: how many days it will feed them, and
// what is standing in the fields.
function showFood() {
  const f = S.food;
  if (!f) { $("food").textContent = ""; return; }
  const days = f.need ? f.store / f.need : 0;
  const crop = f.capacity ? ` · crop ${Math.round(f.crop)}/${Math.round(f.capacity)}` : "";
  $("food").textContent = `Granary ${Math.round(f.store)} (${days.toFixed(1)} days)${crop}`;
  $("food").classList.toggle("short", f.store <= 0);
}

function fmtClock(clock) {
  if (!clock) return "…";
  const h = Math.floor(clock.hour), m = Math.round((clock.hour - h) * 60);
  return `Year ${clock.year} · Day ${clock.day} · ${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function feed(li) {
  const list = $("feed");
  list.prepend(li);
  while (list.children.length > 200) list.lastChild.remove();
}
function who(id) {
  const s = document.createElement("span");
  s.className = "who";
  s.textContent = nameOf(id);
  s.onclick = () => select(id);
  return s;
}
function line(t, ...parts) {
  const li = document.createElement("li");
  const when = document.createElement("span");
  when.className = "when";
  when.textContent = tickTime(t);
  li.append(when, ...parts);
  return li;
}

// ---------------------------------------------------------------------------
// Notices, and what is being built

const NOTICE_SECONDS = 14;
const MAX_NOTICES = 4;

// A notice over the scene for something the village has just done. Only for
// events as they arrive, not for the history a page loads with.
function notify(kind, ...parts) {
  const box = $("notices");
  const div = document.createElement("div");
  div.className = "notice";
  const tag = document.createElement("span");
  tag.className = "kind";
  tag.textContent = kind;
  div.append(tag, ...parts);
  box.prepend(div);
  while (box.children.length > MAX_NOTICES) box.lastChild.remove();
  setTimeout(() => div.classList.add("fade"), (NOTICE_SECONDS - 1) * 1000);
  setTimeout(() => div.remove(), NOTICE_SECONDS * 1000);
}

function names(ids) {
  const out = [];
  ids.forEach((id, i) => {
    if (i) out.push(i === ids.length - 1 ? " and " : ", ");
    out.push(who(id));
  });
  return out;
}

function bar(done, whole) {
  const b = document.createElement("div");
  b.className = "bar";
  const fill = document.createElement("span");
  fill.style.width = `${Math.round(100 * Math.max(0, Math.min(1, whole > 0 ? done / whole : 0)))}%`;
  b.append(fill);
  return b;
}

// The house going up, from the frames (b). A run from before frames carried it
// is pieced together from its events: the couples waiting, the plot on the
// map, and the timber and work the crafters report at dawn.
function renderBuilding() {
  const el = $("building");
  const site = ((S.world && S.world.places) || []).find((p) => p.kind === "site");
  const report = S.buildingReport;
  const b = S.building || ((S.waiting.length || site) ? {
    site: site ? site.id : null, waiting: S.waiting,
    timber: report ? report.timber : null, timber_needed: null,
    work: report ? report.progress : null, work_needed: null, atDawn: !!report } : null);
  const felling = Object.values(S.frameRow).filter((r) => r[3] === "fell").map((r) => r[0]);
  const building = Object.values(S.frameRow).filter((r) => r[3] === "build").map((r) => r[0]);
  const key = JSON.stringify([b, felling, building]);
  if (key === S.buildingShown) return;
  S.buildingShown = key;
  el.innerHTML = "";
  if (!b) {
    const p = document.createElement("p");
    p.className = "hint";
    p.textContent = "Nothing is being built.";
    el.append(p);
    return;
  }
  const head = document.createElement("div");
  const couples = b.waiting || [];
  head.append(b.site ? "A house is going up" : "A house is needed",
              ...(couples.length ? [" for ", ...names(couples[0]), "."] : ["."]),
              b.atDawn ? " (as reported at dawn)" : "");
  el.append(head);
  const goods = Object.entries(b.goods || {}).filter(([, [, need]]) => need > 0);
  if (goods.length && Object.keys(b.goods).some((g) => g !== "timber")) {
    for (const [good, [have, need]] of goods) {
      const d = document.createElement("div");
      d.textContent = `${good[0].toUpperCase()}${good.slice(1)}: ${have} of ${need} still needed`;
      el.append(d, bar(have, need));
    }
  } else if (b.timber != null) {
    const timber = document.createElement("div");
    timber.textContent = b.timber_needed != null
      ? `Timber: ${b.timber} of ${b.timber_needed} still needed`
      : `Timber in hand: ${b.timber}`;
    el.append(timber);
    if (b.timber_needed != null) el.append(bar(b.timber, b.timber_needed));
  }
  if (b.site && b.work != null) {
    const work = document.createElement("div");
    work.textContent = b.work_needed != null
      ? `Work: ${Math.round((100 * b.work) / b.work_needed)}% done` : `Work done: ${b.work}`;
    el.append(work);
    if (b.work_needed != null) el.append(bar(b.work, b.work_needed));
  }
  if (felling.length) {
    const d = document.createElement("div");
    d.append("Felling now: ", ...names(felling));
    el.append(d);
  }
  if (building.length) {
    const d = document.createElement("div");
    d.append("Building now: ", ...names(building));
    el.append(d);
  }
  if (couples.length > 1) {
    const d = document.createElement("div");
    d.className = "hint";
    d.textContent = `${couples.length - 1} more couple${couples.length > 2 ? "s" : ""} waiting after them.`;
    el.append(d);
  }
}

function applyEvent(e, live = true) {
  switch (e.type) {
    case "roster":
      for (const c of e.characters) {
        const known = S.roster[c.id];
        S.roster[c.id] = c;
        // A visitor can appear in a frame before its roster line arrives. Drop
        // the stand-in figure so the next frame draws it properly.
        if (!known && S.people[c.id]) {
          peopleGroup.remove(S.people[c.id].group);
          delete S.people[c.id];
        }
      }
      break;
    case "apprenticed":
      feed(line(e.t, who(e.character), ` leaves school and takes up the trade of ${e.trade}, under `, who(e.master), `.`));
      if (S.roster[e.character]) Object.assign(S.roster[e.character], { trade: e.trade, mentor: e.master });
      break;
    case "took_up_trade":
      feed(line(e.t, who(e.character), ` qualifies as a ${e.trade}.`));
      if (S.roster[e.character]) S.roster[e.character].role = e.trade;
      break;
    case "born":
      feed(line(e.t, who(e.character), ` is born to `, who(e.mother), ` and `, who(e.father), `.`));
      break;
    case "died":
      feed(line(e.t, who(e.character), ` dies in the night, at ${Math.floor(e.age)}.`));
      break;
    case "new_master":
      feed(line(e.t, who(e.character), ` goes on as a ${e.trade} under `, who(e.master), `.`));
      break;
    case "visitor_arrived":
      feed(line(e.t, who(e.character), ` arrives with news from the road: ${(e.carries || []).join("; ")}.`));
      break;
    case "visitor_departed":
      feed(line(e.t, who(e.character), ` takes the east road out, carrying ${(e.takes || []).length} pieces of this village's news.`));
      break;
    case "decision":
      if (e.character !== "world") S.decisions[e.character] = e;
      break;
    case "utterance":
      if (live) say(e.speaker, e.text);
      // A named visitor's lines carry its name (hearthwick/accounts.py).
      feed(line(e.t, e.speaker === "stranger" && e.visitor ? e.visitor : who(e.speaker), `: ${e.text}`));
      remember(e);
      if (e.speaker === S.selected || e.listener === S.selected) renderDetail();
      break;
    case "world_event": {
      if (e.event === "weather") S.weather = (e.data && e.data.kind) || "clear";
      const span = document.createElement("span");
      span.className = "world";
      const what = e.event === "weather" ? `The weather turns to ${(e.data || {}).kind}.`
        : e.event === "sicken" ? `Something turns at the ${e.place}.`
        : e.event === "traveler" ? "A traveler comes up the east road."
        : e.event === "raid" ? "Raiders on the east road."
        : e.event === "festival" ? "The village gathers at the well."
        : e.event === "visitor" ? "A traveling storyteller comes up the east road."
        : e.event === "harvest"
          ? `The harvest is in, and it is ${(e.data || {}).yield}: ${Math.round((e.data || {}).brought_in || 0)} days of food brought in.`
          : e.event;
      span.textContent = what;
      feed(line(e.t, span));
      break;
    }
    case "food":
      S.food = e;
      showFood();
      break;
    case "place_grown": {
      const place = (S.world.places || []).find((p) => p.id === e.place);
      if (place) {
        place.rect = e.rect;
        buildWorld(S.world);
      }
      feed(line(e.t, who(e.by), ` clears new ground. The fields grow to ${e.tiles} plots.`));
      break;
    }
    case "place_added":
      S.world.places = (S.world.places || []).filter((p) => p.id !== e.place.id).concat([e.place]);
      buildWorld(S.world);
      if (e.place.kind === "fields" && e.by) {
        feed(line(e.t, who(e.by), ` and the farmers break new ground: ${e.place.name}.`));
        if (live) notify("Land", who(e.by), ` and the farmers break new ground: ${e.place.name}.`);
      } else if (["quarry", "clay_pit", "forge"].includes(e.place.kind)) {
        feed(line(e.t, `The village opens ${e.place.name}.`));
        if (live) notify("Building", `The village opens ${e.place.name}.`);
      } else if (e.place.kind === "site") {
        feed(line(e.t, who(e.by), ` marks out a plot for a new house.`));
        if (live) notify("Building", who(e.by), ` marks out a plot for a new house.`);
      }
      break;
    case "place_removed":
      S.world.places = (S.world.places || []).filter((p) => p.id !== e.place);
      buildWorld(S.world);
      break;
    case "land_grown":
      S.world.width = e.width;
      S.world.places = (S.world.places || []).map((p) => (e.roads[p.id] ? { ...p, rect: e.roads[p.id] } : p));
      buildWorld(S.world);
      feed(line(e.t, `The village has spread east. There is new land beyond the road, ${e.by} tiles wide.`));
      if (live) notify("Land", `The village has spread east onto new land, ${e.by} tiles wide.`);
      break;
    case "proposed":
      feed(line(e.t, who(e.asker), ` asks `, who(e.asked), ` to marry.`));
      break;
    case "declined":
      feed(line(e.t, who(e.asked), ` says no to `, who(e.asker), `.`));
      break;
    case "married":
      feed(line(e.t, who(e.asked), ` says yes to `, who(e.asker), e.waiting
        ? `. They wait at ${e.home} for a house of their own.` : `. They make their home at ${e.home}.`));
      if (e.waiting) {
        S.waiting.push([e.asker, e.asked]);
        if (live) notify("Building", who(e.asker), " and ", who(e.asked), " marry and need a house of their own.");
      }
      renderBuilding();
      break;
    case "house_built":
      feed(line(e.t, `The crafters finish ${e.place}.`,
        ...(e.couple ? [` `, who(e.couple[0]), ` and `, who(e.couple[1]), ` move in.`] : [])));
      if (live)
        notify("Building", `The crafters finish ${e.place}.`,
               ...(e.couple ? [` `, who(e.couple[0]), ` and `, who(e.couple[1]), ` move in.`] : []));
      S.buildingReport = null;
      if (e.couple) S.waiting = S.waiting.filter((c) => !(c.includes(e.couple[0]) && c.includes(e.couple[1])));
      renderBuilding();
      break;
    case "blight_ended":
      feed(line(e.t, ...(e.by && e.by.length ? [...names(e.by), ` cut the blight out of the fields.`]
                                            : [`The blight is cut out of the fields.`])));
      if (live) notify("Fields", ...(e.by && e.by.length ? [...names(e.by), ` cut the blight out of the fields.`]
                                                         : [`The blight is cut out of the fields.`]));
      break;
    case "purses_opened":
      feed(line(e.t, `Money comes to the village. Everyone living has ${e.coins} coins.`));
      break;
    case "sold": {
      const goods = Object.entries(e.goods || {}).map(([g, a]) => `${a} ${g}`).join(", ");
      feed(line(e.t, who(e.character), ` sells ${goods} at the market for ${e.coins} coins.`));
      break;
    }
    case "inherited":
      if (e.heirs && e.heirs.length && e.coins > 0)
        feed(line(e.t, `What `, who(e.character), ` had, ${e.coins} coins, goes to `, ...names(e.heirs), `.`));
      break;
    case "building":
      // The crafters' report at dawn, while a house is needed.
      S.buildingReport = e;
      if (live) {
        const whole = (S.building && S.building.work_needed) || 180;   // a house's work (building.py)
        const pct = Math.round((100 * (e.progress || 0)) / whole);
        notify("Building", e.site ? `At dawn the house going up is ${pct}% built, with ${e.timber} timber in hand.`
                                  : `At dawn a house is still needed, with ${e.timber} timber in hand.`);
      }
      renderBuilding();
      break;
    case "stage_change":
      feed(line(e.t, who(e.character), ` grows up: ${e.was} to ${e.now}.`));
      if (S.roster[e.character]) S.roster[e.character].stage = e.now;
      break;
    case "persona":
      // Who a villager born here is now, rewritten as it grows (grown personas).
      if (S.roster[e.character]) {
        Object.assign(S.roster[e.character], { persona: e.persona, stage: e.stage, role: e.role, trade: e.trade });
        if (S.selected === e.character) renderDetail();
      }
      break;
  }
}

// ---------------------------------------------------------------------------
// Selection and the detail panel

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let downAt = null;
let hovered = null;
function personAt(ev) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.set(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(peopleGroup.children, true)
    .find((h) => h.object.userData.person && (h.object.isMesh || h.object.isSprite));
  return hit ? hit.object.userData.person : null;
}
renderer.domElement.addEventListener("pointermove", (ev) => {
  hovered = personAt(ev);
  renderer.domElement.style.cursor = hovered ? "pointer" : "";
});
renderer.domElement.addEventListener("pointerdown", (ev) => { downAt = [ev.clientX, ev.clientY]; });
renderer.domElement.addEventListener("pointerup", (ev) => {
  if (!downAt || Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) > 5) return;
  select(personAt(ev));
});

function select(id) {
  if (S.selected && S.people[S.selected]) S.people[S.selected].ring.visible = false;
  S.selected = id;
  if (id && S.people[id]) S.people[id].ring.visible = true;
  renderDetail();
  renderChat();
  const url = new URL(location.href);
  if (id) url.searchParams.set("who", id); else url.searchParams.delete("who");
  history.replaceState(null, "", url);
}

// A villager's side of every conversation it has had: what it said and what
// was said to it, so selecting it shows its conversations and nobody else's.
const TALK_KEPT = 120;
function remember(e) {
  for (const id of [e.speaker, e.listener]) {
    if (!id) continue;
    const lines = (S.talk[id] = S.talk[id] || []);
    lines.push({ t: e.t, conversation: e.conversation, speaker: e.speaker,
                 listener: e.listener, text: e.text, visitor: e.visitor });
    if (lines.length > TALK_KEPT) lines.shift();
  }
}

function conversationsOf(id, esc) {
  const lines = S.talk[id] || [];
  if (!lines.length) return '<p class="hint">No conversations seen yet.</p>';
  // Newest conversation first, its lines in the order they were said.
  const byConv = new Map();
  for (const l of lines) {
    if (!byConv.has(l.conversation)) byConv.set(l.conversation, []);
    byConv.get(l.conversation).push(l);
  }
  return [...byConv.values()].reverse().slice(0, 8).map((conv) => {
    const other = conv[0].speaker === id ? conv[0].listener : conv[0].speaker;
    const said = conv.map((l) => `<li><b>${esc(l.visitor || nameOf(l.speaker))}</b> ${esc(l.text)}</li>`).join("");
    return `<div class="talk"><div class="kv"><b>${esc(tickTime(conv[0].t))}</b> with ${esc(nameOf(other))}</div><ul>${said}</ul></div>`;
  }).join("");
}

function purseOf(id) {
  const p = S.purses[id];
  if (!p) return "";
  const goods = p[1] > 0 ? `, and goods worth ${p[1]}` : "";
  return `<div class="kv"><b>Purse</b> ${p[0]} coins${goods}</div>`;
}

function renderDetail() {
  const box = $("detail");
  const id = S.selected;
  if (!id) {
    box.innerHTML = '<p class="hint">Click a villager to see who they are and what BEAR retrieved for their last decision. Drag to orbit, scroll to zoom.</p>';
    return;
  }
  const prof = S.roster[id] || {};
  const row = S.frameRow[id] || [];
  const d = S.decisions[id];
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const temp = Object.entries(prof.temperament || {}).map(([k, v]) => `<span title="${esc(k)}">${esc(v)}</span>`).join("");
  let decision = '<p class="hint">No decision seen yet.</p>';
  if (d) {
    const items = (d.retrieved || []).filter((r) => r.actionable !== false).slice(0, 5)
      .map((r) => `<li class="${r.id === d.chosen ? "chosen" : ""}">${esc(r.id)} <span>${Number(r.score).toFixed(2)}</span></li>`).join("");
    decision = `<div class="kv"><b>Situation</b> ${esc(d.query)}</div>
      <div class="kv"><b>Chose</b> ${esc(d.chosen || "nothing")}</div>
      <ol class="retrieved">${items}</ol>`;
  }
  box.innerHTML = `<div class="name">${esc(prof.name || id)}</div>
    <div class="sub">${esc(row[4] || prof.stage || "")} · ${esc(prof.role || (prof.trade ? `learning to be a ${prof.trade}` : "no trade yet"))} · age ${Number(row[5] ?? prof.age ?? 0).toFixed(1)}</div>
    <div class="chips">${temp}</div>
    <div class="kv"><b>Now</b> ${esc(row[3] || "…")} at ${esc((placeAt(row[1], row[2]) || {}).name || "the open")}</div>
    ${purseOf(id)}
    <h2>Last decision</h2>${decision}
    <h2>Conversations</h2>${conversationsOf(id, esc)}
    ${prof.persona ? `<h2>Persona</h2><p class="hint">${esc(prof.persona)}</p>` : ""}`;
}

// ---------------------------------------------------------------------------
// Talking with a villager (a village run by `hearthwick serve`)
//
// You are a stranger. The world stands still while you talk, and when you
// leave, the villager decides what to keep of what you said, as it does after
// any conversation. The panel sits outside the detail panel, which is redrawn
// every frame, so what you type is not wiped.

// Who this browser is, for a server reached without a Cloudflare login (as on
// localhost). Behind the login the server knows the account and ignores it.
function visitorToken() {
  try {
    let t = localStorage.getItem("hearthwick-visitor");
    if (!t) {
      t = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
      localStorage.setItem("hearthwick-visitor", t);
    }
    return t;
  } catch {
    return "";
  }
}

async function post(path, body) {
  const r = await fetch(path, { method: "POST",
                                headers: { "Content-Type": "application/json", "X-Visitor": visitorToken() },
                                body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}

async function whoAmI() {
  // A server from before names answers 404, and the chat goes on nameless.
  const r = await fetch("/api/me", { headers: { "X-Visitor": visitorToken() }, cache: "no-store" });
  return r.ok ? r.json() : { name: null, known: false };
}

function renderChat() {
  const box = $("chat");
  const id = S.selected;
  if (!box) return;
  // Only the village the server runs can be talked to. Watching any other
  // run, its villagers are in another process, or already finished.
  if (!S.liveVillage || !id || S.watching !== S.liveRunId) { box.innerHTML = ""; return; }
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  if (S.chat && S.chat.villager !== id) {
    box.innerHTML = `<p class="hint">You are talking with ${esc(S.chat.name)}.</p>`;
    return;
  }
  if (S.naming) {
    // Asked once, before a first chat, and kept against the visitor's account.
    box.innerHTML = `<h2>Talk</h2>
      <form id="name-form"><label for="name-text">What should the villagers call you?</label>
        <input id="name-text" autocomplete="nickname" maxlength="24" placeholder="Your name">
        <button>Save</button></form>
      ${S.chatNote ? `<p class="hint">${esc(S.chatNote)}</p>` : ""}`;
    $("name-form").onsubmit = (ev) => { ev.preventDefault(); saveName(id, $("name-text").value.trim()); };
    $("name-text").focus();
    return;
  }
  if (!S.chat) {
    box.innerHTML = `<h2>Talk</h2><button id="talk-start">Talk to ${esc(nameOf(id))}</button>`
      + (S.chatNote ? `<p class="hint">${esc(S.chatNote)}</p>` : "");
    $("talk-start").onclick = () => talkStart(id);
    return;
  }
  const lines = S.chat.lines.map((l) => `<li><b>${esc(l.who)}</b> ${esc(l.text)}</li>`).join("");
  box.innerHTML = `<h2>Talking with ${esc(S.chat.name)}</h2>
    <p class="hint">Time stands still while you talk.</p>
    <ul class="chatlines">${lines}</ul>
    <form id="talk-form"><input id="talk-text" autocomplete="off" maxlength="500"
      placeholder="${S.chat.busy ? "…" : "Say something"}" ${S.chat.busy ? "disabled" : ""}><button>Say</button></form>
    <button id="talk-end">Leave</button>`;
  $("talk-form").onsubmit = (ev) => {
    ev.preventDefault();
    const text = $("talk-text").value.trim();
    if (text) talkSay(text);
  };
  $("talk-end").onclick = talkEnd;
  if (!S.chat.busy) $("talk-text").focus();
}

async function saveName(id, name) {
  try {
    await post("/api/me", { name });
    S.naming = false;
    S.chatNote = "";
    await talkStart(id);
  } catch (err) {
    S.chatNote = err.message;
    renderChat();
  }
}

async function talkStart(id) {
  try {
    const me = await whoAmI();
    if (!me.name && me.known) {
      S.naming = true;
      S.chatNote = "";
      renderChat();
      return;
    }
    const m = await post("/api/talk/start", { villager: id });
    S.chat = { token: m.token, villager: id, name: m.name, lines: [], busy: false };
    S.chatNote = "";
  } catch (err) {
    S.chatNote = err.message;
  }
  renderChat();
}

async function talkSay(text) {
  const chat = S.chat;
  if (!chat || chat.busy) return;
  chat.lines.push({ who: "You", text });
  chat.busy = true;
  renderChat();
  try {
    const m = await post("/api/talk/say", { token: chat.token, text });
    chat.lines.push({ who: chat.name, text: m.reply || "…" });
  } catch (err) {
    chat.lines.push({ who: "", text: err.message });
  }
  chat.busy = false;
  renderChat();
}

async function talkEnd() {
  const chat = S.chat;
  if (!chat) return;
  try {
    const m = await post("/api/talk/end", { token: chat.token });
    S.chatNote = m.kept === null || m.kept === undefined ? ""
      : m.kept ? `${chat.name} will remember it as: "${m.as}"`
      : m.outcome === "duplicate" ? `${chat.name} had heard that already.`
      : `${chat.name} did not keep what you said.`;
  } catch (err) {
    S.chatNote = err.message;
  }
  S.chat = null;
  renderChat();
}

// ---------------------------------------------------------------------------
// Connection

function setStatus(text, live) {
  $("status-text").textContent = text;
  $("status").classList.toggle("live", !!live);
}

// The card over the scene from connecting until the village answers. The
// first visit after a restart waits minutes while the server reads the run's
// history, and a bare spinner invited refreshing, which only starts again.
const L = { since: 0, timer: null, restarting: false };

function showLoading(restarting) {
  L.restarting = restarting;
  if (!L.since) L.since = Date.now();
  $("loading-title").textContent = restarting ? "The village is restarting…" : "Opening the village…";
  $("loading").hidden = false;
  if (!L.timer) { pollLoading(); L.timer = setInterval(pollLoading, 2000); }
}

function hideLoading() {
  $("loading").hidden = true;
  clearInterval(L.timer);
  L.timer = null;
  L.since = 0;
}

function waited() {
  const s = Math.round((Date.now() - L.since) / 1000);
  if (s < 5) return "";
  return s < 60 ? ` You've waited ${s} seconds.` : ` You've waited ${Math.floor(s / 60)} min ${s % 60} s.`;
}

async function pollLoading() {
  const bar = $("loading-bar");
  try {
    const r = await fetch(`/api/loading?run=${encodeURIComponent(S.run)}`, { cache: "no-store" });
    if (!r.ok) throw new Error(String(r.status));
    const d = await r.json();
    const pct = d.size ? Math.min(100, Math.floor((100 * d.read) / d.size)) : 0;
    bar.classList.remove("unknown");
    $("loading-fill").style.width = `${pct}%`;
    $("loading-text").textContent = pct >= 100
      ? `History read. Drawing the village.${waited()}`
      : `Reading the village's history, ${pct}% done.${waited()}`;
  } catch {
    // The server is not answering yet: starting up, or restarting.
    bar.classList.add("unknown");
    $("loading-fill").style.width = "";
    $("loading-text").textContent = `The village is starting up.${waited()}`;
  }
}

function connect() {
  if (S.ws) { S.ws.onclose = null; S.ws.close(); }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const q = new URLSearchParams({ run: S.run, start: S.start, rate: String(S.rate) });
  if (S.start === "begin" && S.from) q.set("from", String(S.from));
  const ws = new WebSocket(`${proto}://${location.host}/ws/follow?${q}`);
  S.ws = ws;
  setStatus("connecting", false);
  showLoading(L.restarting);
  let greeted = false;
  $("live").classList.toggle("on", S.start === "live");
  $("begin").classList.toggle("on", S.start === "begin");

  ws.onmessage = (msg) => {
    const m = JSON.parse(msg.data);
    if (m.type === "hello") {
      greeted = true;
      L.restarting = false;
      hideLoading();
      for (const p of Object.values(S.people)) peopleGroup.remove(p.group);
      S.people = {}; S.decisions = {}; S.frameRow = {}; S.roster = {}; S.bubbles = []; S.talk = {};
      S.building = null; S.buildingReport = null; S.buildingShown = ""; S.waiting = [];
      S.purses = {};
      $("notices").innerHTML = "";
      $("feed").innerHTML = "";
      for (const c of m.roster || []) S.roster[c.id] = c;
      buildWorld(m.world);
      S.weather = m.weather || "clear";
      S.food = m.food || null;
      showFood();
      Object.assign(S.decisions, m.decisions || {});
      for (const e of m.recent || []) applyEvent(e, false);
      S.live = m.live;
      if (m.frame) applyFrame(m.frame, false);
      setStatus(m.live ? `following ${m.run_id}` : `${m.run_id}, finished`, m.live);
      S.watching = m.run_id;
      renderChat();
      const who = new URLSearchParams(location.search).get("who");
      if (who) select(who);
    } else if (m.type === "tick") {
      for (const e of m.events || []) applyEvent(e, true);
      applyFrame(m.frame, true);
      if (m.live !== S.live) {
        S.live = m.live;
        setStatus(m.live ? `following ${S.run === "latest" ? "the live run" : S.run}` : "run finished", m.live);
      }
    } else if (m.type === "jumped") {
      S.weather = m.weather || S.weather;
      if (m.food) { S.food = m.food; showFood(); }
      Object.assign(S.decisions, m.decisions || {});
      if (m.frame) applyFrame(m.frame, false);
    } else if (m.type === "end") {
      setStatus("end of the run. Press From start to replay it", false);
    } else if (m.type === "error") {
      setStatus(m.detail || "error", false);
    }
  };
  ws.onclose = () => {
    setStatus("disconnected, retrying", false);
    // A live connection that drops is a village restarting; one that never
    // got its hello is still opening.
    showLoading(greeted || L.restarting);
    setTimeout(connect, 3000);
  };
}

async function loadRuns() {
  const sel = $("run");
  const runs = await fetch("/api/runs").then((r) => r.json()).catch(() => []);
  sel.innerHTML = "";
  const latest = document.createElement("option");
  latest.value = "latest";
  latest.textContent = "Latest run";
  sel.append(latest);
  for (const r of runs) {
    const o = document.createElement("option");
    o.value = r.run_id;
    o.textContent = `${r.live ? "● " : ""}${r.run_id}`;
    sel.append(o);
  }
  sel.value = S.run;
}

function updateUrl() {
  const url = new URL(location.href);
  url.searchParams.set("run", S.run);
  url.searchParams.set("start", S.start);
  url.searchParams.set("rate", String(S.rate));
  history.replaceState(null, "", url);
}

// ---------------------------------------------------------------------------
// Frame loop

const clock = new THREE.Clock();
const followTarget = new THREE.Vector3();
function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(0.1, clock.getDelta());
  const now = performance.now();
  const showNames = $("names").checked;
  for (const p of Object.values(S.people)) {
    const k = Math.min(1, (now - p.at) / S.interval);
    // Position along the route at the same share of its length.
    const total = p.lengths ? p.lengths[p.lengths.length - 1] : 0;
    let dx = 0, dz = 0;
    if (total > 1e-4) {
      const d = k * total;
      let i = 1;
      while (i < p.lengths.length - 1 && p.lengths[i] < d) i++;
      const a = p.route[i - 1], b = p.route[i];
      const seg = p.lengths[i] - p.lengths[i - 1];
      p.group.position.lerpVectors(a, b, seg > 0 ? (d - p.lengths[i - 1]) / seg : 1);
      dx = b.x - a.x;
      dz = b.z - a.z;
    } else {
      p.group.position.copy(p.to);
    }
    const moving = k < 1 && dx * dx + dz * dz > 1e-4;
    if (moving) p.body.rotation.y = Math.atan2(dx, dz);
    if (p.worn) p.worn.rotation.y = p.body.rotation.y;
    p.phase += dt * (moving ? 10 : 0);
    const swing = moving ? Math.sin(p.phase) * 0.6 : 0;
    p.legs[0].rotation.x = swing;
    p.legs[1].rotation.x = -swing;
    p.arms[0].rotation.x = -swing * 0.8;
    p.arms[1].rotation.x = swing * 0.8;
    p.body.position.y = moving ? Math.abs(Math.sin(p.phase)) * 0.05 * p.scale : 0;
    p.name.visible = showNames || p.id === S.selected || p.id === hovered;
  }
  S.bubbles = S.bubbles.filter((b) => {
    if (now < b.until) return true;
    b.person.group.remove(b.sprite);
    b.sprite.material.dispose();
    return false;
  });
  for (const hub of millBlades) hub.rotation.z += dt * 0.6;
  moveStructures(dt);
  updateSky();
  updateWeather(dt);
  if ($("follow").checked && S.selected && S.people[S.selected]) {
    followTarget.copy(S.people[S.selected].group.position);
    followTarget.z -= aimNorth;
    const delta = followTarget.clone().sub(controls.target).multiplyScalar(Math.min(1, dt * 3));
    controls.target.add(delta);
    camera.position.add(delta);
  }
  controls.update();
  renderer.render(scene, camera);
  $("overlay").textContent = S.weather !== "clear" ? S.weather : "";
}

// ---------------------------------------------------------------------------
// Start

const params = new URLSearchParams(location.search);
S.run = params.get("run") || "latest";
S.start = params.get("start") === "begin" ? "begin" : "live";
S.rate = Number(params.get("rate")) || 6;
S.from = Number(params.get("from")) || 0;       // replay from this tick
// A still for the paper (?paper=1, experiments/capture_3d.py): no name, run
// id or controls, and none of the panels for mechanics the paper's build has
// off. ?follow=1 keeps the camera on the villager named by ?who. Both are off
// unless the link asks for them, so the viewer is otherwise unchanged.
if (params.get("paper") === "1") {
  document.body.classList.add("paper");
  document.title = "Village Sim";
}
if (params.get("follow") === "1") $("follow").checked = true;
// ?zoom=2 starts the camera twice as close, keeping its angle, and ?aim=4
// keeps it on a point four tiles north of the villager it follows, for a
// villager at the edge of the village.
const zoom = Number(params.get("zoom")) || 1;
if (zoom > 0 && zoom !== 1) camera.position.multiplyScalar(1 / zoom);
const aimNorth = Number(params.get("aim")) || 0;
$("rate").value = String(S.rate);
$("rate-value").textContent = String(S.rate);

$("run").onchange = () => { S.run = $("run").value; updateUrl(); connect(); };
$("live").onclick = () => { S.start = "live"; updateUrl(); connect(); };
$("begin").onclick = () => { S.start = "begin"; updateUrl(); connect(); };
$("rate").oninput = () => {
  S.rate = Number($("rate").value);
  $("rate-value").textContent = String(S.rate);
  if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify({ cmd: "rate", value: S.rate }));
  updateUrl();
};

resize();
animate();
// A server that runs its own village (hearthwick serve) opens on it, unless
// the link names another run, since that is the one that can be talked to.
fetch("/api/live").then((r) => r.json())
  .then((m) => {
    S.liveVillage = !!m.live;
    S.liveRunId = m.run_id || null;
    if (S.liveVillage && !params.get("run")) S.run = S.liveRunId;
  })
  .catch(() => {})
  .finally(() => loadRuns().then(connect));
setInterval(loadRuns, 30000);
