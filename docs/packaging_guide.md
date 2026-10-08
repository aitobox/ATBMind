# ATBMind Desktop 跨平台原生打包与发布指南

本指南介绍如何使用 Nuitka 将 `ATBMind Desktop` 桌面端应用（基于 PySide6 + ATBMind Harness 内核 + RobotRole & Skills 体系）一键打包为免 Python 环境依赖的独立原生可执行文件。

---

## 1. 打包前置准备

### 1.1 Python 环境与编译工具链
- **Python**: 3.12+ (使用 Conda 或 venv)
- **编译工具**:
  - **macOS**: Xcode Command Line Tools (`xcode-select --install`)
  - **Windows**: Visual Studio 2022 (Community 版，勾选 C++ 桌面开发) 或 MinGW64
  - **Linux**: `gcc` / `g++` (`sudo apt-get install build-essential`)
- **Nuitka**:
  ```bash
  pip install nuitka zstandard ordered-set
  ```

---

## 2. 一键打包命令

在项目根目录下执行打包脚本：

```bash
# 1. 检查构建参数与依赖（Dry Run）
bash scripts/build_nuitka.sh --dry-run

# 2. 执行完整独立打包
bash scripts/build_nuitka.sh

# 3. 指定输出目录（可选）
bash scripts/build_nuitka.sh --output-dir=/path/to/custom_dist
```

### 关键编译参数说明
- `--standalone`: 生成包含独立 Python 解释器运行时的免安装发布目录。
- `--enable-plugin=pyside6`: 自动分析并包含 PySide6/Qt6 动态库、字体引擎及 `platforms` 插件（如 `libqcocoa.dylib` 或 `qwindows.dll`）。
- `--include-package=atbmind_core`、`--include-package=apps`、`--include-package=skills`、`--include-package=roles`: 打包核心推理 Harness 内核、桌面客户端与专家角色/技能包。
- `--include-data-files`: 复制 `skills/image_generation/templates/seed_templates.json` 种子模板数据库与 `configs/config.yaml` 基础配置。
- `--macos-create-app-bundle` (macOS 专属): 自动封装为标准的 macOS 原生 `.app` 应用程序包 (`dist/ATBMind.app`)。

---

## 3. 构建产物验证与冒烟测试检查项

在构建完成后，可在无 Python 环境的干净系统下执行以下冒烟测试项：

### 3.1 命令行版本检查
```bash
# macOS
./dist/ATBMind.app/Contents/MacOS/ATBMind --version
# 或独立目录二进制
./dist/main.dist/ATBMind --version

# Windows
dist\main.dist\ATBMind.exe --version
```
**期望输出**：
```
ATBMind Desktop 0.1.0 (ATBMind Core 0.1.0)
```

### 3.2 界面交互与 RobotRole 协同冒烟项
1. **启动测试**: 双击启动应用程序，主界面三栏工作台正常渲染，无动态库缺失报错。
2. **多会话管理**: 点击左侧边栏“+ 新建对话”，会话树正常创建并切换。
3. **专家协同与生图测试**:
   - 在底栏输入口语指令：“帮我生成一张国风人像照片”。
   - 主协调官 (`coordinator`) 自动感知意图并将任务委派给视觉精修专家 (`draw_expert`)。
   - `draw_expert` 调用 `image_generation` 技能生成图像，结果卡片优雅展示。
4. **参数弹出层微调**:
   - 点击底栏风格选择器与模型画幅切换，状态即时同步至团队上下文中。
5. **设置面板持久化**: 打开设置窗口修改 API 密钥或模型并保存，配置成功写入 YAML。
