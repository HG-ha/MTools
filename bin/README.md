# 压缩工具说明

本目录包含图片压缩所需的第三方工具。

## 工具列表

### Windows

- **mozjpeg** (v4.0.3) - 高效的 JPEG 压缩工具
  - 位置: `windows/mozjpeg/shared/Release/cjpeg.exe`
  - 可减小 JPEG 文件 50-70% 的大小
  
- **pngquant** - 高质量的 PNG 压缩工具
  - 位置: `windows/pngquant/pngquant/pngquant.exe`
  - 可减小 PNG 文件 60-80% 的大小

### macOS 和 Linux

需要自行下载对应平台的工具：

- mozjpeg: https://github.com/mozilla/mozjpeg/releases
- pngquant: https://pngquant.org/

## 使用说明

这些工具会被 `ImageService` 自动调用，无需手动操作。

## 许可证

- mozjpeg: BSD-3-Clause
- pngquant: GPL v3 / Commercial

## 注意事项

这些工具体积较大（约 10-20MB），建议：

1. 如果提交到 Git，使用 Git LFS
2. 或者在 .gitignore 中排除 bin/ 目录
3. 在部署时单独下载

