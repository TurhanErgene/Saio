# PyInstaller spec for Saio. Build: pyinstaller saio.spec  ->  dist/Saio.exe
a = Analysis(
    ["main.py"],
    datas=[("saio/assets", "saio/assets")],
    excludes=["numpy", "PIL", "pyautogui", "tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="Saio",
    icon="saio/assets/saio.ico",
    version="version_info.txt",
    console=False,
    upx=False,  # UPX-packed exes trigger more antivirus false positives
)
