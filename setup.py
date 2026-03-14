from setuptools import setup

APP = ["src/dsfm_app.py"]

OPTIONS = {
    "argv_emulation": False,
    "includes": ["dsfm"],
    "packages": ["rumps"],
    "iconfile": "assets/icons/AppIcon.jpg",
    "plist": {
        "CFBundleName": "DSFM",
        "CFBundleDisplayName": "DualSense for Mac",
        "CFBundleIdentifier": "xyz.brc.dsfm",
        "CFBundleVersion": "0.2.0",
        "CFBundleShortVersionString": "0.2.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSUserNotificationAlertStyle": "banner",
    },
}

setup(
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
