<p align="center">
  <img src="docs/assets/supermenu-hero.jpg" alt="SuperMenu — AI right where you already work. Windows · macOS" width="100%">
</p>

<p align="center">
  <a href="https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml"><img src="https://github.com/lfpoulain/SuperMenu/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/lfpoulain/SuperMenu/releases/latest"><img src="https://img.shields.io/github/v/release/lfpoulain/SuperMenu?display_name=tag&amp;sort=semver&amp;label=stable" alt="Latest stable release"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4" alt="Windows 10 and 11">
  <img src="https://img.shields.io/badge/macOS-Apple%20Silicon-000000?logo=apple" alt="macOS Apple Silicon">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-6f42c1" alt="License PolyForm Noncommercial 1.0.0"></a>
</p>

<p align="center">
  <a href="README.md">Version française</a> · <strong>English</strong>
</p>

**Select some text, press a shortcut, pick an action: AI fixes, rephrases,
summarizes or translates it without you ever leaving your app.**

SuperMenu is a desktop app for Windows and macOS. It sits in the notification
area or the menu bar and, with a keyboard shortcut, opens a prompt menu on top
of any application: email, browser, word processor, code editor… The answer
appears in a small window, ready to be copied or inserted in place of your
selection.

> [!NOTE]
> The SuperMenu interface is in French. This page gives each French label as
> it appears in the app, with its English meaning the first time it shows up.

[Installation](#installation) · [Features](#features) ·
[AI engines](#ai-engines) · [Shortcuts](#default-shortcuts) ·
[Privacy](#privacy-and-security) · [Development](#development) ·
[Documentation](#documentation) · [License](#license)

## Why SuperMenu

- **No more round trips to a chat window.** The AI comes to your text, where
  you are writing it, then gets out of the way.
- **Your actions, your shortcuts.** A dozen ready-made prompts that you can
  edit, extend with your own and reorder.
- **The engine of your choice.** OpenAI in the cloud, or a local model
  (Ollama, LM Studio, Foundry Local on Windows, Apple Intelligence on macOS)
  when your text must not leave your machine.
- **Simple by default.** A new installation shows only the essentials; the
  advanced and experimental features can be turned on in the settings whenever
  you need them.

## How it works

1. **Select** text in any application.
2. **Press** `Ctrl+²` on Windows or `Cmd+Shift+Space` on macOS: the prompt menu
   opens next to the cursor.
3. **Pick** an action. The answer appears with **Copier** (Copy), **Insérer le
   texte** (Insert text) and **Réessayer** (Retry), or goes straight into the
   original application if the prompt is set up that way.

## Features

> [!NOTE]
> This README describes the `main` branch, which ships first in the Beta.
> Changes that are not in a Stable release yet are listed under « Non publié »
> (Unreleased) in the [changelog](CHANGELOG.md).

Everything is set in the configuration window, opened from the SuperMenu icon:
the **Prompts**, **Voix** (Voice), **Réglages** (Settings) and **À propos**
(About) tabs and, inside **Réglages**, the **Texte** (Text), **Dictée**
(Dictation), **Raccourcis** (Shortcuts) and **Application** sections. The
**Voix** tab and the **Dictée** section only appear with the experimental
features.

### Essentials — always available

- **Prompt menu on a global shortcut**, usable in all your applications.
- **Ready-made prompts**: fix, rephrase, summarize, explain, expand, extract
  the key passages, draft a reply, find the action items, translate into
  English or French…
- **Your own prompts**: create, edit, reorder, import and export them.
  **Tout restaurer…** (Restore all) brings back the original prompts and
  **Revenir à la copie…** (Go back to a copy) restores an earlier version of
  your library; each further use goes back one more copy, among the five kept.
- **Custom mode** (`Ctrl+Alt+M` / `Cmd+Shift+M`) to type a free-form
  instruction, with or without selected text.
- **Answer window**: **Copier**, **Insérer le texte**, **Réessayer** and
  **Voir le raisonnement** (Show reasoning) when the model provides one.
- **Direct insertion**: a prompt can insert its result without opening the
  answer window.
- **Reasoning set per prompt** (engine setting, without or with reasoning),
  when the model supports it.
- **Every text engine** available on the platform, chosen in
  **Réglages > Texte** (see [AI engines](#ai-engines)).
- **Themes**: dark (default), light or automatic.
- **Built-in updates**, Stable or Beta channel.

### Advanced features

For fine control over which model handles what.

- **One model per prompt**: for each prompt, text or voice, choose the engine
  (OpenAI, the configured Ollama or LM Studio server, Foundry Local on Windows
  or Apple Intelligence on macOS), the model and, with LM Studio, the LM Link
  device that runs it. Local copies and LM Link copies of the same model are
  told apart.
- **A direct shortcut per prompt**, to run an action without opening the
  menu.
- **How long local models stay in memory**: after each use, after 1, 5, 15 or
  30 minutes of inactivity, or until SuperMenu quits. On Windows this applies
  to the Foundry Local text model and voice model; on macOS, to the Apple
  Speech voice model.

Without the advanced features, every prompt uses the engine and model from
**Réglages > Texte**, per-prompt shortcuts are released and local models are
unloaded after 5 minutes of inactivity.

### Experimental features

For voice and, on Windows, the screen. These features may still change.

- **Voice prompts** (**Voix** tab): you speak your request, SuperMenu
  transcribes it and sends it with the prompt’s instruction and, if you wish,
  with the selected text. On Windows, `Ctrl+Alt+²` opens the voice menu; on
  macOS, that menu is the **Voix** submenu of the prompt menu.
- **Live dictation** (**Dicter du texte…**, “Dictate text”, in the voice menu,
  and also in the menu bar on macOS): the text appears while you speak, with
  the microphone level, for up to five minutes. It can then be copied or
  inserted, pasted automatically and, optionally, corrected by the text engine
  before insertion.
- **Instant dictation**: a shortcut, set in **Réglages > Raccourcis**, starts
  dictation from the application you are writing in. Press once, or hold the
  key while you speak.
- **Réglages > Dictée section**: transcription engine, microphone, languages
  and vocabulary, and a 5-second **microphone test** that neither records nor
  sends any audio.
- **Screen capture and analysis** (Windows only, `Ctrl+Alt+&`): full screen,
  a selected area, or **Demander à chaque capture** (Ask at each capture),
  which lets you choose each time. The analysis needs a model that can
  read images; Foundry Local does not support them.

### Turning these features on or off

The **Fonctions avancées** (Advanced features) and **Fonctions
expérimentales** (Experimental features) switches are independent. They live
in **Réglages > Application > Fonctions** and take effect with **Appliquer**
(Apply), without a restart.

| Situation | Advanced features | Experimental features |
|---|---|---|
| New installation | off | off |
| Update from an earlier version | on | on |

Turning a feature off hides and disables it **without deleting anything**:
prompts, shortcuts and settings come back exactly as they were when you turn
it on again. If some prompts have their own model, SuperMenu asks for
confirmation before turning the advanced features off, because those prompts
will then go through the **Réglages > Texte** engine, which may be an online
service.

## AI engines

### Text

| Engine | Where the model runs | Windows | macOS | What you need |
|---|---|:---:|:---:|---|
| **OpenAI** | OpenAI cloud | ✅ | ✅ | an OpenAI API key (pay as you go) |
| **Ollama** | your machine or the server you specify | ✅ | ✅ | a reachable Ollama server |
| **LM Studio**, including **LM Link** | your machine, the server you specify or a device connected through LM Link | ✅ | ✅ | a reachable LM Studio server |
| **Foundry Local** — Qwen3.5 4B or 9B | this PC | ✅ | — | Windows 11 24H2 or later; model downloaded from the settings; 16 GB of RAM recommended for 4B, 24 GB for 9B |
| **Apple Intelligence** (Foundation Models) | this Mac | — | ✅ | macOS 26 or later, a compatible Mac with Apple Intelligence turned on |

Foundry Local needs no API key, account or server: the engine is built into
the Windows app. See [Foundry Local](win32/docs/foundry-local.md) (in French)
for details and limits.

### Voice — experimental features

| Transcription engine | Where the model runs | Windows | macOS | What you need |
|---|---|:---:|:---:|---|
| **OpenAI** · GPT Live Transcribe | OpenAI cloud | ✅ | ✅ | an OpenAI API key |
| **Nemotron 3.5** · Foundry Local | this PC | ✅ | — | Windows 11 24H2 or later; a model of about 756 MB, downloaded once |
| **Apple Speech** | this Mac | — | ✅ | macOS 26 or later; Apple language model |

The voice engine is chosen independently of the text engine. No AI model is
included in the installation files: local models are downloaded when you ask
for them.

## Windows and macOS

Both apps share the same core (prompts, AI providers, interface components)
and each keeps its own native integrations.

| | Windows | macOS |
|---|---|---|
| System | Windows 10 or 11, 64-bit | Apple Silicon Mac, macOS 13 or later |
| Where it lives | icon in the notification area | icon in the menu bar |
| Prompt menu, custom mode, answer window | ✅ | ✅ |
| Answer inserted into the original application | ✅ | ✅ |
| OpenAI, Ollama, LM Studio and LM Link | ✅ | ✅ |
| Built-in local AI | Foundry Local · Qwen3.5 (Windows 11 24H2+) | Apple Intelligence (macOS 26+) |
| Advanced features | ✅ | ✅ |
| Voice prompts and dictation *(experimental)* | OpenAI or Nemotron 3.5 | OpenAI or Apple Speech (macOS 26+) |
| Screen capture and analysis *(experimental)* | ✅ | — |
| Permissions requested | none | Accessibility, plus Microphone for dictation |
| API keys | Windows Credential Manager | settings file readable only by your account |
| Distribution | installer and standalone executable, unsigned | DMG signed with Developer ID and notarized by Apple |
| Built-in update | installed version: downloads the installer, checks its SHA-256 fingerprint and runs it | opens the DMG download |

Windows and macOS version numbers are independent. A release carries the
Windows number; the macOS version is shown in its “Informations de build”
(build information) block and in the app’s **À propos** (About) tab.

## Installation

All files are published on the
[Releases](https://github.com/lfpoulain/SuperMenu/releases) page.

| | Stable (recommended) | Beta |
|---|---|---|
| Where to find it | [latest release](https://github.com/lfpoulain/SuperMenu/releases/latest), marked “Latest” | [`beta` prerelease](https://github.com/lfpoulain/SuperMenu/releases/tag/beta), replaced on every build |
| Windows — installer | `SuperMenu_Setup.exe` | `SuperMenu_Beta_Setup.exe` |
| Windows — standalone executable | `SuperMenu.exe` | `SuperMenu_Beta.exe` |
| macOS Apple Silicon | `SuperMenu-macOS-arm64.dmg` | `SuperMenu_Beta-macOS-arm64.dmg` |
| SHA-256 fingerprints | `SHA256SUMS.txt` | `SHA256SUMS-beta.txt` |

Stable is published for each new validated version. Beta is rebuilt
automatically after every change to the `main` branch that passes CI: it gets
new features first, but may contain regressions. A Stable release is a beta
that was tested, then published under a final number.

Beta and Stable are the same application: installing one replaces the other.
A beta carries the number of the next Stable followed by `-beta.N`: for
example, 1.3.0-beta.40 comes before 1.3.0. Updates only offer a newer
version: if you switch back to the Stable channel, you keep your beta until
the next Stable, or reinstall Stable from the
[latest release](https://github.com/lfpoulain/SuperMenu/releases/latest).

### Windows

1. Download `SuperMenu_Setup.exe`.
2. Run it and accept the permission prompt: the installer puts SuperMenu in
   `Program Files`. You can tick **Démarrer SuperMenu avec Windows** (Start
   SuperMenu with Windows) and create a desktop icon. The installer is in
   French.
3. When installation finishes, SuperMenu starts in the notification area. Open
   its configuration and pick your engine in **Réglages > Texte**.

The standalone `SuperMenu.exe` runs without installation. It does not update
itself: **Vérifier les mises à jour** (Check for updates) reports a newer
version and opens the downloads page.

> [!NOTE]
> The Windows files are not signed with an Authenticode certificate, so
> Windows SmartScreen may show “Windows protected your PC” with an **unknown
> publisher**. Check the file’s fingerprint (see below), then click **More
> info** and **Run anyway**.

### macOS

1. Download `SuperMenu-macOS-arm64.dmg`.
2. Open the DMG and drag `SuperMenu.app` into the **Applications** folder.
3. Launch SuperMenu. As long as the permission is missing, its settings open
   on the **Application** section: click **Configurer Accessibilité…** (Set up
   Accessibility) and accept the macOS dialog. The microphone is only requested
   when you start a dictation or the microphone test.

The DMG is signed with a Developer ID certificate and notarized by Apple:
Gatekeeper checks it when you open it. Install later versions in the same
place so that macOS keeps the Accessibility permission.

### Verifying a download

Put the downloaded file and the fingerprint file from the same release
(`SHA256SUMS.txt` or `SHA256SUMS-beta.txt`) in the same folder, then run the
command from that folder.

Windows, in PowerShell:

```powershell
$file = 'SuperMenu_Setup.exe'   # name of the downloaded file
$sums = 'SHA256SUMS.txt'        # SHA256SUMS-beta.txt for the Beta
$expected = ((Select-String -Path $sums -Pattern $file -SimpleMatch).Line -split '\s+')[0]
(Get-FileHash $file -Algorithm SHA256).Hash -eq $expected   # True: the file is intact
```

macOS, in Terminal (for the Beta, replace the DMG name with
`SuperMenu_Beta-macOS-arm64.dmg` and `SHA256SUMS.txt` with
`SHA256SUMS-beta.txt`):

```bash
grep SuperMenu-macOS-arm64.dmg SHA256SUMS.txt | shasum -a 256 -c
# Expected output: SuperMenu-macOS-arm64.dmg: OK
```

The fingerprint proves the file is intact. To also check that it was built by
this repository’s workflows, every published file comes with a build
provenance attestation signed by GitHub (releases published since the
attestation was added). With [GitHub CLI](https://cli.github.com/) signed in
(`gh auth login`):

```bash
gh attestation verify SuperMenu_Setup.exe --repo lfpoulain/SuperMenu
```

The command shows the workflow and the commit that produced the file, and
fails for a file that was modified or built elsewhere.

### Updates

Pick the **Canal de mise à jour** (Update channel) in **Réglages >
Application > Interface et mises à jour** (Interface and updates). SuperMenu
checks for updates at startup, at most once a day, and on demand with
**Vérifier les mises à jour** (Check for updates).

- **On Windows**, the installed version downloads the channel’s installer into
  a private temporary folder, compares its SHA-256 fingerprint with the one
  published with the release, checks it again right before running it and
  rejects any file that differs. When installation finishes, SuperMenu is
  restarted with your normal rights, never as administrator. The standalone
  executable reports nothing at startup and does not update itself.
- **On macOS**, SuperMenu opens the channel’s DMG download in your browser;
  then replace the app in **Applications**.

## Default shortcuts

| Action | Windows | macOS | Available |
|---|---|---|---|
| Open the prompt menu | `Ctrl+²` | `Cmd+Shift+Space` | always |
| Custom mode | `Ctrl+Alt+M` | `Cmd+Shift+M` | always |
| Direct shortcut for a prompt | set in the **Prompts** tab | set in the **Prompts** tab | advanced features |
| Voice menu | `Ctrl+Alt+²` | **Voix** submenu of the prompt menu | experimental features |
| Instant dictation | to be set | to be set | experimental features |
| Screen capture | `Ctrl+Alt+&` | — | experimental features |

General shortcuts are changed in **Réglages > Raccourcis**, prompt shortcuts in
the **Prompts** tab. The default Windows shortcuts are designed for a French
AZERTY keyboard: on other layouts, `Ctrl+²` uses the key below Esc
(``Ctrl+` `` on QWERTY, `Ctrl+^` on QWERTZ). A shortcut refused by the system
is reported.

## Privacy and security

- **Your text only goes to the engine you chose**: the one in
  **Réglages > Texte**, or the prompt’s own engine with the advanced features;
  your voice only goes to the transcription engine you chose. SuperMenu has no
  account and no server of its own. Apart from these engines, it only contacts
  GitHub, for updates, and, with Foundry Local, Microsoft’s model catalog.
- **Local engines**: with Foundry Local, Apple Intelligence, Nemotron or Apple
  Speech, text and voice are processed on your computer; with Ollama or
  LM Studio, on the server you specified.
- **Separate keys**: the OpenAI key is only sent to OpenAI, and the optional
  token of an Ollama or LM Studio server only to that server.
- **Imported prompts**: server addresses in an imported prompt file are
  ignored, so an imported prompt can only use engines already configured in
  your settings. With the advanced features, however, it can pick its own
  engine, for example OpenAI if your key is saved, even if your usual engine is
  local: check the model of imported prompts.
- **Where secrets are stored**:
  - Windows: the OpenAI key and the server token are kept in **Windows
    Credential Manager**, outside the `%USERPROFILE%\SuperMenu.ini` settings
    file. Uninstalling offers to delete settings, logs and keys;
  - macOS: in the settings file
    `~/Library/Application Support/SuperMenu/SuperMenu.ini`, readable only by
    your account (`0600` permissions), not in the Keychain.
- **Clipboard**: SuperMenu uses it to read the selection and insert the
  answer, then restores it. The text it pastes is excluded from clipboard
  history and clipboard sync.
- **Logs**: they describe what the app does (steps, errors, text lengths),
  never an API key, selected text, a typed prompt or a transcription.
- **Public builds**: releases are built by this repository’s GitHub Actions
  workflows and come with their SHA-256 fingerprints and a build provenance
  attestation. The macOS DMG is signed
  and notarized; during an update, the Windows installer is checked against
  the published fingerprint before it runs.

<details>
<summary>Where to find the logs</summary>

| Platform | Folder |
|---|---|
| Windows (installer or standalone executable) | `%LOCALAPPDATA%\SuperMenu\logs\` |
| Windows, from source | `win32\logs\` |
| macOS | `~/Library/Logs/SuperMenu/` |

The **Ouvrir le dossier des journaux** (Open the logs folder) button is in
**Réglages > Application > Dossiers et diagnostic** (Folders and diagnostics).

</details>

Found a security issue? Do not post it in an issue: follow the
[security policy](SECURITY.md) (in French).

## Development

The repository holds two apps, `win32/` and `macos/`, and the shared
`shared/supermenu_core` package, installed automatically by each platform’s
`requirements.txt`. Installation and tests are always run from the platform
folder.

### Windows

Python 3.11 at least (required by the Foundry Local SDK); Python 3.12 is
recommended and used for published builds.

```powershell
git clone https://github.com/lfpoulain/SuperMenu.git
cd SuperMenu\win32
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run.py
```

### macOS

An Apple Silicon Mac and Python 3.12. The Apple Foundation Models and Apple
Speech components need Xcode 26 or later; the other engines work without them.

```bash
git clone https://github.com/lfpoulain/SuperMenu.git
cd SuperMenu/macos
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
bash scripts/build_foundation_helper.sh   # optional: Apple Intelligence
bash scripts/build_speech_helper.sh       # optional: Apple Speech
python run.py
```

During development, macOS grants the Accessibility permission to the program
that launches SuperMenu (Terminal, your editor or Python).

### Checking your changes

From `win32/` or `macos/`, the same checks as CI:

```text
python -m compileall -q ../shared/supermenu_core src run.py
python -m pytest -q ../shared/tests
python -m pytest -q tests
python -m flake8 ../shared/supermenu_core src tests run.py --select=F,E9
```

On macOS, add the native smoke test `python run.py --smoke-test`. To run the Qt
tests without a display, set `QT_QPA_PLATFORM=offscreen`.

<details>
<summary>Building the executables</summary>

**Windows**, from `win32/`:

```powershell
pyinstaller --noconfirm --clean SuperMenu.spec
$smoke = Start-Process -FilePath dist\SuperMenu.exe -ArgumentList "--smoke-test" -Wait -PassThru
$smoke.ExitCode   # 0 expected
```

The installer is then built with Inno Setup from `setup_supermenu.iss`.

**macOS**, from `macos/`:

```bash
bash scripts/build_dmg.sh
```

Without a Developer ID identity, the script produces an unsigned development
DMG. Published DMGs are signed with Developer ID and notarized by the
repository’s release workflows.

</details>

CI tests Windows with Python 3.11 and 3.12 and macOS with Python 3.12, and
builds a test DMG for every pull request. Releases are built and published by
the repository’s GitHub Actions workflows: a rolling beta after each change to
`main`, and a Stable release on a `vX.Y.Z` tag. Before proposing a change,
read the [contribution guide](CONTRIBUTING.md) (in French).

## Repository layout

```text
SuperMenu/
├── shared/                  # shared core, with no OS-specific code
│   ├── supermenu_core/      # AI providers, prompts, audio, validators, Qt components
│   ├── tests/
│   └── tools/               # preview of the interface components
├── win32/                   # Windows app: Win32, Foundry Local, installer
│   ├── src/  docs/  tests/
│   ├── SuperMenu.spec       # PyInstaller build
│   └── setup_supermenu.iss  # Inno Setup installer
├── macos/                   # macOS app: AppKit, Accessibility, DMG
│   ├── src/  docs/  tests/
│   ├── native/              # Swift components for Apple Intelligence and Apple Speech
│   ├── scripts/             # build, signing and notarization
│   └── SuperMenu-macos.spec
├── docs/                    # README images
├── licenses/                # third-party license texts (LGPL, GPL, Apache, Microsoft…)
├── tools/                   # release checks and third-party license collection
└── .github/                 # CI, beta, Stable releases, issue templates
```

`shared/supermenu_core` never imports Windows- or macOS-specific code; a test
checks it. Global shortcuts, clipboard, insertion, permissions, storage and
packaging stay in each platform.

## Documentation

The project documentation is written in French.

| Topic | Windows | macOS |
|---|---|---|
| Overview | [win32/README.md](win32/README.md) | [macos/README.md](macos/README.md) |
| User guide | [Windows guide](win32/docs/GUIDE_UTILISATION.md) | [macOS guide](macos/docs/GUIDE_UTILISATION.md) |
| Technical architecture | [Windows architecture](win32/docs/ARCHITECTURE.md) | [macOS architecture](macos/docs/ARCHITECTURE.md) |
| Platform specifics | [Foundry Local](win32/docs/foundry-local.md) | [Packaging and notarization](macos/docs/ARCHITECTURE.md#packaging-et-notarisation) |

| Project | Contents |
|---|---|
| [Shared core](shared/README.md) | shared modules and architecture rules |
| [Contributing](CONTRIBUTING.md) | environment, tests, style, pull requests |
| [Security](SECURITY.md) | supported versions, private vulnerability reporting |
| [Code of conduct](CODE_OF_CONDUCT.md) | rules for project discussions |
| [Changelog](CHANGELOG.md) | what changed in each version |
| [Third-party components](THIRD_PARTY_NOTICES.md) | bundled libraries and their licenses |

## License

SuperMenu is distributed under the
**[PolyForm Noncommercial 1.0.0](LICENSE)** license. In short, with the license
text being authoritative:

**Allowed, for any noncommercial purpose:**

- using SuperMenu personally: study, hobby, personal projects, research,
  experiments;
- using it within a charitable organization, an educational institution, a
  public research organization, a public safety or health organization, an
  environmental protection organization or a government institution;
- studying the code, changing it and creating new works based on it;
- redistributing SuperMenu, changed or not, provided you pass on the license
  terms (or their URL) and the `Required Notice:` line of the
  [LICENSE](LICENSE) file.

**Not allowed without a separate agreement with the author:**

- any commercial use, for example selling SuperMenu or a modified version,
  building it into a paid product or service, or using it for a company’s
  business;
- sublicensing or transferring your license to anyone else.

The software comes as is, without any warranty.

Everything published before the switch to PolyForm remains available under
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): the releases
up to v1.2.1 (Windows 1.2.1, macOS 1.2.8), their source code (tags `v1.2.0`
and `v1.2.1`) and the betas published until then. Versions published
afterwards are under PolyForm Noncommercial 1.0.0.

Contributions are accepted under the project license; their authors also
grant the maintainer the right to distribute them under other terms,
including commercial ones (see
[CONTRIBUTING.md](CONTRIBUTING.md#licence-des-contributions), in French).

The published apps contain third-party components (Python, Qt and PySide6,
pynput…) that remain under their own licenses: the list and the texts are in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [licenses/](licenses).
AI models downloaded from SuperMenu come with their own terms.

OpenAI, Ollama, LM Studio, Apple Intelligence and Microsoft Foundry Local are
trademarks of their respective owners; SuperMenu is not affiliated with any of
these providers.
