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

export class KCViewport {
  private container: HTMLElement
  private renderer: THREE.WebGLRenderer
  private scene: THREE.Scene
  private camera: THREE.PerspectiveCamera
  private modelGroup: THREE.Group
  private target = new THREE.Vector3(0, 0, 0)
  private labels: DimLabels | null

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

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
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
  }

  /** Remove the current model (back to the empty plate) and cancel any in-flight load. */
  clearModel(): void {
    this.loadToken++ // a pending load is no longer the latest → it will discard its result
    this.removeModelChildren()
    this.dims = null
    this.labelAnchors = null
    this.hideLabels()
  }

  /** The loaded part's bounding-box dimensions (mm), or null when empty. */
  getDimensions(): Dimensions | null {
    return this.dims
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
