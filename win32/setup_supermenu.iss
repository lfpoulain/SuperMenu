#define MyAppName "SuperMenu"
#ifndef MyAppVersion
  #define VersionFile FileOpen("VERSION")
  #define MyAppVersion Trim(FileRead(VersionFile))
  #expr FileClose(VersionFile)
#endif
#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename "SuperMenu_Setup"
#endif
#define MyAppPublisher "LFPoulain"
#define MyAppURL "https://github.com/lfpoulain/SuperMenu"
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
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
LicenseFile=..\LICENSE
OutputDir=.
OutputBaseFilename={#MyOutputBaseFilename}
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
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
SetupIconFile={#MyAppIcon}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Démarrer SuperMenu avec Windows"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Le bundle PyInstaller one-file contient déjà les ressources.
Source: "dist\SuperMenu.exe"; DestDir: "{app}"; Flags: ignoreversion
; Licence de SuperMenu et avis des composants tiers, lisibles sans lancer l'application.
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\*.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
; Écrit par SuperMenu.spec à côté de l'exécutable pendant le build PyInstaller.
Source: "dist\third_party_licenses\*"; DestDir: "{app}\third_party_licenses"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup; IconFilename: "{app}\{#MyAppExeName}"

[Run]
; Lancer l'application
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Fermer l'application si elle est en cours d'exécution (sinon l'exécutable peut rester verrouillé)
Filename: "cmd.exe"; Parameters: "/c for /l %%i in (1,1,10) do (taskkill /F /IM SuperMenu.exe /T >nul 2>&1 & timeout /t 1 >nul) & exit /b 0"; Flags: runhidden waituntilterminated; RunOnceId: "StopSuperMenu"

[InstallDelete]
; Nettoyer les anciens assets qui ont pu être installés hors du bundle one-file.
Type: filesandordirs; Name: "{app}\bin"
; Les licences tierces d'une version précédente ne doivent pas subsister.
Type: filesandordirs; Name: "{app}\third_party_licenses"

[UninstallDelete]

[Code]
const
  CRED_TYPE_GENERIC = 1;

var
  PurgeUserData: Boolean;

// Les clés API sont stockées par keyring dans le Gestionnaire d'identification
// Windows, hors de {localappdata} : la purge doit les effacer explicitement.
function CredDelete(TargetName: String; CredType: Cardinal; Flags: Cardinal): Bool;
external 'CredDeleteW@advapi32.dll stdcall';

procedure DeleteStoredApiKeys();
begin
  // keyring enregistre le dernier secret sous "SuperMenu" et les précédents
  // sous "<nom>@SuperMenu" ; un identifiant absent est simplement ignoré.
  CredDelete('SuperMenu', CRED_TYPE_GENERIC, 0);
  CredDelete('openai_api_key@SuperMenu', CRED_TYPE_GENERIC, 0);
  CredDelete('custom_endpoint_api_key@SuperMenu', CRED_TYPE_GENERIC, 0);
end;

// Les composants Microsoft de Foundry Local ne sont pas couverts par la
// licence de SuperMenu : Microsoft demande que l'utilisateur accepte leurs
// conditions. Elles sont présentées juste après la licence de SuperMenu.
procedure InitializeWizard();
var
  Page: TOutputMsgMemoWizardPage;
begin
  Page := CreateOutputMsgMemoPage(wpLicense,
    'Composants Microsoft',
    'Conditions des composants Microsoft inclus dans SuperMenu',
    'En poursuivant l''installation, vous acceptez ces conditions pour ces composants.',
    '');
  // Le dernier paramètre est une chaîne ANSI : le texte accentué passe par Lines.
  Page.RichEditViewer.Lines.Text :=
    'SuperMenu pour Windows intègre Microsoft Foundry Local Core ' +
    '(Microsoft.AI.Foundry.Local.Core.dll) et Microsoft Windows ML Runtime ' +
    '(Microsoft.Windows.AI.MachineLearning.dll). Ces composants ne sont pas ' +
    'couverts par la licence de SuperMenu : ils vous sont concédés sous les ' +
    'Microsoft Software License Terms, copiées dans le sous-dossier licenses du ' +
    'dossier d''installation (Microsoft-Foundry-Local-Core.txt et ' +
    'Microsoft-Windows-ML-Runtime.txt).' + #13#10 + #13#10 +
    'Vous ne pouvez notamment pas :' + #13#10 +
    '- extraire ces composants de SuperMenu pour les distribuer séparément ;' + #13#10 +
    '- en faire l''ingénierie inverse, les décompiler ou les désassembler, ' +
    'sauf dans la mesure où la loi l''autorise ;' + #13#10 +
    '- retirer ou modifier les mentions de Microsoft et de ses fournisseurs.' + #13#10 + #13#10 +
    'Microsoft fournit ces composants « en l''état », sans garantie. ' +
    'THIRD_PARTY_NOTICES.md, installé avec SuperMenu, détaille les licences ' +
    'de tous les composants tiers.';
end;

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
    'Supprimer aussi vos données utilisateur (logs, configuration et clés API enregistrées) ?',
    mbConfirmation,
    MB_YESNO
  );
  PurgeUserData := (Res = IDYES);

  KillSuperMenuBestEffort();
  if IsSuperMenuRunning() then
  begin
    MsgBox('SuperMenu est encore en cours d''exécution.' + #13#10 + #13#10 + 'Fermez-le (ou terminez le processus SuperMenu.exe), puis relancez la désinstallation.', mbCriticalError, MB_OK);
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

      DeleteStoredApiKeys();
    end;
  end;
end;
