import asyncio
import os
from rman.storage.session import session_store
from rman.tools.session_search import SessionSearchTool

async def verify():
    print("--- 准备测试数据 ---")
    chat_a = "chat-historical-123"
    chat_b = "chat-current-456"
    
    # 模拟旧对话
    session_store.save_message(chat_a, "user", "如何配置 Nginx 的负载均衡？")
    session_store.save_message(chat_a, "assistant", "可以使用 upstream 模块进行配置。")
    
    # 模拟当前对话（不应被搜到）
    session_store.save_message(chat_b, "user", "Nginx 的配置文件在哪里？")
    
    print("\n--- 执行搜索 (搜索 'Nginx') ---")
    tool = SessionSearchTool()
    
    # 情况 1: 不排除任何 chat_id
    res_all = await tool.execute(query="Nginx", chat_id=None)
    print(f"\n[所有结果]:\n{res_all}")
    
    # 情况 2: 排除当前会话 chat_b
    res_filtered = await tool.execute(query="Nginx", chat_id=chat_b)
    print(f"\n[排除当前会话后的结果]:\n{res_filtered}")
    
    if "chat-historical-123" in res_filtered and "chat-current-456" not in res_filtered:
        print("\n✅ 验证成功：FTS5 检索工作正常，且已正确过滤当前上下文！")
    else:
        print("\n❌ 验证失败：过滤逻辑或检索逻辑异常。")

if __name__ == "__main__":
    asyncio.run(verify())
