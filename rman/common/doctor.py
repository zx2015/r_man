import asyncio
import sys
import os
import sqlite3
from loguru import logger

# 尝试导入内部模块
try:
    from rman.common.config import config
    from rman.agent.backend import llm_backend
    import sqlite_vec
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    print("请确保已安装依赖并设置 PYTHONPATH=. 运行此脚本。")
    sys.exit(1)

async def check_memory_env():
    print("1. [Memory] 检查 SQLite 向量扩展...")
    try:
        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        row = conn.execute("SELECT vec_version();").fetchone()
        print(f"   ✅ sqlite-vec 可用 (版本: {row[0]})")
        return True
    except Exception as e:
        print(f"   ❌ sqlite-vec 加载失败: {e}")
        return False

async def check_llm_connectivity():
    print(f"2. [LLM] 检查后端连通性 (Model: {config.llm.model})...")
    if not config.llm.api_key:
        print("   ❌ 错误: 未配置 LLM API Key")
        return False
    
    try:
        # 发送一个极简测试请求
        msg = [{"role": "user", "content": "ping"}]
        await llm_backend.chat(msg)
        print("   ✅ LLM 响应正常")
        return True
    except Exception as e:
        print(f"   ❌ LLM 请求失败: {e}")
        return False

def check_feishu_config():
    print("3. [Feishu] 检查凭证配置...")
    if not config.feishu.app_id or not config.feishu.app_secret:
        print("   ❌ 错误: 缺少 Feishu AppID 或 Secret")
        return False
    
    if len(config.feishu.app_id) < 5 or config.feishu.app_secret.startswith("..."):
        print("   ⚠️ 警告: Feishu 凭证看起来仍是默认模板值")
        return False
    
    print("   ✅ 凭证已配置")
    return True

def check_directories():
    print("4. [System] 检查目录权限...")
    dirs = ["logs", "data", "workspace"]
    for d in dirs:
        if os.path.exists(d) and os.access(d, os.W_OK):
            print(f"   ✅ 目录 {d} 正常")
        else:
            print(f"   ❌ 目录 {d} 缺失或无写入权限")
            return False
    return True

async def run_doctor():
    print("=" * 40)
    print("🩺 r-man 系统健康诊断 (Doctor)")
    print("=" * 40)
    
    results = [
        await check_memory_env(),
        await check_llm_connectivity(),
        check_feishu_config(),
        check_directories()
    ]
    
    print("-" * 40)
    if all(results):
        print("🎉 恭喜！系统环境一切就绪，可以启动 rman/main.py")
    else:
        print("⚠️ 诊断发现问题，请根据上方红叉提示进行修正。")
    print("=" * 40)

if __name__ == "__main__":
    asyncio.run(run_doctor())
