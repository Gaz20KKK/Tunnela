from __future__ import annotations

import argparse
import base64
import getpass
import io
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
import urllib.error
import venv
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT_VERSION = "1.0.0"
DEFAULT_PORT = 7860
RAW_URL = "https://raw.githubusercontent.com/Gaz20KKK/Tunnela/master/tunnela.py"

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
MODELS_DIR = ROOT / "models"
TOOLS_DIR = ROOT / "tools"
TUNNEL_URL_FILE = ROOT / ".tunnel_url"

RST = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
GRAY = "\033[90m"
WHITE = "\033[97m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"

TAG_COLORS = {
    "setup": CYAN,
    "device": CYAN,
    "model": YELLOW,
    "server": GREEN,
    "tunnel": WHITE,
    "error": RED,
    "done": GREEN,
}

TTY = False


def enable_windows_ansi():
    global TTY
    if os.name == "nt":
        try:
            import ctypes

            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
        except Exception:
            pass
    try:
        TTY = sys.stdout.isatty()
    except Exception:
        TTY = False


def term_width() -> int:
    try:
        cols = shutil.get_terminal_size((64, 20)).columns
    except Exception:
        cols = 64
    return max(46, min(cols, 74))


def log(tag: str, msg: str):
    color = TAG_COLORS.get(tag, GRAY)
    if TTY:
        print(f"{DIM}{datetime.now().strftime('%H:%M:%S')}{RST} {color}{BOLD}[{tag:<6}]{RST} {msg}", flush=True)
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag:<6}] {msg}", flush=True)


def log_ok(msg: str):
    log("setup", f"{GREEN}ok     {RST}{msg}" if TTY else f"ok   {msg}")


def log_warn(msg: str):
    log("setup", f"{YELLOW}catatan{RST} {msg}" if TTY else f"note {msg}")


def section(label: str = ""):
    w = term_width()
    if not label:
        line = GRAY + "-" * w + RST
    else:
        pad = max(1, (w - len(label) - 4) // 2)
        core = f"{'-' * pad}  {label}  {'-' * (w - pad - len(label) - 4)}"
        line = GRAY + core + RST
    print(line, flush=True)


def panel(title: str, rows):
    """rows: list of (label, value); ('', text) untuk baris bebas."""
    w = term_width()

    def plain(s):
        return re.sub(r"\033\[[0-9;]*m", "", s)

    def row(text_plain_len, text):
        spaces = max(1, w - 4 - text_plain_len)
        print(f"{GRAY}|{RST} {text}{' ' * spaces}{GRAY}|{RST}")

    border_top = f"{GRAY}+{'-' * (w - 2)}+{RST}"
    print(border_top)
    row(len(title), f"{BOLD}{title}{RST}")
    if rows:
        print(f"{GRAY}|{'-' * (w - 2)}|{RST}")
    for label, value in rows:
        if label == "":
            row(len(plain(value)), value)
        else:
            pv = f"{DIM}{label:<11}{RST} {value}"
            row(len(plain(f"{label:<11} {value}")), pv)
    print(border_top)


SPIN_FRAMES = ["|", "/", "-", "\\"] if os.name == "nt" else ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class spinner:
    def __init__(self, label: str):
        self.label = label
        self.stop_flag = threading.Event()
        self.thread = None

    def __enter__(self):
        if TTY:
            self.thread = threading.Thread(target=self._spin, daemon=True)
            self.thread.start()
        else:
            log("model", self.label + " ...")
        return self

    def _spin(self):
        i = 0
        while not self.stop_flag.wait(0.09):
            frame = SPIN_FRAMES[i % len(SPIN_FRAMES)]
            i += 1
            print(f"\r{CYAN}{frame}{RST} {self.label}", end="", flush=True)

    def update(self, text: str):
        self.label = text

    def __exit__(self, exc_type, exc, tb):
        if self.thread:
            self.stop_flag.set()
            self.thread.join()
            print("\r" + " " * (term_width() - 1) + "\r", end="", flush=True)
        else:
            log("model", f"{self.label} selesai")
        return False


class tty_progress:
    """Progress unduhan: bar penuh di tty, persen saja di notebook."""

    def __init__(self, total: int):
        self.total = total
        self.t_last = time.time()
        self.got = 0
        self.speed_b = 0

    def tick(self, n: int):
        self.got += n
        now = time.time()
        self.speed_b += n
        if now - self.t_last < 0.45 and self.got < self.total:
            return
        speed = self.speed_b / max(now - self.t_last, 1e-6) / 1024 / 1024
        self.t_last = now
        self.speed_b = 0
        pct = min(100.0, self.got * 100.0 / max(self.total, 1))
        if TTY:
            bw = max(8, min(30, term_width() - 36))
            filled = int(bw * pct / 100)
            bar = YELLOW + "=" * filled + RST + "-" * (bw - filled)
            print(f"\r [{bar}] {pct:5.1f}%  {human_size(self.got)} / {human_size(self.total)}  {speed:.1f} MB/s", end="", flush=True)
        else:
            print(f".. {pct:.0f}%  {human_size(self.got)} / {human_size(self.total)}", flush=True)

    def done(self):
        if TTY:
            print("\r" + " " * term_width() + "\r", end="", flush=True)


def hr():
    section()


def banner():
    if TTY:
        sub = "backend image generation lokal dengan Cloudflare Tunnel"
        panel("", [
            ("", f"{BOLD}Tunnela{RST}{DIM}  v{SCRIPT_VERSION}{RST}"),
            ("", DIM + sub + RST),
        ])
        print()
    else:
        print(f"Tunnela v{SCRIPT_VERSION} - backend image generation lokal + Cloudflare Tunnel")
        print("repo: https://github.com/Gaz20KKK/Tunnela")


def human_size(n) -> str:
    n = float(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}".replace(".0 ", " ") if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} PB"


class Stop(Exception):
    pass


def die(msg: str):
    if TTY:
        panel("berhenti", [("", f"{RED}{msg}{RST}")])
    log("error", msg)
    sys.exit(1)


def prompt_input(label: str, default: str = "") -> str:
    suffix = f" {DIM}[{default}]{RST}" if default else ""
    try:
        val = input(f"{CYAN}>{RST} {label}{suffix}: ").strip()
    except EOFError:
        return default
    return val or default


def prompt_secret(label: str) -> str:
    try:
        val = getpass.getpass(f"{CYAN}>{RST} {label}: ") if sys.stdin.isatty() else input(f"{CYAN}>{RST} {label}: ")
        return val.strip()
    except EOFError:
        return ""


def run_quiet(cmd, timeout=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def free_ram_bytes() -> int:
    try:
        if sys.platform == "linux":
            txt = Path("/proc/meminfo").read_text()
            m = re.search(r"MemAvailable:\s+(\d+) kB", txt)
            if m:
                return int(m.group(1)) * 1024
        elif sys.platform == "darwin":
            out = run_quiet(["sysctl", "-n", "hw.memsize"]).stdout.strip()
            return int(out)
        elif os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return int(stat.ullAvailPhys)
    except Exception:
        pass
    return 0


def detect_device() -> dict:
    info = {
        "kind": "cpu",
        "name": f"CPU ({os.cpu_count()} core)",
        "vram_gb": 0.0,
        "index_url": "https://download.pytorch.org/whl/cpu",
        "dtype": "float32",
        "accel": "CPU",
    }
    if sys.platform == "darwin":
        chip = platform.machine()
        mac_ver = tuple(int(x) for x in platform.mac_ver()[0].split("."))
        info["index_url"] = None
        info["dtype"] = "float16"
        if chip == "arm64" and mac_ver >= (12, 3):
            name = run_quiet(["sysctl", "-n", "machdep.cpu.brand_string"]).stdout.strip() or "Apple Silicon"
            info.update(kind="mps", name=name, accel="MPS")
        else:
            info["accel"] = "CPU"
        ram = free_ram_bytes()
        info["ram_gb"] = round(ram / 1024**3, 1)
        return info

    try:
        out = run_quiet(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ],
            timeout=8,
        )
        if out.returncode == 0 and out.stdout.strip():
            first = out.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first.split(",")]
            name = parts[0]
            vram_mb = float(re.sub(r"[^\d]", "", parts[1])) if len(parts) > 1 else 0
            driver = parts[2] if len(parts) > 2 else "?"
            info.update(
                kind="cuda",
                name=name,
                vram_gb=round(vram_mb / 1024, 1),
                index_url=None,
                dtype="float16",
                accel=f"CUDA (driver {driver})",
            )
    except Exception:
        pass

    ram = free_ram_bytes()
    info["ram_gb"] = round(ram / 1024**3, 1)
    return info


def venv_python_path() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python3"


def inside_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == venv_python_path().resolve()
    except Exception:
        return False


def relaunch_in_venv(extra_args):
    exe = venv_python_path()
    os.execv(str(exe), [str(exe), str(Path(__file__).resolve()), *extra_args])


def ensure_virtualenv() -> None:
    t0 = time.time()
    if VENV_DIR.exists() and venv_python_path().exists():
        log("setup", "virtualenv ditemukan di .venv")
        return
    with spinner("membuat virtualenv .venv"):
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(str(VENV_DIR))
    log("setup", f"virtualenv siap dalam {time.time() - t0:.1f}s")


def pip_install(py: Path, packages: list, label: str, index_url: str | None = None):
    cmd = [str(py), "-m", "pip", "install", "--upgrade", "--progress-bar", "off"]
    if index_url:
        cmd += ["--index-url", index_url]
    cmd += packages
    log("setup", f"menginstal {label} (bisa beberapa menit) ...")
    t0 = time.time()
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        log_warn("gagal, mencoba ulang sekali")
        proc = subprocess.run(cmd)
        if proc.returncode != 0:
            die(f"install {label} gagal. Periksa koneksi lalu jalankan lagi.")
    dur = time.time() - t0
    log_ok(f"{label} selesai ({dur / 60:.1f} menit)" if dur > 90 else f"{label} selesai dalam {dur:.0f}s")


STACK_PACKAGES = ["diffusers", "transformers", "accelerate", "safetensors", "huggingface_hub", "Pillow"]


def install_groups(py: Path, dev: dict, need_torch: bool, need_stack: bool):
    torch_args = ["torch", "torchvision"]
    if need_torch:
        if dev["kind"] == "cuda":
            pip_install(py, torch_args, "PyTorch edisi CUDA")
        elif dev["kind"] == "mps":
            pip_install(py, torch_args, "PyTorch untuk macOS")
        else:
            pip_install(py, torch_args, "PyTorch edisi CPU", dev["index_url"])
    if need_stack:
        pip_install(py, STACK_PACKAGES, "stack diffusers")


def bootstrap_deps(dev: dict) -> None:
    py = venv_python_path()
    install_groups(py, dev, True, True)
    relaunch_in_venv(sys.argv[1:])


def detect_runtime() -> str:
    env = os.environ
    if "google.colab" in sys.modules or any(k.startswith("COLAB_") for k in env):
        return "colab"
    if any(k.startswith("KAGGLE") for k in env) or str(ROOT).startswith("/kaggle"):
        return "kaggle"
    if any(k.startswith("GITHUB_") for k in env) or env.get("CODESPACES"):
        return "codespace"
    try:
        import importlib.util

        if importlib.util.find_spec("jupyter_client"):
            return "notebook"
    except Exception:
        pass
    return "local"


def module_present(mod: str, py: Path | None = None) -> bool:
    if py is None:
        import importlib.util

        try:
            return importlib.util.find_spec(mod) is not None
        except Exception:
            return False
    out = run_quiet([str(py), "-c", f"import {mod}"])
    return out.returncode == 0


PRESETS = [
    {
        "key": "fast",
        "aliases": ("fast", "ringan"),
        "name": "sd-turbo",
        "spec": {"source": "hf", "repo_id": "stabilityai/sd-turbo", "filename": None},
        "size": "~2,5 GB",
        "hint": "langkah 1-4, CPU masih nyaman",
    },
    {
        "key": "balanced",
        "aliases": ("balanced", "seimbang"),
        "name": "sdxl-turbo fp16",
        "spec": {
            "source": "hf",
            "repo_id": "stabilityai/sdxl-turbo",
            "filename": "sd_xl_turbo_1.0_fp16.safetensors",
        },
        "size": "~6,9 GB",
        "hint": "langkah 4 @1024px, enak mulai GPU 8GB",
    },
    {
        "key": "best",
        "aliases": ("best", "terbaik"),
        "name": "FLUX.1-schnell",
        "spec": {"source": "hf", "repo_id": "black-forest-labs/FLUX.1-schnell", "filename": None},
        "size": "~23,8 GB",
        "hint": "kualitas terbaik, berat; offload panjang di GPU kecil",
    },
]


def preset_index_from(token: str) -> int | None:
    token = (token or "").strip().lower()
    for i, p in enumerate(PRESETS):
        if token == str(i + 1) or token == p["key"] or token in p["aliases"]:
            return i
    return None


def render_preset_menu(default_idx: int):
    rows = []
    for i, p in enumerate(PRESETS):
        mark = " <- default" if i == default_idx else ""
        rows.append((f"[{i + 1}] {p['name']}", f"{p['size']}, {p['hint']}{mark}"))
    panel("preset model bawaan", rows)
    print(f"{CYAN}>{RST} nomor preset, atau tempel link sendiri {DIM}[{default_idx + 1}]{RST}: ", end="", flush=True)
    try:
        val = input().strip()
    except EOFError:
        val = ""
    print()
    return val


HF_URL_RE = re.compile(r"huggingface\.co/([\w.-]+/[\w.-]+)")
REPO_ID_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
SINGLE_EXT_RE = re.compile(r"\.(safetensors|ckpt)$", re.IGNORECASE)


def parse_model_source(raw: str) -> dict:
    raw = raw.strip().strip('"').strip("'")
    if "huggingface.co" in raw:
        parts = raw.split("huggingface.co/", 1)[1].split("?")[0]
        segs = parts.split("/")
        repo_id = "/".join(segs[:2])
        blob_idx = next((i for i, s in enumerate(segs) if s in ("blob", "resolve")), None)
        subfolder = []
        filename = None
        if blob_idx is not None and len(segs) > blob_idx + 2:
            tail = segs[blob_idx + 2:]
            tail = [t for t in tail if not t.startswith("@")]
            if tail and SINGLE_EXT_RE.search(tail[-1]):
                filename = tail[-1]
                subfolder = tail[:-1]
        return {"source": "hf", "repo_id": repo_id, "filename": filename, "subfolder": "/".join(subfolder)}
    if "civitai.com/api/download/models/" in raw:
        mid = re.search(r"/api/download/models/(\d+)", raw).group(1)
        return {"source": "civitai", "version_id": mid, "url": raw}
    m = re.search(r"civitai\.com/models/(\d+)(?:.*modelVersionId=(\d+))?", raw)
    if m:
        return {"source": "civitai", "version_id": m.group(2) or "", "url": raw, "page_id": m.group(1)}
    if SINGLE_EXT_RE.search(raw.split("?")[0]):
        return {"source": "direct", "url": raw}
    if REPO_ID_RE.match(raw):
        return {"source": "hf", "repo_id": raw, "filename": None, "subfolder": ""}
    return {"source": "unknown"}


def fetch_json(url: str, token: str = "", auth_header: bool = True):
    headers = {"User-Agent": f"Tunnela/{SCRIPT_VERSION}"}
    if token:
        if auth_header:
            headers["Authorization"] = f"Bearer {token}"
        else:
            sep = "&" if "?" in url else "?"
            url = url + f"{sep}token={token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def hf_model_meta(repo_id: str, token: str = "") -> dict:
    from huggingface_hub import HfApi
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError, HfHubHTTPError

    api = HfApi(token=token or None)
    try:
        info = api.model_info(repo_id, files_metadata=True)
    except (GatedRepoError, RepositoryNotFoundError, HfHubHTTPError) as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        raise PermissionError(code or "gated") from e
    files = {}
    has_index = False
    total = 0
    for s in info.siblings:
        name = s.rfilename
        if name == "model_index.json":
            has_index = True
        if SINGLE_EXT_RE.search(name) or name == "model_index.json":
            files[name] = s.size or 0
            if SINGLE_EXT_RE.search(name):
                total += s.size or 0
    cls_name = ""
    if has_index:
        import urllib.request as u

        req = u.Request(f"https://huggingface.co/{repo_id}/resolve/main/model_index.json")
        with u.urlopen(req, timeout=20) as r:
            cls_name = json.loads(r.read().decode()).get("_class_name", "")
    return {"has_index": has_index, "single_files": sorted(files.keys()), "est_bytes": total, "class_hint": cls_name}


def download_hf(spec: dict, token: str) -> Path:
    from huggingface_hub import snapshot_download, hf_hub_download

    MODELS_DIR.mkdir(exist_ok=True)
    meta = hf_model_meta(spec["repo_id"], token)
    log("model", f"{spec['repo_id']} terdeteksi, estimasi unduhan {human_size(meta['est_bytes'])}")
    t0 = time.time()

    def do_single():
        fname = spec["filename"] or next(
            f for f in meta["single_files"] if SINGLE_EXT_RE.search(f)
        )
        path = hf_hub_download(
            repo_id=spec["repo_id"],
            filename=fname,
            token=token or None,
            local_dir=str(MODELS_DIR),
        )
        return Path(path)

    def do_repo():
        ignore = ["*.ckpt", "*.onnx", "*.msgpack", "*.md", "*.png", "*.jpg", "*.jpeg", ".gitattributes"]
        path = snapshot_download(
            repo_id=spec["repo_id"],
            token=token or None,
            ignore_patterns=ignore,
            max_workers=4,
        )
        return Path(path)

    result = (do_repo if meta["has_index"] else do_single)()
    log("model", f"unduhan selesai dalam {(time.time() - t0) / 60:.1f} menit")
    return result


def stream_to_file(req_url: str, dest: Path, token: str = "") -> Path:
    headers = {"User-Agent": f"Tunnela/{SCRIPT_VERSION}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(req_url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise PermissionError(e.code) from e
        raise
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = int(resp.headers.get("Content-Length") or 0)
    got = 0
    speed_t = time.time()
    speed_b = 0
    with open(dest, "wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            got += len(chunk)
            speed_b += len(chunk)
            now = time.time()
            if now - speed_t >= 1.0:
                mbps = speed_b / (now - speed_t) / 1024 / 1024
                speed_t = now
                speed_b = 0
                if total:
                    pct = got * 100 / total
                    eta = (total - got) / max(speed_b or 1, 1)
                    msg = f"{pct:5.1f}%  {human_size(got)} / {human_size(total)}  {mbps:.1f} MB/s"
                    print(f"\r{DIM}[model  ]{RST} {msg:<52}", end="", flush=True)
                else:
                    print(f"\r{DIM}[model  ]{RST} {human_size(got)} terunduh", end="", flush=True)
    print("\r" + " " * 76 + "\r", end="", flush=True)
    log("model", f"tersimpan ke {dest.name}")
    return dest


def civitai_version(version_id: str, page_id: str = "") -> dict:
    try:
        if version_id:
            data = fetch_json(f"https://civitai.com/api/v1/model-versions/{version_id}")
        else:
            page = fetch_json(f"https://civitai.com/api/v1/models/{page_id}")
            versions = page.get("modelVersions") or []
            if not versions:
                raise ValueError("versi tidak ditemukan pada halaman model Civitai")
            data = versions[0]
            version_id = data.get("id", "")
    except urllib.error.HTTPError as e:
        raise PermissionError(e.code) from e
    dl = data.get("downloadUrl")
    if not dl:
        raise ValueError("downloadUrl tidak tersedia untuk versi ini")
    files = data.get("files") or []
    filename = files[0]["name"] if files else f"civitai_{version_id}.safetensors"
    base = (data.get("baseModel") or "").lower()
    if any(k in base for k in ("xl", "illustrious", "pony", "noob")):
        cls_hint = "StableDiffusionXLPipeline"
    elif "flux" in base:
        cls_hint = "FluxPipeline"
    else:
        cls_hint = "StableDiffusionPipeline"
    return {
        "url": dl,
        "filename": filename,
        "base": base,
        "cls_hint": cls_hint,
        "name": data.get("name") or filename,
    }


def choose_pipeline_class(hint: str, path_or_repo: str) -> str:
    blob = f"{hint} {path_or_repo}".lower()
    if "stablevideo" in hint:
        return hint
    if hint in ("StableDiffusionXLPipeline", "FluxPipeline", "StableDiffusion3Pipeline", "StableDiffusionPipeline"):
        return hint
    if any(k in blob for k in ("xl", "illustrious", "pony", "playground")):
        return "StableDiffusionXLPipeline"
    if "flux" in blob:
        return "FluxPipeline"
    return ""


def pick_class_interactive(candidates=("StableDiffusionXLPipeline", "StableDiffusionPipeline")) -> str:
    print(f"{CYAN}>{RST} Jenis model tidak pasti. Pilih arsitektur:")
    for i, c in enumerate(candidates, 1):
        print(f"  {i}. {c}")
    while True:
        choice = prompt_input("nomor", "1")
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]


def load_pipeline(cls_name: str, src: str, is_file: bool, dev: dict):
    import torch
    import diffusers

    dtype = torch.float16 if dev["dtype"] == "float16" else torch.float32
    if cls_name.startswith("Flux"):
        if dev["kind"] == "cuda":
            try:
                if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
                    dtype = torch.bfloat16
            except Exception:
                pass
        elif dev["kind"] == "cpu":
            try:
                if torch.cpu.supports_bf16():
                    dtype = torch.bfloat16
            except Exception:
                pass
    kwargs = {"torch_dtype": dtype}

    def build(klass):
        target = getattr(diffusers, klass)
        kw = dict(kwargs)
        if klass == "StableDiffusionPipeline":
            kw |= {"safety_checker": None, "requires_safety_checker": False}
        if is_file:
            return target.from_single_file(src, **kw)
        return target.from_pretrained(src, **kw)

    with spinner(f"memuat {Path(src).name if is_file else src} sebagai {cls_name}"):
        t0 = time.time()
        try:
            pipe = build(cls_name)
        except Exception as e:
            alt = (
                "StableDiffusionPipeline"
                if cls_name.startswith(("StableDiffusionXL", "Flux"))
                else "StableDiffusionXLPipeline"
            )
            log_warn(f"gagal sebagai {cls_name} ({type(e).__name__}), mencoba {alt}")
            try:
                pipe = build(alt)
            except Exception:
                raise e
    log_ok(f"bobot dimuat dalam {time.time() - t0:.0f}s")

    try:
        params = sum(p.numel() * p.element_size() for p in getattr(pipe, "components", {}).values())
    except Exception:
        params = 0
    needs_offload = False
    if dev["kind"] == "cuda":
        try:
            free_b, total_b = torch.cuda.mem_get_info()
            needs_offload = params * 1.3 > free_b
        except Exception:
            needs_offload = params * 1.3 > dev["vram_gb"] * 1024**3
        if needs_offload and hasattr(pipe, "enable_model_cpu_offload"):
            pipe.enable_model_cpu_offload()
            log("model", f"VRAM pas-pasan ({dev['vram_gb']} GB): pakai CPU offload otomatis")
        else:
            pipe.to("cuda")
    elif dev["kind"] == "mps":
        pipe.to("mps")
        if hasattr(pipe, "enable_attention_slicing"):
            pipe.enable_attention_slicing()
    else:
        pipe.to("cpu")
        if hasattr(pipe, "enable_attention_slicing"):
            pipe.enable_attention_slicing()

    pipe.set_progress_bar_config(disable=True)
    return pipe


SCHEDULERS = {}


def swap_scheduler(pipe, sampler_key: str):
    import diffusers

    if "built" not in SCHEDULERS:
        SCHEDULERS["map"] = {
            "euler_a": lambda: diffusers.EulerAncestralDiscreteScheduler.from_config(pipe.scheduler.config),
            "euler": lambda: diffusers.EulerDiscreteScheduler.from_config(pipe.scheduler.config),
            "dpmpp_2m_karras": lambda: diffusers.DPMSolverMultistepScheduler.from_config(
                pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="dpmsolver++"
            ),
            "ddim": lambda: diffusers.DDIMScheduler.from_config(pipe.scheduler.config),
        }
    factory = SCHEDULERS["map"].get(sampler_key)
    if factory:
        try:
            pipe.scheduler = factory()
        except Exception:
            pass


APP = {"pipe": None, "info": {}, "lock": threading.Lock(), "ready": False}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/health"):
            self._json({"ok": APP["ready"], **APP["info"], "service": "Tunnela Server", "version": SCRIPT_VERSION})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.split("?")[0] != "/api/txt2img":
            self._json({"error": "not found"}, 404)
            return
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 1 << 22)
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            self._json({"error": "body bukan JSON valid"}, 400)
            return
        if not APP["ready"]:
            self._json({"error": "model masih memuat, tunggu sebentar"}, 503)
            return
        try:
            out = generate(payload)
            self._json(out)
        except ValueError as e:
            self._json({"error": str(e)}, 422)
        except RuntimeError as e:
            self._json({"error": str(e)}, 500)
        except Exception as e:
            log("error", f"generate gagal: {type(e).__name__}: {e}")
            self._json({"error": "generate gagal di server"}, 500)


CLAMP = {
    "width": (256, 1536, 512),
    "height": (256, 1536, 512),
    "steps": (1, 80, 20),
    "cfg_scale": (0.0, 30.0, 7.0),
    "batch_size": (1, 4, 1),
    "seed": (-1, 2**31 - 1, -1),
}


def clamp(key: str, value, integer=True):
    lo, hi, dflt = CLAMP[key]
    try:
        v = float(value) if value is not None else float(dflt)
    except (TypeError, ValueError):
        v = float(dflt)
    v = max(lo, min(hi, v))
    if integer:
        v = int(round(v))
        if key in ("width", "height"):
            v = max(lo, min(hi, round(v / 8) * 8))
        return v
    return v


def generate(payload: dict) -> dict:
    import torch

    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt kosong")
    negative = str(payload.get("negative_prompt") or "").strip()
    width = clamp("width", payload.get("width"))
    height = clamp("height", payload.get("height"))
    steps = clamp("steps", payload.get("steps"))
    cfg = clamp("cfg_scale", payload.get("cfg_scale"), integer=False)
    batch = clamp("batch_size", payload.get("batch_size"))
    seed = clamp("seed", payload.get("seed"))
    sampler = str(payload.get("sampler") or "auto").lower()

    pipe = APP["pipe"]
    generator_kind = APP["info"]["device_kind"]
    g_device = "cuda" if generator_kind == "cuda" else ("mps" if generator_kind == "mps" else "cpu")
    base_seed = seed if seed >= 0 else int(torch.randint(0, 2**31 - 1, (1,)).item())
    gen = torch.Generator(device=g_device).manual_seed(base_seed)

    swap_scheduler(pipe, sampler if sampler != "auto" else "")
    is_flux = hasattr(pipe, "transformer")
    kwargs = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": steps,
        "guidance_scale": cfg,
        "num_images_per_prompt": batch,
        "generator": gen,
    }
    if negative and not is_flux:
        kwargs["negative_prompt"] = negative
    elif negative and is_flux:
        log_warn("pipeline FLUX mengabaikan negative prompt")

    log("model", f"request {width}x{height}, {steps} langkah, CFG {cfg:g}, batch {batch}, seed {base_seed}")
    with APP["lock"]:
        t0 = time.time()
        try:
            with torch.no_grad():
                result = pipe(**kwargs)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            raise RuntimeError("CUDA kehabisan memori. Turunkan resolusi atau batch.")
        took = time.time() - t0

    images_out = []
    for i, img in enumerate(result.images):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        images_out.append({"seed": base_seed + i, "data_uri": "data:image/png;base64," + b64})

    meta = APP["info"]["model_name"]
    log("server", f"{batch} gambar selesai dalam {took:.1f}s  ({meta})")
    return {
        "images": images_out,
        "seed_used": base_seed,
        "width": width,
        "height": height,
        "took_s": round(took, 1),
        "model": meta,
    }


CF_VERSION = "latest"
CF_RELEASES = "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def ensure_cloudflared() -> str | None:
    found = shutil.which("cloudflared")
    if found:
        log("tunnel", f"cloudflared dipakai dari PATH ({found})")
        return found
    TOOLS_DIR.mkdir(exist_ok=True)
    system = platform.system().lower()
    machine = platform.machine().lower()
    assets = {
        ("windows", "amd64"): "cloudflared-windows-amd64.exe",
        ("windows", "arm64"): "cloudflared-windows-arm64.exe",
        ("linux", "x86_64"): "cloudflared-linux-amd64",
        ("linux", "aarch64"): "cloudflared-linux-arm64",
        ("darwin", "amd64"): "cloudflared-darwin-amd64.tgz",
        ("darwin", "arm64"): "cloudflared-darwin-arm64.tgz",
    }
    arch = "amd64" if machine in ("amd64", "x86_64") else ("arm64" if machine in ("arm64", "aarch64") else "")
    asset = assets.get((system, arch)) if arch else None
    if not asset:
        log("tunnel", f"tidak ada cloudflared siap unduh untuk {system}/{machine}")
        return None
    tgz = asset.endswith(".tgz")
    if tgz:
        binary = TOOLS_DIR / ("cloudflared.exe" if system == "windows" else "cloudflared")
    else:
        binary = TOOLS_DIR / asset
    if binary.exists() and (not tgz or binary.stat().st_size > 1000):
        verify = run_quiet([str(binary), "--version"])
        if verify.returncode == 0:
            log("tunnel", f"cloudflared cache dipakai dari {binary}")
            return str(binary)
    url = CF_RELEASES + asset
    log("tunnel", f"mengunduh cloudflared ({asset}) ...")
    tmp_dest = TOOLS_DIR / ("dl.tmp" if not tgz else "dl.tar.gz")
    try:
        with urllib.request.urlopen(url, timeout=120) as resp, open(tmp_dest, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = resp.read(1 << 18)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
                if total:
                    print(f"\r{DIM}[tunnel ]{RST} {got * 100 // total:>3}%  {human_size(got)}", end="", flush=True)
        print("\r" + " " * 60 + "\r", end="", flush=True)
        if tgz:
            with tarfile.open(tmp_dest) as tf:
                member = next(m for m in tf.getmembers() if m.name.endswith("cloudflared"))
                member.name = binary.name
                tf.extract(member, TOOLS_DIR)
        else:
            shutil.move(str(tmp_dest), binary)
    except Exception as e:
        log("tunnel", f"{YELLOW}unduh cloudflared gagal: {e}{RST}")
        return None
    finally:
        if tmp_dest.exists() and not binary.exists():
            shutil.rmtree(tmp_dest, ignore_errors=True)
    if os.name != "nt":
        os.chmod(binary, 0o755)
    verify = run_quiet([str(binary), "--version"])
    if verify.returncode != 0:
        log("tunnel", f"{YELLOW}binary cloudflared tidak bisa jalan di mesin ini{RST}")
        return None
    log("tunnel", f"cloudflared siap ({binary.name})")
    return str(binary)


class Tunnel:
    URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

    def __init__(self, binary: str, port: int):
        self.proc = None
        self.url = None
        self.binary = binary
        self.port = port
        self.reader_thread = None

    def start(self, timeout: float = 60.0) -> str | None:
        cmd = [
            self.binary,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{self.port}",
            "--no-autoupdate",
        ]
        log("tunnel", "menyalakan quick tunnel Cloudflare ...")
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except OSError as e:
            log("tunnel", f"gagal menjalankan cloudflared: {e}")
            return None
        self.reader_thread = threading.Thread(target=self._read_stderr, daemon=True)
        self.reader_thread.start()
        t0 = time.time()
        dot_next = t0 + 4
        while self.url is None and time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                log("tunnel", f"{YELLOW}cloudflared keluar lebih awal (kode {self.proc.returncode}){RST}")
                return None
            if time.time() >= dot_next and self.url is None:
                dot_next += 4
            time.sleep(0.25)
        if self.url:
            TUNNEL_URL_FILE.write_text(self.url, encoding="utf-8")
            return self.url
        log("tunnel", f"{YELLOW}belum ada URL setelah {int(timeout)}s, tunnel tetap dicoba di belakang{RST}")
        return None

    def _read_stderr(self):
        try:
            for line in self.proc.stderr:
                if self.url:
                    continue
                m = Tunnel.URL_RE.search(line)
                if m:
                    self.url = m.group(0)
                elif re.search(r"(failed|error|unauthorized)", line, re.I):
                    trimmed = line.strip()
                    if trimmed:
                        log("tunnel", f"{GRAY}{trimmed[:150]}{RST}")
        except Exception:
            pass

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(5)
                    return
                except subprocess.TimeoutExpired:
                    pass
                self.proc.kill()
                self.proc.wait(8)
            except Exception:
                pass


def make_httpd(port: int) -> ThreadingHTTPServer:
    ThreadingHTTPServer.daemon_threads = True
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    return httpd


CLEANUPS = []


def register_cleanup(fn):
    CLEANUPS.append(fn)


def shutdown_all(httpd=None):
    for fn in CLEANUPS:
        try:
            fn()
        except Exception:
            pass
    if httpd:
        thread = threading.Thread(target=httpd.shutdown, daemon=True)
        thread.start()


def warmup(dev: dict):
    if dev["kind"] == "cpu":
        log("model", "lewati pemanasan di CPU supaya tidak menambah waktu tunggu")
        return
    try:
        generate({"prompt": "a small red circle on white background", "width": 320, "height": 320, "steps": 2, "cfg_scale": 1.0, "batch_size": 1})
        log("model", "pemanasan selesai, request pertama akan lebih cepat")
    except Exception as e:
        log("model", f"{YELLOW}pemanasan dilewati: {type(e).__name__}{RST}")


def acquire_model(args, dev: dict) -> tuple[str, str]:
    local = None
    if args.local and Path(args.local).exists():
        local = Path(args.local)

    if local is None and args.model in (None, "") and args.preset in (None, ""):
        newest = None
        if MODELS_DIR.exists():
            cands = [p for p in MODELS_DIR.glob("*") if SINGLE_EXT_RE.search(p.name)]
            if cands:
                newest = max(cands, key=lambda p: p.stat().st_mtime)
        if newest:
            if TTY:
                answer = prompt_input(f"pakai model lokal {newest.name}? (enter = ya / ketik link)", "y")
                if answer.lower() in ("y", "yes", "ya", ""):
                    local = newest
                else:
                    args.model = answer
            else:
                log("model", f"pakai model lokal tersimpan: {newest.name}")
                local = newest

    if local is None:
        preset_idx = preset_index_from(args.preset or "")
        if args.model in (None, ""):
            if preset_idx is None:
                auto_default = 1 if (dev["kind"] == "cuda" and dev["vram_gb"] >= 8) or dev["kind"] == "mps" else 0
                if TTY:
                    raw = render_preset_menu(auto_default)
                    chosen = preset_index_from(raw)
                    if chosen is None and raw:
                        args.model = raw
                    elif raw == "":
                        chosen = auto_default
                    if chosen is not None:
                        args.preset = PRESETS[chosen]["key"]
                else:
                    auto_msg = f"tanpa input interaktif: dipilih preset {PRESETS[auto_default]['name']}"
                    log("model", auto_msg + ". Pakai --preset fast|balanced|best atau --model LINK untuk mengganti.")
                    args.preset = PRESETS[auto_default]["key"]
            else:
                args.preset = PRESETS[preset_idx]["key"]

    if local:
        cls_guess = (
            "StableDiffusionXLPipeline"
            if any(k in local.stem.lower() for k in ("xl", "illustrious", "pony"))
            else ""
        )
        return cls_guess, str(local), True

    if args.model in (None, "") and args.preset not in (None, ""):
        pinfo = next(p for p in PRESETS if p["key"] == (args.preset or ""))
        spec = dict(pinfo["spec"])
        log("model", f"preset {pinfo['key']}: {pinfo['name']} ({pinfo['size']})")
    else:
        spec = parse_model_source(args.model)
    if spec["source"] == "unknown":
        die(f"Tidak bisa membaca alamat model: {args.model}")

    while spec["source"] == "hf":
        token = os.environ.get("HF_TOKEN", "") or getattr(acquire_model, "_hf_token", "")
        try:
            meta = hf_model_meta(spec["repo_id"], token)
            break
        except PermissionError:
            log("model", "repo ini gated/private. Token akses HuggingFace dibutuhkan.")
            log("model", "buat token di https://huggingface.co/settings/tokens (scope: Read)")
            tok = prompt_secret("tempel token (input tak terlihat)")
            if not tok:
                die("tanpa token, unduhan berhenti.")
            acquire_model._hf_token = tok
            token = tok
        except Exception as e:
            die(f"cek model HuggingFace gagal: {type(e).__name__}. Pastikan repo benar dan internet jalan.")

    if spec["source"] == "hf":
        cls_name = choose_pipeline_class(meta["class_hint"], spec["repo_id"])
        if spec["filename"]:
            cls_name = choose_pipeline_class("", spec["filename"]) or cls_name
        path = download_hf(spec, token)
        if not cls_name:
            idx = path / "model_index.json"
            if idx.exists():
                cls_name = json.loads(idx.read_text(encoding="utf-8")).get("_class_name", "")
        return cls_name, str(path), Path(path).is_file()

    log("model", "sumber Civitai memerlukan API key untuk mengunduh file apa pun")
    log("model", "ambil key gratis di https://civitai.com/user/account")
    token = prompt_secret("API key Civitai (boleh dikosongkan kalau publik)")

    ver = None
    try:
        ver = civitai_version(spec.get("version_id", ""), spec.get("page_id", ""))
    except PermissionError:
        if not token:
            die("Unduhan Civitai butuh API key. Jalankan lagi lalu isi key saat ditanya.")
    except Exception as e:
        die(f"lookup versi Civitai gagal: {e}")

    dest = MODELS_DIR / ver["filename"]
    if dest.exists() and dest.stat().st_size > 10_000_000:
        log("model", f"file {dest.name} sudah ada, lewati unduhan")
    else:
        attempt = 0
        while True:
            try:
                stream_to_file(ver["url"], dest, token)
                break
            except PermissionError:
                attempt += 1
                if attempt > 1 or token:
                    die("tetap ditolak (401/403). Cek key Civitai atau lisensi file.")
                log("model", f"{YELLOW}ditolak tanpa token. Masukkan API key.{RST}")
                token = prompt_secret("API key Civitai")

    log("model", f"base model Civitai: {ver['base'] or 'tidak tercantum'}")
    cls_name = ver["cls_hint"] if "flux" not in ver["base"] else "FluxPipeline"
    return cls_name, str(dest), True


def main():
    enable_windows_ansi()
    epilog = (
        "contoh:\n"
        "  python tunnela.py                          menu preset interaktif\n"
        "  python tunnela.py --preset balanced        langsung pakai sdxl-turbo\n"
        "  python tunnela.py --model civitai.com/api/download/models/123\n"
        "  python tunnela.py --no-tunnel              server lokal saja"
    )
    parser = argparse.ArgumentParser(prog="tunnela", epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="", help="link HuggingFace/Civitai/file lokal")
    parser.add_argument("--preset", default="", help="fast | balanced | best")
    parser.add_argument("--local", default="", help="path file model lokal (.safetensors/.ckpt)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--fresh-venv", action="store_true", help="paksa virtualenv baru meski environment sudah cukup")
    parser.add_argument("--no-tunnel", action="store_true", help="jangan nyalakan cloudflared")
    parser.add_argument("--update", action="store_true", help="perbarui tunnela.py dari repo")
    gp = parser.parse_args()

    if gp.update:
        update_self()
        return

    banner()
    if sys.version_info < (3, 9):
        die("Python 3.9+ dibutuhkan.")

    runtime = detect_runtime()
    dev = detect_device()
    mode_label = {"cuda": "GPU NVIDIA", "mps": "GPU Apple", "cpu": "CPU saja"}[dev["kind"]]
    vram_txt = f"{dev['vram_gb']} GB" if dev["vram_gb"] else f"RAM bebas {dev.get('ram_gb', '?')} GB"
    panel("device", [
        ("tipe", f"{mode_label}, {dev['name']}"),
        ("memori", vram_txt),
        ("akselerator", dev["accel"]),
        ("runtime", {"colab": "Google Colab", "kaggle": "Kaggle notebook", "codespace": "GitHub Codespace", "notebook": "Jupyter", "local": "terminal"}[runtime]),
    ])

    stack_missing = any(not module_present(m) for m in ("diffusers", "transformers", "accelerate", "safetensors", "huggingface_hub", "PIL"))
    torch_missing = not module_present("torch")

    use_shared_env = (not gp.fresh_venv) and (runtime != "local" or (not stack_missing and not torch_missing))
    if use_shared_env:
        log("setup", f"memakai Python aktif ({sys.executable}) tanpa venv")
        if torch_missing or stack_missing:
            section("instalasi library (sekali saja)")
            install_groups(Path(sys.executable), dev, torch_missing, stack_missing)
    else:
        if not inside_venv():
            log("setup", "menyiapkan lingkungan Python terisolasi (.venv) ...")
            ensure_virtualenv()
            relaunch_in_venv(sys.argv[1:])
        py = venv_python_path()
        deps_ok = all(module_present(m, py) for m in ("diffusers", "transformers", "accelerate", "huggingface_hub", "PIL"))
        torch_ok = module_present("torch", py)
        if not deps_ok or not torch_ok:
            section("instalasi library (sekali saja)")
            bootstrap_deps(dev)

    MODELS_DIR.mkdir(exist_ok=True)

    cls_name, src, is_file = acquire_model(gp, dev)
    if not cls_name and is_file:
        stem = Path(src).stem.lower()
        if any(k in stem for k in ("xl", "illustrious", "pony", "noob", "playground")):
            cls_name = "StableDiffusionXLPipeline"
        elif "flux" in stem:
            cls_name = "FluxPipeline"
    if not cls_name:
        cls_name = pick_class_interactive() if TTY else "StableDiffusionPipeline"
    section("memuat model")
    pipe = load_pipeline(cls_name, src, is_file, dev)
    display_name = Path(src).name if is_file else cls_name.replace("Pipeline", "").replace("StableDiffusionXL", "SDXL-").replace("StableDiffusion", "SD-")
    APP["pipe"] = pipe
    APP["info"] = {
        "model": display_name,
        "model_name": display_name,
        "pipeline": cls_name,
        "device_kind": dev["kind"],
        "device": dev["name"],
        "dtype": dev["dtype"],
        "runtime": runtime,
        "port": gp.port,
    }
    APP["ready"] = True
    log_ok(f"model siap: {display_name}")

    warmup(dev)

    port = gp.port
    if port_free(port):
        chosen_port = port
    else:
        log_warn(f"port {port} dipakai proses lain, cari port bebas")
        chosen_port = find_free_port(port + 1)
    httpd = make_httpd(chosen_port)
    thr = threading.Thread(target=httpd.serve_forever, daemon=True)
    thr.start()
    log("server", f"http://127.0.0.1:{chosen_port} hidup (POST /api/txt2img)")

    if not gp.no_tunnel:
        cf_binary = ensure_cloudflared()
        tunnel = Tunnel(cf_binary, chosen_port) if cf_binary else None
        if tunnel:
            register_cleanup(tunnel.stop)
            public_url = tunnel.start()
        else:
            public_url = None
            log("tunnel", "lanjut tanpa tunnel publik; API hanya bisa diakses via LAN.")
    else:
        public_url = None

    register_cleanup(lambda: TUNNEL_URL_FILE.unlink(missing_ok=True))

    section("siap generate")
    rows = [
        ("model", f"{display_name} ({cls_name})"),
        ("device", f"{mode_label}, {dev['name']}"),
        ("endpoint", f"http://127.0.0.1:{chosen_port}/api/txt2img"),
    ]
    if public_url:
        rows.insert(0, ("tunnel", f"{CYAN}{BOLD}{public_url}{RST}"))
    else:
        rows.insert(0, ("tunnel", f"{YELLOW}tidak aktif{RST}" if not gp.no_tunnel else "dimatikan via --no-tunnel"))
    panel("Tunnela berjalan", rows)
    print()
    print(f"{DIM}Paste link tunnel ke halaman Connect di web Tunnela, lalu generate.{RST}")
    print(f"{DIM}Matikan semua dengan Ctrl+C.{RST}")
    print("Menunggu request ...\n", flush=True)

    stop_event = threading.Event()

    def signal_handler(sig, frame):
        print()
        log("done", "Ctrl+C diterima, mematikan proses ...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        while not stop_event.is_set():
            stop_event.wait(3600)
    finally:
        for fn in CLEANUPS:
            fn()
        httpd.shutdown()
        log("done", "server dan tunnel mati. Sampai jumpa.")


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def find_free_port(start: int) -> int:
    for candidate in range(start, start + 25):
        if port_free(candidate):
            return candidate
    die("tidak menemukan port bebas")


def update_self():
    banner()
    log("setup", "mengunduh tunnela.py terbaru dari GitHub ...")
    dest = Path(__file__).resolve()
    tmp = dest.with_suffix(".tmp")
    try:
        urllib.request.urlretrieve(RAW_URL, tmp)
        os.replace(tmp, dest)
        log("setup", f"{dest.name} diperbarui")
    except Exception as e:
        log("error", f"update gagal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
