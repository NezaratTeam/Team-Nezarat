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

# (str) Application versioning
version = 0.2

# (list) Application requirements
# قفل کردن نسخه‌ها برای پایداری در محیط گیت‌هاب
requirements = python3,kivy==2.2.1,requests,urllib3,certifi,chardet,idna

# (list) Permissions
android.permissions = INTERNET

# (int) Target Android API (مطابق با جاوا ۱۷ در فایل yml)
android.api = 33

# (int) Minimum API your APK will support
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 25b

# (bool) use posix to build (تایید خودکار لایسنس برای حل مشکل Broken pipe)
android.accept_sdk_license = True

# (str) The Android arch to build for
android.archs = armeabi-v7a

# (str) Icon of the application (مطمئن شو فایل logo.png در گیت‌هاب هست)
icon.filename = logo.png

# (str) Supported orientation
orientation = portrait

# (bool) Fullscreen mode
fullscreen = 0

[buildozer]
# (int) Log level (2 برای دیدن تمام جزئیات در صورت خطا)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 0
