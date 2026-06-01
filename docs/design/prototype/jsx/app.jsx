// app.jsx — KimCad orchestrator: state machine, chrome, layout, styles, tweaks.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "direction": "workshop",
  "accent": "#c8623a",
  "font": "bricolage",
  "density": "comfortable",
  "previewStyle": "blueprint",
  "tone": "friendly"
}/*EDITMODE-END*/;

let __uid = 0;
const uid = () => 'm' + (++__uid);

function KimCadApp() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const tone = KC_TONE[t.tone] || KC_TONE.friendly;

  const [phase, setPhase] = React.useState('landing'); // landing | workspace
  const [messages, setMessages] = React.useState([]);
  const [params, setParams] = React.useState({ ...KC_DEFAULT_PARAMS });
  const [holes, setHoles] = React.useState([]);
  const [material, setMaterial] = React.useState('PLA');
  const [showCode, setShowCode] = React.useState(false);
  const [thinking, setThinking] = React.useState(false);
  const [thinkingStep, setThinkingStep] = React.useState(0);
  const [builtOnce, setBuiltOnce] = React.useState(false);
  const [versions, setVersions] = React.useState([]);
  const [activeVersion, setActiveVersion] = React.useState(0);
  const [pointChip, setPointChip] = React.useState(null);
  const [pickMode, setPickMode] = React.useState(false);
  const [sliced, setSliced] = React.useState(false);
  const [slicing, setSlicing] = React.useState(false);
  const [toast, setToast] = React.useState(null);
  // v3.0
  const [model, setModel] = React.useState('qwen');
  const [photoOpen, setPhotoOpen] = React.useState(false);
  const [printOpen, setPrintOpen] = React.useState(false);
  const [printed, setPrinted] = React.useState(false);
  const [fromPhoto, setFromPhoto] = React.useState(false);
  const [printer, setPrinter] = React.useState(KC_PRINTER);
  const [firstRun, setFirstRun] = React.useState(() => {
    try { return !localStorage.getItem('kc_setup_v3'); } catch (e) { return true; }
  });

  const completeSetup = ({ model, printer, connected }) => {
    setModel(model);
    if (printer) setPrinter(printer);
    if (connected) setPrinted(false);
    setFirstRun(false);
    try { localStorage.setItem('kc_setup_v3', '1'); } catch (e) {}
  };

  // apply theme tokens to :root
  React.useEffect(() => {
    const root = document.documentElement;
    const dir = KC_DIRECTIONS[t.direction] || KC_DIRECTIONS.workshop;
    Object.entries(dir.vars).forEach(([k, v]) => root.style.setProperty(k, v));
    root.style.setProperty('--accent', t.accent);
    const f = KC_FONTS[t.font] || KC_FONTS.bricolage;
    root.style.setProperty('--font-display', f.display);
    root.style.setProperty('--font-body', f.body);
    root.style.setProperty('--font-mono', KC_MONO);
    const d = KC_DENSITY[t.density] || KC_DENSITY.comfortable;
    root.style.setProperty('--pad', d.pad);
    root.style.setProperty('--gap', d.gap);
    root.style.setProperty('--fs', d.font);
  }, [t.direction, t.accent, t.font, t.density]);

  const gate = React.useMemo(() => kcPrintability(params, holes, printer), [params, holes, printer]);
  const scadText = React.useMemo(() => kcOpenSCAD(params, holes), [params, holes]);
  const smartMesh = React.useMemo(() => kcSmartMesh(params, gate, material), [params, gate, material]);

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const addMsg = (m) => setMessages((prev) => [...prev, { id: uid(), ...m }]);

  const pushVersion = (note, p = params, h = holes) => {
    setVersions((prev) => {
      const next = [...prev, { id: uid(), note, params: { ...p }, holes: [...h] }];
      setActiveVersion(next.length - 1);
      return next;
    });
  };

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 2600); };

  // ── photo on-ramp → confirmed DesignPlan → generate (skips clarify) ──────
  const handlePhotoBuild = async (seed) => {
    setPhotoOpen(false);
    setFromPhoto(true);
    setPhase('workspace');
    addMsg({ role: 'user', text: '📷 Photo of a wall-mounted spool holder' });
    addMsg({ role: 'ai', text: tone === KC_TONE.expert
      ? 'Vision pass complete. DesignPlan seeded from the photo and confirmed; mounting holes set from your selection.'
      : 'Got your photo — I pulled the dimensions off it and you confirmed them. Rebuilding it solid now.' });
    const next = { ...params, ...seed };
    setParams(next);
    await runGenerate(next, []);
  };

  // ── first prompt → clarify ──────────────────────────────────────────────
  const handleFirstSubmit = async (text) => {
    setPhase('workspace');
    addMsg({ role: 'user', text });
    setThinking(true); setThinkingStep(0);
    await wait(900);
    setThinking(false);
    addMsg({ role: 'ai', text: tone.clarifyIntro, kind: 'clarify' });
    await wait(350);
    addMsg({ role: 'ai', text: tone.clarify, options: ['M3', 'M4', 'M5'] });
  };

  // ── clarify answered → generate ─────────────────────────────────────────
  const handleClarify = async (opt) => {
    addMsg({ role: 'user', text: opt });
    const dia = opt === 'M3' ? 3.4 : opt === 'M4' ? 4.5 : 5.5;
    const next = { ...params, hole_diameter: dia };
    setParams(next);
    await runGenerate(next, []);
  };

  const runGenerate = async (p, h) => {
    setThinking(true);
    for (let s = 0; s <= 4; s++) { setThinkingStep(s); await wait(s === 4 ? 250 : 720); }
    setThinking(false);
    setBuiltOnce(true);
    setSliced(false);
    addMsg({ role: 'ai', text: tone.built, kind: 'built' });
    pushVersion('Initial design', p, h);
  };

  // ── conversational refinement ───────────────────────────────────────────
  const handleSend = async (text) => {
    if (!builtOnce) { handleFirstSubmit(text); return; }
    addMsg({ role: 'user', text });
    const lc = text.toLowerCase();
    setThinking(true); setThinkingStep(3); // jump to "checking" feel
    await wait(populateDelay(lc));
    setThinking(false);
    setSliced(false);

    let np = { ...params }, nh = [...holes], reply = 'Updated. Take a look.';

    if (pointChip && /(hole|hook|screw|mount|add|here|point)/.test(lc)) {
      nh = [...holes, { x: pointChip.x, z: pointChip.z }];
      setHoles(nh); setPointChip(null); setPickMode(false);
      reply = tone.holeAdded;
    } else if (/wid|wide|broad/.test(lc)) {
      np.plate_width = Math.min(90, params.plate_width + 12); reply = tone.wider;
    } else if (/thick|wall|stronger|sturd|robust/.test(lc)) {
      np.wall_thickness = Math.max(params.wall_thickness, 4.4); reply = tone.thicker;
    } else if (/tall|high|long|height/.test(lc)) {
      np.plate_height = Math.min(210, params.plate_height + 28); reply = 'Made it taller — still inside the build volume.';
    } else if (/hook|hold more|arm|reach|longer arm/.test(lc)) {
      np.arm_length = Math.min(110, params.arm_length + 18); reply = 'Extended the arm so it holds a wider spool.';
    } else if (/fillet|round|smooth/.test(lc)) {
      np.fillet = Math.min(8, params.fillet + 2); reply = 'Rounded the corners a little more.';
    } else if (/thin|smaller|narrow/.test(lc)) {
      np.plate_width = Math.max(50, params.plate_width - 10); reply = 'Trimmed it down a bit.';
    } else {
      reply = tone.built.length ? 'Got it — tweaked the design. If that\'s not quite right, tell me the dimension you want.' : reply;
    }
    setParams(np);
    addMsg({ role: 'ai', text: reply });
    pushVersion(versionNote(lc));
  };

  const populateDelay = (lc) => (pointChip ? 900 : 1050);
  const versionNote = (lc) => {
    if (/wid|wide/.test(lc)) return 'Wider plate';
    if (/thick|wall/.test(lc)) return 'Thicker walls';
    if (/tall|height/.test(lc)) return 'Taller';
    if (/hole|hook|add/.test(lc)) return 'Extra screw hole';
    if (/arm|reach/.test(lc)) return 'Longer arm';
    if (/fillet|round/.test(lc)) return 'Rounder corners';
    return 'Refinement';
  };

  // ── slider edits (instant, no AI) ───────────────────────────────────────
  const onParamChange = (key, val) => {
    setParams((prev) => ({ ...prev, [key]: val }));
    setSliced(false);
  };

  const onPick = React.useCallback((pt) => {
    setPointChip(pt);
    showToast('Point captured — describe what to add there.');
  }, []);

  const restoreVersion = (i) => {
    const v = versions[i]; if (!v) return;
    setParams({ ...v.params }); setHoles([...v.holes]); setActiveVersion(i); setSliced(false);
  };

  const doSlice = async () => {
    setSlicing(true);
    await wait(1500);
    setSlicing(false); setSliced(true);
    showToast('Sliced on ' + KC_PRINTER.name + ' — file ready.');
  };

  const onDownload = (fmt) => {
    if (fmt === 'gcode') { showToast('G-code locked to ' + KC_PRINTER.name + ' · confirm printer to export.'); return; }
    if (fmt === 'step') { showToast('Exporting spool-holder.step (CadQuery) …'); return; }
    showToast('Downloading spool-holder.3mf …');
  };

  const newProject = () => {
    setPhase('landing'); setMessages([]); setParams({ ...KC_DEFAULT_PARAMS });
    setHoles([]); setBuiltOnce(false); setVersions([]); setActiveVersion(0);
    setPointChip(null); setPickMode(false); setSliced(false); setShowCode(false);
    setFromPhoto(false); setPrinted(false); setPrintOpen(false);
  };

  return (
    <div className="kc-shell">
      <style>{KC_CSS}</style>
      {firstRun && <FirstRunWizard onComplete={completeSetup} onClose={() => { setFirstRun(false); try { localStorage.setItem('kc_setup_v3', '1'); } catch (e) {} }} />}
      <Topbar onNew={newProject} model={model} onModel={setModel} printer={printer} onSetup={() => setFirstRun(true)} />
      {phase === 'landing'
        ? <Landing tone={tone} onSubmit={handleFirstSubmit} onPhoto={() => setPhotoOpen(true)} />
        : (
          <div className="kc-main">
            <div className="kc-col-left">
              <ChatPanel
                messages={messages} onSend={handleSend} onClarify={handleClarify}
                thinking={thinking} thinkingStep={thinkingStep} tone={tone}
                pointChip={pointChip} onClearPoint={() => setPointChip(null)}
                showRefine={builtOnce}
              />
            </div>

            <div className="kc-col-center">
              <div className="kc-viewport" style={{ background: 'var(--viewport-bg)' }}>
                {builtOnce
                  ? <Preview params={params} holes={holes} style={t.previewStyle} accent={t.accent}
                             pickMode={pickMode} onPick={onPick} />
                  : <VPPlaceholder building={thinking} step={thinkingStep} />}

                {builtOnce && (
                  <>
                    <div className="kc-vp-toolbar">
                      <button className={`kc-vp-btn ${pickMode ? 'on' : ''}`} onClick={() => setPickMode((v) => !v)}>
                        <KCIcon name="pin" size={14} /> {pickMode ? 'Click the model…' : 'Add point'}
                      </button>
                      <div className="kc-vp-info"><KCIcon name="ruler" size={13} /> drag to rotate · scroll to zoom</div>
                    </div>
                    <div className="kc-orient-chip"><KCIcon name="arrows" size={13} /><span>Auto-oriented · plate-down</span><button className="kc-orient-x" onClick={() => showToast('Orientation override — drag to set a custom resting face.')}>change</button></div>
                    {pickMode && <div className="kc-pick-banner"><KCIcon name="pin" size={13} /> Click a spot on the model to place a feature there</div>}
                    <VersionRail versions={versions} active={activeVersion} onSelect={restoreVersion} />
                  </>
                )}
              </div>
            </div>

            <div className="kc-col-right kc-scroll">
              {builtOnce ? (
                <>
                  <ParamPanel params={params} onChange={onParamChange}
                              showCode={showCode} onToggleCode={() => setShowCode((v) => !v)} scadText={scadText} />
                  <PrintabilityCard gate={gate} material={material} onMaterial={setMaterial}
                                    onSlice={doSlice} sliced={sliced} slicing={slicing} printer={printer} />
                  {sliced && <SmartMeshCard sm={smartMesh} />}
                  {sliced && <ReportCard params={params} material={material} gate={gate}
                                         onDownload={onDownload} onPrint={() => setPrintOpen(true)} printed={printed} printer={printer} />}
                </>
              ) : (
                <div className="kc-right-empty">
                  <KCIcon name="sliders" size={22} />
                  <p>Parameters, the printability check and your print report will appear here once your first model is generated.</p>
                </div>
              )}
            </div>
          </div>
        )}

      {toast && <div className="kc-toast">{toast}</div>}
      {photoOpen && <PhotoOnramp onClose={() => setPhotoOpen(false)} onBuild={handlePhotoBuild} />}
      {printOpen && <PrintDialog params={params} material={material} printer={printer}
                                 onClose={() => setPrintOpen(false)} onStarted={() => setPrinted(true)} />}

      <TweaksPanel title="Tweaks">
        <TweakSection label="Design direction" />
        <TweakRadio label="Direction" value={t.direction}
          options={[{ value: 'workshop', label: 'Workshop' }, { value: 'studio', label: 'Studio' }, { value: 'daylight', label: 'Daylight' }]}
          onChange={(v) => setTweak({ direction: v, accent: KC_DIRECTIONS[v].accent })} />
        <TweakColor label="Accent" value={t.accent} options={KC_ACCENT_OPTIONS}
          onChange={(v) => setTweak('accent', v)} />
        <TweakSection label="Type & layout" />
        <TweakRadio label="Type" value={t.font}
          options={[{ value: 'bricolage', label: 'Bricolage' }, { value: 'grotesk', label: 'Grotesk' }]}
          onChange={(v) => setTweak('font', v)} />
        <TweakRadio label="Density" value={t.density}
          options={[{ value: 'cozy', label: 'Cozy' }, { value: 'comfortable', label: 'Comfy' }, { value: 'compact', label: 'Compact' }]}
          onChange={(v) => setTweak('density', v)} />
        <TweakSection label="Preview & voice" />
        <TweakRadio label="Render" value={t.previewStyle}
          options={[{ value: 'blueprint', label: 'Blueprint' }, { value: 'solid', label: 'Solid' }, { value: 'hologram', label: 'Holo' }]}
          onChange={(v) => setTweak('previewStyle', v)} />
        <TweakRadio label="AI tone" value={t.tone}
          options={[{ value: 'friendly', label: 'Friendly' }, { value: 'concise', label: 'Concise' }, { value: 'expert', label: 'Expert' }]}
          onChange={(v) => setTweak('tone', v)} />
      </TweaksPanel>
    </div>
  );
}

// ── Top chrome ────────────────────────────────────────────────────────────
function Topbar({ onNew, model, onModel, printer, onSetup }) {
  const PR = printer || KC_PRINTER;
  return (
    <div className="kc-topbar">
      <div className="kc-brand">
        <span className="kc-cube"><KCIcon name="cube" size={18} stroke={1.7} /></span>
        <span className="kc-wordmark">Kim<b>Cad</b></span>
      </div>
      <div className="kc-top-right">
        <div className="kc-printer-chip">
          <span className="kc-dot" /> {PR.name}
          <i>{PR.volume.join('×')} mm</i>
        </div>
        <ModelPicker model={model} onChange={onModel} />
        <button className="kc-gear" onClick={onSetup} title="Setup & settings"><KCIcon name="gear" size={17} /></button>
        <button className="kc-newbtn" onClick={onNew}>New design</button>
      </div>
    </div>
  );
}

// ── Landing hero ──────────────────────────────────────────────────────────
function Landing({ tone, onSubmit, onPhoto }) {
  const [text, setText] = React.useState('');
  const submit = () => { const v = text.trim(); if (v) onSubmit(v); };
  return (
    <div className="kc-landing">
      <div className="kc-hero" style={{ animation: 'kc-fadeup .5s ease both' }}>
        <div className="kc-hero-badge"><span className="kc-dot" /> Ready to print in ~15 minutes · no CAD skills</div>
        <h1 className="kc-hero-title">{tone.greeting}</h1>
        <p className="kc-hero-sub">{tone.sub}</p>
        <div className="kc-hero-input-wrap">
          <textarea className="kc-hero-input" rows={2} autoFocus placeholder="e.g. a wall-mounted holder for a spool of filament"
            value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }} />
          <button className="kc-hero-send" onClick={submit} disabled={!text.trim()}>
            Design it <KCIcon name="send" size={17} />
          </button>
        </div>
        <div className="kc-examples">
          <span className="kc-ex-lbl">Try:</span>
          {KC_EXAMPLES.map((ex) => (
            <button key={ex} className="kc-example" onClick={() => onSubmit(ex)}>{ex}</button>
          ))}
        </div>
        <div className="kc-or-photo">
          <span className="kc-or-line" />
          <button className="kc-photo-link" onClick={onPhoto}>
            <KCIcon name="camera" size={15} /> Have a broken or existing part? <b>Start from a photo</b>
          </button>
          <span className="kc-or-line" />
        </div>
      </div>
      <div className="kc-hero-foot">
        <span><b>1.</b> Describe</span><i /><span><b>2.</b> Preview &amp; refine</span><i /><span><b>3.</b> Check &amp; download</span>
      </div>
    </div>
  );
}

// ── Viewport placeholder / building ─────────────────────────────────────────
function VPPlaceholder({ building, step }) {
  const steps = ['Reading request', 'Design plan', 'Generating geometry', 'Checking printability'];
  return (
    <div className="kc-vp-empty">
      <div className={`kc-scan ${building ? 'on' : ''}`}><KCIcon name="cube" size={46} stroke={1.1} /></div>
      <div className="kc-vp-empty-txt">
        {building ? (step <= 4 ? (steps[Math.min(step, 3)] + '…') : 'Working…') : 'Your model will appear here'}
      </div>
    </div>
  );
}

window.KimCadApp = KimCadApp;
