// fasteners.scad — screw / nut / heat-set helpers for metric hardware (M2–M8).
// All units mm. Cut tools are sized for clearance fits; extend them past the
// surface (caller adds epsilon) so differences stay manifold.
//
// Modules:
//   screw_clearance_hole(size, depth, fn) : through-hole sized to clear a screw
//   counterbore(size, head_d, head_h, depth, fn) : clearance hole + cap-head pocket
//   nut_trap(size, depth, fn) : hex pocket for a captive nut
//   heatset_hole(size, depth, fn) : straight bore for a brass heat-set insert
//
// Lookup helpers return per-size values; unknown sizes fall back to a ratio.

function screw_clearance_dia(size) =
    size == 2   ? 2.4 :
    size == 2.5 ? 2.9 :
    size == 3   ? 3.4 :
    size == 4   ? 4.5 :
    size == 5   ? 5.5 :
    size == 6   ? 6.6 :
    size == 8   ? 9.0 : size * 1.12;

function nut_across_flats(size) =
    size == 2   ? 4.0 :
    size == 2.5 ? 5.0 :
    size == 3   ? 5.5 :
    size == 4   ? 7.0 :
    size == 5   ? 8.0 :
    size == 6   ? 10.0 :
    size == 8   ? 13.0 : size * 1.8;

function heatset_dia(size) =
    size == 3 ? 4.0 :
    size == 4 ? 5.6 :
    size == 5 ? 6.4 : size * 1.3;

module screw_clearance_hole(size = 3, depth = 10, fn = 32) {
    cylinder(h = depth, d = screw_clearance_dia(size), $fn = fn);
}

module counterbore(size = 3, head_d = 6.0, head_h = 3.0, depth = 12, fn = 32) {
    screw_clearance_hole(size, depth, fn);
    cylinder(h = head_h, d = head_d, $fn = fn);
}

module nut_trap(size = 3, depth = 3, fn = 6) {
    // $fn = 6 makes a hexagon; convert across-flats to across-corners diameter.
    af = nut_across_flats(size);
    cylinder(h = depth, d = af / cos(30), $fn = 6);
}

module heatset_hole(size = 3, depth = 6, fn = 32) {
    cylinder(h = depth, d = heatset_dia(size), $fn = fn);
}
