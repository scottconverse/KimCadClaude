# Part-library catalog

KimCad's deterministic template engine ships **86 parametric part families** — **39
benchmarked** and **47 baseline** (the two honesty tiers are explained below). Pick one in the
in-app **Part library** (search, then click a card) and KimCad designs it on the spot, then you
shape it with the live sliders like any other part. You never have to use the library — describing
a part in your own words works just as well, and KimCad designs plenty of shapes the library
doesn't list.

> **This catalog is generated from the live registry.** The families, counts, tiers, and
> summaries below are read from `kimcad.templates.default_registry()` — the same source the app
> and the `GET /api/templates` endpoint use — so they cannot drift from what actually ships.
> Regenerate / verify the counts with:
>
> ```
> .venv/Scripts/python.exe -c "from kimcad.templates import default_registry; \
>   fams=default_registry().families(); \
>   from collections import Counter; \
>   print(len(fams), Counter(f.tier for f in fams))"
> # -> 86 Counter({'baseline': 47, 'benchmarked': 39})
> ```

## The two honesty tiers

Every family carries a **tier** that says, honestly, how much you can trust the printed result
without further checks:

- **benchmarked** — *what you set is what you get.* Change a dimension, get exactly that
  dimension. There's no hidden caveat; these parts are unbadged in the library browser.
- **baseline** — *real, gate-verified geometry, but with a real-world fitness caveat to confirm
  before you rely on it.* The shape is just as real and just as checked as a benchmarked part; the
  tier flags that the part has to *fit something in the physical world* — a screw, a glass tube, a
  phone, a Gridfinity drawer, a monitor's mounting holes — or carry a load, and only you can
  confirm that fit. Examples: the printed nut and bolt are **thread-relief only** (a smooth bore /
  smooth shaft, *not* a certified thread); a Gridfinity bin/baseplate is **compatible** with the
  42 mm system; a VESA plate gives you the standard hole **pattern** to match your device; a
  candle or vase holder is sized to a **press / slip fit** around a physical object. In the
  library browser these parts wear a **"Verify before use"** badge — when you see it, measure
  twice or print a quick test before relying on the fit.

**The tier is inert to the Printability Gate.** Whatever its label, *every* family is
render-verified against its declared **analytic bounding box** by a real OpenSCAD render, and
carries a trusted **CadQuery `.STEP` twin** built from KimCad's own code (never AI-written). The
tier is about real-world *fitness*, never about whether the geometry is sound.

The table column **Tier** below uses these two values; the **Part** column is the family's primary
name (what you'd type or search for in the library).

---

### Core parts (boxes, hooks, brackets & organizers)
*10 families — 10 benchmarked, 0 baseline*

| Part | Tier | What it is |
|---|---|---|
| box | benchmarked | A closed, watertight box sized to its outer envelope. |
| open box | benchmarked | An open-top walled container (tray / bin). |
| enclosure | benchmarked | A two-part enclosure sized from its internal volume; walls add on every side. |
| tube | benchmarked | A ring / cylindrical spacer or standoff. |
| hook | benchmarked | A wall-mounted hook: a screwed-on back plate with an arm projecting out. |
| cable clip | benchmarked | A screw-down cable / cord saddle clip. |
| drawer divider | benchmarked | A drawer divider — a frame split into equal compartments by cross walls. |
| pegboard hook | benchmarked | A hook with two rear pegs that seat into a standard pegboard. |
| spool holder | benchmarked | A wall bracket a filament spool slides onto, with an end stop. |
| l bracket | benchmarked | An L-shaped mounting bracket with screw holes through both arms. |

### Frames
*6 families — 1 benchmarked, 5 baseline*

| Part | Tier | What it is |
|---|---|---|
| picture frame | baseline | A picture frame with a back rabbet that seats glass, art, and backing. |
| certificate frame | baseline | A document/diploma frame (wider border, portrait default). |
| mat board | benchmarked | A flat framing mat with a centered window opening. |
| floating frame | baseline | A floating frame: the art sits on a recessed shelf with a shadow gap. |
| shadow box | baseline | A deep shadow box: solid back, display cavity, and a front glass rabbet. |
| lithophane frame | baseline | A backlit lithophane frame with a panel rebate and an LED light gap. |

### Hangers
*3 families — 0 benchmarked, 3 baseline*

| Part | Tier | What it is |
|---|---|---|
| sawtooth hanger | baseline | A sawtooth picture hanger — a nail catches any tooth to level the frame. |
| keyhole hanger | baseline | A flush keyhole plate: drop over a screw head and slide down to lock. |
| floating shelf bracket | baseline | A concealed floating-shelf support: a wall plate with rods into the shelf. |

### Dishes & holders
*13 families — 7 benchmarked, 6 baseline*

| Part | Tier | What it is |
|---|---|---|
| ring dish | benchmarked | A round trinket / ring dish: a shallow well in a solid puck, with an optional center spike. |
| incense cone holder | benchmarked | A round incense-cone burner dish with an ash moat around a dimpled pedestal. |
| incense stick holder | baseline | A low ash boat for stick incense: a trough along its length with a row of stick bores. |
| catchall tray | benchmarked | A rounded-rect catch-all valet tray: a walled pocket with a solid floor. |
| soap dish | benchmarked | A rectangular draining soap dish: a pocketed tray with floor drain ribs and holes. |
| handled tray | benchmarked | A shallow serving tray with two integral grip cut-outs in the end walls. |
| zen garden | benchmarked | A shallow zen sand garden tray: a rounded-rect tray on four short corner feet. |
| tealight holder | baseline | A tealight / votive holder: a round body with a top pocket that seats a standard ~38-40 mm metal tealight cup. |
| taper candle holder | baseline | A weighted taper candle holder: a solid round base with a centered top socket that grips a standard ~22 mm taper candle. |
| luminary base | baseline | A weighted candle/LED luminary base: an outer cylinder with a center puck cavity and a wider top rim ledge. |
| bud vase | baseline | A printed sleeve that seats a glass test tube as the watertight vessel (bud vase / reed-diffuser / dry-stem sleeve): an outer cylinder with a vertical bore. |
| pencil cup | benchmarked | A straight-walled round pen / pencil / brush cup: an outer cylinder hollowed to a deep pocket over a thick floor. |
| propagation station | baseline | A test-tube propagation station: a horizontal bar on two end legs, with a fixed row of vertical tube bores for plant cuttings. |

### Planters
*4 families — 4 benchmarked, 0 baseline*

| Part | Tier | What it is |
|---|---|---|
| planter pot | benchmarked | A tapered plant pot: a frustum wall (wider at the rim) over a flat floor, with a center drain hole. |
| planter saucer | benchmarked | A shallow round drip tray under a plant pot: a catch pocket inside a full-height outer rim, with a raised inner ring the pot rests on above collected water. |
| bonsai pot | benchmarked | A shallow rectangular bonsai tray-pot: a walled soil pocket over a fixed grid of base drain holes. |
| succulent pot | benchmarked | A small faceted (n-gon) succulent pot: a straight-walled prism hollowed to a soil pocket with a center drain hole. |

### Ornaments & boxes
*9 families — 3 benchmarked, 6 baseline*

| Part | Tier | What it is |
|---|---|---|
| coaster | benchmarked | A round drink coaster with a shallow raised rim to contain condensation: a solid round body with a recessed top pocket inside a rim wall. |
| trivet | baseline | A flat square hot-pad: a square slab with a fixed grid of square through-slots, raised on four short corner feet. |
| bookend | baseline | An L-shaped bookend: a vertical upright slab joined to a horizontal base foot. |
| geometric wall tile | benchmarked | A square modular wall-art tile: a flat backer with a raised perimeter border so tiles register edge-to-edge. |
| tile connector clip | baseline | A flat dogbone connector clip whose two end tongues slot into grooves on two adjoining tiles. |
| ornament | benchmarked | A flat round medallion / ornament disc with a top hanging hole, ready for a relief or engraving. |
| ornament cap | baseline | A press-fit cap that plugs a sphere ornament, topped by a vertical hang loop. |
| gift box lid | baseline | A telescoping two-part gift box printed side by side: a tray base and an overlapping shoulder lid. |
| jar lid | baseline | A round press/recess jar lid: a top disc with a down-skirt ring that caps a jar rim. |

### Stands & ledges
*9 families — 5 benchmarked, 4 baseline*

| Part | Tier | What it is |
|---|---|---|
| easel | benchmarked | A fixed-angle tabletop easel: a triangular wedge with a front lip to prop a framed photo, tile, or sign. |
| display riser | benchmarked | A tiered stepped pedestal that elevates a displayed piece: stacked centered slabs, bottom widest, each stepped in. |
| slanted sign holder | baseline | A weighted base block with an interior angled slot that holds a menu / price card at a readable backward tilt. |
| desk nameplate holder | baseline | A low desk base with a rear leaning wedge: an engraved name strip drops into a near-vertical slot. |
| place card holder | benchmarked | A small base that stands a folded place card upright in a thin vertical slot. |
| picture ledge | baseline | A long narrow wall ledge with a raised front lip that holds framed art leaning against the wall. |
| peg hook rail | benchmarked | A wall back-bar with a fixed row of evenly spaced projecting pegs for coats, towels, or keys. |
| j hook | benchmarked | A decorative J-profile robe/towel hook: an extruded J ribbon (back tab, forward bend, an up catch) with a back screw tab. |
| plate display stand | baseline | An upright display stand that grips a decorative plate or tile on edge: a flat base with a fixed-lean back panel carrying a plate groove. |

### Frame joinery
*10 families — 0 benchmarked, 10 baseline*

| Part | Tier | What it is |
|---|---|---|
| canvas stretcher corner | baseline | An L-shaped mitered corner key that squares and joins two canvas stretcher bars at 90 degrees, with underside tongues that slot into the bar ends. |
| frame corner clamp | baseline | A right-angle frame glue-up jig: a corner block with two perpendicular jaws holding two mitered pieces square. |
| frame corner joiner | baseline | A flat under-side spline plate that screws across a 45-degree frame miter to lock two moulding lengths. |
| frame turn button | baseline | A rotating frame turn-button: a rounded bar with a center pivot bore and a raised boss that screws to a frame back and pivots to retain the backing board. |
| frame backing clip | baseline | A flat stepped offset clip that wedges between a frame rabbet and the backing board to retain it without screws. |
| wire loop hanger | baseline | A screw-on plate with an upstanding triangular wire bail for hanging framed art. |
| z clip | baseline | The wall half of a Z-profile interlocking panel clip; the mating half hangs a flat sign/mirror flush. |
| french cleat pair | baseline | A matched pair of interlocking 45-degree wall cleats (wall half + art half), printed side by side, to hang and self-level a piece. |
| picture rail hook | baseline | An over-the-molding picture-rail hook: an inverted-J that hooks over the rail without nails, with a cord eye. |
| d ring strap hanger | baseline | A screw-down strap plate with a fixed printed D-ring loop for hanging heavier framed art. |

### General hardware
*22 families — 9 benchmarked, 13 baseline*

| Part | Tier | What it is |
|---|---|---|
| washer | benchmarked | A flat washer / shim: a disc with a concentric through bore, extruded to thickness. |
| dowel pin | benchmarked | A solid alignment dowel pin — a plain cylinder (diameter x length). |
| bumper foot | benchmarked | A cabinet/appliance bumper foot: a short cylinder with a centered counterbored screw hole from the bottom. |
| mounting flange | baseline | A round pipe/mounting flange: a disc with a centered bore and 4 bolt holes on a fixed bolt-circle. |
| plate | benchmarked | A rectangular mounting pad with a single centered vertical through-hole. |
| faceplate | benchmarked | A blanking faceplate / cover plate: a thin slab with four corner screw holes. |
| vesa plate | baseline | A VESA monitor-mount adapter plate: a slab with a centered square 4-hole VESA pattern. |
| corner gusset | benchmarked | A triangular corner brace: a right-triangle web braced across its width, with a screw hole through each leg. |
| pcb standoff | baseline | A PCB mounting base: a base plate with four inset corner standoffs, each pierced by a through screw hole. |
| french cleat rail | baseline | The wall half of a 45-degree French cleat: a beveled wall rail with screw holes that a matching cleat on the hung object drops onto. |
| heatset insert boss | baseline | A heat-set insert boss: a cylindrical boss with a blind top pocket sized for a brass heat-set threaded insert. |
| snap fit box | baseline | A two-part friction/snap-fit box: an open-top walled base plus a mating lid that drops over the base rim, printed side by side along X. |
| hinged lid box | baseline | A small parts/tackle box: an open-top base and a separate press-on lid with a downward inner lip that seats inside the base rim, printed side by side. |
| slotted clamp block | baseline | A slotted clamp block: a rectangular block split by a top slot to grip a rod or panel, tightened by a cross screw through the jaws. |
| cable raceway | benchmarked | A long open-top U-channel that routes cables along a wall or desk, with a row of mounting holes through the floor. |
| bar pull handle | benchmarked | A bar pull / drawer-pull handle: two cylindrical posts carry a grip rail spanning between them, with a screw hole through each post base. |
| phone dock | baseline | A weighted desk dock for a phone or tablet: an angled back rest the device leans into (a slot of width slot_w) on a heavy base, with a front cable pass-through. |
| funnel | benchmarked | A hollow truncated-cone pour funnel: a wide inlet at the top tapering down to a narrow outlet spout at the bottom, with a bore that runs through both ends. |
| gridfinity bin | baseline | A Gridfinity-compatible storage bin: a grid of 42 mm cells with a stacking lip and a scooped interior. |
| gridfinity baseplate | baseline | A Gridfinity-compatible baseplate: a grid of 42 mm cells with a cradle each bin foot drops into. |
| hex nut | baseline | A hex nut blank: a hex prism with a smooth center bore. Thread relief only — not a real thread; the bore is a smooth relief for a tapped insert or a printed-thread test. |
| hex bolt | baseline | A hex-head bolt blank: a hex head on a smooth cylindrical shaft. Thread relief only — a smooth shaft, not a real thread. |

---

These families live in two OpenSCAD library files — `library/dishes.scad` (the decor world:
frames, hangers, dishes, holders, planters, ornaments, stands, joinery) and `library/parts.scad`
(engineering hardware: washers, plates, brackets, standoffs, boxes, raceways, Gridfinity,
fasteners) — plus the original seed modules behind the core parts. See
[ARCHITECTURE.md](../ARCHITECTURE.md) for how the template engine emits and verifies each one, and
the [CHANGELOG](../CHANGELOG.md) `#19` entries for the slice-by-slice history of the expansion.
