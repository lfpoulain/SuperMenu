# 🔍 Analyse complète : Problèmes de Threading et Améliorations

## ✅ DÉJÀ CORRIGÉ

### 1. HotkeyManager - Signal émis depuis thread Windows
**Statut :** ✅ Corrigé
- Utilisation de `QMetaObject.invokeMethod()` avec `Qt.QueuedConnection`
- Les signaux sont maintenant émis dans le thread Qt principal

### 2. OpenAIClient - Signaux émis depuis threading.Thread
**Statut :** ✅ Corrigé
- Ajout de méthodes `_emit_finished()` et `_emit_error()`
- Utilisation de `QMetaObject.invokeMethod()` pour émettre les signaux

---

## 🔴 PROBLÈMES CRITIQUES À CORRIGER

### 3. QMessageBox créés dans des callbacks (context_menu.py)

**Lignes concernées :** 268, 404, 442, 471, 546, 584, 640

**Problème :**
```python
# ❌ Peut être appelé depuis un thread non-Qt
QMessageBox.critical(None, "Erreur", message)
```

**Solution :** Utiliser `SafeDialogs` (déjà créé)
```python
# ✅ Thread-safe
from utils.safe_dialogs import SafeDialogs
SafeDialogs.show_critical("Erreur", message)
```

**Fichiers à modifier :**
- `src/utils/context_menu.py` - Remplacer tous les `QMessageBox` par `SafeDialogs`
- `src/audio/voice_recognition.py` lignes 84, 120, 129, 157

---

### 4. QApplication.restoreOverrideCursor() pas toujours garanti

**Lignes :** `context_menu.py:429`, `context_menu.py:533`

**Problème :**
```python
QApplication.setOverrideCursor(Qt.WaitCursor)
try:
    # code...
except:
    # Si exception ici, curseur reste bloqué!
    pass
# restoreOverrideCursor() pas appelé
```

**Solution :** Toujours utiliser `finally:`
```python
QApplication.setOverrideCursor(Qt.WaitCursor)
try:
    # code...
except Exception as e:
    # handle error
finally:
    QApplication.restoreOverrideCursor()  # ✅ TOUJOURS exécuté
```

**Impact :** Curseur bloqué en mode "attente" après une erreur

---

## 🟡 PROBLÈMES MOYENS

### 5. Dialogue modal créé dans voice_recognition.start_voice_recognition()

**Fichier :** `voice_recognition.py` ligne 88-112

**Problème :**
```python
dialog = QDialog(None)
dialog.exec()  # ❌ Bloque le thread Qt
```

**Solution :** Utiliser un dialogue non-modal ou un signal
```python
# Option 1: Non-modal
dialog.show()
dialog.activateWindow()

# Option 2: Signal Qt
recording_started = Signal()
recording_stopped = Signal(str)  # avec texte transcrit
```

**Impact :** Peut bloquer l'interface si appelé au mauvais moment

---

### 6. TextInserter utilise time.sleep() dans le thread Qt

**Fichier :** `text_inserter.py` lignes 43, 50

**Problème :**
```python
time.sleep(CLIPBOARD_COPY_DELAY)  # ❌ Bloque le thread Qt
self.keyboard.press(Key.ctrl)
time.sleep(CLIPBOARD_PASTE_DELAY)  # ❌ Bloque encore
```

**Solution :** Utiliser QTimer pour les délais
```python
QTimer.singleShot(delay_ms, callback)
```

**Impact :** Interface figée pendant l'insertion de texte

---

### 7. Pas de timeout sur les dialogues modaux

**Problème :** Les dialogues peuvent rester ouverts indéfiniment

**Solution :** Ajouter un auto-close timer
```python
dialog = QDialog()
auto_close_timer = QTimer()
auto_close_timer.setSingleShot(True)
auto_close_timer.timeout.connect(dialog.reject)
auto_close_timer.start(30000)  # 30 secondes max
```

---

## 🟢 AMÉLIORATIONS SIMPLES ET TANGIBLES

### A. Ajouter un indicateur visuel pour les opérations longues

**Créer :** `src/utils/loading_indicator.py`

```python
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer

class LoadingIndicator(QDialog):
    def __init__(self, message="Traitement en cours..."):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        layout = QVBoxLayout()
        label = QLabel(message)
        layout.addWidget(label)
        self.setLayout(layout)
        
    def show_for(self, duration_ms):
        """Affiche pour une durée limitée"""
        self.show()
        QTimer.singleShot(duration_ms, self.close)
```

---

### B. Centraliser la gestion des erreurs API

**Créer :** `src/utils/error_handler.py`

```python
class ErrorHandler:
    @staticmethod
    def handle_api_error(error, context=""):
        """Gestion centralisée des erreurs API"""
        from utils.safe_dialogs import SafeDialogs
        
        if "timeout" in str(error).lower():
            SafeDialogs.show_warning(
                "Timeout", 
                "La requête a pris trop de temps. Réessayez."
            )
        elif "401" in str(error):
            SafeDialogs.show_critical(
                "Erreur d'authentification", 
                "Clé API invalide. Vérifiez vos paramètres."
            )
        else:
            SafeDialogs.show_critical(
                "Erreur", 
                f"{context}: {str(error)}"
            )
```

---

### C. Ajouter un rate limiter pour éviter le spam API

**Créer :** `src/utils/rate_limiter.py`

```python
import time
from collections import deque

class RateLimiter:
    def __init__(self, max_calls=10, time_window=60):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = deque()
    
    def can_proceed(self):
        """Vérifie si on peut faire une nouvelle requête"""
        now = time.time()
        
        # Supprimer les appels trop anciens
        while self.calls and self.calls[0] < now - self.time_window:
            self.calls.popleft()
        
        # Vérifier la limite
        if len(self.calls) >= self.max_calls:
            return False
        
        self.calls.append(now)
        return True
    
    def time_until_available(self):
        """Temps d'attente avant la prochaine requête possible"""
        if len(self.calls) < self.max_calls:
            return 0
        
        oldest_call = self.calls[0]
        time_since_oldest = time.time() - oldest_call
        return max(0, self.time_window - time_since_oldest)
```

**Utilisation dans OpenAIClient :**
```python
if not self.rate_limiter.can_proceed():
    wait_time = self.rate_limiter.time_until_available()
    SafeDialogs.show_warning(
        "Rate limit", 
        f"Trop de requêtes. Attendez {wait_time:.0f} secondes."
    )
    return
```

---

### D. Améliorer le logging avec contexte

**Modifier :** `src/utils/logger.py`

```python
import logging
import threading

def log(message, level=logging.INFO, context=""):
    """Log avec information de thread"""
    thread_name = threading.current_thread().name
    if context:
        message = f"[{context}] {message}"
    message = f"[Thread: {thread_name}] {message}"
    
    logging.log(level, message)
```

---

### E. Ajouter un health check pour le hook clavier

**Déjà implémenté dans HotkeyManager mais à améliorer :**

```python
def _check_hook_health(self):
    """Vérification plus complète de la santé du hook"""
    issues = []
    
    if self._hook_error_count >= self._max_errors:
        issues.append("Trop d'erreurs détectées")
    
    if self.registered and self.key_listener_hook is None:
        issues.append("Hook None mais enregistré")
    
    if not self.registered and self.key_listener_hook is not None:
        issues.append("Hook actif mais non enregistré")
    
    # Vérifier que le hook répond
    try:
        test_key = keyboard.is_pressed('shift')
    except Exception as e:
        issues.append(f"Hook ne répond pas: {e}")
    
    if issues:
        log(f"Problèmes détectés: {', '.join(issues)}", logging.WARNING)
        self._attempt_recovery()
```

---

## 📋 PLAN D'ACTION RECOMMANDÉ

### Phase 1 - Critiques (Impact immédiat) 🔴
1. ✅ Corriger les signaux Qt depuis threads (FAIT)
2. ⏳ Remplacer tous les `QMessageBox` par `SafeDialogs`
3. ⏳ Garantir `restoreOverrideCursor()` avec finally

**Temps estimé :** 30 minutes

### Phase 2 - Moyens (Stabilité) 🟡
4. Rendre le dialogue d'enregistrement vocal non-bloquant
5. Remplacer `time.sleep()` par `QTimer` dans TextInserter
6. Ajouter timeouts sur les dialogues

**Temps estimé :** 1-2 heures

### Phase 3 - Améliorations (UX) 🟢
7. Ajouter LoadingIndicator
8. Centraliser la gestion d'erreurs
9. Implémenter le RateLimiter
10. Améliorer le logging

**Temps estimé :** 2-3 heures

---

## 🧪 TESTS RECOMMANDÉS

### Test 1: Endurance du hotkey
- Lancer l'app
- Utiliser le raccourci 100+ fois en 10 minutes
- **Attendu :** Menu s'affiche à chaque fois

### Test 2: Stress API
- Faire 10 requêtes API rapidement
- **Attendu :** Pas de crash, rate limiter fonctionne

### Test 3: Erreurs réseau
- Couper internet pendant une requête
- **Attendu :** Message d'erreur clair, pas de freeze

### Test 4: Longue utilisation
- Laisser l'app tourner 8h+
- **Attendu :** Pas de fuite mémoire, tout fonctionne

---

## 📊 PRIORITÉS PAR IMPACT

| Problème | Impact | Difficulté | Priorité |
|----------|--------|------------|----------|
| Signaux depuis threads | 🔴 Critique | ✅ Fait | P0 |
| QMessageBox non thread-safe | 🔴 Élevé | 🟢 Facile | P1 |
| Curseur bloqué | 🟡 Moyen | 🟢 Facile | P1 |
| Rate limiter | 🟢 Bas | 🟢 Facile | P2 |
| Dialogue bloquant | 🟡 Moyen | 🟡 Moyen | P2 |
| time.sleep() | 🟡 Moyen | 🟡 Moyen | P3 |
| Loading indicator | 🟢 UX | 🟢 Facile | P3 |

---

## 🎯 CONCLUSION

**2 problèmes critiques sont déjà résolus ✅**

**Il reste 3 corrections simples prioritaires :**
1. Remplacer QMessageBox → SafeDialogs (10 min)
2. Ajouter finally pour restoreOverrideCursor (5 min)
3. Tester en conditions réelles (15 min)

**Total : ~30 minutes pour une app beaucoup plus stable !**
