// hooks.scad — wall-mount and pegboard hooks. Units mm.
// All hooks orient the back plate in the X (width) – Z (height) plane with its
// thickness along Y; the wall sits at the -Y face. The hook projects out the +Y
// face. Bounding boxes are documented so the design plan can commit the exact
// envelope (see each module).
//
//   wall_hook(plate_w, plate_h, plate_t, screw_d, screw_spacing, arm_proj, arm_rise, arm_size)
//     Back plate with two screw holes drilled through along Y, plus an L-shaped
//     hook that projects +Y by arm_proj then rises +Z by arm_rise.
//     Bounding box = [plate_w, plate_t + arm_proj, plate_h].
//
//   pegboard_hook(hole_d, hole_spacing, arm_length, plate_w, plate_t, peg_len, arm_rise, arm_size)
//     Back plate with two rearward pegs (-Y) spaced hole_spacing to seat in a
//     pegboard, plus an L-shaped hook projecting +Y then up.
//     Bounding box = [plate_w, peg_len + plate_t + arm_length, hole_spacing + 2*arm_size + 16].

module wall_hook(plate_w = 25, plate_h = 60, plate_t = 4,
                 screw_d = 4, screw_spacing = 30,
                 arm_proj = 35, arm_rise = 20, arm_size = 6, fn = 48) {
    eps = 0.05;
    clear = 0.2;
    arm_x0 = (plate_w - arm_size) / 2;          // centre the arm across the width
    arm_z0 = max(2, (plate_h - arm_rise) / 2);  // seat it so the rise stays within plate_h
    difference() {
        union() {
            cube([plate_w, plate_t, plate_h]);                       // back plate
            translate([arm_x0, plate_t - eps, arm_z0])               // horizontal arm (+Y)
                cube([arm_size, arm_proj + eps, arm_size]);
            translate([arm_x0, plate_t + arm_proj - arm_size, arm_z0])  // up-turned lip (+Z)
                cube([arm_size, arm_size, arm_rise]);
        }
        for (z = [plate_h / 2 - screw_spacing / 2, plate_h / 2 + screw_spacing / 2])
            translate([plate_w / 2, -eps, z])
                rotate([-90, 0, 0])
                    cylinder(h = plate_t + 2 * eps, d = screw_d + clear, $fn = fn);
    }
}

module pegboard_hook(hole_d = 6, hole_spacing = 25.4, arm_length = 45,
                     plate_w = 30, plate_t = 5, peg_len = 12,
                     arm_rise = 15, arm_size = 6, fn = 48) {
    eps = 0.05;
    clear = 0.2;
    peg_d = max(2, hole_d - clear);             // peg a touch under the hole for fit
    plate_h = hole_spacing + 2 * arm_size + 16; // covers both pegs with margin
    z_lo = (plate_h - hole_spacing) / 2;
    z_hi = z_lo + hole_spacing;
    arm_x0 = (plate_w - arm_size) / 2;
    arm_z0 = max(2, z_lo - arm_size);
    union() {
        cube([plate_w, plate_t, plate_h]);                          // back plate
        for (z = [z_lo, z_hi])                                      // rearward pegs (-Y)
            translate([plate_w / 2, eps, z])                        // start inside the plate by eps...
                rotate([90, 0, 0])
                    cylinder(h = peg_len + eps, d = peg_d, $fn = fn);  // ...so the tip reaches exactly -peg_len
        translate([arm_x0, plate_t - eps, arm_z0])                  // horizontal arm (+Y)
            cube([arm_size, arm_length + eps, arm_size]);
        translate([arm_x0, plate_t + arm_length - arm_size, arm_z0])  // up-turned lip (+Z)
            cube([arm_size, arm_size, arm_rise]);
    }
}
