#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CUDA 变体构建准备脚本。

在 flet build 前调用，用于：
1. 将 CUDA_VARIANT 信息写入 app_config.py
2. 修改 pyproject.toml 中的 onnxruntime 依赖为对应的 CUDA 版本

用法：
    python scripts/prepare_cuda_variant.py          # 标准版（不做修改）
    python scripts/prepare_cuda_variant.py cuda      # CUDA 版
    python scripts/prepare_cuda_variant.py cuda_full # CUDA Full 版
"""

import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
APP_CONFIG_FILE = PROJECT_ROOT / "src" / "constants" / "app_config.py"
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"


def write_cuda_variant_to_config(variant: str) -> None:
    """将 CUDA 变体信息写入 app_config.py"""
    print(f"[1/2] 写入 CUDA 变体到 app_config.py: {variant}")
    
    content = APP_CONFIG_FILE.read_text(encoding="utf-8")
    pattern = r'BUILD_CUDA_VARIANT:\s*Final\[str\]\s*=\s*"[^"]*"'
    replacement = f'BUILD_CUDA_VARIANT: Final[str] = "{variant}"'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content == content and variant != "none":
        print(f"  警告: 未找到 BUILD_CUDA_VARIANT 定义，跳过")
        return
    
    APP_CONFIG_FILE.write_text(new_content, encoding="utf-8")
    print(f"  已设置 BUILD_CUDA_VARIANT = \"{variant}\"")


def update_pyproject_for_cuda(variant: str) -> None:
    """修改 pyproject.toml 中的 onnxruntime 依赖"""
    if variant == "none":
        print("[2/2] 标准版，无需修改依赖")
        return
    
    print(f"[2/2] 修改 pyproject.toml 依赖为 CUDA 版本: {variant}")
    
    content = PYPROJECT_FILE.read_text(encoding="utf-8")
    
    # 移除 onnxruntime-directml 和 onnxruntime 的行
    lines = content.split("\n")
    new_lines = []
    ort_cuda_added = False
    
    for line in lines:
        stripped = line.strip().strip('"').strip("'").strip(",")
        
        # 跳过现有的 onnxruntime 相关依赖
        if any(pkg in stripped for pkg in [
            "onnxruntime-directml",
            "onnxruntime==",
            "onnxruntime>",
            "onnxruntime<",
        ]):
            # 在第一个被移除的行位置插入新依赖
            if not ort_cuda_added:
                if variant == "cuda":
                    new_lines.append('  "onnxruntime-gpu==1.22.0",')
                elif variant == "cuda_full":
                    new_lines.append('  "onnxruntime-gpu[cuda,cudnn]==1.22.0",')
                ort_cuda_added = True
                print(f"  已替换 onnxruntime 依赖")
            # 跳过原始行
            continue
        
        new_lines.append(line)
    
    new_content = "\n".join(new_lines)
    PYPROJECT_FILE.write_text(new_content, encoding="utf-8")
    print(f"  pyproject.toml 已更新")


def main():
    # 从命令行参数或环境变量获取变体
    if len(sys.argv) > 1:
        variant = sys.argv[1].lower()
    else:
        variant = os.environ.get("CUDA_VARIANT", "none").lower()
    
    # 验证
    if variant not in ("none", "cuda", "cuda_full"):
        print(f"错误: 无效的 CUDA 变体 '{variant}'，有效值: none, cuda, cuda_full")
        sys.exit(1)
    
    print(f"=== 准备 CUDA 变体: {variant} ===")
    
    write_cuda_variant_to_config(variant)
    update_pyproject_for_cuda(variant)
    
    print(f"=== 完成 ===\n")


if __name__ == "__main__":
    main()
