// Where a villager walked between two ticks, for drawing only.
//
// The simulation moves a villager up to three tiles a tick along a path that
// never enters water, but a frame records only where it ended up. A straight
// line between two frames can therefore cut across the stream when the real
// path went over the bridge. When it would, this finds a dry route instead.
// It has no three.js dependency, so it can be tested on its own.

const key = (x, y) => `${x},${y}`;

// Tiles that cannot be walked on, from the world's blocked rectangles.
export function waterOf(world) {
  const wet = new Set();
  for (const b of world.blocked || []) {
    const [x, y, w, h] = b.rect;
    for (let i = x; i < x + w; i++) for (let j = y; j < y + h; j++) wet.add(key(i, j));
  }
  return wet;
}

// Whether the straight line between two tile centres passes over water.
export function crossesWater(wet, a, b) {
  const n = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) * 4) + 1;
  for (let i = 0; i <= n; i++) {
    const x = a[0] + ((b[0] - a[0]) * i) / n, y = a[1] + ((b[1] - a[1]) * i) / n;
    // Test the tiles the point touches, not only the nearest, so a line that
    // grazes the corner of a water tile counts as crossing it.
    for (const tx of [Math.floor(x + 0.25), Math.ceil(x - 0.25)])
      for (const ty of [Math.floor(y + 0.25), Math.ceil(y - 0.25)])
        if (wet.has(key(tx, ty))) return true;
  }
  return false;
}

// The shortest dry route from a to b, 8-connected, never cutting a wet corner.
// Returns the tiles after a, ending with b, or null if b cannot be reached.
export function dryRoute(wet, width, height, a, b) {
  const start = key(a[0], a[1]), goal = key(b[0], b[1]);
  const prev = new Map([[start, null]]);
  const queue = [a];
  const dry = (x, y) => x >= 0 && y >= 0 && x < width && y < height && !wet.has(key(x, y));
  while (queue.length) {
    const [x, y] = queue.shift();
    if (key(x, y) === goal) break;
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]]) {
      const nx = x + dx, ny = y + dy, k = key(nx, ny);
      if (prev.has(k) || !dry(nx, ny)) continue;
      if (dx && dy && !(dry(x + dx, y) && dry(x, y + dy))) continue;
      prev.set(k, key(x, y));
      queue.push([nx, ny]);
    }
  }
  if (!prev.has(goal)) return null;
  const tiles = [];
  for (let k = goal; k !== start; k = prev.get(k)) tiles.push(k.split(",").map(Number));
  return tiles.reverse();
}

// The waypoints to draw a move through: straight when that stays dry, else a
// dry route with the points where it turns.
export function routeBetween(wet, width, height, a, b) {
  if (!crossesWater(wet, a, b)) return [b];
  const tiles = dryRoute(wet, width, height, a, b);
  if (!tiles) return [b];
  // Keep only the tiles where the route turns, so the walk stays smooth.
  const out = [];
  let from = a;
  for (let i = 0; i < tiles.length; i++) {
    const next = tiles[i + 1];
    if (!next || crossesWater(wet, from, next)) {
      out.push(tiles[i]);
      from = tiles[i];
    }
  }
  return out;
}
