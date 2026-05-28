// fillets.scad — rounding helpers that avoid the expensive minkowski() idiom.
// All units mm. These use cheap 2D operations (hull of circles / offset), never
// 3D minkowski, so they are safe at normal $fn.
//
//   rounded_rect(width, depth, r, fn)        : 2D rounded rectangle
//   rounded_box(width, depth, height, r, fn) : extruded rounded box (vertical edges)
//   rounded_plate(width, depth, height, r, fn): alias for a flat rounded slab

module rounded_rect(width = 40, depth = 30, r = 3, fn = 32) {
    hull()
        for (x = [r, width - r], y = [r, depth - r])
            translate([x, y]) circle(r = r, $fn = fn);
}

module rounded_box(width = 40, depth = 30, height = 20, r = 3, fn = 32) {
    linear_extrude(height = height)
        rounded_rect(width, depth, r, fn);
}

module rounded_plate(width = 50, depth = 50, height = 10, r = 3, fn = 32) {
    rounded_box(width, depth, height, r, fn);
}
