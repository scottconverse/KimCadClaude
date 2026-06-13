# #19 — Frame / Zen / Decor Catalog (Kim's design world)

> Source: the `frame-zen-family-discovery` workflow (2026-06-13), per Scott's directive
> "find more families … Frames (like Kim's Zen design world work) … as many as you can."
> 4 domain lenses → ~51 raw candidates → vetted to **57 buildable families** against the real
> KimCad schema (linear analytic bbox, OpenSCAD primitives, 170³ envelope, CadQuery twin,
> honest tier). 14 dropped (intractable / duplicate / alias-collision). This is the
> implementation reference for the expansion slices; exact defaults/bbox constants are
> render-pinned per family during TDD (the per-family RECIPE in `kc-19-template-breadth.md`).

**Tier rule (unchanged):** `benchmarked` = what-you-set-is-what-you-get; `baseline` = real,
gate-verified geometry but a fitness caveat to check (a press/slip fit to a physical object —
glass, tealight cup, glass tube, jar mouth; a hole/spacing PATTERN to match; or a load /
"fits-my-moulding" claim). Every family is render-verified against its bbox regardless of tier.

**Alias discipline:** every alias was normalized + collision-checked against the existing 7 +
planned 25. Words already owned (hook/coat hook, standoff/spacer/sleeve/ring/bushing, cleat,
bracket/corner/angle/shelf bracket, plate/mounting plate, panel/cover plate, flange,
bumper/foot, tray/bin/container, divider, stand/dock, spout, handle/grip, raceway, clamp) were
trimmed. Two new families deliberately avoid them with distinct geometry: `j_decor_hook`
(extruded J, not plate+arm — avoids wall_hook's "hook") and `bookend` (no "bracket"/holes).

---

## Batch A — frames (9) · `frames.scad` · twin: box.cut(box).cut(rabbet)

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| picture_frame | baseline | [opening_w+2·border, opening_h+2·border, depth] | picture frame, photo frame, art frame |
| floating_frame | baseline | [opening_w+2·gap+2·lip_w, opening_h+2·gap+2·lip_w, depth] | floating frame, float frame |
| shadow_box_frame | baseline | [opening_w+2·border, opening_h+2·border, cavity_depth+rabbet+back_t] | shadow box, memory box frame |
| certificate_frame | baseline | [opening_w+2·border, opening_h+2·border, depth] | certificate frame, diploma frame |
| mat_board | benchmarked | [mat_w, mat_h, mat_t] | mat board, frame mat, photo mat |
| collage_frame | baseline | [cols·cell_w+(cols+1)·bar_w, rows·cell_h+(rows+1)·bar_w, depth] (int count) | collage frame, multi photo frame |
| mini_desktop_frame | baseline | [opening_w+2·border, opening_h+2·border+foot_depth, depth+foot_h] | mini frame, instax frame |
| lithophane_frame | baseline | [outer_w, outer_h, face_rim_t+panel_t+light_gap] | lithophane frame, backlit frame |
| suncatcher_ring | baseline | [od, od, h] | suncatcher, disc frame |

## Batch B — hangers (8) · `hangers.scad` · twin: plate + interior cuts / extruded profile

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| sawtooth_hanger | baseline | [plate_w, plate_t, plate_h+tooth_depth] | sawtooth hanger, frame hanger |
| keyhole_hanger_plate | baseline | [plate_w, plate_t, plate_h] | keyhole hanger, keyhole plate |
| d_ring_strap_hanger | baseline | [strap_w, strap_t+ring_thk, strap_h+ring_od] | d ring hanger, strap hanger |
| wire_loop_hanger | baseline | [base_w, base_t, base_h+loop_height] | wire loop hanger, bail hanger |
| z_clip_panel_hanger | baseline | [length, flange_w+thk, web_h+2·thk] | z clip, z bar hanger |
| art_cleat_pair | baseline | [length, 2·depth+gap, rise] | art cleat, split batten |
| picture_rail_hook | baseline | [width, throat_depth+thk, body_height+throat_gap] | picture rail hook, moulding hook |
| hidden_rod_shelf_bracket | baseline | [plate_w, plate_t+rod_length, plate_h] | floating shelf bracket, hidden shelf bracket |

## Batch C — shelf / ledge / rail (3) · `ledges.scad`

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| picture_ledge_shelf | baseline | [length, depth, back_height] (gap: lip≤back) | picture ledge, art ledge |
| peg_hook_rail | benchmarked | [length, bar_t+peg_length, bar_h] (int peg_count) | peg rail, shaker peg rail |
| j_decor_hook | benchmarked | [width, thk+reach, back_height+catch_rise] (pin back≥catch) | robe hook, towel hook, j hook |

## Batch D — stands / easels (6) · `stands.scad` · twin: wedge prism + slot cut

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| wedge_easel_stand | benchmarked | [width, base_depth, back_height+lip_height] (pin lip≤back) | easel, tabletop easel, sign easel |
| plate_display_stand | baseline | [base_w, base_depth+back_lean_offset, base_h_const+back_height] | plate display stand, tile display stand |
| display_riser | benchmarked | [base_w, base_d, tiers·tier_t] (int tiers, step_in gap) | display riser, pedestal, plinth |
| slanted_sign_holder | baseline | [base_w, base_depth+back_margin, base_height] | sign holder, menu holder |
| desk_nameplate_holder | baseline | [base_w, base_depth, base_height+slot_back_offset] | nameplate holder, name plate holder |
| place_card_holder | benchmarked | [base_w, base_depth, base_height] | place card holder, table number holder |

## Batch E — zen trays / dishes (7) · `dishes.scad` · twin: body − pocket (+feet/ribs)

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| zen_garden_tray | benchmarked | [length, width, wall_h+foot_h] | zen garden, sand tray, rake garden |
| incense_stick_holder | baseline | [length, width, h] | incense holder, incense boat |
| incense_cone_holder | benchmarked | [dish_d, dish_d, h] | incense cone holder, cone burner |
| ring_dish | benchmarked | [od, od, h+spike_h] (spike default 0) | ring dish, jewelry dish, trinket dish |
| catchall_tray | benchmarked | [length, width, h] | catchall, valet tray, edc tray |
| soap_dish | benchmarked | [length, width, h] | soap dish, draining soap dish |
| handled_tray | benchmarked | [length, width, h] | handled tray, serving tray |

## Batch F — holders / cups (6) · `vessels.scad` · twin: circle.extrude.cut(circle)

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| tealight_holder | baseline | [od, od, h] (pocket clamped) | tealight holder, votive holder |
| taper_candle_holder | baseline | [base_d, base_d, h] | taper candle holder, candlestick |
| luminary_base | baseline | [outer_d, outer_d, height] (cavity gap-clamped) | luminary base, candle base |
| bud_vase_sleeve | baseline | [od, od, h] (glass insert holds water) | bud vase, test tube vase, reed diffuser |
| pencil_cup | benchmarked | [od, od, h] (square variant side=od) | pen cup, pencil cup, brush holder |
| propagation_station | baseline | [length, depth, h+leg_h] (int tube_count) | propagation station, plant propagation rack |

## Batch G — planters (4) · `planters.scad` · twin: frustum/cylinder − pocket + drains

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| planter_pot | benchmarked | [top_d, top_d, h] (pin top_d≥bottom_d) | planter, plant pot, flower pot |
| planter_saucer | benchmarked | [od, od, h] | plant saucer, drip tray |
| bonsai_pot | benchmarked | [length, width, h] | bonsai pot, penjing pot |
| succulent_pot | benchmarked | [od, od, h] | succulent pot, cactus pot |

## Batch H — flat decor (5) · `flatdecor.scad`

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| coaster_with_rim | benchmarked | [od, od, h] (square side=od) | coaster, drink coaster |
| trivet | baseline | [size, size, plate_t+foot_h] (PLA heat caveat) | trivet, hot pad |
| bookend | baseline | [base_len, width, height] | bookend, book stop |
| geometric_wall_tile | benchmarked | [side, side, base_t+border_h] (border gap) | wall tile, art tile, modular tile |
| tile_connector_clip | baseline | [length, width, thick] (neck gap) | tile connector, tile clip |

## Batch I — ornaments / packaging (4) · `ornaments.scad`

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| ornament_blank | benchmarked | [diameter, diameter, thick] | ornament, medallion, gift tag |
| ornament_cap | baseline | [cap_d, cap_d, cap_h+loop_od] (loop≤cap_d) | ornament cap, bauble topper |
| gift_box_lid | baseline | [2·width+const, depth+const, lid_h] (pin lid≥base) | gift box, presentation box, keepsake box |
| jar_lid | baseline | [outer_d, outer_d, top_t+skirt_h] (skirt gap) | jar lid, candle lid, press lid |

## Batch J — frame joinery (5) · `framejoinery.scad`

| family | tier | bbox | aliases (first) |
|---|---|---|---|
| canvas_stretcher_corner | baseline | [arm, arm, bar_t+tongue_h] | stretcher corner, canvas stretcher key |
| frame_corner_clamp | baseline | [jaw_l+corner, jaw_l+corner, jaw_h] | frame corner clamp, miter clamp |
| frame_corner_joiner | baseline | [plate, plate, plate_t+rib_h] | frame corner joiner, miter joiner |
| frame_turn_button | baseline | [button_l, button_w, button_t+boss_h] | turn button, backing retainer |
| frame_backing_clip | baseline | [clip_l, clip_w, clip_t+step] | frame backing clip, offset clip |

---

## Dropped (14, recorded for honesty)

Intractable: `folding_aframe_easel` (trig bbox + printed hinge needs bridges → use the
fixed-angle `wedge_easel_stand`), `scroll_corbel_bracket` (organic S-volute, no primitive).
Duplicates/merges: `reed_diffuser_vase`→bud_vase_sleeve; `sign_easel`/`easel_frame`/
`tabletop_frame_stand`→wedge_easel_stand; 2nd `display_riser` copy; `acrylic_standoff_mount`/
`panel_standoff_mount` (tube-family duplicates + standoff/spacer alias collision);
`frame_bumper` (= bumper_foot). Plus alias trims on survivors.

## Coverage gaps (clean future adds, not yet built)

`clock_frame` (bezel + quartz-movement bore), `mirror_frame` (route "mirror" → picture_frame
rabbet), `multi_tealight_tray` (row of pockets, à la collage_frame↔picture_frame),
`wind_chime_topper` / `hanging_mobile_disc` (disc + hole ring), decorative `switch_plate`
(likely defer to faceplate to avoid panel/cover-plate collision), `photo_block` (block + thin
front slot). Add opportunistically if cheap during the relevant batch.
