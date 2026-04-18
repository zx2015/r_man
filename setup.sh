#!/bin/bash

# r-man 全交互式环境初始化向导
set -e

# --- 辅助函数 ---
prompt_user() {
    local prompt_text="$1"
    local default_val="$2"
    local result_var="$3"
    
    read -p "$prompt_text [$default_val]: " input
    if [ -z "$input" ]; then
        eval "$result_var=\"$default_val\""
    else
        eval "$result_var=\"$input\""
    fi
}

echo "=========================================="
echo "🤖 R-MAN 交互式安装与配置向导"
echo "=========================================="

# 1. 环境初始化
echo -e "\nStep 1: 环境检测与依赖安装..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3，请先安装 Python 3.12+"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境 (venv)..."
    python3 -m venv venv
fi

echo "📥 正在安装/更新核心依赖..."
./venv/bin/pip install --upgrade pip > /dev/null
./venv/bin/pip install -r requirements.txt > /dev/null

# 2. LLM 配置
echo -e "\nStep 2: 配置推理大模型 (LLM)..."
prompt_user "LLM Provider (目前仅支持 openai 协议)" "openai" LLM_PROVIDER
prompt_user "LLM Base URL" "https://api.openai.com/v1" LLM_BASE_URL
prompt_user "LLM API Key" "sk-..." LLM_API_KEY
prompt_user "LLM Model Name" "gpt-4o" LLM_MODEL

# 3. Embedding 配置
echo -e "\nStep 3: 配置向量模型 (Embedding)..."
prompt_user "Embedding Base URL" "$LLM_BASE_URL" EMB_BASE_URL
prompt_user "Embedding API Key" "$LLM_API_KEY" EMB_API_KEY
prompt_user "Embedding Model Name" "BAAI/bge-m3" EMB_MODEL

# 4. 飞书配置
echo -e "\nStep 4: 配置飞书 (Feishu) 机器人..."
prompt_user "Feishu App ID" "cli_..." FS_APP_ID
prompt_user "Feishu App Secret" "..." FS_APP_SECRET
prompt_user "Allowed User OpenID (留空则允许所有人，初次运行建议留空)" "*" FS_ALLOWED_USER

# 5. Tavily 配置
echo -e "\nStep 5: 配置联网搜索 (Tavily)..."
prompt_user "Tavily API Key (tvly-...) [可选]" "" TAVILY_KEY

# 6. 路径配置
echo -e "\nStep 6: 存储路径设置..."
prompt_user "审计日志路径" "./logs/audit.log" PATH_AUDIT
prompt_user "数据库路径" "./data/memory.db" PATH_DB
prompt_user "工作目录路径" "@workspace/" PATH_WS

# 7. 生成配置文件 (使用 Python 以确保 YAML 格式正确)
echo -e "\n💾 正在生成配置文件..."
mkdir -p config data logs workspace templates

cat <<EOF > gen_config.py
import yaml
import os

config_data = {
    "agent": {
        "max_iterations": 20,
        "tool_timeout": 30,
        "process_session_max_ttl": 3600,
        "audit_log_path": "$PATH_AUDIT",
        "audit_log_max_size": 10,
        "audit_log_retention": 3,
        "workspace_dir": "$PATH_WS",
        "enable_intermediate_status": True
    },
    "llm": {
        "provider": "$LLM_PROVIDER",
        "base_url": "$LLM_BASE_URL",
        "api_key": "$LLM_API_KEY",
        "model": "$LLM_MODEL",
        "temperature": 0.2,
        "context_window": 200000,
        "max_tokens": 32768,
        "timeout": 60
    },
    "feishu": {
        "app_id": "$FS_APP_ID",
        "app_secret": "$FS_APP_SECRET",
        "receive_mode": "websocket",
        "allowed_user_open_id": "$FS_ALLOWED_USER",
        "agent_response_timeout": 120
    },
    "memory": {
        "provider": "sqlite_vec",
        "db_path": "$PATH_DB",
        "embedding": {
            "base_url": "$EMB_BASE_URL",
            "api_key": "$EMB_API_KEY",
            "model": "$EMB_MODEL"
        },
        "retrieval": {
            "top_k": 3,
            "score_floor": 0.0
        }
    },
    "tavily": {
        "api_key": "$TAVILY_KEY"
    }
}

with open("config/config.yaml", "w", encoding="utf-8") as f:
    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

print("✅ config/config.yaml 已保存。")
EOF

./venv/bin/python3 gen_config.py
rm gen_config.py

# 8. 生成 systemd 服务配置
echo -e "\n⚙️ 正在生成 systemd 服务配置..."
./venv/bin/python rman/common/gen_service.py

# 9. 权限加固
chmod 700 data logs
echo -e "\n🎉 R-MAN 初始化完成！"
echo "----------------------------------------"
echo "1. 请运行自检工具: PYTHONPATH=. ./venv/bin/python rman/common/doctor.py"
echo "2. 启动服务: PYTHONPATH=. ./venv/bin/python rman/main.py"
echo "----------------------------------------"
