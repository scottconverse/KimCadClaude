// data.jsx — design tokens, demo content, and the reactive engineering logic.

// ── Design directions ────────────────────────────────────────────────────────
// Each direction sets a coherent surface palette. Accent is a separate tweak so
// it can be mixed; defaults below seed the matching accent.
const KC_DIRECTIONS = {
  workshop: {
    label: 'Workshop',
    accent: '#c8623a',
    vars: {
      '--bg': '#f0ebe0',
      '--surface': '#faf6ee',
      '--surface-2': '#f4eee2',
      '--ink': '#272219',
      '--muted': '#6f6857',
      '--hair': 'rgba(39,34,25,0.10)',
      '--hair-strong': 'rgba(39,34,25,0.16)',
      '--viewport-bg': '#14171c',
      '--viewport-grid': 'rgba(255,255,255,0.10)',
    },
  },
  studio: {
    label: 'Studio',
    accent: '#4b59d6',
    vars: {
      '--bg': '#e9ecf1',
      '--surface': '#ffffff',
      '--surface-2': '#f1f3f7',
      '--ink': '#1a1e27',
      '--muted': '#5b6473',
      '--hair': 'rgba(26,30,39,0.10)',
      '--hair-strong': 'rgba(26,30,39,0.16)',
      '--viewport-bg': '#10131a',
      '--viewport-grid': 'rgba(255,255,255,0.09)',
    },
  },
  daylight: {
    label: 'Daylight',
    accent: '#2f9e6a',
    vars: {
      '--bg': '#f4f3ee',
      '--surface': '#ffffff',
      '--surface-2': '#f3f2ec',
      '--ink': '#211f18',
      '--muted': '#6b6a60',
      '--hair': 'rgba(33,31,24,0.10)',
      '--hair-strong': 'rgba(33,31,24,0.16)',
      '--viewport-bg': '#121611',
      '--viewport-grid': 'rgba(255,255,255,0.09)',
    },
  },
};

const KC_FONTS = {
  bricolage: { label: 'Bricolage', display: '"Bricolage Grotesque", system-ui, sans-serif', body: '"Hanken Grotesk", system-ui, sans-serif' },
  grotesk: { label: 'Grotesk', display: '"Space Grotesk", system-ui, sans-serif', body: '"Hanken Grotesk", system-ui, sans-serif' },
};
const KC_MONO = '"JetBrains Mono", ui-monospace, monospace';

// density → spacing + type multipliers
const KC_DENSITY = {
  cozy: { pad: 1.18, gap: 1.18, font: 1.06, label: 'Cozy' },
  comfortable: { pad: 1.0, gap: 1.0, font: 1.0, label: 'Comfortable' },
  compact: { pad: 0.82, gap: 0.8, font: 0.94, label: 'Compact' },
};

const KC_ACCENT_OPTIONS = ['#c8623a', '#4b59d6', '#2f9e6a', '#b8902a', '#9a4bd6'];

// ── Demo object: parametric wall-mounted spool holder ────────────────────────
const KC_DEFAULT_PARAMS = {
  plate_width: 70,     // X
  plate_height: 150,   // Z (up)
  arm_length: 45,      // Y (depth, forward)
  arm_radius: 11,
  wall_thickness: 4,
  hole_diameter: 4,    // M4 default after clarification
  fillet: 3,
};

const KC_PARAM_DEFS = [
  { key: 'plate_width', label: 'Plate width', min: 50, max: 90, step: 1, unit: 'mm', axis: 'X' },
  { key: 'plate_height', label: 'Plate height', min: 90, max: 210, step: 1, unit: 'mm', axis: 'Z' },
  { key: 'arm_length', label: 'Arm reach', min: 30, max: 110, step: 1, unit: 'mm', axis: 'Y' },
  { key: 'arm_radius', label: 'Arm radius', min: 6, max: 18, step: 0.5, unit: 'mm' },
  { key: 'wall_thickness', label: 'Wall thickness', min: 2, max: 6, step: 0.1, unit: 'mm' },
  { key: 'hole_diameter', label: 'Screw hole Ø', min: 2.5, max: 6, step: 0.1, unit: 'mm' },
  { key: 'fillet', label: 'Corner fillet', min: 0, max: 8, step: 0.5, unit: 'mm' },
];

const KC_PRINTER = { name: 'Bambu Lab P1S', volume: [256, 256, 256], nozzle: 0.4 };
const KC_MATERIALS = ['PLA', 'PETG', 'TPU', 'ABS'];

// bounding box from params (mm)
function kcBBox(p) {
  return {
    x: p.plate_width,
    y: +(p.wall_thickness + p.arm_length).toFixed(1),
    z: p.plate_height,
  };
}

// rough printed volume → weight → time
function kcEstimate(p, infill = 20) {
  const plate = p.plate_width * p.plate_height * p.wall_thickness;
  const arm = Math.PI * p.arm_radius * p.arm_radius * p.arm_length;
  const gusset = 0.5 * p.arm_length * (p.plate_height * 0.42) * p.wall_thickness;
  const holes = 2 * Math.PI * (p.hole_diameter / 2) ** 2 * p.wall_thickness;
  const mm3 = Math.max(0, plate + arm + gusset - holes);
  const cm3 = mm3 / 1000;
  // shell-dominant: ~ (0.32 solid fraction baseline + infill contribution)
  const solidFrac = 0.30 + (infill / 100) * 0.55;
  const grams = cm3 * 1.24 * solidFrac;
  const minutes = grams * 3.0 + 6;
  return {
    cm3: +cm3.toFixed(1),
    grams: Math.round(grams),
    minutes: Math.round(minutes),
    timeStr: `${Math.floor(minutes / 60)} h ${String(Math.round(minutes % 60)).padStart(2, '0')} m`,
  };
}

// the reactive Printability Gate
function kcPrintability(p, extraHoles, printer) {
  const PR = printer || KC_PRINTER;
  const PR_NOZ = PR.nozzle || 0.4;
  const bbox = kcBBox(p);
  const checks = [];
  // dimensional assertion (always passes in-sim — we render to spec)
  checks.push({ id: 'dims', level: 'pass', label: 'Dimensions match plan',
    detail: `${bbox.x} × ${bbox.y} × ${bbox.z} mm` });
  // build volume
  const [vx, vy, vz] = PR.volume;
  if (bbox.x > vx || bbox.y > vy || bbox.z > vz) {
    checks.push({ id: 'vol', level: 'fail', label: 'Exceeds build volume',
      detail: `Larger than ${PR.name} (${vx}×${vy}×${vz} mm). Scale or split.` });
  } else {
    checks.push({ id: 'vol', level: 'pass', label: 'Fits the build plate',
      detail: `${PR.name} · ${vx}×${vy}×${vz} mm` });
  }
  // wall thickness vs nozzle
  if (p.wall_thickness < 3) {
    checks.push({ id: 'wall', level: 'warn', label: 'Thin wall',
      detail: `One ${p.wall_thickness.toFixed(1)} mm wall is below the 3 mm recommendation for a ${PR_NOZ} mm nozzle.` });
  } else {
    checks.push({ id: 'wall', level: 'pass', label: 'Wall thickness OK',
      detail: `${p.wall_thickness.toFixed(1)} mm · ${(p.wall_thickness / PR_NOZ).toFixed(1)}× nozzle` });
  }
  // overhang / orientation (the horizontal arm)
  checks.push({ id: 'support', level: 'warn', label: 'Supports likely under arm',
    detail: 'The horizontal arm overhangs. Print plate-down — orientation already applied.' });
  // hole tolerance
  if (p.hole_diameter < 3.2) {
    checks.push({ id: 'hole', level: 'warn', label: 'Tight screw clearance',
      detail: `${p.hole_diameter.toFixed(1)} mm hole leaves little clearance after shrinkage. M3 needs ≥ 3.4 mm.` });
  } else {
    checks.push({ id: 'hole', level: 'pass', label: 'Hole clearance OK',
      detail: `${p.hole_diameter.toFixed(1)} mm · clears with shrinkage` });
  }
  // bed contact
  checks.push({ id: 'bed', level: 'pass', label: 'Good first-layer adhesion',
    detail: `${(p.plate_width * p.wall_thickness / 100).toFixed(0)} cm² flat on bed` });

  const fails = checks.filter(c => c.level === 'fail').length;
  const warns = checks.filter(c => c.level === 'warn').length;
  const verdict = fails ? 'fail' : warns ? 'warn' : 'pass';
  const confidence = fails ? 'low' : warns > 1 ? 'medium' : 'high';
  return { checks, verdict, warns, fails, confidence };
}

// ── Conversational tone variants ─────────────────────────────────────────────
const KC_TONE = {
  friendly: {
    greeting: 'What do you want to make today?',
    sub: 'Describe it in plain words — I\'ll turn it into a print-ready model. No CAD needed.',
    thinking: 'Sketching out your design plan…',
    clarifyIntro: 'Quick question before I build this so it actually fits your hardware:',
    clarify: 'What size screws will you mount it with? Most filament holders use M3 or M4.',
    built: 'Here you go! I made a wall-mounted spool holder. Have a look — you can drag to spin it, nudge any dimension on the right, or just tell me what to change.',
    wider: 'Widened the plate for you. The build plate fit still looks good.',
    thicker: 'Beefed up the walls. That clears the thin-wall warning nicely.',
    holeAdded: 'Added a screw hole right where you pointed. Three mounting points now.',
    sliced: 'All sliced and ready! Here\'s your print report — download the file whenever you\'re set.',
  },
  concise: {
    greeting: 'Describe what to make.',
    sub: 'Plain English in, print-ready model out.',
    thinking: 'Generating design plan…',
    clarifyIntro: 'One input needed:',
    clarify: 'Screw size for the mount — M3 or M4?',
    built: 'Wall-mounted spool holder generated. Drag to rotate. Adjust parameters at right.',
    wider: 'Plate widened. Still fits the plate.',
    thicker: 'Walls thickened. Thin-wall warning cleared.',
    holeAdded: 'Screw hole added at clicked point.',
    sliced: 'Sliced. Report below. Download when ready.',
  },
  expert: {
    greeting: 'Specify the part to generate.',
    sub: 'Text → parametric OpenSCAD → validated, sliced output.',
    thinking: 'Composing Design-Plan IR → OpenSCAD…',
    clarifyIntro: 'Missing a load-bearing dimension:',
    clarify: 'Fastener spec for the mounting bosses — M3 (3.4 mm clearance) or M4 (4.5 mm)?',
    built: 'Generated: wall-mounted spool holder. Parameters hoisted; geometry manifold by construction. Orbit to inspect; edit params or refine conversationally.',
    wider: 'plate_width increased. Bounding box re-asserted within build volume.',
    thicker: 'wall_thickness increased above nozzle×7.5; printability gate clears.',
    holeAdded: 'Boss + clearance hole inserted at raycast point.',
    sliced: 'OrcaSlicer pass complete. Print report + 3MF emitted.',
  },
};

const KC_EXAMPLES = [
  'A wall-mounted holder for a spool of filament',
  'An L-bracket with two M4 mounting holes',
  'A box with a snap-fit lid, 80×60×40 mm',
  'A pegboard hook for headphones',
];

// the OpenSCAD that the "model writes" (display only)
function kcOpenSCAD(p, extraHoles) {
  return `// KimCad — wall-mounted spool holder
// units: millimeters · manifold by construction

plate_width    = ${p.plate_width};   // X
plate_height   = ${p.plate_height};  // Z
arm_length     = ${p.arm_length};    // Y reach
arm_radius     = ${p.arm_radius};
wall_thickness = ${p.wall_thickness};
hole_diameter  = ${p.hole_diameter}; // M${p.hole_diameter < 3.5 ? 3 : 4} clearance
fillet         = ${p.fillet};

use <library/fasteners.scad>;
use <library/fillet.scad>;

module back_plate() {
  rounded_plate(plate_width, plate_height, wall_thickness, fillet);
}
module spool_arm() {
  rotate([90,0,0]) cylinder(h=arm_length, r=arm_radius, $fn=64);
}
difference() {
  union() {
    back_plate();
    translate([0, 0, plate_height*0.62]) spool_arm();
    gusset(arm_length, plate_height*0.42, wall_thickness);
  }
  // mounting holes (M${p.hole_diameter < 3.5 ? 3 : 4})
  screw_holes(plate_width, plate_height, hole_diameter);${extraHoles && extraHoles.length ? `
  // + ${extraHoles.length} hole(s) placed by click-to-point` : ''}
}`;
}

// ── v3.0: Model strategy (§7) ─────────────────────────────────────────────────
const KC_MODELS = {
  qwen:  { id: 'qwen',  name: 'Qwen2.5-Coder', size: '1.5B', tag: 'Fast · Local',
           desc: 'Default. Schema-constrained JSON in ~15–20 s, fully offline.', loc: 'local', dot: '#2f9e6a' },
  gemma: { id: 'gemma', name: 'Gemma 4 E4B', size: '~4B', tag: 'Non-China · Local',
           desc: 'Proven alternative from Google. Also powers photo input offline.', loc: 'local', dot: '#2f9e6a' },
  cloud: { id: 'cloud', name: 'OpenRouter', size: 'Cloud', tag: '300+ models',
           desc: 'Fastest drafts & vision. Sends your prompt off-device.', loc: 'cloud', dot: '#c9962f' },
};

// ── v3.0: Smart Mesh readiness + learning (§6.12) ─────────────────────────────
const KC_FIX = {
  wall:   'Raise wall thickness to ≥ 3 mm (slider at right).',
  hole:   'Widen the screw hole or switch to a press-fit insert.',
  support:'Keep the auto-orientation — supports stay only under the arm.',
  vol:    'Scale down or split the model to fit the build plate.',
};
// pretend learning store: prior prints of this object family
const KC_HISTORY = {
  family: 'wall-mounted spool holder',
  total: 14, succeeded: 13,
  note: 'Most failures were thin-wall arms under 2.6 mm.',
};

function kcSmartMesh(params, gate, material) {
  let score = 100;
  gate.checks.forEach((c) => { if (c.level === 'warn') score -= 9; if (c.level === 'fail') score -= 42; });
  if (params.wall_thickness < 2.6) score -= 6;
  if (material === 'TPU') score -= 4;
  score = Math.max(8, Math.min(99, Math.round(score)));
  const band = score >= 88 ? { label: 'Ready to print', tone: 'pass' }
    : score >= 70 ? { label: 'Likely to succeed', tone: 'pass' }
    : score >= 52 ? { label: 'Print with care', tone: 'warn' }
    : { label: 'Not print-ready', tone: 'fail' };
  const risks = gate.checks.filter((c) => c.level !== 'pass')
    .map((c) => ({ label: c.label, level: c.level, fix: KC_FIX[c.id] || c.detail }));
  const recs = [];
  if (params.wall_thickness < 3) recs.push('Thicken walls to 3 mm for a stronger mount.');
  recs.push(`Print in ${material} at 20% infill — matches the strongest runs in this family.`);
  recs.push('Brim on; first layer 0.2 mm for a clean base.');
  // historical percentile from score
  const pct = Math.max(8, Math.min(96, Math.round(score - 4)));
  const rate = Math.round((KC_HISTORY.succeeded / KC_HISTORY.total) * 100);
  return {
    score, band,
    confidence: gate.confidence,
    risks, recs,
    history: { ...KC_HISTORY, rate, percentile: pct },
  };
}

// ── v3.0: Image on-ramp — extracted DesignPlan from a photo (§5.3, §6.10) ──────
const KC_PHOTO_PLAN = {
  object_type: 'Wall-mounted spool holder',
  confidence: 0.86,
  fields: [
    { key: 'plate_width', label: 'Back-plate width', value: 70, unit: 'mm', conf: 'high' },
    { key: 'plate_height', label: 'Back-plate height', value: 150, unit: 'mm', conf: 'high' },
    { key: 'arm_length', label: 'Arm reach', value: 45, unit: 'mm', conf: 'medium' },
    { key: 'hole_diameter', label: 'Mounting holes', value: 4, unit: 'mm', conf: 'low' },
  ],
  features: ['2 mounting holes detected', 'Horizontal spool arm', 'Triangular gusset'],
  notes: 'Arm appears snapped near the base — KimCad will rebuild it solid.',
};

// ── v3.0: Printer execution status (§6.11) ────────────────────────────────────
const KC_PRINTER_STATUS = {
  state: 'Idle · ready',
  nozzle: 27, nozzleTarget: 0,
  bed: 25, bedTarget: 0,
  freeVolume: true,
  ams: 'PLA · Matte Charcoal · 78%',
  connection: 'LAN · Developer Mode',
};

// ── v3.0: First-run wizard data (§5.1, §6.9) ──────────────────────────────────
const KC_PRINTER_PROFILES = {
  bambu:    { maker: 'Bambu Lab', conn: 'bambu', models: [
                { name: 'Bambu Lab P1S', volume: [256, 256, 256] },
                { name: 'Bambu Lab X1 Carbon', volume: [256, 256, 256] },
                { name: 'Bambu Lab A1', volume: [256, 256, 256] },
                { name: 'Bambu Lab A1 mini', volume: [180, 180, 180] } ] },
  creality: { maker: 'Creality', conn: 'octo', models: [
                { name: 'Ender-3 V3', volume: [220, 220, 250] },
                { name: 'Creality K1', volume: [220, 220, 250] },
                { name: 'Creality K1 Max', volume: [300, 300, 300] } ] },
  prusa:    { maker: 'Prusa', conn: 'prusalink', models: [
                { name: 'Prusa MK4', volume: [250, 210, 220] },
                { name: 'Prusa MINI+', volume: [180, 180, 180] },
                { name: 'Prusa XL', volume: [360, 360, 360] } ] },
  elegoo:   { maker: 'Elegoo', conn: 'octo', models: [
                { name: 'Neptune 4', volume: [225, 225, 265] },
                { name: 'Neptune 4 Pro', volume: [225, 225, 265] } ] },
  anycubic: { maker: 'Anycubic', conn: 'octo', models: [
                { name: 'Kobra 2', volume: [220, 220, 250] },
                { name: 'Kobra 3', volume: [250, 250, 260] } ] },
};
const KC_CONN_INFO = {
  bambu:     { label: 'LAN · Developer Mode', fields: [
                 { key: 'ip', label: 'Printer IP', ph: '192.168.1.42' },
                 { key: 'code', label: 'Access code', ph: '8-digit code from the screen' } ],
               note: 'Bambu LAN control needs Developer Mode + the access code (this disables cloud). KimCad walks you through enabling it.' },
  octo:      { label: 'OctoPrint / Moonraker', fields: [
                 { key: 'url', label: 'Server URL', ph: 'http://octopi.local' },
                 { key: 'key', label: 'API key', ph: 'OctoPrint API key' } ],
               note: 'Point KimCad at your OctoPrint or Moonraker instance on the local network.' },
  prusalink: { label: 'PrusaLink', fields: [
                 { key: 'ip', label: 'Printer IP', ph: '192.168.1.50' },
                 { key: 'pw', label: 'Password', ph: 'PrusaLink password' } ],
               note: 'PrusaLink uses Digest auth — the password is on the setup sheet or shown on the printer.' },
};
const KC_BUNDLE = ['App', 'OpenSCAD', 'OrcaSlicer', 'Qwen2.5-Coder', 'PrintProof3D', 'CadQuery'];
const KC_CHECKSUM = 'a3f9 2c71 e840 5bd6 … 9f12';

Object.assign(window, {
  KC_DIRECTIONS, KC_FONTS, KC_MONO, KC_DENSITY, KC_ACCENT_OPTIONS,
  KC_DEFAULT_PARAMS, KC_PARAM_DEFS, KC_PRINTER, KC_MATERIALS,
  KC_TONE, KC_EXAMPLES,
  KC_MODELS, KC_FIX, KC_HISTORY, KC_PHOTO_PLAN, KC_PRINTER_STATUS,
  KC_PRINTER_PROFILES, KC_CONN_INFO, KC_BUNDLE, KC_CHECKSUM,
  kcBBox, kcEstimate, kcPrintability, kcOpenSCAD, kcSmartMesh,
});
