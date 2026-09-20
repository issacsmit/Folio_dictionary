# 朗文六版英汉 MDX → Folio v1 转换报告

日期：2026-09-20。解析器 1.1.0（复核四项修复后重新全量转换）。工作区：`D:\Projects\10-Active\Chrome词典插件`。实现目录：`research/longman-conversion/`。

## 结论

全量遍历了这份朗文 MDX 的 265,545 条索引，每条都有台账去向，没有把未处理内容计为成功。已生成可独立解包的词典包 `output/longman6-folio-v1.zip`，并提供 `python -m folio_ldoce query` 查词。

**可以进入 Folio 插件接入阶段**，前提是显示层实现：有中文显示中文并保留英文；无中文显示原英文。不要宣传为完整中文词库。本包不含例句、音频、图片，也不含原 MDX/MDD。

## 与已有审计对照

| 项目 | 已有审计 | 本次 |
| --- | ---: | ---: |
| 索引记录 | 265,545 | 265,545 |
| `@@@LINK=` 跳转 | 212,797 | 212,797（全部 `alias_mapped`） |
| 非跳转 | 52,748 | 52,748 |
| 无标准 `.def` | 412 | 411 条 `see_also` + 1 条音标表 `faq-about`（有意排除） |

条目数与索引数不同是预期：一条非跳转 HTML 常含多个 homograph、短语动词和 run-on。不能把 265,545 或 52,748 说成独立单词数。

## 产出数量

| 项目 | 数量 |
| --- | ---: |
| 词条（entries.jsonl） | 60,465 |
| 其中主词 / 派生 / 短语动词 / 参见 | 50,877 / 6,878 / 2,299 / 411 |
| 查询键（lookup.jsonl） | 364,887 |
| 双解义项 | 78,919 |
| 纯英文义项 | 13,842 |
| 纯中文义项 | 0 |
| 无独立释义义项（词组框、参见等） | 2,025 |
| 主词转换 / 派生定位页 / 参见 / 辅助页排除 | 46,616 / 5,720 / 411 / 1 |
| 别名已映射 / 失效 / 循环 / 解析失败 | 212,797 / 0 / 0 / 0 |
| 问题清单 | 1（`faq-about` 音标表，有意排除） |

## 体积与耗时（实测）

| 项目 | 实测 |
| --- | --- |
| 源 MDX | 175,656,956 字节，SHA-256 `d5c77423436f08bdd6e275bc5f25b4fac0a1f2c3f74193295c19360e103f287d` |
| 词典包 ZIP | 17,236,618 字节（约 16.4 MiB） |
| ZIP 内 entries.jsonl / lookup.jsonl / manifest.json | 75,870,514 / 101,354,572 / 2,870（未压缩） |
| 转换墙钟时间 | 114.999 秒 |
| 峰值 RSS | 828,903,424 字节（790.5 MiB） |
| 读取完整性 | 记录数与 `len(mdx)` 一致；抽样 3 个记录块 `errors=replace` 的 U+FFFD 为 0；块类型 zlib 18,662 + none 90。readmdict 仍对逐条记录使用 `errors='ignore'`。 |

未解包 MDD（约 1.21 GiB 音频）。

## 必查样本（自动结构 + 代理阅读）

对照 `samples.raw.json` 与实际查询，不是只看字符串出现。

| 查询 | 结果 | 阅读标记 |
| --- | --- | --- |
| throughout | 词头/音标 `θruːˈaʊt`；介词+副词；空间「遍及」与时间「自始至终」两个义项，中英同属义项 | 自动 + 代理 |
| fish | 名词/动词分开；义项均为英文、`zh=null`；未混入词族或其他词释义 | 自动 + 代理 |
| point | 名词义项为观点/地点等，动词与 `point out` 另条，未把词族 POS 混进名词 | 自动 + 代理 |
| run | 动词与名词 homograph 分开，短语动词另条 | 自动 + 代理 |
| cold / light / account / almighty | 有中文；account 含 take account of / take something into account | 自动 + 代理 |
| studies | `@@@LINK=study`，查询以 alias 落到 study 名词/动词，词头是 study | 自动 + 代理 |
| study / went / indices | study 第3义项子义项为学科，父节点不再把搭配当释义；went 为过去式；indices 英文含 index | 自动 + 代理 |
| propagation / refraction | 派生词条，词头是 propagation/refraction，不是动词义项伪装 | 自动 + 代理 |
| chatbot | 仅英文 | 自动 + 代理 |
| threescore | 英文 `60` 保留，中文「六十」 | 自动 + 代理 |
| run out of | 命中短语动词 `run out`，义项「用完」 | 自动 + 代理 |
| take into account | 命中 account 义项，源中 `.lexvar` | 自动 + 代理 |

## 复核修复（转换程序缺陷，不是原词典缺内容）

对照 `research/longman-conversion-review.md` 与原 MDX：

1. **搭配误作释义**：`study` 第 3 义项父节点不再出现 `study ofliterary/historical/scientific etc study`。该 `.def` 只含句型/搭配/例句，现归入 `patterns`；真正释义留在子义项“a subject that people study at a college or university / 〔大学里的〕学科﹔学业”。
2. **缩写全称**：同义项旁的 `.fullform` 已拼进英文。`U.` → `an abbreviation of university`；`v.` 第 1、2 义项含 `verb` / `very`。已嵌在 `<en>` 内的 versus/volt 不重复拼接。
3. **句点查询**：`U.` / `v.` 精确键保留；查 `U.` 先出缩写，查 `U` 先出字母。`run.` 仍回退到 `run`。
4. **ZIP 校验**：`validate_zip` 只读指定 ZIP 内文件，核验 manifest 哈希、schema、entry/sense/parent 引用，不依赖 `output/unpacked`。复制到临时目录的 ZIP 同样通过。

回归测试 22 项通过。独立复制 ZIP 校验：entries 60465，lookup 引用 / sense_id / parent.id 缺失均为 0。

## 限制（原始内容，不是这次转换漏做）

- 约 15% 主义项无中文，按英文回退，无 AI 补写。
- 派生 run-on 多数无独立定义，只保留词头、音标、词性及指向基础词的关系。
- 查询会为搭配建立键，但 CLI 已把词头/别名排在其他词的搭配之前。
- 个别短语动词条目级参见可能带上后起义项的交叉引用（如 `run out` 仍见 cricket）。
- 个别缩写若原文就把全称写在非常规位置，仍可能不完整；已处理标准 `.fullform` 旁置与 `<en>` 内嵌两种。
- 随机字母抽样因按「该字母下先遇到的 key」取样，短词和缩写偏多；类型覆盖（双解/纯英文/参见/多义/派生）仍有。

## 建议

可以开始做 Folio 导入与查词卡，只读本包。不要改原 MDX，不要把本包或释义样本公开发布。
