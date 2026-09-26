#!/usr/bin/env python3
"""Build the stage-2 Word paper draft from frozen D-problem evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


ROOT = Path(__file__).resolve().parent
SKILL_ROOT = ROOT / ".agents" / "skills" / "math-modeling"
DOCX_SCRIPTS = SKILL_ROOT / "tools" / "docx" / "scripts"
sys.path.insert(0, str(DOCX_SCRIPTS))
import paper_format as pf  # noqa: E402


TEMPLATE = ROOT / "官方资料" / "第二十三届华为杯论文模板.docx"
OUTPUT = ROOT / "完整论文.docx"
CHECKPOINT = ROOT / "checkpoints" / "完整论文-V1.docx"


def read_csv(name: str) -> list[dict[str, str]]:
    with (ROOT / "results" / name).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def set_font(run, east="宋体", size=12, bold=False):
    return pf.set_run_font(run, east, size, bold)


def paragraph(doc, text="", first=True, align=WD_ALIGN_PARAGRAPH.JUSTIFY, bold_prefix=None):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    if first:
        p.paragraph_format.first_line_indent = Pt(24)
    if bold_prefix and text.startswith(bold_prefix):
        set_font(p.add_run(bold_prefix), bold=True)
        set_font(p.add_run(text[len(bold_prefix) :]))
    else:
        set_font(p.add_run(text))
    return p


def h1(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(text), "黑体", 14, False)
    return p


def h2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(text), "黑体", 12, False)
    return p


def h3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    set_font(p.add_run(text), "宋体", 12, True)
    return p


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def table(doc, title, rows, font_size=9):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    set_font(p.add_run(title), "宋体", 10, False)
    t = pf.three_line_table(doc, rows)
    set_repeat_table_header(t.rows[0])
    for ri, row in enumerate(t.rows):
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for para in cell.paragraphs:
                para.paragraph_format.space_before = Pt(0)
                para.paragraph_format.space_after = Pt(0)
                para.paragraph_format.line_spacing = 1.0
                for run in para.runs:
                    set_font(run, "宋体", font_size, ri == 0)
    return t


def figure(doc, number, filename, caption, width=14.2):
    pf.image(doc, ROOT / "figures" / filename, width_cm=width)
    pf.figure_caption(doc, f"图{number}  {caption}")


def clear_element(element):
    for child in list(element):
        element.remove(child)


def add_page_number(section, restart=None):
    section.header.is_linked_to_previous = False
    clear_element(section.header._element)
    section.footer.is_linked_to_previous = False
    footer = section.footer
    clear_element(footer._element)
    p = footer.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.extend([fld_char1, instr, fld_char2])
    set_font(run, "宋体", 10)
    if restart is not None:
        sect_pr = section._sectPr
        pg_num = sect_pr.find(qn("w:pgNumType"))
        if pg_num is None:
            pg_num = OxmlElement("w:pgNumType")
            sect_pr.append(pg_num)
        pg_num.set(qn("w:start"), str(restart))


def add_cover(doc):
    section = doc.sections[0]
    clear_element(section.header._element)
    clear_element(section.footer._element)
    for _ in range(2):
        paragraph(doc, "", first=False)
    for text, size in [
        ("中国研究生创新实践系列大赛", 18),
        ("“华为杯”第二十三届中国研究生", 20),
        ("数学建模竞赛", 20),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(6)
        set_font(p.add_run(text), "黑体", size, True)
    for _ in range(4):
        paragraph(doc, "", first=False)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("参赛论文封面"), "黑体", 18, True)
    paragraph(doc, "", first=False)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("题  目：山区洪涝灾害下无人机运输与通信协同优化"), "宋体", 14, False)
    paragraph(doc, "", first=False)
    for text in ["学    校：", "参赛队号：", "队员姓名：1.", "队员姓名：2.", "队员姓名：3."]:
        p2 = doc.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p2.add_run(text + " " * 24), "宋体", 12)


def add_abstract(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    set_font(p.add_run("山区洪涝灾害下无人机运输与通信协同优化"), "黑体", 16, False)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run("摘 要"), "黑体", 14, False)
    abstract = (
        "针对山区洪涝灾害中道路中断、地形起伏、装备异构、能源周转与通信遮挡并存的应急投送问题，本文建立从单点运输能力、异构多架次调度、运输—中继联合调度到任务分区配置的递进模型。首先依据30 m数字高程模型逐航段确定安全巡航海拔，将载荷相关等效航程、爬升附加能耗和返航余量统一到可复算的飞行合同中；对单服务区货箱集合采用安全载荷反演与集合划分动态规划，在“架次数—能耗—作业时间”的字典序目标下求得组批方案。结果表明，80个不可拆货箱可由18个单点往返架次唯一覆盖，总运输能耗为59.231986 kWh，累计作业时间为32777.291307 s，最小返航SOC为22.7893%。"
        "进一步将多点路线、逐箱交接、实体无人机、共享电池和两阶段充电过程耦合，构造硬时限优先、及时性与完成时间协同的异构调度启发式。所得方案包含26个运输架次和5个多站架次，31个硬时限货箱全部按时，最小硬时限松弛为2375.085931 s；全部运输任务在12695.763194 s完成，总能耗83.001330 kWh，加权相对延误为111.450075。"
        "在通信约束下，本文用DEM视距、自由空间传播损耗和双向最弱链路预算刻画直连及单中继可用性，以事件区间自适应细分生成连续覆盖证书，并把中继的准备、建链、悬停、返航及能源组件周转嵌入运输波次。最终26个运输架次分8个波次执行，其中7个波次需要13个中继架次，使用2架中继无人机和5套能源组件；连续区间证书与0.5 s网格的77178个采样点均无中断，最小保守链路余量为0.130757 dB。运输完成时刻为23918.718636 s，计及最后一架中继机返航后的联合完成时间为24472.376375 s，总能耗为95.719762 kWh。"
        "最后将问题三的共访关系压缩为10个不可拆原子任务块，分别穷举2组的511种无重复分区和3组的18660种带标签分区。两组方案仅缺2架中继机；三组方案缺4架中继机与2套中继能源组件，且工作量均衡性更差。返航余量、地面延迟和附加链路裕量的敏感性实验揭示了方案的稳定区间：安全余量不超过20%时单点组批保持18架次，地面统一延迟1200 s仍不触发硬时限违约，而附加链路裕量达到0.2 dB后通信证书开始失效。模型以连续通信证书、资源时间轴和全量守恒复算形成闭环，为山区灾后空地协同投送与资源预置提供可执行依据。"
    )
    paragraph(doc, abstract)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    set_font(p.add_run("关键词："), "宋体", 12, True)
    set_font(p.add_run("无人机应急运输；异构多架次调度；空中通信中继；连续覆盖证书；任务分区；资源配置"), "宋体", 12)


def eq(doc, latex, explanation=None):
    pf.equation(doc, latex)
    if explanation:
        paragraph(doc, explanation)


def build():
    with (ROOT / "results" / "full_results.json").open("r", encoding="utf-8") as f:
        full = json.load(f)
    q1_batches = read_csv("q1_batches.csv")
    q1_payload = read_csv("q1_safe_payload.csv")
    q2_trips = read_csv("q2_transport_trips.csv")
    q2_deliveries = read_csv("q2_box_deliveries.csv")
    q3_trips = read_csv("q3_transport_trips.csv")
    q3_relays = read_csv("q3_relay_missions.csv")
    q3_segments = read_csv("q3_communication_segments.csv")
    q4_groups = read_csv("q4_partition_resources.csv")
    q4_resources = read_csv("q4_shortage_redundancy.csv")
    sens_q1 = read_csv("sensitivity_q1_reserve.csv")
    sens_q2 = read_csv("sensitivity_q2_delay.csv")
    sens_q3 = read_csv("sensitivity_q3_margin.csv")

    doc = pf.new_document(contest="cumcm", template_path=TEMPLATE, preserve_template_content=False)
    add_cover(doc)
    abstract_section = doc.add_section(WD_SECTION_START.NEW_PAGE)
    add_page_number(abstract_section, restart=1)
    add_abstract(doc)
    doc.add_page_break()

    h1(doc, "1  问题重述")
    paragraph(doc, "洪涝灾害使山区道路、供电与通信设施同时受损，传统地面运输难以及时覆盖分散居民点。题目给出1个临时调度中心、15个服务区、80个不可拆货箱、3类共8架运输无人机，以及共享电池、中继无人机、可更换能源组件、通信参数和30 m分辨率DEM。需要在同一套物理口径下回答运输能力、时限调度、连续通信和任务分区四个递进问题。")
    paragraph(doc, "问题一忽略实体机和共享电池并发，仅考察单服务区直接往返。核心是先判断每个机型—服务区组合的最大安全载荷，再在质量、体积和返航余量约束下对同一服务区货箱精确组批，并解释架次数、能耗与作业时间的优先关系。问题二允许单架次连续访问多个服务区，需要把路线、逐箱交接、硬软时限、实体机与电池周转共同排程。")
    paragraph(doc, "问题三要求运输机在准备后的起飞、爬升、巡航、下降和投送全过程保持通信。直连不可用时，只能借助一架空中中继建立两段同时可用的链路，因此中继位置、服务时段、建链提前量和能源资源必须与运输波次同步。问题四不允许改变问题三的路线和通信关系，只能按共访连通关系把15个服务区分为2组或3组，并独立核算每组资源需求、冗余、工作量和库存缺口。")
    paragraph(doc, "四问之间形成严格的数据继承链：问题一提供单点可行性和载荷边界；问题二形成运输路线与资源时间轴；问题三在冻结运输任务集合的基础上加入通信并允许整体延后形成波次；问题四仅对问题三方案做不可拆分区。这样可以避免各问采用不同能耗、时刻或资源口径而导致结论互相矛盾。")

    h1(doc, "2  问题分析")
    h2(doc, "2.1  难点分解与总体路线")
    paragraph(doc, "本题的第一项难点是地形、载荷与能源的耦合。航段巡航高度取沿线DEM最高点再加50 m，爬升量随起终点作业高度变化；载荷又同时影响等效航程和水平能耗。因此不能只按平面距离或额定载重判断可行性，而需逐段跟踪剩余载荷。本文先缓存任意节点对的DEM剖面和几何参数，再对给定路线执行统一飞行仿真。")
    paragraph(doc, "第二项难点是离散组合与连续时间耦合。货箱不可拆、服务区访问次序离散，而无人机、电池充电和中继悬停又由连续时刻约束。若直接构造一个巨型混合整数模型，会产生大量路线、充电和链路状态变量。本文采用“精确求解局部组合—启发式生成全局路线—确定性资源排程—连续证书复核”的分层策略：问题一局部精确，问题二和问题三寻求高质量可行解并明确不宣称全局最优。该思路与无人机路径能耗建模及自适应大邻域搜索文献的结构化分解思想一致[1-5]。")
    paragraph(doc, "第三项难点是通信连续性。固定时间网格只能说明采样点未中断，不能排除采样点之间的短时失联。本文把飞行轨迹按直线段与作业段参数化，对链路余量函数进行区间下界估计；当区间无法直接证明安全时继续二分，直至获得覆盖全时域的叶区间证书。同时保留0.5 s网格作为独立数值复核，而不把网格零中断等同于严格连续证明。")
    paragraph(doc, "第四项难点是分区资源不能简单按服务区数量平均。若一个运输架次访问多个服务区，这些节点必须同组；而中继波次被多个运输架次共享，拆组后需要复制相应中继保障，导致资源冗余。故先建立共访图，压缩成原子任务块，再穷举小规模分区并按时间区间重算各组最少资源。")
    h2(doc, "2.2  多目标优先关系")
    paragraph(doc, "灾害调度中的目标并非等价。硬时限违约意味着医疗或首批保障失败，不能由少量能耗节省补偿；通信中断意味着任务过程失去指挥，也不能与完成时间做连续加权。因此本文不使用主观权重把所有指标压成一个加权和，而采用层级或字典序比较。问题一先减少往返次数，再比较能源和作业时间；问题二先保证硬时限，再比较软迟到、完成时间、能耗和架次；问题三在此基础上把通信中断置于最高可行性层；问题四先比较库存缺口，再比较冗余和工作量均衡。")
    paragraph(doc, "这种优先关系带来两个好处。其一，目标含义清楚，不会因为量纲和归一化方式改变而得到完全不同的救援方案；其二，每次局部改进都可以解释为对更高优先级目标不造成损害。代价是无法画出完整帕累托前沿，且同一层内仍需选择次序。为检验次序影响，我们保留架次数、能耗、时间、迟到和资源规模等分项结果，不仅报告一个综合得分。")
    h2(doc, "2.3  四问的数据继承与闭环")
    paragraph(doc, "问题一的安全载荷表不是直接作为问题二固定载重上限，而是用于发现显然不可行的机型—节点组合；问题二对每条多点路线仍逐段重新计算剩余载荷和能耗。问题二输出的路线、箱级交付顺序、实体机和电池安排成为问题三的运输任务输入；问题三可整体延后波次以等待中继，但不更改组批和访问次序。问题四只读取问题三冻结后的运输与中继区间，分组后复制依赖任务，不重新优化路线。")
    paragraph(doc, "每一层都有可回查的守恒关系：服务区需求质量等于所属货箱质量之和，架次装载等于货箱集合求和，逐箱交付集合等于原始80箱集合；运输路线段时间之和加准备、交接得到返航时刻；中继出航、建链、服务和返航构成完整占用；分组服务区并集等于15个服务区且两两不交。若任一守恒不满足，后续层不再求解，从而避免错误在四问之间放大。")
    h2(doc, "2.4  数据处理与可信性说明")
    paragraph(doc, "所有坐标统一转换到局部等距平面用于距离和DEM采样，海拔统一使用m、时间使用s、能量使用kWh、功率使用kW、路径损耗和链路余量使用dB。30 m高程数据的产品背景参见Copernicus DEM说明[9]，正式计算以题目附件为准。80个货箱以唯一编号为守恒键，任何方案均检查“恰好交付一次”；实体机、电池、中继机和能源组件均以半开时间区间检查占用冲突。模型的随机种子固定为20260923，数据对象概况见表1。")
    paragraph(doc, "数据分析说明：本文在附件读取、异常定位、代码调试、可视化排版和文字组织过程中参考了人工智能工具OpenAI Codex（模型GPT-5，开发机构OpenAI，版本发布日期2025-08-07）的输出。参赛者对模型假设、公式来源、算法逻辑、全部数值和图表进行了理解、重算与人工取舍；文中数学关系均来自题设规则、明确推导或正式文献，不采用无法确认来源的公式。相关工具信息见文献[10]。")
    table(doc, "表1  数据对象、规模与主要用途", [
        ["数据对象", "规模", "主要用途"],
        ["调度中心与服务区", "1+15个节点", "坐标、海拔、作业位置"],
        ["不可拆货箱", "80箱", "质量、体积、类别、时限与优先级"],
        ["运输装备", "3类、8架", "航程、速度、功率、载重和电池"],
        ["通信装备", "2架中继、6套能源组件", "悬停、链路与周转"],
        ["数字高程模型", "30 m网格", "航段最高地形与视距遮挡"],
        ["通信参数", "双向接口参数", "路径损耗预算和可用性判定"],
    ])

    h1(doc, "3  模型假设与符号说明")
    h2(doc, "3.1  模型假设")
    assumptions = [
        "（1）附件给定的坐标、DEM、装备参数、需求和时限构成标准测试场景；气象扰动已由安全高度、额定参数和返航余量吸收，不另外构造未经给定的风场。",
        "（2）运输航段为节点间水平直线，巡航海拔等于沿线DEM最高高程加50 m；服务区投送后回到离地30 m作业高度，再进入下一航段。",
        "（3）货箱不可拆且只交付一次；同一服务区内按货箱编号顺序完成交接，完成时刻包含逐箱交接耗时。",
        "（4）实体无人机一次只执行一个架次；同一共享电池或能源组件的占用与充电区间不得重叠。任务后按题设两阶段模型充至100%才能再次投入。",
        "（5）通信只允许“运输机—G01”直连或“运输机—单架中继—G01”两跳模式，不允许中继间多跳；两个方向均满足链路预算才视为可用。",
        "（6）中继候选悬停点由DEM覆盖范围内的探索性预筛得到，最终可行性由完整轨迹的连续区间证书决定。候选点预筛不构成悬停位置全局最优证明。",
        "（7）问题四保持问题三的货箱组批、访问顺序、运输任务与中继保障关系不变。跨服务区架次诱导的共访连通分量不可拆；各组独立执行时不共享资源。",
    ]
    for a in assumptions:
        paragraph(doc, a)
    h2(doc, "3.2  主要符号")
    paragraph(doc, "全文的核心符号、含义与量纲统一列于表2，后续各节不再重复定义。")
    table(doc, "表2  主要符号及含义", [
        ["符号", "含义", "单位"],
        ["i,j", "任务节点索引", "—"],
        ["k,u,b", "机型、实体无人机、货箱索引", "—"],
        ["d_ij", "节点i到j的水平距离", "m"],
        ["H_ij", "航段计划巡航海拔", "m"],
        ["q", "航段当前有效载荷", "kg"],
        ["E_r,T_r", "架次r的能耗和持续时间", "kWh，s"],
        ["rho_k", "机型k返航安全余量", "1"],
        ["C_b", "货箱b交付完成时刻", "s"],
        ["C_max", "最后一架相关无人机返航时刻", "s"],
        ["L_path,L_max", "总传播损耗与双向允许损耗", "dB"],
        ["M_link", "链路余量L_max-L_path", "dB"],
        ["n_ka", "组k对资源a的独立需求", "架或组"],
        ["D_a,R_a", "资源缺口与分区冗余", "架或组"],
    ])

    h1(doc, "4  公共物理模型")
    h2(doc, "4.1  地形航段、时间与能耗")
    paragraph(doc, "对节点i与j，以局部平面坐标计算水平距离；沿线按DEM像元穿越序列提取最高地面高程，叠加题设50 m净空得到计划巡航海拔。起点和终点作业海拔分别由节点地面高程以及服务区30 m作业高度确定。")
    eq(doc, r"d_{ij}=\sqrt{(x_i-x_j)^2+(y_i-y_j)^2}")
    eq(doc, r"H_{ij}=h_{ij}^{max}+50")
    paragraph(doc, "机型k在载荷q下的等效航程按空载与满载额定航程线性插值。该形式直接来自题设，并与配送无人机载荷相关能耗研究中“载荷增加导致单位航程能耗上升”的经验方向一致[1-3]。")
    eq(doc, r"R_k(q)=R_k^0-\frac{q}{Q_k}(R_k^0-R_k^F)")
    eq(doc, r"T_{ij}^k(q)=\frac{h_{ij}^{up}}{v_k^{up}}+\frac{d_{ij}}{v_k^{cr}}+\frac{h_{ij}^{down}}{v_k^{down}}")
    eq(doc, r"E_{ij}^k(q)=B_k\frac{d_{ij}}{R_k(q)}+\frac{m_k+q}{3600}\,g\,h_{ij}^{up}\eta_k")
    paragraph(doc, "式中第一项为按等效航程折算的水平能耗，第二项为爬升附加能耗；下降附加能耗按题设取0。对一条多点路线，载荷在每次交付后递减，因而每个航段都必须以当时剩余载荷重新计算。架次可行的能量条件为总能耗不超过扣除返航安全余量后的可用能量。")
    eq(doc, r"E_r=\sum_{(i,j)\in r}E_{ij}^{k}(q_{ij})\leq (1-\rho_k)B_k")
    h2(doc, "4.2  两阶段充电与资源占用")
    paragraph(doc, "任务结束后资源剩余SOC为1减去能耗占可用能量的比例。题设规定0%—90%区间占完全充电时间的65%，90%—100%区间占35%，且区间内线性。由此从任意剩余SOC充至100%的时间可写成分段函数。")
    eq(doc, r"SOC_r=1-\frac{E_r}{B_k}")
    eq(doc, r"T^{chg}(s)=\begin{cases}\frac{0.9-s}{0.9}0.65T^{full}+0.35T^{full},&s<0.9\\\frac{1-s}{0.1}0.35T^{full},&s\geq0.9\end{cases}")
    paragraph(doc, "同一资源的任务区间和随后充电区间合并为不可重叠占用区间。排程时采用最早可用规则：在满足机型、资源类型和任务先后关系的候选中，选择可使架次最早开始的实体机—能源资源组合。该规则可确定性复算，并能显式检查资源冲突。")
    h2(doc, "4.3  时刻、交接与完成时间口径")
    paragraph(doc, "架次开始时刻定义为固定准备开始，不是起飞时刻。运输机完成准备后起飞，抵达服务区后按箱逐一交接；货箱的完成时刻是自身交接结束，而不是航段到达时刻。若路线继续访问下一服务区，运输机从当前服务区离地30 m作业高度重新爬升。返航到O01才释放实体机，电池则在返航后进入充电。这个口径使硬时限判断、甘特图和资源释放时刻保持一致。")
    paragraph(doc, "问题二完成时间只看运输无人机最后返航。问题三联合完成时间要同时考虑运输机和中继机，故即使最后一个货箱早已交付，只要中继仍在返航，联合任务就尚未完成。问题四中各组复制完整依赖中继任务，因此组完成时间可能相同；这不是计算错误，而是冻结通信保障关系产生的结果。")
    h2(doc, "4.4  通信链路判定")
    paragraph(doc, "任意两个通信端点首先做DEM视距检查。自由空间传播损耗采用ITU-R P.525-5的标准形式[8]，频率以MHz、三维距离以km代入；若视线被地形遮挡，再叠加附件给定的遮挡损耗。由于控制下行与状态回传都必须可靠，允许损耗取两个方向预算中的较小者。")
    eq(doc, r"FSPL=32.44+20\log_{10}f+20\log_{10}d")
    eq(doc, r"L_{ab}^{path}=FSPL_{ab}+\beta_{ab}L^{block}")
    eq(doc, r"L_{ab}^{max}=\min(L_{a\rightarrow b}^{max},L_{b\rightarrow a}^{max})")
    eq(doc, r"M_{ab}^{link}=L_{ab}^{max}-L_{ab}^{path}")
    paragraph(doc, "当链路余量非负时对应双向链路可用。运输机与G01可用时优先记为直连；否则仅当运输机—中继和中继—G01在同一时刻都可用时记为中继；其余状态为中断。UAV辅助通信中的空中视距优势和轨迹—资源联合优化框架可见文献[6-7]，但本文的数值判据严格采用题设设备参数。")

    h1(doc, "5  问题一：单点往返能力与货箱组批")
    h2(doc, "5.1  最大安全载荷反演")
    paragraph(doc, "对每个机型—服务区组合，路线固定为O01—Si—O01。给定试探载荷q后，按公共物理模型分别计算去程和返程；返程载荷为0。可行性关于q单调，因此在0与额定载重之间二分搜索最大安全载荷。若能量约束在额定载重处仍有余量，则安全载荷取额定载重。")
    eq(doc, r"q_{ik}^{safe}=\max\{q:0\leq q\leq Q_k,\ E_{O_i}^{k}(q)+E_{iO}^{k}(0)\leq(1-\rho_k)B_k\}")
    paragraph(doc, "45个机型—服务区组合均得到确定的安全载荷。近距离节点主要受额定载重限制，远距离或高爬升节点首先触及能量边界。图1把服务区需求、空间距离和安全承载背景放在同一视图中，说明不能仅按需求质量选择机型。")
    figure(doc, 1, "raw_q1_distance_demand.png", "服务区距离、需求规模与单点运输难度", 14.5)
    h2(doc, "5.2  集合划分动态规划")
    paragraph(doc, "同一服务区的货箱数较少，可枚举其所有非空子集。若子集总质量、总体积和飞行能量同时可行，则它构成一个候选架次。对每个候选架次记录机型、时间与能耗，然后用位掩码动态规划覆盖全部货箱。为符合灾害场景中先保证出动规模、再控制能源与时长的原则，采用架次数、总能耗、累计作业时间的字典序目标。")
    eq(doc, r"J_1=(N_{trip},E_{sum},T_{sum})")
    eq(doc, r"F(S)=\min_{r\subseteq S}\{F(S-r)+c_r\}")
    paragraph(doc, "这里的最小值按字典序比较，第一维差异具有最高优先级；只有架次数相同时才比较能耗，前两项相同再比较作业时间。由于每个服务区独立且所有可行子集均被枚举，局部动态规划给出该目标下的精确最优组批。")
    per_service = defaultdict(lambda: [0, 0.0, 0.0])
    for row in q1_batches:
        z = per_service[row["service_id"]]
        z[0] += 1
        z[1] += float(row["energy_kwh"])
        z[2] += float(row["duration_s"])
    q1_rows = [["服务区", "架次数", "能耗/kWh", "累计时间/s"]]
    for sid in sorted(per_service):
        n, e, t = per_service[sid]
        q1_rows.append([sid, n, f"{e:.3f}", f"{t:.1f}"])
    paragraph(doc, "各服务区的架次数、能耗和累计时间汇总见表3。")
    table(doc, "表3  问题一各服务区组批结果", q1_rows, 8.5)
    h2(doc, "5.3  结果与解释")
    paragraph(doc, "最终18个架次唯一覆盖80个货箱，总运输能耗59.231986 kWh，累计飞行及作业时间32777.291307 s。所有架次的最小返航SOC为22.7893%，高于20%的基准安全余量。15个服务区中，需求较集中的节点由C型机承担，远端小批量节点更多使用A或B型机，以避免大机型空载返程造成的额外能耗。")
    paragraph(doc, "各架次质量与体积利用率如图2所示。组批优化不是简单把每架装满：体积、质量、安全能量三种约束在不同节点起主导作用，且字典序目标允许在不增加架次的前提下选择更节能的组合。结果中80箱计数守恒，未出现跨服务区组批或重复交付。")
    figure(doc, 2, "result_q1_batch_utilization.png", "问题一组批的质量与体积利用率", 14.5)
    h2(doc, "5.4  返航安全余量敏感性")
    paragraph(doc, "重新求解10%、15%、20%、25%和30%五个返航余量场景，而非只对基准结果做事后代入。图3显示余量不超过20%时组批方案保持18架次；提升至25%后增加为19架次，30%时为20架次。相应总能耗从59.231986 kWh增至61.181401和67.349440 kWh，表明20%附近存在明显的离散方案转折。")
    paragraph(doc, "五个安全余量场景的精确数值列于表4。")
    sens_rows = [["安全余量", "架次数", "总能耗/kWh", "累计时间/s", "最小返航SOC"]]
    for r in sens_q1:
        sens_rows.append([f"{100*float(r['reserve']):.0f}%", r["trip_count"], f"{float(r['energy_kwh']):.3f}", f"{float(r['duration_s']):.1f}", f"{100*float(r['min_return_soc']):.2f}%"])
    table(doc, "表4  返航安全余量敏感性结果", sens_rows, 8.5)
    figure(doc, 3, "process_q1_reserve_sensitivity.png", "返航安全余量对安全载荷与组批的影响", 14.5)
    h2(doc, "5.5  精确性、复杂度与指标权衡")
    paragraph(doc, "单服务区货箱数有限，枚举规模为2的货箱数次方减1。每个候选子集最多检查3种机型，并执行固定两航段仿真；动态规划状态数同样为2的货箱数次方。由于各服务区相互独立，可逐区求解，实际规模远小于把80箱整体枚举。所有可行子集和所有覆盖状态均被访问，因此在给定字典序目标和物理合同下，问题一结果具有精确最优性。")
    paragraph(doc, "18架次是最高优先级结果，但它不等于能耗最小的任意方案。若允许增加架次，小型机可能以更低单次空载能耗服务部分节点，但会增加准备、交接和累计时间；若只追求最少时间，也可能选择更多并行架次。题目在问题一忽略实体并发，累计作业时间反映总任务量而不是墙钟完成时间，因此本文把它置于能耗之后。该解释避免把三个口径不同的指标简单相加。")
    paragraph(doc, "安全余量实验还说明最大安全载荷和最优组批并非连续变化。余量小幅增加时，部分机型的安全载荷下降但尚未跨过货箱组合质量阈值，架次数保持不变；一旦关键组合不可行，动态规划必须拆分货箱，架次数和能耗发生跳变。因此实际准备中应针对离散阈值预留备用架次，而不能只按能耗百分比线性放大。")

    h1(doc, "6  问题二：异构多点多架次运输调度")
    h2(doc, "6.1  集成目标与约束")
    paragraph(doc, "问题二在问题一飞行合同基础上允许多点访问。对医疗箱和首批保障箱构造有效硬截止：若两类约束同时适用则取较早者；其他货箱的期望时刻只用于软迟到。为防止能耗或架次的小改进牺牲救命物资时效，优化采用分层目标：先最小化硬时限违约数，再最小化加权相对延误，其后比较完成时间、总能耗和架次数。")
    eq(doc, r"d_b^{hard}=\min(d_b^{medical},d_b^{first})")
    eq(doc, r"WTD=\sum_b\alpha_b\frac{\max(0,C_b-d_b^{exp})}{d_b^{exp}}")
    eq(doc, r"J_2=(N_{late},WTD,C_{max},E_{sum},N_{trip})")
    paragraph(doc, "每条路线需同时满足货箱唯一覆盖、载重、体积、逐段能源和返航余量。逐箱完成时刻等于抵达服务区后的累计交接完成时刻，不能用无人机到达时刻替代。实体机和共享电池的开始时刻取两类资源都可用后的最早时刻，并加入固定准备时间；任务结束后能源资源按两阶段模型充电。")
    eq(doc, r"C_b=s_r+T_r^{prep}+T_r^{fly}(b)+T_r^{service}(b)")
    eq(doc, r"s_r\geq\max(A_{u(r)},A_{p(r)})")
    h2(doc, "6.2  求解算法")
    paragraph(doc, "算法先按硬截止、期望时刻、应急优先系数和空间邻近性形成种子任务，再用可行插入生成单点与多点路线。每次插入都重新仿真剩余载荷、DEM航段、逐箱完成时刻和能耗，而非使用静态距离近似。随后采用确定性大邻域改进：从高迟到或低利用率路线移除一组货箱，尝试跨路线重插、路线合并、访问次序交换和机型替换，只接受使分层目标改善的候选。该设计借鉴ALNS的破坏—修复框架[4-5]，但算子针对题目的不可拆货箱、硬时限和共享电池进行了重构。")
    paragraph(doc, "当路线集合冻结后，按优先级和最早可执行时刻逐架次分配实体机与电池；若资源冲突导致开始时刻变化，则重新计算全部交付完成时刻与目标。最终再进行货箱守恒、硬时限、能量、无人机重叠、电池占用及充电重叠六类检查。图4展示需求优先级和时限结构，说明医疗及首批箱集中在早期窗口，后续普通物资主要承担软迟到代价。")
    figure(doc, 4, "raw_q2_deadline_priority.png", "货箱时限、类别与应急优先级结构", 14.5)
    h2(doc, "6.3  调度结果")
    per_unit = defaultdict(lambda: [0, 0.0, 0.0])
    for row in q2_trips:
        z = per_unit[row["unit_id"]]
        z[0] += 1
        z[1] = max(z[1], float(row["return_s"]))
        z[2] += float(row["duration_s"])
    paragraph(doc, "8架实体运输无人机的任务负荷和最后返航时刻见表5。")
    unit_rows = [["实体机", "机型", "架次数", "最后返航/s", "累计任务时间/s"]]
    type_by_unit = {r["unit_id"]: r["type_id"] for r in q2_trips}
    for uid in sorted(per_unit):
        n, last, dur = per_unit[uid]
        unit_rows.append([uid, type_by_unit[uid], n, f"{last:.1f}", f"{dur:.1f}"])
    table(doc, "表5  问题二实体运输无人机使用情况", unit_rows, 8.5)
    paragraph(doc, "求得26个运输架次，其中5个为多服务区路线。31个受硬时限约束的货箱全部按时，最小硬时限松弛为2375.085931 s；全部80箱唯一交付。最后一架运输机于12695.763194 s返航，总运输能耗83.001330 kWh，加权相对延误111.450075。与问题一相比，允许跨服务区访问减少了部分重复返航，但资源并发、优先投送和充电等待使总架次数不再是唯一目标。")
    paragraph(doc, "8架实体机的并行工作甘特图如图5所示，任务间的空隙来自机体可用时刻、电池充电和优先任务次序，而不是漏排。所有实体机占用区间与所有电池“任务+充电”区间分别无重叠。逐箱送达时刻及硬、软时限见图6，硬时限点全部位于截止线之前；普通物资允许以WTD度量渐进惩罚，从而避免为少量软迟到破坏整体完成时间。")
    figure(doc, 5, "process_q2_uav_gantt.png", "问题二实体无人机多架次调度甘特图", 14.5)
    figure(doc, 6, "result_q2_delivery_deadlines.png", "问题二逐箱送达时刻与时限检验", 14.5)
    h2(doc, "6.4  地面延迟稳健性")
    paragraph(doc, "在不改变路线与资源次序的条件下，对所有早期任务叠加0—1200 s统一地面延迟并重新计算硬时限。结果显示硬时限违约数始终为0，最小松弛由2375.085931 s线性下降到1175.085931 s。这说明基准方案为准备、装卸或短时天气等待保留了约19.6 min的保守缓冲；超过该范围时应重新优化而不能继续平移。")
    paragraph(doc, "统一地面延迟的代表性复算结果见表6。")
    table(doc, "表6  统一地面延迟的代表性敏感性结果", [["延迟/s", "硬时限违约数", "最小松弛/s"]] + [[r["ground_delay_s"], r["hard_late_count"], f"{float(r['min_hard_slack_s']):.1f}"] for r in sens_q2[::5]], 9)
    h2(doc, "6.5  路线改进机制与停止准则")
    paragraph(doc, "初始路线强调硬时限可行，但通常存在装载率低或返航重复。改进阶段按四类算子循环：单箱移位把货箱插入另一条路线；同服务区批量移位减少交接碎片；路线合并尝试构造多点架次；机型替换在载重和能源允许时改用更合适的机型。每个候选都从头仿真DEM航段、交接时刻和资源排程，不能沿用旧路线的增量能耗近似。")
    paragraph(doc, "接受准则严格遵循目标元组，只有在所有更高优先级分量不变且当前分量改善时才更新。连续若干轮没有改善，或所有可行移除—插入组合已检查后停止。随机化只用于同值候选的遍历顺序，固定种子保证相同输入得到相同输出。由于没有穷举全部多点路线，该停止准则只说明启发式达到局部稳定，不构成全局最优证据。")
    paragraph(doc, "资源排程不是路线求解后的装饰步骤。某条路线即使几何和能源可行，若唯一适用机型或电池正在执行其他紧急任务，其真实起飞时刻会推迟并改变时限。本文在每轮路线评价中重新排程资源，使目标函数看到等待代价。最终26架次的硬时限全部满足，说明路线与资源两层在同一时刻口径下闭合。")
    paragraph(doc, "统一地面延迟实验相当于对准备、装卸、临时空域协调等共同扰动做压力测试。最小松弛随延迟一比一下降，说明最紧货箱位于同一早期关键链；零违约区间给出了不改变路线时的操作缓冲。若观测延迟接近1175 s，继续执行基准表将失去余度，应触发滚动重排并优先保留医疗和首批箱。")

    h1(doc, "7  问题三：运输—中继联合调度")
    h2(doc, "7.1  运输波次与候选悬停点")
    paragraph(doc, "问题三继承问题二的26条运输路线、货箱组批和访问次序。为给中继准备与建链留出时间，将运输架次按资源可行性和通信需求组织为8个波次，并允许每个波次整体平移。运输路线本身不改变，因此运输能耗仍为83.001330 kWh；但为了等待中继到位，运输完成时间由12695.763194 s延长到23918.718636 s。")
    paragraph(doc, "候选悬停点位于DEM覆盖范围内，悬停离地高度不超过附件上限。先用轨迹关键点和较粗时间样本预筛能覆盖多个非直连区间的位置，再对候选对做波次级组合评估。该步骤只缩小搜索空间；每个选中悬停点的最终合法性、中继往返地形净空、能源和完整轨迹通信均在主程序中重新计算。图7展示各运输波次对中继服务时长的需求差异。")
    figure(doc, 7, "raw_q3_relay_phase_duration.png", "各波次直连与中继需求时长", 14.5)
    h2(doc, "7.2  中继任务时间与能量合同")
    paragraph(doc, "中继架次由固定准备、飞往悬停点、建链、服务、返航和周转组成。为保证运输机起飞时链路已经建立，中继建链完成时刻不得晚于所覆盖运输区间的开始。服务结束取该任务覆盖的最后通信区间结束，返航后才释放中继机；能源组件按实际能耗计算SOC并进入两阶段充电。")
    eq(doc, r"t_h^{ready}=s_h+T_h^{prep}+T_h^{out}+T_h^{link}")
    eq(doc, r"t_h^{ready}\leq\min_{r\in R_h}t_r^{need}")
    eq(doc, r"E_h=P_h^{cr}T_h^{cr}+E_h^{up}+(P_h^{hover}+P_h^{com})T_h^{service}")
    paragraph(doc, "对每个波次构造“候选悬停点—需保障时间区间”的集合覆盖关系，再联合选择最少可行中继任务并排入2架中继无人机和6套能源组件。调度比较顺序为硬时限违约、通信中断、联合完成时间、总能耗及架次数；任何存在通信中断或资源重叠的候选均被淘汰。")
    h2(doc, "7.3  连续通信证书")
    paragraph(doc, "对每个运输架次，把起飞至返航轨迹分成几何运动规律不变的基本区间。在区间端点和内部控制点计算直连及可用中继的链路余量，并结合端点位置变化率构造保守下界。如果该下界非负，则整个区间被认证；否则继续二分。到达最小时间尺度仍无法认证的区间记为未解析，任一点两类路径均不可用则记为中断。")
    eq(doc, r"M^{service}(t)=\max(M_{TG}(t),\max_h\min(M_{TR_h}(t),M_{R_hG}(t)))")
    eq(doc, r"M_I^{L}=M_I^{sample}-K_I\Delta t_I")
    paragraph(doc, "基准方案对26个运输架次全部完成连续区间认证，未解析区间数和中断区间数均为0；另以0.5 s步长检查77178个采样点，中断数同样为0。连续证书的最小保守余量为0.130757 dB，网格检查用于发现实现错误，证书下界用于排除采样间隙失联。")
    h2(doc, "7.4  联合调度结果")
    paragraph(doc, "13个中继架次的波次、执行资源和起止时刻列于表7。")
    relay_rows = [["任务", "波次", "悬停点", "中继机", "能源组件", "开始/s", "结束返航/s"]]
    for r in q3_relays:
        relay_rows.append([r["mission_id"], r["wave"], r["point_name"], r["relay_unit_id"], r["energy_pack_id"], f"{float(r['start_s']):.1f}", f"{float(r['return_s']):.1f}"])
    table(doc, "表7  中继任务调度方案", relay_rows, 7.5)
    paragraph(doc, "8个运输波次中7个需要中继，共安排13个中继架次；实际使用2架中继无人机和5套能源组件，第6套保持备用。89个连续通信区段由直连与中继状态拼接形成，状态切换点与实际几何、遮挡或中继服务边界一致。最后运输机于23918.718636 s返航，最后中继机于24472.376375 s返航，因此按题意联合完成时间取24472.376375 s，而不能使用运输完成时间代替。")
    eq(doc, r"C_{max}^{joint}=\max(C_{max}^{transport},C_{max}^{relay})")
    paragraph(doc, "中继能耗为12.718432 kWh，与运输能耗合计95.719762 kWh。图8表明两架中继机交替承担各波次任务，任务间隔与能源组件轮换相匹配；没有中继机或组件占用重叠，且所有建链完成时刻早于对应运输需求。图9将89个通信区段沿完整时轴展开，未出现中断颜色带。")
    figure(doc, 8, "process_q3_relay_gantt.png", "问题三中继无人机与能源组件调度", 14.5)
    figure(doc, 9, "result_q3_communication_timeline.png", "运输架次连续通信保障时序", 14.5)
    h2(doc, "7.5  链路裕量敏感性")
    paragraph(doc, "为评估参数误差和额外安全要求，在所有链路预算上增加统一附加裕量并重新检查连续证书。增加0.1 dB时26个架次仍全部认证，最差调整后余量为0.030757 dB；增加0.2 dB后只有19个架次保持认证，7个架次失去证书。因此基准方案满足题设参数，但链路鲁棒性边界较窄，实际部署宜通过提高中继高度、增加候选点或提升设备预算留出至少0.2 dB以上工程余量。")
    paragraph(doc, "附加链路裕量逐级增加后的认证结果见表8。")
    table(doc, "表8  附加链路裕量敏感性", [["附加裕量/dB", "已认证架次", "未认证架次", "最差调整余量/dB"]] + [[r["extra_margin_db"], r["certified_trip_count"], r["uncertified_trip_count"], f"{float(r['worst_adjusted_margin_db']):.3f}"] for r in sens_q3], 8.5)
    h2(doc, "7.6  联合调度权衡与可实施性")
    paragraph(doc, "通信约束没有改变26条运输路线的能耗，却显著延长完成时间，这是因为部分波次必须等待中继准备、飞抵和建链。若强行维持问题二的早起飞时刻，需要更多中继机并行覆盖或更靠近任务区的预置点；在现有2架中继机条件下，波次整体平移是保证零中断的必要代价。该结果把装备数量与时效之间的权衡显式化。")
    paragraph(doc, "13个中继架次并不等于13套能源组件。组件在任务后可充电复用，时间轴计算表明5套即可完成全部任务，第6套可作为故障或性能衰减备用。相反，中继机机体本身同时受到飞行、悬停、返航和周转约束，两个重叠悬停点必须由两架机承担。资源需求应由最大区间重叠决定，不能用任务数直接相加。")
    paragraph(doc, "连续证书在链路状态切换附近自动细分，能集中计算于最危险的遮挡边界；长时间高余量区间不必使用同样细的网格。保守下界会牺牲少量可行域，优点是已认证区间具有明确含义。0.5 s网格在所有区间上独立采样，若网格与证书结论不一致，则说明下界实现或事件分割存在问题；本方案两者一致且均为零中断。")
    paragraph(doc, "最小保守余量只有0.130757 dB，意味着题设参数下可行但工程余度有限。实际飞行前应做三项更新：用现场测量修正遮挡附加损耗；把中继悬停位置误差和海拔误差换算为额外路径损耗；根据降雨与设备状态增加预算裕量。若更新后证书失败，可优先提高合法悬停高度或增加靠近薄弱航段的候选点，而不是盲目延长服务时间。")

    h1(doc, "8  问题四：任务分区与资源配置")
    h2(doc, "8.1  原子任务块与分区模型")
    paragraph(doc, "以服务区为顶点，若问题三同一运输架次连续访问两个服务区，则在两点间连边。连通分量内任意节点通过共访关系相连，按题意必须划入同一组，因此压缩为不可拆原子任务块。冻结方案共得到10个原子块，图10给出每个块包含的服务区及其工作量。这一步将15点任意分区转化为10个块的集合分区。")
    figure(doc, 10, "raw_q4_atomic_components.png", "共访图形成的10个原子任务块", 14.5)
    paragraph(doc, "对K=2，固定第一个原子块属于第1组以消除组标签对称，共枚举511个无重复分区。对K=3，固定第一个原子块后枚举18660个带标签方案，其中第2、3组交换产生2倍对称，对应9330个无标签划分。该重复只影响计数，不影响最优划分覆盖。")
    paragraph(doc, "每组独立执行时，从问题三时间轴筛出本组运输任务，并复制其依赖的完整中继任务。某类资源需求等于相应占用区间图的最大重叠数；能源资源还包含充电区间。库存缺口按各组需求之和与全局库存比较，冗余则与集中执行需求比较。")
    eq(doc, r"D_a^{(K)}=\max(0,\sum_{k=1}^{K}n_{ka}-I_a)")
    eq(doc, r"R_a^{(K)}=\sum_{k=1}^{K}n_{ka}-n_a^{central}")
    eq(doc, r"CV_W=\frac{\sqrt{\frac{1}{K}\sum_k(W_k-\overline W)^2}}{\overline W}")
    h2(doc, "8.2  两组与三组最优方案")
    paragraph(doc, "两种组数下的具体服务区划分和独立配置见表9。")
    group_rows = [["K", "组", "服务区", "A/B/C机", "A/B/C电池", "中继机/组件", "工作量/h"]]
    for r in q4_groups:
        group_rows.append([
            r["K"], r["group"], r["services"],
            f"{r['A_uav']}/{r['B_uav']}/{r['C_uav']}",
            f"{r['A_battery']}/{r['B_battery']}/{r['C_battery']}",
            f"{r['relay_uav']}/{r['relay_pack']}", f"{float(r['workload_h']):.2f}",
        ])
    table(doc, "表9  两组与三组任务分区及独立配置", group_rows, 7.2)
    paragraph(doc, "两组方案把S010、S014组成小组，其余13个服务区组成大组；组工作量分别为25.7325 h与5.1437 h。运输机和运输电池总需求均不超过库存，但两个组都要独立保持2架中继机，合计需要4架，相对库存2架缺2架；中继能源组件合计6套，恰好等于库存。所有组完成时刻均保留为24472.376375 s，是因为冻结并复制所依赖的完整跨组中继任务。")
    paragraph(doc, "三组方案将S013进一步独立为第3组，其工作量4.4899 h；主组工作量24.8536 h，另一个小组仍为5.1437 h。三个组各需2架中继机，合计6架，缺口4架；能源组件合计8套，缺口2套；A型电池产生1组额外冗余但总量未超库存。图11比较集中、两组和三组的资源需求，说明组数增加主要放大通信资源，而不是运输机规模。")
    figure(doc, 11, "process_q4_resource_tradeoff.png", "不同分区方式的资源需求、冗余与缺口", 14.5)
    shortages = [["K", "资源", "总需求", "库存", "缺口", "集中需求", "冗余"]]
    for r in q4_resources:
        if int(r["shortfall"]) > 0 or int(r["partition_redundancy"]) > 0:
            shortages.append([r["K"], r["resource"], r["total_group_need"], r["inventory"], r["shortfall"], r["central_need"], r["partition_redundancy"]])
    paragraph(doc, "仅列出出现缺口或冗余的资源后，比较结果汇总于表10。")
    table(doc, "表10  分区造成的关键资源缺口与冗余", shortages, 8.5)
    h2(doc, "8.3  方案比较与推荐")
    paragraph(doc, "在“满足库存—减少缺口—改善工作量均衡—减少冗余”的比较顺序下，两组方案优于三组方案。两组虽存在2架中继机缺口和明显工作量不均衡，但运输与能源组件均可由现有库存覆盖；三组同时扩大中继机和能源组件缺口，且新增独立小组并未缩短完成时间。若只能使用现有2架中继机，则分组不能真正并行独立执行，必须错峰共享，这与题设“资源不得跨组调配”冲突，因此需要增配资源或采用两组顺序执行的替代组织方式。")
    paragraph(doc, "推荐分区的空间映射见图12。S010与S014被同一多点架次联系，必须同组；主组包含其余被共访关系连接或为均衡资源而合并的任务块。空间邻近不是唯一标准，决定分区的是冻结路线与通信任务的耦合关系。")
    figure(doc, 12, "result_q4_partition_map.png", "K=2与K=3任务分区空间方案", 14.5)
    h2(doc, "8.4  穷举目标与资源重复的来源")
    paragraph(doc, "每个候选分区先检查非空和原子块完整性，再从冻结任务表筛选组内运输架次。若一个中继任务保障任意组内运输区间，则该组必须配置该中继任务的完整出航、服务和返航；因此同一原中继任务可能被多个独立组复制。复制后分别计算机体与能源组件的最大重叠，不允许用另一组的空闲资源补位。")
    paragraph(doc, "分区评价首先最小化各类资源总缺口，尤其把中继机和能源组件缺口作为不可忽略的可实施性指标；缺口相同时再比较相对集中执行的冗余总量和工作量变异系数。工作量以运输与中继资源占用机时合计，能反映长航段和长悬停，而服务区数量只能粗略反映任务规模。")
    paragraph(doc, "K=3虽然把S013单独成组，却没有降低其他小组对中继机的峰值需求。每组独立执行都要承受其自身的通信峰值，于是中继机需求从集中执行2架放大到6架。该现象说明通信设施具有显著共享经济：集中或少分组有利于复用同一波次中继，过度分区会把短时峰值复制到每个执行单元。")
    paragraph(doc, "若管理目标更重视地理自治，可保留三组划分，但必须预置4架额外中继机和2套能源组件，或允许不同组错峰启动。后一方案会改变完成时间且实质上重新引入跨组协调，不满足题目定义的完全独立并行。因此在现有库存和冻结方案下，两组是更稳妥的组织选择。")

    h1(doc, "9  模型检验、误差分析与评价")
    h2(doc, "9.1  守恒与资源可行性检验")
    paragraph(doc, "对问题一至问题三分别以货箱编号集合检查唯一覆盖，交付记录均为80条且与原始货箱集合完全一致。问题二和问题三逐一检查运输机、电池、中继机、能源组件的占用区间，无重叠；同一波次中继任务使用的能源组件也互异。所有运输架次满足质量、体积、逐段等效航程和返航余量，所有中继架次满足离地高度、往返净空和能源约束。")
    paragraph(doc, "数值复算对时间、能耗和SOC采用双精度浮点数。问题一能耗的最大独立复算误差为4.55×10^-13 kWh，远低于结果保留精度。JSON和CSV结果中未出现NaN或无穷值。通信方面同时采用连续区间证书和0.5 s稠密网格，两者均给出零中断，降低了单一验证方式漏检的风险。")
    h2(doc, "9.2  敏感性与误差边界")
    paragraph(doc, "三组敏感性实验分别针对能源、调度和通信的主要不确定源。返航余量从20%提高到25%时，离散组批发生跳变，说明能源参数误差可能转化为额外架次；地面延迟1200 s内硬时限仍可行，说明早期任务具有较充足时间缓冲；链路预算仅增加0.2 dB就有7个架次失去连续证书，说明通信是基准方案中最敏感的环节。实际部署应优先实测天线增益、遮挡附加损耗和中继位置误差。")
    paragraph(doc, "DEM为30 m栅格，地形视距和最高高程存在空间离散误差。本文按穿越像元取最大高程并叠加50 m净空，使飞行高度估计偏保守；通信视距仍可能受到栅格未表达的建筑、植被和临时障碍影响。链路敏感性结果表明，应把0.130757 dB视为题设数字场景下的数学余量，而非可直接替代工程安全裕量。")
    h2(doc, "9.3  模型优点")
    paragraph(doc, "第一，四问共用同一飞行、能源、充电、时刻与编号口径，避免局部最优结果无法继承。第二，问题一用全子集枚举和动态规划给出局部精确解，问题四在原子块压缩后完成穷举，能明确最优性边界。第三，问题二把逐箱交接和资源时间轴纳入调度，输出可以直接映射到实体机和电池。第四，问题三不依赖单一时间采样，而以连续区间下界证明通信覆盖，并用网格检查交叉验证。第五，所有图表和提交表均由同一冻结结果自动生成，降低手工转录误差。")
    h2(doc, "9.4  局限与改进")
    paragraph(doc, "问题二和问题三采用针对性启发式，得到的是经过可行性证明的高质量方案，不能据此宣称全局最优。中继悬停点来自有限候选预筛，虽然最终轨迹证书完整，但更优的连续空间位置仍可能存在。后续可用列生成或分支定价联合生成多点路线，用贝叶斯优化或自适应网格细化搜索悬停位置，并将链路裕量直接加入鲁棒优化目标。")
    paragraph(doc, "模型未显式考虑动态风场、降雨衰减、临时禁飞区、维修故障和需求滚动更新。若获得实时气象与遥测，可把航速、能耗和链路损耗改为情景变量，采用滚动时域重优化；若任务需要概率可靠性，可用分布鲁棒机会约束替代确定性安全余量。分区模型目前按冻结方案核算，若允许分组后重新设计路线，资源缺口可能下降，但将不再回答题目规定的冻结比较。")
    h2(doc, "9.5  可重复计算与结果追踪")
    paragraph(doc, "计算链把输入、关键参数、随机种子、路线表、交付表、通信区段和分区表分别保存为结构化文件。论文中的每个核心数字都可由对应表直接求和、取最大或计数得到：总能耗为架次能耗求和，完成时间为返航时刻最大值，硬违约数由完成时刻与有效截止比较，中断数由通信区段状态计数，资源需求由占用区间最大重叠计算。")
    paragraph(doc, "程序对输入文件和输出文件计算哈希，以防附件或结果在排版过程中被无意替换。所有图均从结构化结果重新绘制，提交工作簿也从同一结果生成；论文生成只读取冻结文件，不重新运行随机搜索。这样，模型求解、结果表、图和正文之间形成单向数据流，任何数值变化都需要先回到计算层更新。")
    paragraph(doc, "数值精度方面，内部统一保留双精度；论文对时间通常保留6位小数用于关键总量、图表按可读性缩减小数，资源数量保持整数。不同显示精度不改变时限判断和资源重叠。经复算，货箱集合、区间重叠、能源边界和分区并集均满足逻辑约束，说明导出过程没有改变模型结果。")
    h2(doc, "9.6  应急实施建议")
    paragraph(doc, "执行前应把运输和通信任务分别制作成可操作清单。运输清单按波次列出实体机、机型、电池、货箱、路线、准备开始、起飞、逐箱交接与返航时刻；通信清单列出中继机、能源组件、悬停点经纬度、飞行海拔、最迟建链时刻、服务结束和返航时刻。现场指挥以波次为同步单元，只有运输资源与所需中继均报告就绪后才放行。")
    paragraph(doc, "运行中设置三类触发器：若准备或装卸延迟逼近最小硬时限松弛，则优先重排医疗与首批箱；若实测链路余量低于计划值0.1 dB以上，则暂停尚未起飞的薄弱架次并调整中继；若电池或能源组件实测SOC低于计划值，则按安全余量重新核算，而不能用后续充电预期替代当前可用能量。触发器直接对应敏感性实验揭示的临界因素。")
    paragraph(doc, "两组分区投入实施时，应先解决中继机缺口。新增设备到位前，可将两个任务组视为管理分区而非完全独立的并行分区，由统一通信单元按波次服务；但此时必须明确偏离题设独立资源条件，不能沿用表9的并行完成时间。若能够增配2架同参数中继机，则按冻结任务复制配置即可，无需改变运输路线。")
    paragraph(doc, "模型输出适合作为灾后早期确定性计划，现场仍需持续校准。建议每完成一个波次就回收实际起降、能耗、SOC与链路日志，更新后续架次的可用时刻和安全裕量；当偏差尚未触及触发器时保持原计划，以减少频繁调整，触及阈值后再滚动求解。这样既利用离线模型的整体协调能力，也保留应对天气、设备和需求变化的实时弹性。")
    paragraph(doc, "此外，应保留每次计划更新前后的任务版本和实际执行记录，使指挥人员能够追溯路线变更、资源替换与时限风险的来源，并为灾后复盘、参数标定和装备配置改进提供可信数据基础。")

    h1(doc, "10  结论")
    paragraph(doc, "（1）单点直接往返条件下，通过安全载荷反演和集合划分动态规划，80个货箱可由18个架次完成，总能耗59.231986 kWh、累计作业时间32777.291307 s，最小返航SOC为22.7893%。基准20%返航余量处于稳定区间上沿，提高至25%会增加1个架次。")
    paragraph(doc, "（2）异构多点调度方案含26个架次和5个多站架次，31个硬时限箱全部按时，最小硬时限松弛2375.085931 s；最后运输机于12695.763194 s返航，总能耗83.001330 kWh。8架实体机及共享电池时间轴均无冲突，统一地面延迟1200 s时仍保持零硬违约。")
    paragraph(doc, "（3）加入通信后，26个运输架次分8个波次，其中7个波次由13个中继架次保障，实际使用2架中继机和5套能源组件。连续证书及77178个0.5 s网格点均无中断，最小保守余量0.130757 dB；联合完成时间为24472.376375 s，总能耗95.719762 kWh。通信裕量是最敏感因素，应在工程实施中优先加固。")
    paragraph(doc, "（4）冻结联合方案形成10个不可拆原子块。K=2最优方案需要的运输资源均不超库存，只缺2架中继机；K=3方案缺4架中继机和2套能源组件，且工作量均衡性没有得到足以抵消缺口的改善。因此推荐两组方案，并优先增配2架中继机；若不能增配，应放弃各组完全独立并行执行的组织要求。")

    h1(doc, "参考文献")
    refs = [
        "[1] Dorling K, Heinrichs J, Messier G G, et al. Vehicle Routing Problems for Drone Delivery. IEEE Transactions on Systems, Man, and Cybernetics: Systems, 47(1): 70-85, 2017. DOI: 10.1109/TSMC.2016.2582745.",
        "[2] Zhang J, Campbell J F, Sweeney D C II, et al. Energy Consumption Models for Delivery Drones: A Comparison and Assessment. Transportation Research Part D: Transport and Environment, 90: 102668, 2021. DOI: 10.1016/j.trd.2020.102668.",
        "[3] Cheng C, Adulyasak Y, Rousseau L-M. Drone Routing with Energy Function: Formulation and Exact Algorithm. Transportation Research Part B: Methodological, 139: 364-387, 2020. DOI: 10.1016/j.trb.2020.06.011.",
        "[4] Ropke S, Pisinger D. An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows. Transportation Science, 40(4): 455-472, 2006. DOI: 10.1287/trsc.1050.0135.",
        "[5] Hemmelmayr V C, Cordeau J-F, Crainic T G. An Adaptive Large Neighborhood Search Heuristic for Two-Echelon Vehicle Routing Problems Arising in City Logistics. Computers & Operations Research, 39(12): 3215-3228, 2012. DOI: 10.1016/j.cor.2012.04.007.",
        "[6] Zeng Y, Zhang R, Lim T J. Wireless Communications with Unmanned Aerial Vehicles: Opportunities and Challenges. IEEE Communications Magazine, 54(5): 36-42, 2016. DOI: 10.1109/MCOM.2016.7470933.",
        "[7] Tran-Dinh H, Nguyen V-D, Gautam S, et al. UAV Relay-Assisted Emergency Communications in IoT Networks: Resource Allocation and Trajectory Optimization. IEEE Transactions on Wireless Communications, 21(3): 1621-1637, 2022. DOI: 10.1109/TWC.2021.3105821.",
        "[8] International Telecommunication Union. Recommendation ITU-R P.525-5: Calculation of Free-Space Attenuation. https://www.itu.int/rec/R-REC-P.525-5-202411-I/en, 访问时间：2026年9月24日.",
        "[9] Copernicus Data Space Ecosystem. Copernicus DEM—Global and European Digital Elevation Model. https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM, 访问时间：2026年9月24日. DOI: 10.5270/ESA-c5d3d65.",
        "[10] OpenAI. Introducing GPT-5. https://openai.com/index/introducing-gpt-5/, 访问时间：2026年9月24日.",
    ]
    for ref in refs:
        paragraph(doc, ref, first=False)

    h1(doc, "附录A  结果文件与算法说明")
    paragraph(doc, "论文配套结果文件按题目模板给出问题一组批、问题二运输架次与逐箱送达、问题三中继架次与通信区段、问题四分区资源等工作表。核心求解流程为：读取并校验附件；预计算DEM航段；求解问题一安全载荷和局部集合划分；生成并改进问题二路线；排程实体机与电池；对问题三波次搜索中继组合并生成连续通信证书；压缩共访图后穷举问题四分区；最后统一导出表格和图。")
    paragraph(doc, "为保证可复算，程序固定随机种子20260923，并对输入数据记录SHA-256。全部关键数值直接来自实际运行的结构化结果，不在论文生成阶段重新估计。运输、能源和通信可行性检查与结果导出共用同一函数，避免“求解口径”和“论文口径”分离。")
    paragraph(doc, "问题一算法逐服务区枚举货箱子集，先用质量与体积快速剪枝，再调用航段仿真检查能源；动态规划从空集合向全集扩展并记录前驱。问题二算法以硬时限箱为种子构造路线，插入普通箱后执行移位、合并、换序和机型替换，随后按最早可用原则分配实体机与电池。")
    paragraph(doc, "问题三先从问题二运输任务构造波次，对每个波次计算非直连区间，再从预筛悬停点中选择能够覆盖这些区间的组合；候选组合经中继飞行与能源仿真、资源排程和连续证书验证后才能接受。问题四建立服务区共访图，求连通分量并压缩为原子块，再枚举块分配、筛选冻结任务并计算独立资源峰值。")
    paragraph(doc, "程序最终执行四类自动检查：数据检查验证字段、单位和编号；物理检查验证载荷、体积、能量和高度；调度检查验证时限和资源区间；通信检查验证直连或合法单中继连续覆盖。任一检查失败时不导出正式结果。该机制使附录算法描述、正文结论和提交表具有相同判定基础。")

    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(3.0)
        section.bottom_margin = Cm(1.75)
        section.left_margin = Cm(2.25)
        section.right_margin = Cm(2.25)
        section.header_distance = Cm(0.5)
        section.footer_distance = Cm(0.8)
    clear_element(doc.sections[0].footer._element)
    clear_element(doc.sections[0].header._element)

    # The official template contains an obsolete external image relationship to
    # its author's local Downloads directory.  Cleared template content no
    # longer uses it, so remove the dangling relationship before publication.
    for rel_id, rel in list(doc.part.rels.items()):
        if rel.is_external and rel.reltype.endswith("/image"):
            del doc.part.rels[rel_id]

    if OUTPUT.exists():
        OUTPUT.unlink()
    pf.save_document(doc, ROOT, filename=OUTPUT.name, contest="cumcm", overwrite=False)
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUTPUT, CHECKPOINT)
    report = {
        "stage": 2,
        "status": "V1_CREATED",
        "source": str(Path(__file__).name),
        "template": str(TEMPLATE.relative_to(ROOT)),
        "template_sha256": sha256(TEMPLATE),
        "output": str(OUTPUT.relative_to(ROOT)),
        "output_sha256": sha256(OUTPUT),
        "checkpoint": str(CHECKPOINT.relative_to(ROOT)),
        "checkpoint_sha256": sha256(CHECKPOINT),
        "figures": 12,
        "tables": 10,
        "references": 10,
        "note": "Stage-2 complete draft; page-by-page render QA is reserved for stage 3.",
    }
    (ROOT / "checkpoints" / "阶段二-V1清单.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
