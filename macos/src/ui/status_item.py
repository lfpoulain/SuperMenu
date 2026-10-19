"""AppKit menu-bar item, avoiding Qt's pre-macOS-27 clickCount path."""

import sys
import logging
from PySide6.QtCore import QObject, Signal, Slot, Qt

if sys.platform == "darwin":
    from AppKit import (
        NSStatusBar,
        NSVariableStatusItemLength,
        NSMenu,
        NSMenuItem,
        NSImage,
    )
    from Foundation import NSObject

    class SuperMenuStatusTarget(NSObject):
        def invoke_(self, sender):
            self.dispatch(int(sender.tag()))


class NativeStatusItem(QObject):
    activated = Signal(int)

    def __init__(self, icon_path, actions, parent=None):
        super().__init__(parent)
        self._callbacks = {}
        # Menu items by label, to show or hide one without rebuilding the menu.
        self._items = {}
        self._status_item = None
        self._target = SuperMenuStatusTarget.alloc().init()
        self._target.dispatch = self.activated.emit
        self.activated.connect(self._invoke, Qt.ConnectionType.QueuedConnection)
        self._menu = NSMenu.alloc().initWithTitle_("SuperMenu")
        self._menu.setAutoenablesItems_(False)
        for index, entry in enumerate(actions):
            if entry is None:
                self._menu.addItem_(NSMenuItem.separatorItem())
                continue
            label, callback = entry
            self._callbacks[index] = callback
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                label, "invoke:", ""
            )
            item.setTarget_(self._target)
            item.setTag_(index)
            self._menu.addItem_(item)
            self._items[label] = item
        self._status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        try:
            icon = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
            button = self._status_item.button()
            if icon is not None:
                icon.setSize_((18, 18))
                button.setImage_(icon)
            else:
                button.setTitle_("SuperMenu")
            button.setToolTip_("SuperMenu")
            self._status_item.setMenu_(self._menu)
        except Exception:
            self.hide()
            raise

    @Slot(int)
    def _invoke(self, index):
        if self._status_item is None:
            return
        try:
            self._callbacks[index]()
        except Exception:
            logging.getLogger("SuperMenu").exception(
                "Action de la barre des menus impossible"
            )

    def set_entry_visible(self, label, visible):
        """Show or hide one menu entry; an unknown label is ignored."""
        item = self._items.get(label)
        if item is not None:
            item.setHidden_(not visible)

    def hide(self):
        if self._status_item is not None:
            NSStatusBar.systemStatusBar().removeStatusItem_(self._status_item)
            self._status_item = None
