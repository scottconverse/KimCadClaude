// wizard.jsx — first-run setup walkthrough (§5.1).
// Steps: safe install (SmartScreen) → model + cloud → printer profile → connect (opt) → done.

function FirstRunWizard({ onComplete, onClose }) {
  const STEPS = ['Welcome', 'Choose a model', 'Pick your printer', 'Connect (optional)', 'Ready'];
  const [step, setStep] = React.useState(0);
  const [model, setModel] = React.useState('qwen');
  const [showCloud, setShowCloud] = React.useState(false);
  const [cloudKey, setCloudKey] = React.useState('');
  const [maker, setMaker] = React.useState('bambu');
  const [printerIdx, setPrinterIdx] = React.useState(0);
  const [doConnect, setDoConnect] = React.useState(false);
  const [tested, setTested] = React.useState(false);

  const profile = KC_PRINTER_PROFILES[maker];
  const printer = profile.models[printerIdx];
  const conn = KC_CONN_INFO[profile.conn];

  const next = () => setStep((s) => Math.min(STEPS.length - 1, s + 1));
  const back = () => setStep((s) => Math.max(0, s - 1));
  const finish = () => onComplete({
    model,
    printer: { ...printer, nozzle: 0.4, conn: profile.conn },
    connected: doConnect && tested,
  });

  return (
    <div className="kc-wiz">
      {/* left rail */}
      <aside className="kc-wiz-rail">
        <div className="kc-brand kc-wiz-brand">
          <span className="kc-cube"><KCIcon name="cube" size={18} stroke={1.7} /></span>
          <span className="kc-wordmark">Kim<b>Cad</b></span>
        </div>
        <div className="kc-wiz-steps">
          {STEPS.map((s, i) => (
            <div key={s} className={`kc-wiz-step ${i === step ? 'on' : ''} ${i < step ? 'done' : ''}`}>
              <span className="kc-wiz-num">{i < step ? <KCIcon name="check" size={13} stroke={2.6} /> : i + 1}</span>
              {s}
            </div>
          ))}
        </div>
        <div className="kc-wiz-budget"><KCIcon name="clock" size={14} /> Most first prints are ready in under 15 minutes — install included.</div>
        {onClose && <button className="kc-wiz-skip-all" onClick={onClose}>Skip setup</button>}
      </aside>

      {/* content */}
      <div className="kc-wiz-body kc-scroll">
        <div className="kc-wiz-content" style={{ animation: 'kc-fadeup .28s ease both' }} key={step}>

          {step === 0 && (
            <>
              <h1 className="kc-wiz-h1">Welcome to KimCad</h1>
              <p className="kc-wiz-lede">Describe a part in plain words — or photograph one — and get a print-ready file in minutes. Everything runs on your machine. Let's get you set up.</p>

              <div className="kc-wiz-card">
                <div className="kc-wiz-card-hd"><KCIcon name="shield" size={17} /> About the SmartScreen warning</div>
                <p className="kc-wiz-card-p">KimCad's beta isn't code-signed yet, so Windows shows a blue <b>“Windows protected your PC”</b> screen the first time. That's expected — here's exactly what to click:</p>
                <div className="kc-smartscreen">
                  <div className="kc-ss-title">Windows protected your PC</div>
                  <div className="kc-ss-body">Microsoft Defender SmartScreen prevented an unrecognized app from starting.</div>
                  <div className="kc-ss-moreinfo"><span className="kc-ss-link">More info</span> <span className="kc-ss-arrow">→</span> <span className="kc-ss-run">Run anyway</span></div>
                  <div className="kc-ss-buttons"><span className="kc-ss-btn">Don't run</span></div>
                  <div className="kc-ss-hint">1. Click <b>More info</b> &nbsp;·&nbsp; 2. Click <b>Run anyway</b></div>
                </div>
                <div className="kc-wiz-trust">
                  <div><KCIcon name="check" size={13} stroke={2.4} /> Published from the official GitHub release</div>
                  <div><KCIcon name="check" size={13} stroke={2.4} /> SHA-256 verified <code>{KC_CHECKSUM}</code></div>
                </div>
              </div>

              <div className="kc-wiz-bundle">
                <span className="kc-wiz-bundle-lbl">Bundled in one installer — nothing else to download:</span>
                <div className="kc-bundle-chips">
                  {KC_BUNDLE.map((b) => (<span key={b} className="kc-bundle-chip"><KCIcon name="check" size={12} stroke={2.6} /> {b}</span>))}
                </div>
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <h1 className="kc-wiz-h1">Choose your model</h1>
              <p className="kc-wiz-lede">KimCad runs a small local model to turn your words into a validated design plan. Both options work fully offline — you can switch any time.</p>

              <div className="kc-modelcards">
                {['qwen', 'gemma'].map((id) => {
                  const m = KC_MODELS[id];
                  return (
                    <button key={id} className={`kc-modelcard ${model === id ? 'on' : ''}`} onClick={() => setModel(id)}>
                      <div className="kc-mc-top">
                        <span className="kc-dot" style={{ background: m.dot }} />
                        <span className="kc-mc-name">{m.name}</span>
                        {id === 'qwen' && <span className="kc-mc-rec">Recommended</span>}
                        <span className="kc-mc-radio">{model === id && <i />}</span>
                      </div>
                      <div className="kc-mc-tag">{m.tag} · {m.size}</div>
                      <div className="kc-mc-desc">{m.desc}</div>
                    </button>
                  );
                })}
              </div>

              <div className="kc-cloud-opt">
                {!showCloud ? (
                  <button className="kc-cloud-toggle" onClick={() => setShowCloud(true)}>
                    <KCIcon name="key" size={14} /> Add an OpenRouter key for cloud speed-ups <i>(optional)</i>
                  </button>
                ) : (
                  <div className="kc-cloud-field">
                    <label className="kc-field-lbl"><KCIcon name="key" size={13} /> OpenRouter API key <span className="kc-opt">optional · local always works</span></label>
                    <input className="kc-text-input" type="password" placeholder="sk-or-…" value={cloudKey} onChange={(e) => setCloudKey(e.target.value)} />
                    <div className="kc-field-note">Used only when you opt into a cloud model or photo analysis. Never required to run KimCad.</div>
                  </div>
                )}
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h1 className="kc-wiz-h1">Pick your printer</h1>
              <p className="kc-wiz-lede">This sets your build volume and slicing profile so KimCad's checks match your hardware. Tested profiles ship for the top-5 makers.</p>

              <div className="kc-maker-grid">
                {Object.entries(KC_PRINTER_PROFILES).map(([id, p]) => (
                  <button key={id} className={`kc-maker ${maker === id ? 'on' : ''}`} onClick={() => { setMaker(id); setPrinterIdx(0); setTested(false); }}>
                    <KCIcon name="printer" size={18} />
                    {p.maker}
                  </button>
                ))}
              </div>

              <div className="kc-model-list">
                <div className="kc-field-lbl">{profile.maker} model</div>
                {profile.models.map((m, i) => (
                  <button key={m.name} className={`kc-model-row ${printerIdx === i ? 'on' : ''}`} onClick={() => { setPrinterIdx(i); setTested(false); }}>
                    <span className="kc-mr-radio">{printerIdx === i && <i />}</span>
                    <span className="kc-mr-name">{m.name}</span>
                    <span className="kc-mr-vol">{m.volume.join('×')} mm</span>
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h1 className="kc-wiz-h1">Connect for direct printing</h1>
              <p className="kc-wiz-lede">Optional. Connect <b>{printer.name}</b> to start prints straight from KimCad — or skip and just download files. KimCad never auto-starts a print.</p>

              <div className="kc-conn-choice">
                <button className={`kc-conn-opt ${!doConnect ? 'on' : ''}`} onClick={() => setDoConnect(false)}>
                  <KCIcon name="download" size={18} />
                  <div><div className="kc-co-t">Just download files</div><div className="kc-co-d">Export 3MF / STEP and print however you like.</div></div>
                </button>
                <button className={`kc-conn-opt ${doConnect ? 'on' : ''}`} onClick={() => setDoConnect(true)}>
                  <KCIcon name="plug" size={18} />
                  <div><div className="kc-co-t">Connect this printer</div><div className="kc-co-d">{conn.label} — send & monitor jobs.</div></div>
                </button>
              </div>

              {doConnect && (
                <div className="kc-conn-form" style={{ animation: 'kc-fadeup .2s ease both' }}>
                  {conn.fields.map((f) => (
                    <div key={f.key} className="kc-conn-row">
                      <label className="kc-field-lbl">{f.label}</label>
                      <input className="kc-text-input" placeholder={f.ph} onChange={() => setTested(false)} />
                    </div>
                  ))}
                  <div className="kc-conn-note"><KCIcon name="warn" size={13} stroke={2} /> {conn.note}</div>
                  <button className={`kc-test-btn ${tested ? 'ok' : ''}`} onClick={() => setTested(true)}>
                    {tested ? <><KCIcon name="check" size={14} stroke={2.6} /> Connected — {printer.name} is idle</> : <><KCIcon name="link" size={14} /> Test connection</>}
                  </button>
                </div>
              )}
            </>
          )}

          {step === 4 && (
            <>
              <div className="kc-done-badge"><KCIcon name="check" size={30} stroke={2.4} /></div>
              <h1 className="kc-wiz-h1 kc-center">You're all set</h1>
              <p className="kc-wiz-lede kc-center">KimCad is ready to design. Here's your setup — change any of it later from the gear menu.</p>
              <div className="kc-done-recap">
                <div className="kc-recap-row"><span><KCIcon name="spark" size={14} /> Model</span><b>{KC_MODELS[model].name}{cloudKey ? ' + OpenRouter' : ''}</b></div>
                <div className="kc-recap-row"><span><KCIcon name="printer" size={14} /> Printer</span><b>{printer.name}</b></div>
                <div className="kc-recap-row"><span><KCIcon name="plug" size={14} /> Direct print</span><b>{doConnect && tested ? 'Connected · ' + conn.label : 'File download only'}</b></div>
              </div>
            </>
          )}
        </div>

        {/* footer nav */}
        <div className="kc-wiz-foot">
          <button className="kc-btn-ghost" onClick={back} disabled={step === 0} style={{ opacity: step === 0 ? 0 : 1 }}>Back</button>
          <div className="kc-wiz-dots">
            {STEPS.map((_, i) => <span key={i} className={`kc-wiz-dot ${i === step ? 'on' : ''}`} />)}
          </div>
          {step < STEPS.length - 1
            ? <button className="kc-btn-primary" onClick={next}>Continue <KCIcon name="send" size={15} /></button>
            : <button className="kc-btn-primary" onClick={finish}>Start designing <KCIcon name="send" size={15} /></button>}
        </div>
      </div>
    </div>
  );
}

window.FirstRunWizard = FirstRunWizard;
