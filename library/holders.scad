// holders.scad — wall-mounted holders. Units mm.
//
//   spool_holder(spool_od, spool_width, screw_d, plate_w, plate_t, plate_h, arm_d, fn)
//     A wall bracket: a back plate (screwed to the wall through two holes along Y) with
//     a horizontal support arm projecting +Y that a filament spool slides onto. The arm
//     length is sized to the spool width plus clearance; the plate height clears the
//     spool radius. Back plate in the X–Z plane, thickness along Y, wall at the -Y face.
//     Bounding box = [plate_w, plate_t + arm_len, plate_h], where
//       arm_len = spool_width + 15 (clearance + end stop).

module spool_holder(spool_od = 200, spool_width = 70, screw_d = 4,
                    plate_w = 60, plate_t = 8, plate_h = 120,
                    arm_d = 20, fn = 48) {
    eps = 0.05;
    clear = 0.2;
    arm_len = spool_width + 15;                 // spool width + clearance + end stop
    arm_z = plate_h - arm_d / 2 - 8;            // arm high on the plate so the spool hangs clear
    stop_d = arm_d + 12;                         // end flange keeps the spool on
    screw_z1 = plate_h * 0.25;
    screw_z2 = plate_h * 0.75;
    difference() {
        union() {
            cube([plate_w, plate_t, plate_h]);                 // back plate
            translate([plate_w / 2, plate_t - eps, arm_z])     // support arm (+Y)
                rotate([-90, 0, 0])
                    cylinder(h = arm_len, d = arm_d, $fn = fn);
            translate([plate_w / 2, plate_t + arm_len - 3, arm_z])  // end stop flange
                rotate([-90, 0, 0])
                    cylinder(h = 3, d = stop_d, $fn = fn);
        }
        for (z = [screw_z1, screw_z2])                          // wall screw holes (along Y)
            translate([plate_w / 2, -eps, z])
                rotate([-90, 0, 0])
                    cylinder(h = plate_t + 2 * eps, d = screw_d + clear, $fn = fn);
    }
}
