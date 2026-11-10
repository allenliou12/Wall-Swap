; Inno Setup script for WallSwap-Setup.exe. It wraps the PyInstaller folder dist\WallSwap (build that first).
; Build both with:  powershell -ExecutionPolicy Bypass -File build.ps1
; or just this:     ISCC.exe /DAppVersion=1.0.2 installer\WallSwap.iss
;
; Per-user install, no admin prompt. Two ticked-by-default boxes: a desktop shortcut, and "Start WallSwap when I sign
; in", which writes the very shortcut the app's own Start with Windows switch manages (same file, same target), so
; the switch shows On and can turn it off. Unticking that box never deletes an existing one. The uninstaller removes
; both shortcuts and the Start menu entry; Pictures\WallSwap (settings, favourites, downloads) is never touched.

#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif

[Setup]
; Never change AppId: installing a newer version over an older one upgrades it in place because the ids match
AppId={{5E9E734F-068B-4E01-9571-4206170C824F}
AppName=WallSwap
AppVersion={#AppVersion}
AppVerName=WallSwap {#AppVersion}
AppPublisher=allenliou12
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\WallSwap
DisableProgramGroupPage=yes
DefaultGroupName=WallSwap
UninstallDisplayIcon={app}\WallSwap.exe
UninstallDisplayName=WallSwap
SetupIconFile=..\wallswap.ico
OutputDir=..\dist
OutputBaseFilename=WallSwap-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; The app holds this named mutex while it runs (single instance), so Setup and the uninstaller both ask the user
; to quit WallSwap first instead of failing on files in use
AppMutex=WallSwap_SingleInstance
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Start WallSwap when I sign in"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; An upgrade replaces the bundled runtime wholesale, so files a newer build no longer ships don't linger
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\WallSwap\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WallSwap"; Filename: "{app}\WallSwap.exe"
Name: "{userdesktop}\WallSwap"; Filename: "{app}\WallSwap.exe"; Tasks: desktopicon; Check: KeepShortcut('{userdesktop}\WallSwap.lnk')
; {userstartup}\WallSwap.lnk is startup_shortcut_path(); target, no arguments, working dir and icon match
; startup_shortcut_spec(..., frozen=True) in wallpaper_changer.py. Keep the two in step.
Name: "{userstartup}\WallSwap"; Filename: "{app}\WallSwap.exe"; WorkingDir: "{app}"; IconFilename: "{app}\WallSwap.exe"; IconIndex: 0; Tasks: startupicon; Check: KeepShortcut('{userstartup}\WallSwap.lnk')

[Run]
Filename: "{app}\WallSwap.exe"; Description: "{cm:LaunchProgram,WallSwap}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Also when the app's switch made it rather than the installer (the [Icons] shortcuts the installer made are removed
; anyway). Nothing under Pictures\WallSwap
Type: files; Name: "{userstartup}\WallSwap.lnk"

[Code]
var
  Upgrading: Boolean;

function InitializeSetup(): Boolean;
begin
  // A previous WallSwap install has this uninstall key (AppId + "_is1")
  Upgrading := RegKeyExists(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{5E9E734F-068B-4E01-9571-4206170C824F}_is1');
  Result := True;
end;

// On a first install the ticked boxes decide. On an upgrade only shortcuts that still exist are rewritten, so a
// desktop icon the user deleted, or Start with Windows they turned off, doesn't come back
function KeepShortcut(Path: String): Boolean;
begin
  Result := (not Upgrading) or FileExists(ExpandConstant(Path));
end;
