# update_modal.py — نافذة تحديث Waraqat الاحترافية
import os
import sys
import queue
import customtkinter as ctk
from PIL import Image
from auto_updater import download_and_install
from config import APP_VERSION

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")


class UpdateModal(ctk.CTkToplevel):
    """
    نافذة تحديث حديثة واحترافية متناسقة كلياً مع تصميم Waraqat
    تتضمن:
    - تفاصيل الإصدار الجديد وتغييراته (Changelog)
    - شريط تقدم مباشر مع النسبة المئوية
    - إمكانية التنزيل الذاتي والتثبيت التلقائي مع إعادة التشغيل
    """
    def __init__(self, parent, version_tag, download_url, release_notes=""):
        super().__init__(parent)
        self.parent = parent
        self.version_tag = version_tag
        self.download_url = download_url
        self.release_notes = release_notes or "تحسينات عامة في الأداء وإصلاحات لمشاكل الاستقرار."
        # Worker callbacks are pushed here and handled on the Tk main thread only.
        self._events = queue.Queue()

        self.title("تحديث ورقات | Waraqat Auto-Update")
        self.geometry("520x420")
        self.minsize(480, 380)
        self.resizable(False, False)

        # Set window icon
        ico_path = os.path.join(ASSETS_DIR, "waraqat_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        self.transient(parent)
        self.grab_set()

        self.build_ui()
        self.center_window()
        self._poll_job = self.after(100, self._poll_events)

    def center_window(self):
        self.update_idletasks()
        try:
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
            w, h = 520, 420
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"{w}x{h}+{max(x, 50)}+{max(y, 50)}")
        except Exception:
            pass

    def build_ui(self):
        # Outer Card Container
        card = ctk.CTkFrame(self, fg_color="#181B22", corner_radius=12, border_color="#334155", border_width=1)
        card.pack(fill="both", expand=True, padx=15, pady=15)

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
            font=("Segoe UI", 16, "bold"),
            text_color="#F8FAFC"
        )
        title.pack(anchor="w")

        sub = ctk.CTkLabel(
            title_box,
            text=f"الإصدار الحالي: v{APP_VERSION}  ←  الإصدار الجديد: {self.version_tag}",
            font=("Segoe UI", 11),
            text_color="#38BDF8"
        )
        sub.pack(anchor="w")

        # Release Notes Box
        notes_frame = ctk.CTkFrame(card, fg_color="#12151C", corner_radius=8, border_color="#252A36", border_width=1)
        notes_frame.pack(fill="both", expand=True, padx=16, pady=(5, 12))

        lbl_notes_title = ctk.CTkLabel(
            notes_frame,
            text="سجل التغييرات والميزات الجديدة | What's New:",
            font=("Segoe UI", 11, "bold"),
            text_color="#94A3B8"
        )
        lbl_notes_title.pack(anchor="w", padx=12, pady=(8, 4))

        self.notes_box = ctk.CTkTextbox(
            notes_frame,
            font=("Segoe UI", 11),
            fg_color="transparent",
            text_color="#E2E8F0",
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
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        )
        self.status_lbl.pack(side="left")

        self.pct_lbl = ctk.CTkLabel(
            status_row,
            text="",
            font=("Segoe UI", 11, "bold"),
            text_color="#38BDF8"
        )
        self.pct_lbl.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            height=8,
            progress_color="#059669",
            fg_color="#1E2433"
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        # Action Buttons
        self.btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=16, pady=(0, 16))

        self.btn_install = ctk.CTkButton(
            self.btn_frame,
            text="✓ تحديث وتثبيت الآن | Update & Install",
            height=38,
            font=("Segoe UI", 12, "bold"),
            fg_color="#4F46E5",
            hover_color="#4338CA",
            command=self.start_update
        )
        self.btn_install.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            self.btn_frame,
            text="لاحقاً | Later",
            width=100,
            height=38,
            font=("Segoe UI", 11),
            fg_color="#334155",
            hover_color="#475569",
            command=self.destroy
        )
        self.btn_cancel.pack(side="left")

    def start_update(self):
        if not self.download_url:
            self.status_lbl.configure(text="تعذر العثور على ملف التحديث في خوادم GitHub", text_color="#EF4444")
            return

        self.btn_install.configure(state="disabled", text="جاري التنزيل...")
        self.btn_cancel.configure(state="disabled")
        self.status_lbl.configure(text="جاري تنزيل النسخة الجديدة من GitHub...", text_color="#38BDF8")
        self.progress_bar.set(0)

        def _prog(pct):
            self._events.put(("progress", pct))

        def _done(success, msg):
            self._events.put(("done", (success, msg)))

        download_and_install(self.download_url, progress_callback=_prog, done_callback=_done)

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
        self.pct_lbl.configure(text=f"{pct}%")

    def _on_done(self, success, msg):
        if success:
            self.status_lbl.configure(
                text="✓ تم التنزيل! سيتم إغلاق التطبيق وتثبيت النسخة الجديدة تلقائياً...",
                text_color="#10B981"
            )
            self.pct_lbl.configure(text="100%")
            self.btn_install.configure(state="disabled")
            self.btn_cancel.configure(state="disabled")
            # Give the helper script time to start, then exit so it can
            # replace the locked exe and relaunch the new version.
            self.after(1200, self._exit_for_update)
        else:
            self.status_lbl.configure(text=f"فشل التحديث: {msg}", text_color="#EF4444")
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
