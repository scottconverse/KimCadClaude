// @vitest-environment jsdom
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import { measureBetween } from './KCViewport'

// UI-v2 slice 4 (#23): the measurement math — pure and translation-invariant, which is the
// property that makes measuring in DISPLAY coordinates equal to measuring the real part
// (loadMesh only translates the raw STL; it never scales or rotates it).

describe('measureBetween', () => {
  it('computes the straight-line distance and per-axis |deltas| in mm', () => {
    const m = measureBetween(new THREE.Vector3(0, 0, 0), new THREE.Vector3(80, 0, 60))
    expect(m.points).toBe(2)
    expect(m.distanceMm).toBeCloseTo(100, 6) // 3-4-5 triangle scaled
    expect(m.deltasMm).toEqual([80, 0, 60])
  })

  it('is symmetric and translation-invariant (the display-space guarantee)', () => {
    const a = new THREE.Vector3(3, -7, 12)
    const b = new THREE.Vector3(-15, 4, 2)
    const t = new THREE.Vector3(100, -50, 9) // any mesh display offset
    const m1 = measureBetween(a, b)
    const m2 = measureBetween(b, a)
    const m3 = measureBetween(a.clone().add(t), b.clone().add(t))
    expect(m1.distanceMm).toBeCloseTo(m2.distanceMm!, 9)
    expect(m1.distanceMm).toBeCloseTo(m3.distanceMm!, 9)
    expect(m1.deltasMm).toEqual(m2.deltasMm)
    expect(m1.deltasMm![0]).toBeCloseTo(m3.deltasMm![0], 9)
  })
})
