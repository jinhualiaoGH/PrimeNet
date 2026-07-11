from pathlib import Path
from publisher.config import load_config
from publisher.repository_adapter import load_repository_stats
from publisher.tables import make_tables
from publisher.review import review_publication
if __name__ == '__main__':
    root=Path(__file__).resolve().parent; config=load_config(root); stats=load_repository_stats(root,config); tables=make_tables(stats); status,path,checks=review_publication(root,config,tables); print(path.read_text(encoding='utf-8'))
