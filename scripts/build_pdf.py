"""Build KimCad README-FULL.pdf — the full technical reference with architecture diagrams."""
import sys
import textwrap
from pathlib import Path

try:
    from fpdf import FPDF, XPos, YPos
except ImportError:
    sys.exit("pip install fpdf2 first")

REPO = Path(__file__).parent.parent
OUT = REPO / "docs" / "README-FULL.pdf"

_REPLACEMENTS = {
    "—": "-",   # em dash
    "–": "-",   # en dash
    "‘": "'",   # left single quote
    "’": "'",   # right single quote
    "“": '"',   # left double quote
    "”": '"',   # right double quote
    "…": "...", # ellipsis
    " ": " ",   # non-breaking space
    "→": "->",  # arrow
}


def _safe(text: str) -> str:
    for char, repl in _REPLACEMENTS.items():
        text = text.replace(char, repl)
    return text

# ── colour palette (Zen Design World — matches the 0.9.3 SPA tokens) ────────
# Kept variable names so the rest of the file doesn't churn; `BLUE` is now the
# Zen gold (the primary accent), `ACCENT` is the darker gold for accent text.
BLUE   = (212, 175, 55)   # Zen gold (--kc-accent light)
DARK   = (12, 10, 6)      # Zen deep-black ink (--kc-ink light)
MID    = (90, 85, 76)     # Zen muted (--kc-ink-muted)
LIGHT  = (250, 250, 247)  # Zen warm-white surface (--kc-bg)
WHITE  = (255, 255, 255)
ACCENT = (184, 144, 31)   # Zen gold-strong (--kc-accent-strong)


class KimCadPDF(FPDF):
    VERSION = "0.9.3"

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*MID)
        self.cell(0, 8, f"KimCad {self.VERSION} - Full Reference", align="L")
        self.set_font("Helvetica", "", 8)
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LIGHT)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)
        self.set_text_color(*DARK)

    def footer(self):
        pass


def cover(pdf: KimCadPDF):
    pdf.add_page()
    # full-width blue banner
    pdf.set_fill_color(*BLUE)
    pdf.rect(0, 0, pdf.w, 80, "F")

    # logo cube glyph (geometric approximation)
    cx, cy = 22, 18
    pdf.set_fill_color(*WHITE)
    pdf.set_draw_color(*WHITE)
    pdf.set_line_width(0.5)
    # top face
    pdf.polygon([(cx,cy-6),(cx+7,cy-2),(cx,cy+2),(cx-7,cy-2)], style="F")
    # left face
    pdf.polygon([(cx-7,cy-2),(cx,cy+2),(cx,cy+10),(cx-7,cy+6)], style="F")
    # right face — slightly darker
    pdf.set_fill_color(180, 210, 255)
    pdf.polygon([(cx+7,cy-2),(cx,cy+2),(cx,cy+10),(cx+7,cy+6)], style="F")
    pdf.set_fill_color(*WHITE)

    # title
    pdf.set_xy(10, 88)
    pdf.set_font("Helvetica", "B", 34)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 14, "Kim", new_x=XPos.RIGHT, new_y=YPos.LAST)
    pdf.set_font("Helvetica", "", 34)
    pdf.cell(0, 14, "Cad", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 15)
    pdf.set_text_color(*MID)
    pdf.set_x(10)
    pdf.cell(0, 8, "AI-assisted parametric design for functional 3D prints", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*BLUE)
    pdf.set_x(10)
    pdf.cell(0, 7, "Full Technical Reference", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(6)
    meta = [
        ("Version", f"{KimCadPDF.VERSION} Windows beta"),
        ("Platform", "Windows 11 / macOS / Linux (from source)"),
        ("Source", "github.com/scottconverse/KimCadClaude"),
        ("License", "MIT"),
    ]
    for k, v in meta:
        pdf.set_x(10)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*MID)
        pdf.cell(32, 6, k + ":", new_x=XPos.RIGHT, new_y=YPos.LAST)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 6, v, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(16)
    # divider
    pdf.set_draw_color(*BLUE)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MID)
    pdf.set_x(10)
    pdf.multi_cell(
        0, 6,
        _safe("This document covers the full product - the user-facing interface, the technical surface "
        "for developers and integrators, and the internal architecture. For a quick start, "
        "see the README at the repository root."),
    )


def toc(pdf: KimCadPDF):
    pdf.add_page()
    h1(pdf, "Contents")
    entries = [
        ("Part 1 · Everyday Use", 4),
        ("  What KimCad is (and isn't)", 4),
        ("  Installing on Windows", 4),
        ("  Installing on macOS / Linux", 4),
        ("  First run & the setup wizard", 5),
        ("  The three ways to start a design", 5),
        ("  Live parameter sliders", 5),
        ("  Refining a design", 6),
        ("  Printing — confirming and slicing", 6),
        ("  Sending directly to a printer", 6),
        ("  My Designs library", 7),
        ("  What to do when things go wrong", 7),
        ("  Glossary", 8),
        ("Part 2 · The Technical Surface", 9),
        ("  CLI reference", 9),
        ("  Configuration", 10),
        ("  Printer connectors", 10),
        ("  The MCP server", 11),
        ("  The CadQuery / STEP engine", 11),
        ("  API reference", 12),
        ("Part 3 · Architecture", 13),
        ("  The pipeline — diagram", 13),
        ("  Module map", 14),
        ("  The template engine & catalog", 16),
        ("  The web layer", 17),
        ("  Local-first design & the injectable seam", 18),
        ("  Trust boundaries", 18),
        ("  Testing philosophy", 19),
    ]
    pdf.set_font("Helvetica", "", 10)
    for text, _ in entries:
        is_top = not text.startswith("  ")
        pdf.set_x(10)
        if is_top:
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*BLUE)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*DARK)
        pdf.cell(0, 6, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*DARK)


# ── layout helpers ───────────────────────────────────────────────────────────

def h1(pdf: KimCadPDF, text: str, part: str = ""):
    pdf.ln(4)
    if part:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*BLUE)
        pdf.set_x(10)
        pdf.cell(0, 6, _safe(part), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*DARK)
    pdf.set_x(10)
    pdf.cell(0, 12, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*BLUE)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
    pdf.ln(5)
    pdf.set_text_color(*DARK)


def h2(pdf: KimCadPDF, text: str):
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*DARK)
    pdf.set_x(10)
    pdf.cell(0, 8, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*LIGHT)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), pdf.w - 10, pdf.get_y())
    pdf.ln(3)
    pdf.set_text_color(*DARK)


def h3(pdf: KimCadPDF, text: str):
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ACCENT)
    pdf.set_x(10)
    pdf.cell(0, 7, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*DARK)


def body(pdf: KimCadPDF, text: str, indent: int = 0):
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*DARK)
    pdf.set_x(10 + indent)
    pdf.multi_cell(pdf.w - 20 - indent, 5.5, _safe(text.strip()))
    pdf.ln(1)


def bullet(pdf: KimCadPDF, items: list[str], indent: int = 4):
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*DARK)
    for item in items:
        pdf.set_x(10 + indent)
        pdf.cell(5, 5.5, "*", new_x=XPos.RIGHT, new_y=YPos.LAST)
        pdf.multi_cell(pdf.w - 20 - indent - 5, 5.5, _safe(item.strip()))
    pdf.ln(1)


def note_box(pdf: KimCadPDF, text: str):
    pdf.ln(2)
    x, y = pdf.get_x(), pdf.get_y()
    pdf.set_x(10)
    pdf.set_fill_color(*LIGHT)
    pdf.set_draw_color(*LIGHT)
    line_h = 5.5
    safe_text = _safe(text.strip())
    lines = pdf.multi_cell(pdf.w - 20, line_h, safe_text, dry_run=True, output="LINES")
    box_h = len(lines) * line_h + 8
    pdf.rect(10, y, pdf.w - 20, box_h, "F")
    pdf.set_xy(14, y + 4)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(*MID)
    pdf.multi_cell(pdf.w - 28, line_h, safe_text)
    pdf.set_text_color(*DARK)
    pdf.ln(3)


def code_block(pdf: KimCadPDF, text: str):
    pdf.ln(2)
    y = pdf.get_y()
    pdf.set_fill_color(30, 41, 59)
    pdf.set_draw_color(30, 41, 59)
    lines = _safe(text.strip()).split("\n")
    box_h = len(lines) * 5 + 8
    pdf.rect(10, y, pdf.w - 20, box_h, "F")
    pdf.set_xy(14, y + 4)
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(186, 230, 253)
    for line in lines:
        pdf.set_x(14)
        pdf.cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*DARK)
    pdf.ln(3)


def kv_table(pdf: KimCadPDF, rows: list[tuple[str, str]]):
    pdf.ln(2)
    col_w = 52
    body_w = pdf.w - 20 - col_w
    pdf.set_font("Helvetica", "", 9)
    for k, v in rows:
        k, v = _safe(k), _safe(v)
        y = pdf.get_y()
        pdf.set_fill_color(*LIGHT)
        pdf.set_x(10)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*DARK)
        klines = pdf.multi_cell(col_w, 5, k, dry_run=True, output="LINES")
        vlines = pdf.multi_cell(body_w, 5, v, dry_run=True, output="LINES")
        row_h = max(len(klines), len(vlines)) * 5 + 2
        pdf.rect(10, y, col_w, row_h, "F")
        pdf.set_xy(11, y + 1)
        pdf.multi_cell(col_w - 1, 5, k)
        pdf.set_xy(10 + col_w + 1, y + 1)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*MID)
        pdf.multi_cell(body_w - 2, 5, v)
        pdf.set_xy(10, y + row_h)
        pdf.set_text_color(*DARK)
    pdf.ln(3)


# ── pipeline diagram ─────────────────────────────────────────────────────────

def pipeline_diagram(pdf: KimCadPDF):
    """Draw the design pipeline as a flow diagram."""
    pdf.add_page()
    h1(pdf, "The Design Pipeline", "Part 3 · Architecture")
    body(pdf,
        "Every design request flows through a deterministic pipeline. "
        "The AI model participates in exactly two steps — writing the structured design plan and, "
        "only when no template matches, generating OpenSCAD geometry. Every other stage is "
        "ordinary, testable code."
    )
    pdf.ln(4)

    stages = [
        ("Prompt", "Plain English, photo, or sketch", BLUE),
        ("Design Plan (JSON)", "AI: structured intent - object type, dimensions, features", (79, 70, 229)),
        ("Clarify?", "One question max, only if the part can't be sized", (124, 58, 237)),
        ("Geometry", "Template match -> deterministic emit / No template -> AI writes OpenSCAD", (16, 185, 129)),
        ("Sandboxed Render", "OpenSCAD runs in an isolated temp dir with a timeout", (5, 150, 105)),
        ("Mesh Validation", "Load, check watertight, attempt conservative repair", (8, 145, 178)),
        ("Printability Gate", "Pass / Warn / Fail vs chosen printer + material", (245, 158, 11)),
        ("Auto-Orient", "Rotate to most stable resting face, drop to bed", (249, 115, 22)),
        ("Harden (Manifold3D)", "Round-trip into a guaranteed 2-manifold", (239, 68, 68)),
        ("Smart Mesh Card", "Readiness score, risks, recommendations", (124, 58, 237)),
        ("Confirm + Slice", "OrcaSlicer -> G-code, only on explicit confirmation", (37, 99, 235)),
        ("Print Report", "Time, layers, filament estimate + readiness verdict", (15, 118, 110)),
    ]

    x0 = 20
    box_w = pdf.w - 40
    box_h = 11
    gap = 5
    arrow_h = 5
    x = x0

    for i, (name, desc, color) in enumerate(stages):
        y = pdf.get_y()
        if y + box_h + arrow_h + 10 > pdf.h - pdf.b_margin:
            pdf.add_page()
            y = pdf.get_y()

        # box
        pdf.set_fill_color(*color)
        pdf.set_draw_color(*color)
        pdf.rect(x, y, box_w, box_h, "F")

        # label
        pdf.set_xy(x + 4, y + 1.5)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*WHITE)
        pdf.cell(60, 4, _safe(name), new_x=XPos.RIGHT, new_y=YPos.LAST)

        pdf.set_xy(x + 4, y + 6)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.cell(box_w - 8, 4, _safe(desc))

        pdf.set_y(y + box_h)
        pdf.set_text_color(*DARK)

        # arrow down (not after last)
        if i < len(stages) - 1:
            ax = x + box_w / 2
            ay1 = pdf.get_y()
            ay2 = ay1 + arrow_h - 2
            pdf.set_draw_color(*MID)
            pdf.set_line_width(0.5)
            pdf.line(ax, ay1, ax, ay2)
            # arrowhead
            pdf.line(ax, ay2, ax - 3, ay2 - 3)
            pdf.line(ax, ay2, ax + 3, ay2 - 3)
            pdf.set_y(ay2)

    pdf.ln(8)
    note_box(pdf,
        "The AI is injected at two points only. Every other stage is deterministic — "
        "the renderer, gate, orientation, hardening, and slicer are all ordinary code "
        "with no model calls. This makes the pipeline fully testable offline and means "
        "a geometry mistake is fixed by changing parameters, not by re-running the model."
    )


# ── Part 1 ───────────────────────────────────────────────────────────────────

def part1(pdf: KimCadPDF):
    pdf.add_page()
    h1(pdf, "Everyday Use", "Part 1")

    h2(pdf, "What KimCad is (and isn't)")
    body(pdf,
        "KimCad turns a description of a functional part — a bracket, a holder, a clip, "
        "an enclosure — into a 3D-printable file. You describe it in plain words, or start "
        "from a photo or a rough sketch. KimCad designs it, checks it's actually printable, "
        "and gives you a ready-to-slice file. You never draw anything or edit any code."
    )
    body(pdf,
        "It runs entirely on your own computer. No account is needed, no internet is required, "
        "and nothing you type, photograph, or sketch ever leaves your machine — unless you "
        "explicitly turn on an optional cloud AI feature in Settings."
    )
    body(pdf,
        "KimCad is best at single mechanical parts. It is not a freeform artistic modeler "
        "and not a multi-part assembly tool."
    )

    h2(pdf, "Installing on Windows")
    body(pdf,
        "The easiest path is the double-click installer — no terminal, no Python, "
        "no developer tools needed."
    )
    bullet(pdf, [
        "Download KimCad-Setup-0.9.3.exe from the Releases page on GitHub.",
        "Double-click it. Windows will warn you because the beta isn't code-signed — "
        "click More info → Run anyway. (The release page publishes a checksum you can verify first.)",
        "Follow the wizard. KimCad installs to Program Files by default.",
        "Launch from the Start Menu shortcut.",
    ])
    body(pdf,
        "Requirements: Windows 11 (or Windows 10 with the WebView2 Runtime, which Edge installs "
        "automatically), about 12 GB free disk space for the AI and its models, "
        "16 GB+ RAM recommended. No graphics card needed."
    )

    h2(pdf, "Installing on macOS and Linux")
    body(pdf,
        "The zero-terminal installer is Windows-only for now. On macOS and Linux you run "
        "KimCad from the source code."
    )
    code_block(pdf,
        "pip install kimcad\n"
        "kimcad web"
    )
    body(pdf,
        "You install OpenSCAD and OrcaSlicer yourself and point the config file at them. "
        "Your saved designs and settings land in the platform-standard location "
        "(~/Library/Application Support/KimCad on macOS, ~/.local/share/KimCad on Linux)."
    )

    h2(pdf, "First run and the setup wizard")
    body(pdf,
        "The first time you launch KimCad, a setup wizard walks you through three things:"
    )
    bullet(pdf, [
        "The AI. KimCad runs its design intelligence locally through Ollama (free, included). "
        "It sets Ollama up for you — you don't install anything separately. On first launch it "
        "downloads the engine (~1.4 GB) and then the design model (~4.7 GB). This takes a few "
        "minutes on a reasonable connection.",
        "Your printer. Pick from the catalog of ~29 supported printers, or add your own.",
        "Your material. Choose the filament you're loading.",
    ])
    body(pdf,
        "After setup, KimCad stays ready — Ollama runs in the background while the app is open "
        "and shuts down cleanly when you close it. Models are only downloaded once."
    )

    h2(pdf, "The three ways to start a design")
    h3(pdf, "1. Type a description")
    body(pdf,
        "The simplest path: type what you want in the text field and press Enter. "
        "Be specific about dimensions — 'a cable clip for a 6 mm cable' gets you better results "
        "than 'a cable clip.'"
    )
    h3(pdf, "2. Start from a photo")
    body(pdf,
        "Click the camera icon and upload a photo of an existing part. KimCad's vision model "
        "reads the photo and turns it into a text description that seeds the design. "
        "Review the seed before proceeding — the vision read is a starting point, not a measurement."
    )
    h3(pdf, "3. Start from a sketch")
    body(pdf,
        "Draw a rough sketch with dimensions written on it, photograph it, and upload it. "
        "KimCad reads the sketch and takes the written dimensions as given."
    )

    h2(pdf, "Live parameter sliders")
    body(pdf,
        "When KimCad uses one of its built-in templates — which covers the vast majority of "
        "common shapes — the design comes back with sliders for every parameter: width, height, "
        "depth, wall thickness, and more. Drag a slider and the 3D view updates instantly, "
        "with no AI call. The geometry is rebuilt from scratch in well under a second."
    )
    body(pdf,
        "The slider ranges are bounded to values that will actually print, so you can't "
        "accidentally dial in something the printability check would reject."
    )

    h2(pdf, "Refining a design")
    body(pdf,
        "After a design comes back, you can ask KimCad to adjust it in plain language: "
        "'make the walls thicker', 'add a mounting hole', 'taller'. Each refinement is "
        "a new version; you can go back to any previous version from the history panel."
    )

    h2(pdf, "Printing — confirming and slicing")
    body(pdf,
        "When you're happy with the design, KimCad shows you the Printability Gate result — "
        "pass, warning, or fail, with a plain-English explanation. A passing part gets a "
        "Slice & prepare button. Click it and KimCad runs the slicer and shows you the "
        "estimated print time, layers, and filament use. The sliced file is ready to download "
        "or send directly to your printer."
    )
    note_box(pdf,
        "KimCad never slices anything automatically. You always click a button to confirm "
        "before the slicer runs, and again before anything is sent to a printer."
    )

    h2(pdf, "Sending directly to a printer")
    body(pdf,
        "After slicing, a Send panel appears. Pick the printer from the list and KimCad sends "
        "the file directly — no SD card, no USB drive. Supported connection types:"
    )
    bullet(pdf, [
        "Bambu Lab (LAN mode) — P2S, A1, and compatible models",
        "OctoPrint",
        "Moonraker / Klipper (Voron, Ender with Klipper, RatRig, Mainsail, Fluidd)",
        "PrusaLink — MK4, MK3.9, MINI, XL",
        "Duet / RepRapFirmware",
        "Marlin over USB serial or serial-over-network",
    ])
    body(pdf,
        "In this beta, every connector has been tested against a software simulator that faithfully "
        "mimics the real printer's protocol. Testing against actual hardware is the beta's main job "
        "(tracked in issue #11)."
    )

    h2(pdf, "My Designs library")
    body(pdf,
        "Every design you build is automatically saved to My Designs on your machine. "
        "You can name them, browse them in a gallery, open an old design to adjust it, "
        "duplicate it as a starting point, or export it as a .kimcad file to move to another machine."
    )

    h2(pdf, "What to do when things go wrong")
    kv_table(pdf, [
        ("The AI seems slow", "Planning a part takes 30–120 seconds on a typical laptop CPU — this is normal. The timer in the UI shows progress."),
        ("'KimCad couldn't reach your local AI'", "The AI engine isn't running. Go to Settings → AI setup and restart it."),
        ("Printability check failed", "The part has a geometry or size problem. Read the plain-English reason and adjust your sliders or description."),
        ("The part is the wrong size", "Check that your description included explicit dimensions. Add them and try again."),
        ("SmartScreen warning on install", "Expected — the beta isn't code-signed yet. Click 'More info → Run anyway'. You can verify the SHA-256 checksum on the release page first."),
        ("Slice button is greyed out", "The printability check didn't pass. Fix the geometry first."),
        ("Settings panel closes when I click a section", "Update to 0.9.2 — this was fixed."),
    ])

    h2(pdf, "Glossary")
    kv_table(pdf, [
        ("Ollama", "The free, local AI runtime KimCad uses to run its design intelligence on your machine."),
        ("Template engine", "KimCad's built-in library of 86 common shapes. When your part matches a known shape, geometry is built without any AI call."),
        ("Printability Gate", "The check that tells you whether a part will print successfully on your chosen printer with your chosen material."),
        ("OrcaSlicer", "The free slicing tool KimCad uses to convert a 3D model into the G-code your printer reads."),
        ("G-code", "The instruction file a 3D printer reads. Every move, temperature, and speed is in this file."),
        ("Smart Mesh Card", "The readiness summary KimCad shows after a design is built — score, risks, and plain-English recommendations."),
        ("STEP / .kimcad", "Export formats. STEP is editable in professional CAD tools. .kimcad is KimCad's portable archive format."),
        ("MCP server", "An optional interface that lets AI assistants (like Claude) drive KimCad programmatically."),
    ])


# ── Part 2 ───────────────────────────────────────────────────────────────────

def part2(pdf: KimCadPDF):
    pdf.add_page()
    h1(pdf, "The Technical Surface", "Part 2")

    h2(pdf, "CLI reference")
    body(pdf, "All commands run as kimcad <verb> [options].")
    kv_table(pdf, [
        ("kimcad design \"<prompt>\"", "Design a part. Add --slice to also slice it. Add --send <name> to send to a named printer."),
        ("kimcad web [--port N]", "Start the browser UI at localhost:8765 (or custom port)."),
        ("kimcad shell", "Launch the windowed app (Windows). Falls back to kimcad web on macOS/Linux."),
        ("kimcad models", "Show the hardware-aware AI model recommendation for this machine."),
        ("kimcad bakeoff", "Run a benchmark across multiple AI models and recommend the best one."),
        ("kimcad bench [--slice]", "Run the built-in design benchmark suite."),
        ("kimcad --version", "Print the version."),
    ])

    h2(pdf, "Configuration")
    body(pdf,
        "Configuration is layered: config/default.yaml (shipped, read-only) is overlaid by "
        "config/local.yaml (gitignored, per-user). In installed mode, local.yaml lives "
        "in %LOCALAPPDATA%\\KimCad on Windows."
    )
    body(pdf, "Key settings:")
    kv_table(pdf, [
        ("backends.local.model", "The planning model. Default: qwen2.5:7b."),
        ("backends.local.vision_model", "The vision model for photos/sketches. Default: qwen2.5vl:3b."),
        ("printers", "Named printer configurations with build volume, nozzle size, and connection settings."),
        ("materials", "Named material profiles with density, print temperature, and bed temperature."),
    ])
    note_box(pdf,
        "Credentials (API keys, Bambu access codes, OctoPrint keys) are always read from "
        "environment variables — never stored in config files, never logged."
    )

    h2(pdf, "Printer connectors")
    body(pdf,
        "Each connector is validated end-to-end against a runnable simulator that faithfully "
        "mimics the real printer's protocol, including fault injection."
    )
    kv_table(pdf, [
        ("bambu", "Bambu Lab LAN mode. MQTT-over-TLS for control + FTPS upload. Access code from env var BAMBU_ACCESS_CODE."),
        ("octoprint", "OctoPrint REST API. API key from env var OCTOPRINT_API_KEY."),
        ("moonraker", "Moonraker (Klipper). Optional API key from env var MOONRAKER_API_KEY."),
        ("prusalink", "PrusaLink REST API. API key from env var PRUSALINK_API_KEY."),
        ("duet", "Duet/RepRapFirmware via /rr_* HTTP interface. Optional board password from env var DUET_PASSWORD."),
        ("marlin", "Marlin via USB serial or serial-over-network. Port from env var MARLIN_PORT."),
        ("mock", "In-memory loopback connector for development and testing."),
    ])

    h2(pdf, "The MCP server")
    body(pdf,
        "KimCad ships a printer MCP (Model Context Protocol) server that lets AI assistants "
        "drive the printer connectors programmatically."
    )
    code_block(pdf, "python -m kimcad.mcp_server")
    body(pdf, "Exposed tools:")
    bullet(pdf, [
        "list_connectors — list configured connectors with capabilities",
        "printer_status — get live status of a named connector",
        "printer_capabilities — get the printer's reported build volume and nozzle",
        "send_print — send a sliced file to a named printer (requires confirm=true — the exact boolean)",
    ])

    h2(pdf, "The CadQuery / STEP engine")
    body(pdf,
        "For supported template families, KimCad also builds an editable STEP file alongside "
        "the STL — the kind you can open in Fusion 360, FreeCAD, or any professional CAD tool. "
        "This uses CadQuery, an optional dependency."
    )
    bullet(pdf, [
        "CadQuery is entirely optional. If it's not installed, STEP export is silently unavailable — "
        "everything else works.",
        "KimCad authors every CadQuery script — no AI ever writes CadQuery. "
        "The STEP path carries none of the AI-codegen risk.",
        "The worker runs in a separate process with a restricted environment "
        "as defense-in-depth.",
    ])

    h2(pdf, "API reference (web layer)")
    body(pdf, "All endpoints are on localhost only (127.0.0.1) by default.")
    kv_table(pdf, [
        ("GET /api/health", "Liveness check. Returns version and status."),
        ("POST /api/design", "Run a design. Body: {prompt, printer, material}. Returns plan, gate, mesh_url, parameters."),
        ("POST /api/render/<id>", "Re-render with new parameter values. Body: {values}. No AI call."),
        ("POST /api/slice/<id>", "Slice the validated mesh. Returns time/layers/filament estimate."),
        ("GET /api/gcode/<id>", "Download the sliced 3MF."),
        ("POST /api/send/<id>", "Send to printer. Body: {connector, confirm: true}."),
        ("GET /api/step/<id>", "Download the STEP/BREP file (CadQuery-backed designs only)."),
        ("POST /api/photo-seed", "Upload a photo. Returns a text seed for a design prompt."),
        ("POST /api/sketch-seed", "Upload a sketch. Returns a text seed."),
        ("GET /api/designs", "List saved designs."),
        ("POST /api/designs/save", "Save the current design with a thumbnail."),
        ("GET /api/model-status", "Report which AI models are installed and ready."),
        ("POST /api/model-pull", "Start downloading KimCad's own AI models."),
    ])
    note_box(pdf,
        "State-changing POSTs require an X-KimCad-Session header containing the per-boot "
        "session token injected into the page. This protects against cross-origin requests "
        "from malicious pages. GET requests are never gated."
    )


# ── Part 3 ───────────────────────────────────────────────────────────────────

def part3(pdf: KimCadPDF):
    pipeline_diagram(pdf)

    pdf.add_page()
    h1(pdf, "Module Map", "Part 3 · Architecture")
    body(pdf,
        "Every Python module in src/kimcad/ has a single, bounded responsibility. "
        "The table below gives the purpose of each."
    )

    modules = [
        ("pipeline.py", "The orchestrator. Wires every stage, owns the render/gate retry loop, enforces confirm-before-slice."),
        ("ir.py", "The Design-Plan IR (Pydantic). Validates AI JSON before any geometry is written."),
        ("llm_provider.py", "All AI communication — planning, OpenSCAD codegen, photo/sketch vision reads."),
        ("templates.py", "The deterministic template engine. 86 parametric families, pure string substitution."),
        ("openscad_runner.py", "Sanitize-and-render. Blocks dangerous OpenSCAD constructs before the binary runs."),
        ("cadquery_runner.py", "STEP export via CadQuery. Runs trusted template twins — no AI writes CadQuery."),
        ("cadquery_worker.py", "Out-of-process CadQuery worker with restricted builtins."),
        ("validation.py", "Loads and validates the rendered mesh. Checks watertightness, attempts repair."),
        ("printability.py", "The Printability Gate. Pass/warn/fail against the chosen printer and material."),
        ("orientation.py", "Auto-orientation. Rotates the part to its most stable resting face."),
        ("hardening.py", "Pre-slice mesh hardening via Manifold3D into a guaranteed 2-manifold."),
        ("slicer.py", "OrcaSlicer integration. Proves the result carries a real motion-bearing toolpath."),
        ("smart_mesh.py", "Readiness synthesis. Folds the gate, mesh stats, and PrintProof3D into one verdict."),
        ("model_pull.py", "In-app AI model download with progress reporting."),
        ("ollama_runtime.py", "Managed AI engine lifecycle — download, start headless, teardown on exit."),
        ("paths.py", "Dev/installed path seam. KIMCAD_INSTALL_ROOT switches all paths to install mode."),
        ("webapp.py", "The local web layer. A dependency-free stdlib HTTP server over the same pipeline."),
        ("cli.py", "The kimcad command. Wires all the pieces for terminal use."),
        ("design_store.py", "The My Designs persistence layer. Local-first, best-effort, zip-slip safe."),
        ("design_registry.py", "Per-design web state. Owns locks, LRU eviction, geometry-version guards."),
        ("printer_connector.py", "The send-to-printer abstraction and the ensure_sendable() gate."),
        ("bambu_connector.py", "Bambu Lab LAN connector (MQTT-over-TLS + FTPS)."),
        ("octoprint_connector.py", "OctoPrint REST connector."),
        ("moonraker_connector.py", "Moonraker/Klipper REST connector."),
        ("prusalink_connector.py", "PrusaLink REST connector."),
        ("duet_connector.py", "Duet/RepRapFirmware connector."),
        ("marlin_connector.py", "Marlin USB serial connector."),
        ("mcp_server.py", "The printer MCP server (JSON-RPC over stdio)."),
        ("model_advisor.py", "Hardware-aware AI model recommendation."),
        ("config.py", "Configuration loader. Layers default.yaml and local.yaml."),
        ("errors.py", "Typed, user-facing error classes shared across CLI, pipeline, and web."),
    ]
    kv_table(pdf, modules)

    pdf.add_page()
    h2(pdf, "The Template Engine and Catalog")
    body(pdf,
        "The template engine is the part of KimCad that makes live sliders possible. "
        "When your part matches one of the 86 built-in shapes, KimCad never calls the AI — "
        "it generates the OpenSCAD geometry by pure substitution from a typed template."
    )
    body(pdf,
        "Every template has bounded, named parameters (width, height, wall thickness, etc.), "
        "an analytic bounding box that the Printability Gate asserts against, "
        "and a CadQuery twin for the editable STEP export. "
        "Re-rendering at a new parameter value takes well under a second."
    )
    body(pdf, "The catalog spans eight theme groups:")
    bullet(pdf, [
        "Boxes and enclosures — project boxes, snap boxes, tubes, containers",
        "Brackets and hardware — L-brackets, standoffs, plates, washers, fastener blanks",
        "Organizers — drawer dividers, Gridfinity bins and baseplates, raceways",
        "Hooks and clips — wall hooks, pegboard hooks, cable clips",
        "Kim's decor world — frames, picture hangers, dishes and trays, candle holders, "
        "plant holders, planters, ornaments, gift boxes, stands, ledges, rails",
        "Engineering hardware — Gridfinity, VESA mounts, thread-relief nut/bolt blanks",
        "Outdoor and structural — slanted sign holders, Z-clip panel hangers",
        "Utility — funnels, bar pulls, spool holders",
    ])
    note_box(pdf,
        "Templates are honest about their tier. 'Benchmarked' means what-you-set-is-what-you-get, "
        "measured on the real pipeline. 'Baseline' means real, verified geometry with a "
        "real-world fit/load caveat to check before relying on it — "
        "for example, a thread-relief nut blank or a Gridfinity-compatible footprint."
    )

    h2(pdf, "Trust Boundaries")
    body(pdf,
        "KimCad runs AI-generated code locally. The trust model is explicit:"
    )
    bullet(pdf, [
        "AI-generated OpenSCAD is sanitized before it reaches the binary. "
        "File I/O operations (import, surface), CPU-bomb patterns (minkowski at high resolution), "
        "and any path outside the approved library are blocked — re-prompted, never stripped silently.",
        "No AI ever writes CadQuery. The STEP path uses only KimCad's own trusted template scripts.",
        "The CadQuery worker runs in a separate process with restricted builtins — "
        "no os, no open, no network — as defense-in-depth.",
        "Credentials are read from environment variables only, never stored in config, "
        "never logged, and scrubbed from subprocess environments.",
        "The web layer mints a fresh session token per boot and requires it on every "
        "state-changing request, blocking drive-by cross-origin POSTs.",
        "The photo and sketch vision paths are local-only. The vision model is a dedicated "
        "local provider that cannot be re-routed to a cloud backend.",
    ])

    h2(pdf, "Testing Philosophy")
    body(pdf,
        "The test suite (1,680+ tests as of 0.9.3) is structured to prove the actual runtime "
        "contract, not just that the code runs:"
    )
    bullet(pdf, [
        "The deterministic stages — validation, gate, orientation — are tested directly as pure functions.",
        "The orchestration (pipeline.py) runs with a fake AI provider and a stub renderer against "
        "real trimesh geometry, so the retry loop, gate escape hatch, and confirm-before-slice "
        "rule are proven offline.",
        "Live tests exercise the real OrcaSlicer binary, the real OpenSCAD binary, and the real Ollama "
        "model — the slice result is proven to carry a motion-bearing toolpath.",
        "Every connector is tested against an adversarial runnable simulator with fault injection. "
        "A test that passes against a faithful simulator with Resend:/Error: faults is a test that "
        "earns its green.",
        "The template engine is benchmarked: every family, re-rendered at new values, watertight "
        "at its declared envelope, byte-deterministic, with no model call.",
        "The version is single-sourced (pyproject.toml) and enforced by a test that scans every "
        "surface — CLI, API, installer, Settings UI — for the canonical string.",
    ])


# ── main ─────────────────────────────────────────────────────────────────────

def build():
    pdf = KimCadPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(10, 18, 10)

    cover(pdf)
    toc(pdf)
    part1(pdf)
    part2(pdf)
    part3(pdf)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(f"OK Written {OUT} ({OUT.stat().st_size // 1024} KB, {pdf.page_no()} pages)")


if __name__ == "__main__":
    build()
