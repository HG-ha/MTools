import subprocess
import sys
import warnings

# 屏蔽 libpng 警告
warnings.filterwarnings("ignore", message=".*iCCP.*")

if sys.platform == "win32":
    # 保存原始 Popen
    _original_popen = subprocess.Popen

    class NoWindowPopen(_original_popen):
        def __init__(self, *args, **kwargs):
            # 如果用户没有显式传入 creationflags，则设置为 CREATE_NO_WINDOW
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            else:
                # 如果已有 creationflags，确保合并 CREATE_NO_WINDOW
                kwargs['creationflags'] |= subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    # 替换 subprocess.Popen
    subprocess.Popen = NoWindowPopen