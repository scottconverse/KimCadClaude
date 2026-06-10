// Plain-language definitions for the terms KimCad's UI uses but a first-time maker may not know.
// Surfaced as small "(i)" info tips next to the term (see components/InfoTip). Rules for an entry:
// keep it short, concrete, and free of further jargon — if a definition needs another term, it
// explains that term inline rather than assuming it. This is the single source of truth, so the
// same wording can be reused anywhere a term appears (the readiness card today; the first-run
// wizard and elsewhere later).

export interface GlossaryEntry {
  /** The human term as it reads in the UI (used in the tip's accessible name). */
  term: string
  /** The plain-language explanation. */
  definition: string
}

export const GLOSSARY = {
  readiness: {
    term: 'Readiness',
    definition:
      'An overall estimate of how likely this part is to print well. It blends the basic size and shape checks with a deeper geometry analysis when one is available — higher is better.',
  },
  printability: {
    term: 'Printability',
    definition:
      "KimCad's automatic check that the part can actually be made on a 3D printer: its dimensions, how thick its walls are, and whether it fits on the printer's bed. If a part doesn't pass, KimCad won't slice it or send it to a printer until the problem is fixed.",
  },
  // UX-109 (stage-BCD gate): the standalone "Gate" tip was removed with the badge jargon —
  // the Printability entry (above) carries the concept; the pass-or-fail consequence lives
  // there so one tip tells the whole story.
  // UX-107 (stage-BCD gate): the engine chip's explanation was hover-only (a `title`) —
  // unreachable by keyboard/touch. Same InfoTip affordance as every other technical term.
  engine: {
    term: 'Engine',
    definition:
      'The geometry tool that built this part. KimCad picks whichever fits the part best; parts built by CadQuery also offer an editable STEP (CAD) download.',
  },
  risks: {
    term: 'Risks',
    definition:
      'Spots that could make the print fail or come out rough — like steep overhangs or walls that are too thin. Each risk says what it is and, when possible, shows where it is on the model.',
  },
  recommendations: {
    term: 'Recommendations',
    definition: 'Specific, plain-language changes you can make to improve how the part prints.',
  },
  confidence: {
    term: 'Confidence',
    definition:
      'How sure KimCad is about the readiness score. High means a deeper engine inspected the 3D shape; lower means only the basic checks were possible.',
  },
} as const satisfies Record<string, GlossaryEntry>

export type GlossaryKey = keyof typeof GLOSSARY
