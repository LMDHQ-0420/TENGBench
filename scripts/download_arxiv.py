#!/usr/bin/env python3
"""批量下载 arXiv 论文，按官方标题命名。用于补齐 benchmark 方法论参考文献。"""
import urllib.request, re, html, os, time

# (arXiv_id, 简称-tag)  benchmark 方法论论文，均为 arXiv 开放版
IDS = [
    ('2510.12171', 'MatSciBench'),
    ('2308.09115', 'MaScQA'),
    ('2505.23982', 'MSQA'),
    ('2412.10477', 'ALDbench'),
    ('2409.03161', 'MaterialBENCH'),
    ('2311.12022', 'GPQA'),
    ('2606.27047', 'NuclearQAv2'),
    ('2406.04244', 'BenchmarkDataContamination'),
    ('2412.13670', 'AntiLeakBench'),
]
OUTDIR = '/Users/lmdhq/WorkSpace/TENGBench/docs/papers/benchmark_methods'
HDR = {'User-Agent': 'Mozilla/5.0 (compatible; TENGBench-paper-fetch/1.0)'}

os.makedirs(OUTDIR, exist_ok=True)

for aid, tag in IDS:
    try:
        # 1) 取标题
        req = urllib.request.Request(
            f'https://export.arxiv.org/api/query?id_list={aid}', headers=HDR)
        meta = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
        m = re.search(r'<entry>.*?<title>(.*?)</title>', meta, re.DOTALL)
        if m:
            title = html.unescape(m.group(1).strip().replace('\n', ' '))
            title = re.sub(r'\s+', ' ', title)
        else:
            title = tag
        fname = re.sub(r'[/\\:*?"<>|]', '', title) + '.pdf'
        path = os.path.join(OUTDIR, fname)
        if os.path.exists(path) and os.path.getsize(path) > 20000:
            print(f'SKIP exists: {fname}')
            continue
        # 2) 下载 PDF
        req2 = urllib.request.Request(f'https://arxiv.org/pdf/{aid}', headers=HDR)
        data = urllib.request.urlopen(req2, timeout=90).read()
        if len(data) < 8000 or data[:4] != b'%PDF':
            print(f'FAIL not-pdf ({len(data)}B): {aid} {tag}')
            continue
        with open(path, 'wb') as f:
            f.write(data)
        print(f'OK  {fname} ({len(data)//1024}KB)')
    except Exception as e:
        print(f'ERR {aid} {tag}: {e}')
    time.sleep(1)

print('---')
print('done. files in benchmark_methods:')
for f in sorted(os.listdir(OUTDIR)):
    print('  ', f)
