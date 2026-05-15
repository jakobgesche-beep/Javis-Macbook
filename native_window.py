"""
Natives macOS-Fenster mit WKWebView das das Flask-Dashboard einbettet.
Muss immer vom Main-Thread aufgerufen werden (macOS-Anforderung).
"""

from AppKit import (
    NSWindow, NSMakeRect, NSBackingStoreBuffered,
    NSViewWidthSizable, NSViewHeightSizable, NSApp,
)
from WebKit import WKWebView, WKWebViewConfiguration
from Foundation import NSURL, NSURLRequest

WINDOW_STYLE = 1 | 2 | 4 | 8   # titled | closable | miniaturizable | resizable
DASHBOARD_URL = "http://127.0.0.1:8080"

_window = None
_webview = None


def open_window():
    global _window, _webview

    if _window is not None:
        _window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)
        return

    _window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(100, 200, 1100, 760),
        WINDOW_STYLE,
        NSBackingStoreBuffered,
        False,
    )
    _window.setTitle_("MacBook Jarvis")
    _window.setMinSize_((900, 600))
    _window.setReleasedWhenClosed_(False)

    config = WKWebViewConfiguration.alloc().init()
    _webview = WKWebView.alloc().initWithFrame_configuration_(
        _window.contentView().bounds(), config
    )
    _webview.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)

    nsurl = NSURL.URLWithString_(DASHBOARD_URL)
    _webview.loadRequest_(NSURLRequest.requestWithURL_(nsurl))

    _window.contentView().addSubview_(_webview)
    _window.center()
    _window.makeKeyAndOrderFront_(None)
    NSApp.activateIgnoringOtherApps_(True)
