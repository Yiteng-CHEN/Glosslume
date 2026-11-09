"""Regenerate src/glosslume/localmodel/catalog.json from Hugging Face, GitHub and PyPI (read-only: no model or binary is downloaded).

Run it when you want newer pins:  python tools/refresh_catalog.py
The catalog pins everything the app downloads: the llama.cpp build with its SHA256, and for every model the exact
repository revision plus size and SHA256 of each file. The app refuses a download whose hash differs.
Edit MODELS below to change what the settings page offers.
"""
from __future__ import annotations

import datetime
import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "glosslume" / "localmodel" / "catalog.json"

# id, display name, minimum RAM (GB) for a comfortable run, GGUF (repo, file), MLX repo, one-line notes
MODELS = [
    ("qwen3.5-4b", "Qwen3.5 4B", 8, ("unsloth/Qwen3.5-4B-GGUF", "Qwen3.5-4B-Q4_K_M.gguf"), "mlx-community/Qwen3.5-4B-MLX-4bit",
     {"zh": "最轻量，8 GB 内存的电脑也能跑；中英文够用，复杂句子的解析会弱一些。", "en": "Lightest option; runs on 8 GB machines. Fine for Chinese/English, weaker on complex sentences."}),
    ("qwen3.5-9b", "Qwen3.5 9B", 16, ("unsloth/Qwen3.5-9B-GGUF", "Qwen3.5-9B-Q4_K_M.gguf"), "mlx-community/Qwen3.5-9B-MLX-4bit",
     {"zh": "推荐的默认选择：速度和质量比较均衡，中日韩与英语都不错。", "en": "Recommended default: a good balance of speed and quality; strong on CJK and English."}),
    ("gemma-4-e4b", "Gemma 4 E4B", 16, ("unsloth/gemma-4-E4B-it-GGUF", "gemma-4-E4B-it-Q4_K_M.gguf"), "mlx-community/gemma-4-e4b-it-4bit",
     {"zh": "体积小，欧洲语言（法德西意等）表现好。", "en": "Small, good with European languages."}),
    ("gemma-4-12b", "Gemma 4 12B", 24, ("unsloth/gemma-4-12b-it-GGUF", "gemma-4-12b-it-Q4_K_M.gguf"), "mlx-community/gemma-4-12B-it-4bit",
     {"zh": "质量明显好于小模型，适合 24 GB 以上内存。", "en": "Clearly better than the small models; for 24 GB and up."}),
    ("qwen3-14b", "Qwen3 14B", 24, ("Qwen/Qwen3-14B-GGUF", "Qwen3-14B-Q4_K_M.gguf"), "mlx-community/Qwen3-14B-4bit",
     {"zh": "中日韩语言评价高，适合学术文章；24 GB 以上内存。", "en": "Well regarded for CJK languages and academic text; 24 GB and up."}),
    ("gemma-4-26b-a4b", "Gemma 4 26B-A4B", 32, ("unsloth/gemma-4-26B-A4B-it-GGUF", "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"), "mlx-community/gemma-4-26b-a4b-it-4bit",
     {"zh": "混合专家模型：质量接近大模型，生成速度却接近小模型；32 GB 以上内存。", "en": "Mixture-of-experts: near large-model quality at small-model speed; 32 GB and up."}),
    ("qwen3-32b", "Qwen3 32B", 48, ("Qwen/Qwen3-32B-GGUF", "Qwen3-32B-Q4_K_M.gguf"), "mlx-community/Qwen3-32B-4bit",
     {"zh": "质量最高、也最慢；48 GB 以上内存。", "en": "Highest quality and slowest; 48 GB and up."}),
]
RECOMMENDED = "qwen3.5-9b"
# catalog key -> substring that identifies the llama.cpp release asset
LLAMA_ASSETS = {"darwin-arm64": "bin-macos-arm64.tar.gz", "darwin-x86_64": "bin-macos-x64.tar.gz",
                "linux-x86_64": "bin-ubuntu-x64.tar.gz", "linux-aarch64": "bin-ubuntu-arm64.tar.gz",
                "windows-x86_64": "bin-win-cpu-x64.zip", "windows-arm64": "bin-win-cpu-arm64.zip"}


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "glosslume-refresh-catalog"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def files_of(repo: str, rev: str) -> list[dict]:
    out = []
    for f in get(f"https://huggingface.co/api/models/{repo}/tree/{rev}?recursive=1"):
        if f["type"] == "file":
            lfs = f.get("lfs") or {}
            out.append({"path": f["path"], "size": lfs.get("size", f["size"]), "sha256": lfs.get("oid")})
    return out


def main() -> None:
    models = []
    for mid, name, ram, (grepo, gfile), mrepo, note in MODELS:
        gmeta, mmeta = get(f"https://huggingface.co/api/models/{grepo}"), get(f"https://huggingface.co/api/models/{mrepo}")
        gf = next(f for f in files_of(grepo, gmeta["sha"]) if f["path"] == gfile)
        models.append({
            "id": mid, "name": name, "ram_gb": ram, "note": note,
            "gguf": {"repo": grepo, "rev": gmeta["sha"], "file": gfile, "size": gf["size"], "sha256": gf["sha256"],
                     "license": (gmeta.get("cardData") or {}).get("license") or ""},
            "mlx": {"repo": mrepo, "rev": mmeta["sha"], "files": files_of(mrepo, mmeta["sha"]),
                    "license": (mmeta.get("cardData") or {}).get("license") or ""},
        })
    rel = next(r for r in get("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=8") if len(r["assets"]) > 3)
    assets = {}
    for key, tail in LLAMA_ASSETS.items():
        a = next(x for x in rel["assets"] if x["name"].endswith(tail))
        # api_url is the fallback: github.com/.../releases/download/... is blocked or flaky on some networks while the API address works
        assets[key] = {"name": a["name"], "url": a["browser_download_url"], "api_url": a["url"], "size": a["size"],
                       "sha256": (a.get("digest") or "").removeprefix("sha256:")}
        assert len(assets[key]["sha256"]) == 64, f"no sha256 published for {a['name']}"
    mlx_lm = get("https://pypi.org/pypi/mlx-lm/json")["info"]["version"]
    data = {"generated": datetime.date.today().isoformat(), "recommended": RECOMMENDED,
            "llama_cpp": {"tag": rel["tag_name"], "assets": assets}, "mlx_lm": {"version": mlx_lm}, "models": models}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(models)} models, llama.cpp {rel['tag_name']}, mlx-lm {mlx_lm})")


if __name__ == "__main__":
    main()
