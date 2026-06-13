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
