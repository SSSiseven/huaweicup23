# 山区应急物资运输与通信保障：阶段性论文工程

阅读入口：项目上一级的 `阶段性论文初稿.pdf`。编辑入口：`main.tex`。

这是根据现有题面、原始附件和模型说明组织的阶段性正文，章节按论证需要安排，并未机械照搬目录示例。参考两篇优秀论文的递进结构、图前引入—图后解释、流程图与数据图分工。

## 内容组织

- `sections/abstract.tex`：方法摘要及明确的阶段边界。
- `sections/problem.tex`：四问分析与总体技术路线。
- `sections/assumptions_symbols.tex`：假设与符号。
- `sections/data_physics.tex`：重新核对的需求数据、机型参数、地形/能量/充电公共模型。
- `sections/q1_batching.tex` 至 `q4_partition.tex`：四问数学模型、求解与结果解释口径。
- `sections/validation.tex`：尚待执行的验证与敏感性实验设计。
- `sections/discussion.tex`：适用边界和阶段性认识。
- `figures/data/`：从原始附件重新生成的PDF/PNG；`figures/common/`：总体路线TikZ图源。其他局部示意直接位于对应章节的figure中。
- `tables/`：原始需求汇总表；`appendix/`：统计明细和输出字段口径。
- `references.bib`：本版仅纳入实际读取的赛题及附件，未复制未经本轮核验的外部参考文献。

## 本版可用与待续写部分

已写入的是数据统计、模型定义与求解方法。原有求解器尚存在航段最高地形漏采样、Q4波次关系代替实际中继保障关系的问题，详见 `../audit/20260924/现状审查与问题清单.md`。受影响的旧结果表和结果派生图均未进入本稿；这些问题本轮没有修改。

后续修正并重算后，在每问末尾增写实际结果分析，替换阶段说明；补入安全载荷、路线与资源甘特图、连续通信结果、分区资源表、实际敏感性实验。模型正文中已经给出各类结果应如何验证和解释。

## 模板与构建

由 math-modeling 的 `latex_paper.py init --contest cumcm` 初始化其通用 ctex 构建基线后编辑。`latex-project.json`中的cumcm仅记录初始化来源，不表示本项目参加国赛。目标竞赛为2026第二十三届华为杯；格式参考项目已有 `论文格式规范.txt` 与 `官方资料/第二十三届华为杯论文模板.docx`，本版为正文预览，不是官方LaTeX模板或最终参赛PDF。

组委会2026-09-21提醒要求正式提交稿保留官方封面和4个LOGO，摘要与正文从第二页起；本版未制作含队伍信息的封面，不能直接提交。来源：https://cpipc.acge.org.cn/cw/contestNews/list/4/1 。截止时间和最终上传细节应在最终提交前再核验。本次不执行提交。

本机可从paper目录预览：

```powershell
latexmk -norc -xelatex -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

受控交付使用技能的 `latex_paper.py build paper/main.tex --engine xelatex --publish 阶段性论文初稿.pdf --overwrite`，在上一级项目目录运行。该链路同时生成源码/PDF绑定记录。图片来源绑定 `../audit/paper_20260924/assets/`；数据图与表的生成入口为 `../audit/paper_20260924/prepare_inputs.py`，需要原项目附件及可用Python环境。

生成本稿使用了OpenAI Codex辅助内容整理、LaTeX编写、数据图制作与检查；不能照抄旧源码中关于模型版本的声明。最终AI使用说明由队伍按本次及此前实际使用情况统一整理。
