# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Collect all customtkinter internal assets
ct_datas, ct_binaries, ct_hiddenimports = collect_all('customtkinter')

# Collect arabic_reshaper data
ar_datas, ar_binaries, ar_hiddenimports = collect_all('arabic_reshaper')

a = Analysis(
    ['main.py'],
    pathex=[r'C:\Users\Administrator\Desktop\UniversalDownloader'],
    binaries=ct_binaries + ar_binaries,
    datas=[
        ('assets', 'assets'),
        ('requirements.txt', '.'),
    ] + ct_datas + ar_datas,
    hiddenimports=ct_hiddenimports + ar_hiddenimports + [
        'arabic_reshaper',
        'bidi',
        'bidi.algorithm',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'tqdm',
        'customtkinter',
        'requests',
        'requests.adapters',
        'requests.auth',
        'requests.compat',
        'requests.cookies',
        'requests.exceptions',
        'requests.hooks',
        'requests.models',
        'requests.packages',
        'requests.sessions',
        'requests.structures',
        'requests.utils',
        'bs4',
        'bs4.builder',
        'bs4.builder._htmlparser',
        'bs4.builder._lxml',
        'urllib3',
        'urllib3.util',
        'urllib3.util.retry',
        'urllib3.contrib',
        'certifi',
        'charset_normalizer',
        'idna',
        'lxml',
        'lxml.etree',
        'lxml.html',
        'html.parser',
        'threading',
        'queue',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'json',
        'os',
        'sys',
        'pathlib',
        're',
        'time',
        'concurrent',
        'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Waraqat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\waraqat_icon.ico',
)
