import logging
import math
import threading
import time

import AppKit
import objc
import Quartz

log = logging.getLogger(__name__)

PANEL_SIZE = 240.0
BASE_RADIUS = 28.0
MAX_RADIUS = 65.0
N_POINTS = 64

_THEMES = {
    "dark": {
        "base_gray": 0.08,
        "spots": [(0.28, 0.30, -0.25, 0.30, 1.5)],
    },
    "light": {
        "base_gray": 0.88,
        "spots": [(0.72, 0.35, -0.25, 0.30, 1.5)],
    },
}


def _blob_points(cx, cy, radius, morph, t):
    points = []
    for i in range(N_POINTS):
        theta = 2 * math.pi * i / N_POINTS
        deform = (
            math.sin(3 * theta + t * 2.0) * 0.12
            + math.sin(5 * theta - t * 1.5) * 0.08
            + math.sin(7 * theta + t * 0.9) * 0.05
        )
        r = radius * (1.0 + deform * morph)
        points.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
    return points


def _smooth_closed_path(points):
    n = len(points)
    path = AppKit.NSBezierPath.bezierPath()
    path.moveToPoint_(AppKit.NSMakePoint(*points[0]))
    for i in range(n):
        p0 = points[(i - 1) % n]
        p1 = points[i]
        p2 = points[(i + 1) % n]
        p3 = points[(i + 2) % n]
        cp1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        cp2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        path.curveToPoint_controlPoint1_controlPoint2_(
            AppKit.NSMakePoint(*p2),
            AppKit.NSMakePoint(*cp1),
            AppKit.NSMakePoint(*cp2),
        )
    path.closePath()
    return path


class BlobView(AppKit.NSView):
    def initWithFrame_(self, frame):
        self = objc.super(BlobView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._amplitude = 0.0
        self._t = 0.0
        self._theme = _THEMES["dark"]
        return self

    def setTheme_(self, name):
        self._theme = _THEMES.get(name, _THEMES["dark"])

    def setAmplitude_(self, value):
        if value > self._amplitude:
            self._amplitude = 0.4 * value + 0.6 * self._amplitude
        else:
            self._amplitude = 0.08 * value + 0.92 * self._amplitude

    def setTime_(self, t):
        self._t = t

    def isFlipped(self):
        return False

    def isOpaque(self):
        return False

    def drawRect_(self, rect):
        AppKit.NSColor.clearColor().set()
        AppKit.NSRectFillUsingOperation(
            self.bounds(), AppKit.NSCompositingOperationClear
        )

        bounds = self.bounds()
        cx = bounds.size.width / 2
        cy = bounds.size.height / 2
        amp = self._amplitude
        t = self._t

        radius = BASE_RADIUS + (MAX_RADIUS - BASE_RADIUS) * amp
        morph = min(amp + 0.2, 1.0)

        pts = _blob_points(cx, cy, radius, morph, t)
        blob_path = _smooth_closed_path(pts)

        AppKit.NSGraphicsContext.saveGraphicsState()
        blob_path.addClip()

        theme = self._theme
        base_gray = theme["base_gray"]
        spots = theme["spots"]

        AppKit.NSColor.colorWithCalibratedWhite_alpha_(base_gray, 1.0).setFill()
        blob_path.fill()

        ctx = AppKit.NSGraphicsContext.currentContext().CGContext()
        colorspace = Quartz.CGColorSpaceCreateDeviceGray()
        for gray, alpha, dx, dy, spread in spots:
            gradient = Quartz.CGGradientCreateWithColorComponents(
                colorspace,
                [gray, alpha, gray, 0.0],
                [0.0, 1.0],
                2,
            )
            sx = cx + radius * dx
            sy = cy + radius * dy
            Quartz.CGContextDrawRadialGradient(
                ctx,
                gradient,
                Quartz.CGPointMake(sx, sy),
                0,
                Quartz.CGPointMake(sx, sy),
                radius * spread,
                Quartz.kCGGradientDrawsBeforeStartLocation,
            )

        AppKit.NSGraphicsContext.restoreGraphicsState()


def _make_panel(rect):
    panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        rect,
        AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
        AppKit.NSBackingStoreBuffered,
        False,
    )
    panel.setLevel_(AppKit.NSFloatingWindowLevel + 1)
    panel.setOpaque_(False)
    panel.setAlphaValue_(1.0)
    panel.setBackgroundColor_(AppKit.NSColor.clearColor())
    panel.setHasShadow_(False)
    panel.setIgnoresMouseEvents_(True)
    panel.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
        | AppKit.NSWindowCollectionBehaviorStationary
    )
    panel.setHidesOnDeactivate_(False)
    return panel


class AudioOverlay:
    def __init__(self, theme="dark"):
        self._panel = None
        self._blob_view = None
        self._timer = None
        self._amplitude = 0.0
        self._lock = threading.Lock()
        self._start_time = 0.0
        self._theme = theme
        self._mode = "recording"

    def set_theme(self, name):
        self._theme = name
        if self._blob_view is not None:
            self._blob_view.setTheme_(name)

    def set_mode(self, mode):
        self._mode = mode
        if self._timer is not None:
            self._timer.invalidate()
            fps = 15.0 if mode == "processing" else 60.0
            self._timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                1.0 / fps,
                True,
                lambda _: self._tick(),
            )

    def show(self):
        try:
            screen = AppKit.NSScreen.mainScreen()
            if screen is None:
                return
            sf = screen.frame()
            x = sf.origin.x + (sf.size.width - PANEL_SIZE) / 2
            y = sf.origin.y + (sf.size.height - PANEL_SIZE) / 2
            rect = AppKit.NSMakeRect(x, y, PANEL_SIZE, PANEL_SIZE)

            if self._panel is None:
                self._panel = _make_panel(rect)

                self._blob_view = BlobView.alloc().initWithFrame_(
                    AppKit.NSMakeRect(0, 0, PANEL_SIZE, PANEL_SIZE)
                )
                self._blob_view.setTheme_(self._theme)
                self._panel.setContentView_(self._blob_view)
            else:
                self._panel.setFrame_display_(rect, False)

            with self._lock:
                self._amplitude = 0.0
            self._mode = "recording"
            self._blob_view.setAmplitude_(0.0)
            self._start_time = time.monotonic()
            self._panel.orderFrontRegardless()

            if self._timer is not None:
                self._timer.invalidate()
            self._timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                1.0 / 60.0,
                True,
                lambda _: self._tick(),
            )
        except Exception:
            log.exception("overlay show failed")

    def hide(self):
        if self._timer is not None:
            self._timer.invalidate()
            self._timer = None
        if self._panel is not None:
            self._panel.orderOut_(None)

    def update_amplitude(self, value):
        with self._lock:
            self._amplitude = value

    def _tick(self):
        try:
            t = time.monotonic() - self._start_time
            if self._mode == "processing":
                amp = 0.15 + 0.10 * math.sin(t * 1.8)
                t = t * 0.5
            else:
                with self._lock:
                    amp = self._amplitude
            self._blob_view.setAmplitude_(amp)
            self._blob_view.setTime_(t)
            self._blob_view.setNeedsDisplay_(True)
        except Exception:
            log.exception("overlay tick failed")
