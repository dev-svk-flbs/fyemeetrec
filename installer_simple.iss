; Simple Inno Setup Script for FyeLabs Recording System
; Just packages the PyInstaller output into an installer

[Setup]
AppName=FyeLabs Meeting Recording System
AppVersion=1.0.0
DefaultDirName={autopf}\FyeLabs Recording
DefaultGroupName=FyeLabs Recording
OutputDir=installer_output
OutputBaseFilename=FyeLabs_Recording_Installer
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Just copy the entire PyInstaller output folder
Source: "dist\FyeLabs Recording System\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Dirs]
; Create directories for user data
Name: "{localappdata}\FyeLabs Recording\instance"
Name: "{localappdata}\FyeLabs Recording\logs"
Name: "{localappdata}\FyeLabs Recording\recordings"

[Icons]
; Desktop shortcut
Name: "{autodesktop}\FyeLabs Recording"; Filename: "{app}\FyeLabs Recording System.exe"

; Start menu shortcuts
Name: "{group}\FyeLabs Recording System"; Filename: "{app}\FyeLabs Recording System.exe"
Name: "{group}\Open Dashboard"; Filename: "http://localhost:5000"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"

[Run]
; Option to start after installation
Filename: "{app}\FyeLabs Recording System.exe"; Description: "Start Recording System Now"; Flags: postinstall nowait skipifsilent

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Run at Windows startup"; GroupDescription: "Startup Options:"

[Registry]
; Add to Windows startup if user selects it
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "FyeLabsRecording"; ValueData: """{app}\FyeLabs Recording System.exe"""; Flags: uninsdeletevalue; Tasks: startup
