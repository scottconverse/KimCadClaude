# First hardware contact — the scripted checklist (at Kim's, before the first real print)

The Bambu connector shipped **mock-validated** (Stage 10): the FakePrinter was verified
faithful to bambulabs-api 2.6.6, and the hardware-safety edges (fail-closed busy gate,
post-upload re-check, MQTT disconnect, auth mapping) are pinned by tests — but none of it
has touched metal. Budget **about an hour** for this list before the first real print.
Run everything from the installed beta on Kim's box, with the printer's LAN mode on.

Per printer (P2S first, then A1; the Elegoo Neptune 4 Max has no native connector — its
path is download-and-load):

1. **Configure** in Settings → Printer connections: IP + serial; `setx` the access code;
   restart KimCad. The row should read **Ready**.
2. **Status read (idle):** the send panel's connection line shows the idle state with
   sane temperatures. *Watch the printer's network indicator — sessions should connect
   and DISCONNECT cleanly (the Stage-10 ENG-1002 fix), not accumulate.*
3. **Deliberate wrong access code:** `setx` a wrong code, restart, try a send → expect
   the **auth** message naming the on-printer fix (Settings → WLAN → Access Code) —
   never a generic network error. Restore the right code.
4. **A small real send:** a 20-minute part. Expect: upload visible on the printer, the
   job starts ONLY after the in-app confirm, the live line reads "Printing — your job is
   running," and the percentage tracks the printer's own display.
5. **Busy refusal mid-job:** while it prints, try a second send → expect the typed busy
   refusal, nothing uploaded over the running job (the TOCTOU re-check).
6. **Session churn watch:** leave the live status following the whole job. If the
   printer drops the connection or the app's status stalls, note the time-into-job —
   that's the firmware connection-limit signature the disconnect fix targets.
7. **Power-cycle recovery:** turn the printer off mid-poll → the line should degrade to
   offline politely; back on → a re-send works without restarting KimCad.

Anything that deviates: capture the terminal output (`log_error` now reaches it) and the
printer's screen state. The mock contract gets corrected FIRST, then the connector — the
tests must stay the spec.
