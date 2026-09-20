# Folio 词典包 v1 协议（朗文六版英汉 MDX）

解析器版本：`1.0.0`。格式：`folio-dict-pack` / `1.0`。

本协议根据真实 HTML 结构确定，不是先抽象后套数据。字段供未来 Folio 导入使用，不锁定视觉排版，不截断释义，不只保留首义项。

## 包内容

最终 ZIP：`output/longman6-folio-v1.zip`

| 文件 | 说明 |
| --- | --- |
| `manifest.json` | 格式版本、包标识、源 MDX 路径与 SHA-256、解析器版本、计数、校验。来源版本仅为文件自述，不声称已获出版社授权。 |
| `entries.jsonl` | UTF-8，每行一条词条。 |
| `lookup.jsonl` | 规范化查询键 → 词条／义项，一对多，不覆盖。 |

不捆绑运行代码、原 HTML/JS/CSS、字体、图片、音频、MDX/MDD。

## 词条

- `id`：优先用正文里词条内侧锚点（不含 `LDOCE6_` 定位锚点），同拼写多词条（homograph）互不覆盖。
- `kind`：`word` 主词；`derived` 派生／run-on；`phrasal_verb` 短语动词；`see_also` 无标准 `.def` 的参见项。
- `headword` / `display`：显示词头。`homograph` 为原上标号，没有则为 `null`。
- `source.mdx_keys`：到达该词条的原 MDX key。`source.anchor` 为原锚点。
- `pronunciations[]`：`ipa` + `accent`（`br` / `us` / `unspecified`）。英式取 `.pron`，美式取 `.amevarpron`（去掉 `$`）。没有则空数组，不编造。保留 Unicode 与 `<i>` 中的音标字符。
- `pos_groups[]`：词性分组；`grammar` 为可数性／及物性等；`labels` 为语体／地区／领域，带 `scope`。
- 义项 `definition.en` / `definition.zh`：同属一个义项。缺译为 `null`，不写“暂无翻译”。数字释义（如 `60`）保留。子义项在 `senses`。
- 词组：义项上的 `lexunits`／`patterns`，以及条目级 `phrases`（搭配）。短语动词是独立词条，`parent` 指向主词。
- 交叉引用：`cross_refs`，避免去掉 HTML 链接时丢失“a plural of index”这类解释。

## 查询键

`lookup.jsonl` 的 `norm`：NFKC、折叠空白、casefold、弯引号改直引号。**保留连字符、撇号，以及能区分词头的句点**（`U.` 与 `U` 不同键）。查询先精确匹配，再用去掉首尾句点的松键回退，因此 `run.` 仍能查到 `run`。

同一 `norm` 可对应多条 `matches`（`headword` / `alias` / `inflection` / `phrase` / `phrase_pattern` / `phrasal_verb` / `derived_locator` / `mdx_key`）。

短语变体只从原形、`somebody/something` 槽、`↔`、源中 `.lexvar`／`.propformprep` 生成，不为例句造入口。

## 模块取舍

| 模块 | 处理 | 理由 |
| --- | --- | --- |
| 主 `.entry` 词头、`.sense` / `.subsense`、`.def` 的 `en`/`tran` | 保留 | 主释义，中英文必须配对 |
| `.lexunit`、`.phrvbentry`、`.propform(prep)`、`.lexvar` | 保留 | 词组／短语动词／句型 |
| `.runon` / `.deriv` | 保留为 derived | 派生词有独立词头／音标；无定义时不把动词释义伪装成名词释义 |
| `.collobox` 本词搭配 | 保留名称，解释可空 | 有价值搭配 |
| `.registerlab` `.geo` `.gram` `.ac` | 保留为标记 | 影响理解 |
| `.tail` / `.crossref` | 保留 | 参见项；412 条无 `.def` 记录主要是这一类 |
| `.at-link` 内 Examples / Thesaurus / Collocations from other entries / Word family / Word origin | **丢弃** | 内含其他词的 `.def`/`.pos`，会污染当前词 |
| `.verbtable` `.grambox` `.usagebox` `.thesbox` `.etymology` | **丢弃** | 拓展模块，不是当前词主释义 |
| `script` / 原 CSS / 音频 / 图片 | **丢弃** | 禁止执行词典脚本；初版只要文字和音标 |
| `@@@LINK=` | 别名映射，不复制正文 | 如 `studies → study`；检测循环与失效目标 |

未闭合的 `.buttons` 常包住后文，**不能整段删除**，只删其中的 `.at-link`。

## 派生定位页

`propagation`、`refraction` 等 MDX key 指向含基础动词的页面（词头是 `propagate` / `refract`）。该 key 的查询只映射到 run-on 派生词条，不把动词义项当作该名词的定义。

## 台账状态（互斥，按 MDX key）

- `converted` 主词转换
- `converted_derived_locator` 派生定位页
- `converted_crossref` 参见项（无标准 def）
- `converted_partial` 有问题但仍产出
- `alias_mapped` / `alias_unresolved` / `alias_cycle`
- `error` 无法解析，写入问题清单，不静默丢弃
