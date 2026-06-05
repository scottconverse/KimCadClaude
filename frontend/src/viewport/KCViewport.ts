import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

// KCViewport — a vanilla Three.js viewport for KimCad (Stage 4).
//
// Loads the REAL rendered part — the pipeline exports `*.oriented.stl`, the server serves it at
// GET /api/mesh/<id>, and this loads it with three's STLLoader. Framework-free (no react-three-
// fiber); driven from a thin React wrapper (Viewport.tsx). Units are millimetres (KimCad's mesh
// space); Z is up (build-plate orientation). Print-aware affordances: a bounding box + projected
// X/Y/Z dimension labels (so the centerpiece reads as an instrumented preview, not a decoration).

const VIEWPORT_BG = 0x14171c // Workshop dark viewport
const ACCENT = 0xc8623a // Workshop terracotta
const PLATE = 0xffffff

export interface DimLabels {
  x: HTMLElement
  y: HTMLElement
  z: HTMLElement
}

export interface Dimensions {
  x: number
  y: number
  z: number
}

// Slice 8: a printability/readiness problem to show ON the model. `geometry` is the sanitized
// shape PrintProof3D returns (coords in the same mm space as the loaded STL).
export type HLGeometry =
  | { type: 'point'; x: number; y: number; z: number }
  | { type: 'bounding_box'; min_x: number; min_y: number; min_z: number; max_x: number; max_y: number; max_z: number }
  | { type: 'triangles'; triangles: Array<{ v0: number[]; v1: number[]; v2: number[] }> }

export interface HighlightRisk {
  issueId: string
  tone: string // 'fail' | 'warn' — drives the highlight color
  geometry: HLGeometry
}

const HL_FAIL = 0xe5484d // red — a fail-tone problem region
const HL_WARN = 0xf5a623 // amber — a warn-tone problem region

function hlColor(tone: string): number {
  return tone === 'fail' ? HL_FAIL : HL_WARN
}

/** The net translation loadMesh bakes into the displayed mesh — center XY+Z, then sit on z=0 —
 * reduces to (-center.x, -center.y, -min.z) (the z-center cancels). Highlight geometry (in raw
 * STL mm coords) gets this same offset so it lines up exactly with the rendered part. Pure. */
export function meshDisplayOffset(bb: THREE.Box3): THREE.Vector3 {
  const c = bb.getCenter(new THREE.Vector3())
  return new THREE.Vector3(-c.x, -c.y, -bb.min.z)
}

/** Build the Three.js object for one problem highlight (triangles overlay / bbox wireframe /
 * point marker), translated by `offset` to align with the displayed mesh. Pure (no GL context),
 * so it's unit-testable. Returns null for an empty triangle set. */
export function buildHighlightObject(
  risk: HighlightRisk,
  offset: THREE.Vector3,
): THREE.Object3D | null {
  const color = hlColor(risk.tone)
  const g = risk.geometry
  if (g.type === 'triangles') {
    const pos: number[] = []
    for (const t of g.triangles) pos.push(...t.v0, ...t.v1, ...t.v2)
    if (pos.length === 0) return null
    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
    geom.translate(offset.x, offset.y, offset.z)
    geom.computeVertexNormals()
    return new THREE.Mesh(
      geom,
      new THREE.MeshBasicMaterial({
        color, transparent: true, opacity: 0.5, side: THREE.DoubleSide,
        depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
      }),
    )
  }
  if (g.type === 'bounding_box') {
    const min = new THREE.Vector3(g.min_x, g.min_y, g.min_z).add(offset)
    const max = new THREE.Vector3(g.max_x, g.max_y, g.max_z).add(offset)
    return new THREE.Box3Helper(new THREE.Box3(min, max), color)
  }
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(3, 16, 12),
    new THREE.MeshBasicMaterial({ color }),
  )
  sphere.position.set(g.x, g.y, g.z).add(offset)
  return sphere
}

export class KCViewport {
  private container: HTMLElement
  private renderer: THREE.WebGLRenderer
  private scene: THREE.Scene
  private camera: THREE.PerspectiveCamera
  private modelGroup: THREE.Group
  private target = new THREE.Vector3(0, 0, 0)
  private labels: DimLabels | null

  // Slice 8: problem highlights, in their own group so they don't get wiped by a mesh reload.
  // `meshOffset` mirrors the transform loadMesh bakes into the displayed mesh, so highlight
  // geometry (in raw STL mm coords) lines up exactly.
  private highlightGroup = new THREE.Group()
  private highlights: Array<{ issueId: string; object: THREE.Object3D }> = []
  private latestRisks: HighlightRisk[] = []
  private meshOffset = new THREE.Vector3(0, 0, 0)

  // Spherical camera (azimuth, polar, radius), auto-rotating when idle.
  private theta = -0.7
  private phi = 1.15
  private radius = 460
  private autoRotate = true
  private dragging = false
  private reduceMotion = false

  private dims: Dimensions | null = null
  private labelAnchors: { x: THREE.Vector3; y: THREE.Vector3; z: THREE.Vector3 } | null = null

  private raf = 0
  private disposed = false
  private resumeTimer = 0
  private ro?: ResizeObserver
  private cleanups: Array<() => void> = []
  private dragCleanup?: () => void
  private loadToken = 0

  constructor(container: HTMLElement, canvas: HTMLCanvasElement, labels: DimLabels | null = null) {
    this.container = container
    this.labels = labels
    // Respect the OS "reduce motion" setting — no perpetual auto-rotate for users who opt out.
    this.reduceMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (this.reduceMotion) this.autoRotate = false

    // preserveDrawingBuffer lets us read the canvas for a saved-design thumbnail
    // (captureThumbnail) at any time, not only synchronously inside a render. Negligible cost for
    // a single local CAD preview.
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    this.renderer.setClearColor(VIEWPORT_BG, 1)

    this.scene = new THREE.Scene()
    this.camera = new THREE.PerspectiveCamera(38, 1, 1, 8000)
    this.camera.up.set(0, 0, 1)

    this.scene.add(new THREE.AmbientLight(0xffffff, 0.6))
    const key = new THREE.DirectionalLight(0xffffff, 1.4)
    key.position.set(180, -260, 420)
    this.scene.add(key)
    const fill = new THREE.DirectionalLight(0x88aaff, 0.5)
    fill.position.set(-220, 160, 120)
    this.scene.add(fill)

    this.modelGroup = new THREE.Group()
    this.scene.add(this.modelGroup)
    this.scene.add(this.highlightGroup)

    this.buildPlate(256)
    this.bindInteractions(canvas)
    this.resize()
    this.loop = this.loop.bind(this)
    this.raf = requestAnimationFrame(this.loop)
  }

  /** Load and display the STL at `url`, replacing any current model and framing it. */
  async loadMesh(url: string): Promise<void> {
    const token = ++this.loadToken
    const geometry = await new STLLoader().loadAsync(url)
    if (this.disposed || token !== this.loadToken) {
      geometry.dispose()
      return
    }
    this.removeModelChildren()
    geometry.computeVertexNormals()
    // Capture the original bounds BEFORE centering so highlights can reproduce the exact display
    // transform. Net offset applied to an original vertex p is (-center0.x, -center0.y, -min0.z).
    geometry.computeBoundingBox()
    const bb0 = geometry.boundingBox
    this.meshOffset.copy(bb0 ? meshDisplayOffset(bb0) : new THREE.Vector3(0, 0, 0))
    geometry.center()
    geometry.computeBoundingBox()
    const bb = geometry.boundingBox
    if (bb) geometry.translate(0, 0, -bb.min.z) // sit the part on the plate (z = 0)

    const mesh = new THREE.Mesh(
      geometry,
      new THREE.MeshStandardMaterial({ color: ACCENT, metalness: 0.08, roughness: 0.62 }),
    )
    this.modelGroup.add(mesh)
    const edges = new THREE.EdgesGeometry(geometry, 28)
    this.modelGroup.add(
      new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.18 }),
      ),
    )
    this.buildBBoxAndDims()
    this.frameToModel()
    this._rebuildHighlights() // re-apply any pending problem highlights against the new transform
  }

  // ---- Slice 8: problem highlights -------------------------------------------

  /** Show problem regions on the model. Idempotent; safe to call before or after a mesh load
   * (highlights are (re)built against the current mesh transform). */
  setHighlights(risks: HighlightRisk[]): void {
    this.latestRisks = (risks || []).filter((r) => r && r.geometry && r.issueId)
    this._rebuildHighlights()
  }

  /** Toggle all highlights on/off without discarding them. */
  setHighlightsVisible(visible: boolean): void {
    this.highlightGroup.visible = visible
  }

  /** Frame the camera on one highlighted problem (click-to-focus from the readiness card). */
  focusHighlight(issueId: string): void {
    const hit = this.highlights.find((h) => h.issueId === issueId)
    if (!hit) return
    this.highlightGroup.visible = true
    // A Box3Helper's geometry is a unit cube until updateMatrixWorld bakes its box corners in —
    // without this, setFromObject would frame the origin, not the region (Slice-8 audit Major).
    hit.object.updateMatrixWorld(true)
    const box = new THREE.Box3().setFromObject(hit.object)
    if (box.isEmpty()) return
    box.getCenter(this.target)
    const size = box.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z, 8)
    this.radius = Math.max(80, maxDim * 3)
    this.autoRotate = false // hold still on the region the user asked to see
  }

  private _rebuildHighlights(): void {
    this._clearHighlights()
    for (const r of this.latestRisks) {
      const obj = buildHighlightObject(r, this.meshOffset)
      if (!obj) continue
      this.highlightGroup.add(obj)
      this.highlights.push({ issueId: r.issueId, object: obj })
    }
  }

  private _clearHighlights(): void {
    for (const h of this.highlights) {
      this.highlightGroup.remove(h.object)
      const o = h.object as THREE.Mesh
      o.geometry?.dispose?.()
      const mat = o.material
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose())
      else (mat as THREE.Material | undefined)?.dispose?.()
    }
    this.highlights = []
  }

  /** Remove the current model (back to the empty plate) and cancel any in-flight load. */
  clearModel(): void {
    this.loadToken++ // a pending load is no longer the latest → it will discard its result
    this.removeModelChildren()
    this.latestRisks = []
    this._clearHighlights()
    this.dims = null
    this.labelAnchors = null
    this.hideLabels()
  }

  /** The loaded part's bounding-box dimensions (mm), or null when empty. */
  getDimensions(): Dimensions | null {
    return this.dims
  }

  /** A small PNG data-URL snapshot of the current frame for the "My Designs" gallery, or null if
   * the canvas can't be read. Renders a fresh frame, then downscales onto an offscreen 2D canvas
   * so the saved thumbnail is small regardless of the live canvas size. */
  captureThumbnail(maxDim = 320): string | null {
    try {
      this.renderer.render(this.scene, this.camera)
      const src = this.renderer.domElement
      const sw = src.width
      const sh = src.height
      if (!sw || !sh) return null
      const scale = Math.min(1, maxDim / Math.max(sw, sh))
      const tw = Math.max(1, Math.round(sw * scale))
      const th = Math.max(1, Math.round(sh * scale))
      const off = document.createElement('canvas')
      off.width = tw
      off.height = th
      const ctx = off.getContext('2d')
      if (!ctx) return null
      ctx.drawImage(src, 0, 0, tw, th)
      return off.toDataURL('image/png')
    } catch {
      return null
    }
  }

  resize(): void {
    const w = this.container.clientWidth || 1
    const h = this.container.clientHeight || 1
    this.renderer.setSize(w, h, false)
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
  }

  resetView(): void {
    this.theta = -0.7
    this.phi = 1.15
    this.autoRotate = !this.reduceMotion
    this.frameToModel()
  }

  dispose(): void {
    this.disposed = true
    cancelAnimationFrame(this.raf)
    window.clearTimeout(this.resumeTimer)
    this.dragCleanup?.()
    this.ro?.disconnect()
    this.cleanups.forEach((fn) => fn())
    this.scene.traverse((obj) => {
      const o = obj as THREE.Mesh
      o.geometry?.dispose?.()
      const mat = o.material
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose())
      else (mat as THREE.Material | undefined)?.dispose?.()
    })
    this.renderer.dispose()
    // Proactively release the WebGL context (don't wait for GC) — matters under React
    // StrictMode's dev double-mount and repeated New-design cycles.
    this.renderer.forceContextLoss()
  }

  // ---- internals -------------------------------------------------------------

  private removeModelChildren(): void {
    for (const child of [...this.modelGroup.children]) {
      this.modelGroup.remove(child)
      const c = child as THREE.Mesh | THREE.LineSegments
      c.geometry?.dispose()
      const mat = c.material
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose())
      else mat?.dispose()
    }
  }

  private buildPlate(size: number): void {
    const grid = new THREE.GridHelper(size, 16, PLATE, PLATE)
    grid.rotation.x = Math.PI / 2 // lay flat with Z up
    const gm = grid.material as THREE.Material
    gm.transparent = true
    gm.opacity = 0.1
    this.scene.add(grid)

    const half = size / 2
    const ring = [
      [-half, -half],
      [half, -half],
      [half, half],
      [-half, half],
      [-half, -half],
    ].map(([x, y]) => new THREE.Vector3(x, y, 0))
    const border = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(ring),
      new THREE.LineBasicMaterial({ color: PLATE, transparent: true, opacity: 0.22 }),
    )
    this.scene.add(border)
  }

  /** A faint bounding box around the part + the W/D/H dimensions and their screen-label anchors. */
  private buildBBoxAndDims(): void {
    const box = new THREE.Box3().setFromObject(this.modelGroup)
    if (box.isEmpty()) return
    const min = box.min
    const max = box.max
    const size = box.getSize(new THREE.Vector3())
    this.dims = {
      x: Math.round(size.x),
      y: Math.round(size.y),
      z: Math.round(size.z),
    }

    // 12 edges of the box → a faint wireframe.
    const c = [
      [min.x, min.y, min.z], [max.x, min.y, min.z], [max.x, max.y, min.z], [min.x, max.y, min.z],
      [min.x, min.y, max.z], [max.x, min.y, max.z], [max.x, max.y, max.z], [min.x, max.y, max.z],
    ]
    const e = [
      [0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7],
    ]
    const verts: number[] = []
    for (const [a, b] of e) verts.push(...c[a], ...c[b])
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3))
    this.modelGroup.add(
      new THREE.LineSegments(
        g,
        new THREE.LineBasicMaterial({ color: PLATE, transparent: true, opacity: 0.26 }),
      ),
    )

    // Anchor each dimension label to a front-bottom edge midpoint.
    this.labelAnchors = {
      x: new THREE.Vector3((min.x + max.x) / 2, min.y, min.z),
      y: new THREE.Vector3(max.x, (min.y + max.y) / 2, min.z),
      z: new THREE.Vector3(min.x, min.y, (min.z + max.z) / 2),
    }
  }

  private frameToModel(): void {
    const box = new THREE.Box3().setFromObject(this.modelGroup)
    if (box.isEmpty()) return
    box.getCenter(this.target)
    const size = box.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z, 1)
    this.radius = Math.max(120, maxDim * 2.4)
    if (!this.reduceMotion) this.autoRotate = true
  }

  private positionCamera(): void {
    const { radius: r, theta: t, phi: ph, target: c } = this
    this.camera.position.set(
      c.x + r * Math.sin(ph) * Math.cos(t),
      c.y + r * Math.sin(ph) * Math.sin(t),
      c.z + r * Math.cos(ph),
    )
    this.camera.lookAt(c)
  }

  private hideLabels(): void {
    if (!this.labels) return
    for (const k of ['x', 'y', 'z'] as const) this.labels[k].style.opacity = '0'
  }

  /** Project the dimension anchors to screen space and update the DOM label pills. */
  private updateLabels(): void {
    if (!this.labels || !this.labelAnchors || !this.dims) return
    const w = this.container.clientWidth
    const h = this.container.clientHeight
    const offsets = { x: [0, 18], y: [22, 8], z: [-26, 0] } as const
    for (const k of ['x', 'y', 'z'] as const) {
      const v = this.labelAnchors[k].clone().project(this.camera)
      const el = this.labels[k]
      if (v.z >= 1) {
        el.style.opacity = '0'
        continue
      }
      const sx = (v.x * 0.5 + 0.5) * w + offsets[k][0]
      const sy = (-v.y * 0.5 + 0.5) * h + offsets[k][1]
      el.style.opacity = '1'
      el.style.transform = `translate(-50%, -50%) translate(${sx}px, ${sy}px)`
      el.textContent = `${this.dims[k]} mm`
    }
  }

  private loop(): void {
    if (this.disposed) return
    this.raf = requestAnimationFrame(this.loop)
    if (this.autoRotate && !this.dragging) this.theta += 0.0026
    this.positionCamera()
    this.renderer.render(this.scene, this.camera)
    this.updateLabels()
  }

  private bindInteractions(canvas: HTMLCanvasElement): void {
    if (typeof ResizeObserver !== 'undefined') {
      this.ro = new ResizeObserver(() => this.resize())
      this.ro.observe(this.container)
    }
    const onWinResize = () => this.resize()
    window.addEventListener('resize', onWinResize)
    this.cleanups.push(() => window.removeEventListener('resize', onWinResize))

    // Robustness: if the WebGL context is lost (a driver hiccup, or too many live contexts after
    // repeated reloads), prevent the default teardown so the browser can RESTORE it — the rAF
    // loop then resumes rendering. Without this a lost context silently freezes the viewport.
    const onContextLost = (e: Event) => e.preventDefault()
    canvas.addEventListener('webglcontextlost', onContextLost, false)
    this.cleanups.push(() => canvas.removeEventListener('webglcontextlost', onContextLost))

    let px = 0
    let py = 0
    const move = (e: PointerEvent) => {
      const dx = e.clientX - px
      const dy = e.clientY - py
      px = e.clientX
      py = e.clientY
      this.theta -= dx * 0.01
      this.phi = Math.max(0.2, Math.min(Math.PI - 0.12, this.phi - dy * 0.008))
    }
    const endDrag = () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      this.dragCleanup = undefined
    }
    const up = () => {
      this.dragging = false
      endDrag()
      window.clearTimeout(this.resumeTimer)
      if (!this.reduceMotion) {
        this.resumeTimer = window.setTimeout(() => {
          this.autoRotate = true
        }, 3500)
      }
    }
    const down = (e: PointerEvent) => {
      this.dragging = true
      this.autoRotate = false
      px = e.clientX
      py = e.clientY
      window.addEventListener('pointermove', move)
      window.addEventListener('pointerup', up)
      this.dragCleanup = endDrag
    }
    canvas.addEventListener('pointerdown', down)
    this.cleanups.push(() => canvas.removeEventListener('pointerdown', down))

    const wheel = (e: WheelEvent) => {
      e.preventDefault()
      this.radius = Math.max(60, Math.min(2000, this.radius + e.deltaY * 0.5))
    }
    canvas.addEventListener('wheel', wheel, { passive: false })
    this.cleanups.push(() => canvas.removeEventListener('wheel', wheel))
  }
}
