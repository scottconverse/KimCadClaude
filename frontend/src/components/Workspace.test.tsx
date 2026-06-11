// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DesignResponse } from '../api'
import Workspace from './Workspace'

// Mock the heavy children (Viewport pulls in three.js/WebGL) so this focuses on Workspace's own
// composition — specifically the UX-004 mobile "Check & download" CTA.
vi.mock('./ChatPanel', () => ({ default: () => <div data-testid="chat" /> }))
vi.mock('./Viewport', () => ({ default: () => <div data-testid="viewport" /> }))
// The mock surfaces the lifted `tab` prop (slice 2) so the CTA's tab-switch is assertable.
vi.mock('./RightPanel', () => ({
  default: (p: { tab?: string }) => <div data-testid="right" data-tab={p.tab} />,
}))
vi.mock('./VersionRail', () => ({ default: () => null }))

afterEach(cleanup)

function props(result: DesignResponse | null) {
  return {
    messages: [],
    compareCard: null,
    versions: [],
    versionIdx: -1,
    result,
    meshUrl: null,
    busy: false,
    restoring: false,
    busyElapsed: 0,
    busyPhase: null,
    onCancelDesign: vi.fn(),
    error: null,
    rerendering: false,
    rerenderError: null,
    onRerender: vi.fn(),
    onRefine: vi.fn(),
    onSwitchVersion: vi.fn(),
    onCompare: vi.fn(),
    onTryExperimental: vi.fn(),
    onPhotoSeed: vi.fn(),
    onRetry: vi.fn(),
    onModelReady: vi.fn(),
  }
}

const withMesh: DesignResponse = { status: 'completed', has_mesh: true, mesh_url: '/api/mesh/1' }

describe('Workspace landmark (2026-06-09 audit UX-004)', () => {
  it('renders as the main landmark with the skip-link target id', () => {
    render(<Workspace {...props(withMesh)} />)
    const main = screen.getByRole('main')
    expect(main.id).toBe('kimcad-main')
  })
})

describe('Workspace mobile CTA (UX-004 / RTEST-004)', () => {
  it('shows the "Check & download" CTA only once a part with a mesh exists', () => {
    const { rerender } = render(<Workspace {...props(null)} />)
    expect(screen.queryByRole('button', { name: /check & download/i })).toBeNull()
    rerender(<Workspace {...props(withMesh)} />)
    expect(screen.getByRole('button', { name: /check & download/i })).toBeTruthy()
  })

  it('the CTA opens the Export tab, then scrolls the export card into view', async () => {
    const el = document.createElement('div')
    el.id = 'kc-export-card'
    const scrollSpy = vi.fn()
    el.scrollIntoView = scrollSpy
    document.body.appendChild(el)
    render(<Workspace {...props(withMesh)} />)
    fireEvent.click(screen.getByRole('button', { name: /check & download/i }))
    // Slice 2: the CTA first switches the Inspector to Export…
    expect(screen.getByTestId('right').getAttribute('data-tab')).toBe('export')
    // …then scrolls on the next frame (after the tabpanel un-hides).
    await new Promise((r) => requestAnimationFrame(() => r(null)))
    expect(scrollSpy).toHaveBeenCalled()
    el.remove()
  })
})
