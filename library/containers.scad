// containers.scad — closed boxes, two-part enclosures, and tubes/spacers. Units mm.
//
//   snap_box(width, depth, height, wall, fn)
//     A closed, watertight box sized to its OUTER envelope [width, depth, height],
//     hollow inside. (The snap-fit lid seam itself is Phase-3 part-quality detailing;
//     Phase 1 needs the right size and a sliceable solid.)
//     Bounding box = [width, depth, height].
//
//   enclosure(inner_w, inner_d, inner_h, wall, fn)
//     A two-part enclosure sized from its INTERNAL volume; walls add on every side and
//     the lid adds on top. Bounding box = [inner_w + 2*wall, inner_d + 2*wall, inner_h + 2*wall].
//
//   tube(id, od, height, fn)
//     A plain ring / cylindrical spacer (e.g. a standoff). Bounding box = [od, od, height].

module snap_box(width = 80, depth = 60, height = 40, wall = 2, fn = 48) {
    difference() {
        cube([width, depth, height]);                        // outer solid
        translate([wall, wall, wall])                        // hollow interior
            cube([width - 2 * wall, depth - 2 * wall, height - 2 * wall]);
    }
}

module enclosure(inner_w = 80, inner_d = 50, inner_h = 30, wall = 2.5, fn = 48) {
    snap_box(inner_w + 2 * wall, inner_d + 2 * wall, inner_h + 2 * wall, wall, fn = fn);
}

module tube(id = 8, od = 16, height = 12, fn = 64) {
    eps = 0.05;
    difference() {
        cylinder(h = height, d = od, $fn = fn);
        translate([0, 0, -eps])
            cylinder(h = height + 2 * eps, d = id, $fn = fn);
    }
}
