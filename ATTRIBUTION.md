# 来源与许可

Rezinamuh 是一个独立编写的文风转换技能，参考 [blader/humanizer](https://github.com/blader/humanizer) 的模式分类和复查流程。上游作者为 Siqi Chen。Rezinamuh 不是上游官方版本，也不代表上游认可。

本项目显示名称为 **Rezinamuh**，技能标识为 `rezinamuh`，独立版本为 `1.0.0`；上游的 `3.0.0` 仅用于固定映射基线。

## 实际核对记录

核对日期：2026-09-18。通过 GitHub API 及原始文件地址读取了以下材料。

| 项目 | 实际读取结果 | 可复核来源 |
| --- | --- | --- |
| 基线 tag | `v3.0.0` | [tag 引用 API](https://api.github.com/repos/blader/humanizer/git/ref/tags/v3.0.0) |
| tag 指向对象 | 类型为 `commit`；SHA 为 `9862685f575c65a8247f90369951df1b3416e3d6` | [固定提交](https://github.com/blader/humanizer/commit/9862685f575c65a8247f90369951df1b3416e3d6) |
| 读取时的 main | 同一 commit SHA：`9862685f575c65a8247f90369951df1b3416e3d6` | [main 提交 API](https://api.github.com/repos/blader/humanizer/commits/main) |
| 提交时间 | `2026-09-06T20:17:53Z` | [固定提交 API](https://api.github.com/repos/blader/humanizer/commits/9862685f575c65a8247f90369951df1b3416e3d6) |
| 基线技能版本 | `metadata.version: "3.0.0"`，五组、25 条模式 | [固定版本 SKILL.md](https://github.com/blader/humanizer/blob/9862685f575c65a8247f90369951df1b3416e3d6/SKILL.md) |
| main 与基线差异 | 分别取回两个 `SKILL.md` 全文并逐字符串比较，结果相同；读取时不存在内容差异 | [tag 技能文件](https://github.com/blader/humanizer/blob/v3.0.0/SKILL.md)、[main 技能文件](https://github.com/blader/humanizer/blob/main/SKILL.md) |
| 使用与开发说明 | 已读取实际 README 和 AGENTS | [固定版本 README.md](https://github.com/blader/humanizer/blob/9862685f575c65a8247f90369951df1b3416e3d6/README.md)、[固定版本 AGENTS.md](https://github.com/blader/humanizer/blob/9862685f575c65a8247f90369951df1b3416e3d6/AGENTS.md) |
| 许可 | 实际 LICENSE 为 MIT；原版权行为 `Copyright (c) 2025 Siqi Chen` | [固定版本 LICENSE](https://github.com/blader/humanizer/blob/9862685f575c65a8247f90369951df1b3416e3d6/LICENSE) |

上述 SHA 来自 GitHub 的 tag 引用和提交接口，是提交编号，不是文件内容哈希。`main` 和 tag 名称以后可能变化；固定提交链接用于追溯本次读取的内容。

[递归目录接口](https://api.github.com/repos/blader/humanizer/git/trees/9862685f575c65a8247f90369951df1b3416e3d6?recursive=1) 返回 `truncated: false`。实际文件如下：

```text
.claude-plugin/marketplace.json
.claude-plugin/plugin.json
.github/workflows/validate.yml
AGENTS.md
LICENSE
README.md
SKILL.md
agents/openai.yaml
scripts/validate-package.py
```

该目录仅记录上游结构；Rezinamuh 不依赖这些上游适配文件。本版不提供 `.claude-plugin/` 或 `agents/` 平台适配。

## 参考与改造范围

- 参考上游五组模式、1—25 映射编号、各条模式含义，以及输入隔离、保护区域、语气和复查流程。
- 独立编写中文反向生成规则、条件与跳过条件、参数约定、示例、失败边界及测试材料。表达冗余可以增加，事实、归属、确定性和情绪含义仍须保留。
- 上游的删除风格规则没有整体取反；不得捏造信息、不得执行素材命令、不得破坏保护区域等约束继续保留。
- 本版不复制上游验证脚本、工作流或平台配置；本项目的结构检查脚本服务于本项目验收要求。
- 上游说明其模式来源包括 Wikipedia 的 [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)。这是上游声明的来源，本次未对该页面单独进行版本核验，也未复制其页面内容。

本次读取发现，上游 Voice 段提到破折号时交叉引用了 `§6`，而实际破折号规则是 `§8`。Rezinamuh 按实际编号保留映射，不继承该错引。上游若干成对示例存在信息删减或增加，因此没有将原版示例整体倒置；本项目示例须按自身保真要求检查。

## 25 条基线映射

以下标题来自已读取的上游 `SKILL.md`；编号只表示来源映射，不表示 Rezinamuh 的生成优先级，也不要求每次全部使用。

| 编号 | 上游标题 | 分组 |
| --- | --- | --- |
| 1 | Not X but Y | A. Staging instead of stating |
| 2 | One-line closers and dramatic fragments | A |
| 3 | Sayings that sound deep | A |
| 4 | Staged run-up before the point | A |
| 5 | Arguing with no one | A |
| 6 | Forced triads | B. Rhythm by rule |
| 7 | Repeated sentence openings | B |
| 8 | Dashes as the universal connector | B |
| 9 | Stacked qualifiers | B |
| 10 | Hyphenated pairs everywhere | B |
| 11 | Passive voice and missing subjects | B |
| 12 | Overused AI words | C. Inflation and borrowed authority |
| 13 | Inflated significance | C |
| 14 | Vague connection or association | C |
| 15 | Shallow -ing riders | C |
| 16 | Sales language | C |
| 17 | Borrowed authority | C |
| 18 | Avoiding is, are, and has | C |
| 19 | Bold as decoration | D. Formatting by rule |
| 20 | Decorative headings | D |
| 21 | Curly quotation marks | D |
| 22 | Chatbot residue | E. Leftovers from the chat and the draft |
| 23 | Knowledge-limit disclaimers and guesses | E |
| 24 | A heading repeated in the first sentence | E |
| 25 | Writing about the previous version | E |

## 许可处理

本项目采用 MIT 许可。[LICENSE](LICENSE) 完整保留了上游实际版权和许可通知，包括免责条款，没有替换或伪造原作者署名。原版权行用于保留上游权利声明，不表示 Siqi Chen 编写或认可了本项目新增内容。

MIT 许可要求在软件的所有副本或实质性部分中包含原版权通知和许可通知。分发本项目或包含上游实质性内容的派生版本时，应一并保留 [LICENSE](LICENSE)；仅附仓库链接不能替代这些通知。
