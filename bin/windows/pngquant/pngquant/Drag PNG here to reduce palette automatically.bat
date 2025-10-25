@echo off

set path=%~d0%~p0

:start

"%path%pngquant.exe" --force --verbose --quality=45-85 %1
"%path%pngquant.exe" --force --verbose --ordered --speed=1 --quality=50-90 %1

shift
if NOT x%1==x goto start
