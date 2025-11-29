@REM conda activate mytoolsbuild

conda run -n mytoolsbuild python -m nuitka ^
    --standalone ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=src/assets/icon.ico ^
    --product-name="MyTools" ^
    --file-version=0.1.1.0 ^
    --product-version=0.1.1 ^
    --file-description="MyTools - Multi-functional desktop tool" ^
    --company-name="HG-ha" ^
    --copyright="Copyright (C) 2025 by HG-ha" ^
    --assume-yes-for-downloads ^
    --include-data-dir=src/assets=src/assets ^
    --follow-imports ^
    --nofollow-import-to=tkinter ^
    --nofollow-import-to=unittest ^
    --nofollow-import-to=test ^
    --nofollow-import-to=pytest ^
    --nofollow-import-to=setuptools ^
    --nofollow-import-to=distutils ^
    --nofollow-import-to=wheel ^
    --nofollow-import-to=pip ^
    --nofollow-import-to=IPython ^
    --nofollow-import-to=matplotlib ^
    --output-dir=dist/release ^
    --output-filename=MyTools.exe ^
    --enable-plugin=upx ^
    --onefile-no-compression ^
    --python-flag=-O ^
    --python-flag=no_site ^
    --python-flag=no_warnings ^
    src/main.py

@REM 重命名文件夹为MyTools_x64
move dist\release\main.dist dist\release\MyTools_x64

@REM 进入目录后打包zip，这样zip内部就不会有多余的路径层级
cd dist\release
zip -r MyTools_x64.zip MyTools_x64
cd ..\..