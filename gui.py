import os
import queue
import threading
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

        self.build_ui()
        self.after(50, self.process_events)

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
            font=("Segoe UI", 24, "bold"),
            text_color="#F8FAFC"
        )
        app_title.pack(anchor="w")

        app_sub = ctk.CTkLabel(
            titles_box,
            text=APP_SUBTITLE,
            font=("Segoe UI", 12),
            text_color="#94A3B8"
        )
        app_sub.pack(anchor="w")

        # Version Pill Badge
        version_pill = ctk.CTkLabel(
            header_card,
            text=f"v{APP_VERSION}",
            font=("Segoe UI", 11, "bold"),
            fg_color="#1E293B",
            text_color="#38BDF8",
            corner_radius=12,
            padx=12,
            pady=4
        )
        version_pill.pack(side="right")

        # ----------------------------------
        # Card 1: Input URL Tabs
        # ----------------------------------
        self.tabview = ctk.CTkTabview(
            self,
            height=125,
            corner_radius=10,
            fg_color="#1E222B",
            segmented_button_fg_color="#12151C",
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
            fg_color="#12151C",
            border_color="#334155",
            border_width=1
        )
        self.url_entry.pack(fill="x", padx=8, pady=8)

        # Batch Tab Textbox
        self.batch_textbox = ctk.CTkTextbox(
            self.tab_batch,
            height=65,
            font=("Consolas", 11),
            fg_color="#12151C",
            border_color="#334155",
            border_width=1
        )
        self.batch_textbox.pack(fill="both", expand=True, padx=8, pady=4)
        self.batch_textbox.insert("1.0", "# Paste multiple URLs (one per line) | الصق الروابط هنا (رابط في كل سطر)\n")

        # ----------------------------------
        # Card 2: Save Destination & Folder Tools
        # ----------------------------------
        folder_card = ctk.CTkFrame(self, corner_radius=10, fg_color="#1E222B", border_color="#334155", border_width=1)
        folder_card.pack(fill="x", padx=25, pady=(0, 8))

        folder_inner = ctk.CTkFrame(folder_card, fg_color="transparent")
        folder_inner.pack(fill="x", padx=12, pady=10)

        folder_label = ctk.CTkLabel(
            folder_inner,
            text="Save Location | مجلد الحفظ:",
            font=("Segoe UI", 12, "bold"),
            text_color="#E2E8F0"
        )
        folder_label.pack(side="left", padx=(0, 10))

        self.folder_entry = ctk.CTkEntry(
            folder_inner,
            height=34,
            font=("Segoe UI", 11),
            fg_color="#12151C",
            border_color="#334155"
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
            fg_color="#334155",
            hover_color="#475569",
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
            fg_color="#1E293B",
            hover_color="#334155",
            command=self.open_destination_folder
        )
        self.open_folder_btn.pack(side="left")

        # ----------------------------------
        # Card 3: Status & Concurrency Bar
        # ----------------------------------
        status_bar = ctk.CTkFrame(self, corner_radius=8, fg_color="#161922")
        status_bar.pack(fill="x", padx=25, pady=(0, 8))

        self.site_label = ctk.CTkLabel(
            status_bar,
            text="Domain | الموقع: -",
            font=("Segoe UI", 12),
            text_color="#94A3B8"
        )
        self.site_label.pack(side="left", padx=14, pady=6)

        self.files_label = ctk.CTkLabel(
            status_bar,
            text="Files | الملفات المكتشفة: 0",
            font=("Segoe UI", 12, "bold"),
            text_color="#38BDF8"
        )
        self.files_label.pack(side="left", padx=20, pady=6)

        # Concurrency selector
        threads_label = ctk.CTkLabel(
            status_bar,
            text="Threads | التنزيلات التزامنية:",
            font=("Segoe UI", 12),
            text_color="#94A3B8"
        )
        threads_label.pack(side="right", padx=(5, 8))

        current_workers = str(self.settings.get("max_workers", 5))
        self.threads_menu = ctk.CTkOptionMenu(
            status_bar,
            values=["2", "3", "5", "8", "10"],
            width=70,
            height=28,
            fg_color="#334155",
            button_color="#475569",
            button_hover_color="#64748B",
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
        list_container = ctk.CTkFrame(self, corner_radius=10, fg_color="#1E222B", border_color="#334155", border_width=1)
        list_container.pack(fill="x", padx=25, pady=(0, 8))

        list_header = ctk.CTkFrame(list_container, fg_color="transparent")
        list_header.pack(fill="x", padx=12, pady=(8, 4))

        list_title = ctk.CTkLabel(
            list_header,
            text="Discovered Files | قائمة الملفات المكتشفة:",
            font=("Segoe UI", 12, "bold"),
            text_color="#E2E8F0"
        )
        list_title.pack(side="left")

        self.btn_deselect_all = ctk.CTkButton(
            list_header,
            text="Deselect All | الغاء التحديد",
            width=125,
            height=26,
            font=("Segoe UI", 11),
            fg_color="#334155",
            hover_color="#475569",
            command=self.deselect_all_files
        )
        self.btn_deselect_all.pack(side="right", padx=(6, 0))

        self.btn_select_all = ctk.CTkButton(
            list_header,
            text="Select All | تحديد الكل",
            width=110,
            height=26,
            font=("Segoe UI", 11),
            fg_color="#334155",
            hover_color="#475569",
            command=self.select_all_files
        )
        self.btn_select_all.pack(side="right")

        self.scroll_files_frame = ctk.CTkScrollableFrame(list_container, height=140, fg_color="#12151C")
        self.scroll_files_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.placeholder_label = ctk.CTkLabel(
            self.scroll_files_frame,
            text="No files scanned yet. Click 'Analyze' to scan page(s). | لم يتم فحص اي روابط بعد.",
            text_color="#64748B"
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
            fg_color="#1E293B"
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
            fg_color="#12151C",
            border_color="#334155",
            border_width=1,
            corner_radius=10
        )
        self.log_box.pack(fill="both", expand=True, padx=25, pady=(0, 15))

    # ----------------------------------
    # Settings & Folder Operations
    # ----------------------------------
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
    # Checklist Management with Color Badges
    # ----------------------------------
    def update_file_checklist(self, files):
        for widget in self.scroll_files_frame.winfo_children():
            widget.destroy()

        self.checkbox_vars = []

        if not files:
            lbl = ctk.CTkLabel(
                self.scroll_files_frame,
                text="No files found in scanned page(s). | لم يتم العثور على ملفات.",
                text_color="#64748B"
            )
            lbl.pack(pady=20)
            return

        for i, item in enumerate(files, start=1):
            var = ctk.BooleanVar(value=True)
            self.checkbox_vars.append(var)

            row = ctk.CTkFrame(self.scroll_files_frame, fg_color="#181B22", corner_radius=6)
            row.pack(fill="x", padx=4, pady=3)

            # Checkbox
            cb = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                width=24,
                checkbox_width=20,
                checkbox_height=20,
                fg_color="#4F46E5",
                hover_color="#4338CA"
            )
            cb.pack(side="left", padx=(8, 4), pady=4)

            # Type Badge
            raw_type = item.get("type", "PDF").upper()
            badge_color = TYPE_COLORS.get(raw_type, "#475569")

            badge = ctk.CTkLabel(
                row,
                text=raw_type,
                font=("Segoe UI", 10, "bold"),
                fg_color=badge_color,
                text_color="#FFFFFF",
                corner_radius=6,
                padx=8,
                pady=2
            )
            badge.pack(side="left", padx=(0, 10))

            # Title
            title_lbl = ctk.CTkLabel(
                row,
                text=f"{i}. {item.get('title', 'Document')}",
                font=("Segoe UI", 11),
                text_color="#F1F5F9",
                anchor="w"
            )
            title_lbl.pack(side="left", fill="x", expand=True, padx=(0, 8))

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

                elif event_type == "analyze_done":
                    site = event["site"]
                    count = event["count"]
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

            except queue.Empty:
                break

        self.after(50, self.process_events)

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

            self.files = files
            self.log(f"[+] Scan completed! Found {len(files)} downloadable file(s).")

            self.event_queue.put({
                "type": "analyze_done",
                "site": site_name,
                "count": len(files)
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

        selected_files = [
            item for item, var in zip(self.files, self.checkbox_vars)
            if var.get()
        ]

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
        os.makedirs(target_folder, exist_ok=True)

        try:
            workers = int(self.threads_menu.get())
        except Exception:
            workers = 5

        self.is_working = True
        self.cancel_event.clear()

        self.analyze_btn.configure(state="disabled")
        self.download_btn.configure(state="disabled", text="Downloading... | جاري التحميل")
        self.cancel_btn.configure(state="normal")
        self.progress.set(0)
        self.progress_label.configure(text="0%")

        threading.Thread(
            target=self._download_worker,
            args=(selected_files, target_folder, workers),
            daemon=True
        ).start()

    def cancel_download(self):
        if self.is_working:
            self.cancel_event.set()
            self.log("[!] Cancellation signal sent. Halting active downloads...")
            self.cancel_btn.configure(state="disabled")

    def _download_worker(self, files_to_download, target_folder, workers):
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
                workers
            )

            if self.cancel_event.is_set():
                self.log("[!] Download was cancelled by user.")
            else:
                self.log("=" * 50)
                self.log("[+] All selected downloads finished successfully!")
                self.log(f"[+] All files are stored inside: {target_folder}")
                self.log("[+] Click 'Open | فتح' to view your downloaded files.")
                self.log("=" * 50)

        except Exception as e:
            self.log(f"[ERROR] Download worker error: {str(e)}")
        finally:
            self.event_queue.put({"type": "download_done"})


if __name__ == "__main__":
    app = App()
    app.mainloop()
