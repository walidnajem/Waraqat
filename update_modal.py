# update_modal.py — نافذة تحديث Waraqat الاحترافية
import os
import sys
import queue
import customtkinter as ctk
from PIL import Image
from auto_updater import download_and_install
from config import APP_VERSION
from md3 import COLORS as M3, RADIUS, font as ui_font, center_on_parent, WavyProgressBar

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


class UpdateResultModal(ctk.CTkToplevel):
    """Small theme-aware dialog used for update-check feedback (no download)."""

    def __init__(self, parent, title, message, kind="info"):
        super().__init__(parent)
        self.configure(fg_color=M3["surface"])
        self.parent = parent
        self.title(title)
        self.geometry("420x220")
        self.minsize(360, 180)
        self.resizable(False, False)

        ico_path = os.path.join(ASSETS_DIR, "waraqat_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.transient(parent)

        card = ctk.CTkFrame(
            self,
            fg_color=M3["surface_container_high"],
            corner_radius=RADIUS["xl"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        card.pack(fill="both", expand=True, padx=16, pady=16)

        color = M3["primary"] if kind == "info" else M3["warning"] if kind == "warn" else M3["error"]
        lbl_title = ctk.CTkLabel(card, text=title, font=ui_font(16, "bold"),
                                 text_color=color)
        lbl_title.pack(pady=(18, 6))

        lbl_msg = ctk.CTkLabel(card, text=message, font=ui_font(11),
                               text_color=M3["on_surface_variant"], wraplength=360,
                               justify="center")
        lbl_msg.pack(pady=(4, 12), padx=12)

        btn = ctk.CTkButton(
            card, text="OK | حسناً", width=130, height=40,
            corner_radius=RADIUS["pill"], font=ui_font(12, "bold"),
            fg_color=M3["primary"], hover_color=M3["primary_hover"],
            text_color=M3["on_primary"], border_width=0,
            command=self.destroy
        )
        btn.pack(pady=(4, 16))

        self.center_window()
        self.after(100, self._grab)

    def center_window(self):
        center_on_parent(self, self.parent, 420, 220)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:
            pass


class UpdateModal(ctk.CTkToplevel):
    """
    نافذة تحديث حديثة واحترافية متناسقة كلياً مع تصميم Waraqat
    تتضمن:
    - تفاصيل الإصدار الجديد وتغييراته (Changelog)
    - شريط تقدم مباشر مع النسبة المئوية
    - إمكانية التنزيل الذاتي والتثبيت التلقائي مع إعادة التشغيل
    """
    def __init__(self, parent, version_tag, download_url, release_notes="", sha256=None, skip_callback=None):
        super().__init__(parent)
        self.configure(fg_color=M3["surface"])
        self.parent = parent
        self.version_tag = version_tag
        self.download_url = download_url
        self.release_notes = release_notes or "تحسينات عامة في الأداء وإصلاحات لمشاكل الاستقرار."
        # Worker callbacks are pushed here and handled on the Tk main thread only.
        self.sha256 = sha256
        self.skip_callback = skip_callback
        self._events = queue.Queue()

        self.title("تحديث ورقات | Waraqat Auto-Update")
        self.geometry("520x500")
        self.minsize(500, 480)
        self.resizable(False, False)

        # Set window icon
        ico_path = os.path.join(ASSETS_DIR, "waraqat_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.transient(parent)

        self.build_ui()
        self.center_window()
        self.update_idletasks()
        try:
            self.grab_set()
        except Exception:
            pass
        self._poll_job = self.after(100, self._poll_events)

    def center_window(self):
        center_on_parent(self, self.parent, 520, 500)

    def build_ui(self):
        # Outer Card Container
        card = ctk.CTkFrame(
            self,
            fg_color=M3["surface_container_high"],
            corner_radius=RADIUS["xl"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Top Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 10))

        # Icon
        icon_path = os.path.join(ASSETS_DIR, "update.png")
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))
                lbl_icon = ctk.CTkLabel(header, text="", image=ctk_img)
                lbl_icon.pack(side="left", padx=(0, 12))
            except Exception:
                pass

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        title = ctk.CTkLabel(
            title_box,
            text="يتوفر إصدار جديد من ورقات!",
            font=ui_font(17, "bold"),
            text_color=M3["on_surface"]
        )
        title.pack(anchor="w")

        sub = ctk.CTkLabel(
            title_box,
            text=f"الإصدار الحالي: v{APP_VERSION}  ←  الإصدار الجديد: {self.version_tag}",
            font=ui_font(11),
            text_color=M3["primary"]
        )
        sub.pack(anchor="w")

        # Release Notes Box
        notes_frame = ctk.CTkFrame(
            card,
            fg_color=M3["surface_container_lowest"],
            corner_radius=RADIUS["md"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        notes_frame.pack(fill="both", expand=True, padx=16, pady=(5, 12))

        lbl_notes_title = ctk.CTkLabel(
            notes_frame,
            text="سجل التغييرات والميزات الجديدة | What's New:",
            font=ui_font(11, "bold"),
            text_color=M3["on_surface_variant"]
        )
        lbl_notes_title.pack(anchor="w", padx=12, pady=(8, 4))

        self.notes_box = ctk.CTkTextbox(
            notes_frame,
            font=ui_font(11),
            fg_color="transparent",
            text_color=M3["on_surface_variant"],
            wrap="word",
            border_width=0
        )
        self.notes_box.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.notes_box.insert("1.0", self.release_notes)
        self.notes_box.configure(state="disabled")

        # Status and Progress Bar Container
        self.progress_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=16, pady=(0, 10))

        status_row = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, 4))

        self.status_lbl = ctk.CTkLabel(
            status_row,
            text="جاهز للتنزيل والتثبيت مباشرة",
            font=ui_font(11),
            text_color=M3["on_surface_variant"]
        )
        self.status_lbl.pack(side="left")

        self.pct_lbl = ctk.CTkLabel(
            status_row,
            text="",
            font=ui_font(11, "bold"),
            text_color=M3["primary"]
        )
        self.pct_lbl.pack(side="right")

        self.progress_bar = WavyProgressBar(
            self.progress_frame,
            height=14,
            progress_color=M3["primary"],
            track_color=M3["outline_variant"],
            surface_color=M3["surface_container_high"],
            amplitude=2.4,
            wavelength=34,
            thickness=4.0,
            speed=40.0,
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        # Action Buttons
        self.btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        self.btn_install = ctk.CTkButton(
            self.btn_frame,
            text="✓ تحديث وتثبيت الآن | Update & Install",
            height=42,
            corner_radius=RADIUS["pill"],
            font=ui_font(12, "bold"),
            fg_color=M3["primary"],
            hover_color=M3["primary_hover"],
            text_color=M3["on_primary"],
            border_width=0,
            command=self.start_update
        )
        self.btn_install.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            self.btn_frame,
            text="لاحقاً | Later",
            width=105,
            height=42,
            corner_radius=RADIUS["pill"],
            font=ui_font(11),
            fg_color="transparent",
            hover_color=M3["primary_container"],
            text_color=M3["primary"],
            border_width=1,
            border_color=M3["outline"],
            command=self.destroy
        )
        self.btn_skip = ctk.CTkButton(
            self.btn_frame,
            text="تخطي | Skip",
            width=95,
            height=42,
            corner_radius=RADIUS["pill"],
            font=ui_font(11),
            fg_color="transparent",
            hover_color=M3["surface_container_highest"],
            text_color=M3["on_surface_variant"],
            border_width=0,
            command=self._skip
        )
        self.btn_skip.pack(side="left", padx=(0, 6))

        self.btn_cancel.pack(side="left")

    def start_update(self):
        if not self.download_url:
            self.status_lbl.configure(text="تعذر العثور على ملف التحديث في خوادم GitHub", text_color=M3["error"])
            return

        self.btn_install.configure(state="disabled", text="جاري التنزيل...")
        self.btn_cancel.configure(state="disabled")
        self.status_lbl.configure(text="جاري تنزيل النسخة الجديدة من GitHub...", text_color=M3["primary"])
        self.progress_bar.set(0)
        self.progress_bar.start()

        def _prog(pct):
            self._events.put(("progress", pct))

        def _done(success, msg):
            self._events.put(("done", (success, msg)))

        download_and_install(self.download_url, progress_callback=_prog, done_callback=_done,
                            expected_sha256=self.sha256)

    def _skip(self):
        if self.skip_callback:
            try:
                self.skip_callback(self.version_tag)
            except Exception:
                pass
        self.destroy()

    def _poll_events(self):
        """Drains worker events on the Tk main thread."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "progress":
                    self._on_prog(payload)
                elif kind == "done":
                    self._on_done(*payload)
        except queue.Empty:
            pass

        try:
            self._poll_job = self.after(100, self._poll_events)
        except Exception:
            pass

    def _on_prog(self, pct):
        self.progress_bar.set(pct / 100.0)
        self.progress_bar.start()
        self.pct_lbl.configure(text=f"{pct}%")

    def _on_done(self, success, msg):
        if success:
            self.progress_bar.set(1.0)
            self.progress_bar.stop()
            self.status_lbl.configure(
                text="✓ تم التنزيل! سيتم إغلاق التطبيق وتثبيت النسخة الجديدة تلقائياً...",
                text_color=M3["success"]
            )
            self.pct_lbl.configure(text="100%")
            self.btn_install.configure(state="disabled")
            self.btn_cancel.configure(state="disabled")
            # Give the helper script time to start, then exit so it can
            # replace the locked exe and relaunch the new version.
            self.after(1200, self._exit_for_update)
        else:
            self.progress_bar.stop()
            self.status_lbl.configure(text=f"فشل التحديث: {msg}", text_color=M3["error"])
            self.btn_install.configure(state="normal", text="إعادة المحاولة | Retry")
            self.btn_cancel.configure(state="normal")

    def _exit_for_update(self):
        """Closes the whole application so the updater can replace the exe."""
        try:
            self._poll_job and self.after_cancel(self._poll_job)
        except Exception:
            pass
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        try:
            self.parent.destroy()
        except Exception:
            pass