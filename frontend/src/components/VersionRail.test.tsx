// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DesignResponse, DesignVersion } from '../api'
import VersionRail from './VersionRail'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// A minimal completed result; VersionRail only reads version index/label, not the result body.
function result(): DesignResponse {
  return { status: 'completed', has_mesh: true, mesh_url: '/api/mesh/1' }
}

function version(index: number, label: string): DesignVersion {
  return { index, messages: [], result: result(), label }
}

function renderRail(overrides: Partial<React.ComponentProps<typeof VersionRail>> = {}) {
  const props = {
    versions: [version(1, 'first'), version(2, 'taller'), version(3, 'wider')],
    versionIdx: 2,
    onSwitch: vi.fn(),
    onCompare: vi.fn(),
    ...overrides,
  }
  return { ...render(<VersionRail {...props} />), props }
}

describe('VersionRail', () => {
  it('renders nothing with zero versions', () => {
    const { container } = renderRail({ versions: [], versionIdx: -1 })
    expect(container.firstChild).toBeNull()
  })

  it('UX-011: shows a quiet v1 cue (not the full rail) with one version', () => {
    renderRail({ versions: [version(1, 'only')], versionIdx: 0 })
    expect(screen.getByText(/refine to create versions/i)).toBeTruthy()
    expect(screen.queryByRole('button', { name: /^v1/i })).toBeNull() // no pills until v2
  })

  it('renders a pill per version and marks the active one with aria-current', () => {
    renderRail({ versionIdx: 1 })
    expect(screen.getByRole('button', { name: /Version 1: first/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Version 2: taller/i })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Version 3: wider/i })).toBeTruthy()
    const active = screen.getByRole('button', { name: /Version 2: taller/i })
    expect(active.getAttribute('aria-current')).toBe('true')
    // Non-active pills carry no aria-current.
    expect(screen.getByRole('button', { name: /Version 1: first/i }).getAttribute('aria-current')).toBeNull()
  })

  it('switches to the clicked version', () => {
    const { props } = renderRail({ versionIdx: 2 })
    fireEvent.click(screen.getByRole('button', { name: /Version 1: first/i }))
    expect(props.onSwitch).toHaveBeenCalledWith(0)
  })

  it('disables Undo at the first version and hides Redo at the latest', () => {
    renderRail({ versionIdx: 0 })
    expect((screen.getByRole('button', { name: /Undo/i }) as HTMLButtonElement).disabled).toBe(true)
    // At v1 there IS a later version, so Redo shows.
    expect(screen.queryByRole('button', { name: /Redo/i })).toBeTruthy()
  })

  it('hides Redo at the latest version and enables Undo', () => {
    renderRail({ versionIdx: 2 }) // last of 3
    expect(screen.queryByRole('button', { name: /Redo/i })).toBeNull()
    expect((screen.getByRole('button', { name: /Undo/i }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('Undo and Redo step by one', () => {
    const { props, rerender } = renderRail({ versionIdx: 1 })
    fireEvent.click(screen.getByRole('button', { name: /Undo/i }))
    expect(props.onSwitch).toHaveBeenCalledWith(0)
    fireEvent.click(screen.getByRole('button', { name: /Redo/i }))
    expect(props.onSwitch).toHaveBeenCalledWith(2)
    rerender(<VersionRail {...props} versionIdx={1} />)
  })

  it('Compare defaults to the two most-recent versions', () => {
    const { props } = renderRail({ versionIdx: 2 }) // 3 versions → compare indices 1 and 2
    fireEvent.click(screen.getByRole('button', { name: /Compare/i }))
    expect(props.onCompare).toHaveBeenCalledWith(1, 2)
  })

  it('Compare on exactly two versions uses indices 0 and 1', () => {
    const { props } = renderRail({
      versions: [version(1, 'a'), version(2, 'b')],
      versionIdx: 1,
    })
    fireEvent.click(screen.getByRole('button', { name: /Compare/i }))
    expect(props.onCompare).toHaveBeenCalledWith(0, 1)
  })
})
