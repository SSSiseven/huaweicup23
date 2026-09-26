"""Regenerate paper input figures from supplied workbooks, never solver results."""
from pathlib import Path
import sys
import json
from dataclasses import asdict
import shutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import solve_d
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent
ASSETS = OUT / 'assets'
ASSETS.mkdir(exist_ok=True)
data = solve_d.load_inputs(ROOT)
boxes = data['boxes']
nodes = data['nodes']
ids = sorted(k for k in nodes if k.startswith('S'))
hard_deadlines = boxes.apply(solve_d.box_deadline, axis=1)
hard = hard_deadlines.notna()
medical = boxes['物资类型'].eq('医疗物资')
first = boxes['是否首批保障'].eq('是')
assert len(boxes) == boxes['货箱编号'].nunique() == 80
assert set(boxes['服务区编号']) == set(ids)
assert boxes.iloc[0]['货箱编号'] == 'S001-MED-01'
assert boxes.iloc[-1]['货箱编号'] == 'S015-FOD-01'
grouped = boxes.assign(hard=hard).groupby('服务区编号').agg(
    boxes=('货箱编号','size'), mass=('单箱质量（kg）','sum'),
    volume=('单箱体积（m³）','sum'), hard=('hard','sum'))
grouped.to_csv(OUT / 'input_summary.csv', encoding='utf-8-sig')
stats = {
    'box_count': len(boxes), 'mass_kg': float(boxes['单箱质量（kg）'].sum()),
    'volume_m3': float(boxes['单箱体积（m³）'].sum()),
    'hard_count': int(hard.sum()), 'soft_count': int((~hard).sum()),
    'medical_count': int(medical.sum()), 'first_count': int(first.sum()),
    'overlap_count': int((medical & first).sum()),
    'thresholds_db': data['thresholds'],
    'transport_types': {k: asdict(v) for k,v in data['transport_types'].items()},
    'inventory': data['battery_inventory'], 'relay': asdict(data['relay_type']),
    'input_hashes': data['input_hashes'],
}
(OUT / 'input_facts.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
plt.rcParams.update({'font.family':'SimSun', 'font.size':11, 'axes.unicode_minus':False,
    'pdf.fonttype':42, 'svg.fonttype':'none', 'axes.spines.top':False,
    'axes.spines.right':False, 'savefig.dpi':300})
blue, orange, green = '#2878A5', '#D88435', '#43876B'

def save(fig, name):
    fig.savefig(ASSETS / f'{name}.pdf', bbox_inches='tight')
    fig.savefig(ASSETS / f'{name}.png', dpi=300, bbox_inches='tight')
    plt.close(fig)

fig, ax = plt.subplots(figsize=(7.0,4.2),layout='constrained')
for s in ids:
    n=nodes[s]
    ax.scatter(n.lon,n.lat,s=grouped.loc[s,'mass']*1.4+20,color=blue,alpha=.72)
    ax.annotate(s,(n.lon,n.lat),xytext=(5,5),textcoords='offset points',fontsize=9)
o=nodes['O01']
ax.scatter(o.lon,o.lat,marker='*',s=150,color=orange,label='调度中心 O01',zorder=5)
ax.set(xlabel='经度 / °E',ylabel='纬度 / °N')
ax.ticklabel_format(useOffset=False,style='plain')
ax.set_aspect(1/np.cos(np.deg2rad(np.mean([nodes[s].lat for s in ids]))))
ax.margins(.12); ax.legend(frameon=False)
ax.text(.98,.03,'圆点面积随需求质量增大',transform=ax.transAxes,ha='right',fontsize=9)
save(fig,'raw_service_map')

fig, axes=plt.subplots(1,2,figsize=(9,4.2),layout='constrained')
x=np.arange(len(ids))
axes[0].bar(x,grouped.loc[ids,'mass'],color=blue)
axes[1].bar(x,grouped.loc[ids,'hard'],color=orange,label='硬时限箱')
axes[1].bar(x,grouped.loc[ids,'boxes']-grouped.loc[ids,'hard'],bottom=grouped.loc[ids,'hard'],color=green,label='软时限箱')
for ax in axes:
    ax.set_xticks(x,ids,rotation=60,ha='right'); ax.grid(axis='y',alpha=.2); ax.set_axisbelow(True)
axes[0].set(ylabel='物资质量 / kg',title='(a) 各服务区需求质量')
axes[1].set(ylabel='货箱数量 / 箱',title='(b) 时限类别构成'); axes[1].legend(frameon=False,fontsize=9)
save(fig,'raw_demand_composition')

fig, ax=plt.subplots(figsize=(7.0,3.8),layout='constrained')
categories=[('医疗且首批', medical & first,orange,'D'),('仅医疗',medical & ~first,'#8B6598','^'),
            ('仅首批',first & ~medical,blue,'s'),('一般物资',~hard,green,'o')]
for name,mask,color,marker in categories:
    times=hard_deadlines[mask] if name!='一般物资' else boxes.loc[mask,'期望送达时间（s）']
    # Aggregate equal coordinates so overlap does not hide sample counts.
    xy={}
    for t,w in zip(times,boxes.loc[mask,'应急优先系数']):
        xy[(float(t)/3600,float(w))]=xy.get((float(t)/3600,float(w)),0)+1
    if xy:
        ax.scatter([k[0] for k in xy],[k[1] for k in xy],s=[30+10*n for n in xy.values()],
                   marker=marker,color=color,alpha=.7,label=f'{name}（{int(mask.sum())}箱）')
ax.set(xlabel='有效硬截止 / 一般物资期望时刻（h）',ylabel='应急优先系数')
ax.grid(alpha=.2); ax.legend(frameon=False,fontsize=9,ncol=2,loc='upper right')
save(fig,'raw_deadline_classes')

paper=ROOT/'paper'
(paper/'figures'/'data').mkdir(parents=True,exist_ok=True)
(paper/'tables').mkdir(exist_ok=True)
for p in ASSETS.iterdir(): shutil.copy2(p,paper/'figures'/'data'/p.name)
rows=[]
for s in ids:
    r=grouped.loc[s]
    rows.append(f'{s} & {int(r.boxes)} & {r.mass:.2f} & {r.volume:.3f} & {int(r.hard)} \\\\')
rows.append(f'合计 & 80 & {stats["mass_kg"]:.2f} & {stats["volume_m3"]:.3f} & {stats["hard_count"]} \\\\')
table_head = r'''\begin{longtable}{lrrrr}
\caption{逐服务区需求统计}\label{tab:demand-details}\\
\toprule 服务区 & 箱数 & 质量/kg & 体积/m$^3$ & 硬时限箱数\\\midrule\endfirsthead
\toprule 服务区 & 箱数 & 质量/kg & 体积/m$^3$ & 硬时限箱数\\\midrule\endhead
'''
(paper/'tables'/'service_demand.tex').write_text(table_head+'\n'.join(rows)+'\n'+r'\bottomrule\end{longtable}'+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in stats.items() if k not in ['input_hashes','transport_types','inventory','relay']},ensure_ascii=False,indent=2))
