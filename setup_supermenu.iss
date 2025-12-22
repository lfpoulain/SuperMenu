#define MyAppName "SuperMenu"
#ifndef MyAppVersion
  #define MyAppVersion "1.0"
#endif
#define MyAppPublisher "SuperMenu"
#define MyAppURL ""
#define MyAppExeName "SuperMenu.exe"
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
Name: "startup"; Description: "Démarrer SuperMenu avec Windows"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Inclure l'exécutable packagé et les ressources nécessaires
Source: "dist\SuperMenu.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "*.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "*.md"; DestDir: "{app}"; Flags: ignoreversion; Excludes: "venv\*"
Source: "bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "venv\*"
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\resources\icons\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\resources\icons\app_icon.ico"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup; IconFilename: "{app}\resources\icons\app_icon.ico"

[Run]
; Lancer l'application
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Fermer l'application si elle est en cours d'exécution (sinon l'exécutable peut rester verrouillé)
Filename: "cmd.exe"; Parameters: "/c for /l %%i in (1,1,10) do (taskkill /F /IM SuperMenu.exe /T >nul 2>&1 & timeout /t 1 >nul) & exit /b 0"; Flags: runhidden waituntilterminated

[UninstallDelete]

[Code]
var
  PurgeUserData: Boolean;

function IsSuperMenuRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec('cmd.exe', '/c tasklist /FI "IMAGENAME eq SuperMenu.exe" 2>nul | find /I "SuperMenu.exe" >nul', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
end;

procedure KillSuperMenuBestEffort();
var
  ResultCode: Integer;
  i: Integer;
begin
  for i := 1 to 10 do
  begin
    if not IsSuperMenuRunning() then
      Exit;
    Exec('cmd.exe', '/c taskkill /F /IM SuperMenu.exe /T >nul 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
  end;
end;

function InitializeUninstall(): Boolean;
var
  Res: Integer;
begin
  PurgeUserData := False;

  Res := MsgBox(
    'SuperMenu va être désinstallé.' + #13#10 + #13#10 +
    'Supprimer aussi vos données utilisateur (logs et configuration) ?',
    mbConfirmation,
    MB_YESNO
  );
  PurgeUserData := (Res = IDYES);

  KillSuperMenuBestEffort();
  if IsSuperMenuRunning() then
  begin
    MsgBox('SuperMenu est encore en cours d''exécution.' + #13#10 + #13#10 + 'Ferme-le (ou termine le processus SuperMenu.exe), puis relance la désinstallation.', mbCriticalError, MB_OK);
    Result := False;
    Exit;
  end;

  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  IniPath: string;
  DataDir: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if PurgeUserData then
    begin
      DataDir := ExpandConstant('{localappdata}\\SuperMenu');
      DelTree(DataDir, True, True, True);

      IniPath := ExpandConstant('{%USERPROFILE}\\SuperMenu.ini');
      DeleteFile(IniPath);
    end;
  end;
end;
