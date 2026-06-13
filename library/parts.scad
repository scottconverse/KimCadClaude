// parts.scad — generic engineering ports: rings, plates, and brackets. Units mm.
// Built corner-at-origin (cube) so the bounding box is the exact envelope; cylinders are
// XY-centered like OpenSCAD's cylinder(). Each module documents its analytic bounding box;
// the family registry pins the same formula and a real render confirms it (#19 slice 10).
//
//   flat_washer(od, id, thickness, fn)                                 bbox = [od, od, thickness]
//   dowel_pin(diameter, length, fn)                                    bbox = [diameter, diameter, length]
//   bumper_foot(diameter, height, hole_d, counterbore_d, cbore_h, fn)  bbox = [diameter, diameter, height]
//   mounting_flange(diameter, thickness, bore_d, bolt_hole_d, bolt_circle_d, fn)   bbox = [diameter, diameter, thickness]
//   pierced_mount_pad(width, depth, height, hole_d, fn)                bbox = [width, depth, height]
//   faceplate(width, height, thickness, hole_d, inset)                 bbox = [width, height, thickness]
//   vesa_plate(width, height, thickness, vesa_spacing, hole_d, fn)     bbox = [width, height, thickness]
//   corner_gusset(width, leg, thickness, hole_d, fn)                   bbox = [width, leg, leg]
//   pcb_standoff(board_w, board_d, base_t, standoff_h, hole_d, standoff_d, inset, fn)   bbox = [board_w, board_d, base_t + standoff_h]
//   french_cleat_rail(length, depth, rise, screw_d, fn)               bbox = [length, depth, rise]
//   heatset_insert_boss(boss_d, height, pocket_d, pocket_depth, fn)    bbox = [boss_d, boss_d, height]

// flat_washer(od, id, thickness, fn)
//   A flat washer / shim: a solid disc of outer diameter `od` extruded to `thickness`,
//   with a concentric through bore of diameter `id`. The bore over-cuts eps below the
//   base and eps above the top into open air, so it never shaves a documented face.
//   Bounding box = [od, od, thickness].
module flat_washer(od = 16, id = 8, thickness = 2, fn = 64) {
    eps = 0.05;
    difference() {
        cylinder(h = thickness, d = od, $fn = fn);                  // outer disc
        translate([0, 0, -eps])                                     // concentric through bore
            cylinder(h = thickness + 2 * eps, d = id, $fn = fn);
    }
}

// dowel_pin(diameter, length, fn)
//   A solid alignment dowel pin: a plain cylinder standing on the bed. The cylinder
//   is XY-centered (matches OpenSCAD's cylinder()), so its footprint is exactly
//   [diameter, diameter] and it rises 0..length in Z.
//   Bounding box = [diameter, diameter, length].
module dowel_pin(diameter = 6, length = 30, fn = 64) {
    cylinder(h = length, d = diameter, $fn = fn);
}

// bumper_foot(diameter, height, hole_d, counterbore_d, cbore_h, fn)
//   A cabinet / appliance bumper foot: a short solid cylinder (diameter x height) with a
//   centered counterbored screw hole entering from the BOTTOM — a wider counterbore_d pocket
//   (depth cbore_h) seats the screw head, and a narrower hole_d screw clearance bore continues
//   up toward (but not through) the solid top face. Both cuts open downward into the open air
//   below the base (z < 0), so neither touches the documented outer envelope.
//   Bounding box = [diameter, diameter, height].
module bumper_foot(diameter = 30, height = 12, hole_d = 4.5, counterbore_d = 9, cbore_h = 5, fn = 64) {
    eps = 0.05;
    // The screw clearance bore stops 2 mm short of the top so a solid top cap remains
    // (keeps the foot watertight and gives a flat top contact face). Pinned so the
    // envelope never depends on the bore depth.
    bore_h = height - 2;
    difference() {
        cylinder(h = height, d = diameter, $fn = fn);            // solid foot body
        // screw clearance bore: from just below the base up to the 2 mm top cap
        translate([0, 0, -eps])
            cylinder(h = bore_h + eps, d = hole_d, $fn = fn);
        // counterbore: wider screw-head pocket recessed into the bottom
        translate([0, 0, -eps])
            cylinder(h = cbore_h + eps, d = counterbore_d, $fn = fn);
    }
}

// mounting_flange(diameter, thickness, bore_d, bolt_hole_d, bolt_circle_d, fn)
//   A flat round pipe / mounting flange disc (diameter x thickness), XY-centered, with a
//   centered bore and a ring of 4 bolt holes on a FIXED bolt-circle (bolt_circle_d). The
//   bolt holes sit at radius bolt_circle_d/2 at 45/135/225/315 deg; with diameter pinned
//   >= 40 and bolt_hole_d <= 6 the outer edge of every bolt hole (bolt_circle_d/2 +
//   bolt_hole_d/2 = 16 + 3 = 19) stays inside the disc edge (diameter/2 >= 20), so the
//   footprint stays exactly [diameter, diameter]. The bolt pattern is FIXED so the part
//   mates with the flange it bolts to (tier baseline). Every bore over-cuts -eps below and
//   +eps above into open air, so all faces are clean. bbox = [diameter, diameter, thickness].
module mounting_flange(diameter = 80, thickness = 8, bore_d = 20, bolt_hole_d = 5,
                       bolt_circle_d = 32, fn = 96) {
    eps = 0.05;
    bc_r = bolt_circle_d / 2;
    difference() {
        cylinder(h = thickness, d = diameter, $fn = fn);            // flange disc
        translate([0, 0, -eps])                                     // centered bore
            cylinder(h = thickness + 2 * eps, d = bore_d, $fn = fn);
        for (a = [45, 135, 225, 315])                               // 4 bolt holes, fixed BCD
            translate([bc_r * cos(a), bc_r * sin(a), -eps])
                cylinder(h = thickness + 2 * eps, d = bolt_hole_d, $fn = fn);
    }
}

// pierced_mount_pad(width, depth, height, hole_d, fn)
//   A rectangular mounting pad/slab (corner-at-origin) with a single centered vertical
//   through-hole: cube([width, depth, height]) minus a centered cylinder of diameter
//   hole_d drilled along Z. The bore over-cuts eps below the base and eps above the top
//   into open air on both ends, so it never touches a side face and hole_d is inert to
//   the envelope. Bounding box = [width, depth, height].
module pierced_mount_pad(width = 60, depth = 40, height = 6, hole_d = 8, fn = 64) {
    eps = 0.05;
    difference() {
        cube([width, depth, height]);                 // solid slab, corner at origin
        translate([width / 2, depth / 2, -eps])        // centered vertical bore
            cylinder(h = height + 2 * eps, d = hole_d, $fn = fn);
    }
}

// faceplate(width, height, thickness, hole_d, inset)
//   A blanking faceplate / cover plate: a thin slab [width, height, thickness] with four
//   corner screw clearance holes drilled straight down the thickness. The holes inset from
//   each corner by `inset` and over-cut eps past the top and bottom faces into open air, so
//   the envelope stays exactly [width, height, thickness].
//   Bounding box = [width, height, thickness].
module faceplate(width = 80, height = 60, thickness = 3, hole_d = 4, inset = 6) {
    eps = 0.05;
    difference() {
        cube([width, height, thickness]);
        for (x = [inset, width - inset])
            for (y = [inset, height - inset])
                translate([x, y, -eps])
                    cylinder(h = thickness + 2 * eps, d = hole_d, $fn = 32);
    }
}

// vesa_plate(width, height, thickness, vesa_spacing, hole_d, fn)
//   A VESA monitor-mount adapter slab with a centered square 4-hole VESA pattern
//   (vesa_spacing center-to-center, e.g. 75 or 100 mm). The holes are drilled through
//   Z and stay interior to the slab, so the envelope is exactly [width, height, thickness].
//   Bounding box = [width, height, thickness].
module vesa_plate(width = 140, height = 140, thickness = 4, vesa_spacing = 100, hole_d = 4.5, fn = 32) {
    eps = 0.05;
    cx = width / 2;
    cy = height / 2;
    s = vesa_spacing / 2;
    difference() {
        cube([width, height, thickness]);                       // slab: corner at origin
        // centered square 4-hole VESA pattern, drilled through Z (over-cut into open air)
        for (dx = [-s, s], dy = [-s, s])
            translate([cx + dx, cy + dy, -eps])
                cylinder(h = thickness + 2 * eps, d = hole_d, $fn = fn);
    }
}

// corner_gusset(width, leg, thickness, hole_d, fn)
//   A triangular corner brace: a right-triangle web (leg deep on Y, leg tall on Z) braced
//   across its width (X), with a screw hole bored along X through each leg flat. `thickness`
//   only positions the holes off each leg flat, so it is inert to the [width, leg, leg]
//   envelope. Bounding box = [width, leg, leg].
module corner_gusset(width = 50, leg = 40, thickness = 6, hole_d = 4, fn = 32) {
    eps = 0.05;
    clear = 0.2;
    // The two leg flats lie on the Z-low (bottom) and Y-low (back) faces; place one screw
    // hole at each leg midpoint, its axis running along X through the full web width.
    hole_pos = leg * 0.5;            // along the leg, from the corner
    difference() {
        // Right-triangle profile in XY, extruded +Z by `width`, then mapped to final axes by
        // rotate([90,0,0]) then rotate([0,0,90]) (the wedge_easel_stand orient idiom):
        //   local X (0..leg)   -> final Y (0..leg)
        //   local Y (0..leg)   -> final Z (0..leg)
        //   local Z (0..width) -> final X (0..width)
        // so the solid lands corner-at-origin with envelope [width, leg, leg].
        rotate([0, 0, 90])
            rotate([90, 0, 0])
                linear_extrude(height = width)
                    polygon([[0, 0], [leg, 0], [0, leg]]);
        // Screw hole through the Z-low (bottom) leg flat: axis along X, centered in the web
        // at y = hole_pos, sitting in the bottom leg near z = thickness/2. Over-cuts both web
        // faces (-eps..width+eps) into open air, never past the documented Y/Z faces.
        translate([-eps, hole_pos, thickness / 2])
            rotate([0, 90, 0])
                cylinder(h = width + 2 * eps, d = hole_d + clear, $fn = fn);
        // Screw hole through the Y-low (back) leg flat: axis along X, centered in the web at
        // z = hole_pos, sitting in the back leg near y = thickness/2.
        translate([-eps, thickness / 2, hole_pos])
            rotate([0, 90, 0])
                cylinder(h = width + 2 * eps, d = hole_d + clear, $fn = fn);
    }
}

// pcb_standoff(board_w, board_d, base_t, standoff_h, hole_d, standoff_d, inset, fn)
//   A PCB mounting base: a flat base plate [board_w x board_d x base_t] with four
//   cylindrical standoffs (standoff_d wide, standoff_h tall) rising from inset corners,
//   each pierced by a through screw hole (hole_d). The standoffs sit INSIDE the plate
//   footprint (inset >= standoff_d/2), so the envelope is the plate footprint by the
//   full height: [board_w, board_d, base_t + standoff_h].
//   Bounding box = [board_w, board_d, base_t + standoff_h].
module pcb_standoff(board_w = 70, board_d = 50, base_t = 3, standoff_h = 8,
                    hole_d = 3.2, standoff_d = 8, inset = 5, fn = 48) {
    eps = 0.05;
    // The four inset corner centers (standoff_d/2 <= inset keeps every post inside the plate).
    centers = [
        [inset,           inset],
        [board_w - inset, inset],
        [inset,           board_d - inset],
        [board_w - inset, board_d - inset],
    ];
    difference() {
        union() {
            cube([board_w, board_d, base_t]);            // base plate, corner at origin
            for (c = centers)                            // four standoffs on top of the plate
                translate([c[0], c[1], base_t])
                    cylinder(h = standoff_h, d = standoff_d, $fn = fn);
        }
        // A through screw bore down the whole stack at each standoff (clearance fit hole_d).
        for (c = centers)
            translate([c[0], c[1], -eps])
                cylinder(h = base_t + standoff_h + 2 * eps, d = hole_d, $fn = fn);
    }
}

// french_cleat_rail(length, depth, rise, screw_d, fn)
//   The wall half of a 45-degree French cleat (the half that screws to the wall): a right-
//   trapezoid rail with a 45-degree top bevel, extruded along its length, with a row of screw
//   holes drilled through the solid lower back into the wall. A matching cleat half on the hung
//   object has the mirrored down-facing bevel and drops onto this rail. bbox = [length, depth, rise].
module french_cleat_rail(length = 170, depth = 22, rise = 30, screw_d = 4, fn = 32) {
    eps = 0.05;
    clear = 0.2;
    // Fixed minimum wall stock kept BELOW the bevel chamfer. The 45-degree bevel run is equal in
    // Y (depth) and Z (rise); clamping it to min(depth, rise) - thick keeps it strictly inside the
    // envelope, so the two flat back corners (the +Y mounting face at Y=depth and the back top
    // corner at Z=rise) set the envelope and the bbox stays exactly [length, depth, rise].
    thick = 6;
    bevel = min(depth, rise) - thick;

    // Wall half cross-section in (Y, Z). The chamfer cuts the top-FRONT corner so the 45-degree
    // working face points UP-AND-FRONT (the hung cleat's matching down-facing bevel seats on it).
    // The flat +Y face (Y=depth) is the mounting back, against the wall.
    wall_profile = [
        [0, 0],                 // bottom, front
        [depth, 0],             // bottom, back (wall side)
        [depth, rise],          // top, back
        [bevel, rise],          // top, after the chamfer runs forward by `bevel`
        [0, rise - bevel],      // front face, chamfer descends to here
    ];

    // Two screw holes drilled along +Y through the solid lower-back block, at a Z below where the
    // front chamfer begins, so each bore lies wholly within full-depth material. The bore over-cuts
    // both the front (Y=0) and back (Y=depth) faces by eps into open air, removing material AT the
    // faces but never extending the [length, depth, rise] envelope. The FIXED count of two holes is
    // inert to the envelope (the drawer_divider / propagation_station precedent).
    screw_z = (rise - bevel) / 2;   // centered in the un-chamfered lower front stock
    difference() {
        // linear_extrude raises the (Y,Z) profile +Z by length; rotate([90,0,90]) maps local
        // (x,y,z) -> (z, x, y): profile-x (our Y, 0..depth) -> world Y, profile-y (our Z, 0..rise)
        // -> world Z, extrude (0..length) -> world X. So the rendered extents equal exactly
        // [length, depth, rise].
        rotate([90, 0, 90])
            linear_extrude(height = length)
                polygon(wall_profile);
        for (x = [length * 0.2, length * 0.8]) {
            translate([x, -eps, screw_z])
                rotate([-90, 0, 0])
                    cylinder(h = depth + 2 * eps, d = screw_d + clear, $fn = fn);
        }
    }
}

// heatset_insert_boss(boss_d, height, pocket_d, pocket_depth, fn)
//   A heat-set insert boss: a solid XY-centered cylindrical boss (boss_d x height) with a
//   centered BLIND top pocket (pocket_d x pocket_depth) sized to seat a brass heat-set
//   threaded insert. pocket_d <= boss_d - 2*wall (the gap keeps a boss wall around the
//   insert); pocket_depth <= height - floor (the gap keeps a solid floor under the insert).
//   Both cylinders are XY-centered like OpenSCAD's cylinder(). The pocket over-cuts UP by eps
//   into the open air above the rim (never DOWN past the floor or any documented face), so the
//   envelope is exactly [boss_d, boss_d, height] and the floor stays solid. Same
//   solid-cylinder-minus-top-pocket idiom as dishes.scad::tealight_holder / taper_candle_holder.
//   Bounding box = [boss_d, boss_d, height].
module heatset_insert_boss(boss_d = 12, height = 14, pocket_d = 5, pocket_depth = 8, fn = 96) {
    eps = 0.05;
    difference() {
        cylinder(h = height, d = boss_d, $fn = fn);              // solid boss body
        translate([0, 0, height - pocket_depth])                 // centered blind insert pocket
            cylinder(h = pocket_depth + eps, d = pocket_d, $fn = fn);
    }
}
