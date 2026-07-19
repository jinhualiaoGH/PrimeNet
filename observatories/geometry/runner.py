from __future__ import annotations

import argparse, csv, hashlib, json, platform, subprocess, sys, time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np

from observatories.framework import CoordinateRange
from .engine import compute_geometry_metrics, read_transition_counts_csv
from .metadata import *
from .observation_builder import build_geometry_observation


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"): return value.to_dict()
    if is_dataclass(value): return asdict(value)
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, Path): return str(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _git(args: list[str]) -> str | None:
    try: return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return None


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def _write_matrix(path: Path, labels: tuple[str,...], matrix: np.ndarray) -> None:
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['state',*labels])
        for label,row in zip(labels,matrix): w.writerow([label,*map(float,row)])


def run(args: argparse.Namespace) -> Path:
    started=time.perf_counter()
    info_dir=Path(args.information_output_dir).expanduser().resolve()
    info_summary_path=info_dir/'information_summary.json'
    info_validation_path=info_dir/'information_validation.json'
    if not info_summary_path.is_file(): raise FileNotFoundError(f"Information summary not found: {info_summary_path}")
    if not info_validation_path.is_file(): raise FileNotFoundError(f"Information validation not found: {info_validation_path}")
    info_summary=json.loads(info_summary_path.read_text(encoding='utf-8'))
    info_validation=json.loads(info_validation_path.read_text(encoding='utf-8'))
    if info_validation.get('status') != 'PASS': raise ValueError('Source Information observation is not validated.')
    counts_path=Path(info_summary['inputs']['transition_counts_csv'])
    labels,counts=read_transition_counts_csv(counts_path)
    metrics=compute_geometry_metrics(counts,state_labels=labels,cluster_count=args.clusters,neighbor_count=args.neighbors,js_weight=args.js_weight)
    output=Path(args.output_dir).expanduser().resolve(); output.mkdir(parents=True,exist_ok=True)
    distance_path=output/'state_distance_matrix.csv'; neighbors_path=output/'nearest_neighbors.csv'; clusters_path=output/'cluster_assignments.csv'
    emb2_path=output/'embedding_2d.csv'; emb3_path=output/'embedding_3d.csv'; metrics_path=output/'geometry_metrics.json'; summary_path=output/'geometry_summary.json'; validation_path=output/'geometry_validation.json'; observation_path=output/'geometry_observation.json'; manifest_path=output/'sha256_manifest.json'
    _write_matrix(distance_path,metrics.active_labels,metrics.combined_distance)
    with neighbors_path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['state','rank','neighbor','distance'])
        for i,label in enumerate(metrics.active_labels):
            for rank,(j,d) in enumerate(zip(metrics.nearest_neighbor_indices[i],metrics.nearest_neighbor_distances[i]),start=1): w.writerow([label,rank,metrics.active_labels[int(j)],float(d)])
    with clusters_path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['state','cluster']); [w.writerow([l,int(c)]) for l,c in zip(metrics.active_labels,metrics.cluster_assignments)]
    for path,coords in ((emb2_path,metrics.embedding_2d),(emb3_path,metrics.embedding_3d)):
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(['state',*[f'axis_{i+1}' for i in range(coords.shape[1])]])
            for label,row in zip(metrics.active_labels,coords): w.writerow([label,*map(float,row)])
    metric_dict={
        'active_state_count':metrics.active_state_count,'cluster_count':metrics.cluster_count,
        'mean_pairwise_distance':metrics.mean_pairwise_distance,'max_pairwise_distance':metrics.max_pairwise_distance,
        'mean_nearest_neighbor_distance':metrics.mean_nearest_neighbor_distance,'effective_dimension':metrics.effective_dimension,
        'explained_variance_2d':metrics.explained_variance_2d,'explained_variance_3d':metrics.explained_variance_3d,
    }
    metrics_path.write_text(json.dumps(metric_dict,indent=2),encoding='utf-8')
    checks={
        'source_information_validated':info_validation.get('status')=='PASS',
        'distance_symmetric':bool(np.allclose(metrics.combined_distance,metrics.combined_distance.T)),
        'distance_diagonal_zero':bool(np.allclose(np.diag(metrics.combined_distance),0.0)),
        'distance_nonnegative':bool(np.all(metrics.combined_distance>=-1e-12)),
        'embedding_finite':bool(np.all(np.isfinite(metrics.embedding_3d))),
        'clusters_complete':len(metrics.cluster_assignments)==metrics.active_state_count,
        'neighbors_valid':bool(np.all(metrics.nearest_neighbor_indices>=0)),
        'variance_bounds':0.0<=metrics.explained_variance_2d<=metrics.explained_variance_3d<=1.0+1e-12,
    }
    status='PASS' if all(checks.values()) else 'FAIL'; validation={'status':status,'checks':checks}; validation_path.write_text(json.dumps(validation,indent=2),encoding='utf-8')
    if status!='PASS': raise RuntimeError('Geometry observation validation failed.')
    created=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'); runtime=time.perf_counter()-started
    summary={
        'project':PROJECT,'instrument':'geometry_runner.py','instrument_id':'GO-001','observatory':OBSERVATORY_NAME,'version':VERSION,
        'algorithm':ALGORITHM,'algorithm_version':ALGORITHM_VERSION,'coordinate_system':info_summary.get('coordinate_system',COORDINATE_SYSTEM),
        'start':int(info_summary['start']),'end':int(info_summary['end']),'active_state_count':metrics.active_state_count,'cluster_count':metrics.cluster_count,
        'geometry_metrics':metric_dict,'validation':validation,'runtime':{'total_seconds':runtime,'total_minutes':runtime/60.0},
        'inputs':{'information_summary_json':str(info_summary_path),'information_validation_json':str(info_validation_path),'transition_counts_csv':str(counts_path)},
        'outputs':{'distance_csv':str(distance_path),'neighbors_csv':str(neighbors_path),'clusters_csv':str(clusters_path),'embedding_2d_csv':str(emb2_path),'embedding_3d_csv':str(emb3_path),'metrics_json':str(metrics_path),'validation_json':str(validation_path),'summary_json':str(summary_path),'observation_json':str(observation_path)},
        'created_utc':created,'python_version':platform.python_version(),'platform':platform.platform(),'numpy_version':np.__version__,'git_commit':_git(['rev-parse','HEAD']),'git_tag':_git(['describe','--tags','--exact-match']),'command_line':' '.join(sys.argv),
    }
    summary_path.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    observation=build_geometry_observation(observation_id=args.observation_id,coordinate_range=CoordinateRange(coordinate_system=summary['coordinate_system'],start=summary['start'],end=summary['end']),summary=summary,created_utc=created)
    observation_path.write_text(json.dumps(_jsonable(observation),indent=2,default=_jsonable),encoding='utf-8')
    artifacts=[distance_path,neighbors_path,clusters_path,emb2_path,emb3_path,metrics_path,summary_path,validation_path,observation_path]
    manifest_path.write_text(json.dumps({p.name:_sha256(p) for p in artifacts},indent=2),encoding='utf-8')
    return output


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description='Run PrimeNet Geometry Observatory v1.0')
    p.add_argument('--information-output-dir',required=True); p.add_argument('--output-dir',required=True); p.add_argument('--observation-id',default='GEOMETRY-V1')
    p.add_argument('--clusters',type=int,default=8); p.add_argument('--neighbors',type=int,default=5); p.add_argument('--js-weight',type=float,default=0.5)
    return p


def main() -> None:
    output=run(parser().parse_args()); print('='*80); print('PrimeNet Geometry Observatory v1.0: PASSED'); print(f'Output: {output}'); print('='*80)

if __name__=='__main__': main()
