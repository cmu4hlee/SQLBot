#!/bin/bash

# 前端部署脚本
# 方式1: 使用 serve 启动静态服务器
# 方式2: 使用 vite preview
# 方式3: 使用 nginx

echo "=========================================="
echo "SQLBot 前端部署脚本"
echo "=========================================="

# 检查是否安装了 serve
if command -v serve &> /dev/null; then
    echo "✅ serve 已安装"
    SERVE_CMD="serve -s dist -l 8080"
elif command -v npx &> /dev/null; then
    echo "✅ npx 可用，使用 npx serve"
    SERVE_CMD="npx serve -s dist -l 8080"
else
    echo "❌ 未找到 serve 或 npx"
    exit 1
fi

echo ""
echo "选择部署方式:"
echo "1. 使用 serve (推荐)"
echo "2. 使用 vite preview"
echo "3. 退出"
read -p "请选择 (1-3): " choice

case $choice in
    1)
        echo ""
        echo "🚀 使用 serve 启动前端服务..."
        echo "📍 地址: http://localhost:8080"
        echo "📁 目录: $(pwd)/dist"
        echo ""
        cd /Users/cjlee/Desktop/Project/SQLbot/frontend
        npx serve -s dist -l 8080
        ;;
    2)
        echo ""
        echo "🚀 使用 vite preview 启动前端服务..."
        echo "📍 地址: http://localhost:8080"
        echo ""
        cd /Users/cjlee/Desktop/Project/SQLbot/frontend
        npm run preview -- --port 8080
        ;;
    3)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
