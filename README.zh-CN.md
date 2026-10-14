# HTTP CLI 协议

[![规范版本](https://img.shields.io/badge/spec-v1.0.0-blue)](docs/specification/v1.0.0/http-cli.md)
[![状态](https://img.shields.io/badge/status-draft-orange)](docs/specification/v1.0.0/http-cli.md)
[![Schema](https://img.shields.io/badge/json--schema-draft--2020--12-informational)](docs/specification/v1.0.0/schemas/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

[English](README.md) | **简体中文**

> **HTTP CLI** —— 将系统能力以"自描述、help 驱动的命令树"形式通过纯 HTTP
> 暴露出来的协议规范。

**状态：** Draft · **版本：** [1.0.0](docs/specification/v1.0.0/http-cli.md)

想象一个传统 CLI：一棵命令树，每个命令有 `--help`，每一层为下一层做索引。
本协议把这种体验映射到 HTTP 上——让 AI Agent（以及人类）只需一个 HTTP 客户端
加一个凭证，就能探索并操作一个陌生系统，同时把上下文窗口的消耗降到最低。

## 动机

| 问题 | 本协议的回答 |
|------|--------------|
| Agent 无法为每个工具装一个 CLI 二进制；HTTP 是通用底座。 | 以 URL 路径寻址的 CLI 形态命令树。 |
| 一次性倒出整份 API schema 会撑爆上下文窗口。 | **渐进式 help**：一次一层；每个节点只解释自己和它的直接子节点。 |
| 各家响应格式随意，解析代码难以复用。 | 数据与错误共用**一个信封**、一个错误模型、稳定错误码。 |
| 各组织的鉴权方案不同，难以统一。 | **可插拔凭证** + 规范强制的"尽职清单"：必须文档化并发布你的授权模型（8 项）。 |

## 形态一览

```
GET {base}?help=1                  → 根 help：顶层分组
GET {base}/note?help=1             → 分组 help：note 下的命令
GET {base}/note/list?help=1        → 命令 help：参数 schema
GET {base}/note/list?status=active&fields=id,title   → 执行
GET {base}/version/current         → 当前版本 + 发布时间
GET {base}/version/releases?since=0.1.0 → 自某版本以来的更新
```

无论是 help 还是数据，每个响应都是同一个信封：

```json
{ "data": [ {"id": "n_01", "title": "…"} ],
  "meta": { "request_id": "…", "limit": 5, "has_more": true } }
```

错误会教下一步怎么做：

```json
{ "error": { "code": "invalid_param",
             "message": "parameter \"status\" has invalid value \"open\"",
             "hint": "allowed: active | archived" } }
```

## 为你的项目实现 HTTP CLI

想在自己的系统上落地本协议，把下面这句直接发给你的 agent：

> 按 https://github.com/steven0lisa/http-cli-for-agent/blob/main/INSTALL.md
> 执行，为本项目实现 HTTP CLI。

[INSTALL.md](INSTALL.md) 会引导 agent：如何通读规范并理解背景、如何分步向你
收集必要的信息与设置、如何用符合性套件验收，以及完成后如何在
`AGENTS.md`/`CLAUDE.md` 中补充 HTTP CLI 的同步维护信息，确保代码更新时 CLI
跟着一起更新。

## 文档

| 文档 | 说明 |
|------|------|
| [**协议规范 v1.0.0**](docs/specification/v1.0.0/http-cli.md)（英文） | 规范正文：命令树、help、信封、鉴权、版本化、符合性。 |
| [Schemas](docs/specification/v1.0.0/schemas/) | 机器可读 JSON Schema：信封、help 文档、参数描述符、版本面。 |
| [Changelog](CHANGELOG.md) | 版本历史与升版规则。 |
| [Contributing](CONTRIBUTING.md) | 变更流程、版本与弃用策略、编辑规范。 |

## 参考实现与符合性测试套件

本仓库附带零依赖的 Python 参考实现与黑盒符合性套件：

```bash
make selftest    # 对参考实现跑符合性套件
make serve       # 启动演示命令树（notes 服务）于 http://127.0.0.1:8080/cli
make conformance BASE=http://127.0.0.1:8080/cli TOKEN=demo-token   # 任意部署
```

- `reference/` — 引擎（注册表 → 命令树、help 生成、校验、信封、投影、错误）
  加一套演示命令树。仅用 Python 3 标准库。
- `conformance/run.py` — 黑盒套件，按规范的符合性清单检查**线上部署**。
  不依赖参考实现，适用于任意实现。

## 三大设计支柱

1. **help 驱动的探索（token 经济）。** 每个节点都支持 `?help=1`；分组列表
   限制深度；`fields=` 投影与有界的分页让响应保持精小。上下文开销随任务增长，
   不随系统规模增长。
2. **统一的输出契约。** 成功为 `data`/`meta`，失败为 `error`
   （`code`/`message`/`hint`/`details`），配标准错误码表与稳定命名规则。
   一套解析逻辑，处处可用。
3. **可插拔鉴权 + 有据可查的责任。** 协议只固定凭证如何传输（header、HTTPS）
   与失败语义（401 与 403 的区分）；方案本身由你选择。每个实现必须公开一份
   授权说明，覆盖：凭证类型、签发、作用域、生命周期、传输、失败语义、审计、
   Agent 交接。

## 版本管理

规范采用语义化版本。服务端应在 root help 声明 `protocol_version`，并在响应头
返回 `X-HTTP-CLI-Version`。客户端必须忽略未知响应字段，因此 MINOR 级增量天然
非破坏。详见 [CHANGELOG.md](CHANGELOG.md)。

## 贡献

欢迎提交 Issue 与提案。任何规范行为的变更必须在同一变更中同步更新规范文档与
（如适用的）JSON Schema——Schema 派生自规范，两者绝不可漂移。详见
[CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[Apache License 2.0](LICENSE)
