# 🌙 AI 狼人杀

本地运行的文字版 AI 狼人杀 Web 应用：真人、AI 任意混排，每个 AI 座位可使用不同大模型（OpenAI 兼容协议 / Anthropic Messages），支持全 AI 对局观战、暂停与调速，对局结束后可查看完整回放。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Next.js 15 · React 19 · TypeScript · Tailwind CSS |
| 后端 | FastAPI · SQLAlchemy(async) · SQLite(WAL) · WebSocket |
| 模型 | OpenAI 兼容（OpenAI / Qwen / GLM / 其他）+ Anthropic Messages |
| 环境 | Python `.venv`（项目根目录）· Node.js（前端目录） |

## 快速开始（Windows）

```cmd
setup.cmd     # 首次安装：.venv + 后端依赖 + 前端依赖
start.cmd     # 启动：后端(8000) + 前端(3000)
```

浏览器打开 http://localhost:3000 。

首次使用流程：

1. 管理员登录：默认 `admin` / `admin123`（在 `.env` 中可改）。
2. 「模型配置」页添加模型（OpenAI / Qwen / GLM / Claude 均可），可用「测试连接」验证。
3. （可选）「AI 人格」页创建人格。
4. 注册普通账号 → 创建对局 → 选板子（6/9/12 人）→ 房主添加 AI 或一键 AI 补齐 → 开始游戏。
5. 全 AI 对局中，房主可以在观战栏暂停、调速（1x / 2x / 快进）。

## 模型接入示例

| 服务 | 协议 | Base URL 示例 | 模型名示例 |
| --- | --- | --- | --- |
| OpenAI | openai_compatible | `https://api.openai.com/v1` | gpt-4o |
| 阿里云百炼 (Qwen) | openai_compatible | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-max |
| 智谱 (GLM) | openai_compatible | `https://open.bigmodel.cn/api/paas/v4` | glm-4-plus |
| Anthropic | anthropic_messages | `https://api.anthropic.com` | claude-sonnet-5 |

## 配置说明（.env）

| 变量 | 说明 |
| --- | --- |
| `APP_SECRET_KEY` | 应用主加密密钥，用于加密模型 API Key，**必须修改** |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 首次启动自动创建的管理员（密码留空则用 admin/admin123） |
| `HUMAN_ACTION_TIMEOUT` | 真人发言/行动限时（秒），默认 45 |

## 对局规则

- **板子**：6 人（2狼/1预/1女巫/2平民，无警长）、9 人（3狼/预/女巫/猎人/3平民，有警长）、12 人（4狼/预/女巫/猎人/守卫/4平民，有警长）。
- **胜负**：好人消灭全部狼人获胜；狼人消灭全部平民或全部神职获胜。
- **女巫**：解药、毒药各一瓶整局一次；首夜可自救；同夜不能双药。
- **守卫**：不能连续两晚守护同一目标；目标同时被守卫守护和女巫救治时仍然死亡。
- **猎人**：被狼击杀或被放逐时可开枪；被毒杀不能开枪。
- **预言家**：查验结果只有“好人/狼人”。
- **狼人**：夜间私聊 + 投票击杀（并列空刀）；白天发言阶段可自爆，自爆立即结束白天进入夜晚。
- **警长**：第一夜后竞选；1.5 票；死亡后移交或撕毁；平票进入 PK 发言与重投，二次平票不产生警长或当天无人出局。

## 目录结构

```text
AI_LRS/
├── backend/
│   ├── app/
│   │   ├── api/        # REST + WebSocket
│   │   ├── ai/         # 模型适配器、提示词、AI 编排
│   │   ├── game/       # 游戏引擎（状态机/规则/事件）
│   │   ├── services/   # 单对局管理器、WS Hub
│   │   └── main.py     # FastAPI 入口
│   ├── tests/          # 规则/API/恢复/令牌 回归测试（pytest）
│   ├── mock_model.py   # 本地 Mock 模型（联调用，可选）
│   └── alembic/        # 数据库迁移骨架
├── frontend/           # Next.js 前端
├── data/               # SQLite 数据库（自动创建，不入库）
├── .env                # 本地配置（不入库）
└── setup.cmd / start.cmd
```

## 运行测试

```cmd
cd backend
..\.venv\Scripts\python -m pytest tests/ -q
```

覆盖：6/9/12 人板子完整结算、胜负判定、警长竞选与 PK 平票、信息隔离（旁观者看不到身份、狼人信息不外泄）、重复请求幂等、超时转 AI 托管、快照恢复（含回合令牌续接）、REST API。

## 常见问题（故障排查）

- **前端打不开 / 白屏**：确认后端已启动（http://127.0.0.1:8000/health 返回 ok）、前端 `npm run dev` 窗口无报错。
- **对局不推进，全员“跳过发言”**：AI 座位没有可用模型配置，或模型 Key 无效。到「模型配置」页点「测试连接」确认；删除模型后重新加入 AI 座位。
- **创建对局提示“已有未结束的对局”**：同一时间只允许一场对局。等待对局结束（或在数据库中删除 `data/werewolf.db` 重置——会清空所有数据）。
- **端口被占用**：修改 `start.cmd` 中的端口，前端在 `frontend/package.json` 的 `dev` 脚本改端口，`NEXT_PUBLIC_API_BASE` 指向新后端端口。
- **后端重启后对局恢复**：后端启动时自动从快照恢复未结束对局，为当前阶段重新计时。
- **模型 API Key 安全**：Key 加密存于 SQLite（密钥来自 `.env` 的 `APP_SECRET_KEY`），不会返回前端、不会写入日志与回放。

## 说明

- 首版为单活动对局：同时只有一场未结束对局，结束后才能创建下一场。
- 最多 12 玩家 + 约 20 名本地观众。
- 数据与状态：SQLite（WAL + 外键 + busy_timeout）+ 内存活动状态；所有状态变更经单一 `asyncio.Lock` 串行处理；事件与快照落库支持崩溃恢复。
