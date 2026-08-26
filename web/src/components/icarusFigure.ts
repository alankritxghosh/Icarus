import * as THREE from "three";

/**
 * Icarus, in three dimensions, built from the SAME parametric fan the Mac app
 * draws (mac/Icarus/Sources/Icarus/IconArt.swift): six feathers per wing, one
 * wing defined and mirrored, plus the downward V of the body.
 *
 * Rebuilt from those numbers rather than by loading a model, for two reasons.
 * A stock asset would be somebody else's Icarus and would drift from the Dock
 * icon and the favicon, which are all the same geometry today. And each feather
 * has to be its OWN mesh so the flap can ripple outward along the wing -- a
 * single extruded silhouette can only rotate as a slab.
 *
 * Source-of-truth note: these constants are copied from IconArt.swift. If the
 * mark changes there, it must be changed here; nothing enforces that.
 */
const FEATHERS = 6;
const ROOT_X = 49, ROOT_Y = 54;
const ANGLE_LOW = -2, ANGLE_HIGH = 34;
const LEN_LOW = 32, LEN_HIGH = 58;
const W_LOW = 3, W_HIGH = 5.5;
const COVERTS_REACH = 0.75;

// The Swift path is in a 0..100 box with y measured DOWN (SVG convention).
// Everything below flips y and works from the wing root, so the figure sits at
// the origin and rotates about its own shoulder rather than a corner.
const fx = (x: number) => x - ROOT_X;
const fy = (y: number) => -(y - ROOT_Y);

function tip(angleDeg: number, length: number) {
  const r = (angleDeg * Math.PI) / 180;
  return { x: ROOT_X + Math.cos(r) * length, y: ROOT_Y - Math.sin(r) * length };
}

function featherShape(i: number): THREE.Shape {
  const t = i / (FEATHERS - 1);
  const angle = ANGLE_LOW + (ANGLE_HIGH - ANGLE_LOW) * t;
  const length = LEN_LOW + (LEN_HIGH - LEN_LOW) * t;
  const halfWidth = W_LOW + (W_HIGH - W_LOW) * t;
  const r = (angle * Math.PI) / 180;
  const d = { x: Math.cos(r), y: -Math.sin(r) };
  const perp = { x: Math.sin(r), y: Math.cos(r) };
  const end = tip(angle, length);
  const mid = { x: ROOT_X + 0.52 * length * d.x, y: ROOT_Y + 0.52 * length * d.y };

  const s = new THREE.Shape();
  s.moveTo(fx(ROOT_X), fy(ROOT_Y));
  s.quadraticCurveTo(
    fx(mid.x - perp.x * halfWidth), fy(mid.y - perp.y * halfWidth),
    fx(end.x), fy(end.y),
  );
  s.quadraticCurveTo(
    fx(mid.x + perp.x * halfWidth * 0.3), fy(mid.y + perp.y * halfWidth * 0.3),
    fx(ROOT_X), fy(ROOT_Y),
  );
  s.closePath();
  return s;
}

/** The solid leading edge. Without it the separated feathers read as spikes. */
function covertsShape(): THREE.Shape {
  const top = tip(ANGLE_HIGH, LEN_HIGH);
  const midAngle = ANGLE_LOW + (ANGLE_HIGH - ANGLE_LOW) * 0.45;
  const midLength = LEN_LOW + (LEN_HIGH - LEN_LOW) * 0.45;
  const inner = tip(midAngle, midLength * COVERTS_REACH);
  const bow = tip((ANGLE_HIGH + midAngle) / 2, LEN_HIGH * 0.62);

  const s = new THREE.Shape();
  s.moveTo(fx(ROOT_X), fy(ROOT_Y));
  s.quadraticCurveTo(fx(bow.x), fy(bow.y), fx(top.x), fy(top.y));
  s.lineTo(fx(inner.x), fy(inner.y));
  s.closePath();
  return s;
}

export type Icarus = {
  group: THREE.Group;
  update: (t: number) => void;
  dispose: () => void;
};

export function buildIcarus(): Icarus {
  const group = new THREE.Group();
  const disposables: Array<{ dispose: () => void }> = [];

  const extrude = (shape: THREE.Shape, depth: number) => {
    const g = new THREE.ExtrudeGeometry(shape, {
      depth,
      bevelEnabled: true,
      bevelThickness: 0.35,
      bevelSize: 0.28,
      bevelSegments: 2,
      curveSegments: 14,
    });
    g.center();
    disposables.push(g);
    return g;
  };

  // Wax and feather: warm metal that catches the one light, dark where it does
  // not. Emissive is low on purpose -- this is a body in a room, not a neon.
  const feather = new THREE.MeshStandardMaterial({
    color: 0xd8c9a8, metalness: 0.62, roughness: 0.34,
    emissive: 0x3a2d16, emissiveIntensity: 0.5,
  });
  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0xe8e2d4, metalness: 0.5, roughness: 0.42,
  });
  disposables.push(feather, bodyMat);

  const wingPivots: THREE.Group[] = [];
  const featherPivots: THREE.Group[][] = [];

  for (const side of [1, -1] as const) {
    const wing = new THREE.Group();
    wing.scale.x = side;                       // one wing defined, one mirrored
    const perFeather: THREE.Group[] = [];

    for (let i = 0; i < FEATHERS; i++) {
      const t = i / (FEATHERS - 1);
      const shape = featherShape(i);
      // Each feather hangs off its own pivot at the shoulder, so the flap can
      // travel outward instead of the wing moving as one slab.
      const pivot = new THREE.Group();
      const mesh = new THREE.Mesh(extrude(shape, 0.9 + t * 0.5), feather);
      const angle = ANGLE_LOW + (ANGLE_HIGH - ANGLE_LOW) * t;
      const length = LEN_LOW + (LEN_HIGH - LEN_LOW) * t;
      const r = (angle * Math.PI) / 180;
      mesh.position.set(Math.cos(r) * length * 0.5, Math.sin(r) * length * 0.5, t * 0.5);
      pivot.add(mesh);
      wing.add(pivot);
      perFeather.push(pivot);
    }

    const coverts = new THREE.Mesh(extrude(covertsShape(), 1.4), feather);
    coverts.position.set(16, 7, 0);
    wing.add(coverts);

    group.add(wing);
    wingPivots.push(wing);
    featherPivots.push(perFeather);
  }

  // ---- the figure ---------------------------------------------------------
  // In the 2D mark the body is a downward V, and it stays that way in the
  // header, the Dock icon and the favicon -- that is the logo and it does not
  // change. Here there is depth to use, so it becomes an actual figure: the
  // man wearing the wings, not a wedge standing in for him.
  const figure = new THREE.Group();

  const torso = new THREE.Mesh(
    new THREE.CapsuleGeometry(2.0, 6.2, 6, 16), bodyMat,
  );
  torso.position.y = -6.0;
  figure.add(torso);

  const head = new THREE.Mesh(new THREE.SphereGeometry(2.05, 20, 16), bodyMat);
  head.position.y = -0.6;
  figure.add(head);

  // Legs trail rather than hang: he is climbing, and a vertical pair reads as
  // someone standing in mid-air.
  for (const side of [-1, 1] as const) {
    const leg = new THREE.Mesh(new THREE.CapsuleGeometry(0.95, 7.4, 5, 12), bodyMat);
    leg.position.set(side * 1.15, -13.0, -0.8);
    leg.rotation.x = 0.34;
    leg.rotation.z = side * 0.07;
    figure.add(leg);
  }

  // Arms swept back into the wing roots, so the wings read as worn.
  for (const side of [-1, 1] as const) {
    const arm = new THREE.Mesh(new THREE.CapsuleGeometry(0.8, 5.6, 5, 12), bodyMat);
    arm.position.set(side * 3.0, -3.4, 0.2);
    arm.rotation.z = side * 0.95;
    figure.add(arm);
  }

  const figureMeshes = figure.children as THREE.Mesh[];
  figureMeshes.forEach((m) => { m.castShadow = false; });
  group.add(figure);
  const bodyPivot = figure;

  // 0..100 box down to something that sits sensibly beside a unit-ball graph
  group.scale.setScalar(0.026);

  const update = (t: number) => {
    // One slow wingbeat. The ratio matters more than the numbers: the downstroke
    // is quicker than the recovery, which is what stops it reading as a metronome.
    const beat = Math.sin(t * 1.15);
    const drive = beat > 0 ? beat : beat * 0.62;

    wingPivots.forEach((wing, w) => {
      const side = w === 0 ? 1 : -1;
      wing.rotation.x = drive * 0.42;
      wing.rotation.z = side * drive * 0.08;
      featherPivots[w].forEach((p, i) => {
        // outer feathers lag, so the stroke ripples along the wing
        const lag = (i / (FEATHERS - 1)) * 0.55;
        p.rotation.x = Math.sin(t * 1.15 - lag) * 0.20 * (0.35 + i / FEATHERS);
      });
    });

    // The body answers the stroke a beat late, the way a swimmer's hips do.
    bodyPivot.rotation.x = -0.10 + drive * 0.07;
    bodyPivot.position.y = drive * 0.5;

    // Rising, banking, never quite level. He is going up; that is the story.
    group.position.y = Math.sin(t * 0.42) * 0.12 + 0.06;
    group.rotation.z = Math.sin(t * 0.31) * 0.09;
    group.rotation.y = -0.34 + Math.sin(t * 0.23) * 0.14;
  };

  return {
    group,
    update,
    dispose: () => disposables.forEach((d) => d.dispose()),
  };
}
