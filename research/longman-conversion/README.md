# 朗文六版英汉 MDX → Folio 词典包

将本地 `电子词典/电脑版~朗文当代第六版英汉/朗文当代第六版（英汉）.mdx` 转为 Folio v1 词典包。不修改原文件，不实现 Chrome 插件或 UI。缺中文时保留英文，不用 AI 补写。

协议见 `PROTOCOL.md`。许可与 readmdict（GPL-3）见 `LICENSES.md`。

## 环境

本目录隔离虚拟环境，不改用户全局 Python。

```text
cd /d D:\Projects\10-Active\Chrome词典插件\research\longman-conversion
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## 命令

在 `research/longman-conversion` 下：

```text
.venv\Scripts\python -m pytest tests
.venv\Scripts\python -m folio_ldoce convert
.venv\Scripts\python -m folio_ldoce validate
.venv\Scripts\python -m folio_ldoce verify
.venv\Scripts\python -m folio_ldoce query fish
.venv\Scripts\python -m folio_ldoce query "run out of"
.venv\Scripts\python -m folio_ldoce query throughout
```

`query` 读取 `output/longman6-folio-v1.zip`（也可 `--pack output\unpacked`）。`validate --zip` 只校验该 ZIP 自身，不依赖旁边的解包目录。

## 产物

- `output/longman6-folio-v1.zip` — 可独立解包的词典包
- `output/unpacked/` — manifest / entries.jsonl / lookup.jsonl
- `output/ledger.jsonl` — 每条 MDX 索引的去向
- `output/issues.jsonl` — 无法解析或别名失败
- `output/stats.json` — 计数与耗时
- `output/random_sample.json` — 固定种子字母区间抽样
- `report.md` — 结论

原 MDX/MDD 只读。
