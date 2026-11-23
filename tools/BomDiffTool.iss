#ifndef PackageDir
  #error PackageDir must point to the extracted BOM Diff Tool package
#endif

[Setup]
AppId=BOMDiffTool
AppName=BOM Diff Tool
AppVersion=3.1.0
AppPublisher=BOM Diff Tool
DefaultDirName={localappdata}\Programs\BOM Diff Tool
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputBaseFilename=BOM-Diff-Tool-Setup-Windows-x64
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\BOM Diff Tool.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Files]
Source: "{#PackageDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{userprograms}\BOM Diff Tool\BOM Diff Tool (日本語)"; Filename: "{app}\BOM Diff Tool.exe"; WorkingDir: "{app}"
Name: "{userprograms}\BOM Diff Tool\BOM Diff Tool (English)"; Filename: "{app}\BOM Diff Tool (English).exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\BOM Diff Tool.exe"; Description: "BOM Diff Tool (日本語)"; WorkingDir: "{app}"; Languages: japanese; Flags: nowait postinstall skipifsilent
Filename: "{app}\BOM Diff Tool (English).exe"; Description: "BOM Diff Tool (English)"; WorkingDir: "{app}"; Languages: english; Flags: nowait postinstall skipifsilent
