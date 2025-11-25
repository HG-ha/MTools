@REM 开发快速编译版本 - 编译速度优先
@REM conda activate mytoolsbuild

python -m nuitka ^
    --standalone ^
    --windows-icon-from-ico=src/assets/icon2.png ^
    --assume-yes-for-downloads ^
    --include-data-dir=bin=bin ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/cjpeg.exe=bin/windows/mozjpeg/shared/Release/cjpeg.exe ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/djpeg.exe=bin/windows/mozjpeg/shared/Release/djpeg.exe ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/jpegtran.exe=bin/windows/mozjpeg/shared/Release/jpegtran.exe ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/rdjpgcom.exe=bin/windows/mozjpeg/shared/Release/rdjpgcom.exe ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/wrjpgcom.exe=bin/windows/mozjpeg/shared/Release/wrjpgcom.exe ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/jpeg62.dll=bin/windows/mozjpeg/shared/Release/jpeg62.dll ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/turbojpeg.dll=bin/windows/mozjpeg/shared/Release/turbojpeg.dll ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/libpng16.dll=bin/windows/mozjpeg/shared/Release/libpng16.dll ^
    --include-data-files=bin/windows/mozjpeg/shared/Release/zlib1.dll=bin/windows/mozjpeg/shared/Release/zlib1.dll ^
    --include-data-files=bin/windows/pngquant/pngquant/pngquant.exe=bin/windows/pngquant/pngquant/pngquant.exe ^
    --include-data-dir=src/assets=src/assets ^
    --nofollow-import-to=tkinter ^
    --nofollow-import-to=unittest ^
    --nofollow-import-to=test ^
    --nofollow-import-to=pytest ^
    --nofollow-import-to=setuptools ^
    --nofollow-import-to=distutils ^
    --nofollow-import-to=wheel ^
    --nofollow-import-to=pip ^
    --output-dir=dist ^
    --output-filename=mytools.exe ^
    --jobs=8 ^
    --low-memory ^
    --remove-output ^
    --python-flag=-O ^
    src/main.py
