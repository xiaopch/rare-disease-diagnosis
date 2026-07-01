#!/usr/bin/env python3
"""
罕见病诊断脚本 v2.1
基于本地 JSON 疾病知识库，通过关键词加权匹配进行罕见病辅助诊断。

Usage:
  python diagnose.py "<症状描述>"
  python diagnose.py "<症状描述>" --top 3
  python diagnose.py "<症状描述>" --json
  python diagnose.py "<症状描述>" --output
  python diagnose.py "<症状描述>" --fuzzy
  python diagnose.py --list-diseases
"""

import json
import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional


# ─────────────────────────────────────────────
# 文本预处理
# ─────────────────────────────────────────────
def normalize_text(text: str) -> str:
    """标准化文本：全角转半角、去标点、合并空格、转小写"""
    # 全角转半角
    chars = []
    for c in text:
        code = ord(c)
        if 0xFF01 <= code <= 0xFF5E:
            chars.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            chars.append(' ')
        else:
            chars.append(c)
    text = ''.join(chars).lower()
    # 去标点（保留中文、字母、数字、空格）
    text = re.sub(r'[^\w\s\u4e00-\u9fff]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def fuzzy_match_chars(keyword: str, text: str) -> tuple[bool, float]:
    """
    字符级模糊匹配：检查 keyword 中每个字是否按顺序出现在 text 中。
    精确子串匹配返回质量 1.0，模糊匹配按紧凑度折算。

    Returns:
        (是否匹配, 匹配质量 0.0~1.0)
    """
    if keyword in text:
        return True, 1.0
    chars = list(keyword)
    pos = 0
    first_pos = -1
    for c in chars:
        found = text.find(c, pos)
        if found == -1:
            return False, 0.0
        if first_pos < 0:
            first_pos = found
        pos = found + 1
    span = pos - first_pos
    quality = max(0.1, min(1.0, len(chars) / span)) if span > 0 else 1.0
    return True, quality


# ─────────────────────────────────────────────
# 数据加载
# ─────────────────────────────────────────────
def load_disease_db(data_path: Optional[str] = None) -> list[dict]:
    """
    加载本地罕见病 JSON 数据库。

    Args:
        data_path: JSON 数据文件路径。默认从脚本同级 data/diseases.json 加载。

    Returns:
        疾病列表
    """
    if data_path is None:
        script_dir = Path(__file__).resolve().parent
        skill_root = script_dir.parent
        data_path = skill_root / 'data' / 'diseases.json'
    else:
        data_path = Path(data_path)

    if not data_path.exists():
        print(f'错误：数据文件不存在 → {data_path}', file=sys.stderr)
        sys.exit(1)

    with open(data_path, 'r', encoding='utf-8-sig') as f:
        db = json.load(f)

    return db.get('diseases', [])


# ─────────────────────────────────────────────
# 匹配引擎
# ─────────────────────────────────────────────
def match_disease(symptoms: str, diseases: list[dict], top_k: int = 1,
                  fuzzy: bool = False) -> list[dict]:
    """
    基于关键词加权匹配，对用户症状描述进行罕见病诊断。

    匹配逻辑：
      1. 标准化用户输入（全角转半角、去标点、转小写）
      2. 对每种疾病，统计 keywords 和 core_symptoms 中有多少项出现在用户输入中
      3. 关键词权重 1.0，核心症状权重 1.5
      4. 可选 fuzzy 模式：当精确子串匹配失败时，尝试字符级顺序模糊匹配（质量折算）
      5. 按原始得分降序排列，返回 top_k 个结果

    Args:
        symptoms: 用户症状描述文本
        diseases: 疾病数据库列表
        top_k: 返回前 K 个匹配结果
        fuzzy: 是否启用字符级模糊匹配

    Returns:
        匹配结果列表，每项包含疾病信息和匹配得分
    """
    normalized = normalize_text(symptoms)
    results = []

    for disease in diseases:
        keywords = disease.get('keywords', [])
        core_symptoms = disease.get('core_symptoms', [])

        keyword_hits = []
        keyword_score = 0.0
        symptom_hits = []
        symptom_score = 0.0

        for kw in keywords:
            kw_norm = normalize_text(kw)
            if kw_norm in normalized:
                keyword_hits.append(kw)
                keyword_score += 1.0
            elif fuzzy:
                matched, quality = fuzzy_match_chars(kw_norm, normalized)
                if matched:
                    keyword_hits.append(kw + '(模糊)')
                    keyword_score += quality

        for s in core_symptoms:
            s_norm = normalize_text(s)
            if s_norm in normalized:
                symptom_hits.append(s)
                symptom_score += 1.5
            elif fuzzy:
                matched, quality = fuzzy_match_chars(s_norm, normalized)
                if matched:
                    symptom_hits.append(s + '(模糊)')
                    symptom_score += 1.5 * quality

        total_possible = len(keywords) * 1.0 + len(core_symptoms) * 1.5
        raw_score = keyword_score + symptom_score
        normalized_score = raw_score / total_possible if total_possible > 0 else 0

        if raw_score > 0:
            results.append({
                'id': disease['id'],
                'name': disease['name'],
                'name_en': disease.get('name_en', ''),
                'icd10': disease.get('icd10', ''),
                'category': disease.get('category', ''),
                'prevalence': disease.get('prevalence', ''),
                'key_features': disease.get('key_features', ''),
                'onset_age': disease.get('onset_age', ''),
                'diagnostic_criteria': disease.get('diagnostic_criteria', ''),
                'lab_markers': disease.get('lab_markers', []),
                'genetic_test': disease.get('genetic_test', ''),
                'treatment_summary': disease.get('treatment_summary', ''),
                'keyword_hits': keyword_hits,
                'symptom_hits': symptom_hits,
                'raw_score': round(raw_score, 2),
                'normalized_score': round(normalized_score, 4),
                'confidence': _score_to_confidence(raw_score),
                'cases': disease.get('cases', []),
            })

    results.sort(key=lambda x: x['raw_score'], reverse=True)
    return results[:top_k]


def _score_to_confidence(raw_score: float) -> str:
    """
    将原始得分转换为置信度等级。

    规则：
      - 命中 5+ 个关键词/症状 → 高置信度
      - 命中 3-4 个 → 中置信度
      - 命中 1-2 个 → 低置信度
    """
    if raw_score >= 5.0:
        return '高'
    elif raw_score >= 3.0:
        return '中'
    else:
        return '低'


# ─────────────────────────────────────────────
# 输出格式化
# ─────────────────────────────────────────────
def format_cases(cases: list[dict]) -> str:
    """将案例数据格式化为可读文本"""
    if not cases:
        return ''
    lines = []
    lines.append('')
    lines.append(f'【相关临床案例共 {len(cases)} 例】')
    lines.append('')
    for i, case in enumerate(cases, 1):
        lines.append(f'  ┌─ 案例 {i}: {case.get("title", "")}')
        lines.append(f'  │ 患者: {case.get("patient", "")}')
        lines.append(f'  │ 主诉: {case.get("chief_complaint", "")}')
        lines.append(f'  ├─ 病史')
        for h_line in case.get('history', '').split('。'):
            if h_line.strip():
                lines.append(f'  │    {h_line.strip()}。')
        lines.append(f'  ├─ 检查发现')
        for f_line in case.get('findings', '').split('。'):
            if f_line.strip():
                lines.append(f'  │    {f_line.strip()}。')
        lines.append(f'  ├─ 诊断')
        for d_line in case.get('diagnosis', '').split('。'):
            if d_line.strip():
                lines.append(f'  │    {d_line.strip()}。')
        lines.append(f'  ├─ 治疗经过')
        for t_line in case.get('treatment', '').split('。'):
            if t_line.strip():
                lines.append(f'  │    {t_line.strip()}。')
        lines.append(f'  └─ 【启示】{case.get("key_takeaway", "")}')
        lines.append('')
    return '\n'.join(lines)


def format_result_text(results: list[dict], symptoms: str,
                       detail: bool = False, show_cases: bool = False) -> str:
    """将匹配结果格式化为可读文本"""
    if not results:
        return '该用户可能患有其他疾病（未在罕见病知识库中找到匹配）'

    lines = []
    top = results[0]

    if top['confidence'] == '高':
        lines.append(f'该用户可能患有{top["name"]}（{top["name_en"]}）')
    elif top['confidence'] == '中':
        lines.append(f'该用户可能患有{top["name"]}（{top["name_en"]}）— 建议进一步检查')
    else:
        lines.append(f'该用户可能患有{top["name"]}（{top["name_en"]}）— 匹配度较低，仅供参考')

    lines.append('')
    lines.append('【疾病信息】')
    lines.append(f'  ICD-10: {top["icd10"]}')
    lines.append(f'  分类: {top["category"]}')
    lines.append(f'  患病率: {top["prevalence"]}')
    lines.append(f'  好发年龄: {top["onset_age"]}')
    lines.append(f'  核心特征: {top["key_features"]}')
    if top.get('diagnostic_criteria'):
        lines.append(f'  诊断标准: {top["diagnostic_criteria"]}')
    if top.get('genetic_test'):
        lines.append(f'  基因检测: {top["genetic_test"]}')

    lines.append('')
    lines.append('【匹配详情】')
    lines.append(f'  置信度: {top["confidence"]}')
    if detail:
        lines.append(f'  原始得分: {top["raw_score"]}')
        lines.append(f'  归一化得分: {top["normalized_score"]}')
    if top['keyword_hits']:
        lines.append(f'  命中关键词: {", ".join(top["keyword_hits"])}')
    if top['symptom_hits']:
        lines.append(f'  命中核心症状: {", ".join(top["symptom_hits"])}')

    if len(results) > 1:
        lines.append('')
        lines.append('【鉴别诊断】')
        for r in results[1:3]:
            if detail:
                lines.append(f'  - {r["name"]}（{r["name_en"]}），置信度: {r["confidence"]}（得分: {r["raw_score"]}）')
            else:
                lines.append(f'  - {r["name"]}（{r["name_en"]}），置信度: {r["confidence"]}')

    lines.append('')
    lines.append('【实验室检查】')
    if top.get('lab_markers'):
        for marker in top['lab_markers']:
            lines.append(f'  • {marker}')

    lines.append('')
    lines.append('【治疗概要】')
    if top.get('treatment_summary'):
        lines.append(f'  {top["treatment_summary"]}')

    if show_cases and top.get('cases'):
        lines.append(format_cases(top['cases']))

    lines.append('')
    lines.append('[!] 免责声明：本结果仅供学习参考，不构成医疗诊断依据。如有健康疑虑，请及时就医。')

    return '\n'.join(lines)


def format_result_json(results: list[dict]) -> str:
    """将匹配结果格式化为 JSON"""
    if not results:
        return json.dumps({
            'diagnosis': '该用户可能患有其他疾病',
            'matches': [],
            'disclaimer': '本结果仅供学习参考，不构成医疗诊断依据。'
        }, ensure_ascii=False, indent=2)

    output = {
        'diagnosis': f'该用户可能患有{results[0]["name"]}',
        'top_match': {
            'name': results[0]['name'],
            'name_en': results[0]['name_en'],
            'icd10': results[0]['icd10'],
            'category': results[0]['category'],
            'confidence': results[0]['confidence'],
            'raw_score': results[0]['raw_score'],
            'normalized_score': results[0]['normalized_score'],
            'key_features': results[0]['key_features'],
        },
        'differential_diagnosis': [
            {
                'name': r['name'],
                'name_en': r['name_en'],
                'confidence': r['confidence'],
                'raw_score': r['raw_score'],
            }
            for r in results[1:3]
        ],
        'disclaimer': '本结果仅供学习参考，不构成医疗诊断依据。'
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


def save_output(text: str, symptoms: str) -> str:
    """将诊断结果保存至 output/ 目录"""
    output_dir = Path.cwd() / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
    filepath = output_dir / f'{timestamp}_diagnosis.md'
    markdown = (
        f'# 罕见病辅助诊断报告\n\n'
        f'## 基本信息\n\n'
        f'- **诊断时间**: {timestamp}\n'
        f'- **症状描述**: {symptoms}\n\n'
        f'---\n\n'
        f'## 诊断结果\n\n{text}\n'
    )
    filepath.write_text(markdown, encoding='utf-8')
    return str(filepath)


# ─────────────────────────────────────────────
# 辅助功能
# ─────────────────────────────────────────────
def list_diseases(diseases: list[dict]) -> str:
    """列出数据库中所有罕见病"""
    lines = [f'罕见病知识库共收录 {len(diseases)} 种疾病：', '']
    for i, d in enumerate(diseases, 1):
        lines.append(f'  {i:2d}. {d["name"]}（{d.get("name_en", "")}）— {d.get("category", "")}')
    return '\n'.join(lines)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='罕见病辅助诊断脚本 — 基于本地 JSON 知识库的关键词匹配',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('symptoms', nargs='*', help='症状描述文本（支持多个参数，自动拼接）')
    parser.add_argument('--top', '-k', type=int, default=3,
                        help='返回前 K 个匹配结果（默认 3）')
    parser.add_argument('--json', '-j', action='store_true',
                        help='以 JSON 格式输出')
    parser.add_argument('--data', '-d', help='指定疾病数据库 JSON 文件路径')
    parser.add_argument('--list-diseases', '-l', action='store_true',
                        help='列出数据库中所有疾病')
    parser.add_argument('--fuzzy', '-f', action='store_true',
                        help='启用字符级模糊匹配（降低准确度换取更高召回率）')
    parser.add_argument('--output', '-o', action='store_true',
                        help='将诊断结果保存至 output/ 目录（同时打印到终端）')
    parser.add_argument('--detail', action='store_true',
                        help='显示详细匹配得分信息')
    parser.add_argument('--cases', '-c', action='store_true',
                        help='显示匹配疾病的详细临床案例')
    return parser.parse_args()


def main():
    args = parse_args()
    diseases = load_disease_db(args.data)

    if args.list_diseases:
        print(list_diseases(diseases))
        return

    symptoms_parts = args.symptoms if isinstance(args.symptoms, list) else [args.symptoms]
    top_k = args.top

    if len(symptoms_parts) >= 2 and symptoms_parts[-1].isdigit():
        try:
            top_k = int(symptoms_parts[-1])
            symptoms_parts = symptoms_parts[:-1]
        except ValueError:
            pass

    symptoms_text = ' '.join(symptoms_parts) if symptoms_parts else ''

    if not symptoms_text:
        print('用法: python diagnose.py "<症状描述>"')
        print('      python diagnose.py --list-diseases')
        sys.exit(1)

    results = match_disease(symptoms_text, diseases, top_k=top_k, fuzzy=args.fuzzy)

    if args.json:
        output = format_result_json(results)
    else:
        output = format_result_text(results, symptoms_text, detail=args.detail, show_cases=args.cases)

    print(output)

    if args.output and not args.json:
        saved_path = save_output(output, symptoms_text)
        print(f'\n[已保存至] {saved_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
