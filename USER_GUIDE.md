# R-MAN 用户使用指南

欢迎使用 **R-MAN** —— 您的通用 AI 自动化执行助理。

---

## 1. 快速上手

### 1.1 环境初始化
在 Linux 服务器上克隆项目后，执行安装脚本：
```bash
chmod +x setup.sh
./setup.sh
```

### 1.2 配置凭证
编辑 `config/config.yaml`，填入以下必要信息：
*   **Feishu**: `app_id`, `app_secret` 以及 `allowed_user_open_id`（可通过初次启动日志获取）。
*   **LLM**: `api_key` 和 `base_url` (支持 OpenAI 兼容接口)。
*   **Tavily**: `api_key` (用于联网搜索)。

### 1.3 运行诊断
启动前，建议运行自检工具确认一切就绪：
```bash
PYTHONPATH=. ./venv/bin/python rman/common/doctor.py
```

### 1.4 启动服务
```bash
PYTHONPATH=. ./venv/bin/python rman/main.py
```

---

## 2. 核心功能与交互

### 2.1 任务执行 (ReAct)
直接在飞书发送自然语言指令。R-MAN 会经历：
1.  `<think>`: 内部逻辑推理。
2.  `Action`: 调用真实工具（如 Shell, 文件读写）。
3.  `<final>`: 提交最终报告。

### 2.2 长期记忆 (Memory)
*   **记录**: “记住我的开发服务器 IP 是 10.0.0.1”。
*   **检索**: “我上次提到的服务器 IP 是多少？”。
*   **有效期**: 记忆默认保存 90 天，支持自动清理。

### 2.3 联网搜索
R-MAN 可以通过 `tavily_search` 访问实时互联网，您可以问它关于今天的新闻、最新的股价或技术文档。

---

## 3. 安全准则

1.  **权限隔离**: R-MAN 默认被锁定在 `workspace/` 和 `/tmp/` 目录。
2.  **二次确认**: 执行删除文件（`rm`）或强杀进程（`kill`）等破坏性操作前，R-MAN 会在飞书上请求您的 **文字回复“确认”**。
3.  **DNA 保护**: `RMAN.md` 和 `TOOLS.md` 是 Agent 的核心指令文件，建议通过 Git 或外部编辑器进行版本管理。

---

## 4. 运维与维护

### 4.1 日志查看
*   **运行日志**: `logs/rman.log`
*   **安全审计**: `logs/audit.log` (记录所有敏感操作意图)

### 4.2 后台常驻 (systemd)
参考 `rman.service.template` 配置系统服务，实现故障自愈与开机自启。

---
> 🤖 **R-MAN**: 推理先于执行，安全重于一切。
