# 朗文双语词典 OCR 试验（24 页样本）

将扫描版《朗文当代高级英语辞典（英英·英汉双解）第6版》的 24 页正文，经本地 OCR 转为可查询的结构化样本库。不处理全书，不改 UI，不上传原书。

## 环境

- Windows，项目内 `.venv`（Python 3.11）
- RapidOCR 3.9.2 + PP-OCRv6-small，ONNX Runtime DirectML（本机 RTX 5070）
- 渲染：PyMuPDF 将每页 600 dpi JBIG2 单色扫描绘成灰度 PNG（约 3427×5057）

```powershell
cd "D:\Projects\10-Active\Chrome词典插件\research\pdf-dictionary-pilot"
uv venv .venv --python 3.11.15
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe run_pilot.py all
```

分步：`extract` → `ocr` → `parse` → `db`。已完成的页面会跳过；`--force` 重跑。查询：

```powershell
.\.venv\Scripts\python.exe run_pilot.py query cold
```

## 样本页

PDF 页码（从 1 计）：99–104、499–504、999–1004、1999–2004。前后各多 OCR 1 页（98、105…）只用于补全跨页词条。

## 产出

| 路径 | 内容 |
|---|---|
| `output/pages/page_XXXX.png` | 原生分辨率页面图 |
| `output/ocr/page_XXXX.json` | 页级 OCR 行、框、版面 |
| `output/entries.auto.jsonl` | 自动结构化结果（未改） |
| `output/entries.revised.jsonl` | 30 条页面校订，不覆盖自动文件 |
| `output/folio_sample.sqlite` | 可按词头/词组精确查询；校订条 `revised=1` |
| `output/verification.json` | 30 条字段对错统计 |
| `output/report.md` | 质量、耗时、是否扩到全书 |

原始 PDF 不会被修改。结论：**当前自动流程不值得扩到整本当产品词库**；中文短义可作校对底稿，音标不能用。详情见 `output/report.md`。
