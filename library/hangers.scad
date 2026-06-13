// hangers.scad — picture/art hanging hardware. Units mm.
// Back plates lie in the X (width) – Z (height) plane, thickness along Y, wall at the -Y
// face. Built corner-at-origin so the bounding box is the exact envelope. Overlaps (eps) are
// placed so they never change the declared envelope (e.g. teeth/rods over-extend INTO the
// plate, never past the documented outer dimension).
//
//   sawtooth_hanger(plate_w, plate_h, plate_t, tooth_count, tooth_depth)
//     A flat plate with a sawtooth top edge (a nail catches any tooth) and two screw holes.
//     Bounding box = [plate_w, plate_t, plate_h + tooth_depth].
//
//   keyhole_hanger_plate(plate_w, plate_h, plate_t, hole_d, slot_w)
//     A flush plate with a keyhole slot (drop over a screw head, slide down to lock) and a
//     back counterbore so it sits flat. Bounding box = [plate_w, plate_t, plate_h].
//
//   hidden_rod_shelf_bracket(plate_w, plate_h, plate_t, rod_length, rod_d)
//     A concealed floating-shelf support: a wall plate with two horizontal rods that insert
//     into holes drilled in the shelf. Bounding box = [plate_w, plate_t + rod_length, plate_h].

module sawtooth_hanger(plate_w = 40, plate_h = 15, plate_t = 3, tooth_count = 5,
                       tooth_depth = 4, screw_d = 3, fn = 24) {
    eps = 0.05;
    clear = 0.2;
    run = plate_w / tooth_count;
    difference() {
        union() {
            cube([plate_w, plate_t, plate_h]);
            // sawtooth teeth on the top edge; each rises tooth_depth, base overlaps the plate
            // by eps so the top stays exactly at plate_h + tooth_depth (envelope-exact).
            for (i = [0:tooth_count - 1])
                translate([i * run, plate_t, plate_h - eps])
                    rotate([90, 0, 0])
                        linear_extrude(height = plate_t)
                            polygon([[0, 0], [run, 0], [0, tooth_depth + eps]]);
        }
        // two screw holes through the plate (along Y)
        for (x = [plate_w * 0.25, plate_w * 0.75])
            translate([x, -eps, plate_h * 0.45])
                rotate([-90, 0, 0])
                    cylinder(h = plate_t + 2 * eps, d = screw_d + clear, $fn = fn);
    }
}

module keyhole_hanger_plate(plate_w = 30, plate_h = 50, plate_t = 4, hole_d = 10, slot_w = 5,
                            fn = 32) {
    eps = 0.05;
    head_z = plate_h * 0.72;        // entry hole near the top
    slot_bot = plate_h * 0.30;
    cb_d = hole_d + 6;              // back counterbore clears the screw head
    cb_depth = plate_t * 0.5;
    difference() {
        cube([plate_w, plate_t, plate_h]);
        // entry hole (through Y)
        translate([plate_w / 2, -eps, head_z])
            rotate([-90, 0, 0]) cylinder(h = plate_t + 2 * eps, d = hole_d, $fn = fn);
        // slot down from the entry hole
        translate([plate_w / 2 - slot_w / 2, -eps, slot_bot])
            cube([slot_w, plate_t + 2 * eps, head_z - slot_bot]);
        // rounded slot bottom
        translate([plate_w / 2, -eps, slot_bot])
            rotate([-90, 0, 0]) cylinder(h = plate_t + 2 * eps, d = slot_w, $fn = fn);
        // back counterbore around the entry hole (from the -Y face)
        translate([plate_w / 2, -eps, head_z])
            rotate([-90, 0, 0]) cylinder(h = cb_depth + eps, d = cb_d, $fn = fn);
    }
}

module hidden_rod_shelf_bracket(plate_w = 80, plate_h = 40, plate_t = 6, rod_length = 40,
                                rod_d = 8, screw_d = 4, fn = 32) {
    eps = 0.05;
    clear = 0.2;
    union() {
        difference() {
            cube([plate_w, plate_t, plate_h]);
            // two wall screw holes through the plate (along Y)
            for (z = [plate_h * 0.25, plate_h * 0.75])
                translate([plate_w / 2, -eps, z])
                    rotate([-90, 0, 0])
                        cylinder(h = plate_t + 2 * eps, d = screw_d + clear, $fn = fn);
        }
        // two horizontal rods projecting +Y into the shelf; base overlaps the plate by eps so
        // the far tip lands exactly at plate_t + rod_length (envelope-exact).
        for (x = [plate_w * 0.25, plate_w * 0.75])
            translate([x, plate_t - eps, plate_h / 2])
                rotate([-90, 0, 0])
                    cylinder(h = rod_length + eps, d = rod_d, $fn = fn);
    }
}
