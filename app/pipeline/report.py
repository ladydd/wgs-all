"""
HTML 报告生成 — 一页纸总结所有分析结果

输入: 各分析步骤的结果
输出: 一个自包含的 HTML 文件
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.logging import logger


def generate_report(
    sample_id: str,
    output_file: str,
    y_haplogroup: Optional[str] = None,
    y_qc: Optional[float] = None,
    mt_haplogroup: Optional[str] = None,
    mt_quality: Optional[float] = None,
    admixture: Optional[Dict[str, Dict[str, float]]] = None,
    g25_nearest: Optional[List[tuple]] = None,
    eigenstrat_snps: Optional[int] = None,
    chip_formats: Optional[int] = None,
    reference: str = "hg38",
):
    """生成 HTML 报告"""

    # 祖源计算器 HTML
    admix_html = ""
    if admixture:
        for calc_name, components in admixture.items():
            sorted_comp = sorted(components.items(), key=lambda x: -x[1])
            rows = "".join(
                f'<tr><td>{name}</td><td><div class="bar" style="width:{pct*3}px"></div>{pct:.2f}%</td></tr>'
                for name, pct in sorted_comp if pct > 0.1
            )
            admix_html += f'<h3>{calc_name}</h3><table>{rows}</table>'

    # G25 最近人群
    g25_html = ""
    if g25_nearest:
        rows = "".join(
            f'<tr><td>{name}</td><td>{dist:.6f}</td></tr>'
            for name, dist in g25_nearest[:10]
        )
        g25_html = f'<h3>G25 最近人群</h3><table><tr><th>人群</th><th>距离</th></tr>{rows}</table>'

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>{sample_id} — WGS 分析报告</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #1a1a2e; color: #eee; }}
h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}
h2 {{ color: #7fdbff; margin-top: 30px; }}
h3 {{ color: #aaa; font-size: 14px; margin: 15px 0 5px; }}
.card {{ background: #16213e; border-radius: 8px; padding: 15px 20px; margin: 10px 0; }}
.card .label {{ color: #888; font-size: 12px; }}
.card .value {{ font-size: 24px; font-weight: bold; color: #00d4ff; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
tr:nth-child(even) {{ background: #1a1a3e; }}
td, th {{ padding: 4px 8px; text-align: left; }}
.bar {{ display: inline-block; height: 12px; background: #00d4ff; border-radius: 3px; margin-right: 5px; vertical-align: middle; }}
.footer {{ margin-top: 40px; color: #555; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>🧬 {sample_id}</h1>
<p style="color:#888">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 参考基因组: {reference}</p>

<h2>单倍群</h2>
<div class="grid">
  <div class="card">
    <div class="label">Y 染色体单倍群</div>
    <div class="value">{y_haplogroup or '—'}</div>
    <div class="label">QC: {y_qc if y_qc is not None else '—'}</div>
  </div>
  <div class="card">
    <div class="label">线粒体单倍群</div>
    <div class="value">{mt_haplogroup or '—'}</div>
    <div class="label">质量: {mt_quality if mt_quality is not None else '—'}</div>
  </div>
</div>

<h2>祖源成分</h2>
{admix_html or '<p style="color:#666">未计算</p>'}

{g25_html}

<h2>数据产出</h2>
<div class="grid">
  <div class="card">
    <div class="label">EIGENSTRAT SNP 数</div>
    <div class="value">{eigenstrat_snps or '—'}</div>
  </div>
  <div class="card">
    <div class="label">芯片格式</div>
    <div class="value">{chip_formats or '—'} 种</div>
  </div>
</div>

<div class="footer">
  wgs-all v1.2.0 | WGS 古 DNA 分析平台
</div>
</body>
</html>"""

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    logger.info(f"HTML 报告已生成: {output_file}")
    return output_file
