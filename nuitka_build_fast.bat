@REM 超快速编译 - 仅用于快速测试
@REM conda activate mytoolsbuild

python -m nuitka ^
    --standalone ^
    --windows-console-mode=attach ^
    --assume-yes-for-downloads ^
    --include-data-dir=bin=bin ^
    --include-data-dir=src/assets=src/assets ^
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
    --output-dir=dist ^
    --output-filename=mytools_test.exe ^
    --jobs=8 ^
    --low-memory ^
    --remove-output ^
    src/main.py

