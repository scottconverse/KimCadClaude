// advanced.jsx — v3.0 interface elements:
// model picker, image on-ramp + DesignPlan confirm, Smart Mesh readiness, direct print.

// ── Model picker (§5.2, §7.4) ─────────────────────────────────────────────────
function ModelPicker({ model, onChange }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('pointerdown', h);
    return () => document.removeEventListener('pointerdown', h);
  }, []);
  const m = KC_MODELS[model] || KC_MODELS.qwen;
  return (
    <div className="kc-mp" ref={ref}>
      <button className="kc-mp-btn" onClick={() => setOpen((v) => !v)}>
        <span className="kc-dot" style={{ background: m.dot, boxShadow: `0 0 0 3px color-mix(in srgb,${m.dot} 22%,transparent)` }} />
        <span className="kc-mp-name">{m.name}<i>{m.size}</i></span>
        <KCIcon name="chevron" size={14} />
      </button>
      {open && (
        <div className="kc-mp-menu" style={{ animation: 'kc-fadeup .16s ease both' }}>
          <div className="kc-mp-hd">Model</div>
          {Object.values(KC_MODELS).map((opt) => (
            <button key={opt.id} className={`kc-mp-row ${opt.id === model ? 'on' : ''}`} onClick={() => { onChange(opt.id); setOpen(false); }}>
              <span className="kc-dot" style={{ background: opt.dot, boxShadow: `0 0 0 3px color-mix(in srgb,${opt.dot} 22%,transparent)` }} />
              <span className="kc-mp-info">
                <span className="kc-mp-row-top">{opt.name} <i>{opt.tag}</i></span>
                <span className="kc-mp-desc">{opt.desc}</span>
              </span>
              {opt.id === model && <span className="kc-mp-check"><KCIcon name="check" size={14} stroke={2.4} /></span>}
            </button>
          ))}
          <div className="kc-mp-foot"><KCIcon name="bolt" size={12} /> Local always works — cloud is an accelerant, never required.</div>
        </div>
      )}
    </div>
  );
}

// ── Image on-ramp (§5.3, §6.10) ───────────────────────────────────────────────
function PhotoOnramp({ onClose, onBuild }) {
  const [stage, setStage] = React.useState('upload'); // upload | analyzing | plan
  const [img, setImg] = React.useState(null);
  const [hole, setHole] = React.useState(4);
  const fileRef = React.useRef(null);

  const analyze = (dataUrl) => { setImg(dataUrl); setStage('analyzing');
    setTimeout(() => setStage('plan'), 2100); };
  const onFile = (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    const r = new FileReader(); r.onload = () => analyze(r.result); r.readAsDataURL(f);
  };
  const plan = KC_PHOTO_PLAN;

  return (
    <div className="kc-modal-scrim" onClick={onClose}>
      <div className="kc-modal kc-photo" onClick={(e) => e.stopPropagation()} style={{ animation: 'kc-fadeup .22s ease both' }}>
        <div className="kc-modal-hd">
          <div className="kc-modal-title"><KCIcon name="camera" size={18} /> Start from a photo</div>
          <button className="kc-x-mini" onClick={onClose}><KCIcon name="x" size={16} /></button>
        </div>

        {stage === 'upload' && (
          <>
            <p className="kc-modal-sub">Have a broken or existing part? Upload a photo and KimCad estimates its dimensions to pre-fill a design — then you confirm before anything is built.</p>
            <label className="kc-dropzone">
              <input ref={fileRef} type="file" accept="image/*" onChange={onFile} hidden />
              <KCIcon name="upload" size={26} />
              <span className="kc-dz-main">Drop a photo or <b>browse</b></span>
              <span className="kc-dz-sub">JPG or PNG · a single part on a plain background works best</span>
            </label>
            <button className="kc-sample-btn" onClick={() => analyze(null)}>
              <KCIcon name="spark" size={14} /> Try with a sample part
            </button>
            <div className="kc-disclose"><KCIcon name="warn" size={13} stroke={2} /><span>Default analysis runs on a free OpenRouter vision model — your photo leaves the device. Switch to <b>Gemma 4 E4B</b> to analyze locally &amp; offline.</span></div>
          </>
        )}

        {stage === 'analyzing' && (
          <div className="kc-analyzing">
            <div className="kc-photo-frame">
              {img ? <img src={img} alt="upload" /> : <div className="kc-photo-ph"><KCIcon name="camera" size={34} /><span>sample-part.jpg</span></div>}
              <div className="kc-scanline" />
            </div>
            <div className="kc-analyze-txt"><i className="kc-spin" /> Estimating geometry &amp; dimensions…</div>
          </div>
        )}

        {stage === 'plan' && (
          <div className="kc-plan">
            <div className="kc-plan-top">
              <div className="kc-photo-frame kc-photo-sm">
                {img ? <img src={img} alt="upload" /> : <div className="kc-photo-ph"><KCIcon name="camera" size={22} /></div>}
              </div>
              <div className="kc-plan-head">
                <span className="kc-eyebrow">Detected · DesignPlan draft</span>
                <div className="kc-plan-type">{plan.object_type}</div>
                <div className="kc-plan-conf"><KCIcon name="target" size={13} /> <span>{Math.round(plan.confidence * 100)}% match · confirm before building</span></div>
              </div>
            </div>
            <div className="kc-plan-fields">
              {plan.fields.map((f) => (
                <div key={f.key} className="kc-plan-field">
                  <span className="kc-pf-lbl">{f.label}</span>
                  {f.key === 'hole_diameter' ? (
                    <div className="kc-seg kc-seg-sm">
                      {[3, 4, 5].map((d) => (
                        <button key={d} className={`kc-seg-btn ${hole === d ? 'on' : ''}`} onClick={() => setHole(d)}>M{d}</button>
                      ))}
                    </div>
                  ) : (
                    <span className="kc-pf-val">{f.value}<i>{f.unit}</i><span className={`kc-conf-pill kc-conf-${f.conf}`}>{f.conf}</span></span>
                  )}
                </div>
              ))}
            </div>
            <div className="kc-plan-note"><KCIcon name="warn" size={13} stroke={2} /> {plan.notes}</div>
            <div className="kc-plan-actions">
              <button className="kc-btn-ghost" onClick={() => setStage('upload')}>Use a different photo</button>
              <button className="kc-btn-primary kc-grow" onClick={() => onBuild({ hole_diameter: hole === 3 ? 3.4 : hole === 4 ? 4.5 : 5.5 })}>
                Build this part <KCIcon name="send" size={15} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Smart Mesh readiness (§5.5, §6.12) ────────────────────────────────────────
function ScoreRing({ score, tone }) {
  const R = 26, C = 2 * Math.PI * R;
  const col = tone === 'pass' ? '#2f9e6a' : tone === 'warn' ? '#c9962f' : '#c8623a';
  return (
    <svg width="68" height="68" viewBox="0 0 68 68" className="kc-ring">
      <circle cx="34" cy="34" r={R} fill="none" stroke="var(--hair-strong)" strokeWidth="6" />
      <circle cx="34" cy="34" r={R} fill="none" stroke={col} strokeWidth="6" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={C * (1 - score / 100)} transform="rotate(-90 34 34)"
        style={{ transition: 'stroke-dashoffset .6s ease' }} />
      <text x="34" y="34" textAnchor="middle" dominantBaseline="central" fontFamily="var(--font-mono)" fontSize="19" fontWeight="700" fill="var(--ink)">{score}</text>
    </svg>
  );
}

function SmartMeshCard({ sm }) {
  return (
    <div className="kc-card kc-smartmesh" style={{ animation: 'kc-fadeup .35s ease both' }}>
      <div className="kc-card-hd">
        <div className="kc-card-title"><KCIcon name="spark" size={16} /> Smart Mesh readiness</div>
        <span className={`kc-conf kc-conf-${sm.confidence}`}>{sm.confidence} confidence</span>
      </div>
      <div className="kc-sm-top">
        <ScoreRing score={sm.score} tone={sm.band.tone} />
        <div className="kc-sm-band">
          <div className={`kc-sm-verdict kc-verdict-${sm.band.tone}-txt`}>{sm.band.label}</div>
          <div className="kc-sm-hist"><KCIcon name="history" size={13} />
            <span>Top {100 - sm.history.percentile}% of {sm.history.total} similar {sm.history.family}s · {sm.history.rate}% printed clean</span>
          </div>
        </div>
      </div>

      {sm.risks.length > 0 && (
        <div className="kc-sm-sec">
          <div className="kc-sm-sec-hd">Risks</div>
          {sm.risks.map((r, i) => (
            <div key={i} className={`kc-sm-risk kc-check-${r.level}`}>
              <span className="kc-check-ic"><KCIcon name="warn" size={12} stroke={2.2} /></span>
              <div><div className="kc-check-lbl">{r.label}</div><div className="kc-check-det">{r.fix}</div></div>
            </div>
          ))}
        </div>
      )}

      <div className="kc-sm-sec">
        <div className="kc-sm-sec-hd">Recommendations</div>
        <ul className="kc-sm-recs">
          {sm.recs.map((r, i) => (<li key={i}><KCIcon name="check" size={13} stroke={2.4} /> {r}</li>))}
        </ul>
      </div>
      <div className="kc-sm-foot">Learned from your local print history · PrintProof3D validation engine</div>
    </div>
  );
}

// ── Direct print execution (§5.6, §6.11) ──────────────────────────────────────
function PrintDialog({ params, material, onClose, onStarted, printer }) {
  const PR = printer || KC_PRINTER;
  const [step, setStep] = React.useState('review'); // review | sending | printing
  const st = KC_PRINTER_STATUS;
  const bbox = kcBBox(params);
  const est = kcEstimate(params, 20);

  const start = () => {
    setStep('sending');
    setTimeout(() => { setStep('printing'); onStarted && onStarted(); }, 1900);
  };

  return (
    <div className="kc-modal-scrim" onClick={onClose}>
      <div className="kc-modal kc-printdlg" onClick={(e) => e.stopPropagation()} style={{ animation: 'kc-fadeup .22s ease both' }}>
        <div className="kc-modal-hd">
          <div className="kc-modal-title"><KCIcon name="printer" size={18} /> Send to printer</div>
          <button className="kc-x-mini" onClick={onClose}><KCIcon name="x" size={16} /></button>
        </div>

        {/* live printer status */}
        <div className="kc-pstatus">
          <div className="kc-pstatus-hd">
            <span className="kc-printer-name"><span className="kc-dot" /> {PR.name}</span>
            <span className="kc-pstate">{st.state}</span>
          </div>
          <div className="kc-pstatus-grid">
            <div><KCIcon name="thermo" size={13} /> Nozzle <b>{st.nozzle}°C</b></div>
            <div><KCIcon name="thermo" size={13} /> Bed <b>{st.bed}°C</b></div>
            <div><KCIcon name="cube" size={13} /> Plate <b>free</b></div>
            <div><KCIcon name="layers" size={13} /> {st.ams}</div>
          </div>
          <div className="kc-pconn">{KC_CONN_INFO[PR.conn] ? KC_CONN_INFO[PR.conn].label : st.connection} · KimCad never auto-starts a print</div>
        </div>

        {step === 'review' && (
          <>
            <div className="kc-confirm-rows">
              {[['Geometry', `${bbox.x} × ${bbox.y} × ${bbox.z} mm`],
                ['Printer', PR.name],
                ['Material', `${material} · 0.2 mm · 20% infill`],
                ['Estimated', `${est.timeStr} · ${est.grams} g`]].map(([k, v]) => (
                <div key={k} className="kc-crow"><span>{k}</span><b>{v}</b></div>
              ))}
            </div>
            <button className="kc-btn-primary kc-block" onClick={start}>
              <KCIcon name="printer" size={16} /> Confirm &amp; start print
            </button>
            <div className="kc-dl-note">One final confirmation before any command leaves the app.</div>
          </>
        )}

        {step === 'sending' && (
          <div className="kc-sending"><i className="kc-spin" /> Uploading file &amp; starting job on {PR.name}…</div>
        )}

        {step === 'printing' && (
          <div className="kc-printing">
            <div className="kc-print-ok"><KCIcon name="check" size={22} stroke={2.4} /></div>
            <div className="kc-print-ok-txt">Print started</div>
            <div className="kc-print-bar"><span style={{ width: '4%' }} /></div>
            <div className="kc-print-sub">Layer 1 / ~{Math.round(params.plate_height / 0.2)} · monitoring live</div>
            <button className="kc-btn-ghost kc-block" onClick={onClose}>Done</button>
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { ModelPicker, PhotoOnramp, SmartMeshCard, ScoreRing, PrintDialog });
