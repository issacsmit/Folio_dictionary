# 依赖与许可

本转换程序**不**自行宣布为 MIT。

## readmdict

- 使用方式：运行时导入已有 `readmdict.py`（优先项目 `tmp/mdx-audit-uv-cache` 中的 0.1.1 副本），不把该文件复制进本包再换许可。
- PyPI 包装器 `readmdict 0.1.1` 的元数据声称 MIT。
- 实际 `readmdict.py` 文件头为 **GNU GPL v3**（Copyright Xiaoqiang Wang）。
- 因此：分发本转换工具时必须遵守 GPL-3 对衍生作品的要求；本目录内自写代码未另选与之冲突的许可证声明。

## 其他

- lxml：BSD 系列
- jsonschema：MIT
- pytest / psutil：测试与资源统计，非词典包内容

## 词典内容

朗文 MDX、生成的 `entries.jsonl` / 词典包、含释义的样本与测试输出都不是可公开发布的数据。本次不上传、不发布、不创建 PR。
