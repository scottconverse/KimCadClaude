// box.scad — parameterized box: walls, floor, optional closed top.
// All units mm. Minimum FDM wall on a 0.4 mm nozzle is ~0.8; default 2.0 is sturdy.
//
//   box(width, depth, height, wall, floor, open_top)
//     width, depth, height : outer envelope (mm)
//     wall     : side-wall thickness (mm, keep >= 0.8)
//     floor    : floor/base thickness (mm)
//     open_top : true = open container, false = fully enclosed solid box

module box(width = 60, depth = 40, height = 30, wall = 2.0, floor = 2.0, open_top = true) {
    difference() {
        cube([width, depth, height]);
        translate([wall, wall, floor])
            cube([
                width  - 2 * wall,
                depth  - 2 * wall,
                height - floor + (open_top ? 1 : -wall)   // +1 breaks the top surface
            ]);
    }
}
