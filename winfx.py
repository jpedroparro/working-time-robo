"""Truques de janela do Windows: sempre no topo, fundo transparente e arrastar."""

import sys

import pygame


class WindowFX:
    """No-op fora do Windows; lá usa a API user32 via ctypes."""

    def __init__(self):
        self.ok = False
        self.transparent = False
        self._key = 0
        self._last_alpha = None
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            self._c, self._w = ctypes, wintypes
            self._u = ctypes.windll.user32
            self.hwnd = pygame.display.get_wm_info().get("window")
            if self.hwnd:
                self._declare_types()
                self.ok = True
        except Exception:
            self.ok = False

    def _declare_types(self):
        c, w, u = self._c, self._w, self._u
        u.GetWindowLongW.argtypes = [w.HWND, c.c_int]
        u.GetWindowLongW.restype = c.c_long
        u.SetWindowLongW.argtypes = [w.HWND, c.c_int, c.c_long]
        u.SetWindowLongW.restype = c.c_long
        u.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int,
                                   c.c_int, c.c_int, c.c_uint]
        u.SetLayeredWindowAttributes.argtypes = [w.HWND, c.c_uint32,
                                                 c.c_ubyte, c.c_uint32]
        u.MoveWindow.argtypes = [w.HWND, c.c_int, c.c_int, c.c_int, c.c_int,
                                 w.BOOL]
        u.GetCursorPos.argtypes = [c.POINTER(w.POINT)]
        u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]

    def keep_on_top(self):
        if self.ok:
            # HWND_TOPMOST = -1; flags: NOSIZE | NOMOVE
            self._u.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0003)

    def make_transparent(self, key):
        """Pinta de transparente tudo que tiver a cor `key` (layered window)."""
        if not self.ok:
            return
        style = self._u.GetWindowLongW(self.hwnd, -20)        # GWL_EXSTYLE
        self._u.SetWindowLongW(self.hwnd, -20, style | 0x00080000)  # LAYERED
        # NOSIZE | NOMOVE | NOZORDER | FRAMECHANGED
        self._u.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, 0x0027)
        self._key = key[0] | (key[1] << 8) | (key[2] << 16)
        self.transparent = True

    def set_alpha(self, alpha):
        if not (self.ok and self.transparent):
            return
        alpha = max(0, min(255, int(alpha)))
        if alpha == self._last_alpha:
            return
        self._last_alpha = alpha
        # LWA_COLORKEY | LWA_ALPHA
        self._u.SetLayeredWindowAttributes(self.hwnd, self._key, alpha, 0x3)

    def cursor(self):
        pt = self._w.POINT()
        self._u.GetCursorPos(self._c.byref(pt))
        return pt.x, pt.y

    def origin(self):
        rect = self._w.RECT()
        self._u.GetWindowRect(self.hwnd, self._c.byref(rect))
        return rect.left, rect.top

    def move(self, x, y, width, height):
        if self.ok:
            self._u.MoveWindow(self.hwnd, x, y, width, height, True)
