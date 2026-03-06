"""打包脚本 - 生成 autocertsync.pyz"""

import os
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
PACKAGE_DIR = os.path.join(PROJECT_DIR, "autocertsync")
OUTPUT = os.path.join(PROJECT_DIR, "autocertsync.pyz")


def build():
    # 清理
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR)

    # 复制包到 build/autocertsync/
    shutil.copytree(PACKAGE_DIR, os.path.join(BUILD_DIR, "autocertsync"))

    # 创建顶层 __main__.py 作为入口
    with open(os.path.join(BUILD_DIR, "__main__.py"), "w") as f:
        f.write("from autocertsync.__main__ import main\nmain()\n")

    # 打包
    subprocess.run([
        sys.executable, "-m", "zipapp", BUILD_DIR,
        "-p", "/usr/bin/env python3",
        "-o", OUTPUT,
    ], check=True)

    # 清理
    shutil.rmtree(BUILD_DIR)
    print(f"打包完成: {OUTPUT}")


if __name__ == "__main__":
    build()
