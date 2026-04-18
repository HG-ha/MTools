"""扫描 build/windows/ 下所有 DLL/EXE 的导入表，找出"外部依赖"：
既不在目录本身，也不是 Windows 标配 system32 DLL。
用于诊断 0xc000007b "应用程序无法正常启动" 的缺失 DLL。
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

# Windows 10+ 标配 DLL（大小写无关）。这里不追求穷尽，只覆盖常见场景。
SYSTEM_DLLS = {
    # Kernel / user
    "kernel32.dll", "kernelbase.dll", "user32.dll", "gdi32.dll", "gdi32full.dll",
    "advapi32.dll", "shell32.dll", "shlwapi.dll", "ole32.dll", "oleaut32.dll",
    "ws2_32.dll", "winmm.dll", "comdlg32.dll", "comctl32.dll", "imm32.dll",
    "version.dll", "psapi.dll", "crypt32.dll", "bcrypt.dll", "ncrypt.dll",
    "secur32.dll", "userenv.dll", "netapi32.dll", "iphlpapi.dll", "rpcrt4.dll",
    "dnsapi.dll", "wininet.dll", "urlmon.dll", "wldap32.dll", "dbghelp.dll",
    "setupapi.dll", "cfgmgr32.dll", "winhttp.dll", "credui.dll", "mpr.dll",
    "propsys.dll", "dwmapi.dll", "uxtheme.dll", "msimg32.dll", "powrprof.dll",
    "wtsapi32.dll", "profapi.dll", "authz.dll",
    # DirectX / graphics
    "d3d9.dll", "d3d11.dll", "dxgi.dll", "d2d1.dll", "dwrite.dll",
    "d3dcompiler_47.dll", "opengl32.dll", "glu32.dll",
    # Multimedia / shell
    "mfplat.dll", "mf.dll", "mfreadwrite.dll", "mfcore.dll", "avrt.dll",
    "shcore.dll", "combase.dll",
    # UCRT / API sets (Win10+)
    "ucrtbase.dll", "ntdll.dll",
    # Python embedded（打包时由 flet build 带入，但名义上也算系统能找到）
    "python312.dll", "python3.dll", "python311.dll", "python310.dll",
}


def is_api_set(name: str) -> bool:
    """api-ms-win-*.dll / ext-ms-*.dll 是 API 集合，系统虚拟 DLL。"""
    n = name.lower()
    return n.startswith("api-ms-win-") or n.startswith("ext-ms-")


def scan(path: Path) -> list[str]:
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
    except Exception as e:
        return [f"<failed: {e}>"]

    deps = []
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            name = entry.dll.decode("ascii", errors="replace")
            deps.append(name)
    pe.close()
    return deps


def main() -> int:
    if not TARGET_DIR.is_dir():
        print(f"目录不存在: {TARGET_DIR}")
        return 1

    local_files = {
        p.name.lower() for p in TARGET_DIR.iterdir() if p.is_file()
    }

    # 要扫描的关键文件
    targets = sorted(
        [p for p in TARGET_DIR.iterdir() if p.suffix.lower() in (".exe", ".dll")],
        key=lambda p: p.name.lower(),
    )

    print(f"扫描目录: {TARGET_DIR}")
    print(f"目录内文件数: {len(local_files)}")
    print("=" * 80)

    all_missing: dict[str, list[str]] = {}

    for f in targets:
        deps = scan(f)
        # 找出既不在本地，也不是系统标配的依赖
        missing = []
        for d in deps:
            dl = d.lower()
            if dl in local_files:
                continue
            if dl in SYSTEM_DLLS:
                continue
            if is_api_set(dl):
                continue
            missing.append(d)

        status = "✅ OK" if not missing else f"❌ 缺 {len(missing)} 个"
        print(f"\n[{status}] {f.name}")
        if missing:
            for m in missing:
                print(f"    → {m}")
                all_missing.setdefault(m.lower(), []).append(f.name)

    print("\n" + "=" * 80)
    if all_missing:
        print(f"汇总：{len(all_missing)} 个可能缺失的 DLL（按影响范围排序）")
        for dll, users in sorted(all_missing.items(), key=lambda kv: -len(kv[1])):
            print(f"\n  {dll}")
            print(f"    被 {len(users)} 个模块依赖: {', '.join(users[:5])}" +
                  (f" 等" if len(users) > 5 else ""))
    else:
        print("✅ 未发现可疑的外部依赖，所有依赖要么在本地要么是系统 DLL")

    return 0


if __name__ == "__main__":
    sys.exit(main())
