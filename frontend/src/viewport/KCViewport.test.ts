import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { type HighlightRisk, buildHighlightObject, meshDisplayOffset } from './KCViewport'

// Slice 8: the highlight math is the load-bearing correctness of "show the problem in the RIGHT
// place." These exercise the pure helpers directly (no WebGL context needed), so the alignment
// and the bounding-box focus fix are guarded by tests, not just by reading.

describe('meshDisplayOffset', () => {
  it('reproduces the mesh display transform: (-center.x, -center.y, -min.z)', () => {
    const bb = new THREE.Box3(new THREE.Vector3(10, 20, 30), new THREE.Vector3(50, 60, 70))
    const off = meshDisplayOffset(bb)
    expect(off.x).toBeCloseTo(-30) // -(10+50)/2 — centered in X
    expect(off.y).toBeCloseTo(-40) // -(20+60)/2 — centered in Y
    expect(off.z).toBeCloseTo(-30) // -min.z — the part sits on the plate (z = 0)
  })
})

describe('buildHighlightObject alignment', () => {
  const off = new THREE.Vector3(-30, -40, -30)

  it('places a point marker at point + offset', () => {
    const r: HighlightRisk = {
      issueId: 'P', tone: 'warn', geometry: { type: 'point', x: 30, y: 40, z: 30 },
    }
    const obj = buildHighlightObject(r, off)
    expect(obj).not.toBeNull()
    expect(obj!.position.x).toBeCloseTo(0)
    expect(obj!.position.y).toBeCloseTo(0)
    expect(obj!.position.z).toBeCloseTo(0)
  })

  it('builds a triangles overlay whose bbox sits at the triangle coords + offset', () => {
    const r: HighlightRisk = {
      issueId: 'T', tone: 'fail',
      geometry: { type: 'triangles', triangles: [{ v0: [30, 40, 30], v1: [33, 40, 30], v2: [30, 43, 30] }] },
    }
    const obj = buildHighlightObject(r, off) as THREE.Mesh
    obj.updateMatrixWorld(true)
    const c = new THREE.Box3().setFromObject(obj).getCenter(new THREE.Vector3())
    expect(c.x).toBeCloseTo(1.5) // x in [0,3] after offset
    expect(c.y).toBeCloseTo(1.5) // y in [0,3]
    expect(c.z).toBeCloseTo(0) // flat on the plate
  })

  it('builds a bounding-box highlight that centers correctly AFTER updateMatrixWorld (focus regression)', () => {
    const r: HighlightRisk = {
      issueId: 'B', tone: 'warn',
      geometry: { type: 'bounding_box', min_x: 30, min_y: 40, min_z: 30, max_x: 50, max_y: 60, max_z: 50 },
    }
    const obj = buildHighlightObject(r, off)!
    obj.updateMatrixWorld(true) // the bake focusHighlight performs; without it the box reads as a unit cube
    const c = new THREE.Box3().setFromObject(obj).getCenter(new THREE.Vector3())
    // (30,40,30)-(50,60,50) + (-30,-40,-30) = (0,0,0)-(20,20,20) -> center (10,10,10)
    expect(c.x).toBeCloseTo(10)
    expect(c.y).toBeCloseTo(10)
    expect(c.z).toBeCloseTo(10)
  })

  it('returns null for an empty triangle set (no degenerate highlight)', () => {
    const r: HighlightRisk = {
      issueId: 'E', tone: 'warn', geometry: { type: 'triangles', triangles: [] },
    }
    expect(buildHighlightObject(r, off)).toBeNull()
  })
})
