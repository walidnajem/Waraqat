import os
import queue
import threading
from auto_updater import check_for_update
from update_modal import UpdateModal
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from config import (
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    DEFAULT_DOWNLOAD_FOLDER,
    load_settings,
    save_settings
)
from site_detector import detect_site
from extractor import extract_files, extract_files_batch
from downloader import download_parallel
from utils import clean_filename
from notifications import notify_download_complete, notify_error

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

import sys

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Type badge colors
TYPE_COLORS = {
    "PDF": "#DC2626",       # Red
    "DOCX": "#2563EB",      # Blue
    "DOC": "#2563EB",       # Blue
    "GDRIVE": "#D97706",    # Amber
    "MEDIAFIRE": "#0891B2", # Cyan
    "PPTX": "#EA580C",      # Orange
    "PPT": "#EA580C",       # Orange
    "EPUB": "#9333EA",      # Purple
    "MEGA": "#D32F2F",      # Red (Mega brand)
    "DJVU": "#795548",      # Brown
    "ARCHIVE": "#FF6F00",   # Orange (Archive.org brand)
}


def load_icon_image(name, size=(18, 18)):
    """Loads a PNG from assets as CTkImage with high-DPI support."""
    path = os.path.join(ASSETS_DIR, f"{name}.png")
    if os.path.exists(path):
        try:
            img = Image.open(path)
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)
        except Exception:
            pass
    return None


class NewFolderModal(ctk.CTkToplevel):
    """
    A custom next-level modal window matching Waraqat design for creating
    and selecting a new dedicated download subfolder.
    """

    def __init__(self, parent, current_path, on_folder_created):
        super().__init__(parent)

        self.parent = parent
        self.on_folder_created = on_folder_created
        self.default_downloads = os.path.join(os.path.expanduser("~"), DEFAULT_DOWNLOAD_FOLDER)

        self.title("إنشاء مجلد جديد | Create New Folder")
        self.geometry("520x350")
        self.minsize(480, 320)
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

        # Location choice: "downloads" vs "current"
        self.base_choice_var = ctk.StringVar(value="downloads")
        self.current_path = current_path if os.path.exists(current_path) else self.default_downloads

        self.build_modal_ui()

        # Center on parent window
        self.center_window()
        self.entry.focus_set()

    def center_window(self):
        self.update_idletasks()
        try:
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
            w = 520
            h = 350
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"{w}x{h}+{max(x, 50)}+{max(y, 50)}")
        except Exception:
            pass

    def build_modal_ui(self):
        # Card container
        card = ctk.CTkFrame(self, fg_color="#181B22", corner_radius=12, border_color="#334155", border_width=1)
        card.pack(fill="both", expand=True, padx=15, pady=15)

        # Header with folder icon
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        folder_icon = load_icon_image("folder_new", (26, 26))
        if folder_icon:
            icon_lbl = ctk.CTkLabel(header_frame, text="", image=folder_icon)
            icon_lbl.pack(side="left", padx=(0, 10))

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left")

        title = ctk.CTkLabel(
            title_box,
            text="إنشاء مجلد جديد للتحميل | Create New Folder",
            font=("Segoe UI", 15, "bold"),
            text_color="#F8FAFC"
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="سيتم حفظ الملفات المحملة داخل هذا المجلد تلقائياً",
            font=("Segoe UI", 11),
            text_color="#94A3B8"
        )
        subtitle.pack(anchor="w")

        # Base directory option
        options_frame = ctk.CTkFrame(card, fg_color="#12151C", corner_radius=8)
        options_frame.pack(fill="x", padx=15, pady=(5, 10))

        radio_downloads = ctk.CTkRadioButton(
            options_frame,
            text="داخل مجلد التنزيلات الرئيسي (Downloads)",
            variable=self.base_choice_var,
            value="downloads",
            font=("Segoe UI", 11),
            command=self.update_preview
        )
        radio_downloads.pack(anchor="w", padx=12, pady=(8, 4))

        radio_current = ctk.CTkRadioButton(
            options_frame,
            text=f"داخل المجلد الحالي: {os.path.basename(self.current_path)}",
            variable=self.base_choice_var,
            value="current",
            font=("Segoe UI", 11),
            command=self.update_preview
        )
        radio_current.pack(anchor="w", padx=12, pady=(0, 8))

        # Folder Name Entry
        entry_label = ctk.CTkLabel(
            card,
            text="اسم المجلد الجديد | Folder Name:",
            font=("Segoe UI", 11, "bold"),
            text_color="#E2E8F0"
        )
        entry_label.pack(anchor="w", padx=15, pady=(2, 2))

        self.entry = ctk.CTkEntry(
            card,
            placeholder_text="مثال: روايات, امتحانات 2024, دروس الفيزياء...",
            height=38,
            font=("Segoe UI", 12),
            fg_color="#12151C",
            border_color="#475569"
        )
        self.entry.pack(fill="x", padx=15, pady=(0, 8))
        self.entry.bind("<KeyRelease>", self.update_preview)
        self.entry.bind("<Return>", lambda e: self.confirm_create())
        self.entry.bind("<Escape>", lambda e: self.destroy())

        # Live Path Preview Box
        self.preview_lbl = ctk.CTkLabel(
            card,
            text="مسار الحفظ النهائي: ...",
            font=("Consolas", 10),
            text_color="#38BDF8",
            wraplength=460,
            justify="left"
        )
        self.preview_lbl.pack(fill="x", padx=15, pady=(0, 12))

        # Action Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 12))

        confirm_btn = ctk.CTkButton(
            btn_frame,
            text="✓ إنشاء وتحديد المجلد | Create & Select",
            height=36,
            font=("Segoe UI", 12, "bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self.confirm_create
        )
        confirm_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="إلغاء | Cancel",
            width=100,
            height=36,
            font=("Segoe UI", 11),
            fg_color="#334155",
            hover_color="#475569",
            command=self.destroy
        )
        cancel_btn.pack(side="left")

        self.update_preview()

    def get_target_base(self):
        if self.base_choice_var.get() == "current" and os.path.exists(self.current_path):
            return self.current_path
        return self.default_downloads

    def update_preview(self, event=None):
        name = self.entry.get().strip()
        base = self.get_target_base()
        if name:
            cleaned = clean_filename(name)
            final_path = os.path.join(base, cleaned)
            self.preview_lbl.configure(text=f"مسار الحفظ: {final_path}")
        else:
            self.preview_lbl.configure(text=f"مسار الحفظ: {base}\\[اسم_المجلد]")

    def confirm_create(self):
        name = self.entry.get().strip()
        if not name:
            self.entry.configure(border_color="#EF4444")
            return

        cleaned = clean_filename(name)
        base = self.get_target_base()
        full_new_path = os.path.join(base, cleaned)

        try:
            os.makedirs(full_new_path, exist_ok=True)
            if self.on_folder_created:
                self.on_folder_created(full_new_path, cleaned)
            self.destroy()
        except Exception as e:
            self.preview_lbl.configure(text=f"خطأ في إنشاء المجلد: {str(e)}", text_color="#EF4444")


# -------------------------------------------------------------------
# Settings Modal – نافذة إعدادات عصرية ومتكاملة بمستوى احترافي
# -------------------------------------------------------------------
class SettingsModal(ctk.CTkToplevel):
    """
    نافذة إعدادات بتصميم عالمي حديث ومنظم في بطاقات:
    - مسار حفظ الملفات الافتراضي مع زر استعراض
    - عدد التنزيلات التزامنية (Threads) مع خيارات محسنة
    - مظهر التطبيق (Dark / Light / System) مع تطبيق فوري
    - خيارات الأتمتة: فتح المجلد تلقائياً بعد الانتهاء، وفحص التحديثات عند البدء
    """
    def __init__(self, parent, settings, on_save):
        super().__init__(parent)
        self.parent = parent
        self._settings = dict(settings)
        self._on_save = on_save

        self.title("الإعدادات | Settings")
        self.geometry("540x610")
        self.minsize(500, 560)
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

    def center_window(self):
        self.update_idletasks()
        try:
            pw = self.parent.winfo_width()
            ph = self.parent.winfo_height()
            px = self.parent.winfo_rootx()
            py = self.parent.winfo_rooty()
            w, h = 540, 610
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"{w}x{h}+{max(x, 50)}+{max(y, 50)}")
        except Exception:
            pass

    def build_ui(self):
        # Card container
        card = ctk.CTkFrame(self, fg_color="#181B22", corner_radius=12, border_color="#334155", border_width=1)
        card.pack(fill="both", expand=True, padx=15, pady=15)

        # Header with icon
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 12))

        settings_icon = load_icon_image("settings", (24, 24))
        if settings_icon:
            icon_lbl = ctk.CTkLabel(header, text="", image=settings_icon)
            icon_lbl.pack(side="left", padx=(0, 10))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left")

        title = ctk.CTkLabel(
            title_box,
            text="إعدادات التطبيق | Preferences",
            font=("Segoe UI", 15, "bold")
        )
        title.pack(anchor="w")

        sub = ctk.CTkLabel(
            title_box,
            text="تخصيص سلوك التحميل والمظهر العام لبرنامج ورقات",
            font=("Segoe UI", 11)
        )
        sub.pack(anchor="w")

        # Scrollable / Section Container
        content = ctk.CTkFrame(card, fg_color=("gray90", "#12151C"), corner_radius=10, border_color=("gray75", "#252A36"), border_width=1)
        content.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # --- Section 1: Save Path ---
        sec1 = ctk.CTkFrame(content, fg_color="transparent")
        sec1.pack(fill="x", padx=14, pady=(14, 8))

        ctk.CTkLabel(
            sec1,
            text="📁 مسار التنزيل الافتراضي | Default Download Location:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))

        path_row = ctk.CTkFrame(sec1, fg_color="transparent")
        path_row.pack(fill="x")

        self.path_entry = ctk.CTkEntry(
            path_row,
            height=34,
            font=("Segoe UI", 11),
            fg_color=("gray95", "#1A1F2C"),
            border_color=("gray70", "#334155")
        )
        self.path_entry.insert(0, self._settings.get("save_path", ""))
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_btn = ctk.CTkButton(
            path_row,
            text="استعراض...",
            width=85,
            height=34,
            font=("Segoe UI", 11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._browse_folder
        )
        browse_btn.pack(side="left")

        # --- Section 2: Concurrency & Speed ---
        sec2 = ctk.CTkFrame(content, fg_color="transparent")
        sec2.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(
            sec2,
            text="⚡ سرعة التنزيل والاتصالات المتزامنة | Concurrent Threads:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))

        threads_row = ctk.CTkFrame(sec2, fg_color="transparent")
        threads_row.pack(fill="x")

        self.threads_menu = ctk.CTkOptionMenu(
            threads_row,
            values=["2 ملفات (اتصال هادئ)", "3 ملفات", "5 ملفات (موصى به)", "8 ملفات (اتصال سريع)", "10 ملفات (فائق السرعة)"],
            width=220,
            height=32
        )
        curr_workers = self._settings.get("max_workers", 5)
        # Select matching menu value
        match_val = f"{curr_workers} ملفات (موصى به)" if curr_workers == 5 else f"{curr_workers} ملفات"
        for v in self.threads_menu._values:
            if str(curr_workers) in v:
                match_val = v
                break
        self.threads_menu.set(match_val)
        self.threads_menu.pack(side="left")

        timeout_row = ctk.CTkFrame(sec2, fg_color="transparent")
        timeout_row.pack(fill="x", pady=(6, 0))

        ctk.CTkLabel(
            timeout_row,
            text="مهلة القراءة | Read timeout:",
            font=("Segoe UI", 11)
        ).pack(side="left", padx=(0, 8))

        self.timeout_menu = ctk.CTkOptionMenu(
            timeout_row,
            values=["15 ثانية", "30 ثانية", "60 ثانية (موصى به)", "120 ثانية"],
            width=180,
            height=30
        )
        try:
            curr_timeout = int(self._settings.get("timeout", 60))
        except (TypeError, ValueError):
            curr_timeout = 60
        timeout_match = f"{curr_timeout} ثانية"
        if curr_timeout == 60:
            timeout_match = "60 ثانية (موصى به)"
        for tv in self.timeout_menu._values:
            if str(curr_timeout) in tv:
                timeout_match = tv
                break
        self.timeout_menu.set(timeout_match)
        self.timeout_menu.pack(side="left")

        # --- Section 3: Appearance & Theme ---
        sec3 = ctk.CTkFrame(content, fg_color="transparent")
        sec3.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(
            sec3,
            text="🎨 مظهر التطبيق | Theme:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))

        self.theme_menu = ctk.CTkOptionMenu(
            sec3,
            values=["Dark (الوضع الداكن)", "Light (الوضع الفاتح)", "System (مطابق للنظام)"],
            width=220,
            height=32
        )
        curr_theme = self._settings.get("theme", "Dark")
        for tv in self.theme_menu._values:
            if curr_theme.lower() in tv.lower():
                self.theme_menu.set(tv)
                break
        self.theme_menu.pack(anchor="w")

        # --- Section 4: Automation Toggles ---
        sec4 = ctk.CTkFrame(content, fg_color="transparent")
        sec4.pack(fill="x", padx=14, pady=(8, 14))

        ctk.CTkLabel(
            sec4,
            text="⚙️ سلوك التطبيق التلقائي | Automation Options:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        self.var_open_folder = ctk.BooleanVar(value=self._settings.get("open_folder_on_finish", True))
        cb_open = ctk.CTkCheckBox(
            sec4,
            text="فتح مجلد الحفظ في File Explorer تلقائياً عند انتهاء التحميل",
            variable=self.var_open_folder,
            font=("Segoe UI", 11),
            fg_color="#4F46E5",
            hover_color="#4338CA"
        )
        cb_open.pack(anchor="w", pady=(0, 4))

        self.var_auto_update = ctk.BooleanVar(value=self._settings.get("auto_check_updates", True))
        cb_update = ctk.CTkCheckBox(
            sec4,
            text="البحث عن تحديثات ورقات تلقائياً عند تشغيل البرنامج",
            variable=self.var_auto_update,
            font=("Segoe UI", 11),
            fg_color="#4F46E5",
            hover_color="#4338CA"
        )
        cb_update.pack(anchor="w", pady=(0, 4))

        self.var_notifications = ctk.BooleanVar(value=self._settings.get("notifications_enabled", True))
        cb_notify = ctk.CTkCheckBox(
            sec4,
            text="تفعيل إشعارات الويندوز (Toast Notifications) عند اكتمال التنزيل",
            variable=self.var_notifications,
            font=("Segoe UI", 11),
            fg_color="#4F46E5",
            hover_color="#4338CA"
        )
        cb_notify.pack(anchor="w")

        # --- Bottom Action Buttons ---
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(10, 16))

        save_btn = ctk.CTkButton(
            btn_row,
            text="✓ حفظ الإعدادات | Save Settings",
            height=38,
            font=("Segoe UI", 12, "bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self._save
        )
        save_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        cancel_btn = ctk.CTkButton(
            btn_row,
            text="إلغاء | Cancel",
            width=100,
            height=38,
            font=("Segoe UI", 11),
            fg_color="#475569",
            hover_color="#64748B",
            command=self.destroy
        )
        cancel_btn.pack(side="left")

    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.path_entry.get().strip() or self._settings.get("save_path", ""))
        if folder:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)

    def _save(self):
        new_path = self.path_entry.get().strip()
        if new_path:
            self._settings["save_path"] = new_path

        # Parse workers
        raw_worker = self.threads_menu.get().split()[0]
        try:
            self._settings["max_workers"] = int(raw_worker)
        except Exception:
            self._settings["max_workers"] = 5

        # Parse read timeout
        raw_timeout = self.timeout_menu.get().split()[0]
        try:
            self._settings["timeout"] = int(raw_timeout)
        except Exception:
            self._settings["timeout"] = 60

        # Parse theme
        raw_theme = self.theme_menu.get().split()[0]
        self._settings["theme"] = raw_theme
        ctk.set_appearance_mode(raw_theme)

        # Automation
        self._settings["open_folder_on_finish"] = self.var_open_folder.get()
        self._settings["auto_check_updates"] = self.var_auto_update.get()
        self._settings["notifications_enabled"] = self.var_notifications.get()

        self._on_save(self._settings)
        self.destroy()


class DownloadItem(ctk.CTkFrame):
    """
    Modern file item widget featuring:
    - Checkbox selection
    - File type badge with vibrant glow color
    - File title
    - Per-file interactive progress bar
    - Dynamic status indicator (Waiting, % Progress, Done, Skipped, Error)
    """
    def __init__(self, master, index, item, var):
        super().__init__(master, fg_color=("white", "#181B22"), corner_radius=8, border_color=("gray75", "#252A36"), border_width=1)
        self.pack(fill="x", padx=4, pady=3)
        self.index = index
        self.item = item
        self.var = var

        # Main top row container
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(6, 4))

        # Checkbox
        self.cb = ctk.CTkCheckBox(
            top_row,
            text="",
            variable=var,
            width=22,
            checkbox_width=18,
            checkbox_height=18,
            fg_color="#4F46E5",
            hover_color="#4338CA"
        )
        self.cb.pack(side="left", padx=(0, 6))

        # Type Badge
        raw_type = item.get("type", "PDF").upper()
        badge_color = TYPE_COLORS.get(raw_type, "#475569")
        self.badge = ctk.CTkLabel(
            top_row,
            text=raw_type,
            font=("Segoe UI", 10, "bold"),
            fg_color=badge_color,
            text_color="#FFFFFF",
            corner_radius=6,
            padx=8,
            pady=2
        )
        self.badge.pack(side="left", padx=(0, 10))

        # File Title
        title_text = f"{index}. {item.get('title', 'Document')}"
        self.title_lbl = ctk.CTkLabel(
            top_row,
            text=title_text,
            font=("Segoe UI", 11),
            text_color=("gray10", "#F1F5F9"),
            anchor="w"
        )
        self.title_lbl.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Status text on the right
        self.status_lbl = ctk.CTkLabel(
            top_row,
            text="Ready | جاهز",
            font=("Segoe UI", 10),
            text_color=("gray40", "#64748B"),
            width=85,
            anchor="e"
        )
        self.status_lbl.pack(side="right")

        # Per-file sleek progress bar (visible when downloading or completed)
        self.progress_bar = ctk.CTkProgressBar(
            self,
            height=4,
            progress_color="#6366F1",
            fg_color=("gray80", "#1E2433"),
            corner_radius=2
        )
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 6))
        self.progress_bar.set(0)

    def update_state(self, status, percent=0.0):
        if status == "downloading":
            self.configure(border_color="#4F46E5", fg_color=("#EEF2FF", "#1A1F2C"))
            self.status_lbl.configure(text=f"{int(percent)}%", text_color=("#2563EB", "#38BDF8"))
            self.progress_bar.configure(progress_color="#38BDF8")
            self.progress_bar.set(percent / 100.0)
        elif status == "progress":
            self.status_lbl.configure(text=f"{int(percent)}%", text_color=("#2563EB", "#38BDF8"))
            self.progress_bar.set(percent / 100.0)
        elif status == "success":
            self.configure(border_color="#059669", fg_color=("#ECFDF5", "#14231E"))
            self.status_lbl.configure(text="Completed ✓", text_color="#059669")
            self.progress_bar.configure(progress_color="#10B981")
            self.progress_bar.set(1.0)
        elif status == "skip":
            self.configure(border_color=("gray75", "#334155"), fg_color=("gray95", "#161922"))
            self.status_lbl.configure(text="Exists (Skip)", text_color=("gray50", "#94A3B8"))
            self.progress_bar.set(1.0)
            self.progress_bar.configure(progress_color="#475569")
        elif status == "failed":
            self.configure(border_color="#DC2626", fg_color=("#FEF2F2", "#241416"))
            self.status_lbl.configure(text="Failed ✗", text_color="#DC2626")
            self.progress_bar.configure(progress_color="#EF4444")
        elif status == "cancelled":
            self.status_lbl.configure(text="Cancelled", text_color="#D97706")
            self.progress_bar.configure(progress_color="#F59E0B")
        elif status == "retry":
            self.status_lbl.configure(text="Retrying...", text_color="#D97706")



class App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1020x880")
        self.minsize(880, 720)

        # Set official Waraqat window icon
        ico_path = os.path.join(ASSETS_DIR, "waraqat_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # Load settings
        self.settings = load_settings()
        self.selected_save_path = self.settings.get("save_path")
        if not self.selected_save_path or not os.path.exists(self.selected_save_path):
            self.selected_save_path = os.path.join(os.path.expanduser("~"), DEFAULT_DOWNLOAD_FOLDER)

        # Apply saved appearance mode
        saved_theme = self.settings.get("theme", "Dark")
        try:
            ctk.set_appearance_mode(saved_theme)
        except Exception:
            pass

        self.files = []
        self.checkbox_vars = []
        self.event_queue = queue.Queue()
        self.is_working = False
        self.cancel_event = threading.Event()

        # Cache button icons
        self.icon_search = load_icon_image("search", (16, 16))
        self.icon_download = load_icon_image("download", (16, 16))
        self.icon_folder_new = load_icon_image("folder_new", (16, 16))
        self.icon_folder_browse = load_icon_image("folder_browse", (16, 16))
        self.icon_folder_open = load_icon_image("folder_open", (16, 16))
        self.icon_cancel = load_icon_image("cancel", (16, 16))
        self.icon_settings = load_icon_image("settings", (16, 16))
        self.icon_update = load_icon_image("update", (16, 16))
        self.icon_sun = load_icon_image("sun", (18, 18))
        self.icon_moon = load_icon_image("moon", (18, 18))

        self.download_item_widgets = {}  # Map index -> DownloadItem widget
        self.file_vars = {}  # Map 0-based orig_idx -> BooleanVar
        self._displayed_indices = []  # List of visible 0-based indices

        # Filter state
        self.filter_entry = None  # Set in build_ui
        self.active_type_filters = set()  # empty = all types
        self.type_filter_buttons = {}  # type_name -> button widget

        self.build_ui()
        # بعد بناء الواجهة، نستدعي فحص التحديثات تلقائيًا
        self.after_ui_build()
        self.after(50, self.process_events)

    def after_ui_build(self):
        """Called after the UI is constructed.
        Initiates an asynchronous check for new releases in the background if enabled in settings.
        """
        if not self.settings.get("auto_check_updates", True):
            return

        def _callback(latest_tag, download_url, release_notes=""):
            self.event_queue.put({
                "type": "update_result",
                "latest_tag": latest_tag,
                "download_url": download_url,
                "release_notes": release_notes,
                "manual": False,
            })

        check_for_update(_callback)

    def manual_check_updates(self):
        """Triggered manually by user clicking 'Check for Updates' button."""
        self.update_btn.configure(state="disabled", text="جاري الفحص...")
        self.log("[*] Checking GitHub repository for latest updates...")

        def _callback(latest_tag, download_url, release_notes=""):
            self.event_queue.put({
                "type": "update_result",
                "latest_tag": latest_tag,
                "download_url": download_url,
                "release_notes": release_notes,
                "manual": True,
            })

        check_for_update(_callback)

    def build_ui(self):
        # ----------------------------------
        # Top Brand Header
        # ----------------------------------
        header_card = ctk.CTkFrame(self, fg_color="transparent")
        header_card.pack(fill="x", padx=25, pady=(15, 8))

        logo_img = load_icon_image("logo", (42, 42))
        if logo_img:
            logo_label = ctk.CTkLabel(header_card, text="", image=logo_img)
            logo_label.pack(side="left", padx=(0, 14))

        titles_box = ctk.CTkFrame(header_card, fg_color="transparent")
        titles_box.pack(side="left")

        app_title = ctk.CTkLabel(
            titles_box,
            text=APP_NAME,
            font=("Segoe UI", 24, "bold")
        )
        app_title.pack(anchor="w")

        app_sub = ctk.CTkLabel(
            titles_box,
            text=APP_SUBTITLE,
            font=("Segoe UI", 12),
            text_color=("gray40", "#94A3B8")
        )
        app_sub.pack(anchor="w")

        # Version Pill Badge
        version_pill = ctk.CTkLabel(
            header_card,
            text=f"v{APP_VERSION}",
            font=("Segoe UI", 11, "bold"),
            fg_color=("gray85", "#1E293B"),
            text_color=("#2563EB", "#38BDF8"),
            corner_radius=12,
            padx=12,
            pady=4
        )
        version_pill.pack(side="right", padx=(8, 0))

        # Settings Button
        settings_btn = ctk.CTkButton(
            header_card,
            text="الإعدادات | Settings",
            image=self.icon_settings,
            font=("Segoe UI", 11),
            width=130,
            height=32,
            fg_color=("gray85", "#1E222B"),
            hover_color=("gray75", "#2A303C"),
            border_color=("gray70", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            border_width=1,
            command=self.open_settings_dialog
        )
        settings_btn.pack(side="right", padx=(6, 0))

        # Check Updates Button
        self.update_btn = ctk.CTkButton(
            header_card,
            text="فحص التحديثات | Updates",
            image=self.icon_update,
            font=("Segoe UI", 11),
            width=150,
            height=32,
            fg_color=("gray85", "#1E222B"),
            hover_color=("gray75", "#2A303C"),
            border_color=("gray70", "#334155"),
            text_color=("gray10", "#F8FAFC"),
            border_width=1,
            command=self.manual_check_updates
        )
        self.update_btn.pack(side="right", padx=(6, 0))

        # Sun / Moon Quick Theme Toggle Button
        curr_mode = ctk.get_appearance_mode().lower()
        theme_icon = self.icon_sun if curr_mode == "dark" else self.icon_moon
        self.theme_btn = ctk.CTkButton(
            header_card,
            text="",
            image=theme_icon,
            width=36,
            height=32,
            fg_color=("gray85", "#1E222B"),
            hover_color=("gray75", "#2A303C"),
            border_color=("gray70", "#334155"),
            border_width=1,
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="right")

        # ----------------------------------
        # Card 1: Input URL Tabs
        # ----------------------------------
        self.tabview = ctk.CTkTabview(
            self,
            height=125,
            corner_radius=10,
            fg_color=("gray90", "#1E222B"),
            segmented_button_fg_color=("gray80", "#12151C"),
            segmented_button_selected_color="#4F46E5",
            segmented_button_selected_hover_color="#4338CA"
        )
        self.tabview.pack(fill="x", padx=25, pady=(0, 8))

        self.tab_single = self.tabview.add("Single URL | صفحة واحدة")
        self.tab_batch = self.tabview.add("Batch URLs | صفحات متعددة")

        # Single Tab Entry
        self.url_entry = ctk.CTkEntry(
            self.tab_single,
            placeholder_text="https://example.com/books-or-lessons-page",
            height=38,
            font=("Segoe UI", 12),
            fg_color=("white", "#12151C"),
            border_color=("gray70", "#334155"),
            border_width=1
        )
        self.url_entry.pack(fill="x", padx=8, pady=8)

        # Batch Tab Textbox
        self.batch_textbox = ctk.CTkTextbox(
            self.tab_batch,
            height=65,
            font=("Consolas", 11),
            fg_color=("white", "#12151C"),
            border_color=("gray70", "#334155"),
            border_width=1
        )
        self.batch_textbox.pack(fill="both", expand=True, padx=8, pady=4)
        self.batch_textbox.insert("1.0", "# Paste multiple URLs (one per line) | الصق الروابط هنا (رابط في كل سطر)\n")

        # ----------------------------------
        # Card 2: Save Destination & Folder Tools
        # ----------------------------------
        folder_card = ctk.CTkFrame(self, corner_radius=10, fg_color=("gray90", "#1E222B"), border_color=("gray75", "#334155"), border_width=1)
        folder_card.pack(fill="x", padx=25, pady=(0, 8))

        folder_inner = ctk.CTkFrame(folder_card, fg_color="transparent")
        folder_inner.pack(fill="x", padx=12, pady=10)

        folder_label = ctk.CTkLabel(
            folder_inner,
            text="Save Location | مجلد الحفظ:",
            font=("Segoe UI", 12, "bold")
        )
        folder_label.pack(side="left", padx=(0, 10))

        self.folder_entry = ctk.CTkEntry(
            folder_inner,
            height=34,
            font=("Segoe UI", 11),
            fg_color=("white", "#12151C"),
            border_color=("gray70", "#334155")
        )
        self.folder_entry.insert(0, self.selected_save_path)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        # + New Folder Button
        self.new_folder_btn = ctk.CTkButton(
            folder_inner,
            text="New Folder | مجلد جديد",
            image=self.icon_folder_new,
            width=135,
            height=34,
            font=("Segoe UI", 11, "bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.open_new_folder_dialog
        )
        self.new_folder_btn.pack(side="left", padx=(0, 6))

        # Browse Button
        self.browse_btn = ctk.CTkButton(
            folder_inner,
            text="Browse | استعراض",
            image=self.icon_folder_browse,
            width=115,
            height=34,
            font=("Segoe UI", 11),
            fg_color=("gray75", "#334155"),
            hover_color=("gray65", "#475569"),
            text_color=("gray10", "white"),
            command=self.browse_folder
        )
        self.browse_btn.pack(side="left", padx=(0, 6))

        # Open in Explorer Button
        self.open_folder_btn = ctk.CTkButton(
            folder_inner,
            text="Open | فتح",
            image=self.icon_folder_open,
            width=85,
            height=34,
            font=("Segoe UI", 11),
            fg_color=("gray80", "#1E293B"),
            hover_color=("gray70", "#334155"),
            text_color=("gray10", "white"),
            command=self.open_destination_folder
        )
        self.open_folder_btn.pack(side="left")

        # ----------------------------------
        # Card 3: Status & Concurrency Bar
        # ----------------------------------
        status_bar = ctk.CTkFrame(self, corner_radius=8, fg_color=("gray85", "#161922"))
        status_bar.pack(fill="x", padx=25, pady=(0, 8))

        self.site_label = ctk.CTkLabel(
            status_bar,
            text="Domain | الموقع: -",
            font=("Segoe UI", 12),
            text_color=("gray30", "#94A3B8")
        )
        self.site_label.pack(side="left", padx=14, pady=6)

        self.files_label = ctk.CTkLabel(
            status_bar,
            text="Files | الملفات المكتشفة: 0",
            font=("Segoe UI", 12, "bold"),
            text_color=("#0284C7", "#38BDF8")
        )
        self.files_label.pack(side="left", padx=20, pady=6)

        # Concurrency selector
        threads_label = ctk.CTkLabel(
            status_bar,
            text="Threads | التنزيلات التزامنية:",
            font=("Segoe UI", 12),
            text_color=("gray30", "#94A3B8")
        )
        threads_label.pack(side="right", padx=(5, 8))

        current_workers = str(self.settings.get("max_workers", 5))
        self.threads_menu = ctk.CTkOptionMenu(
            status_bar,
            values=["2", "3", "5", "8", "10"],
            width=70,
            height=28,
            fg_color=("gray75", "#334155"),
            button_color=("gray65", "#475569"),
            button_hover_color=("gray55", "#64748B"),
            command=self.on_threads_change
        )
        self.threads_menu.set(current_workers)
        self.threads_menu.pack(side="right", padx=(0, 12))

        # ----------------------------------
        # Card 4: Action Triggers (Analyze, Download, Cancel)
        # ----------------------------------
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(fill="x", padx=25, pady=(0, 8))

        # Analyze Button
        self.analyze_btn = ctk.CTkButton(
            actions_frame,
            text="Analyze | فحص الروابط",
            image=self.icon_search,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#4F46E5",
            hover_color="#4338CA",
            command=self.analyze
        )
        self.analyze_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Download Selected Button
        self.download_btn = ctk.CTkButton(
            actions_frame,
            text="Download Selected | بدء تنزيل المحدد",
            image=self.icon_download,
            height=40,
            font=("Segoe UI", 13, "bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self.start_download
        )
        self.download_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Cancel Button
        self.cancel_btn = ctk.CTkButton(
            actions_frame,
            text="Cancel | الغاء",
            image=self.icon_cancel,
            width=110,
            height=40,
            font=("Segoe UI", 12, "bold"),
            fg_color="#DC2626",
            hover_color="#B91C1C",
            state="disabled",
            command=self.cancel_download
        )
        self.cancel_btn.pack(side="left")

        # ----------------------------------
        # Card 5: Files Checklist Frame
        # ----------------------------------
        list_container = ctk.CTkFrame(self, corner_radius=10, fg_color=("gray90", "#1E222B"), border_color=("gray75", "#334155"), border_width=1)
        list_container.pack(fill="x", padx=25, pady=(0, 8))

        list_header = ctk.CTkFrame(list_container, fg_color="transparent")
        list_header.pack(fill="x", padx=12, pady=(8, 4))

        list_title = ctk.CTkLabel(
            list_header,
            text="Discovered Files | قائمة الملفات المكتشفة:",
            font=("Segoe UI", 12, "bold")
        )
        list_title.pack(side="left")

        self.btn_deselect_all = ctk.CTkButton(
            list_header,
            text="Deselect All | الغاء التحديد",
            width=125,
            height=26,
            font=("Segoe UI", 11),
            fg_color=("gray75", "#334155"),
            hover_color=("gray65", "#475569"),
            text_color=("gray10", "white"),
            command=self.deselect_all_files
        )
        self.btn_deselect_all.pack(side="right", padx=(6, 0))

        self.btn_select_all = ctk.CTkButton(
            list_header,
            text="Select All | تحديد الكل",
            width=110,
            height=26,
            font=("Segoe UI", 11),
            fg_color=("gray75", "#334155"),
            hover_color=("gray65", "#475569"),
            text_color=("gray10", "white"),
            command=self.select_all_files
        )
        self.btn_select_all.pack(side="right")

        # ----------------------------------
        # Filter Bar (search + type pill toggles)
        # ----------------------------------
        filter_bar = ctk.CTkFrame(list_container, fg_color="transparent")
        filter_bar.pack(fill="x", padx=12, pady=(2, 4))

        self.filter_entry = ctk.CTkEntry(
            filter_bar,
            placeholder_text="Search files... | بحث في الملفات...",
            width=260,
            height=30,
            font=("Segoe UI", 11),
            fg_color=("white", "#12151C"),
            border_color=("gray70", "#334155"),
            text_color=("gray10", "#F1F5F9"),
            placeholder_text_color=("gray50", "#64748B"),
            corner_radius=6
        )
        self.filter_entry.pack(side="left", padx=(0, 10))
        self.filter_entry.bind("<KeyRelease>", self.filter_files)

        # Type pill toggle buttons
        pill_types = [("All | الكل", "ALL"), ("PDF", "PDF"), ("DOCX", "DOCX"),
                      ("PPTX", "PPTX"), ("GDRIVE", "GDRIVE"), ("EPUB", "EPUB")]
        inactive_fg = ("gray75", "#334155")
        inactive_hover = ("gray65", "#475569")
        inactive_text = ("gray10", "white")

        self.type_filter_buttons = {}
        for label, type_key in pill_types:
            btn = ctk.CTkButton(
                filter_bar,
                text=label,
                width=60 if type_key != "ALL" else 75,
                height=26,
                font=("Segoe UI", 10, "bold"),
                fg_color=inactive_fg,
                hover_color=inactive_hover,
                text_color=inactive_text,
                corner_radius=12,
                command=lambda tk=type_key: self._toggle_type_filter(tk)
            )
            btn.pack(side="left", padx=2)
            self.type_filter_buttons[type_key] = btn

        self.scroll_files_frame = ctk.CTkScrollableFrame(list_container, height=220, fg_color=("white", "#12151C"))
        self.scroll_files_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.placeholder_label = ctk.CTkLabel(
            self.scroll_files_frame,
            text="No files scanned yet. Click 'Analyze' to scan page(s). | لم يتم فحص اي روابط بعد.",
            text_color=("gray50", "#64748B")
        )
        self.placeholder_label.pack(pady=20)

        # ----------------------------------
        # Card 6: Progress Bar & Percentage
        # ----------------------------------
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=25, pady=(2, 4))

        self.progress = ctk.CTkProgressBar(
            progress_frame,
            height=10,
            progress_color="#10B981",
            fg_color=("gray80", "#1E293B")
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="0%",
            font=("Segoe UI", 11, "bold"),
            width=45,
            text_color="#10B981"
        )
        self.progress_label.pack(side="right")

        # ----------------------------------
        # Card 7: Sleek Console Log Box
        # ----------------------------------
        self.log_box = ctk.CTkTextbox(
            self,
            font=("Consolas", 11),
            wrap="word",
            fg_color=("white", "#12151C"),
            border_color=("gray70", "#334155"),
            text_color=("gray10", "#E2E8F0"),
            border_width=1,
            corner_radius=10
        )
        self.log_box.pack(fill="both", expand=True, padx=25, pady=(0, 15))

    # ----------------------------------
    # Settings & Folder Operations
    # ----------------------------------
    def toggle_theme(self):
        """Toggles between Dark and Light mode with Sun / Moon icon transition."""
        curr = ctk.get_appearance_mode().lower()
        if curr == "dark":
            ctk.set_appearance_mode("Light")
            self.settings["theme"] = "Light"
            if self.icon_moon:
                self.theme_btn.configure(image=self.icon_moon)
        else:
            ctk.set_appearance_mode("Dark")
            self.settings["theme"] = "Dark"
            if self.icon_sun:
                self.theme_btn.configure(image=self.icon_sun)
        save_settings(self.settings)

    def open_settings_dialog(self):
        """Opens modern Settings modal dialog."""
        SettingsModal(self, self.settings, self._on_settings_saved)

    def _on_settings_saved(self, new_settings):
        """Callback when settings are saved."""
        self.settings = new_settings
        save_settings(self.settings)
        if "save_path" in new_settings:
            self.selected_save_path = new_settings["save_path"]
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, self.selected_save_path)
        if "max_workers" in new_settings:
            self.threads_menu.set(str(new_settings["max_workers"]))
        self.log(f"[SETTINGS] Saved settings successfully: {new_settings}")

    def open_new_folder_dialog(self):
        """Opens the modern custom Waraqat New Folder modal dialog."""
        current_path = self.folder_entry.get().strip() or self.selected_save_path
        NewFolderModal(self, current_path, self._on_new_folder_created)

    def _on_new_folder_created(self, full_new_path, folder_name):
        """Callback when a new folder is created in the modal."""
        self.selected_save_path = full_new_path
        self.folder_entry.delete(0, "end")
        self.folder_entry.insert(0, full_new_path)
        self.settings["save_path"] = full_new_path
        save_settings(self.settings)

        self.log("=" * 45)
        self.log(f"[FOLDER] Created and selected new folder: {folder_name}")
        self.log(f"[FOLDER] Full path: {full_new_path}")
        self.log("=" * 45)

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.selected_save_path)
        if folder:
            self.selected_save_path = folder
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)
            self.settings["save_path"] = folder
            save_settings(self.settings)
            self.log(f"[FOLDER] Save location set to: {folder}")

    def open_destination_folder(self):
        raw_target = self.folder_entry.get().strip() or self.selected_save_path
        if not os.path.isabs(raw_target):
            raw_target = os.path.join(os.path.expanduser("~"), DEFAULT_DOWNLOAD_FOLDER, raw_target)

        target = os.path.abspath(raw_target)
        if not os.path.exists(target):
            try:
                os.makedirs(target, exist_ok=True)
            except Exception:
                pass
        try:
            os.startfile(target)
            self.log(f"[FOLDER] Opened folder in File Explorer: {target}")
        except Exception as e:
            self.log(f"[ERROR] Could not open folder: {str(e)}")

    def on_threads_change(self, value):
        try:
            self.settings["max_workers"] = int(value)
            save_settings(self.settings)
            self.log(f"[SETTINGS] Max concurrent threads set to: {value}")
        except Exception:
            pass

    # ----------------------------------
    # Checklist Management with Color Badges & Per-file Widgets
    # ----------------------------------
    def update_file_checklist(self, files):
        for widget in self.scroll_files_frame.winfo_children():
            widget.destroy()

        self.checkbox_vars = []
        self.download_item_widgets = {}
        self.file_vars = {i: ctk.BooleanVar(value=True) for i in range(len(files))}
        self._displayed_indices = list(range(len(files)))

        # Reset filter bar
        if self.filter_entry is not None:
            self.filter_entry.delete(0, "end")
        self.active_type_filters = set()
        self._refresh_pill_styles()

        if not files:
            lbl = ctk.CTkLabel(
                self.scroll_files_frame,
                text="No files found in scanned page(s). | لم يتم العثور على ملفات.",
                text_color="#64748B"
            )
            lbl.pack(pady=20)
            return

        for i, item in enumerate(files, start=1):
            var = self.file_vars[i - 1]
            self.checkbox_vars.append(var)

            # Create interactive DownloadItem widget
            item_widget = DownloadItem(self.scroll_files_frame, i, item, var)
            self.download_item_widgets[i] = item_widget

    def _toggle_type_filter(self, type_key):
        """Toggle a type filter pill. 'ALL' clears all filters."""
        if type_key == "ALL":
            self.active_type_filters = set()
        else:
            if type_key in self.active_type_filters:
                self.active_type_filters.discard(type_key)
            else:
                self.active_type_filters.add(type_key)
        self._refresh_pill_styles()
        self.filter_files()

    def _refresh_pill_styles(self):
        """Update pill button colors based on active_type_filters."""
        inactive_fg = ("gray75", "#334155")
        inactive_text = ("gray10", "white")
        for type_key, btn in self.type_filter_buttons.items():
            if type_key == "ALL":
                if not self.active_type_filters:
                    btn.configure(fg_color="#4F46E5", text_color="#FFFFFF")
                else:
                    btn.configure(fg_color=inactive_fg, text_color=inactive_text)
            else:
                if type_key in self.active_type_filters:
                    color = TYPE_COLORS.get(type_key, "#475569")
                    btn.configure(fg_color=color, text_color="#FFFFFF")
                else:
                    btn.configure(fg_color=inactive_fg, text_color=inactive_text)

    def filter_files(self, event=None):
        """Filter self.files by search text and active type filters, then redraw."""
        if not self.files:
            return

        search_text = ""
        if self.filter_entry is not None:
            search_text = self.filter_entry.get().strip().lower()

        filtered = []
        for i, item in enumerate(self.files):
            title = item.get("title", "").lower()
            file_type = item.get("type", "").upper()

            # Text match
            if search_text and search_text not in title:
                continue

            # Type match
            if self.active_type_filters and file_type not in self.active_type_filters:
                continue

            filtered.append((i, item))  # Keep original 0-based index

        self.update_file_checklist_filtered(filtered)

    def update_file_checklist_filtered(self, filtered_files):
        """Redraw only filtered items, preserving self.files and using original indices."""
        for widget in self.scroll_files_frame.winfo_children():
            widget.destroy()

        self.checkbox_vars = []
        self.download_item_widgets = {}
        self._displayed_indices = [orig_idx_0 for orig_idx_0, _ in filtered_files]

        total = len(self.files)
        shown = len(filtered_files)

        if shown < total:
            self.files_label.configure(text=f"Files | الملفات المكتشفة: {shown}/{total}")
        else:
            self.files_label.configure(text=f"Files | الملفات المكتشفة: {total}")

        if not filtered_files:
            lbl = ctk.CTkLabel(
                self.scroll_files_frame,
                text="No matching files. | لا توجد ملفات مطابقة.",
                text_color="#64748B"
            )
            lbl.pack(pady=20)
            return

        for orig_idx_0, item in filtered_files:
            orig_idx_1 = orig_idx_0 + 1  # 1-based index as used by DownloadItem
            var = self.file_vars.get(orig_idx_0)
            if var is None:
                var = ctk.BooleanVar(value=True)
                self.file_vars[orig_idx_0] = var
            self.checkbox_vars.append(var)

            item_widget = DownloadItem(self.scroll_files_frame, orig_idx_1, item, var)
            self.download_item_widgets[orig_idx_1] = item_widget

    def select_all_files(self):
        for var in self.checkbox_vars:
            var.set(True)

    def deselect_all_files(self):
        for var in self.checkbox_vars:
            var.set(False)

    # ----------------------------------
    # Event Queue Processing
    # ----------------------------------
    def process_events(self):
        while True:
            try:
                event = self.event_queue.get_nowait()
                event_type = event["type"]

                if event_type == "log":
                    self.log_box.insert("end", event["message"] + "\n")
                    self.log_box.see("end")

                elif event_type == "progress":
                    current = event["current"]
                    total = event["total"]
                    if total > 0:
                        value = current / total
                        self.progress.set(value)
                        self.progress_label.configure(text=f"{round(value * 100)}%")

                elif event_type == "item_progress":
                    idx = event["index"]
                    status = event["status"]
                    pct = event["percent"]
                    if idx in self.download_item_widgets:
                        self.download_item_widgets[idx].update_state(status, pct)

                elif event_type == "analyze_done":
                    site = event["site"]
                    count = event["count"]
                    self.files = event.get("files", [])
                    self.site_label.configure(text=f"Domain | الموقع: {site}")
                    self.files_label.configure(text=f"Files | الملفات المكتشفة: {count}")
                    self.update_file_checklist(self.files)
                    self.analyze_btn.configure(state="normal", text="Analyze | فحص الروابط")
                    self.download_btn.configure(state="normal")
                    self.is_working = False

                elif event_type == "analyze_error":
                    self.analyze_btn.configure(state="normal", text="Analyze | فحص الروابط")
                    self.download_btn.configure(state="normal")
                    self.is_working = False

                elif event_type == "download_done":
                    self.analyze_btn.configure(state="normal")
                    self.download_btn.configure(state="normal", text="Download Selected | بدء تنزيل المحدد")
                    self.cancel_btn.configure(state="disabled")
                    self.is_working = False

                elif event_type == "update_result":
                    manual = event.get("manual", False)
                    latest_tag = event.get("latest_tag")
                    download_url = event.get("download_url")
                    release_notes = event.get("release_notes", "")

                    if manual:
                        self.update_btn.configure(state="normal", text="فحص التحديثات | Updates")

                    if latest_tag and download_url:
                        if manual:
                            self.log(f"[+] Update available: {latest_tag}")
                        UpdateModal(self, latest_tag, download_url, release_notes)
                    elif manual:
                        if release_notes == "up_to_date":
                            self.log("[+] Waraqat is up to date! (أنت تستخدم أحدث إصدار)")
                        elif release_notes == "no_asset":
                            self.log("[!] The latest release does not include a Waraqat.exe asset.")
                        else:
                            self.log("[!] Unable to reach GitHub releases or check updates.")

            except queue.Empty:
                break

        self.after(50, self.process_events)

    def update_item_progress(self, index, status, percent=0.0):
        self.event_queue.put({
            "type": "item_progress",
            "index": index,
            "status": status,
            "percent": percent
        })

    def log(self, text):
        self.event_queue.put({"type": "log", "message": str(text)})

    def update_progress(self, current, total):
        self.event_queue.put({"type": "progress", "current": current, "total": total})

    # ----------------------------------
    # Analyze (Background Thread)
    # ----------------------------------
    def analyze(self):
        if self.is_working:
            return

        current_tab = self.tabview.get()
        urls_to_scan = []

        if "Single" in current_tab:
            single_url = self.url_entry.get().strip()
            if not single_url:
                self.log("[!] Please enter a webpage URL first | يرجى ادخال رابط الصفحة")
                return
            if not single_url.startswith(("http://", "https://")):
                single_url = "https://" + single_url
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, single_url)
            urls_to_scan = [single_url]
        else:
            raw_text = self.batch_textbox.get("1.0", "end").strip()
            lines = [l.strip() for l in raw_text.splitlines() if l.strip() and not l.strip().startswith("#")]
            for l in lines:
                if not l.startswith(("http://", "https://")):
                    l = "https://" + l
                urls_to_scan.append(l)

            if not urls_to_scan:
                self.log("[!] Please enter at least one URL in the Batch tab | يرجى ادخال رابط واحد على الاقل")
                return

        self.is_working = True
        self.analyze_btn.configure(state="disabled", text="Scanning... | جاري الفحص")
        self.download_btn.configure(state="disabled")
        self.progress.set(0)
        self.progress_label.configure(text="0%")

        threading.Thread(target=self._analyze_worker, args=(urls_to_scan,), daemon=True).start()

    def _analyze_worker(self, urls):
        try:
            if len(urls) == 1:
                url = urls[0]
                self.log(f"[*] Scanning webpage: {url}")
                detection = detect_site(url)
                self.log(f"[*] Domain detected: {detection['site']}")
                files = extract_files(url)
                site_name = detection["site"]
            else:
                self.log(f"[*] Starting Batch Scan on {len(urls)} pages...")
                files = extract_files_batch(urls, self.log)
                site_name = f"Batch ({len(urls)} URLs)"

            self.log(f"[+] Scan completed! Found {len(files)} downloadable file(s).")

            self.event_queue.put({
                "type": "analyze_done",
                "site": site_name,
                "count": len(files),
                "files": files
            })

        except Exception as e:
            self.log(f"[ERROR] Error scanning page: {str(e)}")
            self.event_queue.put({"type": "analyze_error", "error": str(e)})

    # ----------------------------------
    # Download (Background Thread)
    # ----------------------------------
    def start_download(self):
        if self.is_working:
            return

        if not self.files:
            self.log("[!] Please scan URLs first before downloading.")
            return

        selected_files = []
        for idx in self._displayed_indices:
            var = self.file_vars.get(idx)
            if var and var.get():
                item_copy = dict(self.files[idx])
                item_copy["orig_index"] = idx + 1
                selected_files.append(item_copy)

        if not selected_files:
            self.log("[!] No files selected! Check at least one file from the checklist.")
            return

        # Normalize target folder
        raw_folder = self.folder_entry.get().strip() or self.selected_save_path
        if not os.path.isabs(raw_folder):
            target_folder = os.path.join(os.path.expanduser("~"), DEFAULT_DOWNLOAD_FOLDER, raw_folder)
        else:
            target_folder = raw_folder

        target_folder = os.path.abspath(target_folder)
        try:
            os.makedirs(target_folder, exist_ok=True)
        except OSError as e:
            self.log(f"[ERROR] Could not create save folder: {str(e)}")
            return

        try:
            workers = int(self.threads_menu.get())
        except Exception:
            workers = 5

        try:
            timeout = int(self.settings.get("timeout", 60))
        except (TypeError, ValueError):
            timeout = 60
        if timeout <= 0:
            timeout = 60

        self.is_working = True
        self.cancel_event.clear()

        self.analyze_btn.configure(state="disabled")
        self.download_btn.configure(state="disabled", text="Downloading... | جاري التحميل")
        self.cancel_btn.configure(state="normal")
        self.progress.set(0)
        self.progress_label.configure(text="0%")

        threading.Thread(
            target=self._download_worker,
            args=(selected_files, target_folder, workers, timeout),
            daemon=True
        ).start()

    def cancel_download(self):
        if self.is_working:
            self.cancel_event.set()
            self.log("[!] Cancellation signal sent. Partial files are kept as .part and will resume next time.")
            self.cancel_btn.configure(state="disabled")

    def _download_worker(self, files_to_download, target_folder, workers, timeout=60):
        try:
            os.makedirs(target_folder, exist_ok=True)
            self.log("=" * 50)
            self.log(f"[*] Starting download into target folder:")
            self.log(f"[*] Folder path: {target_folder}")
            self.log(f"[*] Selected files count: {len(files_to_download)}")
            self.log("=" * 50)

            result = download_parallel(
                files_to_download,
                target_folder,
                self.update_progress,
                self.log,
                self.cancel_event,
                workers,
                item_callback=self.update_item_progress,
                timeout=timeout
            )

            if self.cancel_event.is_set():
                self.log("[!] Download was cancelled by user.")
            else:
                self.log("=" * 50)
                failed_count = result.get("failed", 0)
                if failed_count > 0:
                    self.log(f"[!] Downloads finished with {failed_count} failure(s). Check the log above.")
                else:
                    self.log("[+] All selected downloads finished successfully!")
                self.log(f"[+] All files are stored inside: {target_folder}")
                self.log("[+] Click 'Open | فتح' to view your downloaded files.")
                self.log("=" * 50)

                # Toast notification on completion
                if self.settings.get("notifications_enabled", True):
                    message = f"تم تحميل {result.get('success', 0)} ملف بنجاح إلى {target_folder}"
                    if failed_count:
                        message += f" (فشل {failed_count})"
                    notify_download_complete("ورقات | Waraqat", message)

                # Auto-open folder if enabled in settings
                if self.settings.get("open_folder_on_finish", True):
                    try:
                        os.startfile(target_folder)
                    except Exception:
                        pass

        except Exception as e:
            self.log(f"[ERROR] Download worker error: {str(e)}")
            if self.settings.get("notifications_enabled", True):
                notify_error("ورقات | Waraqat", str(e))
        finally:
            self.event_queue.put({"type": "download_done"})


if __name__ == "__main__":
    app = App()
    app.mainloop()
