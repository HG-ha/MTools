"""检查 build/windows/ 下所有 DLL/EXE 的 CPU 架构。
0xc000007b 的常见原因是 32/64 位混用，此脚本快速定位。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pefile  # type: ignore

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TARGET_DIR = Path(__file__).resolve().parent.parent / "build" / "windows"

MACHINE_NAMES = {
    0x014c: "x86 (32-bit)",
    0x8664: "x64 (AMD64)",
    0x01c0: "ARM",
    0xaa64: "ARM64",
    0x0200: "IA64",
}


def main() -> int:
    if not TARGET_DIR.is_dir():
        print(f"目录不存在: {TARGET_DIR}")
        return 1

    files = sorted(
        [p for p in TARGET_DIR.iterdir() if p.suffix.lower() in (".exe", ".dll")],
        key=lambda p: p.name.lower(),
    )

    arch_counts: dict[str, int] = {}
    mismatches = []

    for f in files:
        try:
            pe = pefile.PE(str(f), fast_load=True)
            machine = pe.FILE_HEADER.Machine
            pe.close()
            arch = MACHINE_NAMES.get(machine, f"unknown (0x{machine:04x})")
        except Exception as e:
            arch = f"<failed: {e}>"

        arch_counts[arch] = arch_counts.get(arch, 0) + 1
        marker = ""
        if arch != "x64 (AMD64)":
            marker = "  ⚠️  非 x64"
            mismatches.append((f.name, arch))
        print(f"  {f.name:<50} {arch}{marker}")

    print()
    print("=" * 70)
    print("架构统计:")
    for arch, cnt in sorted(arch_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {arch:<25} {cnt} 个")

    print()
    if mismatches:
        print(f"⚠️  发现 {len(mismatches)} 个非 x64 文件，很可能是 0xc000007b 根源:")
        for name, arch in mismatches:
            print(f"  - {name}: {arch}")
        return 2
    else:
        print("✅ 所有 EXE/DLL 都是 x64，不是位数问题。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
