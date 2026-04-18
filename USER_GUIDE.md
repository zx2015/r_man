# R-MAN 用户使用指南

欢迎使用 **R-MAN** —— 您的通用 AI 自动化执行助理。

---

## 1. 快速上手

### 1.1 环境初始化与交互式配置
在 Linux 服务器上克隆项目后，执行安装脚本。该脚本将引导您安装依赖并配置所有必要凭证：
```bash
chmod +x setup.sh
./setup.sh
```
按照屏幕提示逐步输入您的 API Key 和配置项。对于路径配置，您可以直接按回车使用推荐的默认值。

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
`setup.sh` 会根据您的实际路径自动生成 `rman.service`。部署步骤如下：
1.  将生成的文件拷贝到系统服务目录：
    ```bash
    sudo cp rman.service /etc/systemd/system/
    ```
2.  启动并设置开机自启：
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable rman
    sudo systemctl start rman
    ```

---
> 🤖 **R-MAN**: 推理先于执行，安全重于一切。
