# 山区应急物资运输与通信保障：LaTeX 论文工程

阅读入口：项目上一级的 `论文_完善稿.pdf`。编辑入口：`main.tex`。

这是根据题面、原始附件、统一计算结果和模型说明组织的完整正文。章节按论证需要安排，并采用图前引入—图后解释、流程图与数据图分工的写法。

## 内容组织

- `sections/abstract.tex`：方法摘要及明确的阶段边界。
- `sections/problem.tex`：四问分析与总体技术路线。
- `sections/assumptions_symbols.tex`：假设与符号。
- `sections/data_physics.tex`：重新核对的需求数据、机型参数、地形/能量/充电公共模型。
- `sections/q1_batching.tex` 至 `q4_partition.tex`：四问数学模型、求解与结果解释口径。
- `sections/validation.tex`：模型检验、已完成的敏感性实验、误差分析与评价。
- `sections/discussion.tex`：四问结论、适用边界和执行建议。
- `figures/data/`：从原始附件重新生成的PDF/PNG；`figures/common/`：总体路线TikZ图源。其他局部示意直接位于对应章节的figure中。
- `tables/`：原始需求汇总表；`appendix/`：统计明细和输出字段口径。
- `references.bib`：包含题目与数据附件，以及经检索核验并在正文中实际引用的外部文献。

## 当前内容

正文已经纳入四问的模型、算法、流程图、计算结果与解释，并补充模型检验、敏感性实验、误差分析、模型评价、结论和参考文献。数值以当前统一结果链为准；旧版本输出不作为本文依据。

## 模板与构建

由 math-modeling 的 `latex_paper.py init --contest cumcm` 初始化其通用 ctex 构建基线后编辑。`latex-project.json`中的cumcm仅记录初始化来源，不表示本项目参加国赛。目标竞赛为2026第二十三届华为杯；格式参考项目已有 `论文格式规范.txt` 与 `官方资料/第二十三届华为杯论文模板.docx`，本版为按照现有格式规范排版的正文稿，并非组委会发布的官方 LaTeX 模板。

组委会2026-09-21提醒要求正式提交稿保留官方封面和4个LOGO，摘要与正文从第二页起；本版未制作含队伍信息的封面，不能直接提交。来源：https://cpipc.acge.org.cn/cw/contestNews/list/4/1 。截止时间和最终上传细节应在最终提交前再核验。本次不执行提交。

本机可从paper目录预览：

```powershell
latexmk -norc -xelatex -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

受控交付使用 `latex_paper.py build paper/main.tex --engine xelatex --publish 论文_完善稿.pdf --overwrite`，在上一级项目目录运行。该链路同时生成源码/PDF绑定记录。图片来源绑定 `../audit/paper_20260924/assets/`；数据图与表的生成入口为 `../audit/paper_20260924/prepare_inputs.py`，需要原项目附件及可用Python环境。

生成本稿使用了OpenAI Codex辅助内容整理、LaTeX编写、数据图制作与检查；不能照抄旧源码中关于模型版本的声明。最终AI使用说明由队伍按本次及此前实际使用情况统一整理。
