; Stage 11 Slice 11.5 — the KimCad Windows installer.
; Compiled by scripts/build_installer.py with the PINNED Inno Setup 6.7.3:
;   ISCC /DAppVersion=<pyproject version> /DStagingDir=<dist/staging> kimcad.iss
; The version is ALWAYS a /D define (Slice 11.3's single-source rule — the tripwire test
; fails the build if a literal ever lands here).

#ifndef AppVersion
  #error AppVersion must be passed by the build script (/DAppVersion=...)
#endif
#ifndef StagingDir
  #error StagingDir must be passed by the build script (/DStagingDir=...)
#endif
#ifndef AppVersionQuad
  #error AppVersionQuad must be passed by the build script (/DAppVersionQuad=...)
#endif

[Setup]
AppId={{7E6F3A52-0A45-4D2B-9C1E-KimCadBeta01}
AppName=KimCad
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersionQuad}
AppPublisher=KimCad (open source, Apache-2.0)
AppPublisherURL=https://github.com/scottconverse/KimCadClaude
DefaultDirName={autopf}\KimCad
DefaultGroupName=KimCad
DisableProgramGroupPage=yes
; Per-user installs work too (no admin): lowest-privileges-that-work.
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=KimCad-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile={#StagingDir}\LICENSE
; The app payload is ~1.5 GB unpacked (Python + tools); the AI models are ANOTHER ~13 GB
; that the in-app wizard downloads — said plainly on the final page below.
ExtraDiskSpaceRequired=200000000
UninstallDisplayName=KimCad {#AppVersion}

[Files]
Source: "{#StagingDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\KimCad"; Filename: "{app}\python\pythonw.exe"; \
  Parameters: """{app}\kimcad_launcher.py"""; WorkingDir: "{app}"; Comment: "KimCad"
Name: "{autodesktop}\KimCad"; Filename: "{app}\python\pythonw.exe"; \
  Parameters: """{app}\kimcad_launcher.py"""; WorkingDir: "{app}"; \
  Comment: "KimCad"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\kimcad_launcher.py"""; \
  WorkingDir: "{app}"; Description: "Launch KimCad now"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; 11.5-audit FINDING-002: the launcher disables bytecode writing, but belt-and-braces —
; the whole payload tree goes (user data is NOT here; it lives in {localappdata}\KimCad
; and ~\.kimcad, both handled separately below/never touched).
Type: filesandordirs; Name: "{app}\site-packages"
Type: filesandordirs; Name: "{app}\python"

; (BG-U011: SmartScreen guidance lives in docs/install-guide.md, BEFORE the user runs
; this installer - by the time this wizard shows, SmartScreen is already behind them.)
[Code]
var
  DataPage: TOutputMsgWizardPage;

procedure InitializeWizard;
begin
  { The honest final word: what still downloads and where the user's work lives.
    (BG-U006: the data-retention claims are exact - saved designs are NEVER removed by
    the uninstaller; only the app's working data is, and only if asked.) }
  DataPage := CreateOutputMsgPage(wpInfoAfter,
    'Before you start', 'Two things worth knowing',
    'AI models: KimCad''s design AI runs locally via Ollama (free). On first run, ' +
    'KimCad checks for Ollama and offers to download its two models (about 13 GB total) ' +
    'with a progress bar - nothing is sent to the cloud.' + #13#10#13#10 +
    'Your work: saved designs and settings live in your user profile (the .kimcad ' +
    'folder) and are NEVER removed by the uninstaller. The app''s working data ' +
    '(design output, the window''s browser profile) is separate, and the uninstaller ' +
    'asks before removing it.');
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
  Local: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Local := ExpandConstant('{localappdata}\KimCad');
    if DirExists(Local) then
    begin
      if MsgBox('Also remove your KimCad data (design output and the app''s browser ' +
                'profile) from ' + Local + '?' + #13#10 +
                'Your saved designs in the .kimcad folder of your user profile are NOT ' +
                'touched either way.', mbConfirmation, MB_YESNO) = IDYES then
        DelTree(Local, True, True, True);
    end;
    ResultCode := 0;
  end;
end;
