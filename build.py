#!/usr/bin/env python3
"""
UniReader 构建脚本

使用方法:
    python build.py              # 构建当前平台版本
    python build.py --clean      # 清理后重新构建
    python build.py --version    # 显示版本信息
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


def get_version():
    """从 config.yaml 或 git 获取版本号"""
    version = "1.0.0"

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
        )
        if result.returncode == 0:
            version = result.stdout.strip().lstrip("v")
    except:
        pass

    return version


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ["build", "dist", "__pycache__"]
    files_to_remove = ["*.pyc", "*.pyo"]

    for dir_name in dirs_to_remove:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"Removing {dir_path}/")
            shutil.rmtree(dir_path)

    for pattern in files_to_remove:
        for file_path in Path(".").rglob(pattern):
            print(f"Removing {file_path}")
            file_path.unlink()

    for dir_path in Path(".").rglob("__pycache__"):
        print(f"Removing {dir_path}/")
        shutil.rmtree(dir_path)


def build():
    """执行构建"""
    print("=" * 50)
    print("UniReader Build Script")
    print(f"Version: {get_version()}")
    print(f"Platform: {sys.platform}")
    print("=" * 50)

    spec_file = Path("UniReader.spec")
    if not spec_file.exists():
        print("ERROR: UniReader.spec not found")
        sys.exit(1)

    static_dir = Path("static")
    if not static_dir.exists():
        print("ERROR: static/ directory not found")
        sys.exit(1)

    print("\nRunning PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "UniReader.spec", "--noconfirm"],
        cwd=Path(__file__).parent,
    )

    if result.returncode != 0:
        print("ERROR: PyInstaller failed")
        sys.exit(1)

    dist_dir = Path("dist") / "UniReader"
    if not dist_dir.exists():
        print("ERROR: Build output not found")
        sys.exit(1)

    print("\nCopying additional files...")

    config_template = Path("config.yaml.template")
    if config_template.exists():
        dest = dist_dir / "config.yaml.template"
        shutil.copy(config_template, dest)
        print(f"  - config.yaml.template")

    for doc_file in ["README.md", "GUIDE.md"]:
        src = Path(doc_file)
        if src.exists():
            dest = dist_dir / doc_file
            shutil.copy(src, dest)
            print(f"  - {doc_file}")

    data_dir = dist_dir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / "papers").mkdir(exist_ok=True)
    print("  - data/papers/")

    static_dest = dist_dir / "static"
    if not static_dest.exists():
        shutil.copytree(static_dir, static_dest)
        print("  - static/")

    print("\n" + "=" * 50)
    print("Build completed successfully!")
    print(f"Output: {dist_dir.absolute()}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="UniReader Build Script")
    parser.add_argument(
        "--clean", action="store_true", help="Clean build directories before building"
    )
    parser.add_argument(
        "--version", action="store_true", help="Show version information"
    )
    parser.add_argument(
        "--clean-only", action="store_true", help="Only clean, don't build"
    )

    args = parser.parse_args()

    if args.version:
        print(f"UniReader v{get_version()}")
        return

    if args.clean or args.clean_only:
        clean_build()

    if args.clean_only:
        return

    build()


if __name__ == "__main__":
    main()
