import logging
import time

import AppKit

log = logging.getLogger(__name__)

_ACTIVATE_DELAY = 0.05


def capture():
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    return workspace.frontmostApplication()


def restore(app):
    if app is None:
        return

    if app.isTerminated():
        log.info("Source app terminated, skipping focus restore")
        return

    result = app.activateWithOptions_(
        AppKit.NSApplicationActivateIgnoringOtherApps
    )
    if not result:
        log.warning("Failed to activate app: %s", app.localizedName())
        return

    time.sleep(_ACTIVATE_DELAY)
