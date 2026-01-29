[app]
# (str) Title of your application
title = Team Nezarat

# (str) Package name
package.name = teamnezarat

# (str) Package domain (needed for android packaging)
package.domain = ir.mafia

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,json,kv

# (str) Application versioning (method 1)
version = 0.1

# (list) Application requirements
# قفل کردن نسخه کیوی و سایفون برای پایداری در گیت‌هاب
requirements = python3,kivy==2.1.0,requests,urllib3,certifi,chardet,idna,Cython==0.29.33

# (str) Custom source folders for requirements
# (list) Permissions
android.permissions = INTERNET

# (int) Target Android API, should be as high as possible.
android.api = 31

# (int) Minimum API your APK will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (bool) use posix to build (needed for github actions)
android.accept_sdk_license = True

# (str) The Android arch to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = armeabi-v7a

# (str) Icon of the application
icon.filename = logo.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Fullscreen mode
fullscreen = 0

[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = off, 1 = on)
warn_on_root = 0
