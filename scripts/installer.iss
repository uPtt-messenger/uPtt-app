; Inno Setup Script for uPtt
; This script is used by CI to package the Nuitka standalone build into a Windows installer.

#define MyAppName "uPtt"
#define MyAppExeName "uPtt.exe"
#define MyAppPublisher "uPtt"
#define MyAppURL "https://github.com/uPtt-messenger/uPtt-app"

; VERSION is passed via /D flag from CI: iscc /DVERSION=x.y.z
#ifndef VERSION
  #define VERSION "0.0.0"
#endif

[Setup]
AppId={{E8A3F2B1-7C4D-4E9A-B5D6-1F2A3C4D5E6F}
AppName={#MyAppName}
AppVersion={#VERSION}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputBaseFilename=uPtt-Windows-Setup
OutputDir=..\dist\installer
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
SetupIconFile=..\src\uPtt\ui\assets\logo_icon.ico
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "tchinese"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\uPtt\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
