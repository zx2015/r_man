#!/bin/bash

# r-man 环境初始化脚本
set -e

echo "🚀 开始初始化 r-man 环境..."

# 1. 检查 Python 版本
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3，请先安装 Python 3.12+"
    exit 1
fi

# 2. 创建并激活虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境 (venv)..."
    python3 -m venv venv
else
    echo "✅ 虚拟环境已存在。"
fi

# 3. 升级 pip 并安装依赖
echo "📥 正在安装依赖 (requirements.txt)..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 4. 初始化目录结构
echo "📁 初始化目录结构..."
mkdir -p logs data workspace templates
chmod 700 data  # 保护数据库目录

# 5. 处理配置文件
if [ ! -f "config/config.yaml" ]; then
    echo "📝 未检测到 config.yaml，正在从模板生成..."
    if [ -f "config/config.yaml.example" ]; then
        cp config/config.yaml.example config/config.yaml
        echo "⚠️ 请在 config/config.yaml 中填入您的 AppID 和 Secret。"
    else
        echo "❌ 错误: 未找到配置模板 config.yaml.example"
    fi
fi

# 6. 环境自检预告
echo "----------------------------------------"
echo "✅ 初始化完成！"
echo "接下来您可以："
echo "  1. 编辑 config/config.yaml 配置凭证"
echo "  2. 运行自检工具: PYTHONPATH=. ./venv/bin/python rman/common/doctor.py"
echo "  3. 启动服务: PYTHONPATH=. ./venv/bin/python rman/main.py"
echo "----------------------------------------"
