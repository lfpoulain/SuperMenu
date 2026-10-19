# Composants tiers et licences

SuperMenu est distribué sous la licence
[PolyForm Noncommercial 1.0.0](LICENSE). Tout ce qui a été publié avant ce
changement de licence reste disponible sous sa licence d'origine,
CC BY-NC 4.0 : les releases jusqu'à v1.2.1 (Windows 1.2.1, macOS 1.2.8), les
bêtas publiées jusque-là et l'historique Git antérieur au commit qui remplace
`LICENSE`.

Les applications publiées (exécutable Windows, installateur Windows et
application macOS) contiennent aussi des composants écrits par d'autres
auteurs. Chacun reste sous sa propre licence : la licence de SuperMenu ne
s'applique pas à eux et ne restreint aucun des droits que leurs licences
vous donnent.

## Où trouver les textes de licence

- **Dans ce dépôt** : le dossier [`licenses/`](licenses) contient les textes
  complets des licences citées dans ce fichier :
  - LGPL-3.0, GPL-3.0 (à laquelle la LGPL renvoie), LGPL-2.1 (FFmpeg) et
    Apache 2.0 ;
  - `Qt-third-party.txt` : mentions de copyright et licences du code tiers
    intégré aux bibliothèques Qt ;
  - les conditions de Microsoft pour Foundry Local Core et Windows ML
    Runtime, les licences MIT et les avis tiers d'ONNX Runtime et d'ONNX
    Runtime GenAI, et la licence MIT de jiter.
- **Dans chaque build** : le dossier `third_party_licenses/` est généré
  pendant la compilation par
  [`tools/collect_third_party_licenses.py`](tools/collect_third_party_licenses.py).
  Il contient les fichiers de licence fournis par chaque paquet Python inclus
  et un `INDEX.txt` qui donne, pour cette build précise, la liste de ces
  paquets avec leur version exacte. Les bibliothèques natives livrées dans
  ces paquets ou trouvées pendant le build (Qt, FFmpeg, OpenSSL, runtime
  Microsoft…) n'y figurent pas : elles sont décrites ci-dessous.
- **Windows** : l'installateur place `LICENSE.txt`, ce fichier, `licenses\`
  et `third_party_licenses\` dans le dossier d'installation. L'exécutable
  portable les contient aussi ; l'onglet « À propos » ouvre la copie incluse.
- **macOS** : les mêmes fichiers se trouvent dans
  `SuperMenu.app/Contents/Resources/`.

## Composants inclus dans les applications

Les versions des dépendances directes sont celles épinglées dans
`win32/requirements.txt` et `macos/requirements.txt`. Les versions marquées
d'un astérisque (\*) sont des dépendances indirectes non épinglées : la
valeur indiquée est celle de l'environnement de référence, la version exacte
de chaque build figure dans `third_party_licenses/INDEX.txt`. Selon
l'environnement de build, PyInstaller peut aussi inclure des modules
optionnels d'autres paquets installés (par exemple des outils de
développement) : ils figurent alors, avec leurs fichiers de licence, dans ce
même index.

| Composant | Version | Licence (identifiant SPDX s'il existe) | Site | Windows | macOS |
| --- | --- | --- | --- | :---: | :---: |
| Python (interpréteur et bibliothèque standard) | 3.12 | PSF-2.0 | <https://www.python.org/> | oui | oui |
| OpenSSL (voir les notes) | 3 | Apache-2.0 | <https://www.openssl.org/> | oui | oui |
| Runtime Microsoft Visual C++ et Universal C Runtime | 14 | Code distribuable Microsoft | <https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files> | oui | non |
| Chargeur PyInstaller (bootloader) | 6.17.0 | GPL-2.0-or-later WITH Bootloader-exception | <https://pyinstaller.org/> | oui | oui |
| Scripts d'exécution de pyinstaller-hooks-contrib | 2025.10\* | Apache-2.0 | <https://github.com/pyinstaller/pyinstaller-hooks-contrib> | oui | selon la build |
| Qt for Python : PySide6, PySide6_Essentials, PySide6_Addons, shiboken6 | 6.11.1 | LGPL-3.0-only (choisie parmi LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only) | <https://pyside.org/> | oui | oui |
| Qt (bibliothèques livrées avec PySide6) | 6.11.1 | LGPL-3.0-only ; code tiers intégré sous licences permissives, voir `licenses/Qt-third-party.txt` | <https://www.qt.io/> | oui | oui |
| FFmpeg (avcodec, avformat, avutil, swresample, swscale), chargé par Qt Multimedia | 7.1.3 | LGPL-2.1-or-later | <https://ffmpeg.org/> | oui | oui |
| pynput | 1.8.2 | LGPL-3.0-or-later | <https://github.com/moses-palmer/pynput> | oui | oui |
| six | 1.17.0\* | MIT | <https://github.com/benjaminp/six> | oui | oui |
| pyqtdarktheme (avec sa copie intégrée de QtPy) | 0.1.7 | MIT | <https://github.com/5yutan5/PyQtDarkTheme> | oui | oui |
| requests | 2.34.2 | Apache-2.0 | <https://github.com/psf/requests> | oui | oui |
| urllib3 | 2.5.0\* | MIT | <https://github.com/urllib3/urllib3> | oui | oui |
| idna | 3.10\* | BSD-3-Clause | <https://github.com/kjd/idna> | oui | oui |
| charset-normalizer | 3.4.2\* | MIT | <https://github.com/jawah/charset_normalizer> | oui | oui |
| certifi | 2025.8.3\* | MPL-2.0 | <https://github.com/certifi/python-certifi> | oui | oui |
| websocket-client | 1.9.0 | Apache-2.0 | <https://github.com/websocket-client/websocket-client> | oui | oui |
| PyObjC : pyobjc-core, pyobjc-framework-Cocoa, -Quartz, -CoreText, -ApplicationServices | 12.2.2 | MIT | <https://github.com/ronaldoussoren/pyobjc> | non | oui |
| keyring | 25.7.0 | MIT | <https://github.com/jaraco/keyring> | oui | non |
| jaraco.classes, jaraco.context, jaraco.functools | 3.4.0\*, 6.0.1\*, 4.2.1\* | MIT | <https://github.com/jaraco> | oui | non |
| more-itertools | 10.7.0\* | MIT | <https://github.com/more-itertools/more-itertools> | oui | non |
| pywin32-ctypes | 0.2.3\* | BSD-3-Clause | <https://github.com/enthought/pywin32-ctypes> | oui | non |
| pywin32 | 311 | PSF-2.0 | <https://github.com/mhammond/pywin32> | oui | non |
| Pillow | 12.2.0 | MIT-CMU | <https://python-pillow.github.io/> | oui | non |
| openai (SDK Python) | 2.37.0 | Apache-2.0 | <https://github.com/openai/openai-python> | oui | non |
| httpx | 0.28.1\* | BSD-3-Clause | <https://github.com/encode/httpx> | oui | non |
| httpcore | 1.0.9\* | BSD-3-Clause | <https://github.com/encode/httpcore> | oui | non |
| h11 | 0.16.0\* | MIT | <https://github.com/python-hyper/h11> | oui | non |
| anyio | 4.10.0\* | MIT | <https://github.com/agronholm/anyio> | oui | non |
| sniffio | 1.3.1\* | MIT OR Apache-2.0 | <https://github.com/python-trio/sniffio> | oui | non |
| distro | 1.9.0\* | Apache-2.0 | <https://github.com/python-distro/distro> | oui | non |
| jiter | 0.10.0\* | MIT | <https://github.com/pydantic/jiter> | oui | non |
| pydantic | 2.11.7\* | MIT | <https://github.com/pydantic/pydantic> | oui | non |
| pydantic-core | 2.33.2\* | MIT | <https://github.com/pydantic/pydantic-core> | oui | non |
| annotated-types | 0.7.0\* | MIT | <https://github.com/annotated-types/annotated-types> | oui | non |
| typing-extensions | 4.14.1\* | PSF-2.0 | <https://github.com/python/typing_extensions> | oui | non |
| typing-inspection | 0.4.1\* | MIT | <https://github.com/pydantic/typing-inspection> | oui | non |
| tqdm | 4.67.1\* | MPL-2.0 AND MIT | <https://github.com/tqdm/tqdm> | oui | non |
| colorama | 0.4.6\* | BSD-3-Clause | <https://github.com/tartley/colorama> | oui | non |
| foundry-local-sdk-winml (SDK Foundry Local) | 1.2.4 | MIT | <https://github.com/microsoft/Foundry-Local> | oui | non |
| foundry-local-core-winml, onnxruntime-core, onnxruntime-genai-core | 1.2.4, 1.26.0, 0.14.1 | conditions Microsoft et MIT, voir [ci-dessous](#composants-dexécution-microsoft-foundry-local) | <https://github.com/microsoft/Foundry-Local> | oui | non |
| Inno Setup (programme d'installation uniquement) | 6 | Licence Inno Setup | <https://jrsoftware.org/isinfo.php> | installateur | non |

Notes :

- **Python** : le fichier `LICENSE.txt` de l'interpréteur, copié dans
  `third_party_licenses/python/`, contient aussi les conditions des
  bibliothèques livrées avec lui (bzip2, libffi, OpenSSL, etc.) et, sous
  Windows, celles du code distribuable Microsoft (runtime Visual C++).
- **OpenSSL** : Python embarque ses propres bibliothèques OpenSSL 3
  (`libcrypto-3`, `libssl-3`). Sous Windows, le hook QtNetwork de PyInstaller
  cherche aussi `libcrypto-3-x64.dll` et `libssl-3-x64.dll` dans le `PATH` de
  la machine de build (par exemple celles de Git pour Windows ou d'une
  installation d'OpenSSL) et les inclut s'il les trouve. Elles servent au
  module TLS de Qt, qui utilise sinon Schannel, le TLS de Windows. Leur
  version dépend donc de la machine de build ; OpenSSL 3 est sous licence
  Apache 2.0 (`licenses/Apache-2.0.txt`).
- **Qt** : la LGPL-3.0 couvre les bibliothèques Qt elles-mêmes. Elles
  intègrent du code tiers (FreeType, HarfBuzz, PCRE2, libpng, libjpeg-turbo,
  zlib, libtiff, libwebp…) dont les mentions et les licences sont regroupées
  dans `licenses/Qt-third-party.txt`. Trois éléments collectés par les hooks
  Qt de PyInstaller mais jamais utilisés par SuperMenu sont retirés des
  builds : Qt Virtual Keyboard, disponible seulement sous GPL-3.0 ou sous
  licence commerciale ; Qt Pdf et son module d'images, qui intègrent PDFium ;
  et, sous Windows, `opengl32sw.dll`, le rendu OpenGL logiciel de Mesa.
- **FFmpeg** : Qt Multimedia, qui sert au micro, charge les bibliothèques
  FFmpeg livrées avec PySide6. Qt les compile sans les options GPL : elles
  sont sous LGPL-2.1 ou ultérieure (`licenses/LGPL-2.1.txt`), avec quelques
  fichiers sous licences permissives listés dans
  `licenses/Qt-third-party.txt`. Voir plus bas pour leurs sources et leur
  remplacement.
- **PyInstaller** : l'exception « Bootloader » de sa licence autorise la
  distribution du chargeur intégré à l'exécutable, quelle que soit la licence
  de l'application. Ses scripts d'exécution (runtime hooks) sont sous licence
  Apache 2.0.
- **Inno Setup** sert uniquement à produire l'installateur Windows, qui en
  contient le programme d'installation. Sa
  [licence](https://jrsoftware.org/files/is/license.txt) en autorise l'usage
  à toute fin, y compris la distribution des installateurs ainsi créés.
- **jiter** ne fournit pas de fichier de licence dans son paquet :
  `INDEX.txt` le signale. Sa licence MIT est reproduite dans
  `licenses/jiter-MIT.txt`.
- La roue PySide6 ne contient qu'un renvoi aux conditions commerciales de
  Qt (`LicenseRef-Qt-Commercial.txt`). SuperMenu n'utilise pas de licence
  commerciale : PySide6 et Qt sont utilisés sous LGPL-3.0, voir plus bas.

## Composants d'exécution Microsoft Foundry Local

Sous Windows, SuperMenu intègre le SDK Python
[Foundry Local](https://github.com/microsoft/Foundry-Local) et les composants
d'exécution que Microsoft publie avec lui sur PyPI. Les paquets PyPI de ces
composants ne contiennent aucune mention de licence ; les conditions
ci-dessous sont celles sous lesquelles Microsoft publie les mêmes fichiers
sur NuGet. Leurs textes sont copiés dans `licenses/`.

| Paquet PyPI | Fichiers livrés | Conditions | Texte |
| --- | --- | --- | --- |
| `foundry-local-sdk-winml` 1.2.4 | code Python du SDK | MIT | fourni par le paquet (`third_party_licenses/`) |
| `foundry-local-core-winml` 1.2.4 | `Microsoft.AI.Foundry.Local.Core.dll` | Microsoft Software License Terms, Foundry Local Core ([NuGet `Microsoft.AI.Foundry.Local.Core` 1.2.4](https://www.nuget.org/packages/Microsoft.AI.Foundry.Local.Core/1.2.4)) | `licenses/Microsoft-Foundry-Local-Core.txt` |
| `foundry-local-core-winml` 1.2.4 | `Microsoft.Windows.AI.MachineLearning.dll` (Windows ML Runtime 2.1.1) | Microsoft Software License Terms, Microsoft Windows ML Runtime ([NuGet `Microsoft.Windows.AI.MachineLearning` 2.1.1](https://www.nuget.org/packages/Microsoft.Windows.AI.MachineLearning/2.1.1)) | `licenses/Microsoft-Windows-ML-Runtime.txt` ; ses avis tiers sont ceux d'ONNX Runtime |
| `onnxruntime-core` 1.26.0 | `onnxruntime.dll`, `onnxruntime_providers_shared.dll` | MIT ([ONNX Runtime](https://github.com/microsoft/onnxruntime)), avec les avis de ses composants tiers | `licenses/onnxruntime-MIT.txt`, `licenses/onnxruntime-ThirdPartyNotices.txt` |
| `onnxruntime-genai-core` 0.14.1 | `onnxruntime-genai.dll` | MIT ([ONNX Runtime GenAI](https://github.com/microsoft/onnxruntime-genai)), avec les avis de ses composants tiers | `licenses/onnxruntime-genai-MIT.txt`, `licenses/onnxruntime-genai-ThirdPartyNotices.txt` |

Microsoft autorise la distribution de `Microsoft.AI.Foundry.Local.Core.dll`
et de `Microsoft.Windows.AI.MachineLearning.dll` avec une application, à
condition que ses utilisateurs acceptent des conditions qui protègent ces
composants au moins autant que les siennes. Si vous utilisez SuperMenu pour
Windows, ces deux composants vous sont donc concédés sous les conditions de
Microsoft citées ci-dessus, et non sous la licence de SuperMenu, qui ne vous
donne aucun droit sur eux. En particulier :

- vous ne pouvez pas les extraire de SuperMenu pour les distribuer
  séparément, ni les proposer comme un produit autonome ;
- vous ne pouvez pas en faire l'ingénierie inverse, les décompiler ou les
  désassembler, sauf dans la mesure où la loi l'autorise malgré cette
  limitation ;
- vous ne pouvez pas retirer, masquer ou modifier les mentions de Microsoft
  et de ses fournisseurs ;
- Microsoft les fournit « en l'état », avec les exclusions de garantie et
  les limitations de responsabilité de ses conditions.

Si vous redistribuez SuperMenu pour Windows, transmettez ces conditions avec
lui. Elles ne concernent que ces deux composants Microsoft : ni le reste de
SuperMenu, ni les bibliothèques sous LGPL décrites plus bas. L'installateur
Windows les présente avant l'installation.

## Modèles d'IA

Aucun modèle d'IA n'est inclus dans SuperMenu.

- **Foundry Local (Windows)** télécharge, uniquement à votre demande, les
  modèles de texte Qwen3.5 et le modèle vocal Nemotron depuis le catalogue
  de Microsoft. Chaque modèle est régi par sa propre licence, indiquée sur
  sa fiche :
  [Qwen3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B),
  [Qwen3.5 9B](https://huggingface.co/Qwen/Qwen3.5-9B),
  [Nemotron 3.5 ASR Streaming 0.6B](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b).
  Consultez aussi les conditions affichées par le catalogue Foundry Local.
- **Apple Foundation Models** et la **reconnaissance vocale d'Apple**
  (macOS) sont des frameworks du système : SuperMenu les appelle sans les
  redistribuer, ils restent soumis aux conditions de macOS.
- **OpenAI, Ollama, LM Studio et les serveurs compatibles** sont des services
  ou logiciels que vous configurez vous-même ; leurs conditions d'utilisation
  et celles des modèles que vous choisissez s'appliquent.

## Bibliothèques sous LGPL : PySide6, Qt, FFmpeg et pynput

SuperMenu utilise PySide6 (avec shiboken6, les bibliothèques Qt qu'il fournit
et les bibliothèques FFmpeg que charge Qt Multimedia) et pynput sans les
modifier, comme des bibliothèques distinctes chargées par l'interpréteur
Python intégré. Leurs licences sont la LGPL-3.0
([`licenses/LGPL-3.0.txt`](licenses/LGPL-3.0.txt)), qui complète la GPL-3.0
([`licenses/GPL-3.0.txt`](licenses/GPL-3.0.txt)), et, pour FFmpeg, la
LGPL-2.1 ou ultérieure ([`licenses/LGPL-2.1.txt`](licenses/LGPL-2.1.txt)).

Codes sources des versions livrées :

- PySide6 et shiboken6 6.11.1 : étiquette
  [`v6.11.1` de pyside-setup](https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.11.1)
  et archive
  [`pyside-setup-everywhere-src-6.11.1.zip`](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/) ;
- Qt 6.11.1 : <https://download.qt.io/archive/qt/6.11/6.11.1/> (archive
  complète `single/qt-everywhere-src-6.11.1.tar.xz`) ; les licences des
  composants tiers de Qt sont aussi listées sur
  <https://doc.qt.io/qt-6/licenses-used-in-qt.html> ;
- FFmpeg 7.1.3 : <https://ffmpeg.org/releases/ffmpeg-7.1.3.tar.xz> ; les
  options de compilation utilisées par Qt se trouvent dans ses
  [scripts de provisioning](https://code.qt.io/cgit/qt/qt5.git/tree/coin/provisioning?h=v6.11.1) ;
- pynput 1.8.2 : <https://github.com/moses-palmer/pynput> et l'archive
  source sur <https://pypi.org/project/pynput/1.8.2/#files>.

Vous pouvez remplacer ces bibliothèques par une version modifiée ou plus
récente :

1. **Depuis les sources de SuperMenu** (méthode recommandée) : clonez
   <https://github.com/lfpoulain/SuperMenu>, créez un environnement Python
   3.12, installez `win32/requirements-dev.txt` ou
   `macos/requirements-dev.txt` (qui incluent `requirements.txt` et
   PyInstaller), puis installez votre version de PySide6 ou de pynput à la
   place de celle épinglée. Lancez l'application avec `python run.py` depuis
   `win32/` ou `macos/`, ou reconstruisez-la avec PyInstaller
   (`pyinstaller SuperMenu.spec` sous Windows, `scripts/build_dmg.sh` sous
   macOS).
2. **Dans une application déjà construite** : sous macOS, `SuperMenu.app` est
   un dossier et les bibliothèques Qt et FFmpeg se trouvent dans
   `SuperMenu.app/Contents/Frameworks/PySide6/`. Vous pouvez y substituer des
   versions compatibles, puis signer de nouveau l'application pour votre
   machine (`codesign --force --deep --sign - SuperMenu.app`), car toute
   modification invalide la signature d'origine. Sous Windows, l'exécutable
   est un fichier unique : pour changer ces bibliothèques, reconstruisez-le
   comme indiqué au point 1. pynput étant du code Python intégré à l'archive
   de l'application, il se remplace aussi en reconstruisant.

Quelle que soit la licence de SuperMenu, rien n'interdit de modifier les
parties de PySide6, de Qt, de FFmpeg et de pynput contenues dans
l'application, ni de procéder à l'ingénierie inverse nécessaire pour déboguer
ces modifications. La licence PolyForm s'applique au code de SuperMenu, pas à
ces bibliothèques.

## Anciennes versions et historique du dépôt

La version Windows 1.2.0 (release `v1.2.0`) intégrait le programme
`ffmpeg.exe`, et l'historique Git contient ce fichier, d'abord dans
`bin/ffmpeg.exe` puis dans `win32/bin/ffmpeg.exe`, du commit `7014606` au
commit `dfa9438`, qui l'a retiré. Il s'agit d'une build FFmpeg 7.1.1
« essentials » publiée par [gyan.dev](https://www.gyan.dev/ffmpeg/builds/),
compilée avec `--enable-gpl` et `--enable-version3` et avec des bibliothèques
sous GPL (x264, x265…) : ce programme est distribué sous GPL-3.0
([`licenses/GPL-3.0.txt`](licenses/GPL-3.0.txt)). Son code source est celui
de FFmpeg 7.1.1 (<https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz>) et des
bibliothèques indiquées par gyan.dev pour cette build. Les versions suivantes
de SuperMenu ne contiennent plus ce programme.
