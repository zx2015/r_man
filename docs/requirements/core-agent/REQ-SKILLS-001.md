# REQ-SKILLS-001: 智能体技能系统 (Agent Skills System)

| 版本号 | 日期 | 变更说明 | 作者 |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-04-19 | 初始版本 | Gemini CLI |

## 1. 需求背景与目标 (Background & Goals)

为了提升 R-MAN 处理特定领域问题的专业能力，系统引入“技能 (Skills)”机制。与固化的代码级工具不同，Skill 是一种**动态注入的专家级 Prompt、工作流约束和领域知识库**。它允许用户通过编写简单的 Markdown 文件，快速为 Agent 赋予处理特定任务的专业指导。

核心目标：
1. **零代码扩展**: 允许非开发人员通过 Markdown 扩展 Agent 的领域知识。
2. **动态加载**: 系统启动时自动发现和注册技能。
3. **Agentic 串联**: 放弃静态的交叉引用，将何时调用技能、如何串联多个技能的决策权完全交给 LLM 自身。

## 2. 目录规范与文件结构 (Directory Structure & File Format)

### 2.1 存储路径
- 所有的技能必须存放在项目根目录下的 `skills/` 文件夹内。
- 允许一级子目录结构，例如 `skills/python-expert/`。

### 2.2 文件命名与位置
- 技能文件必须严格命名为 `SKILL.md`。
- 只有直接位于 `skills/` 下的 `SKILL.md`，或者位于其**一级子目录**下的 `SKILL.md` （例如 `skills/my-skill/SKILL.md`）才会被系统识别。更深层级的目录将被忽略。

### 2.3 核心元数据 (Frontmatter Metadata)
每个 `SKILL.md` 文件必须在其最开头包含由 `---` 包裹的 YAML 格式元数据区（Frontmatter）。

#### 必须包含的字段：
1. `name` (String): 技能的唯一标识符。
2. `description` (String): 技能的简短描述，用于让 LLM 理解该技能的用途。

*示例 `skills/python-expert/SKILL.md`:*
```markdown
---
name: python-expert
description: Python 高级工程实践与 Pydantic V1 兼容层指导。
---

# 技能详情
当用户询问关于 Python 的架构问题时，请遵循以下原则：
1. 优先使用异步编程。
2. 保持类型注解的严格性。
...
```

## 3. 系统感知与生命周期 (System Lifecycle)

### 3.1 启动扫描与校验 (Boot Scanning & Validation)
系统在启动（或重新加载配置）时，必须执行完整的扫描流程，依次进行以下三项强制性检查：

#### ① 文件命名检查 (File Name Check)
- 仅识别文件名为 `SKILL.md` 的文件。
- 仅扫描根级和一级子目录。

#### ② 结构合法性检查 (Frontmatter Check)
- 系统使用正则表达式（`FRONTMATTER_REGEX`）检查文件头部。
- 如果文件开头没有严格被 `---` 包裹的元数据区，该技能将被**直接忽略**（跳过且不注册）。

#### ③ 核心元数据检查 (Required Metadata)
- 通过 YAML 解析器提取元数据区内容（如果 YAML 解析失败，系统应包含简单的 KV 解析器作为回退方案）。
- **字段存在性**: 必须同时包含 `name` 和 `description` 字段。
- **类型检查**: 两个字段都必须是字符串类型。
- **名称脱敏 (Sanitization)**: 系统必须自动对 `name` 字段进行清理，将所有非法字符（如 `:`, `\`, `/`）替换为连字符 `-`。

### 3.2 冲突处理 (Precedence Check)
如果在多个扫描路径（如不同的一级子目录）中发现了脱敏后同名的技能：
- 系统**不应崩溃**。
- 系统应记录一条**警告级别 (Warning) 的日志**，指出冲突的技能名称和具体的文件路径。
- 系统可自行决定覆盖策略（如：后扫描的覆盖先扫描的，或保留第一个发现的），但必须在日志中明确说明最终注册的是哪一个。

### 3.3 系统层感知 (System Prompt Integration)
扫描完成后，所有合法注册的技能信息（脱敏后的 `name` 和 `description`）必须被动态注入到：
1. **System Prompt (系统层)** 的可用工具列表中，或者；
2. 元工具 `activate_skill` 的工具描述参数中。
*目的：确保 LLM 在规划任务时，能够明确知道当前有哪些领域专家可供咨询。*

## 4. 动态技能串联 (Agentic Chaining)

### 4.1 取消静态交叉引用
为了保持技能模块的高内聚和低耦合，**Skill 系统本身不支持静态的、声明式的交叉引用**（即不能在 A 技能的元数据中声明“依赖” B 技能）。

### 4.2 基于 Agent 的动态决策
- 通过提供内置工具 `activate_skill`，Agent 可以在 `<think>` 阶段根据用户的复杂指令，自主决定是否需要调用某个技能。
- Agent 可以根据执行过程中的逻辑反馈，在同一任务中**动态地串联或并行使用多个技能**。
- 这完全符合 “Agentic” 的设计初衷：将流程控制权和依赖解析权交给具备推理能力的 LLM，而非硬编码在配置文件中。

## 5. 技能激活生命周期 (Skill Activation Lifecycle)

当 LLM 通过 `activate_skill` 工具激活某个技能时，将触发一系列系统级变更：

### 5.1 状态变更 (State Update)
在后端的 `SkillManager` (或相关会话状态模块) 中，该技能会被明确标记为 `active`。Agent 在后续的对话回合中将明确知道这个技能已经“上线”。

### 5.2 资源感知与自由读取 (Resource Awareness & Read Access)
- **读取权限**: Agent 被允许使用 `read_file` 工具读取技能目录下的完整 `SKILL.md`，以防注入内容被意外截断或需要重新审视。
- **目录树扫描**: 激活时，系统会自动扫描该技能目录下的文件结构（例如 `scripts/`、`references/`、`assets/`）。
- **按需加载**: 为了节省 Token，系统仅将这些文件的“目录结构树”返回给 Agent。Agent 在感知到这些资源存在后，会在需要时主动通过 `read_file` 获取具体文件内容。

### 5.3 上下文包装与角色转变 (Context Injection & Role Shift)
技能的正文内容会被实时注入到当前的 Context Window 中，并使用特殊的 XML 标签包装，以强化系统指令的优先级：
- 通过注入指令，Agent 的角色会从“通用助手”强制转换为该技能定义的“专属专家”。

### 5.4 生命周期管理 (Lifecycle Scope)
- **单次会话有效**: 技能的激活状态仅绑定于当前 Session（会话）。开启全新会话时，所有技能默认恢复为未激活状态，需要按需再次触发。
- **UI 反馈**: 激活成功后，系统会在 CLI 或 UI 界面上向用户呈现反馈（如 `Skill "xxx" activated`），明确告知用户当前 Agent 的能力已被临时增强。
