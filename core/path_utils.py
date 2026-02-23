import sys
import os
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    """检查是否在 PyInstaller 打包环境中运行"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_base_dir() -> Path:
    """
    获取程序根目录

    - 打包后：EXE 所在目录
    - 开发环境：项目根目录（main.py 所在目录）
    """
    if is_frozen():
        return Path(sys.executable).parent.resolve()
    else:
        return Path(__file__).parent.parent.resolve()


def get_internal_dir() -> Path:
    """
    获取 PyInstaller 内部解压目录（打包后使用）

    开发环境返回 None
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    return None


def get_static_dir() -> Path:
    """获取静态文件目录"""
    if is_frozen():
        return get_base_dir() / "static"
    else:
        return get_base_dir() / "static"


def get_data_dir() -> Path:
    """获取数据目录"""
    return get_base_dir() / "data"


def get_papers_dir() -> Path:
    """获取论文数据目录"""
    papers_dir = get_data_dir() / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    return papers_dir


def get_config_file() -> Path:
    """获取配置文件路径"""
    return get_base_dir() / "config.yaml"


def get_config_template_file() -> Path:
    """获取配置模板文件路径"""
    if is_frozen():
        internal = get_internal_dir()
        if internal:
            template_path = internal / "config.yaml.template"
            if template_path.exists():
                return template_path
    return get_base_dir() / "config.yaml.template"


def ensure_data_dirs():
    """确保数据目录存在"""
    get_papers_dir()

    config_file = get_config_file()
    if not config_file.exists():
        template_file = get_config_template_file()
        if template_file.exists():
            import shutil

            shutil.copy(template_file, config_file)
            print(f"Created config file from template: {config_file}")


def get_file_server_url(host: str, port: int) -> str:
    """获取文件服务器 URL"""
    if host == "0.0.0.0":
        import socket

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            ip = "127.0.0.1"
        return f"http://{ip}:{port}"
    return f"http://{host}:{port}"
