#!/usr/bin/env python3
"""
KnowS Evidence Search Python Wrapper
封装 knows-evidence-search skill 的 Node.js 脚本调用，提供 Python 接口。

Usage:
  python evidence_search.py "<query>"
  python evidence_search.py "<query>" --sources paper_en guide trial
"""

import json
import sys
import os
import time
import subprocess
import argparse
from pathlib import Path
from typing import Optional, List, Dict

os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


DEFAULT_SOURCES = ['paper_en', 'guide', 'trial']
VALID_SOURCES = ['paper_en', 'paper_cn', 'meeting', 'guide', 'trial', 'package_insert']


def search_evidence(query: str, sources: List[str] = None, delay: float = 0.5) -> Dict:
    """
    搜索 KnowS 医学证据 API。
    
    Args:
        query: 搜索查询词
        sources: 证据来源列表，默认为 ['paper_en', 'guide', 'trial']
        delay: 串行调用之间的延迟（秒），避免速率限制
    
    Returns:
        包含所有来源证据的字典
    """
    if sources is None:
        sources = DEFAULT_SOURCES
    
    sources = [s for s in sources if s in VALID_SOURCES]
    
    if not sources:
        return {'error': 'No valid sources specified'}
    
    script_dir = Path(__file__).resolve().parent
    search_js_path = script_dir / 'search.js'
    
    if not search_js_path.exists():
        return {'error': f'search.js not found at {search_js_path}'}
    
    results = {}
    total_evidences = 0
    
    for source in sources:
        try:
            result = subprocess.run(
                ['node', str(search_js_path), '--source', source, '--query', query],
                capture_output=True,
                text=True,
                encoding='utf-8',
                cwd=str(script_dir.parent),
                timeout=30
            )
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout.strip())
                    results[source] = data
                    evidence_count = len(data.get('evidences', []))
                    total_evidences += evidence_count
                except json.JSONDecodeError:
                    results[source] = {
                        'error': 'Failed to parse JSON response',
                        'raw': result.stdout.strip()[:500]
                    }
            else:
                results[source] = {
                    'error': result.stderr.strip()[:500],
                    'return_code': result.returncode
                }
        except subprocess.TimeoutExpired:
            results[source] = {'error': 'Request timed out'}
        except FileNotFoundError:
            return {'error': 'Node.js is not installed or not in PATH'}
        except Exception as e:
            results[source] = {'error': str(e)}
        
        time.sleep(delay)
    
    return {
        'query': query,
        'sources': sources,
        'total_evidences': total_evidences,
        'results': results
    }


def format_evidence_summary(evidence_data: Dict) -> str:
    """
    将证据搜索结果格式化为可读文本摘要。
    
    Args:
        evidence_data: search_evidence 返回的字典
    
    Returns:
        格式化的文本摘要
    """
    if 'error' in evidence_data:
        return f"[证据搜索失败]: {evidence_data['error']}"
    
    lines = []
    lines.append(f"【证据搜索结果】")
    lines.append(f"  查询词: {evidence_data['query']}")
    lines.append(f"  搜索来源: {', '.join(evidence_data['sources'])}")
    lines.append(f"  总证据数: {evidence_data['total_evidences']}")
    lines.append(f"")
    
    for source, data in evidence_data['results'].items():
        if 'error' in data:
            lines.append(f"  [{source}] ❌ 搜索失败: {data['error']}")
            continue
        
        evidences = data.get('evidences', [])
        question_id = data.get('question_id', '')
        
        if not evidences:
            lines.append(f"  [{source}] 未找到相关证据")
            continue
        
        lines.append(f"  [{source}] 找到 {len(evidences)} 条证据 (question_id: {question_id})")
        for i, evidence in enumerate(evidences[:3], 1):
            title = evidence.get('title', 'No title')
            abstract = evidence.get('abstract', '')[:150]
            authors = ', '.join(evidence.get('authors', []))[:50]
            journal = evidence.get('journal', '')
            publish_date = evidence.get('publish_date', '')
            
            lines.append(f"    {i}. {title}")
            if authors:
                lines.append(f"       作者: {authors}")
            if journal:
                lines.append(f"       期刊: {journal}")
            if publish_date:
                lines.append(f"       日期: {publish_date}")
            if abstract:
                lines.append(f"       摘要: {abstract}...")
            lines.append(f"")
    
    return '\n'.join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='KnowS Evidence Search Python Wrapper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('query', help='搜索查询词')
    parser.add_argument('--sources', '-s', nargs='+', default=DEFAULT_SOURCES,
                        help=f'证据来源（默认: {" ".join(DEFAULT_SOURCES)}）')
    parser.add_argument('--json', '-j', action='store_true', help='以 JSON 格式输出')
    return parser.parse_args()


def main():
    args = parse_args()
    
    result = search_evidence(args.query, args.sources)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_evidence_summary(result))


if __name__ == '__main__':
    main()