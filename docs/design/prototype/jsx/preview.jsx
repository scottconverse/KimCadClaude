// preview.jsx — Three.js print-aware blueprint viewport.

// ── Imperative controller ────────────────────────────────────────────────────
class KCViewport {
  constructor(container, canvas, labels, opts) {
    this.container = container;
    this.canvas = canvas;
    this.labels = labels; // {x, y, z} dom nodes
    this.opts = opts || {};
    this.params = Object.assign({}, KC_DEFAULT_PARAMS);
    this.holes = [];
    this.style = 'blueprint';
    this.accent = '#c8623a';
    this.bg = '#14171c';
    this.gridColor = 'rgba(255,255,255,0.1)';
    this._theta = -0.7;     // azimuth
    this._phi = 1.15;       // polar
    this._radius = 460;
    this._autoRotate = true;
    this._dragging = false;
    this._marker = null;
    this._initThree();
    this._bind();
    this._loop = this._loop.bind(this);
    this._raf = requestAnimationFrame(this._loop);
  }

  _initThree() {
    const THREE = window.THREE;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, 1, 1, 5000);
    this.camera.up.set(0, 0, 1);
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // lights (for solid / hologram)
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const d1 = new THREE.DirectionalLight(0xffffff, 0.9); d1.position.set(180, -260, 420); this.scene.add(d1);
    const d2 = new THREE.DirectionalLight(0x88aaff, 0.35); d2.position.set(-220, 160, 120); this.scene.add(d2);

    this.modelGroup = new THREE.Group();
    this.scene.add(this.modelGroup);

    this.bboxGroup = new THREE.Group();
    this.scene.add(this.bboxGroup);

    this._buildPlate();
    this.rebuild();
    this._resize();
  }

  _buildPlate() {
    const THREE = window.THREE;
    const [vx, vy] = KC_PRINTER.volume;
    if (this.grid) this.scene.remove(this.grid);
    const grid = new THREE.GridHelper(vx, 16, 0xffffff, 0xffffff);
    grid.rotation.x = Math.PI / 2; // to XY plane (Z up)
    grid.material.transparent = true;
    grid.material.opacity = 0.10;
    this.grid = grid;
    this.scene.add(grid);
    // plate border
    const half = vx / 2;
    const pts = [[-half,-half],[half,-half],[half,half],[-half,half],[-half,-half]]
      .map(([x,y]) => new THREE.Vector3(x, y, 0));
    const bg = new THREE.BufferGeometry().setFromPoints(pts);
    if (this.plateBorder) this.scene.remove(this.plateBorder);
    this.plateBorder = new THREE.Line(bg, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.22 }));
    this.scene.add(this.plateBorder);
  }

  // build a triangular-prism geometry (gusset) along X
  _prismGeometry(hw, profile) {
    const THREE = window.THREE;
    const [a, b, c] = profile; // each [y,z]
    const v = [];
    for (const x of [-hw, hw]) for (const [y, z] of [a, b, c]) v.push(x, y, z);
    const pos = new Float32Array(v);
    const idx = [
      0,1,2, 5,4,3,            // caps
      0,3,4, 0,4,1,            // side a-b
      1,4,5, 1,5,2,            // side b-c
      2,5,3, 2,3,0,            // side c-a
    ];
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    g.setIndex(idx);
    g.computeVertexNormals();
    return g;
  }

  rebuild() {
    const THREE = window.THREE;
    const p = this.params;
    // clear
    while (this.modelGroup.children.length) {
      const ch = this.modelGroup.children.pop();
      ch.geometry && ch.geometry.dispose && ch.geometry.dispose();
    }
    const armZ = p.plate_height * 0.62;
    const parts = [];
    // back plate
    const plate = new THREE.BoxGeometry(p.plate_width, p.wall_thickness, p.plate_height);
    plate.translate(0, p.wall_thickness / 2, p.plate_height / 2);
    parts.push({ g: plate, kind: 'plate' });
    // spool arm (cylinder along Y)
    const arm = new THREE.CylinderGeometry(p.arm_radius, p.arm_radius, p.arm_length, 40);
    arm.translate(0, p.wall_thickness + p.arm_length / 2, armZ);
    parts.push({ g: arm, kind: 'arm' });
    // end cap lip on arm
    const lip = new THREE.CylinderGeometry(p.arm_radius * 1.28, p.arm_radius * 1.28, p.wall_thickness * 1.6, 40);
    lip.translate(0, p.wall_thickness + p.arm_length - p.wall_thickness, armZ);
    parts.push({ g: lip, kind: 'arm' });
    // gusset
    const gH = p.plate_height * 0.30, gD = p.arm_length * 0.6;
    const gus = this._prismGeometry(p.wall_thickness / 2, [
      [p.wall_thickness, armZ],
      [p.wall_thickness, armZ - gH],
      [p.wall_thickness + gD, armZ - gH * 0.18],
    ]);
    parts.push({ g: gus, kind: 'plate' });

    const accent = new THREE.Color(this.accent);
    const isBlue = this.style === 'blueprint';
    const isHolo = this.style === 'hologram';

    for (const { g } of parts) {
      if (isBlue) {
        const e = new THREE.EdgesGeometry(g, 22);
        const line = new THREE.LineSegments(e, new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0.92 }));
        this.modelGroup.add(line);
        // faint surface
        const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.06 }));
        this.modelGroup.add(m);
      } else if (isHolo) {
        const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: accent, transparent: true, opacity: 0.22, metalness: 0.1, roughness: 0.5, side: THREE.DoubleSide }));
        this.modelGroup.add(m);
        const e = new THREE.EdgesGeometry(g, 22);
        this.modelGroup.add(new THREE.LineSegments(e, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.75 })));
      } else { // solid
        const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: accent, metalness: 0.08, roughness: 0.62 }));
        this.modelGroup.add(m);
        const e = new THREE.EdgesGeometry(g, 30);
        this.modelGroup.add(new THREE.LineSegments(e, new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.18 })));
      }
    }

    // holes (outlines on plate front face)
    const allHoles = this._holePositions();
    for (const h of allHoles) this._addHole(h, isBlue);

    this._buildBBox();
    this._pickTarget = this.modelGroup.children.find(c => c.geometry && c.geometry.type === 'BoxGeometry') || this.modelGroup.children[0];
    this._renderOnce();
  }

  _holePositions() {
    const p = this.params;
    const base = [
      { x: -p.plate_width * 0.26, z: p.plate_height * 0.86 },
      { x: p.plate_width * 0.26, z: p.plate_height * 0.86 },
    ];
    return base.concat(this.holes);
  }

  _addHole(h, isBlue) {
    const THREE = window.THREE;
    const p = this.params;
    const r = p.hole_diameter / 2;
    const segs = 28;
    const pts = [];
    for (let i = 0; i <= segs; i++) {
      const a = (i / segs) * Math.PI * 2;
      pts.push(new THREE.Vector3(h.x + Math.cos(a) * r, p.wall_thickness + 0.4, h.z + Math.sin(a) * r));
    }
    const g = new THREE.BufferGeometry().setFromPoints(pts);
    const col = isBlue ? new THREE.Color(this.accent) : new THREE.Color(0xffffff);
    const line = new THREE.LineLoop(g, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.95 }));
    this.modelGroup.add(line);
    // counterbore ring
    const pts2 = pts.map(v => new THREE.Vector3((v.x - h.x) * 1.7 + h.x, v.y, (v.z - h.z) * 1.7 + h.z));
    const g2 = new THREE.BufferGeometry().setFromPoints(pts2);
    this.modelGroup.add(new THREE.LineLoop(g2, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.4 })));
  }

  _buildBBox() {
    const THREE = window.THREE;
    while (this.bboxGroup.children.length) {
      const ch = this.bboxGroup.children.pop();
      ch.geometry && ch.geometry.dispose();
    }
    const box = new THREE.Box3().setFromObject(this.modelGroup);
    this._box = box;
    const min = box.min, max = box.max;
    const c = [
      [min.x,min.y,min.z],[max.x,min.y,min.z],[max.x,max.y,min.z],[min.x,max.y,min.z],
      [min.x,min.y,max.z],[max.x,min.y,max.z],[max.x,max.y,max.z],[min.x,max.y,max.z],
    ];
    const E = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    const verts = [];
    for (const [a,b] of E) { verts.push(...c[a], ...c[b]); }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
    const col = new THREE.Color(0xffffff);
    this.bboxGroup.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.28 })));
    // store label anchor points (edge midpoints near front-bottom)
    this._labelAnchors = {
      x: new THREE.Vector3((min.x+max.x)/2, min.y, min.z),
      y: new THREE.Vector3(max.x, (min.y+max.y)/2, min.z),
      z: new THREE.Vector3(min.x, min.y, (min.z+max.z)/2),
    };
    this._center = new THREE.Vector3((min.x+max.x)/2, (min.y+max.y)/2, (min.z+max.z)/2);
  }

  _updateLabels() {
    if (!this._labelAnchors) return;
    const w = this.container.clientWidth, h = this.container.clientHeight;
    const bbox = kcBBox(this.params);
    const dims = { x: bbox.x, y: bbox.y, z: bbox.z };
    for (const k of ['x','y','z']) {
      const el = this.labels[k];
      if (!el) continue;
      const v = this._labelAnchors[k].clone().project(this.camera);
      const sx = (v.x * 0.5 + 0.5) * w;
      const sy = (-v.y * 0.5 + 0.5) * h;
      const off = k === 'z' ? -34 : (k === 'x' ? 0 : 26);
      const offy = k === 'z' ? 0 : 22;
      el.style.transform = `translate(-50%,-50%) translate(${sx + off}px, ${sy + offy}px)`;
      el.style.opacity = v.z < 1 ? 1 : 0;
      el.querySelector('[data-v]').textContent = `${dims[k]} mm`;
    }
  }

  _resize() {
    const w = this.container.clientWidth, h = this.container.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this._renderOnce();
  }

  _positionCamera() {
    const r = this._radius, t = this._theta, ph = this._phi;
    const cx = this._center ? this._center.x : 0;
    const cy = this._center ? this._center.y : 40;
    const cz = this._center ? this._center.z : 80;
    this.camera.position.set(
      cx + r * Math.sin(ph) * Math.cos(t),
      cy + r * Math.sin(ph) * Math.sin(t),
      cz + r * Math.cos(ph)
    );
    this.camera.lookAt(cx, cy, cz);
  }

  _renderOnce() {
    if (!this.renderer) return;
    this._positionCamera();
    this.renderer.render(this.scene, this.camera);
    this._updateLabels();
  }

  _loop() {
    this._raf = requestAnimationFrame(this._loop);
    if (this._autoRotate && !this._dragging) this._theta += 0.0026;
    this._renderOnce();
  }

  _bind() {
    this._onResize = () => this._resize();
    window.addEventListener('resize', this._onResize);
    if (typeof ResizeObserver !== 'undefined') {
      this._ro = new ResizeObserver(() => this._resize());
      this._ro.observe(this.container);
    }
    const c = this.canvas;
    let px = 0, py = 0, moved = 0;
    const down = (e) => {
      this._dragging = true; this._autoRotate = false; moved = 0;
      px = e.clientX; py = e.clientY;
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    };
    const move = (e) => {
      const dx = e.clientX - px, dy = e.clientY - py;
      px = e.clientX; py = e.clientY; moved += Math.abs(dx) + Math.abs(dy);
      this._theta -= dx * 0.01;
      this._phi = Math.max(0.25, Math.min(Math.PI - 0.15, this._phi - dy * 0.008));
      this._renderOnce();
    };
    const up = (e) => {
      this._dragging = false;
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      if (moved < 5) this._tryPick(e);
      clearTimeout(this._idleT);
      this._idleT = setTimeout(() => { this._autoRotate = true; }, 4000);
    };
    c.addEventListener('pointerdown', down);
    const wheel = (e) => {
      e.preventDefault();
      this._radius = Math.max(220, Math.min(900, this._radius + e.deltaY * 0.4));
      this._renderOnce();
    };
    c.addEventListener('wheel', wheel, { passive: false });
    this._unbind = () => {
      window.removeEventListener('resize', this._onResize);
      this._ro && this._ro.disconnect();
      c.removeEventListener('pointerdown', down);
      c.removeEventListener('wheel', wheel);
    };
  }

  _tryPick(e) {
    if (!this.opts.pickMode || !this._pickTarget) return;
    const THREE = window.THREE;
    const r = this.canvas.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((e.clientX - r.left) / r.width) * 2 - 1,
      -((e.clientY - r.top) / r.height) * 2 + 1
    );
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, this.camera);
    const meshes = this.modelGroup.children.filter(c => c.isMesh);
    const hits = ray.intersectObjects(meshes, false);
    if (hits.length) {
      const pt = hits[0].point;
      this._setMarker(pt);
      this.opts.onPick && this.opts.onPick({ x: +pt.x.toFixed(0), y: +pt.y.toFixed(0), z: +pt.z.toFixed(0) });
    }
  }

  _setMarker(pt) {
    const THREE = window.THREE;
    if (this._marker) this.scene.remove(this._marker);
    const grp = new THREE.Group();
    const dot = new THREE.Mesh(new THREE.SphereGeometry(2.4, 16, 16), new THREE.MeshBasicMaterial({ color: 0xffffff }));
    dot.position.copy(pt); grp.add(dot);
    const ringPts = [];
    for (let i = 0; i <= 32; i++) { const a = i/32*Math.PI*2; ringPts.push(new THREE.Vector3(pt.x+Math.cos(a)*6, pt.y+0.3, pt.z+Math.sin(a)*6)); }
    grp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(ringPts), new THREE.LineBasicMaterial({ color: 0xffffff })));
    this._marker = grp;
    this.scene.add(grp);
  }
  clearMarker() { if (this._marker) { this.scene.remove(this._marker); this._marker = null; } }

  setParams(p) { this.params = Object.assign({}, p); this.rebuild(); }
  setHoles(holes) { this.holes = holes || []; this.rebuild(); }
  setStyle(s) { this.style = s; this.rebuild(); }
  setAccent(a) { this.accent = a; this.rebuild(); }
  setPickMode(on) { this.opts.pickMode = on; }
  resetView() { this._theta = -0.7; this._phi = 1.15; this._radius = 460; this._autoRotate = true; }

  dispose() {
    cancelAnimationFrame(this._raf);
    this._unbind && this._unbind();
    this.renderer.dispose();
  }
}

// ── React wrapper ─────────────────────────────────────────────────────────────
function Preview({ params, holes, style, accent, pickMode, onPick, density }) {
  const wrapRef = React.useRef(null);
  const canvasRef = React.useRef(null);
  const lx = React.useRef(null), ly = React.useRef(null), lz = React.useRef(null);
  const vpRef = React.useRef(null);

  React.useEffect(() => {
    const vp = new KCViewport(wrapRef.current, canvasRef.current,
      { x: lx.current, y: ly.current, z: lz.current }, { pickMode, onPick });
    vpRef.current = vp;
    return () => vp.dispose();
  }, []);

  React.useEffect(() => { vpRef.current && vpRef.current.setParams(params); }, [params]);
  React.useEffect(() => { vpRef.current && vpRef.current.setHoles(holes); }, [holes]);
  React.useEffect(() => { vpRef.current && vpRef.current.setStyle(style); }, [style]);
  React.useEffect(() => { vpRef.current && vpRef.current.setAccent(accent); }, [accent]);
  React.useEffect(() => { vpRef.current && (vpRef.current.opts.pickMode = pickMode, vpRef.current.opts.onPick = onPick); }, [pickMode, onPick]);

  const labelStyle = {
    position: 'absolute', top: 0, left: 0, pointerEvents: 'none',
    fontFamily: KC_MONO, fontSize: 11, fontWeight: 600, letterSpacing: '0.02em',
    color: 'rgba(255,255,255,0.92)', whiteSpace: 'nowrap',
    background: 'rgba(0,0,0,0.45)', padding: '2px 7px', borderRadius: 5,
    border: '0.5px solid rgba(255,255,255,0.18)', backdropFilter: 'blur(4px)',
  };
  return (
    <div ref={wrapRef} style={{ position: 'absolute', inset: 0, cursor: pickMode ? 'crosshair' : 'grab' }}>
      <canvas ref={canvasRef} style={{ width: '100%', height: '100%', display: 'block', touchAction: 'none' }} />
      <div ref={lx} style={labelStyle}><span style={{ opacity: 0.5 }}>W </span><span data-v></span></div>
      <div ref={ly} style={labelStyle}><span style={{ opacity: 0.5 }}>D </span><span data-v></span></div>
      <div ref={lz} style={labelStyle}><span style={{ opacity: 0.5 }}>H </span><span data-v></span></div>
    </div>
  );
}

Object.assign(window, { KCViewport, Preview });
