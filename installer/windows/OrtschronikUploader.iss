#define MyAppName "ODV"
#define MyAppVersion "v83"
#define MyAppPublisher "Ortschronisten"
#define MyAppExeName "ODV.exe"

[Setup]
AppId={{5C6067F8-B3B3-4AAE-AEF1-ORTSCHRONIK83}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ODV
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=ODV_Setup_v83
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Symbol erstellen"; GroupDescription: "Zusätzliche Symbole:"

[Files]
Source: "..\..\dist\ODV\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} starten"; Flags: nowait postinstall skipifsilent
