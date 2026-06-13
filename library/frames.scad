// frames.scad — picture / art frames and framing boards. Units mm.
// All modules build corner-at-origin (the cube([x,y,z]) idiom) so the bounding box is the
// exact envelope. Each module documents its analytic bounding box; the family registry pins
// the same formula and tests/test_library_modules.py renders it to confirm (#19).
//
//   picture_frame(opening_w, opening_h, border, rabbet, depth, lip)
//     A rectangular frame: a solid face with a through window and a back rabbet (wider than
//     the window by `lip` each side, `rabbet` deep) that seats glass + art + backing.
//     Bounding box = [opening_w + 2*border, opening_h + 2*border, depth]. (border > lip.)
//
//   mat_board(mat_w, mat_h, window_w, window_h, mat_t)
//     A flat framing mat: a thin sheet with a centered straight-walled window.
//     Bounding box = [mat_w, mat_h, mat_t].
//
//   floating_frame(opening_w, opening_h, lip_w, gap, depth, back_t)
//     A floating frame: an open front with a recessed back shelf so the art sits with a
//     shadow gap inside the surrounding lip.
//     Bounding box = [opening_w + 2*gap + 2*lip_w, opening_h + 2*gap + 2*lip_w, depth].
//
//   shadow_box_frame(opening_w, opening_h, border, cavity_depth, rabbet, back_t, lip)
//     A deep shadow box: a solid back, a blind display cavity, and a front glass rabbet.
//     Bounding box = [opening_w + 2*border, opening_h + 2*border, cavity_depth + rabbet + back_t].
//
//   lithophane_frame(outer_w, outer_h, face_rim, light_gap, panel_t, face_rim_t)
//     A backlit lithophane frame: a front face rim with a viewing window, a panel rebate, and
//     an open-back light cavity for an LED strip.
//     Bounding box = [outer_w, outer_h, face_rim_t + panel_t + light_gap].

module picture_frame(opening_w = 90, opening_h = 130, border = 12, rabbet = 4, depth = 10,
                     lip = 3) {
    eps = 0.05;
    ow = opening_w + 2 * border;
    oh = opening_h + 2 * border;
    difference() {
        cube([ow, oh, depth]);
        // visible through window
        translate([border, border, -eps])
            cube([opening_w, opening_h, depth + 2 * eps]);
        // back rabbet: wider than the window by `lip` each side, `rabbet` deep from the back
        translate([border - lip, border - lip, -eps])
            cube([opening_w + 2 * lip, opening_h + 2 * lip, rabbet + eps]);
    }
}

module mat_board(mat_w = 130, mat_h = 160, window_w = 90, window_h = 120, mat_t = 2) {
    eps = 0.05;
    difference() {
        cube([mat_w, mat_h, mat_t]);
        translate([(mat_w - window_w) / 2, (mat_h - window_h) / 2, -eps])
            cube([window_w, window_h, mat_t + 2 * eps]);
    }
}

module floating_frame(opening_w = 90, opening_h = 90, lip_w = 10, gap = 5, depth = 20,
                      back_t = 3) {
    eps = 0.05;
    ow = opening_w + 2 * gap + 2 * lip_w;
    oh = opening_h + 2 * gap + 2 * lip_w;
    difference() {
        cube([ow, oh, depth]);
        // front-open cavity holding the art on the back shelf, with the shadow gap around it
        translate([lip_w, lip_w, back_t])
            cube([opening_w + 2 * gap, opening_h + 2 * gap, depth - back_t + eps]);
    }
}

module shadow_box_frame(opening_w = 80, opening_h = 80, border = 12, cavity_depth = 25,
                        rabbet = 4, back_t = 3, lip = 3) {
    eps = 0.05;
    ow = opening_w + 2 * border;
    oh = opening_h + 2 * border;
    depth = cavity_depth + rabbet + back_t;
    difference() {
        cube([ow, oh, depth]);
        // blind display cavity above the solid back
        translate([border, border, back_t])
            cube([opening_w, opening_h, cavity_depth + eps]);
        // front glass rabbet, wider than the cavity by `lip` each side
        translate([border - lip, border - lip, back_t + cavity_depth])
            cube([opening_w + 2 * lip, opening_h + 2 * lip, rabbet + eps]);
    }
}

module lithophane_frame(outer_w = 100, outer_h = 120, face_rim = 8, light_gap = 12,
                        panel_t = 3, face_rim_t = 2) {
    eps = 0.05;
    depth = face_rim_t + panel_t + light_gap;
    difference() {
        cube([outer_w, outer_h, depth]);
        // front viewing window through the face rim
        translate([face_rim, face_rim, -eps])
            cube([outer_w - 2 * face_rim, outer_h - 2 * face_rim, face_rim_t + eps]);
        // panel rebate + open-back light cavity (seats the panel on the face rim)
        translate([face_rim / 2, face_rim / 2, face_rim_t])
            cube([outer_w - face_rim, outer_h - face_rim, panel_t + light_gap + eps]);
    }
}
