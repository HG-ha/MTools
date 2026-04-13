#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CUDA 变体构建准备脚本。

在 flet build 前调用，用于：
1. 将 CUDA_VARIANT 信息写入 app_config.py
2. 修改 pyproject.toml 中的 onnxruntime / sherpa-onnx 依赖为对应的 CUDA 版本

sherpa-onnx CUDA 轮子托管在 k2-fsa 的自定义索引上，pip 需要 --find-links 才能定位。
脚本会自动向 pyproject.toml 追加 [[tool.uv.find-links]] 段（供 uv sync 使用），
并在 flet_build.py 中通过 PIP_FIND_LINKS 环境变量传递给 pip。

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

SHERPA_CUDA_FIND_LINKS = "https://k2-fsa.github.io/sherpa/onnx/cuda.html"


def write_cuda_variant_to_config(variant: str) -> None:
    """将 CUDA 变体信息写入 app_config.py"""
    print(f"[1/3] 写入 CUDA 变体到 app_config.py: {variant}")

    content = APP_CONFIG_FILE.read_text(encoding="utf-8")
    pattern = r'BUILD_CUDA_VARIANT:\s*Final\[str\]\s*=\s*"[^"]*"'
    replacement = f'BUILD_CUDA_VARIANT: Final[str] = "{variant}"'

    new_content = re.sub(pattern, replacement, content)

    if new_content == content and variant != "none":
        print("  警告: 未找到 BUILD_CUDA_VARIANT 定义，跳过")
        return

    APP_CONFIG_FILE.write_text(new_content, encoding="utf-8")
    print(f'  已设置 BUILD_CUDA_VARIANT = "{variant}"')


def update_pyproject_for_cuda(variant: str) -> None:
    """修改 pyproject.toml 中的 onnxruntime 和 sherpa-onnx 依赖"""
    if variant == "none":
        print("[2/3] 标准版，无需修改依赖")
        return

    print(f"[2/3] 修改 pyproject.toml 依赖为 CUDA 版本: {variant}")

    content = PYPROJECT_FILE.read_text(encoding="utf-8")
    lines = content.split("\n")
    new_lines: list[str] = []
    ort_cuda_added = False
    sherpa_cuda_added = False

    for line in lines:
        stripped = line.strip().strip('"').strip("'").strip(",")

        # ---- onnxruntime 替换 ----
        if any(pkg in stripped for pkg in [
            "onnxruntime-directml",
            "onnxruntime==",
            "onnxruntime>",
            "onnxruntime<",
        ]):
            if not ort_cuda_added:
                if variant == "cuda":
                    new_lines.append('  "onnxruntime-gpu==1.24.4",')
                elif variant == "cuda_full":
                    new_lines.append('  "onnxruntime-gpu[cuda,cudnn]==1.24.4",')
                ort_cuda_added = True
                print("  已替换 onnxruntime 依赖")
            continue

        # ---- sherpa-onnx 替换 ----
        # +cuda = CUDA 11 + cuDNN 8（需用户自装 CUDA 11）
        # +cuda12.cudnn9 = CUDA 12 + cuDNN 9（与 onnxruntime-gpu 1.24 匹配）
        if re.match(r'^\s*"sherpa-onnx[=<>!]', line):
            if not sherpa_cuda_added:
                ver = _extract_sherpa_version(stripped)
                if variant == "cuda":
                    sherpa_suffix = "cuda12.cudnn9"
                elif variant == "cuda_full":
                    sherpa_suffix = "cuda12.cudnn9"
                else:
                    sherpa_suffix = "cuda"
                new_lines.append(f'  "sherpa-onnx=={ver}+{sherpa_suffix}",')
                sherpa_cuda_added = True
                print(f"  已替换 sherpa-onnx 依赖 → {ver}+{sherpa_suffix}")
            continue

        new_lines.append(line)

    new_content = "\n".join(new_lines)
    PYPROJECT_FILE.write_text(new_content, encoding="utf-8")
    print("  pyproject.toml 已更新")


def add_find_links(variant: str) -> None:
    """向 pyproject.toml 追加 [[tool.uv.find-links]] 段（如果尚不存在）。"""
    if variant == "none":
        print("[3/3] 标准版，无需添加 find-links")
        return

    print("[3/3] 添加 sherpa-onnx CUDA find-links")

    content = PYPROJECT_FILE.read_text(encoding="utf-8")

    if SHERPA_CUDA_FIND_LINKS in content:
        print("  find-links 已存在，跳过")
        return

    block = (
        "\n"
        "[[tool.uv.find-links]]\n"
        f'url = "{SHERPA_CUDA_FIND_LINKS}"\n'
    )
    content += block
    PYPROJECT_FILE.write_text(content, encoding="utf-8")
    print(f"  已添加 [[tool.uv.find-links]] → {SHERPA_CUDA_FIND_LINKS}")


def _extract_sherpa_version(dep_str: str) -> str:
    """从依赖字符串中提取 sherpa-onnx 版本号。"""
    m = re.search(r"sherpa-onnx[=<>!]=*(\d+\.\d+\.\d+)", dep_str)
    if m:
        return m.group(1)
    return "1.12.35"


def main():
    if len(sys.argv) > 1:
        variant = sys.argv[1].lower()
    else:
        variant = os.environ.get("CUDA_VARIANT", "none").lower()

    if variant not in ("none", "cuda", "cuda_full"):
        print(f"错误: 无效的 CUDA 变体 '{variant}'，有效值: none, cuda, cuda_full")
        sys.exit(1)

    print(f"=== 准备 CUDA 变体: {variant} ===")

    write_cuda_variant_to_config(variant)
    update_pyproject_for_cuda(variant)
    add_find_links(variant)

    if variant != "none":
        print()
        print("提示: flet build 时请确保 pip 能访问 sherpa-onnx CUDA 轮子:")
        print(f"  set PIP_FIND_LINKS={SHERPA_CUDA_FIND_LINKS}")
        print("  或使用 flet_build.py（已自动处理）")

    print(f"\n=== 完成 ===\n")


if __name__ == "__main__":
    main()
