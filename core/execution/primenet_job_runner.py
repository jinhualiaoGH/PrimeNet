
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import psutil
except Exception:
    psutil = None

if os.name == "nt":
    import ctypes
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_AWAYMODE_REQUIRED = 0x00000040
else:
    ctypes = None


def now_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def safe_name(s: str) -> str:
    return ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in s).strip('_') or 'job'


class StayAwake:
    def __init__(self, enable: bool = True):
        self.enable = enable
        self.result = None

    def __enter__(self):
        if self.enable and os.name == "nt":
            try:
                # ES_AWAYMODE_REQUIRED is useful on desktops but may be ignored on laptops.
                flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
                self.result = bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
            except Exception:
                self.result = False
        else:
            self.result = False
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.enable and os.name == "nt":
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            except Exception:
                pass


def collect_environment(command: List[str], workdir: Path, stay_awake_result: Any) -> Dict[str, Any]:
    env = {
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "working_directory": str(workdir),
        "command": command,
        "stay_awake_result": stay_awake_result,
    }
    if psutil:
        try:
            env["cpu_count_logical"] = psutil.cpu_count(logical=True)
            env["cpu_count_physical"] = psutil.cpu_count(logical=False)
            vm = psutil.virtual_memory()
            env["memory_total_bytes"] = vm.total
            env["memory_available_bytes"] = vm.available
            if hasattr(psutil, 'sensors_battery'):
                batt = psutil.sensors_battery()
                if batt:
                    env["battery"] = {
                        "percent": batt.percent,
                        "power_plugged": batt.power_plugged,
                        "secsleft": batt.secsleft,
                    }
        except Exception as e:
            env["environment_collection_error"] = repr(e)
    return env


def process_tree_cpu_seconds(proc: subprocess.Popen) -> Optional[float]:
    if not psutil:
        return None
    try:
        p = psutil.Process(proc.pid)
        procs = [p] + p.children(recursive=True)
        total = 0.0
        for q in procs:
            try:
                t = q.cpu_times()
                total += float(t.user) + float(t.system)
            except Exception:
                pass
        return total
    except Exception:
        return None


def process_tree_memory_rss(proc: subprocess.Popen) -> Optional[int]:
    if not psutil:
        return None
    try:
        p = psutil.Process(proc.pid)
        procs = [p] + p.children(recursive=True)
        total = 0
        for q in procs:
            try:
                total += int(q.memory_info().rss)
            except Exception:
                pass
        return total
    except Exception:
        return None


def stream_reader(pipe, log_path: Path, echo: bool):
    with log_path.open('w', encoding='utf-8', errors='replace') as f:
        for line in iter(pipe.readline, ''):
            f.write(line)
            f.flush()
            if echo:
                print(line, end='')
        pipe.close()


def run_job(args: argparse.Namespace) -> int:
    if not args.command:
        raise SystemExit("No command supplied after --")
    workdir = Path(args.workdir or os.getcwd()).resolve()
    run_root = Path(args.run_root).resolve()
    job_id = f"{now_id()}_{safe_name(args.name)}"
    run_dir = run_root / job_id
    run_dir.mkdir(parents=True, exist_ok=False)

    stdout_path = run_dir / 'stdout.log'
    stderr_path = run_dir / 'stderr.log'
    heartbeat_path = run_dir / 'heartbeat.csv'
    summary_path = run_dir / 'job_summary.json'
    env_path = run_dir / 'environment.json'
    command_path = run_dir / 'command.txt'

    command_path.write_text(' '.join(args.command) + '\n', encoding='utf-8')

    print("="*72)
    print("PrimeNet Controlled Execution Framework v1.0")
    print("PrimeNet Job Runner")
    print("="*72)
    print(f"Job ID      : {job_id}")
    print(f"Workdir     : {workdir}")
    print(f"Command     : {' '.join(args.command)}")
    print(f"Run dir     : {run_dir}")

    start_wall = time.perf_counter()
    last_cpu = None
    last_wall = start_wall
    heartbeat_gap_warnings = 0
    max_wall_delta = 0.0
    last_valid_cpu = None

    with StayAwake(enable=not args.no_stay_awake) as awake:
        print(f"Stay awake  : {not args.no_stay_awake} result={awake.result}")
        print(f"Heartbeat   : every {args.heartbeat_seconds:.1f} sec")
        print("="*72)

        env = collect_environment(args.command, workdir, awake.result)
        env_path.write_text(json.dumps(env, indent=2), encoding='utf-8')

        proc = subprocess.Popen(
            args.command,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            creationflags=0,
        )

        t_out = threading.Thread(target=stream_reader, args=(proc.stdout, stdout_path, not args.quiet), daemon=True)
        t_err = threading.Thread(target=stream_reader, args=(proc.stderr, stderr_path, not args.quiet), daemon=True)
        t_out.start(); t_err.start()

        hb_rows = 0
        with heartbeat_path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp','wall_elapsed_seconds','wall_delta_seconds',
                'child_cpu_seconds','cpu_delta_seconds','cpu_wall_ratio',
                'rss_bytes','system_cpu_percent','memory_available_bytes',
                'heartbeat_gap_warning','process_returncode'
            ])
            writer.writeheader()
            while True:
                now = time.perf_counter()
                wall_elapsed = now - start_wall
                wall_delta = now - last_wall
                max_wall_delta = max(max_wall_delta, wall_delta)
                cpu = process_tree_cpu_seconds(proc)
                rss = process_tree_memory_rss(proc)
                if cpu is not None:
                    last_valid_cpu = cpu
                cpu_delta = None if (cpu is None or last_cpu is None) else cpu - last_cpu
                ratio = None if cpu is None or wall_elapsed <= 0 else cpu / wall_elapsed
                gap_warning = wall_delta > args.heartbeat_seconds * args.gap_warning_factor + 1.0
                if gap_warning:
                    heartbeat_gap_warnings += 1

                sys_cpu = None
                mem_avail = None
                if psutil:
                    try:
                        sys_cpu = psutil.cpu_percent(interval=None)
                        mem_avail = psutil.virtual_memory().available
                    except Exception:
                        pass

                writer.writerow({
                    'timestamp': datetime.now().isoformat(timespec='seconds'),
                    'wall_elapsed_seconds': f"{wall_elapsed:.6f}",
                    'wall_delta_seconds': f"{wall_delta:.6f}",
                    'child_cpu_seconds': '' if cpu is None else f"{cpu:.6f}",
                    'cpu_delta_seconds': '' if cpu_delta is None else f"{cpu_delta:.6f}",
                    'cpu_wall_ratio': '' if ratio is None else f"{ratio:.6f}",
                    'rss_bytes': '' if rss is None else str(rss),
                    'system_cpu_percent': '' if sys_cpu is None else f"{sys_cpu:.2f}",
                    'memory_available_bytes': '' if mem_avail is None else str(mem_avail),
                    'heartbeat_gap_warning': int(gap_warning),
                    'process_returncode': '' if proc.poll() is None else proc.poll(),
                })
                f.flush()
                hb_rows += 1

                rc = proc.poll()
                if rc is not None:
                    break
                last_wall = now
                if cpu is not None:
                    last_cpu = cpu
                time.sleep(args.heartbeat_seconds)

        t_out.join(timeout=5); t_err.join(timeout=5)
        exit_code = proc.returncode

    elapsed = time.perf_counter() - start_wall
    final_cpu = last_valid_cpu
    summary = {
        'job_id': job_id,
        'name': args.name,
        'exit_code': exit_code,
        'elapsed_wall_seconds': elapsed,
        'child_cpu_seconds_final': final_cpu,
        'cpu_wall_ratio_final': None if final_cpu is None or elapsed <= 0 else final_cpu / elapsed,
        'heartbeat_rows': hb_rows,
        'heartbeat_gap_warnings': heartbeat_gap_warnings,
        'max_wall_delta_seconds': max_wall_delta,
        'workdir': str(workdir),
        'command': args.command,
        'run_dir': str(run_dir),
        'summary': str(summary_path),
        'stdout': str(stdout_path),
        'stderr': str(stderr_path),
        'heartbeat': str(heartbeat_path),
        'environment': str(env_path),
        'command_file': str(command_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')

    print("="*72)
    print("Job complete")
    print("="*72)
    print(json.dumps({
        'job_id': job_id,
        'exit_code': exit_code,
        'elapsed_wall_seconds': elapsed,
        'child_cpu_seconds_final': final_cpu,
        'cpu_wall_ratio_final': summary['cpu_wall_ratio_final'],
        'heartbeat_rows': hb_rows,
        'heartbeat_gap_warnings': heartbeat_gap_warnings,
        'max_wall_delta_seconds': max_wall_delta,
        'summary': str(summary_path),
        'stdout': str(stdout_path),
        'stderr': str(stderr_path),
        'heartbeat': str(heartbeat_path),
    }, indent=2))
    return int(exit_code or 0)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='PrimeNet controlled job runner')
    p.add_argument('--name', required=True, help='Short job name')
    p.add_argument('--workdir', default=None, help='Child command working directory')
    p.add_argument('--run-root', default='runs', help='Directory where run evidence folders are stored')
    p.add_argument('--heartbeat-seconds', type=float, default=5.0)
    p.add_argument('--gap-warning-factor', type=float, default=3.0)
    p.add_argument('--no-stay-awake', action='store_true')
    p.add_argument('--quiet', action='store_true', help='Do not echo child stdout/stderr to console')
    p.add_argument('command', nargs=argparse.REMAINDER, help='Command to run after --')
    ns = p.parse_args()
    if ns.command and ns.command[0] == '--':
        ns.command = ns.command[1:]
    return ns


if __name__ == '__main__':
    raise SystemExit(run_job(parse_args()))
