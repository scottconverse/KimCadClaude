// bracket.scad — L bracket (two arms at 90°) with mounting holes. Units mm.
// Keep `thick` >= 3 mm for load-bearing parts on a 0.4 mm nozzle.
//
//   l_bracket(arm, width, thick, screw, inset)
//     arm   : length of each arm (mm)
//     width : bracket width (mm)
//     thick : material thickness (mm)
//     screw : metric screw size for mounting holes (e.g. 4 = M4)
//     inset : hole distance from arm end / side edges (mm)

// Relative (same-dir) include: library files sit beside each other, so this resolves to
// library/fasteners.scad. The library/ prefix convention applies to model-generated code
// the sanitizer checks — not to one trusted library module pulling in another.
use <fasteners.scad>;

module l_bracket(arm = 40, width = 30, thick = 4, screw = 4, inset = 8) {
    eps = 0.01;
    difference() {
        union() {
            cube([arm, width, thick]);   // base arm, lies in XY
            cube([thick, width, arm]);   // upright arm, rises in Z
        }
        // holes through the base arm (cut along Z)
        for (y = [inset, width - inset])
            translate([arm - inset, y, -eps])
                screw_clearance_hole(screw, thick + 2 * eps);
        // holes through the upright arm (cut along X)
        for (y = [inset, width - inset])
            translate([-eps, y, arm - inset])
                rotate([0, 90, 0])
                    screw_clearance_hole(screw, thick + 2 * eps);
    }
}
