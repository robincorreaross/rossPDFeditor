; RossPDFEditor.iss - Script do instalador (Inno Setup 6)

[Setup]
AppId={{D1A2B3C4-E5F6-4A7B-8C9D-0E1F2A3B4C5D}
AppName=Ross PDF Editor
AppVersion=1.7.4
AppVerName=Ross PDF Editor v1.7.4
AppPublisher=Ross Sistemas
DefaultDirName={autopf}\RossPDFEditor
DefaultGroupName=Ross PDF Editor
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=RossPDFEditor_Setup_v1.7.4
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
AllowNoIcons=yes
UninstallDisplayName=Ross PDF Editor
UninstallDisplayIcon={app}\_internal\assets\icon.ico
SetupIconFile=assets\icon.ico

[Languages]
Name: "english"; MessagesFile: "installer_meta\Default.isl"
Name: "brazilianportuguese"; MessagesFile: "installer_meta\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon";   Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"
Name: "startmenuicon"; Description: "Criar atalho no Menu Iniciar";     GroupDescription: "Atalhos:"

[Files]
Source: "dist\RossPDFEditor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Ross PDF Editor";       Filename: "{app}\RossPDFEditor.exe"; Tasks: desktopicon
Name: "{group}\Ross PDF Editor";             Filename: "{app}\RossPDFEditor.exe"; Tasks: startmenuicon
Name: "{group}\Desinstalar Ross PDF Editor"; Filename: "{uninstallexe}";         IconFilename: "{app}\_internal\assets\icon.ico"; Tasks: startmenuicon

[Run]
Filename: "{app}\RossPDFEditor.exe"; Description: "Abrir Ross PDF Editor agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
