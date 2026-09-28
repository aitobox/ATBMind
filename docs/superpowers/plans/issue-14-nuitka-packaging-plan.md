# Issue #14 Plan: 编写 Nuitka 跨平台原生打包脚本与一键发布流程

## Implementation Steps
1. **Update `apps/atb_draw_desktop/main.py` CLI parser**:
   - 增加 `argparse` 处理 `--version` 和 `--help`，使客户端既能作为 GUI 窗口启动，也能通过 `./dist/ATBDraw --version` 验证构建产物。
2. **Nuitka Build Script (`scripts/build_nuitka.sh`)**:
   - 编写带可执行权限的标准 Bash 打包脚本，支持 `--standalone`、`--enable-plugin=pyside6`、资源文件复制以及 `--dry-run` 检查。
3. **Packaging Guide (`docs/packaging_guide.md`)**:
   - 编写跨平台打包与无 Python 干净机器冒烟测试指南。
4. **Unit Tests (`tests/test_packaging_script.py`)**:
   - 验证 `scripts/build_nuitka.sh` 脚本语法及 `--dry-run` 执行。
   - 验证 `apps/atb_draw_desktop/main.py --version` CLI 输出。
5. **Verification**:
   - 运行 `PYTHONPATH=. conda run -n ATBMind pytest tests/` 确保所有测试通过。
