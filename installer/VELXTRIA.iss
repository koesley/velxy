#define MyAppName "VELXTRIA Desktop"
#define MyAppVersion "58.2"
#define MyAppExeName "VELXTRIA-Desktop.exe"
[Setup]
AppId={{7EDE9278-8F90-478C-85BA-26E5C457C2E9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\VELXTRIA
DefaultGroupName=VELXTRIA
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=VELXTRIA-Desktop-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
[Files]
Source: "..\dist\VELXTRIA-Desktop\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\VELXTRIA Desktop"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\VELXTRIA Desktop"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch VELXTRIA"; Flags: nowait postinstall skipifsilent
[UninstallDelete]
; User business data in LocalAppData\VELXTRIA\Data is intentionally preserved.
