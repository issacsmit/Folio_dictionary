# 朗文转换产物复核

日期：2026-09-20。范围：读取实际 ZIP、转换代码、原 MDX 重点样本；运行现有测试与验证，补充独立哈希和引用检查。未修改转换器或重新生成词典包。

## 最新复验：解析器 1.1.0

Grok 修复并重新生成后，本轮针对下列四项问题复验通过。下面的原始发现保留为历史记录，不再表示仍未修复。

- 重跑 22 项测试，全部通过。最初的 3 个测试在沙箱内因 Windows 临时目录权限错误未能执行，使用新建项目临时目录并通过平台权限机制重跑后通过；没有修改测试断言或转换代码。
- 将最终 ZIP 单独复制到新的临时目录后运行 validate_zip，校验通过：60,465 个词条、364,887 个查询键，entry/sense/parent 引用缺失均为 0，重复词条 ID 为 0，包内内容哈希通过。
- 直接检查新包 study 名词第 3 义项：父节点定义为空；真正的中英文“学科”释义保留在子义项。原错误拼接串不再作为该父节点的释义。
- 直接检查新包 U. / v.：英文全称 university / verb / very 已保留，原本内嵌的 versus 没有重复拼接。
- 对最终包执行查询：U. 首结果是缩写 U.，U 首结果是字母 U；v. 与 V 同样区分；run. 可回退到 run。
- 当前包为 17,236,618 字节，parser_version=1.1.0。

结论：本轮阻碍接入的四项问题已通过针对性复验，可以作为下一步插件导入与查词展示的基准包。该结论不等于已逐条校勘全书，不改变纯英文回退、派生词可能无独立释义等已知内容限制。本轮没有扩大到新的全量语义审计，也未开始插件开发。

## 判断

路线已跑通，可以作为数据转换原型。建议先修复下面四项，再作为插件导入与展示的基准词典包。现有测试通过不能代替内容正确性检查；不能把已知的解析错误都视为源词典缺陷。

## 已确认通过

- 16 项 pytest 测试通过；有 pytest 缓存目录权限警告，不影响此次测试结果。
- 现有 validate 命令通过，报告 60,465 个词条、362,784 个查询键、265,545 条处理台账。
- 独立检查 ZIP：entries.jsonl 与 lookup.jsonl 的 SHA-256 均符合包内 manifest；ZIP 的三个文件与 output/unpacked 的对应文件逐字节一致。
- 独立检查最终包全部 lookup 的 sense_id：没有指向所属词条之外或不存在的义项；所有 parent.id 可找到对应词条。
- throughout 的空间／时间义项及中英配对正常；propagation 保留派生词身份及基础词关系；run out of 可以定位到 run out 的相关义项。
- ZIP 为 17,202,841 字节，约 16.4 MiB；包内文件解压后总量约 168.6 MiB。这不等于未来 IndexedDB 占用或运行内存。

## 需要修复

### 1. 搭配／句型被误识别为释义（高优先级）

位置：`longman-conversion/folio_ldoce/parse.py` 的 `extract_definition`（约第 203 行）和 `_sense_def`（约第 444 行）。

最终包 study 名词第 3 义项的父节点 definition.en 为 `study ofliterary/historical/scientific etc study`。实际原文的一个 `.def` 容器只是包着 gramexa、propformprep、colloexa 与例句；真正释义在子义项里：`a subject that people study at a college or university`，对应中文“〔大学里的〕学科﹔学业”。

所以不能只修空格。应区分含真实释义的容器和只含搭配／句型的容器，将后者归入对应字段，父义项可无独立释义。对全量数据检查同类污染；回归测试同时断言真正子义项保留、假释义不存在。

### 2. 缩写全称被漏提取（高优先级）

最终包 U. 英文只剩 `an abbreviation of`；v. 第 1、2 义项只剩 `a written abbreviation of` / `the written abbreviation of`。

直接读取原 MDX 确认 university、verb、very 均存在，在 `.def` 之后的同义项 `.fullform` 标签中。不是原词典没有英文全称，也不应交由 AI 补写。

需要保留同义项的全称关系或正确拼接到释义。其他义项中 fullform 已嵌在英文定义内部，处理时避免重复拼接。建立跨全量缩写样本的回归检查。

### 3. 有意义的句点被归一化掉，缩写与字母查询混淆

位置：`longman-conversion/folio_ldoce/normalize.py` 第 30–36 行及 query.py 排序。

normalize_lookup 去掉首尾句点并 casefold，导致 U. 与 U、v. 与 V 共用查询键；实际 query('U.', limit=1) 显示 U 字母，query('v.', limit=1) 显示 V 字母，而不是缩写。缩写条目仍在后续结果里，但默认首结果与用户输入不符。

保留能区分词头的原始精确键，并优先精确匹配，再用归一化结果补充检索。不能仅靠对所有输入增加大小写敏感来修复普通词查词。测试至少覆盖 U / U. / V / v. 及普通词大小写和句末标点的回退。

### 4. ZIP 验证没有验证目标 ZIP 内的结构

位置：`longman-conversion/folio_ldoce/validate.py` 第 80–90 行。

validate_zip 检查 ZIP 成员名和 CRC 后，调用的是固定 UNPACKED_DIR 的 schema 校验；若该目录不存在，则把 ZIP 路径当目录传给 validate_unpacked，会失败。manifest 中的内容哈希在当前校验函数中也没有核验；它只验证 lookup.entry_id，没有验证 sense_id 和 parent.id。

当前交付包已由本次独立检查确认一致，没有发现坏包。但该验证器不能作为未来导入任意词典包的验收工具。应直接验证指定 ZIP 的实际内容、manifest 哈希、schema、条目及义项／父条目引用，且不依赖项目旁边的解包目录。增加独立 ZIP 的正确／篡改／引用失效测试。避免修改或删除用户现有 unpacked 目录来做测试。

## 修复交付建议

沿用现有实现修复，不重做词典格式或插件。补针对性回归测试，全量重新转换，独立校验新 ZIP，更新 report.md 与问题统计。报告明确区分“原始内容限制”（缺中文、派生词没有独立定义）和“转换程序缺陷”（漏全称、误判释义）。抽样阅读应对照原文，不能只阅读结构化输出后宣布提取正确。

本次不是全书逐义项校勘，未证明全量语义无误，也没有复跑整个转换过程或更改插件功能。
