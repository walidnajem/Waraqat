import os
import queue
import threading
try:
    from tkinterdnd2 import TkinterDnD, DND_TEXT, DND_FILES
    _HAS_DND = True
except Exception:
    _HAS_DND = False
    TkinterDnD = None
    DND_TEXT = None
    DND_FILES = None
try:
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning, module="fitz")
    import fitz as _fitz
    _HAS_PDF_PREVIEW = True
except Exception:
    _HAS_PDF_PREVIEW = False
    _fitz = None
try:
    import pystray
    from PIL import Image as _PILImage
    _HAS_TRAY = True
except Exception:
    _HAS_TRAY = False
    pystray = None
    _PILImage = None
from auto_updater import check_for_update
from update_modal import UpdateModal, UpdateResultModal
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageDraw

from config import (
    APP_NAME,
    APP_SUBTITLE,
    APP_VERSION,
    DEFAULT_DOWNLOAD_FOLDER,
    load_settings,
    save_settings
)
from extractor import extract_files, extract_files_batch
from downloader import download_parallel
from utils import clean_filename, fit_filename, get_site_name
from notifications import notify_download_complete, notify_error
from md3 import COLORS as M3, RADIUS, font as ui_font, center_on_parent, WavyProgressBar

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
    "DJVU": "#795548",      # Brown
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


_CHECK_ICON_CACHE = None


def check_icon(size=(14, 14)):
    """Theme-aware checkmark used by selected Material 3 filter chips."""
    global _CHECK_ICON_CACHE
    if _CHECK_ICON_CACHE is None:
        scale = 4
        w = h = size[0] * scale

        def draw(color):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            drawer = ImageDraw.Draw(img)
            drawer.line(
                [(w * 0.22, h * 0.52), (w * 0.43, h * 0.72), (w * 0.80, h * 0.30)],
                fill=color,
                width=scale * 2,
                joint="curve",
            )
            return img.resize(size, Image.Resampling.LANCZOS)

        _CHECK_ICON_CACHE = ctk.CTkImage(
            light_image=draw("#1B1B3A"),
            dark_image=draw("#E4E1F9"),
            size=size,
        )
    return _CHECK_ICON_CACHE


# ---------------------------------------------------------------------------
# Material 3 widget helpers
# ---------------------------------------------------------------------------
_BUTTON_VARIANTS = {
    "filled": {
        "fg_color": M3["primary"],
        "hover_color": M3["primary_hover"],
        "text_color": M3["on_primary"],
    },
    "tonal": {
        "fg_color": M3["secondary_container"],
        "hover_color": M3["secondary_hover"],
        "text_color": M3["on_secondary_container"],
    },
    "outlined": {
        "fg_color": "transparent",
        "hover_color": M3["primary_container"],
        "text_color": M3["primary"],
        "border_width": 1,
        "border_color": M3["outline"],
    },
    "text": {
        "fg_color": "transparent",
        "hover_color": M3["primary_container"],
        "text_color": M3["primary"],
    },
    "success": {
        "fg_color": M3["success"],
        "hover_color": M3["success_hover"],
        "text_color": M3["on_success"],
    },
    "danger": {
        "fg_color": M3["error_container"],
        "hover_color": M3["error_hover"],
        "text_color": M3["on_error_container"],
    },
    "icon": {
        "fg_color": "transparent",
        "hover_color": M3["surface_container_high"],
        "text_color": M3["on_surface_variant"],
        "width": 40,
        "height": 40,
    },
}


def m3_button(parent, text="", variant="filled", **kwargs):
    """Creates a Material 3 styled button."""
    style = {
        "height": 40,
        "corner_radius": RADIUS["pill"],
        "font": ui_font(12, "bold"),
        "border_width": 0,
    }
    style.update(_BUTTON_VARIANTS.get(variant, _BUTTON_VARIANTS["filled"]))
    style.update(kwargs)
    return ctk.CTkButton(parent, text=text, **style)


def m3_input(widget):
    """Applies the Material 3 outlined text-field look, including focus ring."""
    widget.configure(
        fg_color=M3["surface_container_lowest"],
        border_color=M3["outline_variant"],
        border_width=1,
        corner_radius=RADIUS["md"],
    )

    def _focus_in(_event):
        try:
            widget.configure(border_color=M3["primary"], border_width=2)
        except Exception:
            pass

    def _focus_out(_event):
        try:
            widget.configure(border_color=M3["outline_variant"], border_width=1)
        except Exception:
            pass

    widget.bind("<FocusIn>", _focus_in, add="+")
    widget.bind("<FocusOut>", _focus_out, add="+")
    return widget


class NewFolderModal(ctk.CTkToplevel):
    """
    A custom next-level modal window matching Waraqat design for creating
    and selecting a new dedicated download subfolder.
    """

    def __init__(self, parent, current_path, on_folder_created):
        super().__init__(parent)
        self.configure(fg_color=M3["surface"])

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
        center_on_parent(self, self.parent, 520, 350)

    def build_modal_ui(self):
        # Card container
        card = ctk.CTkFrame(
            self,
            fg_color=M3["surface_container_high"],
            corner_radius=RADIUS["xl"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        card.pack(fill="both", expand=True, padx=16, pady=16)

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
            font=ui_font(16, "bold"),
            text_color=M3["on_surface"]
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_box,
            text="سيتم حفظ الملفات المحملة داخل هذا المجلد تلقائياً",
            font=ui_font(11),
            text_color=M3["on_surface_variant"]
        )
        subtitle.pack(anchor="w")

        # Base directory option
        options_frame = ctk.CTkFrame(
            card,
            fg_color=M3["surface_container_lowest"],
            corner_radius=RADIUS["md"]
        )
        options_frame.pack(fill="x", padx=15, pady=(5, 10))

        radio_downloads = ctk.CTkRadioButton(
            options_frame,
            text="داخل مجلد التنزيلات الرئيسي (Downloads)",
            variable=self.base_choice_var,
            value="downloads",
            font=ui_font(11),
            fg_color=M3["primary"],
            hover_color=M3["primary_hover"],
            text_color=M3["on_surface"],
            command=self.update_preview
        )
        radio_downloads.pack(anchor="w", padx=12, pady=(8, 4))

        radio_current = ctk.CTkRadioButton(
            options_frame,
            text=f"داخل المجلد الحالي: {os.path.basename(self.current_path)}",
            variable=self.base_choice_var,
            value="current",
            font=ui_font(11),
            fg_color=M3["primary"],
            hover_color=M3["primary_hover"],
            text_color=M3["on_surface"],
            command=self.update_preview
        )
        radio_current.pack(anchor="w", padx=12, pady=(0, 8))

        # Folder Name Entry
        entry_label = ctk.CTkLabel(
            card,
            text="اسم المجلد الجديد | Folder Name:",
            font=ui_font(11, "bold"),
            text_color=M3["on_surface"]
        )
        entry_label.pack(anchor="w", padx=15, pady=(2, 2))

        self.entry = m3_input(ctk.CTkEntry(
            card,
            placeholder_text="مثال: روايات, امتحانات 2024, دروس الفيزياء...",
            height=42,
            font=ui_font(12),
            placeholder_text_color=M3["on_surface_variant"]
        ))
        self.entry.pack(fill="x", padx=15, pady=(0, 8))
        self.entry.bind("<KeyRelease>", self.update_preview)
        self.entry.bind("<Return>", lambda e: self.confirm_create())
        self.entry.bind("<Escape>", lambda e: self.destroy())

        # Live Path Preview Box
        self.preview_lbl = ctk.CTkLabel(
            card,
            text="مسار الحفظ النهائي: ...",
            font=("Consolas", 10),
            text_color=M3["primary"],
            wraplength=460,
            justify="left"
        )
        self.preview_lbl.pack(fill="x", padx=15, pady=(0, 12))

        # Action Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 12))

        confirm_btn = m3_button(
            btn_frame,
            text="✓ إنشاء وتحديد المجلد | Create & Select",
            variant="success",
            height=42,
            font=ui_font(12, "bold"),
            command=self.confirm_create
        )
        confirm_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        cancel_btn = m3_button(
            btn_frame,
            text="إلغاء | Cancel",
            variant="outlined",
            width=110,
            height=42,
            font=ui_font(11),
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
        self.configure(fg_color=M3["surface"])
        self.parent = parent
        self._settings = dict(settings)
        self._on_save = on_save

        self.title("الإعدادات | Settings")
        # Tall enough for all sections when the screen allows it; scrolls otherwise.
        self._win_w = 540
        self._win_h = min(740, self.winfo_screenheight() - 160)
        self.geometry(f"{self._win_w}x{self._win_h}")
        self.minsize(520, min(640, self._win_h))
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

    def center_window(self):
        center_on_parent(self, self.parent, self._win_w, self._win_h)

    def build_ui(self):
        # Card container
        card = ctk.CTkFrame(
            self,
            fg_color=M3["surface_container_high"],
            corner_radius=RADIUS["xl"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        card.pack(fill="both", expand=True, padx=16, pady=16)

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
            font=ui_font(16, "bold"),
            text_color=M3["on_surface"]
        )
        title.pack(anchor="w")

        sub = ctk.CTkLabel(
            title_box,
            text="تخصيص سلوك التحميل والمظهر العام لبرنامج ورقات",
            font=ui_font(11),
            text_color=M3["on_surface_variant"]
        )
        sub.pack(anchor="w")

        # Scrollable section container; actions stay pinned at the bottom.
        content = ctk.CTkScrollableFrame(
            card,
            fg_color=M3["surface_container_low"],
            corner_radius=RADIUS["lg"],
            border_color=M3["outline_variant"],
            border_width=1,
            scrollbar_button_color=M3["outline_variant"],
            scrollbar_button_hover_color=M3["outline"]
        )
        content.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # --- Section 1: Save Path ---
        sec1 = ctk.CTkFrame(content, fg_color="transparent")
        sec1.pack(fill="x", padx=14, pady=(14, 8))

        ctk.CTkLabel(
            sec1,
            text="مسار التنزيل الافتراضي | Default Download Location:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))

        path_row = ctk.CTkFrame(sec1, fg_color="transparent")
        path_row.pack(fill="x")

        self.path_entry = m3_input(ctk.CTkEntry(
            path_row,
            height=40,
            font=ui_font(11)
        ))
        self.path_entry.insert(0, self._settings.get("save_path", ""))
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_btn = m3_button(
            path_row,
            text="استعراض...",
            variant="outlined",
            width=95,
            height=40,
            font=ui_font(11),
            command=self._browse_folder
        )
        browse_btn.pack(side="left")

        # --- Section 2: Concurrency & Speed ---
        sec2 = ctk.CTkFrame(content, fg_color="transparent")
        sec2.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(
            sec2,
            text="سرعة التنزيل والاتصالات المتزامنة | Concurrent Threads:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))

        threads_row = ctk.CTkFrame(sec2, fg_color="transparent")
        threads_row.pack(fill="x")

        self.threads_menu = ctk.CTkOptionMenu(
            threads_row,
            values=["2 ملفات (اتصال هادئ)", "3 ملفات", "5 ملفات (موصى به)", "8 ملفات (اتصال سريع)", "10 ملفات (فائق السرعة)"],
            width=230,
            height=36,
            corner_radius=RADIUS["pill"],
            font=ui_font(11),
            dropdown_font=ui_font(11),
            fg_color=M3["surface_container_highest"],
            button_color=M3["surface_container_high"],
            button_hover_color=M3["outline_variant"],
            text_color=M3["on_surface"],
            dropdown_fg_color=M3["surface_container_high"],
            dropdown_hover_color=M3["primary_container"],
            dropdown_text_color=M3["on_surface"]
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
            width=190,
            height=34,
            corner_radius=RADIUS["pill"],
            font=ui_font(11),
            dropdown_font=ui_font(11),
            fg_color=M3["surface_container_highest"],
            button_color=M3["surface_container_high"],
            button_hover_color=M3["outline_variant"],
            text_color=M3["on_surface"],
            dropdown_fg_color=M3["surface_container_high"],
            dropdown_hover_color=M3["primary_container"],
            dropdown_text_color=M3["on_surface"]
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

        # --- Section 2b: Proxy (optional) ---
        sec2b = ctk.CTkFrame(content, fg_color="transparent")
        sec2b.pack(fill="x", padx=14, pady=(8, 4))

        ctk.CTkLabel(
            sec2b,
            text="Proxy (اختياري | optional):",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))

        self.proxy_entry = m3_input(ctk.CTkEntry(
            sec2b,
            placeholder_text="http://user:pass@host:port  (اتركه فارغاً لتعطيله)",
            height=40,
            font=ui_font(11),
            placeholder_text_color=M3["on_surface_variant"]
        ))
        self.proxy_entry.pack(fill="x")
        self.proxy_entry.insert(0, self._settings.get("proxy", "") or "")

        # --- Section 3: Appearance & Theme ---

        sec3 = ctk.CTkFrame(content, fg_color="transparent")
        sec3.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(
            sec3,
            text="مظهر التطبيق | Theme:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 4))

        self.theme_menu = ctk.CTkOptionMenu(
            sec3,
            values=["Dark (الوضع الداكن)", "Light (الوضع الفاتح)", "System (مطابق للنظام)"],
            width=230,
            height=36,
            corner_radius=RADIUS["pill"],
            font=ui_font(11),
            dropdown_font=ui_font(11),
            fg_color=M3["surface_container_highest"],
            button_color=M3["surface_container_high"],
            button_hover_color=M3["outline_variant"],
            text_color=M3["on_surface"],
            dropdown_fg_color=M3["surface_container_high"],
            dropdown_hover_color=M3["primary_container"],
            dropdown_text_color=M3["on_surface"]
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
            text="سلوك التطبيق التلقائي | Automation Options:",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 6))

        self.var_open_folder = ctk.BooleanVar(value=self._settings.get("open_folder_on_finish", True))
        cb_open = ctk.CTkCheckBox(
            sec4,
            text="فتح مجلد الحفظ في File Explorer تلقائياً عند انتهاء التحميل",
            variable=self.var_open_folder,
            font=ui_font(11),
            text_color=M3["on_surface"],
            fg_color=M3["primary"],
            hover_color=M3["primary_hover"],
            border_color=M3["outline"],
            checkmark_color=M3["on_primary"]
        )
        cb_open.pack(anchor="w", pady=(0, 4))

        self.var_auto_update = ctk.BooleanVar(value=self._settings.get("auto_check_updates", True))
        cb_update = ctk.CTkCheckBox(
            sec4,
            text="البحث عن تحديثات ورقات تلقائياً عند تشغيل البرنامج",
            variable=self.var_auto_update,
            font=ui_font(11),
            text_color=M3["on_surface"],
            fg_color=M3["primary"],
            hover_color=M3["primary_hover"],
            border_color=M3["outline"],
            checkmark_color=M3["on_primary"]
        )
        cb_update.pack(anchor="w", pady=(0, 4))

        self.var_notifications = ctk.BooleanVar(value=self._settings.get("notifications_enabled", True))
        cb_notify = ctk.CTkCheckBox(
            sec4,
            text="تفعيل إشعارات الويندوز (Toast Notifications) عند اكتمال التنزيل",
            variable=self.var_notifications,
            font=ui_font(11),
            text_color=M3["on_surface"],
            fg_color=M3["primary"],
            hover_color=M3["primary_hover"],
            border_color=M3["outline"],
            checkmark_color=M3["on_primary"]
        )
        cb_notify.pack(anchor="w")

        # --- Bottom Action Buttons ---
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(10, 16))

        save_btn = m3_button(
            btn_row,
            text="✓ حفظ الإعدادات | Save Settings",
            variant="success",
            height=42,
            font=ui_font(12, "bold"),
            command=self._save
        )
        save_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        cancel_btn = m3_button(
            btn_row,
            text="إلغاء | Cancel",
            variant="outlined",
            width=110,
            height=42,
            font=ui_font(11),
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
        self._settings["proxy"] = self.proxy_entry.get().strip()
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
    def __init__(self, master, index, item, var, open_resolver=None):
        super().__init__(
            master,
            fg_color=M3["surface_container_lowest"],
            corner_radius=RADIUS["md"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        self.pack(fill="x", padx=4, pady=3)
        self.index = index
        self.item = item
        self.var = var
        self._open_resolver = open_resolver

        # Main row: text/controls on the left, optional thumbnail on the right.
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="x")

        top_row = ctk.CTkFrame(self.body, fg_color="transparent")
        top_row.pack(side="left", fill="x", expand=True, padx=10, pady=(6, 4))

        # Checkbox
        self.cb = ctk.CTkCheckBox(
            top_row,
            text="",
            variable=var,
            width=22,
            checkbox_width=18,
            checkbox_height=18,
            corner_radius=4,
            fg_color=M3["primary"],
            hover_color=M3["primary_hover"],
            border_color=M3["outline"],
            checkmark_color=M3["on_primary"]
        )
        self.cb.pack(side="left", padx=(0, 6))

        # Type Badge
        raw_type = item.get("type", "PDF").upper()
        badge_color = TYPE_COLORS.get(raw_type, "#475569")
        self.badge = ctk.CTkLabel(
            top_row,
            text=raw_type,
            font=ui_font(10, "bold"),
            fg_color=badge_color,
            text_color="#FFFFFF",
            corner_radius=RADIUS["sm"],
            padx=9,
            pady=3
        )
        self.badge.pack(side="left", padx=(0, 10))

        # File Title
        title_text = f"{index}. {item.get('title', 'Document')}"
        self.title_lbl = ctk.CTkLabel(
            top_row,
            text=title_text,
            font=ui_font(12),
            text_color=M3["on_surface"],
            anchor="w"
        )
        self.title_lbl.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # Status text on the right
        self.status_lbl = ctk.CTkLabel(
            top_row,
            text="Ready | جاهز",
            font=ui_font(10),
            text_color=M3["on_surface_variant"],
            width=105,
            anchor="e"
        )
        self.status_lbl.pack(side="right")

        self.open_btn = m3_button(
            top_row,
            text="Open",
            variant="icon",
            width=56,
            height=30,
            corner_radius=15,
            font=ui_font(10, "bold"),
            command=self._open_file
        )
        self.open_btn.pack(side="right", padx=(4, 0))

        self.thumb_label = ctk.CTkLabel(
            self.body,
            text="",
            width=48,
            height=64,
            corner_radius=RADIUS["sm"],
            fg_color=M3["surface_container"]
        )
        # Packed only after a preview image is ready, so rows stay compact.
        self.thumb_label.bind("<Button-1>", lambda e: self._open_file())
        self._thumb_filepath = None
        self._thumb_image = None

        # Per-file sleek progress bar (visible when downloading or completed)
        self.progress_bar = WavyProgressBar(
            self,
            height=10,
            progress_color=M3["primary"],
            track_color=M3["outline_variant"],
            surface_color=M3["surface_container_lowest"],
            amplitude=1.8,
            wavelength=32,
            thickness=2.6,
            speed=34.0,
        )
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 6))
        self.progress_bar.set(0)

    def _open_file(self):
        path = getattr(self, "_thumb_filepath", None)
        # The file may already exist on disk even if this item was never
        # downloaded during the current session (or the preview is still
        # rendering). Resolve its expected path as a fallback.
        if (not path or not os.path.exists(path)) and self._open_resolver:
            try:
                path = self._open_resolver()
            except Exception:
                path = None
        if path and os.path.exists(path):
            try:
                os.startfile(path)
                return
            except Exception:
                pass
        try:
            self.status_lbl.configure(text="Download first | نزّل أولاً", text_color=M3["warning"])
        except Exception:
            pass

    def _render_thumbnail(self, filepath):
        if not _HAS_PDF_PREVIEW or not filepath or not os.path.exists(filepath):
            return
        try:
            doc = _fitz.open(filepath)
            page = doc[0]
            pix = page.get_pixmap(matrix=_fitz.Matrix(0.25, 0.25))
            from PIL import Image as _PILImage
            img = _PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(pix.width, pix.height))

            def apply():
                self._thumb_image = ctk_img
                self._thumb_filepath = filepath
                try:
                    self.thumb_label.configure(image=ctk_img, text="")
                    if not self.thumb_label.winfo_manager():
                        self.thumb_label.pack(side="right", padx=(6, 10), pady=(8, 6))
                except Exception:
                    pass

            self.after(0, apply)
        except Exception:
            pass

    def update_state(self, status, percent=0.0, downloaded=0, total=0, filepath=None):
        if status == "downloading":
            self.configure(border_color=M3["primary"], fg_color=M3["primary_container"])
            self.status_lbl.configure(text=f"{int(percent)}%", text_color=M3["primary"])
            self.progress_bar.set_colors(progress_color=M3["primary"])
            self.progress_bar.set(percent / 100.0)
            self.progress_bar.start()
        elif status == "progress":
            if total and total > 0:
                txt = f"{int(percent)}% ({downloaded/1048576:.1f}/{total/1048576:.1f} MB)"
            else:
                txt = f"{int(percent)}%"
            self.status_lbl.configure(text=txt, text_color=M3["primary"])
            self.progress_bar.set(percent / 100.0)
            self.progress_bar.start()
        elif status == "success":
            if filepath:
                self._thumb_filepath = filepath
                if _HAS_PDF_PREVIEW and str(filepath).lower().endswith(".pdf"):
                    import threading
                    threading.Thread(target=self._render_thumbnail, args=(filepath,), daemon=True).start()
            self.configure(border_color=M3["success"], fg_color=M3["success_container"])
            self.status_lbl.configure(text="Completed ✓", text_color=M3["success"])
            self.progress_bar.set_colors(progress_color=M3["success"])
            self.progress_bar.set(1.0)
            self.progress_bar.stop()
        elif status == "skip":
            if filepath:
                self._thumb_filepath = filepath
                if _HAS_PDF_PREVIEW and str(filepath).lower().endswith(".pdf"):
                    import threading
                    threading.Thread(target=self._render_thumbnail, args=(filepath,), daemon=True).start()
            self.configure(border_color=M3["outline_variant"], fg_color=M3["surface_container"])
            self.status_lbl.configure(text="Exists (Skip)", text_color=M3["on_surface_variant"])
            self.progress_bar.set(1.0)
            self.progress_bar.set_colors(progress_color=M3["outline"])
            self.progress_bar.stop()
        elif status == "failed":
            self.configure(border_color=M3["error"], fg_color=M3["error_container"])
            self.status_lbl.configure(text="Failed ✗", text_color=M3["error"])
            self.progress_bar.set_colors(progress_color=M3["error"])
            self.progress_bar.stop()
        elif status == "cancelled":
            self.status_lbl.configure(text="Cancelled", text_color=M3["warning"])
            self.progress_bar.set_colors(progress_color=M3["warning"])
            self.progress_bar.stop()
        elif status == "retry":
            self.status_lbl.configure(text="Retrying...", text_color=M3["warning"])
            self.progress_bar.stop()

        # Keep the wavy bar background in sync with the current row colour.
        try:
            self.progress_bar.set_surface(self.cget("fg_color"))
        except Exception:
            pass


class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.configure(fg_color=M3["surface"])

        self.title(f"{APP_NAME} v{APP_VERSION}")

        # Center on screen and keep the whole window inside the work area.
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(1020, screen_w - 80)
        win_h = min(880, screen_h - 100)
        win_x = max(20, (screen_w - win_w) // 2)
        win_y = max(20, (screen_h - win_h) // 2 - 20)
        self.geometry(f"{win_w}x{win_h}+{win_x}+{win_y}")
        self.minsize(min(880, max(760, screen_w - 80)), min(720, max(600, screen_h - 100)))

        # Set official Waraqat window icon
        ico_path = os.path.join(ASSETS_DIR, "waraqat_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # Load settings
        self.settings = load_settings()
        self._apply_proxy(self.settings)
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
        self.bind_shortcuts()
        if _HAS_DND:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self._enable_dnd()
            except Exception:
                pass
        if _HAS_TRAY:
            try:
                self._setup_tray()
            except Exception:
                pass
        self.protocol("WM_DELETE_WINDOW", self._on_close_to_tray)
        # بعد بناء الواجهة، نستدعي فحص التحديثات تلقائيًا
        self.after_ui_build()
        self.after(50, self.process_events)

    def after_ui_build(self):
        """Called after the UI is constructed.
        Initiates an asynchronous check for new releases in the background if enabled in settings.
        """
        if not self.settings.get("auto_check_updates", True):
            return

        def _callback(latest_tag, download_url, release_notes="", sha256=None):
            self.event_queue.put({
                "type": "update_result",
                "latest_tag": latest_tag,
                "download_url": download_url,
                "release_notes": release_notes,
                "sha256": sha256,
                "manual": False,
            })

        check_for_update(_callback, allow_skipped=False,
                         skipped_version=self.settings.get("skipped_update_version"))

    def manual_check_updates(self):
        """Triggered manually by user clicking 'Check for Updates' button."""
        self.update_btn.configure(state="disabled", text="جاري الفحص...")
        self.log("[*] Checking GitHub repository for latest updates...")

        def _callback(latest_tag, download_url, release_notes="", sha256=None):
            self.event_queue.put({
                "type": "update_result",
                "latest_tag": latest_tag,
                "download_url": download_url,
                "release_notes": release_notes,
                "sha256": sha256,
                "manual": True,
            })

        check_for_update(_callback, allow_skipped=True,
                         skipped_version=self.settings.get("skipped_update_version"))

    def build_ui(self):
        # ----------------------------------
        # Material 3 top app bar
        # ----------------------------------
        app_bar = ctk.CTkFrame(self, fg_color="transparent")
        app_bar.pack(fill="x", padx=24, pady=(12, 8))

        brand = ctk.CTkFrame(app_bar, fg_color="transparent")
        brand.pack(side="left")

        logo_img = load_icon_image("logo", (40, 40))
        if logo_img:
            ctk.CTkLabel(brand, text="", image=logo_img).pack(side="left", padx=(0, 14))

        titles_box = ctk.CTkFrame(brand, fg_color="transparent")
        titles_box.pack(side="left")

        ctk.CTkLabel(
            titles_box,
            text=APP_NAME,
            font=ui_font(24, "bold"),
            text_color=M3["on_surface"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            titles_box,
            text=APP_SUBTITLE,
            font=ui_font(12),
            text_color=M3["on_surface_variant"]
        ).pack(anchor="w")

        bar_actions = ctk.CTkFrame(app_bar, fg_color="transparent")
        bar_actions.pack(side="right")

        version_pill = ctk.CTkLabel(
            bar_actions,
            text=f"v{APP_VERSION}",
            font=ui_font(11, "bold"),
            fg_color=M3["primary_container"],
            text_color=M3["on_primary_container"],
            corner_radius=RADIUS["sm"],
            padx=12,
            pady=5
        )
        version_pill.pack(side="left", padx=(0, 10))

        # Sun / Moon quick theme toggle (Material icon button)
        curr_mode = ctk.get_appearance_mode().lower()
        theme_icon = self.icon_sun if curr_mode == "dark" else self.icon_moon
        self.theme_btn = m3_button(
            bar_actions,
            text="",
            variant="icon",
            image=theme_icon,
            corner_radius=RADIUS["pill"],
            command=self.toggle_theme
        )
        self.theme_btn.pack(side="left", padx=2)

        self.update_btn = m3_button(
            bar_actions,
            text="Updates | التحديثات",
            variant="outlined",
            image=self.icon_update,
            width=155,
            height=38,
            font=ui_font(11),
            command=self.manual_check_updates
        )
        self.update_btn.pack(side="left", padx=4)

        self.settings_btn = m3_button(
            bar_actions,
            text="Settings | الإعدادات",
            variant="tonal",
            image=self.icon_settings,
            width=150,
            height=38,
            font=ui_font(11),
            command=self.open_settings_dialog
        )
        self.settings_btn.pack(side="left", padx=(4, 0))

        # ----------------------------------
        # Card 1: URL input tabs
        # ----------------------------------
        input_card = ctk.CTkFrame(
            self,
            fg_color=M3["surface_container_low"],
            corner_radius=RADIUS["lg"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        input_card.pack(fill="x", padx=24, pady=(0, 8))

        self.tabview = ctk.CTkTabview(
            input_card,
            height=112,
            corner_radius=RADIUS["md"],
            fg_color=M3["surface_container_low"],
            segmented_button_fg_color=M3["surface_container"],
            segmented_button_selected_color=M3["primary_container"],
            segmented_button_selected_hover_color=M3["secondary_hover"],
            segmented_button_unselected_color=M3["surface_container"],
            segmented_button_unselected_hover_color=M3["surface_container_high"],
            text_color=M3["on_surface"]
        )
        self.tabview.pack(fill="x", padx=6, pady=4)

        self.tab_single = self.tabview.add("Single URL | صفحة واحدة")
        self.tab_batch = self.tabview.add("Batch URLs | صفحات متعددة")

        self.url_entry = m3_input(ctk.CTkEntry(
            self.tab_single,
            placeholder_text="https://example.com/books-or-lessons-page",
            height=40,
            font=ui_font(12),
            placeholder_text_color=M3["on_surface_variant"]
        ))
        self.url_entry.pack(fill="x", padx=8, pady=8)

        self.batch_textbox = m3_input(ctk.CTkTextbox(
            self.tab_batch,
            height=58,
            font=("Consolas", 11),
            text_color=M3["on_surface"]
        ))
        self.batch_textbox.pack(fill="both", expand=True, padx=8, pady=4)
        self.batch_textbox.insert("1.0", "# Paste multiple URLs (one per line) | الصق الروابط هنا (رابط في كل سطر)\n")

        # ----------------------------------
        # Card 2: Save destination
        # ----------------------------------
        folder_card = ctk.CTkFrame(
            self,
            fg_color=M3["surface_container_low"],
            corner_radius=RADIUS["lg"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        folder_card.pack(fill="x", padx=24, pady=(0, 8))

        folder_inner = ctk.CTkFrame(folder_card, fg_color="transparent")
        folder_inner.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(
            folder_inner,
            text="Save Location | مجلد الحفظ:",
            font=ui_font(12, "bold"),
            text_color=M3["on_surface"]
        ).pack(side="left", padx=(0, 10))

        self.folder_entry = m3_input(ctk.CTkEntry(
            folder_inner,
            height=36,
            font=ui_font(11)
        ))
        self.folder_entry.insert(0, self.selected_save_path)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.new_folder_btn = m3_button(
            folder_inner,
            text="New Folder | مجلد جديد",
            variant="tonal",
            image=self.icon_folder_new,
            width=150,
            height=36,
            font=ui_font(11),
            command=self.open_new_folder_dialog
        )
        self.new_folder_btn.pack(side="left", padx=(0, 6))

        self.browse_btn = m3_button(
            folder_inner,
            text="Browse | استعراض",
            variant="outlined",
            image=self.icon_folder_browse,
            width=125,
            height=36,
            font=ui_font(11),
            command=self.browse_folder
        )
        self.browse_btn.pack(side="left", padx=(0, 6))

        self.open_folder_btn = m3_button(
            folder_inner,
            text="Open | فتح",
            variant="text",
            image=self.icon_folder_open,
            width=95,
            height=36,
            font=ui_font(11),
            command=self.open_destination_folder
        )
        self.open_folder_btn.pack(side="left")

        # ----------------------------------
        # Card 3: Status & concurrency
        # ----------------------------------
        status_bar = ctk.CTkFrame(
            self,
            fg_color=M3["surface_container"],
            corner_radius=RADIUS["md"]
        )
        status_bar.pack(fill="x", padx=24, pady=(0, 8))

        self.site_label = ctk.CTkLabel(
            status_bar,
            text="Domain | الموقع: -",
            font=ui_font(12),
            text_color=M3["on_surface_variant"]
        )
        self.site_label.pack(side="left", padx=14, pady=6)

        self.files_label = ctk.CTkLabel(
            status_bar,
            text="Files | الملفات المكتشفة: 0",
            font=ui_font(12, "bold"),
            text_color=M3["primary"]
        )
        self.files_label.pack(side="left", padx=18, pady=6)

        threads_label = ctk.CTkLabel(
            status_bar,
            text="Threads | التنزيلات التزامنية:",
            font=ui_font(12),
            text_color=M3["on_surface_variant"]
        )
        current_workers = str(self.settings.get("max_workers", 5))
        self.threads_menu = ctk.CTkOptionMenu(
            status_bar,
            values=["2", "3", "5", "8", "10"],
            width=74,
            height=28,
            corner_radius=14,
            font=ui_font(11),
            dropdown_font=ui_font(11),
            fg_color=M3["surface_container_highest"],
            button_color=M3["surface_container_high"],
            button_hover_color=M3["outline_variant"],
            text_color=M3["on_surface"],
            dropdown_fg_color=M3["surface_container_high"],
            dropdown_hover_color=M3["primary_container"],
            dropdown_text_color=M3["on_surface"],
            command=self.on_threads_change
        )
        self.threads_menu.set(current_workers)
        self.threads_menu.pack(side="right", padx=(0, 12))
        threads_label.pack(side="right", padx=(0, 8))

        # ----------------------------------
        # Card 4: Primary actions
        # ----------------------------------
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.pack(fill="x", padx=24, pady=(0, 8))

        self.analyze_btn = m3_button(
            actions_frame,
            text="Analyze | فحص الروابط",
            variant="filled",
            image=self.icon_search,
            height=42,
            font=ui_font(13, "bold"),
            command=self.analyze
        )
        self.analyze_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.download_btn = m3_button(
            actions_frame,
            text="Download Selected | بدء تنزيل المحدد",
            variant="success",
            image=self.icon_download,
            height=42,
            font=ui_font(13, "bold"),
            command=self.start_download
        )
        self.download_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.cancel_btn = m3_button(
            actions_frame,
            text="Cancel | الغاء",
            variant="danger",
            image=self.icon_cancel,
            width=125,
            height=42,
            font=ui_font(12, "bold"),
            state="disabled",
            command=self.cancel_download
        )
        self.cancel_btn.pack(side="left")

        # ----------------------------------
        # Card 5: Discovered files checklist
        # ----------------------------------
        list_container = ctk.CTkFrame(
            self,
            fg_color=M3["surface_container_low"],
            corner_radius=RADIUS["lg"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        list_container.pack(fill="x", padx=24, pady=(0, 8))

        list_header = ctk.CTkFrame(list_container, fg_color="transparent")
        list_header.pack(fill="x", padx=12, pady=(8, 3))

        ctk.CTkLabel(
            list_header,
            text="Discovered Files | قائمة الملفات المكتشفة:",
            font=ui_font(13, "bold"),
            text_color=M3["on_surface"]
        ).pack(side="left")

        self.btn_deselect_all = m3_button(
            list_header,
            text="Deselect All | الغاء التحديد",
            variant="text",
            width=140,
            height=32,
            font=ui_font(11),
            command=self.deselect_all_files
        )
        self.btn_deselect_all.pack(side="right", padx=(6, 0))

        self.btn_select_all = m3_button(
            list_header,
            text="Select All | تحديد الكل",
            variant="text",
            width=125,
            height=32,
            font=ui_font(11),
            command=self.select_all_files
        )
        self.btn_select_all.pack(side="right")

        # Filter bar (search + type chips)
        filter_bar = ctk.CTkFrame(list_container, fg_color="transparent")
        filter_bar.pack(fill="x", padx=12, pady=(2, 6))

        self.filter_entry = m3_input(ctk.CTkEntry(
            filter_bar,
            placeholder_text="Search files... | بحث في الملفات...",
            width=260,
            height=36,
            font=ui_font(11),
            text_color=M3["on_surface"],
            placeholder_text_color=M3["on_surface_variant"]
        ))
        self.filter_entry.pack(side="left", padx=(0, 10))
        self.filter_entry.bind("<KeyRelease>", self.filter_files)

        pill_types = [
            ("All | الكل", "ALL", 98),
            ("PDF", "PDF", 80),
            ("DOCX", "DOCX", 90),
            ("PPTX", "PPTX", 88),
            ("GDRIVE", "GDRIVE", 102),
            ("EPUB", "EPUB", 82),
        ]

        self.type_filter_buttons = {}
        self.type_filter_labels = {}
        for label, type_key, chip_width in pill_types:
            self.type_filter_labels[type_key] = label
            btn = m3_button(
                filter_bar,
                text=label,
                variant="outlined",
                width=chip_width,
                height=34,
                font=ui_font(11, "bold"),
                corner_radius=17,
                command=lambda tk=type_key: self._toggle_type_filter(tk)
            )
            btn.pack(side="left", padx=3)
            self.type_filter_buttons[type_key] = btn
        self._refresh_pill_styles()

        self.scroll_files_frame = ctk.CTkScrollableFrame(
            list_container,
            height=175,
            fg_color=M3["surface_container_lowest"],
            corner_radius=RADIUS["md"],
            border_color=M3["outline_variant"],
            border_width=1
        )
        self.scroll_files_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.placeholder_label = ctk.CTkLabel(
            self.scroll_files_frame,
            text="No files scanned yet. Click 'Analyze' to scan page(s). | لم يتم فحص اي روابط بعد.",
            font=ui_font(11),
            text_color=M3["on_surface_variant"]
        )
        self.placeholder_label.pack(pady=24)

        # ----------------------------------
        # Card 6: Overall progress
        # ----------------------------------
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=24, pady=(2, 4))

        self.progress = WavyProgressBar(
            progress_frame,
            height=16,
            progress_color=M3["primary"],
            track_color=M3["outline_variant"],
            surface_color=M3["surface"],
            amplitude=3.0,
            wavelength=38,
            thickness=4.5,
            speed=46.0,
        )
        self.progress.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=2)
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="0%",
            font=ui_font(11, "bold"),
            width=48,
            text_color=M3["primary"]
        )
        self.progress_label.pack(side="right")

        # ----------------------------------
        # Card 7: Console log
        # ----------------------------------
        self.log_box = ctk.CTkTextbox(
            self,
            font=("Consolas", 11),
            wrap="word",
            fg_color=M3["surface_container_lowest"],
            border_color=M3["outline_variant"],
            text_color=M3["on_surface_variant"],
            border_width=1,
            corner_radius=RADIUS["md"]
        )
        self.log_box.pack(fill="both", expand=True, padx=24, pady=(0, 12))

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
        self._apply_proxy(self.settings)

        # Canvas-based wavy bars need an explicit repaint after theme switches.
        try:
            self.progress.refresh_theme()
            for item in self.download_item_widgets.values():
                item.progress_bar.set_surface(item.cget("fg_color"))
        except Exception:
            pass

    def bind_shortcuts(self):
        """Registers global keyboard shortcuts for power users."""
        self.bind_all("<Control-o>", lambda e: self.open_destination_folder())
        self.bind_all("<Control-s>", lambda e: self.open_settings_dialog())
        self.bind_all("<F5>", lambda e: self.analyze())
        self.bind_all("<Control-u>", lambda e: self.manual_check_updates())

    def _apply_proxy(self, settings):
        proxy = (settings or {}).get("proxy", "") or ""
        proxy = proxy.strip()
        if proxy:
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy
            os.environ["ALL_PROXY"] = proxy
        else:
            for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                os.environ.pop(key, None)

    def _expected_file_path(self, item, index):
        """Returns the path where an item is (or would be) downloaded."""
        try:
            folder = self.folder_entry.get().strip() or self.selected_save_path
            try:
                # Keep the number shown in the checklist, exactly like the
                # downloader does.
                file_idx = int(item.get("orig_index", index))
            except (TypeError, ValueError):
                file_idx = index
            raw_type = item.get("type", "PDF").upper()
            ext = raw_type.lower()
            if ext in ("gdrive", "mediafire"):
                ext = "pdf"
            title = clean_filename(item.get("title", f"Document_{index}"))
            filename = fit_filename(folder, f"{file_idx:02d}_{title}.{ext}")
            return os.path.join(folder, filename)
        except Exception:
            return None

    def _enable_dnd(self):
        """Enables drag & drop of text/URLs onto the URL and batch inputs."""
        targets = []
        if hasattr(self, "url_entry"):
            targets.append(self.url_entry)
        if hasattr(self, "batch_textbox"):
            targets.append(self.batch_textbox)
        for widget in targets:
            try:
                widget.drop_target_register(DND_TEXT, DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _on_drop(self, event):
        data = getattr(event, "data", "") or ""
        # tkinterdnd2 wraps file lists in braces; extract plain text/urls.
        text = data.strip()
        if text.startswith("{") and text.endswith("}"):
            text = text[1:-1]
        # If a .txt file was dropped, read its contents.
        if text.lower().endswith(".txt") and os.path.isfile(text):
            try:
                with open(text, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                pass
        try:
            if hasattr(self, "url_entry") and self.url_entry.winfo_containing(event.x_root, event.y_root) is self.url_entry:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, text.strip().splitlines()[0] if text.strip() else "")
                return
        except Exception:
            pass
        try:
            self.batch_textbox.delete("1.0", "end")
            self.batch_textbox.insert("1.0", text)
        except Exception:
            pass

    def _setup_tray(self):
        self._tray_icon = None
        self._quitting = False
        icon_path = os.path.join(ASSETS_DIR, "logo.png")
        try:
            image = _PILImage.open(icon_path) if os.path.exists(icon_path) else _PILImage.new("RGB", (64, 64), (79, 70, 229))
        except Exception:
            image = _PILImage.new("RGB", (64, 64), (79, 70, 229))

        def on_show(icon, item):
            self.after(0, self._show_from_tray)

        def on_quit(icon, item):
            self._quitting = True
            try:
                icon.stop()
            except Exception:
                pass
            self.after(0, self.destroy)

        menu = pystray.Menu(
            pystray.MenuItem("Show Waraqat | إظهار", on_show, default=True),
            pystray.MenuItem("Quit | خروج", on_quit),
        )
        self._tray_icon = pystray.Icon("Waraqat", image, "Waraqat | ورقات", menu)

        def run_icon():
            try:
                self._tray_icon.run()
            except Exception:
                pass

        import threading
        threading.Thread(target=run_icon, daemon=True).start()

    def _show_from_tray(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def destroy(self):
        """Stops the tray icon before tearing down the Tk application."""
        try:
            if getattr(self, "_tray_icon", None):
                self._tray_icon.stop()
                self._tray_icon = None
        except Exception:
            pass
        try:
            super().destroy()
        except Exception:
            pass

    def _on_close_to_tray(self):
        if getattr(self, "_quitting", False):
            try:
                if getattr(self, "_tray_icon", None):
                    self._tray_icon.stop()
            except Exception:
                pass
            self.destroy()
            return
        # Hide to tray instead of closing.
        try:
            self.withdraw()
        except Exception:
            self.destroy()

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

        # Reset filter bar (restore the placeholder that delete() removes)
        if self.filter_entry is not None:
            self.filter_entry.delete(0, "end")
            try:
                self.filter_entry._activate_placeholder()
            except Exception:
                pass
        self.active_type_filters = set()
        self._refresh_pill_styles()

        if not files:
            lbl = ctk.CTkLabel(
                self.scroll_files_frame,
                text="No files found in scanned page(s). | لم يتم العثور على ملفات.",
                text_color=("gray50", "#64748B")
            )
            lbl.pack(pady=20)
            return

        for i, item in enumerate(files, start=1):
            var = self.file_vars[i - 1]
            self.checkbox_vars.append(var)

            # Create interactive DownloadItem widget
            item_widget = DownloadItem(
                self.scroll_files_frame, i, item, var,
                open_resolver=lambda it=item, idx=i: self._expected_file_path(it, idx)
            )
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

    def _type_counts(self):
        """Number of discovered files per type, used in the chip labels."""
        counts = {}
        for item in getattr(self, "files", None) or []:
            file_type = str(item.get("type", "")).upper()
            if file_type:
                counts[file_type] = counts.get(file_type, 0) + 1
        return counts

    def _chip_label(self, type_key):
        """Base bilingual label plus a live count for type chips."""
        base = self.type_filter_labels.get(type_key, type_key)
        if type_key == "ALL":
            return base
        count = self._type_counts().get(type_key, 0)
        return f"{base} · {count}" if count else base

    def _refresh_pill_styles(self):
        """Unified Material 3 filter-chip styling (no per-type colours)."""
        for type_key, btn in self.type_filter_buttons.items():
            selected = (
                (type_key == "ALL" and not self.active_type_filters)
                or (type_key != "ALL" and type_key in self.active_type_filters)
            )
            try:
                btn.configure(
                    text=self._chip_label(type_key),
                    image=check_icon() if selected else None,
                    compound="left",
                )
                if selected:
                    btn.configure(
                        fg_color=M3["secondary_container"],
                        hover_color=M3["secondary_hover"],
                        text_color=M3["on_secondary_container"],
                        border_width=0,
                    )
                else:
                    btn.configure(
                        fg_color="transparent",
                        hover_color=M3["surface_container_high"],
                        text_color=M3["on_surface_variant"],
                        border_width=1,
                        border_color=M3["outline_variant"],
                    )
            except Exception:
                pass

    def filter_files(self, event=None):
        """Filter self.files by search text and active type filters, then redraw."""
        if not self.files:
            return

        search_text = ""
        if self.filter_entry is not None:
            # Ignore the placeholder text; it is stored as real entry content.
            if not getattr(self.filter_entry, "_placeholder_text_active", False):
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
                text_color=("gray50", "#64748B")
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

            item_widget = DownloadItem(
                self.scroll_files_frame, orig_idx_1, item, var,
                open_resolver=lambda it=item, idx=orig_idx_1: self._expected_file_path(it, idx)
            )
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
    def _skip_update(self, version_tag):
        self.settings["skipped_update_version"] = version_tag
        try:
            save_settings(self.settings)
        except Exception:
            pass
        self.log(f"[*] Skipped version {version_tag}. | تم تخطي الإصدار {version_tag}.")

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
                    downloaded = event.get("downloaded", 0)
                    total = event.get("total", 0)
                    filepath = event.get("filepath")
                    if idx in self.download_item_widgets:
                        self.download_item_widgets[idx].update_state(status, pct, downloaded, total, filepath)

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
                    self.progress.stop()
                    self.analyze_btn.configure(state="normal")
                    self.download_btn.configure(state="normal", text="Download Selected | بدء تنزيل المحدد")
                    self.cancel_btn.configure(state="disabled")
                    self.is_working = False

                elif event_type == "update_result":
                    manual = event.get("manual", False)
                    latest_tag = event.get("latest_tag")
                    download_url = event.get("download_url")
                    release_notes = event.get("release_notes", "")
                    sha256 = event.get("sha256")

                    if manual:
                        self.update_btn.configure(state="normal", text="فحص التحديثات | Updates")

                    if latest_tag and download_url:
                        if manual:
                            self.log(f"[+] Update available: {latest_tag}")
                        UpdateModal(self, latest_tag, download_url, release_notes, sha256=sha256,
                                   skip_callback=self._skip_update)
                    elif manual:
                        status = release_notes or ""
                        if status == "up_to_date":
                            self.log("[+] Waraqat is up to date! (أنت تستخدم أحدث إصدار)")
                            UpdateResultModal(self, "محدّث | Up to date",
                                             "أنت تستخدم أحدث إصدار من ورقات.\nYou are using the latest version of Waraqat.",
                                             "info")
                        elif status == "skipped":
                            self.log("[*] This version was skipped. | تم تخطي هذا الإصدار.")
                        elif status == "no_asset":
                            self.log("[!] The latest release does not include a Waraqat.exe asset.")
                            UpdateResultModal(self, "لا يوجد ملف تحديث | No update file",
                                             "الإصدار الأحدث لا يحتوي على ملف Waraqat.exe.\nThe latest release has no Waraqat.exe asset.",
                                             "warn")
                        elif status == "rate_limit":
                            self.log("[!] GitHub rate limit reached.")
                            UpdateResultModal(self, "حد GitHub | Rate limit",
                                             "تم تجاوز حد طلبات GitHub. حاول لاحقاً.\nGitHub rate limit reached. Try again later.",
                                             "error")
                        elif status == "not_found":
                            self.log("[!] Release not found.")
                            UpdateResultModal(self, "غير موجود | Not found",
                                             "لم يتم العثور على الإصدار.\nRelease not found.",
                                             "error")
                        else:
                            self.log("[!] Unable to reach GitHub releases or check updates.")
                            UpdateResultModal(self, "فشل الفحص | Check failed",
                                             "تعذر الوصول إلى GitHub أو فحص التحديثات.\nUnable to reach GitHub releases.",
                                             "error")

            except queue.Empty:
                break

        self.after(50, self.process_events)

    def update_item_progress(self, index, status, percent=0.0, downloaded=0, total=0, filepath=None):
        self.event_queue.put({
            "type": "item_progress",
            "index": index,
            "status": status,
            "percent": percent,
            "downloaded": downloaded,
            "total": total,
            "filepath": filepath
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
        self.progress.stop()
        self.progress.set(0)
        self.progress_label.configure(text="0%")

        threading.Thread(target=self._analyze_worker, args=(urls_to_scan,), daemon=True).start()

    def _analyze_worker(self, urls):
        try:
            if len(urls) == 1:
                url = urls[0]
                self.log(f"[*] Scanning webpage: {url}")
                site_name = get_site_name(url)
                self.log(f"[*] Domain detected: {site_name}")
                files = extract_files(url)
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
        self.progress.start()

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


if _HAS_DND:
    try:
        App.__bases__ = (ctk.CTk, TkinterDnD.DnDWrapper)
    except Exception:
        pass
