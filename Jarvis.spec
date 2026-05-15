# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Alle rumps/PyObjC Abhängigkeiten einsammeln
datas = [
    ('templates',       'templates'),
    ('static',          'static'),
    ('modes',           'modes'),
]
datas += collect_data_files('rumps')
datas += collect_data_files('flask')
datas += collect_data_files('jinja2')
datas += collect_data_files('anthropic')

hiddenimports = [
    'rumps', 'flask', 'flask.templating',
    'jinja2', 'jinja2.ext',
    'requests', 'urllib3',
    'anthropic',
    'password_vault', 'evaluator', 'computer',
    'dashboard_app', 'menubar', 'feedback', 'native_window', 'updater',
    'AppKit', 'Foundation', 'objc', 'WebKit',
]

a = Analysis(
    ['app_main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'PIL'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='Jarvis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Jarvis',
)

app = BUNDLE(
    coll,
    name='Jarvis.app',
    icon=None,
    bundle_identifier='com.jarvis.app',
    info_plist={
        'CFBundleName': 'Jarvis',
        'CFBundleDisplayName': 'MacBook Jarvis',
        'CFBundleVersion': '1.0.3',
        'CFBundleShortVersionString': '1.0.3',
        'NSHighResolutionCapable': True,
        'LSUIElement': True,          # Kein Dock-Icon — nur Menüleiste
        'NSRequiresAquaSystemAppearance': False,
        'LSMinimumSystemVersion': '12.0',
        'NSHumanReadableCopyright': 'Open Source',
        'NSAppTransportSecurity': {
            'NSAllowsLocalNetworking': True,
            'NSAllowsArbitraryLoads': True,
        },
    },
)
