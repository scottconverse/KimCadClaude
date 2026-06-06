// Slice 11 (copy): turn an internal object_type slug into plain words for display.
// The planner emits slugs like "snap_box", "cable_clip", "drawer_divider"; a first-time maker
// shouldn't see underscores. Lowercase words, spaces for separators — "snap box", "cable clip".
// Unknown/empty falls back to "part" so a card/label is never blank.
export function humanizeObjectType(type: string | null | undefined): string {
  if (!type) return 'part'
  const words = type
    .trim()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return words || 'part'
}
