; Inno Setup script for WallSwap-Setup.exe. It wraps the PyInstaller folder dist\WallSwap (build that first).
; Build both with:  powershell -ExecutionPolicy Bypass -File build.ps1
; or just this:     ISCC.exe /DAppVersion=0.1.0 installer\WallSwap.iss
;
; Per-user install, no admin prompt. The installer never creates Startup\WallSwap.lnk (the app's own Start with
; Windows switch owns it), but the uninstaller removes it so an uninstalled app doesn't start at sign-in.
; Pictures\WallSwap (settings, favourites, downloads) is never touched.

#ifndef AppVersion
  #define AppVersion "0.1.0"
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
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; An upgrade replaces the bundled runtime wholesale, so files a newer build no longer ships don't linger
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\WallSwap\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\WallSwap"; Filename: "{app}\WallSwap.exe"
Name: "{autodesktop}\WallSwap"; Filename: "{app}\WallSwap.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WallSwap.exe"; Description: "{cm:LaunchProgram,WallSwap}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only the app's own Start with Windows shortcut; nothing under Pictures\WallSwap
Type: files; Name: "{userstartup}\WallSwap.lnk"
