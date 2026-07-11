from pathlib import Path
from .config import load_config
from .export import ensure_dirs
from .repository_adapter import load_repository_stats
from .figures import build_all as build_figures
from .tables import build_all as build_tables
from .bibliography import write_reference_plan
from .manuscript import build_docx
from .review import review_publication
from .manifest import write_manifest
from .captions import FIGURE_CAPTIONS
from .manuscript_source import section_paragraphs
def main():
 root=Path(__file__).resolve().parents[1]; config=load_config(root); ensure_dirs(root,config); theme=config.get('theme',{}).get('name','primenet_light')
 print('='*66); print('PrimeNet Publisher v2.2'); print('='*66); print(f'Root:  {root}'); print(f'Title: {config.get("title")}'); print(f'Theme: {theme}')
 stats=load_repository_stats(root,config); print(f'Repository statistics source: {stats.get("_source")}')
 fig_dir=root/config['paths']['figures']; tab_dir=root/config['paths']['tables']; ref_dir=root/config['paths']['references']; out_dir=root/config['paths']['output']
 if config.get('outputs',{}).get('figures',True): build_figures(fig_dir,theme)
 tables=build_tables(tab_dir,stats) if config.get('outputs',{}).get('tables',True) else {}
 write_reference_plan(ref_dir/'reference_plan.md')
 if config.get('outputs',{}).get('docx',True): print(f'Generated integrated DOCX: {build_docx(root,config,stats,tables)}')
 status='SKIPPED'
 if config.get('outputs',{}).get('review',True): status,path,checks=review_publication(root,config,tables); print(f'Generated review report: {path}')
 if config.get('outputs',{}).get('manifest',True): write_manifest(out_dir/'publication_manifest.json',config,stats,list(FIGURE_CAPTIONS.keys()),list(tables.keys()),status,[s['title'] for s in section_paragraphs(stats)]); print(f'Generated publication manifest: {out_dir/"publication_manifest.json"}')
 print('='*66); print(f'PrimeNet publication build status: {status}'); print('='*66)
if __name__=='__main__': main()
