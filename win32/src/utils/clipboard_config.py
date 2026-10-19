"""Delays for Windows clipboard operations and simulated copy/paste shortcuts."""

CLIPBOARD_PASTE_DELAY = 0.3
CLIPBOARD_COPY_DELAY = 0.2
CLIPBOARD_RESTORE_DELAY = 0.2
# Remote desktop and virtual machine clients fetch the clipboard on demand,
# over the network, after the forwarded Ctrl+V: restoring too early pastes
# the previous clipboard content instead of the answer.
CLIPBOARD_REMOTE_RESTORE_DELAY = 1.5
