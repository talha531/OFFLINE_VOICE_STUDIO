"""Inline SVG icons (24x24, stroke based). No icon font or network request is needed."""

from __future__ import annotations

_PATHS: dict[str, str] = {
    "dashboard": '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
    "tts": '<path d="M2 10v3M6 6v11M10 3v18M14 8v7M18 5v13M22 10v3"/>',
    "document": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "library": '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>',
    "settings": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    "play": '<path d="M7 4.5v15l12-7.5z"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "alert": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "x-circle": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "check-circle": '<circle cx="12" cy="12" r="9"/><path d="M8 12.5l3 3 5-6"/>',
    "upload": '<path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
    "download": '<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9.5 12l2 2 3-3.5"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="10" y="10" width="4" height="4"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>',
    "sparkle": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>',
    "trash": '<path d="M4 7h16M10 3h4M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
    "star": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "folder": '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "database": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5"/>',
    "loader": '<path d="M12 3a9 9 0 1 0 9 9"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "edit": '<path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19z"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5"/>',
    "zap": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "wifi-off": '<path d="M3 3l18 18M5 12.5a10 10 0 0 1 4-2.3M12 17h.01M8.5 14.5a5 5 0 0 1 2.5-1.3M19 12.5a10 10 0 0 0-5-2.6M16 15a5 5 0 0 0-1.5-1"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "headphones": '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4" height="7" rx="1.5"/><rect x="17" y="14" width="4" height="7" rx="1.5"/>',
    "file-audio": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M10 17v-4l4-1v4"/>',
}

_LOGO = (
    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" '
    'stroke-linecap="round" aria-hidden="true"><path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/></svg>'
)


def icon(name: str, size: int | None = None, cls: str = "") -> str:
    """Return an inline SVG string for ``name`` (decorative, hidden from screen readers)."""
    body = _PATHS.get(name, _PATHS["info"])
    style = f' style="width:{size}px;height:{size}px"' if size else ""
    classes = f"vs-icon {cls}".strip()
    return (
        f'<svg class="{classes}"{style} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{body}</svg>'
    )


def logo() -> str:
    return _LOGO
