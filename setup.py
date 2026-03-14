from setuptools import setup

APP = ["src/dsfm_app.py"]

OPTIONS = {
    "argv_emulation": False,
    "includes": ["dsfm"],
    "packages": ["rumps"],
    "iconfile": "assets/icons/AppIcon.png",
    "resources": [
        "assets/icons/icon_menubar_active.png",
        "assets/icons/icon_menubar_active@2x.png",
        "assets/icons/icon_menubar_inactive.png",
        "assets/icons/icon_menubar_inactive@2x.png",
    ],
    "plist": {
        "CFBundleName": "DSFM",
        "CFBundleDisplayName": "DualSense for Mac",
        "CFBundleIdentifier": "xyz.brc.dsfm",
        "CFBundleVersion": "0.1.1",
        "CFBundleShortVersionString": "0.1.1",
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
