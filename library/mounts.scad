// mounts.scad — hole-grid and VESA-style mounting patterns. Units mm.
// Produces cut tools (cylinders) to subtract from a plate; the caller wraps these
// in difference(). Origin is the first hole; extend depth past the plate for a
// manifold cut.
//
//   hole_grid(cols, rows, dx, dy, size, depth, fn) : rectangular grid of screw holes
//   vesa(pattern, size, depth, fn)                 : square 4-hole pattern (e.g. 75/100)

use <fasteners.scad>;

module hole_grid(cols = 2, rows = 2, dx = 20, dy = 20, size = 4, depth = 12, fn = 32) {
    for (i = [0 : cols - 1], j = [0 : rows - 1])
        translate([i * dx, j * dy, 0])
            screw_clearance_hole(size, depth, fn);
}

module vesa(pattern = 100, size = 4, depth = 12, fn = 32) {
    for (x = [0, pattern], y = [0, pattern])
        translate([x, y, 0])
            screw_clearance_hole(size, depth, fn);
}
