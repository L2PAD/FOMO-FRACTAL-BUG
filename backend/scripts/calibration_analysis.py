"""Block 8.1 — Confidence Calibration Data Collector"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from pymongo import MongoClient, DESCENDING
from collections import defaultdict

mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'intelligence_engine').strip('"')
db = MongoClient(mongo_url)[db_name]
col = db['exchange_forecasts']

# 1. Count
total = col.count_documents({})
evaluated = col.count_documents({'evaluated': True})
print(f'Total forecasts: {total}')
print(f'Evaluated: {evaluated}')

# 2. Collect calibration data
all_eval = list(col.find(
    {'evaluated': True},
    {'_id': 0, 'confidence': 1, 'confidenceRaw': 1, 'direction': 1,
     'directionClass': 1, 'outcome': 1, 'entryPrice': 1, 'targetPrice': 1,
     'horizon': 1, 'asset': 1, 'confidenceDirection': 1, 'confidenceTarget': 1}
))

print(f'With evaluation: {len(all_eval)}')

# 3. Sample outcomes to understand structure
print('\nSample outcomes:')
for d in all_eval[:5]:
    o = d.get('outcome', {})
    print(f"  asset={d.get('asset')} h={d.get('horizon')} dir={d.get('direction')} "
          f"conf={d.get('confidence')} confRaw={d.get('confidenceRaw')} outcome={o}")

# 4. Bucket analysis
buckets = defaultdict(lambda: {'count': 0, 'correct': 0, 'confs': []})
skipped = 0

for d in all_eval:
    conf = d.get('confidence') or d.get('confidenceRaw') or 0
    outcome = d.get('outcome')
    if not outcome or not isinstance(outcome, dict):
        skipped += 1
        continue

    label = outcome.get('outcome', outcome.get('label', ''))
    if not label:
        skipped += 1
        continue

    # Determine bucket
    if conf < 0.2:
        bk = '0.0-0.2'
    elif conf < 0.4:
        bk = '0.2-0.4'
    elif conf < 0.6:
        bk = '0.4-0.6'
    elif conf < 0.8:
        bk = '0.6-0.8'
    else:
        bk = '0.8-1.0'

    is_correct = label in ('TP', 'WEAK')
    buckets[bk]['count'] += 1
    buckets[bk]['correct'] += 1 if is_correct else 0
    buckets[bk]['confs'].append(conf)

print(f'\nSkipped: {skipped}')
print(f'\n{"Bucket":<10} {"Count":<8} {"Avg Conf":<10} {"Real Acc":<10} {"Gap":<8}')
print('-' * 50)

for bk in ['0.0-0.2', '0.2-0.4', '0.4-0.6', '0.6-0.8', '0.8-1.0']:
    data = buckets.get(bk, {'count': 0, 'correct': 0, 'confs': []})
    if data['count'] > 0:
        avg_conf = sum(data['confs']) / len(data['confs'])
        real_acc = data['correct'] / data['count']
        gap = avg_conf - real_acc
        print(f'{bk:<10} {data["count"]:<8} {avg_conf:<10.4f} {real_acc:<10.4f} {gap:<+8.4f}')
    else:
        print(f'{bk:<10} {"0":<8} {"-":<10} {"-":<10} {"-":<8}')

# 5. Per-horizon analysis
print('\n--- Per Horizon ---')
for h in ['24H', '7D', '30D']:
    h_docs = [d for d in all_eval if d.get('horizon') == h]
    if not h_docs:
        print(f'  {h}: no data')
        continue
    correct = 0
    total_h = 0
    confs = []
    for d in h_docs:
        outcome = d.get('outcome')
        if not outcome or not isinstance(outcome, dict):
            continue
        label = outcome.get('outcome', outcome.get('label', ''))
        if not label:
            continue
        total_h += 1
        confs.append(d.get('confidence') or d.get('confidenceRaw') or 0)
        if label in ('TP', 'WEAK'):
            correct += 1
    if total_h > 0:
        avg_c = sum(confs) / len(confs) if confs else 0
        acc = correct / total_h
        print(f'  {h}: n={total_h}, avg_conf={avg_c:.4f}, real_acc={acc:.4f}, gap={avg_c - acc:+.4f}')

# 6. Direction distribution
print('\n--- Direction Distribution ---')
dir_counts = defaultdict(int)
for d in all_eval:
    dir_counts[d.get('direction', 'UNKNOWN')] += 1
for k, v in sorted(dir_counts.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v} ({v/len(all_eval)*100:.1f}%)')
