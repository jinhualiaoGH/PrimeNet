from pathlib import Path
import copy
DEFAULT_CONFIG={"title":"PrimeNet: An Observatory for Prime Information Structures","author":"Jinhua Liao","affiliation":"Independent Researcher","version":"Publication Draft","paths":{"figures":"figures","tables":"tables","manuscript":"manuscript","output":"output","references":"references","data":"data","build_logs":"build_logs"},"outputs":{"figures":True,"tables":True,"docx":True,"review":True,"manifest":True},"theme":{"name":"primenet_light"},"layout":{"figure_width_inches":5.75,"table_font_size":8}}
def _deep_update(base, incoming):
    for k,v in (incoming or {}).items():
        if isinstance(v,dict) and isinstance(base.get(k),dict): _deep_update(base[k],v)
        else: base[k]=v
    return base
def load_config(root:Path):
    cfg=copy.deepcopy(DEFAULT_CONFIG); p=root/'publication.yaml'
    if not p.exists(): return cfg
    try:
        import yaml
        return _deep_update(cfg, yaml.safe_load(p.read_text(encoding='utf-8')) or {})
    except Exception as e:
        print(f"[WARN] Could not read publication.yaml ({e}); using defaults."); return cfg
