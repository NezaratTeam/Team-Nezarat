[app]
title = Team Nezarat
package.name = teamnezarat
package.domain = ir.mafia
source.dir = .
source.include_exts = py,png,jpg,json,kv
version = 0.1
requirements = python3,kivy==2.2.1,requests,urllib3,certifi,chardet,idna
android.permissions = INTERNET
android.api = 31
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = armeabi-v7a
icon.filename = logo.png
orientation = portrait
fullscreen = 0
[buildozer]
log_level = 2
warn_on_root = 0
