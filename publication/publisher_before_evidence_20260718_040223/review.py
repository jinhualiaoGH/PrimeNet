from pathlib import Path
from .captions import FIGURE_CAPTIONS
from .manuscript_source import section_paragraphs

OPTIONAL_PUBLICATION_TABLES = {
    'table07_observational_performance',
}

def _active_review_tables(table_dir, tables):
    active = []
    for table_name in tables:
        paths = [
            table_dir / f'{table_name}.{ext}'
            for ext in ('csv', 'md', 'docx')
        ]
        if (
            table_name in OPTIONAL_PUBLICATION_TABLES
            and not any(path.exists() for path in paths)
        ):
            print(
                f'[SKIP] Optional verification table unavailable: '
                f'{table_name}'
            )
            continue
        active.append(table_name)
    return active

def review_publication(root,config,tables):
 root=Path(root); fig_dir=root/config['paths']['figures']; table_dir=root/config['paths']['tables']; out_dir=root/config['paths']['output']; checks=[]
 def check(name,ok,detail=''): checks.append({'check':name,'status':'PASSED' if ok else 'FAILED','detail':detail})
 for fig in FIGURE_CAPTIONS:
  for ext,minsize in [('png',20000),('svg',5000)]:
   p=fig_dir/f'{fig}.{ext}'; check(f'Figure {ext.upper()} exists: {fig}',p.exists());
   if p.exists(): check(f'Figure {ext.upper()} nontrivial size: {fig}',p.stat().st_size>minsize,f'{p.stat().st_size} bytes')
 for t in _active_review_tables(table_dir, tables):
  for ext in ['csv','md','docx']: check(f'Table {ext.upper()} exists: {t}',(table_dir/f'{t}.{ext}').exists())
 docs=list(out_dir.glob('PrimeNet_Architecture_Publication_Draft_v2_3.docx')); check('Integrated Draft 2 DOCX exists',bool(docs));
 if docs: check('Integrated Draft 2 DOCX nontrivial size',docs[0].stat().st_size>150000,f'{docs[0].stat().st_size} bytes')
 secs=section_paragraphs({}); check('Manuscript sections present',len(secs)>=10,f'{len(secs)} sections configured')
 status='PASSED' if all(c['status']=='PASSED' for c in checks) else 'FAILED'
 lines=['='*60,'PrimeNet Publication Verification v2.3','='*60]
 for c in checks:
  sym='OK' if c['status']=='PASSED' else 'FAIL'; det=f" - {c['detail']}" if c.get('detail') else ''; lines.append(f'[{sym}] {c["check"]}{det}')
 lines += ['='*60,f'Overall Status: {status}','='*60]
 path=out_dir/'publication_review_report.txt'; path.write_text('\n'.join(lines)+'\n',encoding='utf-8'); return status,path,checks
