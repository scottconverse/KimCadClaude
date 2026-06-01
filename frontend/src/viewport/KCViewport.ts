import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

// KCViewport — a vanilla Three.js viewport for KimCad (Stage 4, Slice 3).
//
// Unlike the design prototype's KCViewport (which builds fake procedural geometry from
// sliders), this loads the REAL rendered part: the pipeline exports `*.oriented.stl`
// (pipeline.py), the web server serves it at GET /api/mesh/<id>, and this loads that STL
// with three's STLLoader. Kept framework-free (no react-three-fiber) and driven from a thin
// React wrapper (Viewport.tsx). Units are millimetres (KimCad's mesh space); Z is up
// (build-plate orientation), matching the exported, plate-down oriented mesh.

const VIEWPORT_BG = 0x14171c // Workshop dark viewport
const ACCENT = 0xc8623a // Workshop terracotta
const PLATE = 0xffffff

export class KCViewport {
  private container: HTMLElement
  private renderer: THREE.WebGLRenderer
  private scene: THREE.Scene
  private camera: THREE.PerspectiveCamera
  private modelGroup: THREE.Group
  private target = new THREE.Vector3(0, 0, 0)

  // Spherical camera (azimuth, polar, radius), auto-rotating when idle.
  private theta = -0.7
  private phi = 1.15
  private radius = 460
  private autoRotate = true
  private dragging = false

  private raf = 0
  private disposed = false
  private resumeTimer = 0
  private ro?: ResizeObserver
  private cleanups: Array<() => void> = []
  private dragCleanup?: () => void
  // Monotonic load id: a load that's no longer the latest (a newer load started, or the model
  // was cleared) discards its result instead of clobbering the viewport — guards the STL race.
  private loadToken = 0

  constructor(container: HTMLElement, canvas: HTMLCanvasElement) {
    this.container = container

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
    // Discard if disposed, or if a newer load / a clear happened while we were fetching.
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
    this.frameToModel()
  }

  /** Remove the current model (back to the empty plate) and cancel any in-flight load. */
  clearModel(): void {
    this.loadToken++ // a pending load is no longer the latest → it will discard its result
    this.removeModelChildren()
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
    this.autoRotate = true
    this.frameToModel()
  }

  dispose(): void {
    this.disposed = true
    cancelAnimationFrame(this.raf)
    window.clearTimeout(this.resumeTimer)
    this.dragCleanup?.()
    this.ro?.disconnect()
    this.cleanups.forEach((fn) => fn())
    // Release every GPU resource in the scene — model, grid, and plate border (lights carry
    // no geometry/material). renderer.dispose() alone does not free these.
    this.scene.traverse((obj) => {
      const o = obj as THREE.Mesh
      o.geometry?.dispose?.()
      const mat = o.material
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose())
      else (mat as THREE.Material | undefined)?.dispose?.()
    })
    this.renderer.dispose()
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

  private frameToModel(): void {
    const box = new THREE.Box3().setFromObject(this.modelGroup)
    if (box.isEmpty()) return
    box.getCenter(this.target)
    const size = box.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z, 1)
    this.radius = Math.max(120, maxDim * 2.4)
    this.autoRotate = true
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

  private loop(): void {
    if (this.disposed) return
    this.raf = requestAnimationFrame(this.loop)
    if (this.autoRotate && !this.dragging) this.theta += 0.0026
    this.positionCamera()
    this.renderer.render(this.scene, this.camera)
  }

  private bindInteractions(canvas: HTMLCanvasElement): void {
    if (typeof ResizeObserver !== 'undefined') {
      this.ro = new ResizeObserver(() => this.resize())
      this.ro.observe(this.container)
    }
    const onWinResize = () => this.resize()
    window.addEventListener('resize', onWinResize)
    this.cleanups.push(() => window.removeEventListener('resize', onWinResize))

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
      this.resumeTimer = window.setTimeout(() => {
        this.autoRotate = true
      }, 3500)
    }
    const down = (e: PointerEvent) => {
      this.dragging = true
      this.autoRotate = false
      px = e.clientX
      py = e.clientY
      window.addEventListener('pointermove', move)
      window.addEventListener('pointerup', up)
      this.dragCleanup = endDrag // so dispose() during an active drag removes these too
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
