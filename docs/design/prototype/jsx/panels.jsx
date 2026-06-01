// panels.jsx — chat, parameter sliders, printability gate, print report, version rail.

function KCIcon({ name, size = 16, stroke = 1.6 }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round' };
  const paths = {
    send: <path d="M5 12h14M13 6l6 6-6 6" />,
    cube: <g><path d="M12 2.5 21 7v10l-9 4.5L3 17V7z" /><path d="M3 7l9 4.5L21 7M12 11.5V21.5" /></g>,
    sliders: <g><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="2.4" fill="var(--surface)" /><circle cx="15" cy="17" r="2.4" fill="var(--surface)" /></g>,
    download: <path d="M12 3v12m0 0 4-4m-4 4-4-4M4 19h16" />,
    check: <path d="M5 12.5 10 17.5 19.5 7" />,
    warn: <g><path d="M12 4 22 20H2z" /><path d="M12 10v5M12 18h.01" /></g>,
    x: <path d="M6 6l12 12M18 6 6 18" />,
    pin: <g><path d="M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11z" /><circle cx="12" cy="10" r="2.4" /></g>,
    undo: <path d="M9 7 4 12l5 5M4 12h11a5 5 0 0 1 0 10h-3" />,
    code: <path d="M9 8l-5 4 5 4M15 8l5 4-5 4" />,
    spark: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.5 6.5l2.5 2.5M15 15l2.5 2.5M17.5 6.5 15 9M9 15l-2.5 2.5" />,
    layers: <path d="M12 3 3 8l9 5 9-5zM3 13l9 5 9-5M3 18l9 5 9-5" />,
    ruler: <g><path d="M3 8h18v8H3z" /><path d="M7 8v3M11 8v4M15 8v3M19 8v4" /></g>,
    arrows: <path d="M8 7 4 11l4 4M16 7l4 4-4 4M4 11h16" />,
    chevron: <path d="M6 9l6 6 6-6" />,
    camera: <g><path d="M3 8a2 2 0 0 1 2-2h2l1.5-2h7L19 6h0a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><circle cx="12" cy="12.5" r="3.4" /></g>,
    upload: <path d="M12 16V4m0 0 4 4m-4-4-4 4M4 18h16" />,
    printer: <g><path d="M7 8V3h10v5" /><path d="M5 8h14a2 2 0 0 1 2 2v6h-4M3 16V10a2 2 0 0 1 2-2" /><path d="M7 14h10v7H7z" /></g>,
    history: <g><path d="M3 12a9 9 0 1 0 3-6.7M3 4v4h4" /><path d="M12 8v4l3 2" /></g>,
    thermo: <g><path d="M12 14.5V5a2 2 0 0 0-4 0v9.5a4 4 0 1 0 4 0z" /></g>,
    step: <g><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" /></g>,
    bolt: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
    target: <g><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></g>,
    shield: <path d="M12 3 5 6v5c0 4 3 7 7 9 4-2 7-5 7-9V6z" />,
    key: <g><circle cx="8" cy="14" r="4" /><path d="M11 11 20 2M17 5l2 2M14 8l2 2" /></g>,
    link: <g><path d="M9 15l6-6" /><path d="M11 6l1-1a4 4 0 0 1 6 6l-1 1M13 18l-1 1a4 4 0 0 1-6-6l1-1" /></g>,
    clock: <g><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></g>,
    gear: <g><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" /></g>,
    plug: <g><path d="M9 2v6M15 2v6M7 8h10v3a5 5 0 0 1-10 0zM12 16v6" /></g>,
  };
  return <svg {...common}>{paths[name] || null}</svg>;
}

// ── Conversation ─────────────────────────────────────────────────────────────
function ChatPanel({ messages, onSend, onClarify, thinking, thinkingStep, tone,
                     pointChip, onClearPoint, showRefine }) {
  const [text, setText] = React.useState('');
  const listRef = React.useRef(null);
  React.useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight + 999;
  }, [messages.length, thinking, thinkingStep]);

  const submit = () => { const t = text.trim(); if (!t) return; onSend(t); setText(''); };

  const steps = ['Reading your request', 'Writing the design plan', 'Generating the model', 'Checking printability'];

  return (
    <div className="kc-chat">
      <div className="kc-panel-hd">
        <span className="kc-eyebrow">Conversation</span>
      </div>
      <div ref={listRef} className="kc-chat-list kc-scroll">
        {messages.map((m) => (
          <div key={m.id} className={`kc-msg kc-msg-${m.role}`} style={{ animation: 'kc-fadeup .3s ease both' }}>
            {m.role === 'ai' && <div className="kc-ava"><KCIcon name="cube" size={15} /></div>}
            <div className="kc-bubble-wrap">
              <div className={`kc-bubble kc-bubble-${m.role}${m.kind ? ' kc-bubble-' + m.kind : ''}`}>
                {m.text}
              </div>
              {m.options && (
                <div className="kc-quick">
                  {m.options.map((o) => (
                    <button key={o} className="kc-chip kc-chip-accent" onClick={() => onClarify(o)}>{o}</button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {thinking && (
          <div className="kc-msg kc-msg-ai">
            <div className="kc-ava kc-ava-busy"><KCIcon name="cube" size={15} /></div>
            <div className="kc-bubble-wrap">
              <div className="kc-think">
                {steps.map((s, i) => (
                  <div key={s} className={`kc-think-row ${i < thinkingStep ? 'done' : i === thinkingStep ? 'active' : ''}`}>
                    <span className="kc-think-dot">
                      {i < thinkingStep ? <KCIcon name="check" size={12} stroke={2.4} /> : <i className="kc-spin" />}
                    </span>
                    {s}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="kc-composer">
        {showRefine && (
          <div className="kc-refine-row">
            {['Make it wider', 'Thicker walls', 'Make it taller', 'Add a hook'].map((c) => (
              <button key={c} className="kc-chip" onClick={() => onSend(c)}>{c}</button>
            ))}
          </div>
        )}
        {pointChip && (
          <div className="kc-point-chip">
            <KCIcon name="pin" size={13} />
            <span style={{ fontFamily: KC_MONO, fontSize: 11.5 }}>x {pointChip.x} · y {pointChip.y} · z {pointChip.z}</span>
            <button className="kc-x-mini" onClick={onClearPoint}><KCIcon name="x" size={12} /></button>
          </div>
        )}
        <div className="kc-input-row">
          <textarea
            className="kc-input"
            rows={1}
            placeholder={pointChip ? 'Describe what goes here…' : 'Tell KimCad what to change…'}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
          />
          <button className="kc-send" onClick={submit} disabled={!text.trim()}><KCIcon name="send" size={17} /></button>
        </div>
      </div>
    </div>
  );
}

// ── Parameter sliders ────────────────────────────────────────────────────────
function ParamPanel({ params, onChange, showCode, onToggleCode, scadText }) {
  return (
    <div className="kc-card">
      <div className="kc-card-hd">
        <div className="kc-card-title"><KCIcon name="sliders" size={16} /> Parameters</div>
        <button className={`kc-mini-toggle ${showCode ? 'on' : ''}`} onClick={onToggleCode}>
          <KCIcon name="code" size={13} /> {showCode ? 'Hide code' : 'Show code'}
        </button>
      </div>
      <div className="kc-card-sub">Drag a slider — the model re-renders instantly, no AI round-trip.</div>
      <div className="kc-params">
        {KC_PARAM_DEFS.map((d) => {
          const v = params[d.key];
          const pct = ((v - d.min) / (d.max - d.min)) * 100;
          return (
            <div key={d.key} className="kc-prow">
              <div className="kc-plabel">
                <span>{d.label}{d.axis && <i className="kc-axis">{d.axis}</i>}</span>
                <span className="kc-pval">{Number.isInteger(v) ? v : v.toFixed(1)}<i>{d.unit}</i></span>
              </div>
              <input type="range" className="kc-range" min={d.min} max={d.max} step={d.step} value={v}
                     style={{ '--pct': pct + '%' }}
                     onChange={(e) => onChange(d.key, Number(e.target.value))} />
            </div>
          );
        })}
      </div>
      {showCode && (
        <pre className="kc-code kc-scroll">{scadText}</pre>
      )}
    </div>
  );
}

// ── Printability gate ────────────────────────────────────────────────────────
function PrintabilityCard({ gate, material, onMaterial, onSlice, sliced, slicing, printer }) {
  const PR = printer || KC_PRINTER;
  const vIcon = { pass: 'check', warn: 'warn', fail: 'warn' };
  return (
    <div className="kc-card">
      <div className="kc-card-hd">
        <div className="kc-card-title"><KCIcon name="layers" size={16} /> Printability check</div>
        <span className={`kc-verdict kc-verdict-${gate.verdict}`}>
          {gate.verdict === 'pass' ? 'Ready' : gate.verdict === 'warn' ? `${gate.warns} note${gate.warns>1?'s':''}` : 'Blocked'}
        </span>
      </div>
      <div className="kc-mat-row">
        <span className="kc-mat-lbl">Material</span>
        <div className="kc-seg">
          {KC_MATERIALS.map((m) => (
            <button key={m} className={`kc-seg-btn ${material === m ? 'on' : ''}`} onClick={() => onMaterial(m)}>{m}</button>
          ))}
        </div>
      </div>
      <div className="kc-checks">
        {gate.checks.map((c) => (
          <div key={c.id} className={`kc-check kc-check-${c.level}`}>
            <span className="kc-check-ic"><KCIcon name={vIcon[c.level]} size={13} stroke={2.2} /></span>
            <div>
              <div className="kc-check-lbl">{c.label}</div>
              <div className="kc-check-det">{c.detail}</div>
            </div>
          </div>
        ))}
      </div>
      {!sliced && (
        <button className="kc-btn-primary kc-block" disabled={gate.verdict === 'fail' || slicing} onClick={onSlice}>
          {slicing ? <><i className="kc-spin kc-spin-light" /> Slicing on {PR.name.split(' ').slice(-1)}…</>
                   : <>Slice &amp; prepare file <KCIcon name="layers" size={15} /></>}
        </button>
      )}
    </div>
  );
}

// ── Print report ─────────────────────────────────────────────────────────────
function ReportCard({ params, material, gate, onDownload, onPrint, printed, printer }) {
  const PR = printer || KC_PRINTER;
  const est = kcEstimate(params, 20);
  const bbox = kcBBox(params);
  const rows = [
    { k: 'Dimensions', v: `${bbox.x} × ${bbox.y} × ${bbox.z} mm`, hint: `fits ${PR.name}` },
    { k: 'Material', v: `${material} · 0.2 mm layer · 20% infill` },
    { k: 'Estimated print', v: est.timeStr, hint: `${est.grams} g filament` },
    { k: 'Supports', v: gate.checks.find(c=>c.id==='support') ? 'Under arm only' : 'None' },
  ];
  return (
    <div className="kc-card kc-report" style={{ animation: 'kc-fadeup .35s ease both' }}>
      <div className="kc-card-hd">
        <div className="kc-card-title"><KCIcon name="cube" size={16} /> Print report</div>
        <span className={`kc-conf kc-conf-${gate.confidence}`}>{gate.confidence} confidence</span>
      </div>
      <div className="kc-report-rows">
        {rows.map((r) => (
          <div key={r.k} className="kc-rrow">
            <span className="kc-rk">{r.k}</span>
            <span className="kc-rv">{r.v}{r.hint && <i className="kc-rhint">{r.hint}</i>}</span>
          </div>
        ))}
      </div>
      {gate.warns > 0 && (
        <div className="kc-report-warn">
          <KCIcon name="warn" size={13} stroke={2.2} />
          {gate.checks.filter(c=>c.level==='warn')[0].detail}
        </div>
      )}
      <div className="kc-dl-row">
        <button className="kc-btn-primary kc-grow" onClick={() => onDownload('3mf')}>
          <KCIcon name="download" size={16} /> Download .3MF
        </button>
        <button className="kc-btn-ghost" onClick={() => onDownload('step')} title="STEP via CadQuery backend">
          <KCIcon name="step" size={14} /> STEP
        </button>
        <button className="kc-btn-ghost" onClick={() => onDownload('gcode')} title="Requires printer confirmation">
          G-code
        </button>
      </div>
      <div className="kc-dl-note">3MF is printer-agnostic &amp; safe to share · STEP for CAD editing · G-code locks to {PR.name}.</div>
      <button className={`kc-send-printer ${printed ? 'done' : ''}`} onClick={onPrint}>
        <KCIcon name="printer" size={16} /> {printed ? 'Printing on ' + PR.name + ' →' : 'Send to ' + PR.name}
      </button>
    </div>
  );
}

// ── Version rail ─────────────────────────────────────────────────────────────
function VersionRail({ versions, active, onSelect }) {
  if (versions.length < 1) return null;
  return (
    <div className="kc-verrail">
      <span className="kc-ver-lbl"><KCIcon name="undo" size={13} /> History</span>
      <div className="kc-ver-track">
        {versions.map((v, i) => (
          <button key={v.id} className={`kc-ver-node ${active === i ? 'on' : ''}`} onClick={() => onSelect(i)} title={v.note}>
            <span className="kc-ver-tag">v{i + 1}</span>
            <span className="kc-ver-note">{v.note}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { KCIcon, ChatPanel, ParamPanel, PrintabilityCard, ReportCard, VersionRail });
