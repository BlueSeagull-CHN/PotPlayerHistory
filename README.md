# 🎬 PotPlayer 播放位置记忆管理器

![Version](https://img.shields.io/badge/Version-1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.8+-brightgreen)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![License](https://img.shields.io/badge/License-MIT-green)

一个现代化、易用且强大的 **PotPlayer 播放记录管理工具**，帮助你轻松管理、筛选和清理视频播放进度记忆。

---

## ✨ 核心特性

- **智能自动加载**：启动时自动检测并加载同目录下的 PotPlayer 配置文件
- **双模式过滤**：支持「排除关键词」和「提取关键词」两种过滤方式
- **按日期搜索**：快速找到指定日期之前播放的旧记录（支持快捷选择 7/30/90/180 天）
- **失效文件清理**：一键找出并选中已不存在的文件记录
- **安全撤销系统**：支持操作撤销 + 选择状态撤销（最多保留 5 步选择历史）
- **自动备份**：保存时自动创建带时间戳的备份文件
- **多编码支持**：完美兼容 UTF-8、UTF-16、GBK、ANSI 等编码
- **高分屏适配**：支持 Windows 高 DPI 显示

---

## 📸 界面预览

![主界面](screenshot-main.png)
![日期搜索功能](screenshot-search.png)

---

## 🚀 下载使用

前往 [Releases](../../releases/latest) 下载最新版 `PotPlayerHistoryManager.exe`

---

## 📖 使用指南

### 启动后
- 程序会**自动**尝试加载当前目录下的 PotPlayer 配置文件（PotPlayerMini64.ini 等）
- 若未自动加载，可手动点击「打开配置文件」

### 常用操作
- **筛选记录**：输入关键词，支持排除或提取模式
- **清理旧记录**：点击「按日期搜索」，选择天数后一键选中
- **清理失效文件**：点击「清理失效」自动选中不存在的文件
- **批量删除**：选中后按 `Delete` 键或点击「删除选中」
- **保存修改**：点击「保存」按钮（自动备份原文件）

### 快捷键
- `Ctrl + O` → 打开配置文件
- `Ctrl + S` → 保存修改
- `Ctrl + Z` → 撤销操作
- `Ctrl + A` → 全选
- `Ctrl + I` → 反选
- `Delete` → 删除选中记录

---

## 🛠️ 技术特点

- 基于 Python + Tkinter 开发
- 单文件绿色便携，无需安装
- 支持多种配置文件编码
- 完善的错误处理与用户提示
- 代码结构清晰，易于维护

---

## 📁 文件说明

- `PotPlayer播放位置记忆管理器.exe` —— 主程序（推荐）
- `logo.ico` —— 程序图标
- `config.ini` —— 打包配置文件（可选）

---

## ❤️ 致谢

感谢 PotPlayer 这款优秀播放器，让我们能更好地管理观影记忆。

欢迎提出 Issue 和建议，一起让这个工具变得更好！

---

**Made with ❤️ for all PotPlayer users**
