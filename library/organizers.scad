// organizers.scad — drawer dividers and trays. Units mm.
//
//   drawer_divider(length, depth, height, panel_t, compartments, fn)
//     A rectangular divider frame (four outer panels, open top and bottom) split into
//     `compartments` equal cells by (compartments-1) cross walls running across the
//     depth. length = X, depth = Y, height = Z.
//     Bounding box = [length, depth, height].

module drawer_divider(length = 150, depth = 80, height = 50,
                      panel_t = 2, compartments = 3, fn = 32) {
    eps = 0.05;
    // outer frame: hollow box with no floor or ceiling -> four upright walls
    difference() {
        cube([length, depth, height]);
        translate([panel_t, panel_t, -eps])
            cube([length - 2 * panel_t, depth - 2 * panel_t, height + 2 * eps]);
    }
    // interior cross walls dividing the length into equal compartments
    if (compartments > 1)
        for (i = [1 : compartments - 1]) {
            x = i * length / compartments - panel_t / 2;
            translate([x, panel_t - eps, 0])
                cube([panel_t, depth - 2 * panel_t + 2 * eps, height]);
        }
}
