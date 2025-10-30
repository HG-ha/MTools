# 主题色实时切换修复说明

## 问题描述

1. **图片裁剪界面（crop_view.py）**：裁剪指南卡片的渐变色在创建时固定，切换主题色后不会更新
2. **图片信息查看界面（info_view.py）**：概览卡片的渐变色只在重新选择图片时才会更新主题色

## 修复方案

### 1. crop_view.py 修复

#### 修改点：
- 将 `instruction_card` 保存为实例变量 `self.instruction_card`
- 添加 `_update_instruction_card_gradient()` 方法，用于动态更新渐变色
- 添加 `did_mount()` 生命周期方法，在视图挂载时更新主题色
- 在 `_update_instruction_card_gradient()` 中同时更新空状态的背景色

#### 工作原理：
- 每次视图被切换回来时，`did_mount()` 会被调用
- `did_mount()` 调用 `_update_instruction_card_gradient()` 获取最新的主题色
- 更新 `instruction_card` 的渐变色属性
- 同时更新 `empty_state_widget` 的背景色

### 2. info_view.py 修复

#### 修改点：
- 在 `_display_info()` 中保存概览卡片为 `self.summary_section`
- 在 `_build_summary_section()` 中保存统计瓦片和复制按钮的引用
- 添加 `_update_summary_section_theme()` 方法，用于动态更新主题色
- 添加 `did_mount()` 生命周期方法，在视图挂载时更新主题色

#### 工作原理：
- 创建概览卡片时，保存所有需要更新主题色的组件引用
- `_update_summary_section_theme()` 会更新：
  - 主容器的渐变和边框
  - 所有统计瓦片的渐变
  - 复制按钮的背景色
- 每次视图被切换回来时，`did_mount()` 会检查是否有概览卡片并更新其主题色

## 技术细节

### did_mount() 生命周期

Flet 框架支持 `did_mount()` 生命周期方法，当控件被添加到页面并完成渲染后会自动调用。这是更新动态属性的最佳时机。

### 主题色获取

使用 `_get_theme_primary_color()` 方法实时获取当前主题色：
- 优先从 `page.dark_theme` 或 `page.theme` 获取 `color_scheme_seed`
- 如果获取失败，回退到默认的 `PRIMARY_COLOR`

### 更新策略

1. **初始化时**：创建组件时设置初始主题色
2. **挂载时**：通过 `did_mount()` 确保主题色是最新的
3. **动态更新**：提供专门的更新方法，可以在需要时手动调用

## 测试步骤

1. 启动应用
2. 进入图片裁剪或图片信息查看页面
3. 打开设置，切换主题色
4. 返回图片裁剪或图片信息查看页面
5. 验证指南卡片/概览卡片的颜色已更新为新主题色

## 影响范围

- ✅ 图片裁剪页面的指南卡片
- ✅ 图片裁剪页面的空状态背景
- ✅ 图片信息页面的概览卡片
- ✅ 图片信息页面的统计瓦片
- ✅ 图片信息页面的复制按钮

## 注意事项

- 修复不会影响其他功能
- 所有主题色相关的组件现在都会响应主题切换
- `did_mount()` 方法的异常已被捕获，不会影响页面正常显示

