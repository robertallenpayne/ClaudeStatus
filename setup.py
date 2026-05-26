"""py2app build configuration for Claude Status widget."""

from setuptools import setup
import os

APP = ["widget.py"]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon.icns",
    "plist": {
        "CFBundleName": "Claude Status",
        "CFBundleDisplayName": "Claude Status",
        "CFBundleIdentifier": "com.robertallenpayne.claude-status",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "LSUIElement": True,          # hides from Dock while running (widget style)
        "NSHighResolutionCapable": True,
    },
    # Pull in customtkinter (with its assets: fonts, themes) and its dep
    "packages": ["customtkinter", "packaging", "darkdetect"],
    "excludes": ["tkinter.test", "unittest", "email", "html", "http", "xml",
                 "xmlrpc", "pydoc", "doctest", "difflib"],
}

setup(
    name="Claude Status",
    app=APP,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
