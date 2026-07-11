from pathlib import Path
def ensure_dirs(root,config):
 root=Path(root)
 for k in ['figures','tables','manuscript','output','references','data','build_logs']:(root/config['paths'][k]).mkdir(parents=True,exist_ok=True)
