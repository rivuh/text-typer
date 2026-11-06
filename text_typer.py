"""Text Typer - paste text, press Type It, and it gets typed into the focused window.

Keeps plain formatting: spaces, tabs, line breaks, blank lines.
"""

import ctypes
import queue
import sys
import threading
import tkinter as tk
import unicodedata

import customtkinter as ctk
from pynput import keyboard

APP_NAME = "Text Typer"
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.VkKeyScanW.argtypes = [ctypes.c_wchar]
    _user32.VkKeyScanW.restype = ctypes.c_short
    _user32.GetKeyState.argtypes = [ctypes.c_int]
    _user32.GetKeyState.restype = ctypes.c_short

VK_CAPITAL = 0x14
# VkKeyScan modifier bits -> pynput keys
_MOD_KEYS = ((1, keyboard.Key.shift), (2, keyboard.Key.ctrl), (4, keyboard.Key.alt))


def strip_control_chars(text: str) -> tuple[str, int]:
    """Remove invisible control characters (keeps newline and tab). Returns (text, removed_count)."""
    kept = [ch for ch in text if ch in "\n\t" or unicodedata.category(ch) != "Cc"]
    return "".join(kept), len(text) - len(kept)


class TextTyperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("660x600")
        self.minsize(560, 500)

        self.kb = keyboard.Controller()
        self.stop_event = threading.Event()
        self.typing = False
        self.ui_queue: "queue.Queue[tuple]" = queue.Queue()

        self._build_ui()

        # Global Esc hotkey to stop typing, even when another window has focus.
        self.esc_listener = keyboard.Listener(on_press=self._on_global_key)
        self.esc_listener.daemon = True
        self.esc_listener.start()

        self.after(50, self._process_ui_queue)
        self.after(300, self._update_count)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        ctk.CTkLabel(header, text=APP_NAME, font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Paste text, press Type It, then click into the target window.",
            text_color=("gray35", "gray65"),
        ).pack(anchor="w")

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=16, pady=(6, 4))
        ctk.CTkButton(toolbar, text="Paste", width=80, command=self._paste).pack(side="left")
        ctk.CTkButton(
            toolbar, text="Clear", width=80, fg_color="gray40", hover_color="gray30", command=self._clear
        ).pack(side="left", padx=(8, 0))
        self.count_label = ctk.CTkLabel(toolbar, text="0 chars · 0 lines", text_color=("gray35", "gray65"))
        self.count_label.pack(side="right")

        # Text box
        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=13), wrap="none", undo=True)
        self.textbox.grid(row=2, column=0, sticky="nsew", padx=16, pady=4)

        # Settings
        settings = ctk.CTkFrame(self)
        settings.grid(row=3, column=0, sticky="ew", padx=16, pady=8)
        settings.grid_columnconfigure((1, 4), weight=1)

        ctk.CTkLabel(settings, text="Start delay").grid(row=0, column=0, padx=(12, 6), pady=(10, 4), sticky="w")
        self.delay_var = tk.IntVar(value=3)
        ctk.CTkSlider(
            settings, from_=0, to=10, number_of_steps=10, variable=self.delay_var,
            command=lambda v: self.delay_val.configure(text=f"{int(v)} s"),
        ).grid(row=0, column=1, sticky="ew", pady=(10, 4))
        self.delay_val = ctk.CTkLabel(settings, text="3 s", width=50)
        self.delay_val.grid(row=0, column=2, padx=(6, 12), pady=(10, 4))

        ctk.CTkLabel(settings, text="Speed").grid(row=0, column=3, padx=(0, 6), pady=(10, 4), sticky="w")
        self.speed_var = tk.IntVar(value=10)
        ctk.CTkSlider(
            settings, from_=0, to=100, number_of_steps=100, variable=self.speed_var,
            command=lambda v: self.speed_val.configure(text=f"{int(v)} ms"),
        ).grid(row=0, column=4, sticky="ew", pady=(10, 4))
        self.speed_val = ctk.CTkLabel(settings, text="10 ms", width=56)
        self.speed_val.grid(row=0, column=5, padx=(6, 12), pady=(10, 4))

        toggles = ctk.CTkFrame(settings, fg_color="transparent")
        toggles.grid(row=1, column=0, columnspan=6, sticky="ew", padx=12, pady=(4, 10))

        self.topmost_switch = ctk.CTkSwitch(toggles, text="Always on top", command=self._toggle_topmost)
        self.topmost_switch.pack(side="left")

        self.compat_switch = ctk.CTkSwitch(toggles, text="Compatibility mode")
        self.compat_switch.pack(side="left", padx=(16, 0))
        if not IS_WINDOWS:
            self.compat_switch.configure(state="disabled")

        theme = ctk.CTkSegmentedButton(
            toggles, values=["System", "Dark", "Light"], command=lambda m: ctk.set_appearance_mode(m)
        )
        theme.set("System")
        theme.pack(side="right")

        # Actions
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 6))
        actions.grid_columnconfigure(0, weight=1)
        self.type_btn = ctk.CTkButton(
            actions, text="Type It", height=40, font=ctk.CTkFont(size=15, weight="bold"), command=self._start
        )
        self.type_btn.grid(row=0, column=0, sticky="ew")
        self.stop_btn = ctk.CTkButton(
            actions, text="Stop", height=40, width=110, fg_color="#b33a3a", hover_color="#8f2e2e",
            state="disabled", command=self._stop,
        )
        self.stop_btn.grid(row=0, column=1, padx=(8, 0))

        # Status bar
        status = ctk.CTkFrame(self, fg_color="transparent")
        status.grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 4))
        status.grid_columnconfigure(1, weight=1)
        self.status_label = ctk.CTkLabel(status, text="Ready", width=170, anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.progress = ctk.CTkProgressBar(status)
        self.progress.set(0)
        self.progress.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkLabel(
            self,
            text=(
                "Press Esc anytime to stop. Compatibility mode: use for games, remote desktop and VMs.\n"
                "Auto-indenting editors (VS Code etc.) may double indentation."
            ),
            justify="left",
            text_color=("gray40", "gray60"),
            font=ctk.CTkFont(size=11),
        ).grid(row=6, column=0, sticky="w", padx=16, pady=(0, 10))

    # ------------------------------------------------------------ helpers
    def _get_text(self) -> str:
        return self.textbox.get("1.0", "end-1c").replace("\r\n", "\n").replace("\r", "\n")

    def _update_count(self):
        text = self._get_text()
        lines = text.count("\n") + 1 if text else 0
        self.count_label.configure(text=f"{len(text)} chars · {lines} lines")
        self.after(300, self._update_count)

    def _paste(self):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            self._set_status("Clipboard is empty")
            return
        self.textbox.insert("insert", clip)

    def _clear(self):
        self.textbox.delete("1.0", "end")

    def _toggle_topmost(self):
        self.attributes("-topmost", bool(self.topmost_switch.get()))

    def _set_status(self, text):
        self.status_label.configure(text=text)

    def _on_global_key(self, key):
        if key == keyboard.Key.esc and self.typing:
            self.stop_event.set()

    # ------------------------------------------------------------ typing
    def _start(self):
        text, removed = strip_control_chars(self._get_text())
        if not text:
            self._set_status("Nothing to type")
            return
        self.removed_count = removed
        self.compat = bool(self.compat_switch.get()) and IS_WINDOWS
        self.typing = True
        self.stop_event.clear()
        self.type_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.textbox.configure(state="disabled")
        self.progress.set(0)
        threading.Thread(
            target=self._worker,
            args=(text, int(self.delay_var.get()), int(self.speed_var.get())),
            daemon=True,
        ).start()

    def _stop(self):
        self.stop_event.set()

    def _worker(self, text, delay_s, speed_ms):
        post = self.ui_queue.put

        for remaining in range(delay_s, 0, -1):
            post(("status", f"Starting in {remaining}…"))
            if self.stop_event.wait(1):
                post(("done", "Stopped"))
                return

        total = len(text)
        step = max(1, total // 200)  # limit UI updates on long texts
        pause = speed_ms / 1000

        for i, ch in enumerate(text, 1):
            if self.stop_event.is_set():
                post(("done", f"Stopped at {i - 1} / {total}"))
                return
            self._type_char(ch)
            if i % step == 0 or i == total:
                post(("progress", i, total))
            if pause:
                self.stop_event.wait(pause)

        done = "Done"
        if self.removed_count:
            done += f" (skipped {self.removed_count} control char{'s' if self.removed_count != 1 else ''})"
        post(("done", done))

    def _tap(self, key):
        self.kb.press(key)
        self.kb.release(key)

    def _type_char(self, ch):
        if ch == "\n":
            self._tap(keyboard.Key.enter)
            return
        if ch == "\t":
            self._tap(keyboard.Key.tab)
            return

        if IS_WINDOWS and ord(ch) <= 0xFFFF:
            res = _user32.VkKeyScanW(ch)
            if res != -1:
                vk = res & 0xFF
                mods = (res >> 8) & 0xFF
                # Plain keys always go as real key presses; with compatibility mode on,
                # Shift / AltGr characters do too (instead of Unicode injection).
                if mods == 0 or (self.compat and mods & ~0x07 == 0):
                    caps_on = _user32.GetKeyState(VK_CAPITAL) & 1
                    if caps_on and ch.isalpha():
                        mods ^= 1  # Caps Lock flips the case, so flip Shift to compensate
                    held = [key for bit, key in _MOD_KEYS if mods & bit]
                    for key in held:
                        self.kb.press(key)
                    try:
                        self._tap(keyboard.KeyCode.from_vk(vk))
                    finally:
                        for key in reversed(held):
                            self.kb.release(key)
                    return

        # Everything else (accents, symbols, emoji, other alphabets) is sent as Unicode text.
        self.kb.type(ch)

    def _process_ui_queue(self):
        try:
            while True:
                msg = self.ui_queue.get_nowait()
                if msg[0] == "status":
                    self._set_status(msg[1])
                elif msg[0] == "progress":
                    _, i, total = msg
                    self._set_status(f"Typing… {i} / {total}")
                    self.progress.set(i / total)
                elif msg[0] == "done":
                    self._finish(msg[1])
        except queue.Empty:
            pass
        self.after(50, self._process_ui_queue)

    def _finish(self, status):
        self.typing = False
        self._set_status(status)
        self.type_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.textbox.configure(state="normal")

    def _on_close(self):
        self.stop_event.set()
        try:
            self.esc_listener.stop()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    TextTyperApp().mainloop()
