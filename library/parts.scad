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
//
// #19 slice 11: boxes + specialty
//   snap_fit_box(width, depth, height, wall, lid_h, gap, fn)           bbox = [2*width + gap, depth, height]
//   hinged_lid_box(width, depth, height, wall, gap)                    bbox = [2*width + gap, depth, height]
//   slot_clamp_block(width, depth, height, slot_w, screw_d, fn)        bbox = [width, depth, height]
//   cable_raceway(length, width, height, wall, fn)                     bbox = [length, width, height]
//   bar_pull_handle(span, height, depth, post_d, grip_d, fn)           bbox = [span, depth, height]
//   phone_dock(width, depth, height, slot_w, cable_d, fn)              bbox = [width, depth, height]
//   pour_funnel(inlet_d, height, outlet_d, wall, fn)                   bbox = [inlet_d, inlet_d, height]  (inlet_d >= outlet_d)
//   gridfinity_bin(grid_x, grid_y, height, wall, floor_t, lip)         bbox = [42*grid_x, 42*grid_y, height]
//   gridfinity_baseplate(grid_x, grid_y, height)                       bbox = [42*grid_x, 42*grid_y, height]
//   hex_nut_blank(hex_af, height, bore_d, fn)                          bbox = [hex_af/cos(30), hex_af, height]
//   threaded_bolt(head_af, head_h, shaft_d, shaft_l, fn)               bbox = [head_af/cos(30), head_af, head_h + shaft_l]

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

// ============================================================================
// #19 slice 11: boxes + specialty
// ============================================================================

module snap_fit_box(width = 80, depth = 60, height = 40, wall = 2, lid_h = 12, gap = 10, fn = 48) {
    eps = 0.05;
    fit = 0.4;                       // diametral slip-fit clearance: lid bore over base outer

    // --- BASE: open-top walled box at the origin, floor = wall ---------------------------
    translate([0, 0, 0])
        difference() {
            cube([width, depth, height]);                        // outer body
            translate([wall, wall, wall])                        // cavity (open top, +eps into air)
                cube([width - 2 * wall, depth - 2 * wall, height - wall + eps]);
        }

    // --- LID: open-DOWN friction cap at x = width + gap ----------------------------------
    // The lid bore = base OUTER footprint + fit, so the cap slips over the base rim. The bore
    // stays strictly inside the lid's own outer wall (bore = width - 2*wall + fit < width), so
    // the lid's X span is exactly `width` and the cavity never breaks the outer face. lid_h is
    // pinned <= height (height min >= lid_h), so the BASE is the tallest part (bbox_z = height).
    bore_w = width - 2 * wall + fit;                             // lid cavity width  (< width)
    bore_d = depth - 2 * wall + fit;                             // lid cavity depth  (< depth)
    translate([width + gap, 0, 0])
        difference() {
            cube([width, depth, lid_h]);                         // outer cap body
            translate([(width - bore_w) / 2, (depth - bore_d) / 2, -eps]) // open DOWN, +eps below
                cube([bore_w, bore_d, lid_h - wall + eps]);      // leaves a wall-thick top
        }
}

// hinged_lid_box(width, depth, height, wall, gap)   bbox = [2*width + gap, depth, height]
//
// A small parts/tackle box printed SIDE BY SIDE along X with a fixed print gap: an open-top
// walled BASE at the origin, and a separate press-on LID at x = width + gap. The lid is a
// flat top plate (full [width, depth] footprint) with a DOWNWARD INNER LIP that seats INSIDE
// the base rim (distinct from gift_box_lid's telescoping outer shoulder, and from snap_fit_box's
// snap). Both parts span the same z = 0 .. height, and the lid footprint is exactly
// [width, depth], so the combined envelope is exactly [2*width + gap, depth, height]. Built
// corner-at-origin so the bounding box is the exact envelope.
module hinged_lid_box(width = 80, depth = 60, height = 40, wall = 2, gap = 10) {
    eps = 0.05;
    fit = 0.4;                          // diametral slip-fit clearance: lip outer < base cavity

    // --- BASE: open-top walled box at the origin, floor = wall ---------------------------
    translate([0, 0, 0])
        difference() {
            cube([width, depth, height]);                        // outer body
            translate([wall, wall, wall])                        // cavity (open top, +eps into air)
                cube([width - 2 * wall, depth - 2 * wall, height - wall + eps]);
        }

    // --- LID: a flat top plate with a downward inner lip seating inside the base rim ------
    // Plate occupies the top `wall` of the height across the full [width, depth] footprint.
    // The inner lip hangs from the floor (z = 0) up into the plate, sized to drop INSIDE the
    // base cavity with `fit` clearance, so it seats against the inner face of the base rim.
    lip_outer_w = width - 2 * wall - fit;       // lip OD width  (< base cavity width)
    lip_outer_d = depth - 2 * wall - fit;       // lip OD depth  (< base cavity depth)
    lip_inner_w = lip_outer_w - 2 * wall;       // lip bore (open underside of the lid)
    lip_inner_d = lip_outer_d - 2 * wall;
    lip_h = height - wall;                      // lip hangs from z = 0 up to the plate underside
    translate([width + gap, 0, 0]) {
        union() {
            // top plate, full footprint, top `wall` of the height
            translate([0, 0, height - wall])
                cube([width, depth, wall]);
            // downward inner lip ring (seats inside the base rim); fuses +eps up into the plate
            translate([(width - lip_outer_w) / 2, (depth - lip_outer_d) / 2, 0])
                difference() {
                    cube([lip_outer_w, lip_outer_d, lip_h + eps]);          // lip outer
                    translate([wall, wall, -eps])                           // lip bore
                        cube([lip_inner_w, lip_inner_d, lip_h + 3 * eps]);
                }
        }
    }
}

// slot_clamp_block(width, depth, height, slot_w, screw_d, fn)    bbox = [width, depth, height]
module slot_clamp_block(width = 40, depth = 30, height = 35, slot_w = 4, screw_d = 5, fn = 48) {
    eps = 0.05;
    // Slot bottom sits a third of the way up, leaving a solid base that joins the jaws;
    // the cross screw hole passes through the jaws above the slot bottom.
    slot_bottom = height / 3;             // z of the closed slot bottom
    screw_z = slot_bottom + (height - slot_bottom) / 2;   // hole centred up the jaw span
    difference() {
        cube([width, depth, height]);     // solid block, corner at origin

        // vertical slot: centred in X, full depth (over-cut +/-eps past front/back faces),
        // open at the top (over-cut +eps up into open air above the block).
        translate([(width - slot_w) / 2, -eps, slot_bottom])
            cube([slot_w, depth + 2 * eps, height - slot_bottom + eps]);

        // cross screw hole through both jaws, along X, over-cut past both X faces.
        translate([-eps, depth / 2, screw_z])
            rotate([0, 90, 0])
                cylinder(h = width + 2 * eps, d = screw_d, $fn = fn);
    }
}

// cable_raceway(length, width, height, wall, fn)   bbox = [length, width, height]
module cable_raceway(length = 160, width = 30, height = 20, wall = 3, fn = 32) {
    eps = 0.05;
    mount_holes = 5;                          // FIXED — inert to the bbox (drawer_divider precedent)
    hole_d = 4;                               // mounting screw clearance bore
    chan_l = length - 2 * wall;               // open-top cable channel
    chan_w = width - 2 * wall;
    chan_depth = height - wall + eps;         // floor = wall thick, open top (+eps into air)
    difference() {
        cube([length, width, height]);        // outer envelope
        translate([wall, wall, wall])         // top-open cable channel
            cube([chan_l, chan_w, chan_depth]);
        // mounting bores: a centered row through the wall-thick floor, each over-cut -eps
        // below the base and up into the open channel cavity, so the bbox is untouched.
        for (i = [0 : mount_holes - 1]) {
            x = length / 2 + (i - (mount_holes - 1) / 2) * (length / (mount_holes + 1));
            translate([x, width / 2, -eps])
                cylinder(h = wall + 2 * eps, d = hole_d, $fn = fn);
        }
    }
}

// bar_pull_handle(span, height, depth, post_d, grip_d)   bbox = [span, depth, height]
//   A bar pull / drawer-pull handle: two vertical cylindrical posts at the span ends rise
//   the full height; each carries a horizontal arm projecting forward by `depth` to a
//   horizontal grip rail that spans the full `span` across the front. A screw hole is
//   drilled down through each post base. Cylinders are XY-centered like OpenSCAD's
//   cylinder(); the assembly is laid out corner-at-origin so the envelope is exactly
//   [span, depth, height]:
//     X (span)   : the grip rail is a horizontal cylinder along X from x=0 to x=span; the two
//                  posts sit at x=post_d/2 and x=span-post_d/2 (edges at x=0 and x=span).
//     Y (depth)  : posts sit at the back (edge at y=0); the grip front face is at y=depth
//                  (grip axis at y=depth-grip_d/2). Y extent = depth.
//     Z (height) : posts span z=0..height; the grip rail top sits at z=height
//                  (grip axis at z=height-grip_d/2). Z extent = height.
module bar_pull_handle(span = 128, height = 32, depth = 30, post_d = 14, grip_d = 12, fn = 64) {
    eps = 0.05;
    screw_d = 4;                                              // FIXED screw bore through each post base
    post_cx0 = post_d / 2;                                    // left post center x  (edge at x=0)
    post_cx1 = span - post_d / 2;                             // right post center x (edge at x=span)
    post_cy  = post_d / 2;                                    // posts at the back, edge at y=0
    grip_cy  = depth - grip_d / 2;                            // grip at the front, front face at y=depth
    grip_cz  = height - grip_d / 2;                           // grip at the top, top face at z=height
    arm_d    = min(post_d, grip_d);                           // arm never fatter than the members it joins
    arm_z    = grip_cz;                                       // arm centered in the grip (arm_d<=grip_d => inside)
    difference() {
        union() {
            // Two vertical posts, full height, at the span ends (back row).
            for (cx = [post_cx0, post_cx1])
                translate([cx, post_cy, 0])
                    cylinder(h = height, d = post_d, $fn = fn);
            // Two forward arms (horizontal cylinders along +Y) from each post to the grip.
            // Rotating a +Z cylinder by -90 about X points it along +Y. Each arm runs from the
            // back face (y=0, flush with the post back) and ends BURIED inside the grip (at the
            // grip axis, y=grip_cy), so its flat end cap is interior to the grip solid. The arm
            // diameter is min(post_d, grip_d) so the arm is never fatter than either member it
            // joins — it slides cleanly INTO both the post and the grip. The grip supplies the
            // front face at y=depth, so the Y extent stays exactly `depth`.
            for (cx = [post_cx0, post_cx1])
                translate([cx, 0, arm_z])
                    rotate([-90, 0, 0])
                        cylinder(h = grip_cy, d = arm_d, $fn = fn);
            // The grip rail: a horizontal cylinder along +X spanning the full span at the front.
            // Rotating a +Z cylinder by +90 about Y points it along +X.
            translate([0, grip_cy, grip_cz])
                rotate([0, 90, 0])
                    cylinder(h = span, d = grip_d, $fn = fn);
        }
        // A screw hole down through each post base (open at the bottom, stops short of the top).
        for (cx = [post_cx0, post_cx1])
            translate([cx, post_cy, -eps])
                cylinder(h = height, d = screw_d, $fn = fn);
    }
}

module phone_dock(width = 80, depth = 70, height = 90, slot_w = 12, cable_d = 10, fn = 48) {
    eps = 0.05;
    // A weighted base slab the device-rest wedge rises from, plus an angled back rest the
    // phone/tablet leans into (a slot of width slot_w receives the device) and a front cable
    // pass-through bore. Every solid stays inside [width, depth, height] so the analytic bbox
    // is exactly that envelope and stays linear.
    base_h = height * 0.4;                       // weighted base height (fixed coef of height)
    front_y = depth * 0.35;                      // wedge front foot — leaves a front base shelf
    // Device slot geometry: a thin channel parallel to the rest incline, centered across width,
    // ends inset so it never reaches the X faces. It opens at the top (over-cut UP into open air)
    // and sinks into the wedge; it never touches the documented top/side faces.
    slot_len_x = width - 2 * (width * 0.12 + 4); // interior in X (never the X faces)
    // lean angle of the rest hypotenuse from vertical (back face at Y=depth, apex at Z=height)
    rest_run = depth - front_y;                  // forward reach of the incline
    lean_a = atan(rest_run / height);            // from vertical
    // slot mouth sits at the rest face near the top-back; centered across width.
    slot_seat = height * 0.5;                     // how deep the slot sinks below the rim
    py = depth - rest_run * 0.45;                 // where the slot meets the rest face (in Y)
    slot_run = height + slot_seat + 2 * eps;      // tall enough to fully cut the rest
    difference() {
        union() {
            // weighted base — full footprint, prints flat on its bottom face
            cube([width, depth, base_h]);
            // angled back rest wedge: right-triangle profile in (depth, vertical) coords,
            // extruded along the width then oriented with rotate([90,0,90]) so depth->Y,
            // vertical->Z, width->X. Vertical BACK face at Y=depth rising to Z=height; the
            // hypotenuse from the front foot up to the back apex is the inclined REST face.
            // The triangle base sits on the Z=0 floor and shares the lower (0..base_h) volume
            // with the base slab, so the two fuse without dipping below the documented floor.
            rotate([90, 0, 90])
                linear_extrude(height = width)
                    polygon([
                        [front_y, 0],        // front foot, on the floor / into the base slab
                        [depth,   0],        // back foot, on the floor / into the base slab
                        [depth,   height]    // back apex (the Z top)
                    ]);
        }
        // device slot: a thin box leaning back at the rest angle, centered across the width.
        // Built upright, rotated -lean_a about X so it lies parallel to the rest hypotenuse,
        // and positioned so its mouth opens at the top and it sinks slot_seat into the wedge.
        // Over-cuts UP into the open air above the apex; only DOWN into solid material.
        translate([(width - slot_len_x) / 2, py, height - slot_seat])
            rotate([-lean_a, 0, 0])
                cube([slot_len_x, slot_w, slot_run]);
        // front cable pass-through: a horizontal bore of diameter cable_d through the front of
        // the base, running along Y. XY-centered cylinder rotated to point +Y; spans the base
        // front-to-back with eps over-cut at both open ends (never the X/Z faces).
        translate([width / 2, -eps, base_h * 0.5])
            rotate([-90, 0, 0])
                cylinder(h = front_y + 2 * eps, d = cable_d, $fn = fn);
    }
}

// pour_funnel(inlet_d, height, outlet_d, wall)   bbox = [inlet_d, inlet_d, height]  (inlet_d >= outlet_d)
module pour_funnel(inlet_d = 90, height = 80, outlet_d = 20, wall = 3, fn = 96) {
    eps = 0.05;
    // A hollow truncated-cone pour funnel: a wide inlet at the TOP (inlet_d), a narrow
    // outlet at the BOTTOM (outlet_d), height tall, wall thick. The bore runs all the way
    // THROUGH (open at both the inlet and the outlet) so liquid pours through. inlet_d is
    // PINNED >= outlet_d so the top rim is the widest point and sets the footprint, making
    // the envelope exactly [inlet_d, inlet_d, height] (linear, no max()). Cylinders are
    // XY-centered like OpenSCAD's cylinder(); the outer/inner walls are frusta (cylinder
    // d1/d2 taper). The inner bore is inset `wall` all round at each end and cut THROUGH
    // both faces — over-cut -eps below the base and +eps above the rim into open air, so
    // both openings are clean and the cut never touches a documented face.
    in_bot = outlet_d - 2 * wall;                        // inner bore diameter at the outlet
    in_top = inlet_d - 2 * wall;                         // inner bore diameter at the inlet
    difference() {
        cylinder(h = height, d1 = outlet_d, d2 = inlet_d, $fn = fn);            // outer cone wall
        translate([0, 0, -eps])
            cylinder(h = height + 2 * eps, d1 = in_bot, d2 = in_top, $fn = fn); // through bore
    }
}

// gridfinity_bin(grid_x, grid_y, height, wall, floor_t, lip)
//   A grid_x by grid_y array of 42 mm Gridfinity cells, `height` tall, with a stacking
//   lip recessed into the top inner rim and a scooped (open-top) interior. Everything cut
//   stays inside the outer walls, so the bounding box is exactly
//   [42*grid_x, 42*grid_y, height]. (42 mm is the fixed Gridfinity pitch.)
module gridfinity_bin(grid_x = 2, grid_y = 1, height = 35, wall = 1.2, floor_t = 4, lip = 2.4) {
    eps = 0.05;
    pitch = 42;
    bx = pitch * grid_x;   // outer footprint X = exactly 42*grid_x
    by = pitch * grid_y;   // outer footprint Y = exactly 42*grid_y

    // inner scoop opening (inset by the wall on every side)
    ix = bx - 2 * wall;
    iy = by - 2 * wall;

    // stacking-lip recess: the top `lip` of height steps the rim inward, thinning the
    // upper wall to lip_wall so a bin stacked above nests onto the ledge. Clamped to leave
    // a >=0.4 mm upper wall, so the recess NEVER reaches the envelope faces.
    lip_wall = max(0.4, wall - lip);     // remaining upper wall after the rim step
    lx = bx - 2 * lip_wall;
    ly = by - 2 * lip_wall;
    lip_z = height - lip;

    difference() {
        // outer solid — the full [bx, by, height] envelope
        cube([bx, by, height]);

        // scooped interior cavity, open top: from the floor up through the rim (+eps into air)
        translate([wall, wall, floor_t])
            cube([ix, iy, height - floor_t + eps]);

        // stacking-lip rim recess at the very top (cut down into the rim, +eps up into air)
        translate([lip_wall, lip_wall, lip_z])
            cube([lx, ly, lip + eps]);
    }
}

// gridfinity_baseplate(grid_x, grid_y, height)
//   A grid_x by grid_y array of 42 mm Gridfinity cells. Each cell has a stepped
//   cradle recess cut into the TOP face that a standard Gridfinity bin foot drops
//   into (a funnel: wide opening at the rim, narrowing as it goes down). The recess
//   never reaches the bottom, so the slab stays a solid, watertight base.
//   Bounding box = [42*grid_x, 42*grid_y, height].
module gridfinity_baseplate(grid_x = 2, grid_y = 2, height = 6) {
    eps = 0.05;
    pitch = 42;                 // Gridfinity grid pitch (mm)
    clear = 0.25;               // per-side clearance: cell opening = 41.5 mm

    // Cradle funnel: a 3-step recess into the top, each step narrower AND deeper than
    // the one above, so the pocket steps inward as it descends — the Gridfinity bin-foot
    // cradle. The deepest cut is capped at height - 1 so a >= 1 mm solid base survives.
    open_w  = pitch - 2 * clear;           // 41.5 mm rim opening
    mid_w   = open_w - 1.6;                 // 39.9 mm
    throat_w = open_w - 3.4;                // 38.1 mm throat

    cradle  = min(2.6, height - 1);         // total recess depth
    d1 = cradle * (0.8 / 2.6);              // rim band depth
    d2 = cradle * (1.8 / 2.6);              // mid band depth
    d3 = cradle;                            // throat depth (deepest)

    difference() {
        cube([pitch * grid_x, pitch * grid_y, height]);   // solid slab
        for (gx = [0 : grid_x - 1])
            for (gy = [0 : grid_y - 1]) {
                cx = gx * pitch + pitch / 2;
                cy = gy * pitch + pitch / 2;
                // rim band: full opening, top down d1 (over-cut +eps up into open air)
                translate([cx - open_w / 2, cy - open_w / 2, height - d1])
                    cube([open_w, open_w, d1 + eps]);
                // mid band: narrower, top down d2
                translate([cx - mid_w / 2, cy - mid_w / 2, height - d2])
                    cube([mid_w, mid_w, d2 + eps]);
                // throat: narrowest, top down d3 (the deepest, flat-bottomed cradle floor)
                translate([cx - throat_w / 2, cy - throat_w / 2, height - d3])
                    cube([throat_w, throat_w, d3 + eps]);
            }
    }
}

// hex_nut_blank(hex_af, height, bore_d, fn)
//   A hex nut BLANK — THREAD-RELIEF ONLY (a hex prism with a SMOOTH center bore, NOT a
//   real thread). cylinder($fn=6) draws a hexagon with vertices at 0/60/.../300 deg, so
//   its `d` argument is the across-CORNERS diameter; converting hex_af to across-corners
//   via hex_af / cos(30) makes the across-FLATS dimension exactly hex_af. The smooth bore
//   is a relief for a tapped insert or a printed-thread test — there is NO modeled thread.
//   Envelope: X = across-corners = hex_af / cos(30); Y = across-flats = hex_af; Z = height.
//   Bounding box = [hex_af / cos(30), hex_af, height].
module hex_nut_blank(hex_af = 19, height = 10, bore_d = 13, fn = 64) {
    eps = 0.05;
    difference() {
        // hexagon: across-corners diameter = hex_af / cos(30) so across-flats == hex_af
        cylinder(h = height, d = hex_af / cos(30), $fn = 6);
        // smooth center bore — relief only, over-cut both ends into open air
        translate([0, 0, -eps])
            cylinder(h = height + 2 * eps, d = bore_d, $fn = fn);
    }
}

// threaded_bolt(head_af, head_h, shaft_d, shaft_l, fn)
//   A hex-head bolt blank — THREAD RELIEF ONLY: a hex head ($fn=6, across-flats head_af,
//   head_h tall) on top of a SMOOTH cylindrical shaft (shaft_d x shaft_l), NOT a real thread.
//   The smooth shaft rises z=0..shaft_l; the hex head caps it shaft_l..shaft_l+head_h. The
//   hex is cylinder($fn=6) at across-corners diameter head_af/cos(30), so its vertices land on
//   the X axis: X = across-corners = head_af/cos(30), Y = across-flats = head_af.
//   Bounding box = [head_af / cos(30), head_af, head_h + shaft_l].
module threaded_bolt(head_af = 13, head_h = 8, shaft_d = 8, shaft_l = 40, fn = 64) {
    eps = 0.05;
    // smooth shaft, XY-centered, z = 0 .. shaft_l (over-extends +eps up INTO the head solid)
    cylinder(h = shaft_l + eps, d = shaft_d, $fn = fn);
    // hex head on top: $fn=6, across-flats head_af -> across-corners head_af/cos(30)
    translate([0, 0, shaft_l])
        cylinder(h = head_h, d = head_af / cos(30), $fn = 6);
}
