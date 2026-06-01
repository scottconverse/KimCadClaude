// styles.jsx — full KimCad visual system (consumes :root design tokens).
window.KC_CSS = `
.kc-shell{height:100vh;display:flex;flex-direction:column;font-size:calc(15px*var(--fs,1));}

/* ── Top chrome ── */
.kc-topbar{height:58px;flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;
  padding:0 18px;border-bottom:1px solid var(--hair);background:var(--surface);}
.kc-brand{display:flex;align-items:center;gap:11px;}
.kc-cube{width:32px;height:32px;border-radius:9px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;}
.kc-wordmark{font-family:var(--font-display);font-size:21px;font-weight:600;letter-spacing:-.015em;color:var(--ink);}
.kc-wordmark b{font-weight:800;color:var(--accent);}
.kc-top-right{display:flex;align-items:center;gap:10px;}
.kc-printer-chip{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:var(--ink);
  padding:7px 12px;border-radius:10px;border:1px solid var(--hair);background:var(--surface-2);}
.kc-printer-chip i{font-style:normal;font-family:var(--font-mono);font-size:11px;color:var(--muted);}
.kc-dot{width:7px;height:7px;border-radius:50%;background:#2f9e6a;box-shadow:0 0 0 3px color-mix(in srgb,#2f9e6a 22%,transparent);flex:0 0 auto;}
.kc-backend-chip{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:var(--muted);padding:7px 11px;border-radius:10px;border:1px solid var(--hair);}
.kc-backend-chip svg{color:var(--accent);}
.kc-newbtn{font:inherit;font-size:12.5px;font-weight:600;padding:8px 15px;border-radius:10px;border:0;background:var(--ink);color:var(--bg);cursor:pointer;transition:.15s;}
.kc-newbtn:hover{opacity:.84;}

/* ── Main layout ── */
.kc-main{flex:1;min-height:0;display:grid;grid-template-columns:360px 1fr 392px;}
.kc-col-left{border-right:1px solid var(--hair);background:var(--surface);min-height:0;display:flex;flex-direction:column;}
.kc-col-center{position:relative;min-width:0;background:var(--bg);padding:14px;display:flex;}
.kc-col-right{border-left:1px solid var(--hair);background:var(--bg);padding:calc(15px*var(--pad));
  display:flex;flex-direction:column;gap:calc(14px*var(--gap));overflow-y:auto;}
.kc-viewport{position:relative;flex:1;border-radius:16px;overflow:hidden;border:1px solid var(--hair-strong);}

/* ── Conversation ── */
.kc-chat{display:flex;flex-direction:column;height:100%;min-height:0;}
.kc-panel-hd{padding:15px 16px 8px;}
.kc-eyebrow{font-size:11px;font-weight:700;letter-spacing:.11em;text-transform:uppercase;color:var(--muted);}
.kc-chat-list{flex:1;overflow-y:auto;padding:8px 16px 16px;display:flex;flex-direction:column;gap:14px;}
.kc-msg{display:flex;gap:9px;}
.kc-msg-user{flex-direction:row-reverse;}
.kc-ava{width:28px;height:28px;border-radius:9px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;flex:0 0 auto;}
.kc-ava-busy{animation:kc-pulse 1.2s ease-in-out infinite;}
.kc-bubble-wrap{display:flex;flex-direction:column;gap:8px;min-width:0;max-width:85%;}
.kc-msg-user .kc-bubble-wrap{align-items:flex-end;}
.kc-bubble{padding:10px 13px;border-radius:15px;font-size:calc(14px*var(--fs));line-height:1.5;text-wrap:pretty;}
.kc-bubble-ai{background:var(--surface-2);border:1px solid var(--hair);border-top-left-radius:5px;color:var(--ink);}
.kc-bubble-user{background:var(--accent);color:#fff;border-top-right-radius:5px;}
.kc-bubble-clarify{background:color-mix(in srgb,var(--accent) 9%,var(--surface));border-color:color-mix(in srgb,var(--accent) 28%,transparent);}
.kc-quick{display:flex;flex-wrap:wrap;gap:7px;}
.kc-chip{font:inherit;font-size:calc(13px*var(--fs));padding:7px 13px;border-radius:999px;border:1px solid var(--hair-strong);
  background:var(--surface);color:var(--ink);cursor:pointer;transition:.15s;}
.kc-chip:hover{border-color:var(--accent);color:var(--accent);}
.kc-chip-accent{border-color:color-mix(in srgb,var(--accent) 42%,transparent);background:color-mix(in srgb,var(--accent) 8%,var(--surface));font-weight:600;}
.kc-chip-accent:hover{background:var(--accent);color:#fff;border-color:var(--accent);}
.kc-think{background:var(--surface-2);border:1px solid var(--hair);border-radius:15px;border-top-left-radius:5px;padding:12px 13px;display:flex;flex-direction:column;gap:10px;}
.kc-think-row{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--muted);transition:.2s;}
.kc-think-row.active{color:var(--ink);font-weight:600;}
.kc-think-dot{width:16px;height:16px;display:flex;align-items:center;justify-content:center;color:var(--accent);flex:0 0 auto;}
.kc-think-row:not(.active):not(.done) .kc-think-dot{opacity:.35;}
.kc-spin{width:11px;height:11px;border-radius:50%;border:2px solid color-mix(in srgb,var(--accent) 28%,transparent);
  border-top-color:var(--accent);animation:kc-spin .7s linear infinite;display:inline-block;}

/* ── Composer ── */
.kc-composer{flex:0 0 auto;border-top:1px solid var(--hair);padding:12px 14px;background:var(--surface);display:flex;flex-direction:column;gap:9px;}
.kc-refine-row{display:flex;flex-wrap:wrap;gap:7px;}
.kc-point-chip{display:flex;align-items:center;gap:7px;align-self:flex-start;padding:6px 8px 6px 10px;border-radius:10px;
  background:color-mix(in srgb,var(--accent) 12%,var(--surface));border:1px solid color-mix(in srgb,var(--accent) 35%,transparent);color:var(--accent);}
.kc-x-mini{border:0;background:transparent;color:inherit;cursor:pointer;display:flex;padding:2px;border-radius:5px;}
.kc-x-mini:hover{background:color-mix(in srgb,var(--accent) 20%,transparent);}
.kc-input-row{display:flex;gap:8px;align-items:flex-end;}
.kc-input{flex:1;resize:none;border:1px solid var(--hair-strong);border-radius:12px;padding:11px 13px;font:inherit;
  font-size:calc(14px*var(--fs));background:var(--bg);color:var(--ink);max-height:120px;line-height:1.4;outline:none;}
.kc-input:focus{border-color:var(--accent);}
.kc-send{flex:0 0 auto;width:42px;height:42px;border-radius:12px;border:0;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:.15s;}
.kc-send:disabled{opacity:.4;cursor:default;}
.kc-send:not(:disabled):hover{filter:brightness(1.08);}

/* ── Cards ── */
.kc-card{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:calc(15px*var(--pad));display:flex;flex-direction:column;gap:calc(11px*var(--gap));}
.kc-card-hd{display:flex;align-items:center;justify-content:space-between;gap:10px;}
.kc-card-title{display:flex;align-items:center;gap:8px;font-family:var(--font-display);font-weight:600;font-size:calc(15px*var(--fs));color:var(--ink);}
.kc-card-title svg{color:var(--accent);}
.kc-card-sub{font-size:calc(12px*var(--fs));color:var(--muted);margin-top:-5px;line-height:1.45;}
.kc-mini-toggle{display:flex;align-items:center;gap:5px;font:inherit;font-size:11.5px;font-weight:600;padding:5px 9px;border-radius:8px;
  border:1px solid var(--hair-strong);background:var(--surface);color:var(--muted);cursor:pointer;transition:.15s;white-space:nowrap;flex:0 0 auto;}
.kc-mini-toggle.on{color:var(--accent);border-color:var(--accent);background:color-mix(in srgb,var(--accent) 8%,var(--surface));}

/* ── Parameters ── */
.kc-params{display:flex;flex-direction:column;gap:calc(13px*var(--gap));}
.kc-prow{display:flex;flex-direction:column;gap:8px;}
.kc-plabel{display:flex;justify-content:space-between;align-items:baseline;font-size:calc(13px*var(--fs));}
.kc-plabel>span:first-child{color:var(--ink);font-weight:500;display:flex;align-items:center;gap:6px;white-space:nowrap;}
.kc-axis{font-family:var(--font-mono);font-size:9.5px;font-weight:600;color:var(--muted);background:var(--surface-2);
  border:1px solid var(--hair);border-radius:4px;padding:1px 4px;font-style:normal;}
.kc-pval{font-family:var(--font-mono);font-size:13px;font-weight:600;color:var(--ink);}
.kc-pval i{color:var(--muted);font-style:normal;font-size:11px;margin-left:2px;}
.kc-range{-webkit-appearance:none;appearance:none;width:100%;height:5px;border-radius:999px;
  background:linear-gradient(to right,var(--accent) var(--pct,50%),var(--hair-strong) var(--pct,50%));outline:none;cursor:pointer;}
.kc-range::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:17px;height:17px;border-radius:50%;
  background:var(--surface);border:2px solid var(--accent);box-shadow:0 1px 4px rgba(0,0,0,.22);cursor:grab;}
.kc-range::-moz-range-thumb{width:17px;height:17px;border-radius:50%;background:var(--surface);border:2px solid var(--accent);cursor:grab;}
.kc-code{font-family:var(--font-mono);font-size:11.5px;line-height:1.6;background:var(--viewport-bg);color:#cdd6e3;
  border-radius:10px;padding:13px;max-height:230px;overflow:auto;white-space:pre;margin:0;}

/* ── Printability ── */
.kc-verdict{font-size:11.5px;font-weight:700;padding:4px 10px;border-radius:999px;white-space:nowrap;}
.kc-verdict-pass{background:color-mix(in srgb,#2f9e6a 15%,var(--surface));color:#1d7a4e;}
.kc-verdict-warn{background:color-mix(in srgb,#c9962f 20%,var(--surface));color:#876312;}
.kc-verdict-fail{background:color-mix(in srgb,#c8623a 18%,var(--surface));color:#a8431f;}
.kc-mat-row{display:flex;align-items:center;justify-content:space-between;gap:12px;}
.kc-mat-lbl{font-size:13px;color:var(--muted);font-weight:500;}
.kc-seg{display:flex;gap:3px;background:var(--surface-2);border:1px solid var(--hair);border-radius:9px;padding:3px;flex:1;max-width:230px;}
.kc-seg-btn{flex:1;border:0;background:transparent;font:inherit;font-size:12px;font-weight:600;padding:5px 6px;border-radius:6px;color:var(--muted);cursor:pointer;transition:.12s;}
.kc-seg-btn.on{background:var(--surface);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.1);}
.kc-checks{display:flex;flex-direction:column;gap:8px;}
.kc-check{display:flex;gap:9px;align-items:flex-start;padding:9px 11px;border-radius:11px;background:var(--surface-2);border:1px solid var(--hair);}
.kc-check-ic{flex:0 0 auto;width:19px;height:19px;border-radius:6px;display:flex;align-items:center;justify-content:center;margin-top:1px;}
.kc-check-pass .kc-check-ic{background:color-mix(in srgb,#2f9e6a 18%,transparent);color:#1d7a4e;}
.kc-check-warn .kc-check-ic{background:color-mix(in srgb,#c9962f 22%,transparent);color:#876312;}
.kc-check-fail .kc-check-ic{background:color-mix(in srgb,#c8623a 20%,transparent);color:#a8431f;}
.kc-check-lbl{font-size:13px;font-weight:600;color:var(--ink);line-height:1.35;white-space:nowrap;}
.kc-check-det{font-size:11.5px;color:var(--muted);line-height:1.45;margin-top:1px;}

/* ── Buttons ── */
.kc-btn-primary{display:flex;align-items:center;justify-content:center;gap:8px;font:inherit;font-size:14px;font-weight:600;
  padding:12px 16px;border-radius:12px;border:0;background:var(--accent);color:#fff;cursor:pointer;transition:.15s;white-space:nowrap;}
.kc-btn-primary:hover:not(:disabled){filter:brightness(1.08);}
.kc-btn-primary:disabled{opacity:.5;cursor:default;}
.kc-block{width:100%;}
.kc-spin-light{border-color:rgba(255,255,255,.4);border-top-color:#fff;}
.kc-btn-ghost{font:inherit;font-size:13px;font-weight:600;padding:11px 15px;border-radius:11px;border:1px solid var(--hair-strong);
  background:var(--surface);color:var(--ink);cursor:pointer;transition:.15s;white-space:nowrap;}
.kc-btn-ghost:hover{border-color:var(--accent);color:var(--accent);}

/* ── Report ── */
.kc-report{border-color:color-mix(in srgb,var(--accent) 24%,var(--hair));}
.kc-conf{font-size:11px;font-weight:700;text-transform:capitalize;padding:4px 9px;border-radius:999px;white-space:nowrap;}
.kc-conf-high{background:color-mix(in srgb,#2f9e6a 15%,var(--surface));color:#1d7a4e;}
.kc-conf-medium{background:color-mix(in srgb,#c9962f 18%,var(--surface));color:#876312;}
.kc-conf-low{background:color-mix(in srgb,#c8623a 16%,var(--surface));color:#a8431f;}
.kc-report-rows{display:flex;flex-direction:column;}
.kc-rrow{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--hair);font-size:13px;}
.kc-rrow:last-child{border-bottom:0;}
.kc-rk{color:var(--muted);}
.kc-rv{color:var(--ink);font-weight:600;text-align:right;font-family:var(--font-mono);font-size:12.5px;}
.kc-rhint{display:block;font-family:var(--font-body);font-weight:400;font-size:11px;color:var(--muted);margin-top:2px;}
.kc-report-warn{display:flex;gap:8px;align-items:flex-start;font-size:12px;color:#876312;
  background:color-mix(in srgb,#c9962f 12%,var(--surface));border:1px solid color-mix(in srgb,#c9962f 28%,transparent);
  border-radius:10px;padding:9px 11px;line-height:1.45;}
.kc-report-warn svg{flex:0 0 auto;margin-top:1px;color:#876312;}
.kc-dl-row{display:flex;gap:8px;}
.kc-grow{flex:1;}
.kc-dl-note{font-size:11px;color:var(--muted);line-height:1.45;}

/* ── Version rail ── */
.kc-verrail{position:absolute;left:14px;bottom:14px;right:14px;display:flex;align-items:center;gap:12px;
  background:rgba(0,0,0,.4);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.12);border-radius:12px;padding:8px 12px;}
.kc-ver-lbl{display:flex;align-items:center;gap:6px;font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:rgba(255,255,255,.65);flex:0 0 auto;}
.kc-ver-track{display:flex;gap:8px;overflow-x:auto;}
.kc-ver-node{display:flex;flex-direction:column;gap:1px;align-items:flex-start;padding:5px 11px;border-radius:9px;
  border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);color:#fff;cursor:pointer;white-space:nowrap;transition:.15s;}
.kc-ver-node:hover{background:rgba(255,255,255,.13);}
.kc-ver-node.on{background:var(--accent);border-color:var(--accent);}
.kc-ver-tag{font-family:var(--font-mono);font-size:11px;font-weight:700;}
.kc-ver-note{font-size:10.5px;opacity:.82;}

/* ── Viewport overlays ── */
.kc-vp-toolbar{position:absolute;top:14px;left:14px;right:14px;display:flex;align-items:center;justify-content:space-between;gap:10px;pointer-events:none;}
.kc-vp-btn{pointer-events:auto;display:flex;align-items:center;gap:7px;font:inherit;font-size:12.5px;font-weight:600;
  padding:8px 13px;border-radius:10px;border:1px solid rgba(255,255,255,.16);background:rgba(0,0,0,.36);backdrop-filter:blur(10px);color:#fff;cursor:pointer;transition:.15s;}
.kc-vp-btn:hover{background:rgba(0,0,0,.52);}
.kc-vp-btn.on{background:var(--accent);border-color:var(--accent);}
.kc-vp-info{display:flex;align-items:center;gap:6px;font-size:11px;color:rgba(255,255,255,.6);font-family:var(--font-mono);}
.kc-pick-banner{position:absolute;top:62px;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:7px;
  font-size:12.5px;font-weight:600;color:#fff;background:var(--accent);padding:8px 15px;border-radius:999px;box-shadow:0 8px 24px rgba(0,0,0,.32);animation:kc-fadeup .3s ease both;}
.kc-vp-empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;color:rgba(255,255,255,.4);}
.kc-scan{color:rgba(255,255,255,.28);}
.kc-scan.on{color:var(--accent);animation:kc-pulse 1.1s ease-in-out infinite;}
.kc-vp-empty-txt{font-family:var(--font-mono);font-size:13px;letter-spacing:.02em;}
.kc-right-empty{display:flex;flex-direction:column;gap:13px;align-items:center;text-align:center;padding:46px 24px;color:var(--muted);}
.kc-right-empty svg{color:var(--accent);opacity:.6;}
.kc-right-empty p{font-size:13px;line-height:1.55;max-width:250px;margin:0;}

/* ── Landing ── */
.kc-landing{flex:1;min-height:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;position:relative;background:var(--bg);}
.kc-hero{width:100%;max-width:680px;display:flex;flex-direction:column;align-items:center;text-align:center;gap:18px;}
.kc-hero-badge{display:flex;align-items:center;gap:8px;font-size:12.5px;font-weight:600;color:var(--muted);padding:7px 14px;border-radius:999px;border:1px solid var(--hair-strong);background:var(--surface);white-space:nowrap;}
.kc-hero-title{font-family:var(--font-display);font-size:clamp(30px,4.4vw,47px);font-weight:700;line-height:1.04;letter-spacing:-.02em;color:var(--ink);margin:0;}
.kc-hero-sub{font-size:16px;line-height:1.55;color:var(--muted);margin:0;max-width:470px;}
.kc-hero-input-wrap{width:100%;display:flex;gap:10px;align-items:flex-end;background:var(--surface);border:1.5px solid var(--hair-strong);
  border-radius:18px;padding:12px;box-shadow:0 18px 50px -22px rgba(0,0,0,.4);transition:.2s;}
.kc-hero-input-wrap:focus-within{border-color:var(--accent);}
.kc-hero-input{flex:1;resize:none;border:0;background:transparent;font:inherit;font-size:16px;line-height:1.45;color:var(--ink);outline:none;padding:6px 8px;}
.kc-hero-send{flex:0 0 auto;display:flex;align-items:center;gap:8px;font:inherit;font-size:15px;font-weight:600;padding:13px 20px;border-radius:13px;border:0;background:var(--accent);color:#fff;cursor:pointer;transition:.15s;}
.kc-hero-send:disabled{opacity:.45;cursor:default;}
.kc-hero-send:not(:disabled):hover{filter:brightness(1.08);}
.kc-examples{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:center;margin-top:2px;}
.kc-ex-lbl{font-size:13px;color:var(--muted);font-weight:600;}
.kc-example{font:inherit;font-size:13px;padding:8px 14px;border-radius:999px;border:1px solid var(--hair);background:var(--surface);color:var(--ink);cursor:pointer;transition:.15s;white-space:nowrap;}
.kc-example:hover{border-color:var(--accent);color:var(--accent);}
.kc-hero-foot{position:absolute;bottom:26px;display:flex;align-items:center;gap:14px;font-size:13px;color:var(--muted);}
.kc-hero-foot b{color:var(--accent);font-family:var(--font-mono);}
.kc-hero-foot i{width:22px;height:1px;background:var(--hair-strong);}

/* ── Toast ── */
.kc-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--ink);color:var(--bg);
  font-size:13px;font-weight:500;padding:11px 18px;border-radius:12px;box-shadow:0 14px 34px rgba(0,0,0,.28);z-index:9999;animation:kc-fadeup .25s ease both;}

/* ── v3.0: Model picker ── */
.kc-mp{position:relative;}
.kc-mp-btn{display:flex;align-items:center;gap:8px;font:inherit;font-size:12.5px;font-weight:600;color:var(--ink);
  padding:7px 11px;border-radius:10px;border:1px solid var(--hair);background:var(--surface-2);cursor:pointer;transition:.15s;}
.kc-mp-btn:hover{border-color:var(--hair-strong);}
.kc-mp-btn svg:last-child{color:var(--muted);}
.kc-mp-name{display:flex;align-items:baseline;gap:6px;}
.kc-mp-name i{font-style:normal;font-family:var(--font-mono);font-size:10.5px;color:var(--muted);}
.kc-mp-menu{position:absolute;top:calc(100% + 8px);right:0;width:312px;background:var(--surface);border:1px solid var(--hair-strong);
  border-radius:14px;box-shadow:0 20px 54px -20px rgba(0,0,0,.42);padding:7px;z-index:9000;}
.kc-mp-hd{font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);padding:8px 10px 6px;}
.kc-mp-row{display:flex;align-items:flex-start;gap:10px;width:100%;text-align:left;padding:10px;border-radius:10px;border:0;background:transparent;cursor:pointer;transition:.12s;}
.kc-mp-row:hover{background:var(--surface-2);}
.kc-mp-row.on{background:color-mix(in srgb,var(--accent) 8%,var(--surface));}
.kc-mp-row .kc-dot{margin-top:5px;}
.kc-mp-info{display:flex;flex-direction:column;gap:2px;flex:1;min-width:0;}
.kc-mp-row-top{font-size:13.5px;font-weight:600;color:var(--ink);display:flex;align-items:baseline;gap:7px;}
.kc-mp-row-top i{font-style:normal;font-size:10.5px;font-weight:600;color:var(--accent);background:color-mix(in srgb,var(--accent) 11%,transparent);padding:1px 6px;border-radius:5px;}
.kc-mp-desc{font-size:11.5px;color:var(--muted);line-height:1.4;}
.kc-mp-check{color:var(--accent);margin-top:2px;}
.kc-mp-foot{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--muted);padding:9px 10px 6px;border-top:1px solid var(--hair);margin-top:4px;line-height:1.4;}
.kc-mp-foot svg{color:var(--accent);flex:0 0 auto;}

/* ── v3.0: Landing photo on-ramp ── */
.kc-or-photo{display:flex;align-items:center;gap:14px;width:100%;max-width:540px;margin-top:6px;}
.kc-or-line{flex:1;height:1px;background:var(--hair-strong);}
.kc-photo-link{display:flex;align-items:center;gap:8px;font:inherit;font-size:13px;color:var(--muted);background:transparent;border:0;cursor:pointer;white-space:nowrap;transition:.15s;}
.kc-photo-link svg{color:var(--accent);}
.kc-photo-link b{color:var(--accent);font-weight:600;}
.kc-photo-link:hover{color:var(--ink);}

/* ── v3.0: Modals ── */
.kc-modal-scrim{position:fixed;inset:0;background:color-mix(in srgb,var(--ink) 42%,transparent);backdrop-filter:blur(4px);
  display:flex;align-items:center;justify-content:center;z-index:9500;padding:24px;}
.kc-modal{width:100%;max-width:480px;background:var(--surface);border:1px solid var(--hair-strong);border-radius:20px;
  box-shadow:0 32px 80px -28px rgba(0,0,0,.55);padding:22px;display:flex;flex-direction:column;gap:16px;max-height:90vh;overflow-x:hidden;overflow-y:auto;}
.kc-modal-hd{display:flex;align-items:center;justify-content:space-between;}
.kc-modal-title{display:flex;align-items:center;gap:9px;font-family:var(--font-display);font-size:18px;font-weight:700;color:var(--ink);}
.kc-modal-title svg{color:var(--accent);}
.kc-modal-sub{font-size:13.5px;color:var(--muted);line-height:1.5;margin:0;}

.kc-dropzone{display:flex;flex-direction:column;align-items:center;gap:7px;text-align:center;padding:30px 20px;border-radius:14px;
  border:1.5px dashed var(--hair-strong);background:var(--surface-2);color:var(--muted);cursor:pointer;transition:.15s;}
.kc-dropzone:hover{border-color:var(--accent);color:var(--ink);background:color-mix(in srgb,var(--accent) 5%,var(--surface-2));}
.kc-dropzone svg{color:var(--accent);}
.kc-dz-main{font-size:14px;font-weight:600;color:var(--ink);}
.kc-dz-main b{color:var(--accent);}
.kc-dz-sub{font-size:11.5px;}
.kc-sample-btn{display:flex;align-items:center;justify-content:center;gap:8px;font:inherit;font-size:13px;font-weight:600;
  padding:11px;border-radius:11px;border:1px solid var(--hair-strong);background:var(--surface);color:var(--ink);cursor:pointer;transition:.15s;}
.kc-sample-btn:hover{border-color:var(--accent);color:var(--accent);}
.kc-sample-btn svg{color:var(--accent);}
.kc-disclose{display:flex;gap:8px;align-items:flex-start;font-size:11.5px;color:var(--muted);line-height:1.5;
  background:var(--surface-2);border:1px solid var(--hair);border-radius:10px;padding:10px 12px;}
.kc-disclose svg{flex:0 0 auto;margin-top:1px;color:#c9962f;}
.kc-disclose b{color:var(--ink);font-weight:600;}

.kc-analyzing{display:flex;flex-direction:column;align-items:center;gap:16px;padding:8px 0;}
.kc-photo-frame{position:relative;width:200px;height:150px;border-radius:14px;overflow:hidden;border:1px solid var(--hair-strong);background:var(--viewport-bg);}
.kc-photo-frame img{width:100%;height:100%;object-fit:cover;}
.kc-photo-ph{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;color:rgba(255,255,255,.4);font-family:var(--font-mono);font-size:11px;}
.kc-scanline{position:absolute;left:0;right:0;height:34%;top:0;background:linear-gradient(to bottom,color-mix(in srgb,var(--accent) 36%,transparent),transparent);
  border-bottom:1.5px solid var(--accent);animation:kc-scan 1.7s ease-in-out infinite;}
@keyframes kc-scan{0%{top:-34%;}100%{top:100%;}}
.kc-analyze-txt{display:flex;align-items:center;gap:9px;font-size:13.5px;color:var(--ink);font-weight:500;}

.kc-plan{display:flex;flex-direction:column;gap:14px;}
.kc-plan-top{display:flex;gap:13px;align-items:center;}
.kc-photo-sm{width:84px;height:84px;flex:0 0 auto;border-radius:12px;}
.kc-photo-sm .kc-photo-ph{color:rgba(255,255,255,.45);}
.kc-plan-head{display:flex;flex-direction:column;gap:4px;}
.kc-plan-type{font-family:var(--font-display);font-size:18px;font-weight:700;color:var(--ink);line-height:1.1;}
.kc-plan-conf{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);}
.kc-plan-conf svg{color:var(--accent);}
.kc-plan-fields{display:flex;flex-direction:column;gap:2px;}
.kc-plan-field{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--hair);}
.kc-plan-field:last-child{border-bottom:0;}
.kc-pf-lbl{font-size:13px;color:var(--ink);}
.kc-pf-val{display:flex;align-items:center;gap:8px;font-family:var(--font-mono);font-size:13px;font-weight:600;color:var(--ink);}
.kc-pf-val i{font-style:normal;color:var(--muted);font-size:11px;margin-left:-4px;}
.kc-conf-pill{font-family:var(--font-body);font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:2px 6px;border-radius:5px;}
.kc-conf-high{background:color-mix(in srgb,#2f9e6a 15%,transparent);color:#1d7a4e;}
.kc-conf-medium{background:color-mix(in srgb,#c9962f 18%,transparent);color:#876312;}
.kc-conf-low{background:color-mix(in srgb,#c8623a 16%,transparent);color:#a8431f;}
.kc-seg-sm{max-width:150px;}
.kc-seg-sm .kc-seg-btn{font-size:11.5px;padding:5px 4px;}
.kc-plan-note{display:flex;gap:8px;align-items:flex-start;font-size:12px;color:#876312;line-height:1.45;
  background:color-mix(in srgb,#c9962f 11%,var(--surface));border:1px solid color-mix(in srgb,#c9962f 26%,transparent);border-radius:10px;padding:9px 11px;}
.kc-plan-note svg{flex:0 0 auto;margin-top:1px;}
.kc-plan-actions{display:flex;gap:9px;}

/* ── v3.0: Smart Mesh ── */
.kc-smartmesh{border-color:color-mix(in srgb,var(--accent) 26%,var(--hair));background:linear-gradient(180deg,color-mix(in srgb,var(--accent) 5%,var(--surface)),var(--surface));}
.kc-sm-top{display:flex;align-items:center;gap:15px;}
.kc-ring{flex:0 0 auto;}
.kc-sm-band{display:flex;flex-direction:column;gap:5px;}
.kc-sm-verdict{font-family:var(--font-display);font-size:18px;font-weight:700;line-height:1.05;}
.kc-verdict-pass-txt{color:#1d7a4e;}
.kc-verdict-warn-txt{color:#876312;}
.kc-verdict-fail-txt{color:#a8431f;}
.kc-sm-hist{display:flex;align-items:flex-start;gap:6px;font-size:12px;color:var(--muted);line-height:1.45;}
.kc-sm-hist svg{flex:0 0 auto;margin-top:1px;color:var(--accent);}
.kc-sm-sec{display:flex;flex-direction:column;gap:7px;}
.kc-sm-sec-hd{font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);}
.kc-sm-risk{display:flex;gap:9px;align-items:flex-start;padding:9px 11px;border-radius:11px;background:var(--surface-2);border:1px solid var(--hair);}
.kc-sm-recs{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px;}
.kc-sm-recs li{display:flex;gap:8px;align-items:flex-start;font-size:12.5px;color:var(--ink);line-height:1.45;}
.kc-sm-recs li svg{flex:0 0 auto;margin-top:2px;color:#1d7a4e;}
.kc-sm-foot{font-size:11px;color:var(--muted);border-top:1px solid var(--hair);padding-top:10px;line-height:1.4;}

/* ── v3.0: Report send-to-printer ── */
.kc-send-printer{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;font:inherit;font-size:13.5px;font-weight:600;
  padding:11px;border-radius:12px;border:1px solid color-mix(in srgb,var(--accent) 38%,transparent);
  background:color-mix(in srgb,var(--accent) 8%,var(--surface));color:var(--accent);cursor:pointer;transition:.15s;margin-top:2px;}
.kc-send-printer:hover{background:var(--accent);color:#fff;border-color:var(--accent);}
.kc-send-printer.done{background:color-mix(in srgb,#2f9e6a 12%,var(--surface));color:#1d7a4e;border-color:color-mix(in srgb,#2f9e6a 34%,transparent);}
.kc-send-printer.done:hover{background:#2f9e6a;color:#fff;}

/* ── v3.0: Print dialog ── */
.kc-pstatus{background:var(--viewport-bg);border-radius:14px;padding:14px;color:#e8edf4;display:flex;flex-direction:column;gap:11px;}
.kc-pstatus-hd{display:flex;align-items:center;justify-content:space-between;}
.kc-printer-name{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:600;}
.kc-pstate{font-size:11.5px;font-weight:600;color:#7ee0b0;background:rgba(47,158,106,.18);padding:3px 9px;border-radius:999px;}
.kc-pstatus-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;}
.kc-pstatus-grid>div{display:flex;align-items:center;gap:7px;font-size:12px;color:rgba(232,237,244,.7);}
.kc-pstatus-grid b{color:#fff;font-family:var(--font-mono);font-weight:600;}
.kc-pstatus-grid svg{color:rgba(232,237,244,.5);}
.kc-pconn{font-size:10.5px;color:rgba(232,237,244,.45);font-family:var(--font-mono);border-top:1px solid rgba(255,255,255,.1);padding-top:9px;}
.kc-confirm-rows{display:flex;flex-direction:column;}
.kc-crow{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--hair);font-size:13px;color:var(--muted);}
.kc-crow:last-child{border-bottom:0;}
.kc-crow b{color:var(--ink);font-family:var(--font-mono);font-size:12.5px;font-weight:600;}
.kc-sending{display:flex;align-items:center;justify-content:center;gap:10px;padding:24px;font-size:14px;color:var(--ink);}
.kc-printing{display:flex;flex-direction:column;align-items:center;gap:11px;padding:8px 0;text-align:center;}
.kc-print-ok{width:48px;height:48px;border-radius:50%;background:color-mix(in srgb,#2f9e6a 16%,transparent);color:#1d7a4e;display:flex;align-items:center;justify-content:center;}
.kc-print-ok-txt{font-family:var(--font-display);font-size:18px;font-weight:700;color:var(--ink);}
.kc-print-bar{width:100%;height:7px;border-radius:999px;background:var(--surface-2);overflow:hidden;}
.kc-print-bar span{display:block;height:100%;background:var(--accent);border-radius:999px;transition:width .6s ease;}
.kc-print-sub{font-size:12px;color:var(--muted);font-family:var(--font-mono);}

/* ── v3.0: Auto-orient chip ── */
.kc-orient-chip{position:absolute;top:60px;left:14px;display:flex;align-items:center;gap:7px;font-size:11.5px;font-weight:600;color:#fff;white-space:nowrap;
  background:rgba(0,0,0,.36);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,.16);border-radius:9px;padding:6px 11px;}
.kc-orient-chip svg{color:rgba(255,255,255,.7);}
.kc-orient-x{font:inherit;font-size:11px;font-weight:600;color:#fff;background:rgba(255,255,255,.14);border:0;border-radius:6px;padding:2px 8px;margin-left:2px;cursor:pointer;transition:.12s;}
.kc-orient-x:hover{background:rgba(255,255,255,.26);}

/* ── v3.0: Setup gear ── */
.kc-gear{width:38px;height:38px;display:flex;align-items:center;justify-content:center;border-radius:10px;border:1px solid var(--hair);background:var(--surface-2);color:var(--muted);cursor:pointer;transition:.15s;}
.kc-gear:hover{color:var(--accent);border-color:var(--hair-strong);}

/* ── v3.0: First-run wizard ── */
.kc-wiz{position:fixed;inset:0;z-index:9800;display:grid;grid-template-columns:300px 1fr;background:var(--bg);}
.kc-wiz-rail{background:var(--surface-2);border-right:1px solid var(--hair);padding:26px 24px;display:flex;flex-direction:column;}
.kc-wiz-brand{margin-bottom:34px;}
.kc-wiz-steps{display:flex;flex-direction:column;gap:4px;}
.kc-wiz-step{display:flex;align-items:center;gap:12px;font-size:14px;font-weight:500;color:var(--muted);padding:11px 12px;border-radius:11px;transition:.18s;}
.kc-wiz-step.on{color:var(--ink);background:var(--surface);font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.05);}
.kc-wiz-step.done{color:var(--ink);}
.kc-wiz-num{width:23px;height:23px;flex:0 0 auto;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:var(--font-mono);font-size:12px;font-weight:700;
  background:var(--surface);border:1px solid var(--hair-strong);color:var(--muted);}
.kc-wiz-step.on .kc-wiz-num{background:var(--accent);border-color:var(--accent);color:#fff;}
.kc-wiz-step.done .kc-wiz-num{background:color-mix(in srgb,#2f9e6a 16%,transparent);border-color:transparent;color:#1d7a4e;}
.kc-wiz-budget{margin-top:auto;display:flex;gap:9px;align-items:flex-start;font-size:12px;line-height:1.45;color:var(--muted);
  background:var(--surface);border:1px solid var(--hair);border-radius:11px;padding:12px;}
.kc-wiz-budget svg{flex:0 0 auto;margin-top:1px;color:var(--accent);}
.kc-wiz-skip-all{margin-top:12px;font:inherit;font-size:12.5px;font-weight:600;color:var(--muted);background:transparent;border:0;cursor:pointer;align-self:flex-start;padding:4px;white-space:nowrap;}
.kc-wiz-skip-all:hover{color:var(--ink);}

.kc-wiz-body{display:flex;flex-direction:column;overflow-y:auto;}
.kc-wiz-content{flex:1;max-width:620px;width:100%;margin:0 auto;padding:52px 44px 24px;}
.kc-wiz-h1{font-family:var(--font-display);font-size:32px;font-weight:700;letter-spacing:-.02em;color:var(--ink);margin:0 0 10px;}
.kc-wiz-h1.kc-center{text-align:center;}
.kc-wiz-lede{font-size:15.5px;line-height:1.55;color:var(--muted);margin:0 0 26px;text-wrap:pretty;}
.kc-wiz-lede.kc-center{text-align:center;max-width:440px;margin-left:auto;margin-right:auto;}

.kc-wiz-card{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:20px;display:flex;flex-direction:column;gap:14px;}
.kc-wiz-card-hd{display:flex;align-items:center;gap:9px;font-family:var(--font-display);font-size:16px;font-weight:700;color:var(--ink);}
.kc-wiz-card-hd svg{color:var(--accent);}
.kc-wiz-card-p{font-size:13.5px;line-height:1.55;color:var(--muted);margin:0;}
.kc-wiz-card-p b{color:var(--ink);}
.kc-smartscreen{background:#1b2733;border-radius:12px;padding:16px 17px;color:#dde6f0;display:flex;flex-direction:column;gap:7px;}
.kc-ss-title{font-size:15px;font-weight:700;color:#fff;}
.kc-ss-body{font-size:12px;color:rgba(221,230,240,.7);line-height:1.45;}
.kc-ss-moreinfo{display:flex;align-items:center;gap:8px;font-size:12.5px;margin-top:4px;}
.kc-ss-link{color:#7fb2ff;text-decoration:underline;white-space:nowrap;}
.kc-ss-arrow{color:rgba(221,230,240,.45);}
.kc-ss-run{color:#fff;font-weight:700;background:var(--accent);padding:3px 11px;border-radius:6px;white-space:nowrap;}
.kc-ss-buttons{margin-top:2px;}
.kc-ss-btn{display:inline-block;font-size:12px;padding:5px 14px;border-radius:6px;background:rgba(255,255,255,.12);color:rgba(221,230,240,.7);white-space:nowrap;}
.kc-ss-hint{font-size:11.5px;color:rgba(221,230,240,.55);border-top:1px solid rgba(255,255,255,.1);padding-top:9px;margin-top:5px;}
.kc-ss-hint b{color:#fff;}
.kc-wiz-trust{display:flex;flex-direction:column;gap:6px;}
.kc-wiz-trust>div{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--muted);}
.kc-wiz-trust svg{color:#1d7a4e;flex:0 0 auto;}
.kc-wiz-trust code{font-family:var(--font-mono);font-size:11px;color:var(--ink);background:var(--surface-2);padding:1px 7px;border-radius:5px;}
.kc-wiz-bundle{margin-top:18px;}
.kc-wiz-bundle-lbl{font-size:12.5px;color:var(--muted);}
.kc-bundle-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;}
.kc-bundle-chip{display:flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;color:var(--ink);padding:6px 12px;border-radius:999px;
  background:var(--surface);border:1px solid var(--hair);white-space:nowrap;}
.kc-bundle-chip svg{color:#1d7a4e;}

/* model cards */
.kc-modelcards{display:flex;flex-direction:column;gap:11px;}
.kc-modelcard{text-align:left;background:var(--surface);border:1.5px solid var(--hair);border-radius:14px;padding:16px;cursor:pointer;transition:.15s;display:flex;flex-direction:column;gap:6px;}
.kc-modelcard:hover{border-color:var(--hair-strong);}
.kc-modelcard.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 5%,var(--surface));}
.kc-mc-top{display:flex;align-items:center;gap:9px;}
.kc-mc-name{font-family:var(--font-display);font-size:16px;font-weight:700;color:var(--ink);}
.kc-mc-rec{font-size:10.5px;font-weight:700;color:var(--accent);background:color-mix(in srgb,var(--accent) 12%,transparent);padding:2px 8px;border-radius:6px;text-transform:uppercase;letter-spacing:.04em;}
.kc-mc-radio{margin-left:auto;width:18px;height:18px;border-radius:50%;border:2px solid var(--hair-strong);display:flex;align-items:center;justify-content:center;}
.kc-modelcard.on .kc-mc-radio{border-color:var(--accent);}
.kc-mc-radio i{width:9px;height:9px;border-radius:50%;background:var(--accent);}
.kc-mc-tag{font-family:var(--font-mono);font-size:11.5px;color:var(--accent);font-weight:600;}
.kc-mc-desc{font-size:13px;color:var(--muted);line-height:1.45;}
.kc-cloud-opt{margin-top:16px;}
.kc-cloud-toggle{display:flex;align-items:center;gap:8px;font:inherit;font-size:13.5px;font-weight:600;color:var(--ink);background:var(--surface-2);border:1px dashed var(--hair-strong);border-radius:11px;padding:13px 15px;cursor:pointer;width:100%;transition:.15s;}
.kc-cloud-toggle:hover{border-color:var(--accent);color:var(--accent);}
.kc-cloud-toggle svg{color:var(--accent);}
.kc-cloud-toggle i{font-style:normal;color:var(--muted);font-weight:400;}
.kc-cloud-field{background:var(--surface);border:1px solid var(--hair);border-radius:12px;padding:15px;display:flex;flex-direction:column;gap:8px;}
.kc-field-lbl{display:flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;color:var(--ink);}
.kc-field-lbl svg{color:var(--accent);}
.kc-opt{font-weight:400;color:var(--muted);font-size:11.5px;}
.kc-text-input{font:inherit;font-size:14px;padding:11px 13px;border-radius:10px;border:1px solid var(--hair-strong);background:var(--bg);color:var(--ink);outline:none;transition:.15s;}
.kc-text-input:focus{border-color:var(--accent);}
.kc-field-note{font-size:11.5px;color:var(--muted);line-height:1.45;}

/* printer */
.kc-maker-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:9px;margin-bottom:22px;}
.kc-maker{display:flex;flex-direction:column;align-items:center;gap:8px;padding:15px 8px;border-radius:12px;border:1.5px solid var(--hair);background:var(--surface);color:var(--ink);font:inherit;font-size:12px;font-weight:600;cursor:pointer;transition:.15s;text-align:center;}
.kc-maker svg{color:var(--muted);transition:.15s;}
.kc-maker:hover{border-color:var(--hair-strong);}
.kc-maker.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 6%,var(--surface));}
.kc-maker.on svg{color:var(--accent);}
.kc-model-list{display:flex;flex-direction:column;gap:7px;}
.kc-model-list .kc-field-lbl{margin-bottom:4px;}
.kc-model-row{display:flex;align-items:center;gap:11px;padding:12px 14px;border-radius:11px;border:1.5px solid var(--hair);background:var(--surface);cursor:pointer;transition:.15s;}
.kc-model-row:hover{border-color:var(--hair-strong);}
.kc-model-row.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 5%,var(--surface));}
.kc-mr-radio{width:18px;height:18px;flex:0 0 auto;border-radius:50%;border:2px solid var(--hair-strong);display:flex;align-items:center;justify-content:center;}
.kc-model-row.on .kc-mr-radio{border-color:var(--accent);}
.kc-mr-radio i{width:9px;height:9px;border-radius:50%;background:var(--accent);}
.kc-mr-name{font-size:14px;font-weight:600;color:var(--ink);}
.kc-mr-vol{margin-left:auto;font-family:var(--font-mono);font-size:12px;color:var(--muted);}

/* connect */
.kc-conn-choice{display:flex;flex-direction:column;gap:10px;}
.kc-conn-opt{display:flex;align-items:center;gap:13px;text-align:left;padding:15px;border-radius:13px;border:1.5px solid var(--hair);background:var(--surface);cursor:pointer;transition:.15s;}
.kc-conn-opt:hover{border-color:var(--hair-strong);}
.kc-conn-opt.on{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 5%,var(--surface));}
.kc-conn-opt svg{color:var(--accent);flex:0 0 auto;}
.kc-co-t{font-size:14.5px;font-weight:600;color:var(--ink);}
.kc-co-d{font-size:12.5px;color:var(--muted);margin-top:2px;}
.kc-conn-form{margin-top:16px;display:flex;flex-direction:column;gap:13px;background:var(--surface);border:1px solid var(--hair);border-radius:13px;padding:17px;}
.kc-conn-row{display:flex;flex-direction:column;gap:6px;}
.kc-conn-note{display:flex;gap:8px;align-items:flex-start;font-size:12px;color:#876312;line-height:1.45;background:color-mix(in srgb,#c9962f 11%,var(--surface));border:1px solid color-mix(in srgb,#c9962f 26%,transparent);border-radius:10px;padding:10px 12px;}
.kc-conn-note svg{flex:0 0 auto;margin-top:1px;}
.kc-test-btn{display:flex;align-items:center;justify-content:center;gap:8px;font:inherit;font-size:13.5px;font-weight:600;padding:11px;border-radius:11px;border:1px solid var(--hair-strong);background:var(--surface-2);color:var(--ink);cursor:pointer;transition:.15s;white-space:nowrap;}
.kc-test-btn:hover{border-color:var(--accent);color:var(--accent);}
.kc-test-btn.ok{background:color-mix(in srgb,#2f9e6a 12%,var(--surface));color:#1d7a4e;border-color:color-mix(in srgb,#2f9e6a 34%,transparent);}
.kc-test-btn.ok svg{color:#1d7a4e;}

/* done */
.kc-done-badge{width:64px;height:64px;border-radius:50%;background:color-mix(in srgb,#2f9e6a 15%,transparent);color:#1d7a4e;display:flex;align-items:center;justify-content:center;margin:0 auto 18px;}
.kc-done-recap{background:var(--surface);border:1px solid var(--hair);border-radius:14px;padding:6px 18px;max-width:430px;margin:6px auto 0;}
.kc-recap-row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:13px 0;border-bottom:1px solid var(--hair);font-size:13.5px;}
.kc-recap-row:last-child{border-bottom:0;}
.kc-recap-row span{display:flex;align-items:center;gap:8px;color:var(--muted);}
.kc-recap-row span svg{color:var(--accent);}
.kc-recap-row b{color:var(--ink);text-align:right;}

/* footer */
.kc-wiz-foot{position:sticky;bottom:0;display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding:18px 44px;border-top:1px solid var(--hair);background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(8px);max-width:620px;width:100%;margin:0 auto;}
.kc-wiz-dots{display:flex;gap:7px;}
.kc-wiz-dot{width:7px;height:7px;border-radius:50%;background:var(--hair-strong);transition:.2s;}
.kc-wiz-dot.on{background:var(--accent);width:22px;border-radius:999px;}

@media (max-width:860px){
  .kc-wiz{grid-template-columns:1fr;}
  .kc-wiz-rail{display:none;}
  .kc-maker-grid{grid-template-columns:repeat(3,1fr);}
}

@media (max-width:1320px){.kc-main{grid-template-columns:330px 1fr 360px;}}
@media (max-width:1140px){.kc-main{grid-template-columns:300px 1fr 330px;}}
@media (max-width:1000px){
  .kc-main{display:flex;flex-direction:column;overflow-y:auto;}
  .kc-col-left,.kc-col-right{border:0;}
  .kc-col-left{height:auto;max-height:none;}
  .kc-col-center{height:62vh;}
  .kc-viewport{min-height:340px;}
}
`;
