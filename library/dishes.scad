// dishes.scad — zen / desktop trays, dishes, and incense holders. Units mm.
// Built corner-at-origin (cube / offset(square)) so the bounding box is the exact envelope;
// cylinders are XY-centered like OpenSCAD's cylinder(). Each module documents its analytic
// bounding box; the family registry pins the same formula and a real render confirms it (#19).
//
//   ring_dish(od, h, wall, well_depth, spike_h, spike_d)        bbox = [od, od, h + spike_h]
//   incense_cone_holder(dish_d, h, ped_d, moat_depth, dimple_d, rim)   bbox = [dish_d, dish_d, h]
//   incense_stick_holder(length, width, h, hole_d, trough_depth)       bbox = [length, width, h]
//   catchall_tray(length, width, h, wall, corner_r, floor)             bbox = [length, width, h]
//   soap_dish(length, width, h, wall, rib_count)                       bbox = [length, width, h]
//   handled_tray(length, width, h, wall, handle_w)                     bbox = [length, width, h]
//   zen_garden_tray(length, width, wall_h, wall, foot_h, corner_r, foot_d)
//                                                       bbox = [length, width, wall_h + foot_h]
//   tealight_holder(od, h, pocket_d, pocket_h, wall)                   bbox = [od, od, h]
//   taper_candle_holder(base_d, h, bore_d, bore_depth)                 bbox = [base_d, base_d, h]
//   luminary_base(outer_d, height, cavity_d, cavity_h, rim_ledge, ledge_t)   bbox = [outer_d, outer_d, height]
//   bud_vase_sleeve(od, h, bore_d, bore_depth, wall)                   bbox = [od, od, h]
//   pencil_cup(od, h, wall, floor_t)                                   bbox = [od, od, h]
//   propagation_station(length, depth, h, tube_d, leg_h)              bbox = [length, depth, h + leg_h]
//   planter_pot(bottom_d, top_d, h, wall, drain_d)      bbox = [top_d, top_d, h]  (top_d>=bottom_d)
//   planter_saucer(od, h, wall, floor_t, rim_h, rim_w)                 bbox = [od, od, h]
//   bonsai_pot(length, width, h, wall, drain_d)                        bbox = [length, width, h]
//   succulent_pot(od, h, wall, facets, drain_d)                        bbox = [od, od, h]
//   --- #19 slice 7: flat decor + ornaments ---
//   coaster_with_rim(od, h, rim_w, rim_h, floor_t)                     bbox = [od, od, h]
//   hotplate_trivet(size, plate_t, slot_w, foot_h)                     bbox = [size, size, plate_t + foot_h]
//   l_bookend(height, width, base_len, upright_t, base_t)              bbox = [base_len, width, height]
//   geometric_wall_tile(side, base_t, border_w, border_h)             bbox = [side, side, base_t + border_h]
//   tile_connector_clip(length, width, neck_w, thick, tongue_l)        bbox = [length, width, thick]
//   medallion_blank(diameter, thick, hole_d, rim_margin)        bbox = [diameter, diameter, thick]
//   ornament_cap(cap_d, cap_h, neck_d, loop_od, loop_t)               bbox = [cap_d, cap_d, cap_h + loop_od]
//   gift_box_lid(width, depth, base_h, lid_h, wall, gap)   bbox = [2*width + gap, depth, lid_h]  (lid_h>=base_h)
//   jar_lid(outer_d, top_t, skirt_d, skirt_h, skirt_wall)        bbox = [outer_d, outer_d, top_t + skirt_h]  (skirt_d <= outer_d)
//   --- #19 slice 8: stands / ledges / rails ---
//   wedge_easel_stand(width, back_height, base_depth, lip_height, lip_depth)        bbox = [width, base_depth, back_height + lip_height]
//   display_riser(base_w, base_d, tiers, step_in, tier_t)                bbox = [base_w, base_d, tiers * tier_t]
//   slanted_card_easel(base_w, base_depth, base_height, slot_w, back_margin, lean_deg) -> bbox [base_w, base_depth + back_margin, base_height]
//   desk_nameplate_strip_stand(base_w, base_depth, base_height, slot_w, slot_back_offset)        bbox = [base_w, base_depth, base_height + slot_back_offset]
//   place_card_holder(base_w, base_depth, base_height, slit_w, slit_depth, end_margin)   bbox = [base_w, base_depth, base_height]
//   picture_ledge_shelf(length, depth, back_height, lip_height, thk, screw_d)        bbox = [length, depth, back_height]  (lip_height <= back_height)
//   peg_hook_rail(length, bar_h, bar_t, peg_length, peg_d)                bbox = [length, bar_t + peg_length, bar_h]
//   j_decor_hook(width, back_height, reach, catch_rise, thk, screw_d)        bbox = [width, thk + reach, back_height + catch_rise]
//   plate_display_stand(base_w, base_depth, back_height, groove_w, base_h, lean_off)        bbox = [base_w, base_depth + lean_off, base_h + back_height]

module ring_dish(od = 70, h = 18, wall = 3, well_depth = 12, spike_h = 0, spike_d = 6, fn = 96) {
    eps = 0.05;
    well_floor = h - well_depth;                                  // z of the well floor
    union() {
        difference() {
            cylinder(h = h, d = od, $fn = fn);                   // outer dish body
            translate([0, 0, well_floor])                        // top well (over-cut up by eps)
                cylinder(h = well_depth + eps, d = od - 2 * wall, $fn = fn);
        }
        // optional center spike: rises from the well floor to exactly h + spike_h (no protrusion
        // at spike_h = 0). Dropped -eps into the solid floor so it fuses without a z-fight gap.
        translate([0, 0, well_floor - eps])
            cylinder(h = well_depth + spike_h + eps, d = spike_d, $fn = fn);
    }
}

module incense_cone_holder(dish_d = 70, h = 18, ped_d = 28, moat_depth = 8, dimple_d = 12,
                           rim = 4, fn = 96) {
    eps = 0.05;
    moat_outer_d = dish_d - 2 * rim;                             // moat wall, interior to the dish
    difference() {
        cylinder(h = h, d = dish_d, $fn = fn);
        // annular ash moat around the central raised pedestal
        translate([0, 0, h - moat_depth])
            difference() {
                cylinder(h = moat_depth + eps, d = moat_outer_d, $fn = fn);
                translate([0, 0, -eps])
                    cylinder(h = moat_depth + 3 * eps, d = ped_d, $fn = fn);
            }
        // cylindrical socket cut into the pedestal top to seat the incense cone
        translate([0, 0, h - moat_depth])
            cylinder(h = moat_depth + eps, d = dimple_d, $fn = fn);
    }
}

module incense_stick_holder(length = 120, width = 40, h = 12,
                            hole_d = 4, trough_depth = 6, fn = 48) {
    eps = 0.05;
    bores = 5;                                                   // FIXED count — not in the bbox
    end_inset = 0.1 * length;
    side_inset = 0.2 * width;
    trough_w = width - 2 * side_inset;
    trough_l = length - 2 * end_inset;
    bore_y = width - side_inset - hole_d / 2 - 1;                // 1 mm clear of the trough wall
    bore_depth = h - 2;                                          // leaves a >=2 mm floor
    difference() {
        cube([length, width, h]);
        translate([end_inset, side_inset, h - trough_depth])     // ash trough (open top)
            cube([trough_l, trough_w, trough_depth + eps]);
        for (i = [0 : bores - 1]) {                              // vertical stick bores
            x = length / 2 + (i - (bores - 1) / 2) * (length / (bores + 1));
            translate([x, bore_y, h - bore_depth])
                cylinder(h = bore_depth + eps, d = hole_d, $fn = fn);
        }
    }
}

module catchall_tray(length = 120, width = 90, h = 25, wall = 3, corner_r = 8, floor = 2) {
    eps = 0.05;
    inner_r = corner_r - wall;
    difference() {
        // outer rounded-rect prism spanning exactly [0..length, 0..width, 0..h]
        linear_extrude(height = h)
            translate([corner_r, corner_r])
                offset(r = corner_r)
                    square([length - 2 * corner_r, width - 2 * corner_r], center = false);
        // inner rounded pocket: `wall` walls all round, `floor` floor, open top (over-cut +eps)
        translate([wall, wall, floor])
            linear_extrude(height = h - floor + eps)
                offset(r = inner_r)
                    translate([inner_r, inner_r])
                        square([length - 2 * wall - 2 * inner_r,
                                width - 2 * wall - 2 * inner_r], center = false);
    }
}

module soap_dish(length = 110, width = 80, h = 22, wall = 3, rib_count = 4, fn = 32) {
    eps = 0.05;
    pocket_l = length - 2 * wall;
    pocket_w = width - 2 * wall;
    pocket_depth = h - wall;                                     // floor = wall thick
    pitch = pocket_l / (rib_count + 1);
    rib_t = min(1.6, pitch / 4);
    rib_h = min(2.0, pocket_depth / 2);
    drain_d = min(min(3.0, pitch / 4), pocket_w / 2);
    difference() {
        union() {
            difference() {
                cube([length, width, h]);                       // outer envelope
                translate([wall, wall, wall])                   // recessed pocket (open top)
                    cube([pocket_l, pocket_w, pocket_depth + eps]);
            }
            if (rib_count > 0)                                  // raised drainage ribs
                for (i = [1 : rib_count]) {
                    x = wall + i * pitch - rib_t / 2;
                    translate([x, wall, wall - eps])
                        cube([rib_t, pocket_w, rib_h + eps]);
                }
        }
        if (rib_count > 0)                                      // drain holes in the rib gaps
            for (i = [0 : rib_count]) {
                x = wall + i * pitch + pitch / 2;
                translate([x, width / 2, -eps])
                    cylinder(h = wall + 2 * eps, d = drain_d, $fn = fn);
            }
    }
}

module handled_tray(length = 180, width = 120, h = 40, wall = 3, handle_w = 70, fn = 48) {
    eps = 0.05;
    slot_h = h * 0.25;                                          // grip opening height
    slot_r = slot_h / 2;
    slot_z = h - wall - slot_h - h * 0.10;                      // leave a bar above the rim
    difference() {
        cube([length, width, h]);
        translate([wall, wall, wall])                           // recessed pocket (open top)
            cube([length - 2 * wall, width - 2 * wall, h - wall + eps]);
        for (x = [-eps, length - wall - eps]) {                 // grips through the short end walls
            translate([x, width / 2 - handle_w / 2 + slot_r, slot_z + slot_r])
                rotate([0, 90, 0])
                    hull() {
                        cylinder(h = wall + 2 * eps, r = slot_r, $fn = fn);
                        translate([0, handle_w - 2 * slot_r, 0])
                            cylinder(h = wall + 2 * eps, r = slot_r, $fn = fn);
                    }
        }
    }
}

module zen_garden_tray(length = 120, width = 90, wall_h = 18, wall = 3, foot_h = 6,
                       corner_r = 6, foot_d = 10, fn = 48) {
    eps = 0.05;
    foot_r = foot_d / 2;
    inset = corner_r + foot_r;                                  // feet tucked inside the corners
    for (x = [inset, length - inset], y = [inset, width - inset])
        translate([x, y, 0])
            cylinder(h = foot_h + eps, r = foot_r, $fn = fn);   // four corner feet
    translate([0, 0, foot_h])
        difference() {
            linear_extrude(height = wall_h)                     // rounded-rect tray body
                translate([corner_r, corner_r])
                    offset(r = corner_r)
                        square([length - 2 * corner_r, width - 2 * corner_r], center = false);
            translate([0, 0, wall])                             // sand cavity (open top)
                linear_extrude(height = wall_h - wall + eps)
                    translate([corner_r, corner_r])
                        offset(r = corner_r - wall)
                            square([length - 2 * corner_r, width - 2 * corner_r], center = false);
        }
}

// --- #19 slice 6: holders / cups + planters -----------------------------------------

module tealight_holder(od = 50, h = 20, pocket_d = 39.5, pocket_h = 12, wall = 3, fn = 96) {
    eps = 0.05;
    // A tealight / votive holder: a solid round body (od x h) with a centered top pocket
    // (pocket_d x pocket_h) sized to drop in a standard ~38-40 mm metal tealight cup. The
    // `wall` param documents the minimum rim left around the pocket (pocket_d <= od - 2*wall).
    // Both cylinders are XY-centered like OpenSCAD's cylinder(). The pocket over-cuts UP by eps
    // into the open air above the rim (never below into a documented face), so the envelope is
    // exactly [od, od, h] and the floor stays solid.
    difference() {
        cylinder(h = h, d = od, $fn = fn);                       // solid outer body
        translate([0, 0, h - pocket_h])                          // centered tealight pocket
            cylinder(h = pocket_h + eps, d = pocket_d, $fn = fn);
    }
}

module taper_candle_holder(base_d = 70, h = 40, bore_d = 22, bore_depth = 25, fn = 96) {
    eps = 0.05;
    // A weighted taper candle holder: a solid round base (base_d x h) with a centered top
    // bore (bore_d x bore_depth) that grips the tapered foot of a standard ~22 mm taper.
    // Both cylinders are XY-centered like OpenSCAD's cylinder(). The bore over-cuts UP by eps
    // into the open air above the rim (never below into a documented face), so the top face is
    // clean and the envelope is exactly [base_d, base_d, h].
    difference() {
        cylinder(h = h, d = base_d, $fn = fn);                   // solid base body
        translate([0, 0, h - bore_depth])                        // centered candle socket
            cylinder(h = bore_depth + eps, d = bore_d, $fn = fn);
    }
}

module luminary_base(outer_d = 80, height = 40, cavity_d = 52, cavity_h = 26,
                     rim_ledge = 5, ledge_t = 3, fn = 96) {
    eps = 0.05;
    cavity_floor = height - cavity_h;            // z of the puck-cavity floor
    // widened seat at the very top, clamped strictly inside the outer wall so the ledge can
    // never reach the body edge and shave the documented height (keeps the Z bbox exact).
    ledge_d = min(cavity_d + 2 * rim_ledge, outer_d - 2);
    difference() {
        cylinder(h = height, d = outer_d, $fn = fn);          // weighted outer body
        // center cavity for the tealight / LED puck — open top, over-cut up into open air
        translate([0, 0, cavity_floor])
            cylinder(h = cavity_h + eps, d = cavity_d, $fn = fn);
        // top rim ledge: a shallow wider counterbore the puck flange seats on, cut from the
        // top down by ledge_t and over-cut up by eps (never past the outer height)
        translate([0, 0, height - ledge_t])
            cylinder(h = ledge_t + eps, d = ledge_d, $fn = fn);
    }
}

module bud_vase_sleeve(od = 60, h = 120, bore_d = 26, bore_depth = 110, wall = 4, fn = 96) {
    eps = 0.05;
    // The bore never breaks the outer wall: clamped to leave >= wall all round (the registry
    // gap also enforces this, so the clamp is just belt-and-braces and never changes the bbox).
    safe_bore = min(bore_d, od - 2 * wall);
    bore_floor = h - bore_depth;                              // z of the bore floor
    difference() {
        cylinder(h = h, d = od, $fn = fn);                   // outer sleeve body, [od, od, h]
        // vertical bore that seats the glass test tube — over-cut UP into open air by eps so
        // the top face is clean; the floor stays >= (h - bore_depth) of solid material.
        translate([0, 0, bore_floor])
            cylinder(h = bore_depth + eps, d = safe_bore, $fn = fn);
    }
}

module pencil_cup(od = 70, h = 100, wall = 3, floor_t = 4, fn = 96) {
    eps = 0.05;
    // Straight-walled round pen / pencil / brush cup: a solid outer cylinder hollowed to a
    // top-open pocket with a thick floor. The pocket bore is od - 2*wall; its floor sits at
    // z = floor_t. The cut over-cuts UP by eps into the open air above the rim (never past h),
    // so the top face is clean and the bbox is exactly [od, od, h].
    difference() {
        cylinder(h = h, d = od, $fn = fn);                       // outer body, XY-centered
        translate([0, 0, floor_t])                               // top-open pocket
            cylinder(h = h - floor_t + eps, d = od - 2 * wall, $fn = fn);
    }
}

module propagation_station(length = 160, depth = 40, h = 20, tube_d = 24, leg_h = 70, fn = 64) {
    eps = 0.05;
    bores = 5;                                                  // FIXED count — NOT in the bbox
    leg_w = 10;                                                 // fixed end-leg footprint along X
    bore_depth = h - 2;                                         // bore down through the bar, 2 mm floor
    union() {
        difference() {
            // The horizontal bar sits ON TOP of the legs: it spans the full [length, depth]
            // footprint (the X/Y envelope) and rises from z = leg_h to z = leg_h + h (the Z top).
            translate([0, 0, leg_h])
                cube([length, depth, h]);
            // A FIXED row of vertical tube bores, evenly spaced along the bar's length and
            // centered across its depth. Each bore is open at the top (over-cut UP by eps into
            // the air above the rim, never past leg_h + h) and stops 2 mm above the bar floor.
            for (i = [0 : bores - 1]) {
                x = length / 2 + (i - (bores - 1) / 2) * (length / (bores + 1));
                translate([x, depth / 2, leg_h + h - bore_depth])
                    cylinder(h = bore_depth + eps, d = tube_d, $fn = fn);
            }
        }
        // Two end legs, each the full depth, from the floor up INTO the bar (over-cut +eps up so
        // the leg fuses to the bar without a z-fight gap, never past the bar's own solid). The
        // legs sit inside the bar's [0, length] footprint, so they add nothing to the envelope.
        for (x = [0, length - leg_w])
            translate([x, 0, 0])
                cube([leg_w, depth, leg_h + eps]);
    }
}

module planter_pot(bottom_d = 70, top_d = 90, h = 90, wall = 3, drain_d = 12, fn = 96) {
    eps = 0.05;
    // A tapered plant pot: an outer frustum wall (bottom_d at the base, top_d at the rim, h
    // tall) over a flat floor, with a center drain hole. top_d is PINNED >= bottom_d, so the
    // rim is the widest point and sets the footprint -> envelope is exactly [top_d, top_d, h].
    // Cylinders are XY-centered like OpenSCAD's cylinder(); floor thickness = wall.
    floor = wall;                                                // solid floor under the cavity
    in_bot = bottom_d - 2 * wall;                                // inner taper, inset `wall` all round
    in_top = top_d - 2 * wall;
    difference() {
        cylinder(h = h, d1 = bottom_d, d2 = top_d, $fn = fn);    // outer tapered wall
        // inner tapered cavity from the floor up, over-cut +eps UP into the open air above the
        // rim (never past a documented face) so the soil cavity is open-topped and clean.
        translate([0, 0, floor])
            cylinder(h = h - floor + eps, d1 = in_bot, d2 = in_top, $fn = fn);
        // center drain hole: -eps below the floor up through it +eps into the cavity above.
        translate([0, 0, -eps])
            cylinder(h = floor + 2 * eps, d = drain_d, $fn = fn);
    }
}

module planter_saucer(od = 140, h = 22, wall = 4, floor_t = 3, rim_h = 6, rim_w = 4, fn = 96) {
    eps = 0.05;
    pocket_d = od - 2 * wall;                       // catch pocket diameter (inside the outer rim)
    rim_id = pocket_d - 2 * rim_w;                  // inner bore of the raised pot-rest ring
    union() {
        difference() {
            cylinder(h = h, d = od, $fn = fn);                       // outer body / saucer wall (rim)
            translate([0, 0, floor_t])                               // catch pocket (open top, over-cut up by eps)
                cylinder(h = h - floor_t + eps, d = pocket_d, $fn = fn);
        }
        // raised inner rim the pot sits on: an annular ring rising rim_h off the pocket floor,
        // dropped -eps into the floor so it fuses without a z-fight gap; rises into open air,
        // never above the outer rim top (gaps keep rim_h <= h - floor_t).
        translate([0, 0, floor_t - eps])
            difference() {
                cylinder(h = rim_h + eps, d = pocket_d, $fn = fn);
                translate([0, 0, -eps])
                    cylinder(h = rim_h + 3 * eps, d = rim_id, $fn = fn);
            }
    }
}

module bonsai_pot(length = 140, width = 100, h = 35, wall = 4, drain_d = 8, fn = 48) {
    eps = 0.05;
    pocket_l = length - 2 * wall;
    pocket_w = width - 2 * wall;
    pocket_depth = h - wall;                                      // floor = wall thick
    difference() {
        cube([length, width, h]);                                // outer envelope
        translate([wall, wall, wall])                            // recessed soil pocket (open top, +eps into air)
            cube([pocket_l, pocket_w, pocket_depth + eps]);
        for (dx = [length * 0.3, length * 0.7], dy = [width * 0.3, width * 0.7])
            translate([dx, dy, -eps])
                cylinder(h = wall + 2 * eps, d = drain_d, $fn = fn);
    }
}

module succulent_pot(od = 80, h = 75, wall = 3, facets = 8, drain_d = 12, fn = 48) {
    eps = 0.05;
    // A small straight-walled faceted pot for one succulent: an n-gon prism (facets sides)
    // hollowed to a top-open soil pocket above a `wall`-thick floor, with one center drain
    // bored through that floor. The outer prism is OpenSCAD's XY-centered cylinder($fn=facets),
    // so its vertices ride the across-corners circle of diameter `od` — od is therefore the
    // across-corners diameter, and an octagon (the default, facets a multiple of 4) fills the
    // bbox to exactly [od, od, h]. `facets` only re-shapes the prism INSIDE that od circle, so
    // it never pushes the envelope past od (the drawer_divider count-is-inert precedent); the
    // analytic bbox stays [od, od, h]. The pocket bore is od - 2*wall and its floor sits at
    // z = wall; the pocket over-cuts UP by eps into the open air above the rim (never past h).
    // The drain over-cuts -eps below the base and +eps into the pocket so both faces are clean.
    difference() {
        cylinder(h = h, d = od, $fn = facets);                   // outer faceted body
        translate([0, 0, wall])                                  // top-open soil pocket
            cylinder(h = h - wall + eps, d = od - 2 * wall, $fn = facets);
        translate([0, 0, -eps])                                  // center drain through the floor
            cylinder(h = wall + 2 * eps, d = drain_d, $fn = fn);
    }
}

// --- #19 slice 7: flat decor + ornaments -------------------------------------------

module coaster_with_rim(od = 90, h = 6, rim_w = 4, rim_h = 3, floor_t = 2, fn = 96) {
    eps = 0.05;
    pocket_floor = h - rim_h;
    difference() {
        cylinder(h = h, d = od, $fn = fn);
        translate([0, 0, pocket_floor])
            cylinder(h = rim_h + eps, d = od - 2 * rim_w, $fn = fn);
    }
}

module hotplate_trivet(size = 140, plate_t = 6, slot_w = 10, foot_h = 8, fn = 32) {
    eps = 0.05;
    grid = 4;                                                    // FIXED slot grid (grid x grid) — NOT in the bbox
    foot_d = 12;                                                 // fixed corner-foot diameter
    foot_r = foot_d / 2;
    inset = foot_r + 4;                                          // feet tucked inside the corners
    // Fixed grid x grid lattice of square through-slots, centered on a size/5 pitch so the slots
    // scale WITH the plate and never reach an outer edge; the count is inert to the envelope.
    pitch = size / (grid + 1);
    union() {
        // Four corner feet: solid round posts from the floor up INTO the plate (over-cut +eps up
        // so they fuse without a z-fight gap, never past the plate solid). Inside [0,size], so
        // they add nothing to the X/Y envelope.
        for (x = [inset, size - inset], y = [inset, size - inset])
            translate([x, y, 0])
                cylinder(h = foot_h + eps, r = foot_r, $fn = fn);
        // The square hot-pad slab, raised onto the feet: spans [0..size, 0..size] in X/Y and
        // z = foot_h .. foot_h + plate_t (the Z top). The grid x grid square through-slots are
        // cut clean through it — each over-cut by eps BELOW and ABOVE into the open air on both
        // open ends of the slot (never past a solid outer face).
        translate([0, 0, foot_h])
            difference() {
                cube([size, size, plate_t]);
                for (i = [1 : grid], j = [1 : grid])
                    translate([i * pitch - slot_w / 2, j * pitch - slot_w / 2, -eps])
                        cube([slot_w, slot_w, plate_t + 2 * eps]);
            }
    }
}

module l_bookend(height = 150, width = 120, base_len = 110, upright_t = 6, base_t = 5) {
    eps = 0.05;
    // L-shaped bookend: a vertical upright slab joined to a horizontal base foot.
    // Both solid, corner-at-origin. The base over-spans the upright by upright_t in X so the
    // two slabs fuse with no z-fight gap (the overlap is interior to the union, never a face).
    union() {
        // vertical upright slab at the back: x in [0, upright_t], full width, full height.
        // Carries the Z envelope; upright_t stays << base_len so it never touches the X extent.
        cube([upright_t, width, height]);
        // horizontal base foot at z=0: full base_len, full width, base_t thick.
        // Carries the X envelope (base_len) and the Y envelope (width).
        cube([base_len, width, base_t]);
    }
}

module geometric_wall_tile(side = 100, base_t = 3, border_w = 6, border_h = 4, fn = 96) {
    eps = 0.05;
    // A square modular wall-art tile: a flat backer (side x side x base_t) plus a raised square
    // border frame (border_w wide, border_h tall) rising from the backer top. The frame is the
    // outer block minus an inner window; the inner cut over-cuts DOWN -eps into the backer (clean
    // fuse) and UP +eps into open air above the rim, so the envelope is exactly
    // [side, side, base_t + border_h].
    union() {
        cube([side, side, base_t]);                              // flat backer
        translate([0, 0, base_t])
            difference() {
                cube([side, side, border_h]);                    // outer border block
                translate([border_w, border_w, -eps])            // inner window
                    cube([side - 2 * border_w, side - 2 * border_w, border_h + 2 * eps]);
            }
    }
}

module tile_connector_clip(length = 60, width = 24, neck_w = 12, thick = 4, tongue_l = 14) {
    eps = 0.05;
    // A flat dogbone / H connector clip: a bar [length, width, thick] whose two END tongues
    // (each tongue_l long, full width) slot into grooves on two neighboring tiles, joined by a
    // narrowed NECK in the middle (neck_w < width). The neck is formed by cutting a side notch
    // off EACH Y edge across the central span between the tongues. Built corner-at-origin so the
    // envelope is exact: the tongues keep the full width, so the Y bbox stays `width`; the cuts
    // remove (width - neck_w)/2 from each side and over-cut OUTWARD past the side faces (into open
    // air) by eps, never past the documented X/Z faces. bbox = [length, width, thick].
    side = (width - neck_w) / 2;             // material removed off each Y edge to form the neck
    neck_x0 = tongue_l;                      // neck spans [tongue_l .. length - tongue_l] in X
    neck_l = length - 2 * tongue_l;
    difference() {
        cube([length, width, thick]);                       // full flat bar
        // -Y side notch: from the bottom edge inward, over-cut DOWN past the -Y face by eps
        translate([neck_x0, -eps, -eps])
            cube([neck_l, side + eps, thick + 2 * eps]);
        // +Y side notch: from the top edge inward, over-cut UP past the +Y face by eps
        translate([neck_x0, width - side, -eps])
            cube([neck_l, side + eps, thick + 2 * eps]);
    }
}

module medallion_blank(diameter = 60, thick = 4, hole_d = 4, rim_margin = 5, fn = 96) {
    eps = 0.05;
    // A flat round medallion / ornament disc (diameter x thick), XY-centered, with one vertical
    // hanging hole bored through near the top edge. The hole center sits off +Y at
    // y = diameter/2 - rim_margin - hole_d/2, so its top reaches only y = diameter/2 - rim_margin
    // (inside the edge) and the footprint stays [diameter, diameter]. The bore over-cuts -eps
    // below and +eps above into open air, so both faces are clean. bbox = [diameter, diameter, thick].
    hole_y = diameter / 2 - rim_margin - hole_d / 2;
    difference() {
        cylinder(h = thick, d = diameter, $fn = fn);
        translate([0, hole_y, -eps])
            cylinder(h = thick + 2 * eps, d = hole_d, $fn = fn);
    }
}

module ornament_cap(cap_d = 22, cap_h = 12, neck_d = 14, loop_od = 14, loop_t = 4, fn = 96) {
    eps = 0.05;
    // A printed cap that plugs a glass/plastic sphere ornament: a short round cap body
    // (cap_d x cap_h) with a bore (neck_d) up from the bottom to press-fit over the
    // ornament neck, topped by a vertical hang loop (an annular ring, loop_od OD,
    // loop_t thick) the hook/string threads through. Cylinders are XY-centered like
    // OpenSCAD's cylinder(). loop_od is PINNED <= cap_d, so the loop never widens the
    // footprint; the loop rises exactly loop_od above the cap top, so the envelope is
    // exactly [cap_d, cap_d, cap_h + loop_od].
    union() {
        difference() {
            cylinder(h = cap_h, d = cap_d, $fn = fn);            // solid cap body, base at z=0
            // ornament-neck bore: open at the BOTTOM, over-cut DOWN by eps into the open
            // air below the base (never past the cap top), leaving a solid >=2 mm crown.
            translate([0, 0, -eps])
                cylinder(h = cap_h - 2 + eps, d = neck_d, $fn = fn);
        }
        // vertical hang loop: an annulus (loop_od OD, loop_t wall thickness) extruded along
        // its own thickness loop_t then stood vertical with rotate([90,0,0]) so its ring plane
        // is the XZ plane. The loop center is placed so the ring TOP reaches exactly
        // cap_h + loop_od; its bottom arc sits at cap_h, where the ring solid overlaps the cap
        // crown and fuses without a z-fight gap (loop_od <= cap_d guarantees that overlap). The
        // ring spans loop_od in X (<= cap_d) and loop_od in Z; thickness loop_t runs along Y.
        loop_id = loop_od - 2 * loop_t;                          // inner bore of the ring
        translate([0, loop_t / 2, cap_h + loop_od / 2])
            rotate([90, 0, 0])
                linear_extrude(height = loop_t, center = true)
                    difference() {
                        circle(d = loop_od, $fn = fn);
                        circle(d = loop_id, $fn = fn);
                    }
    }
}

module gift_box_lid(width = 90, depth = 70, base_h = 35, lid_h = 40, wall = 2, gap = 8) {
    eps = 0.05;
    fit = 0.4;                  // diametral slip-fit clearance between lid bore and base outer

    // --- tray BASE: an open-top walled box at the origin, floor = wall -------------------
    translate([0, 0, 0])
        difference() {
            cube([width, depth, base_h]);                        // outer body
            translate([wall, wall, wall])                        // cavity (open top, +eps into air)
                cube([width - 2 * wall, depth - 2 * wall, base_h - wall + eps]);
        }

    // --- shoulder LID: an open-top cap at width+gap, taller (lid_h), floor = wall --------
    // The lid bore = base outer footprint + fit, so it drops over the base. The bore stays
    // strictly inside the lid's own outer wall (width footprint), so the X envelope is exactly
    // 2*width + gap and the cavity never breaks the outer face.
    bore_w = width - 2 * wall + fit;                             // lid cavity width  (< width)
    bore_d = depth - 2 * wall + fit;                             // lid cavity depth  (< depth)
    translate([width + gap, 0, 0])
        difference() {
            cube([width, depth, lid_h]);                         // outer cap body
            translate([(width - bore_w) / 2, (depth - bore_d) / 2, wall]) // centered cavity
                cube([bore_w, bore_d, lid_h - wall + eps]);      // open top, +eps into air
        }
}

module jar_lid(outer_d = 70, top_t = 4, skirt_d = 64, skirt_h = 12, skirt_wall = 3, fn = 96) {
    eps = 0.05;
    // A round press/recess jar lid. The top disc (outer_d x top_t) sits on TOP, spanning
    // z = skirt_h .. skirt_h + top_t. A concentric down-skirt ring (skirt_d OD, skirt_wall
    // thick, skirt_h tall) hangs BELOW the disc, z = 0 .. skirt_h, and caps the jar rim — its
    // inner bore (skirt_d - 2*skirt_wall) is the open mouth that drops over the jar neck.
    // skirt_d is pinned <= outer_d (the disc is the widest part), so the envelope is exactly
    // [outer_d, outer_d, top_t + skirt_h]. Both cylinders are XY-centered like OpenSCAD's
    // cylinder(). The skirt rises +eps UP INTO the disc solid so the two fuse without a z-fight gap.
    skirt_id = skirt_d - 2 * skirt_wall;            // open mouth that drops over the jar rim
    union() {
        // top disc, on top
        translate([0, 0, skirt_h])
            cylinder(h = top_t, d = outer_d, $fn = fn);
        // down-skirt annular ring, hanging below the disc (over-cut +eps UP into the disc solid)
        difference() {
            cylinder(h = skirt_h + eps, d = skirt_d, $fn = fn);
            translate([0, 0, -eps])
                cylinder(h = skirt_h + 3 * eps, d = skirt_id, $fn = fn);
        }
    }
}


// --- #19 slice 8: stands / ledges / rails ---
module wedge_easel_stand(width = 80, back_height = 70, base_depth = 60,
                         lip_height = 14, lip_depth = 10) {
    eps = 0.05;
    union() {
        // Wedge body: a right-triangle profile (depth x back_height) extruded across the
        // width. The polygon lies in XY as [[0,0],[base_depth,0],[base_depth,back_height]]
        // and extrudes +Z by width; rotate([90,0,90]) lays it into the output frame so the
        // envelope is exactly [width, base_depth, back_height] corner-at-origin. The vertical
        // BACK face is at Y = base_depth (full back_height); the hypotenuse from the front
        // edge up to the back-top is the inclined REST face a framed photo/tile/sign leans on.
        rotate([90, 0, 90])
            linear_extrude(height = width)
                polygon([[0, 0], [base_depth, 0], [base_depth, back_height]]);
        // Front retaining lip: a full-width rail at the front edge (Y = 0). It shares the
        // Z = 0 base plane with the wedge and overlaps lip_depth into the (thin) front of the
        // wedge body, so the two fuse without a z-fight gap. Its top sits EXACTLY at
        // back_height + lip_height (no +eps past the documented top face), so bbox_z is
        // exactly back_height + lip_height and stays linear; bbox_x/y are unchanged (the lip
        // is within width and within base_depth).
        cube([width, lip_depth, back_height + lip_height]);
    }
}

module display_riser(base_w = 90, base_d = 70, tiers = 4, step_in = 8, tier_t = 8) {
    eps = 0.05;
    n = round(tiers);                                            // integer tier count
    union() {
        for (i = [0 : n - 1]) {
            tw = base_w - 2 * i * step_in;                       // this tier's width  (bottom widest)
            td = base_d - 2 * i * step_in;                       // this tier's depth
            z0 = (i == 0) ? 0 : i * tier_t - eps;                // over-cut down by eps into tier below
            zt = (i + 1) * tier_t;                               // top of this tier
            // centered slab on the base footprint: corner placed so its center sits at
            // (base_w/2, base_d/2); top tier lands at exactly z = n * tier_t.
            translate([(base_w - tw) / 2, (base_d - td) / 2, z0])
                cube([tw, td, zt - z0]);
        }
    }
}

module slanted_card_easel(base_w = 90, base_depth = 40, base_height = 45, slot_w = 4,
                          back_margin = 12, lean_deg = 15, fn = 48) {
    eps = 0.05;
    block_d = base_depth + back_margin;
    a = lean_deg;
    slot_len_x = base_w - 2 * (base_height * 0.12 + 4);
    cut_h = base_height * 1.6;
    px = base_w / 2;
    pz = base_height;
    py = back_margin + slot_w / 2;
    difference() {
        cube([base_w, block_d, base_height]);
        translate([px, py, pz])
            rotate([a, 0, 0])
                translate([-slot_len_x / 2, -slot_w / 2, -cut_h + eps])
                    cube([slot_len_x, slot_w, cut_h + eps]);
    }
}

module desk_nameplate_strip_stand(base_w = 120, base_depth = 45, base_height = 14,
                                  slot_w = 4, slot_back_offset = 30, fn = 48) {
    eps = 0.05;
    // The rear support is a right-triangle prism: its vertical leg at the BACK face (y =
    // base_depth) rises slot_back_offset above the base top; the hypotenuse leans forward down to
    // the base top. lean_run (the wedge's forward reach) is pinned to a fraction of base_depth so
    // the wedge always fits inside the footprint and the analytic bbox stays linear.
    lean_run = base_depth * 0.55;
    lean_a = atan(lean_run / slot_back_offset);          // lean from vertical = the wedge slope
    // The strip slot is a thin near-vertical channel parallel to the wedge hypotenuse, centered
    // across the width. It seats the strip from the base top down into the base.
    slot_seat = base_height * 0.6;                       // how far the slot sinks into the base
    // where the slot's lower (front) edge meets the base top, measured from the front face
    slot_foot_y = base_depth - lean_run * 0.5;

    difference() {
        union() {
            // low base block — full footprint, prints flat on its bottom face
            cube([base_w, base_depth, base_height]);
            // rear leaning wedge: triangle profile in [depth, vertical] coords, extruded along the
            // width then oriented with rotate([90,0,90]) so depth->Y, vertical->Z, width->X (the
            // per-axis orientation proven by a render probe). The base foot over-laps the base top
            // by eps so the two fuse; the apex lands exactly at base_height + slot_back_offset
            // (envelope-exact in Z).
            translate([0, 0, base_height])
                rotate([90, 0, 90])
                    linear_extrude(height = base_w)
                        polygon([
                            [base_depth - lean_run, -eps],            // front foot, on base top
                            [base_depth,            -eps],            // back foot, on base top
                            [base_depth,            slot_back_offset] // back apex (Z top)
                        ]);
        }
        // near-vertical strip slot: a thin tall box leaning back at the wedge angle. Built upright,
        // rotated -lean_a about X so it leans the same way as the hypotenuse, and positioned so its
        // mouth opens at the top and it sinks slot_seat into the base. It over-cuts UP into the
        // open air above the apex and only DOWN into the solid base/wedge.
        slot_run = (base_height + slot_back_offset) + slot_seat + 2 * eps;
        translate([(base_w - slot_w) / 2, slot_foot_y, -slot_seat])
            rotate([-lean_a, 0, 0])
                cube([slot_w, eps + base_depth, slot_run]);   // thin in X (slot_w), tall in Z
    }
}

module place_card_holder(base_w = 60, base_depth = 25, base_height = 18,
                         slit_w = 2.5, slit_depth = 12, end_margin = 6) {
    eps = 0.05;
    slot_l = base_depth - 2 * end_margin;                       // slot runs along Y, ends interior
    slot_x0 = (base_w - slit_w) / 2;                            // centered across the width
    difference() {
        cube([base_w, base_depth, base_height]);               // base block, corner-at-origin
        // thin vertical card slot: opens at the TOP (over-cut +eps up into open air), drops down
        // slit_depth, fully interior in X (centered) and Y (end_margin both ends), never the bottom.
        translate([slot_x0, end_margin, base_height - slit_depth])
            cube([slit_w, slot_l, slit_depth + eps]);
    }
}

module picture_ledge_shelf(length = 160, depth = 70, back_height = 40, lip_height = 15,
                           thk = 4, screw_d = 4, fn = 32) {
    eps = 0.05;
    clear = 0.2;
    difference() {
        union() {
            // back wall — vertical slab at the -Y face, full height
            cube([length, thk, back_height]);
            // floor — horizontal slab across the full depth, sitting on the bed
            cube([length, depth, thk]);
            // front lip — vertical slab at the +Y front edge, lip_height tall.
            // base overlaps the floor by eps (down into solid), so it fuses cleanly and
            // its top lands exactly at lip_height (<= back_height, so never past Z).
            translate([0, depth - thk, thk - eps])
                cube([length, thk, lip_height - thk + eps]);
        }
        // two back-wall screw holes through the back wall (along +Y), centered in the wall
        // height; over-cut eps on both faces so both ends are clean (never past X faces).
        for (x = [length * 0.25, length * 0.75])
            translate([x, -eps, back_height / 2])
                rotate([-90, 0, 0])
                    cylinder(h = thk + 2 * eps, d = screw_d + clear, $fn = fn);
    }
}

module peg_hook_rail(length = 160, bar_h = 40, bar_t = 12, peg_length = 35, peg_d = 12,
                     peg_count = 5, fn = 32) {
    eps = 0.05;
    union() {
        // back bar: corner-at-origin, X = length, Y = bar_t, Z = bar_h
        cube([length, bar_t, bar_h]);
        // a FIXED row of evenly-spaced horizontal +Y pegs, centered in Z. Each peg's base
        // overlaps INTO the bar by eps (never past the -Y wall face), so the far tip lands
        // exactly at bar_t + peg_length (envelope-exact). peg_count is fixed internally and
        // inert to the envelope (the hidden_rod_shelf_bracket / propagation_station precedent);
        // peg_d is pinned <= bar_h (peg stays inside the bar face in Z) and <= length/3 (the
        // inset end pegs never overhang the X envelope), so the bbox stays linear.
        for (i = [0:peg_count - 1])
            translate([length / 2 + (i - (peg_count - 1) / 2) * (length / (peg_count + 1)),
                       bar_t - eps, bar_h / 2])
                rotate([-90, 0, 0])
                    cylinder(h = peg_length + eps, d = peg_d, $fn = fn);
    }
}

module j_decor_hook(width = 60, back_height = 70, reach = 22, catch_rise = 18, thk = 5,
                    screw_d = 4, fn = 32) {
    // A decorative J/U-profile robe/towel hook. A constant-thickness J ribbon is traced in the
    // (Y, Z) plane as one watertight polygon (back tab + forward foot/bend + an up catch at the
    // front) and extruded across the hook WIDTH; a screw hole is drilled through the back tab so
    // it mounts to a wall. Bounding box = [width, thk + reach, back_height + catch_rise].
    // back_height is pinned >= catch_rise upstream, so the front-catch tip (at back_height +
    // catch_rise) is always the global Z max and the envelope stays the linear sum (no max()).
    eps = 0.05;
    clear = 0.2;
    difference() {
        // linear_extrude raises the (Y,Z) profile +Z by width; rotate([90,0,90]) maps the
        // extrude axis -> +X (width), the profile's local-x -> +Y (thk+reach) and local-y ->
        // +Z (back_height+catch_rise), so the rendered extents equal the declared bbox.
        rotate([90, 0, 90])
            linear_extrude(height = width)
                polygon([
                    [0, 0],                                    // back-bottom (outer)
                    [thk + reach, 0],                          // front-bottom (foot, full reach)
                    [thk + reach, back_height + catch_rise],   // catch tip (Z max, outer)
                    [reach, back_height + catch_rise],         // catch tip (inner)
                    [reach, thk],                              // inner: catch meets foot top
                    [thk, thk],                                // inner: foot meets back tab
                    [thk, back_height],                        // back tab top (inner)
                    [0, back_height],                          // back tab top (outer)
                ]);
        // screw hole through the back tab into the wall: drilled along +Y (front-to-back through
        // the thk-thick tab), centered across the width (X) and high on the tab (Z). Over-cuts
        // both tab faces by eps so no skin is left, never past the documented outer faces.
        translate([width / 2, -eps, back_height * 0.72])
            rotate([-90, 0, 0])
                cylinder(h = thk + 2 * eps, d = screw_d + clear, $fn = fn);
    }
}

module plate_display_stand(base_w = 90, base_depth = 70, back_height = 90, groove_w = 8,
                           base_h = 10, lean_off = 24, fn = 48) {
    // An upright display stand that grips a decorative plate / tile on edge.
    //   base_w      X footprint of the base slab and the back upright.
    //   base_depth  Y footprint of the base slab.
    //   back_height rise of the leaning back panel above the base top.
    //   groove_w    width of the plate-gripping groove cut into the front face of the back.
    //   base_h      FIXED base slab thickness (Z constant; not a slider).
    //   lean_off    FIXED rearward offset of the back's top vs its bottom (sets the fixed lean).
    //
    // Prints flat on the base (Z=0). The back leans BACK (+Y) at a FIXED shallow angle
    // (atan(lean_off/back_height) ~ 15 deg at the defaults), so the wall self-supports as it
    // rises — no bridge / support. The groove faces FORWARD (the panel front, toward -Y) and
    // opens UP, so a plate drops into it on edge.
    //
    // Bounding box = [base_w, base_depth + lean_off, base_h + back_height].
    //   X: base_w (base and back share the full width).
    //   Y: base spans 0..base_depth; the back's bottom sits at the base rear and its leaned top
    //      reaches y = base_depth + lean_off (the rear-most, top-most point).
    //   Z: base_h (base slab) + back_height (back rise).
    eps = 0.05;
    back_t = 12;                      // FIXED back-panel thickness (run along the lean base)
    back_y0 = base_depth - back_t;    // FIXED: back bottom sits flush at the base rear
    groove_d = 6;                     // FIXED groove depth into the front face
    groove_z_lo = base_h + 8;         // FIXED cradle lip: groove starts above the base top

    difference() {
        union() {
            // --- base slab: corner-at-origin, flat on the bed ---
            cube([base_w, base_depth, base_h]);

            // --- leaning back panel ---
            // Profile authored in the Y-Z plane: local-x carries the Z values, local-y the Y
            // values; extruded along its own +Z then stood up by rotate([0,-90,0]) (extrude axis
            // -> -X) and shifted +base_w so the width lands at X 0..base_w. The bottom edge sinks
            // eps into the base slab so the union fuses with no z-fight seam.
            translate([base_w, 0, 0])
                rotate([0, -90, 0])
                    linear_extrude(height = base_w)
                        polygon([
                            [base_h - eps,          back_y0],                       // bottom front
                            [base_h - eps,          back_y0 + back_t],              // bottom back
                            [base_h + back_height,  back_y0 + back_t + lean_off],   // top back
                            [base_h + back_height,  back_y0 + lean_off],            // top front
                        ]);
        }
        // --- plate groove: a leaning slot cut into the FRONT face of the back panel, centered in
        // X (width groove_w). It cuts groove_d INTO the panel and over-runs UP past the panel top
        // into open air (never past an outer X/Y/Z face on the solid), so the envelope is
        // unchanged. The cut parallelogram shares the panel's lean: its front edge starts eps
        // ahead of the front face, its rear edge is groove_d back. ---
        translate([(base_w + groove_w) / 2, 0, 0])
            rotate([0, -90, 0])
                linear_extrude(height = groove_w)
                    polygon([
                        [groove_z_lo,                 back_y0 - eps],                        // front, low
                        [groove_z_lo,                 back_y0 + groove_d],                   // rear, low
                        [base_h + back_height + eps,  back_y0 + groove_d + lean_off],        // rear, top (into air)
                        [base_h + back_height + eps,  back_y0 - eps + lean_off],             // front, top (into air)
                    ]);
    }
}
