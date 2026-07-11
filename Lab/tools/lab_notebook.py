import argparse
from pathlib import Path
from datetime import datetime

def main():
    ap = argparse.ArgumentParser(description="Append a PrimeNet Lab notebook entry.")
    ap.add_argument("--id", required=True, help="Example: LAB-001")
    ap.add_argument("--title", required=True)
    ap.add_argument("--issue", required=True)
    ap.add_argument("--hypothesis", default="")
    ap.add_argument("--experiment", default="")
    ap.add_argument("--result", default="")
    ap.add_argument("--conclusion", default="")
    ap.add_argument("--notebook", default="C:\\PrimeNet\\Lab\\notes\\lab_notebook.md")
    args = ap.parse_args()
    p = Path(args.notebook); p.parent.mkdir(parents=True, exist_ok=True)
    entry = f"""
## {args.id}: {args.title}

Date: {datetime.now().isoformat(timespec='seconds')}

Issue:
{args.issue}

Hypothesis:
{args.hypothesis}

Experiment:
{args.experiment}

Result:
{args.result}

Conclusion:
{args.conclusion}

---
"""
    with p.open("a", encoding="utf-8") as f: f.write(entry)
    print(f"Notebook updated: {p}")

if __name__ == "__main__": main()
