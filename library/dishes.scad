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
