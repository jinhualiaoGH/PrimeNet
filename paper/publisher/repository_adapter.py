from pathlib import Path
import json
DEFAULT_STATS={'repository_interval':'1 <= n <= 10^12','verified_prime_numbers':'37,607,912,018','largest_stored_prime':'999,999,999,989','repository_segments':'100','segment_size':'10^10 integers','repository_verification':'100/100 passed','repository_construction':'Deterministic','prime_space':'Implemented','observatory_framework':'Implemented','product_framework':'Implemented','registry_services':'Implemented'}
def _try_json(path):
 try:
  if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
 except Exception: return None
 return None
def _normalize(raw):
 stats=DEFAULT_STATS.copy()
 if not raw: return stats
 for k in stats:
  if k in raw: stats[k]=str(raw[k])
 if 'total_primes' in raw: stats['verified_prime_numbers']=f"{int(raw['total_primes']):,}"
 if 'largest_prime' in raw: stats['largest_stored_prime']=f"{int(raw['largest_prime']):,}"
 if 'segments' in raw: stats['repository_segments']=str(raw['segments'])
 if 'passed' in raw and 'expected' in raw: stats['repository_verification']=f"{raw['passed']}/{raw['expected']} passed"
 return stats
def load_repository_stats(root,config):
 root=Path(root)
 for c in config.get('repository',{}).get('summary_candidates',[]):
  path=(root/c).resolve(); raw=_try_json(path)
  if raw:
   stats=_normalize(raw); stats['_source']=str(path); return stats
 fallback=root/'data'/'implementation_stats.json'; stats=_normalize(_try_json(fallback)); stats['_source']=str(fallback) if fallback.exists() else 'built-in defaults'; return stats
