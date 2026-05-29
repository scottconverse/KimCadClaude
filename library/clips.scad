// clips.scad — cable / cord clips. Units mm.
//
//   cable_clip(cable_d, width, screw_d, wall, fn)
//     A screw-down saddle clip: a block straddling the cable along X (its `width`),
//     with a half-round channel cut along the top for the cable, and one screw hole
//     through the base beside the channel. Prints flat, no supports.
//     Bounding box = [width, cable_d + 5*wall + screw_d, cable_d/2 + 2*wall].
//     The cable-fit clearance lives only in the channel cut, never in the envelope.

module cable_clip(cable_d = 6, width = 20, screw_d = 4, wall = 3, fn = 48) {
    eps = 0.05;
    clear = 0.2;
    chan_r = (cable_d + clear) / 2;               // bore radius carries the fit clearance
    body_y = cable_d + 2 * wall;                 // depth of the saddle around the cable
    tab_y = screw_d + 3 * wall;                  // mounting-tab depth beside the saddle
    depth = body_y + tab_y;                       // total Y
    height = cable_d / 2 + 2 * wall;               // Z: nominal cable radius + walls (no clearance)
    chan_cy = body_y / 2;                          // cable centred across the saddle depth
    difference() {
        cube([width, depth, height]);              // solid block
        // half-round cable channel cut along X, open at the top
        translate([-eps, chan_cy, height])
            rotate([0, 90, 0])
                cylinder(h = width + 2 * eps, r = chan_r, $fn = fn);
        // screw hole through the mounting tab (along Z)
        translate([width / 2, body_y + tab_y / 2, -eps])
            cylinder(h = height + 2 * eps, d = screw_d + clear, $fn = fn);
    }
}
