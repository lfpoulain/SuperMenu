#define MyAppName "SuperMenu"
#define MyAppVersion "1.0"
#define MyAppPublisher "SuperMenu"
#define MyAppURL ""
#define MyAppExeName "start_supermenu.bat"
#define MyAppIcon "resources\icons\app_icon.ico"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
AppId={{C8F9E2A0-1F3A-4E5D-B6A9-D5C8E4E0F2A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=.
OutputBaseFilename=SuperMenu_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=no
DisableReadyPage=no
DisableFinishedPage=no
WizardStyle=modern
WizardSizePercent=120
SetupLogging=yes
UninstallDisplayIcon={app}\resources\icons\app_icon.ico
UninstallDisplayName={#MyAppName}
SetupIconFile={#MyAppIcon}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Inclure tous les fichiers sauf le dossier venv
Source: "*.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "*.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "*.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "*.md"; DestDir: "{app}"; Flags: ignoreversion; Excludes: "venv\*"
Source: "src\*"; DestDir: "{app}\src"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "venv\*"
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\resources\icons\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\resources\icons\app_icon.ico"

[Run]
; Créer un script batch temporaire qui redirige la sortie de install.bat vers un fichier log
Filename: "cmd.exe"; Parameters: "/c echo @echo off > ""{tmp}\run_install.bat"" && echo cd /d ""{app}"" >> ""{tmp}\run_install.bat"" && echo echo Installation de l'environnement Python... >> ""{tmp}\run_install.bat"" && echo call install.bat > ""{tmp}\install_log.txt"" 2>&1 >> ""{tmp}\run_install.bat"""; Flags: runhidden

; Exécuter le script batch temporaire et afficher la progression
Filename: "{tmp}\run_install.bat"; StatusMsg: "Installation de l'environnement Python..."; Flags: shellexec waituntilterminated

; Lancer l'application
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Créer un script batch temporaire pour la désinstallation
Filename: "cmd.exe"; Parameters: "/c echo @echo off > ""{tmp}\uninstall_cleanup.bat"" && echo echo Suppression de l'environnement Python... >> ""{tmp}\uninstall_cleanup.bat"" && echo cd ""{app}"" >> ""{tmp}\uninstall_cleanup.bat"" && echo if exist ""venv"" rmdir /S /Q ""venv"" >> ""{tmp}\uninstall_cleanup.bat"""; Flags: runhidden

; Exécuter le script de nettoyage
Filename: "{tmp}\uninstall_cleanup.bat"; StatusMsg: "Suppression de l'environnement Python..."; Flags: shellexec waituntilterminated

[Code]
// Fonction pour supprimer les dossiers vides après la désinstallation
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Supprimer explicitement le dossier venv s'il existe encore
    DeleteFile(ExpandConstant('{app}\venv\*.*'));
    RemoveDir(ExpandConstant('{app}\venv'));
    
    // Supprimer le dossier de l'application s'il est vide
    RemoveDir(ExpandConstant('{app}'));
  end;
end;
