// The class city in 3D: one house per student, one rounded block per floor.
//
// It runs in the browser of whoever opens the City tab, never on the board,
// which only serves this file. Two quality levels:
//   high   antialiasing, soft shadows, rounded blocks, sharp at any pixel ratio
//   light  plain blocks, no shadows, 3/4 resolution: for weak machines, or a
//          browser running on the UNO Q itself
// Geometries and textures are shared; each house owns only its two materials
// and its name label. Rendering stops whenever the tab is hidden.
import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";
import { RoundedBoxGeometry } from "three/addons/RoundedBoxGeometry.js";

const FLOOR_H = 0.62;
const GAP = 0.04;           // a thin line between floors, so you can count them
const W = 1.5;              // house width
const LOT = 3.3;            // distance between houses
const LABEL_DISTANCE = 38;  // names further than this from the camera are hidden

export function preferredQuality() {
  try {
    const saved = localStorage.getItem("kc-quality");
    if (saved) return saved;
  } catch { /* fine */ }
  const weak = (navigator.hardwareConcurrency || 4) <= 4 || (navigator.deviceMemory || 8) <= 4;
  return weak ? "light" : "high";
}

function canvasTexture(size, draw) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  draw(canvas.getContext("2d"), size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

// Built once per quality level and shared by every house
function makeKit(high) {
  const box = (w, h, d, r) => high && r ? new RoundedBoxGeometry(w, h, d, 3, r) : new THREE.BoxGeometry(w, h, d);
  const Mat = high ? THREE.MeshStandardMaterial : THREE.MeshLambertMaterial;
  const mat = (color, extra = {}) => new Mat({ color, ...(high ? { roughness: 0.85 } : {}), ...extra });
  // Walls are white in the texture, so the house color tints them; windows are a soft grey
  const windows = (g, s, wall, glass) => {
    g.fillStyle = wall; g.fillRect(0, 0, s, s);
    g.fillStyle = glass;
    const u = s / 16;
    g.beginPath();
    g.roundRect(3 * u, 4 * u, 4 * u, 7 * u, u);
    g.roundRect(9 * u, 4 * u, 4 * u, 7 * u, u);
    g.fill();
  };
  return {
    high,
    Mat,
    geo: {
      floor: box(W, FLOOR_H - GAP, W, 0.08),
      cap: box(W + 0.12, 0.12, W + 0.12, 0.05),
      hut: box(0.5, 0.32, 0.5, 0.06),
      door: box(0.38, 0.5, 0.06, 0.03),
      lot: box(LOT - 0.5, 0.1, LOT - 0.5, 0.05),
      tank: new THREE.CylinderGeometry(0.19, 0.19, 0.34, high ? 20 : 10),
      lid: new THREE.CylinderGeometry(0.21, 0.21, 0.04, high ? 20 : 10),
      pipe: new THREE.CylinderGeometry(0.02, 0.02, 0.4, 6),
      trunk: new THREE.CylinderGeometry(0.05, 0.06, 0.35, 8),
      crown: new THREE.IcosahedronGeometry(0.32, high ? 1 : 0),
      bed: box(0.9, 0.12, 0.5, 0.05),
      panel: box(0.3, 0.03, 0.56, 0.01),
      leg: box(0.04, 0.14, 0.04),
      planter: box(0.62, 0.12, 0.62, 0.04),
      rim: box(0.66, 0.12, 0.62, 0.04),
      water: new THREE.BoxGeometry(0.52, 0.02, 0.48),
      tower: new THREE.CylinderGeometry(0.018, 0.028, 1.0, 8),
      hub: new THREE.SphereGeometry(0.05, 12, 8),
      blade: box(0.05, 0.42, 0.012, 0.005),
      pin: new THREE.ConeGeometry(0.2, 0.42, high ? 24 : 8),
      coin: new THREE.CylinderGeometry(0.14, 0.14, 0.04, high ? 20 : 10),
    },
    mat: {
      ground: mat(0xf1f1ee),
      lot: mat(0xffffff),
      door: mat(0x8a6a55),
      white: mat(0xf4f4f2),
      tank: mat(0x9ec9e2),
      lid: mat(0x6e9fbf),
      trunk: mat(0x9b7b63),
      crown: mat(0x8fd19e),
      bed: mat(0xf7b8cf),
      panel: mat(0x34478a, high ? { roughness: 0.35, metalness: 0.3 } : {}),
      soil: mat(0x8a6a55),
      shrub: mat(0x6cc283),
      water: mat(0x7fd3f0, high ? { roughness: 0.15, metalness: 0.1 } : {}),
      blade: mat(0xc3cad3),
      pin: new THREE.MeshBasicMaterial({ color: 0x2f6fe4 }),
      coin: mat(0xf6c343, { emissive: 0x4a3200 }),
    },
    wall: canvasTexture(high ? 128 : 32, (g, s) => windows(g, s, "#ffffff", "#c9ced6")),
  };
}

function labelSprite(text, high) {
  const scale = high ? 2 : 1;
  const canvas = document.createElement("canvas");
  canvas.width = 256 * scale; canvas.height = 64 * scale;
  const g = canvas.getContext("2d");
  g.scale(scale, scale);
  g.font = "600 26px system-ui, sans-serif";
  const label = text.length > 16 ? text.slice(0, 15) + "…" : text;
  const width = Math.min(240, g.measureText(label).width + 32);
  g.fillStyle = "rgba(255,255,255,0.92)";
  g.beginPath(); g.roundRect(128 - width / 2, 12, width, 40, 20); g.fill();
  g.fillStyle = "#17181c"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(label, 128, 33);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  // Always on top, so a tall neighbour never hides a name
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, depthTest: false, depthWrite: false }));
  sprite.renderOrder = 10;
  sprite.scale.set(2.3, 0.575, 1);
  return sprite;
}

class House {
  constructor(kit, resident) {
    this.kit = kit;
    this.group = new THREE.Group();
    this.shown = 0;
    this.growing = [];
    this.key = "";
    this.update(resident);
  }

  // Rebuild only when the color or the items change; new floors grow in place
  update(r) {
    const key = r.color + "|" + r.items.join(",");
    if (key !== this.key) {
      this.dispose();
      this.key = key;
      this.build(r);
      this.addFloors(r.floors, false);
    } else if (r.floors > this.shown) {
      this.addFloors(r.floors, true);
    }
    this.placeTop();
  }

  mesh(geo, mat, shadow = true) {
    const m = new THREE.Mesh(geo, mat);
    m.castShadow = m.receiveShadow = shadow && this.kit.high;
    return m;
  }

  build(r) {
    const { geo, mat, high } = this.kit;
    this.wall = new this.kit.Mat({ color: new THREE.Color(r.color), map: this.kit.wall, ...(high ? { roughness: 0.8 } : {}) });
    this.capMat = new this.kit.Mat({ color: new THREE.Color(r.color).lerp(new THREE.Color(0xffffff), 0.55) });

    this.group.add(this.mesh(geo.lot, mat.lot));
    const door = this.mesh(geo.door, mat.door);
    door.position.set(0, 0.3, W / 2 + 0.02);
    this.group.add(door);
    this.floors = new THREE.Group();
    this.group.add(this.floors);

    // The roof and everything on it moves up with each floor. Each roof item
    // has its own corner, so any mix of them fits:
    //   back left: stairs hut (+ rainwater tank on it)   back right: solar panels
    //   front left: roof garden             front right: pool
    //   middle: the wind turbine, above the rest
    const C = 0.4;
    this.top = new THREE.Group();
    this.top.add(this.mesh(geo.cap, this.capMat));
    const hut = this.mesh(geo.hut, this.capMat);
    hut.position.set(-C, 0.22, -C);
    this.top.add(hut);
    if (r.items.includes("rain_tank")) {
      // Collects rain for the garden: a tank on the hut, a pipe down its side
      const tank = this.mesh(geo.tank, mat.tank);
      tank.position.set(-C, 0.55, -C);
      const lid = this.mesh(geo.lid, mat.lid);
      lid.position.set(-C, 0.74, -C);
      const pipe = this.mesh(geo.pipe, mat.lid);
      pipe.position.set(-C + 0.27, 0.26, -C + 0.1);
      this.top.add(tank, lid, pipe);
    }
    if (r.items.includes("solar")) {
      for (const x of [C - 0.16, C + 0.16]) {
        const panel = this.mesh(geo.panel, mat.panel);
        panel.position.set(x, 0.17, -C);
        panel.rotation.x = 0.4;   // tilted towards the sun
        const leg = this.mesh(geo.leg, mat.white);
        leg.position.set(x, 0.12, -C - 0.16);
        this.top.add(panel, leg);
      }
    }
    if (r.items.includes("roof_garden")) {
      const planter = this.mesh(geo.planter, mat.soil);
      planter.position.set(-C, 0.1, C);
      this.top.add(planter);
      for (const [dx, dz, s] of [[-0.14, -0.12, 0.42], [0.14, -0.1, 0.34], [-0.1, 0.15, 0.32], [0.15, 0.15, 0.4]]) {
        const shrub = this.mesh(geo.crown, mat.shrub);
        shrub.position.set(-C + dx, 0.2 + s * 0.2, C + dz);
        shrub.scale.setScalar(s);
        this.top.add(shrub);
      }
    }
    if (r.items.includes("pool")) {
      const rim = this.mesh(geo.rim, mat.white);
      rim.position.set(C, 0.1, C);
      const water = this.mesh(geo.water, mat.water, false);
      water.position.set(C, 0.165, C);
      this.top.add(rim, water);
    }
    if (r.items.includes("wind")) {
      const tower = this.mesh(geo.tower, mat.white);
      tower.position.set(0, 0.56, 0);
      this.rotor = new THREE.Group();
      this.rotor.position.set(0, 1.06, 0.06);
      this.rotor.add(this.mesh(geo.hub, mat.blade));
      for (let k = 0; k < 3; k++) {
        const arm = new THREE.Group();
        arm.rotation.z = (k * 2 * Math.PI) / 3;
        const blade = this.mesh(geo.blade, mat.blade);
        blade.position.y = 0.23;
        arm.add(blade);
        this.rotor.add(arm);
      }
      this.top.add(tower, this.rotor);
    }
    this.group.add(this.top);

    if (r.items.includes("trees")) {
      const bed = this.mesh(geo.bed, mat.bed);
      bed.position.set(-0.95, 0.1, 1.1);
      this.group.add(bed);
      for (const [x, z, s] of [[1.12, 1.05, 1], [1.12, -0.9, 0.8]]) {
        const trunk = this.mesh(geo.trunk, mat.trunk);
        trunk.position.set(x, 0.22, z);
        const crown = this.mesh(geo.crown, mat.crown);
        crown.position.set(x, 0.6 * s + 0.1, z);
        crown.scale.setScalar(s);
        this.group.add(trunk, crown);
      }
    }

    // The name floats above the tallest roof item
    this.labelLift = r.items.includes("wind") ? 1.85 : r.items.includes("rain_tank") ? 1.55 : 1.05;
    this.label = labelSprite(r.student, high);
    this.group.add(this.label);
  }

  addFloors(count, animate) {
    while (this.shown < count) {
      const floor = this.mesh(this.kit.geo.floor, this.wall);
      floor.position.y = 0.05 + FLOOR_H * (this.shown + 0.5);
      if (animate) {
        floor.scale.set(1, 0.01, 1);
        this.growing.push({ mesh: floor, t: 0 });
      }
      this.floors.add(floor);
      this.shown++;
    }
  }

  get height() { return 0.05 + FLOOR_H * this.shown; }

  placeTop() {
    this.top.position.y = this.height + 0.04;
    this.label.position.y = this.height + this.labelLift;
  }

  tick(dt, time) {
    for (const g of this.growing) {
      g.t = Math.min(1, g.t + dt * 1.5);
      const s = g.t < 1 ? 1 - Math.pow(1 - g.t, 3) * Math.cos(g.t * 6) : 1;   // ease out with a small bounce
      g.mesh.scale.y = Math.max(0.01, s);
    }
    this.growing = this.growing.filter(g => g.t < 1);
    // The turbine turns slowly (a smooth motion, nothing flashes)
    if (this.rotor) this.rotor.rotation.z = -time * 1.5;
  }

  dispose() {
    this.wall?.dispose();
    this.capMat?.dispose();
    if (this.label) { this.label.material.map.dispose(); this.label.material.dispose(); }
    this.group.clear();
    this.shown = 0;
    this.growing = [];
    this.rotor = null;
  }
}

export class CityView {
  constructor(canvas, quality = "high") {
    const high = quality === "high";
    this.canvas = canvas;
    this.kit = makeKit(high);
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: high, alpha: false, powerPreference: high ? "default" : "low-power" });
    this.renderer.setPixelRatio(high ? Math.min(devicePixelRatio, 2) : 0.75);
    this.renderer.setClearColor(0xf6f6f3);
    if (high) {
      this.renderer.shadowMap.enabled = true;
      this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    }

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0xf6f6f3, 45, 110);
    this.camera = new THREE.PerspectiveCamera(32, 1, 0.5, 300);
    this.camera.position.set(14, 12, 14);

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xe6e3dc, high ? 2.2 : 2.3));
    this.sun = new THREE.DirectionalLight(0xfff6ea, high ? 2.4 : 1.5);
    if (high) {
      this.sun.castShadow = true;
      this.sun.shadow.mapSize.set(2048, 2048);
      this.sun.shadow.radius = 5;
      this.sun.shadow.bias = -0.0004;
      this.sun.shadow.normalBias = 0.02;
    }
    this.scene.add(this.sun, this.sun.target);

    const ground = new THREE.Mesh(new THREE.PlaneGeometry(400, 400), this.kit.mat.ground);
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = high;
    this.scene.add(ground);

    this.pin = new THREE.Mesh(this.kit.geo.pin, this.kit.mat.pin);
    this.pin.renderOrder = 11;
    this.kit.mat.pin.depthTest = false;   // drawn over neighbours, like the names
    this.pin.rotation.x = Math.PI;
    this.pin.visible = false;
    this.scene.add(this.pin);

    // Camera: drag to turn, wheel or pinch to zoom towards the pointer.
    // It glides to my house once; as soon as the student touches the map, it
    // stops following and stops spinning, so nothing fights their zoom.
    this.controls = new OrbitControls(this.camera, canvas);
    Object.assign(this.controls, {
      enableDamping: true, dampingFactor: 0.1, enablePan: false, zoomToCursor: true, zoomSpeed: 1.2,
      minPolarAngle: 0.35, maxPolarAngle: 1.3, minDistance: 3, maxDistance: 90,
      autoRotate: true, autoRotateSpeed: 0.35,
    });
    this.follow = true;           // gliding to my house
    this.followDistance = null;   // camera distance to reach while gliding (null: keep it)
    this.controls.addEventListener("start", () => {
      this.follow = false;
      this.controls.autoRotate = false;
    });

    this.houses = new Map();
    this.sparks = [];
    this.me = null;
    this.framed = false;
    this.clock = new THREE.Clock();
    this.observer = new ResizeObserver(() => this.resize());
    this.observer.observe(canvas);
    this.resize();
  }

  setActive(on) {
    this.renderer.setAnimationLoop(on ? () => this.frame() : null);
    if (on) { this.clock.getDelta(); this.resize(); }
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.canvas;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  // residents: the list from /api/city; me: the current student's name
  setResidents(residents, me) {
    this.me = me;
    const names = new Set(residents.map(r => r.student));
    for (const [name, house] of this.houses) {
      if (!names.has(name)) { house.dispose(); this.scene.remove(house.group); this.houses.delete(name); }
    }
    const cols = Math.max(3, Math.ceil(Math.sqrt(residents.length)));
    const rows = Math.max(1, Math.ceil(residents.length / cols));
    residents.forEach((r, i) => {
      let house = this.houses.get(r.student);
      if (!house) {
        house = new House(this.kit, r);
        this.houses.set(r.student, house);
        this.scene.add(house.group);
      } else {
        house.update(r);
      }
      house.group.position.set(((i % cols) - (cols - 1) / 2) * LOT, 0, (Math.floor(i / cols) - (rows - 1) / 2) * LOT);
    });

    const size = Math.max(cols, rows) * LOT;
    const shadow = this.sun.shadow.camera;
    shadow.left = shadow.bottom = -size;
    shadow.right = shadow.top = size;
    shadow.far = 120;
    shadow.updateProjectionMatrix();
    this.controls.maxDistance = 14 + size * 2;
    if (!this.framed) {   // first look: the whole city, from a corner
      const d = 6 + size * 1.2;
      this.camera.position.set(d * 0.7, d * 0.6, d * 0.7);
      this.controls.target.set(0, 0, 0);
      this.framed = true;
    }
  }

  // Glide back to my house, close enough to see its roof
  focusMe() {
    this.follow = true;
    this.followDistance = 16;
  }

  // Golden coins jump out of a house: a purchase or a new floor
  celebrate(student, count = 16) {
    const house = this.houses.get(student);
    if (!house) return;
    const origin = house.group.position.clone().setY(house.height + 0.6);
    for (let i = 0; i < count; i++) {
      const mesh = new THREE.Mesh(this.kit.geo.coin, this.kit.mat.coin);
      mesh.position.copy(origin);
      mesh.rotation.x = Math.PI / 2;
      const v = new THREE.Vector3((Math.random() - 0.5) * 3, 3 + Math.random() * 3, (Math.random() - 0.5) * 3);
      this.scene.add(mesh);
      this.sparks.push({ mesh, v, life: 1.3 });
    }
  }

  frame() {
    const dt = Math.min(0.05, this.clock.getDelta());
    const time = this.clock.elapsedTime;

    const mine = this.me && this.houses.get(this.me);
    if (mine && this.follow) {
      // Move the target and the camera together, so the zoom stays as it is
      const target = this.controls.target;
      const goal = mine.group.position.clone().setY(mine.height * 0.5);
      const step = goal.sub(target).multiplyScalar(0.06);
      target.add(step);
      this.camera.position.add(step);
      let still = step.length() < 0.002;
      if (this.followDistance) {
        const offset = this.camera.position.clone().sub(target);
        const length = offset.length();
        const next = length + (this.followDistance - length) * 0.08;
        this.camera.position.copy(target).add(offset.setLength(next));
        still = still && Math.abs(next - this.followDistance) < 0.02;
      }
      if (still) { this.follow = false; this.followDistance = null; }
    }
    if (mine) {
      this.pin.visible = true;
      this.pin.position.copy(mine.group.position);
      this.pin.position.y = mine.height + mine.labelLift + 0.7 + Math.sin(time * 2.5) * 0.1;
      this.pin.rotation.y = time;
    }
    this.controls.update();
    const t = this.controls.target;
    this.sun.position.set(t.x + 10, 18, t.z + 7);
    this.sun.target.position.copy(t);

    for (const house of this.houses.values()) {
      house.tick(dt, time);
      // With a full class, only nearby names are shown (and always mine): zoom in to read the others
      house.label.visible = house === mine || this.camera.position.distanceTo(house.group.position) < LABEL_DISTANCE;
    }
    for (const s of this.sparks) {
      s.life -= dt;
      s.v.y -= 9 * dt;
      s.mesh.position.addScaledVector(s.v, dt);
      s.mesh.rotation.z += dt * 8;
    }
    for (const s of this.sparks.filter(s => s.life <= 0)) this.scene.remove(s.mesh);
    this.sparks = this.sparks.filter(s => s.life > 0);

    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.setActive(false);
    this.observer.disconnect();
    this.controls.dispose();
    for (const house of this.houses.values()) house.dispose();
    for (const g of Object.values(this.kit.geo)) g.dispose();
    for (const m of Object.values(this.kit.mat)) m.dispose();
    this.kit.wall.dispose();
    this.renderer.dispose();
  }
}
