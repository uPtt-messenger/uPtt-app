# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 需要明確加入的隱藏依賴項
hidden_imports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'PyPtt',
]

a = Analysis(
    ['src/run_app.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
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
    [],
    exclude_binaries=True, # 不要在 exe 裡面包二進位檔
    name='uPttTerm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# 使用 COLLECT 模式，將程式庫與執行檔放在同一個目錄
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='uPttTerm',
)

app = BUNDLE(
    coll, # 打包 COLLECT 出來的目錄
    name='uPttTerm.app',
    icon=None,
    bundle_identifier='com.uptt.messenger.uPttTerm',
)
