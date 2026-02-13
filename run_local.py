#!/usr/bin/env python3
"""
本地启动 SQLBot 服务
不需要 Docker，直接使用本地 Python 环境运行
"""
import subprocess
import sys
import os

def check_dependencies():
    """检查依赖是否安装"""
    print("检查 Python 环境...")
    print(f"Python 版本: {sys.version}")

    # 检查 uv 是否可用
    result = subprocess.run(["which", "uv"], capture_output=True)
    if result.returncode == 0:
        print("✅ uv 已安装")
        return "uv"
    
    # 检查 pip 是否可用
    result = subprocess.run(["which", "pip"], capture_output=True)
    if result.returncode == 0:
        print("✅ pip 已安装")
        return "pip"
    
    print("❌ 未找到 uv 或 pip")
    return None

def install_dependencies(manager):
    """安装依赖"""
    print(f"\n使用 {manager} 安装依赖...")
    
    os.chdir("/Users/cjlee/Desktop/Project/SQLbot/backend")
    
    if manager == "uv":
        cmd = ["uv", "sync"]
    else:
        cmd = ["pip", "install", "-e", "."]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ 依赖安装成功")
        return True
    else:
        print(f"❌ 依赖安装失败: {result.stderr}")
        return False

def start_service():
    """启动服务"""
    print("\n启动 SQLBot 服务...")
    print("=" * 60)
    
    os.chdir("/Users/cjlee/Desktop/Project/SQLbot/backend")
    
    # 使用 uvicorn 启动
    cmd = [
        sys.executable, "-m", "uvicorn",
        "main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    
    print(f"执行命令: {' '.join(cmd)}")
    print("=" * 60)
    
    # 使用 os.system 以便可以看到输出
    os.system(' '.join(cmd))

def main():
    print("=" * 60)
    print("SQLBot 本地启动脚本")
    print("=" * 60)
    
    # 检查依赖管理工具
    manager = check_dependencies()
    if not manager:
        print("\n请安装 uv 或 pip:")
        print("  uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
        print("  pip: python -m pip install --upgrade pip")
        return
    
    # 安装依赖
    if not install_dependencies(manager):
        return
    
    # 启动服务
    start_service()

if __name__ == "__main__":
    main()
