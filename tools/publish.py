"""发一个版本到 GitHub：版本号 +1 → 打包 → 建 Release → 传包 → 改线上那张表。

用法（仓库根）：

    python tools\\publish.py "修了刷油被委托打断"            # 只打包 + 生成本地文件（不联网，先看效果）
    python tools\\publish.py "修了刷油被委托打断" --push      # 真的发：建 Release、传包、提交并推

一次性准备（只做一次）：
  1. 建一个 GitHub 仓库（**个人账号下的普通仓库**，不要挂公司名）
  2. 改 `tools\\publish.json` 里的 `repo`：`"你的名字/mumu-azurlane-helper"`
  3. 申请一个 token（Settings → Developer settings → Personal access tokens，勾 `repo` 或 `Contents: write`）
     设成环境变量：`setx GITHUB_TOKEN 你的一串字符`（设完要重开窗口）
  4. 在仓库 Settings → Pages 里把源设成 `main 分支 / docs 目录`，下载页就有了

产物：
    dist\\shell-<版本>.zip           自动更新用的代码包（几百 KB）
    dist\\MuMu碧蓝助手-<版本>.zip     给第一次装的人（几十 MB）
    docs\\shell.json                线上那张表（壳会读它）
    docs\\index.html                下载页（约等于"一个网址给用户下载"）
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DOCS = ROOT / "docs"
CONFIG = ROOT / "tools" / "publish.json"
INIT = ROOT / "onetap" / "__init__.py"
UPDATE = ROOT / "onetap" / "update.py"
FULL_DIR = DIST / "MuMu碧蓝助手"
PLACEHOLDER = "CHANGE_ME/mumu-azurlane-helper"

sys.path.insert(0, str(ROOT / "tools"))
import build_exe  # noqa: E402
import release    # noqa: E402


def main(argv: list[str]) -> int:
    notes = " ".join(a for a in argv if not a.startswith("--")).strip()
    if not notes:
        raise SystemExit('给一句更新说明：python tools\\publish.py "修了 xx"')
    push = "--push" in argv
    repo, branch = load_config()

    old = build_exe.version()
    new = release.bump(old)
    release.write_version(old, new)
    print(f"版本：{old} → {new}")

    code_zip = build_exe.build_code(new)
    full_zip = ensure_full(new)
    url = f"https://github.com/{repo}/releases/download/v{new}/{code_zip.name}"
    shell = {"version": new, "url": url, "sha256": sha256(code_zip),
             "size": code_zip.stat().st_size, "rollout": 100,
             "min_supported": old, "notes": notes}

    write_index_urls(repo, branch)
    write_shell_json(shell)
    write_page(repo)

    if not push:
        print("\n本地文件都好了（没联网）。确认无误后加 --push 真发。")
        print(json.dumps({"shell": shell}, ensure_ascii=False, indent=2))
        return 0
    if repo == PLACEHOLDER:
        raise SystemExit("tools\\publish.json 里还是占位仓库名，先改成你自己的仓库")
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("没设 GITHUB_TOKEN（见本文件开头的准备步骤）")

    release_id = create_release(repo, new, notes, token)
    upload(repo, release_id, full_zip, token)
    upload(repo, release_id, code_zip, token)
    commit_and_push(repo, new)
    print(f"\n发布完成。下载页：https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/")
    print(f"Release   ：https://github.com/{repo}/releases/tag/v{new}")
    return 0


# ---------------- 打包 ----------------
def ensure_full(version: str) -> Path:
    """整包要是旧的（里面 `app\\onetap` 的版本号对不上）就重新打 —— 否则用户装到的是上一版。"""
    init = FULL_DIR / "app" / "onetap" / "__init__.py"
    fresh = init.exists() and f'__version__ = "{version}"' in init.read_text(encoding="utf-8")
    if not fresh:
        print("dist 里的整包不是这个版本 → 重新打包（约 20 秒）")
        build_exe.build_full(version)
    return pack_full(version)


def pack_full(version: str) -> Path:
    """把 `dist\\MuMu碧蓝助手\\` 压成给新用户下载的整包（里面第一层就是 `MuMu碧蓝助手\\`）。

    **压缩包文件名必须是纯 ASCII**（`mumu-azurlane-helper-<版本>.zip`）：
    GitHub 的附件名会丢掉非 ASCII 字符 —— 2026-10-21 实测 `MuMu碧蓝助手-0.2.2.zip`
    传上去变成了 `MuMu.-0.2.2.zip`（中文全没了，连分隔的 `-` 都跟着变形）。
    里面解出来的目录名照旧是中文，用户看不出区别。
    """
    out = DIST / f"mumu-azurlane-helper-{version}.zip"
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(FULL_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(DIST))
    print(f"整包：{out}  {out.stat().st_size / 1024 / 1024:.1f} MB")
    return out


# ---------------- 本地文件 ----------------
def load_config() -> tuple[str, str]:
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SystemExit(f"缺 {CONFIG}（见本文件开头的准备步骤）")
    return str(data.get("repo") or PLACEHOLDER), str(data.get("branch") or "main")


def write_index_urls(repo: str, branch: str) -> None:
    """把壳读取的地址换成这个仓库的（**raw 优先，jsDelivr 兜底**）。

    顺序为什么是这样（2026-10-21 实测）：jsDelivr 对 `@main` 这种分支引用**会缓存几小时**，
    我们刚改完 `events` 它还在发旧的 → 用户看不到新活动。raw 基本不缓存（几分钟），
    所以 raw 先试；raw 在国内偶尔连不上时再退回 jsDelivr（那时旧一点也能用）。
    """
    text = UPDATE.read_text(encoding="utf-8")
    block = (f'INDEX_URLS: tuple[str, ...] = (\n'
             f'    "https://raw.githubusercontent.com/{repo}/{branch}/docs/shell.json",\n'
             f'    "https://cdn.jsdelivr.net/gh/{repo}@{branch}/docs/shell.json",\n'
             f')\n')
    text = re.sub(r"INDEX_URLS: tuple\[str, \.\.\.\] = \(\n(?:.*\n)*?\)\n", block, text)
    UPDATE.write_text(text, encoding="utf-8")


def write_shell_json(shell: dict) -> None:
    """写线上表：只换 `shell` 段，**其余字段原样保留**。

    `alas`（latest / broken / url / note）和 `events`（当前在开的新活动）是**平时随手改**的，
    不能因为发一次版就被清空 —— 2026-10-21 第一次真发版撞到过，`events` 直接被写没了。
    """
    path = DOCS / "shell.json"
    data: dict = {"notice": "", "rollback": False}
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(old, dict):
            data.update(old)                 # 保住 alas / events / notice / rollback
    except (OSError, json.JSONDecodeError):
        pass
    data["shell"] = shell
    data.setdefault("notice", "")
    data.setdefault("rollback", False)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_page(repo: str) -> None:
    page = DOCS / "index.html"
    if not page.exists():
        return
    text = page.read_text(encoding="utf-8")
    text = re.sub(r"{{REPO}}|[\w.-]+/[\w.-]+(?=/releases)", repo, text)
    page.write_text(text, encoding="utf-8")


# ---------------- GitHub ----------------
def api(path: str, token: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def create_release(repo: str, version: str, notes: str, token: str) -> int:
    tag = f"v{version}"
    try:
        return int(api(f"{repo}/releases",
                       token, {"tag_name": tag, "name": tag,
                               "body": notes})["id"])
    except urllib.error.HTTPError as exc:
        if exc.code != 422:          # 422 = 这个 tag 已经存在 → 用现成的
            raise SystemExit(f"建 Release 失败：{exc.code} {exc.reason}")
    return int(api(f"{repo}/releases/tags/{tag}", token)["id"])


def upload(repo: str, release_id: int, path: Path, token: str) -> None:
    """传一个附件。文件名带版本号，不会和上一版撞名。

    ⚠️ 文件名要 **percent-encode**：`MuMu碧蓝助手-0.2.1.zip` 里有中文，
    直接拼进 URL 会抛 `UnicodeEncodeError: 'ascii' codec can't encode`
    —— 2026-10-21 第一次真发版时撞到，整包里是中文名，必踩。
    """
    name = quote(path.name)
    req = urllib.request.Request(
        f"https://uploads.github.com/repos/{repo}/releases/{release_id}/assets?name={name}",
        data=path.read_bytes(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/zip"},
        method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        print(f"传好了：{path.name}（{resp.status}）")


def commit_and_push(repo: str, version: str) -> None:
    """提交那三个文件并推送。

    **推送用带 token 的地址**（不写进 `.git/config`）：否则 git 会弹"要账号密码"，
    而我们是无人值守跑的 —— 弹出来就等于卡住（和 git fetch 那个坑是同一类）。
    """
    files = ["docs/shell.json", "docs/index.html", "onetap/update.py"]
    subprocess.run(["git", "add", *files], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", f"release v{version}"], cwd=ROOT, check=False)
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    branch = load_config()[1]
    url = (f"https://x-access-token:{token}@github.com/{repo}.git" if token
           else f"https://github.com/{repo}.git")
    done = subprocess.run(["git", "push", url, f"HEAD:refs/heads/{branch}"],
                          cwd=ROOT, check=False)
    if done.returncode != 0:
        print("⚠️ 推送失败：检查仓库名、token 权限（Contents: write），或者先手动 git push 一次")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
