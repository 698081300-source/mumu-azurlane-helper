"""看一眼 Alas 上游更新了没、新活动目录叫什么。

用法（仓库根）：

    python tools\\watch_alas.py            # 只看，打印结论
    python tools\\watch_alas.py --json     # 机器可读（给别的脚本用）

为什么要有它：
  游戏出了新活动 → 新活动图的数据要等 Alas 上游加上 → 才能进线上表的 `events`
  （壳靠它决定"要不要提示用户更新 Alas"）。**没有这个工具就只能靠人隔一会儿去翻仓库。**

只读远端，不下载、不改用户机器上的 Alas。
数据来源是 GitHub API（用环境变量里的 GITHUB_TOKEN，没有就用匿名，每小时 60 次也够）。
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL_JSON = ROOT / "docs" / "shell.json"
REPO = "LmeSzinc/AzurLaneAutoScript"
API = f"https://api.github.com/repos/{REPO}"


def _token() -> str:
    """优先环境变量；没有就读 Windows 用户环境变量（`setx` 写的那个）。"""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return str(winreg.QueryValueEx(key, "GITHUB_TOKEN")[0]).strip()
    except (ImportError, OSError):
        return ""


def api(path: str) -> object:
    req = urllib.request.Request(f"{API}{path}", headers={
        "User-Agent": "mumu-azurlane-helper-watch",
        "Accept": "application/vnd.github+json",
        **({"Authorization": f"Bearer {_token()}"} if _token() else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _bj(iso: str) -> str:
    """UTC 的 ISO 时间 → 北京时间 `YYYY-MM-DD`。

    **不能用"本机时区"**：GitHub Actions 跑在 UTC 上，用 `astimezone()` 会得到
    前一天（2026-10-19T20:38Z 其实已经是北京 10-20 凌晨），看着像"上游没更新"。
    """
    import datetime
    if not iso:
        return ""
    try:
        moment = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso[:10]
    return moment.astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d")


def _now_bj() -> str:
    import datetime
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")


def latest_commit() -> tuple[str, str, str]:
    """`(短 sha, 北京时间日期, 标题)` —— 只读一次，不翻历史。"""
    data = api("/commits?sha=master&per_page=1")
    if not isinstance(data, list) or not data:
        return "", "", ""
    item = data[0]
    raw = str(item.get("commit", {}).get("author", {}).get("date", ""))
    return (str(item.get("sha", ""))[:7], _bj(raw),
            str(item.get("commit", {}).get("message", "")).splitlines()[0][:60])


def event_folders() -> list[str]:
    """上游 `campaign/` 下的活动目录（新→旧）。"""
    data = api("/contents/campaign?ref=master")
    names = [str(x.get("name") or "") for x in data] if isinstance(data, list) else []
    return sorted((n for n in names if n.startswith("event_")), reverse=True)


def local_newest(root: Path) -> list[str]:
    """本机 Alas 已经有哪几个活动（给"要不要更新"做对照）。"""
    try:
        return sorted((p.name for p in (root / "campaign").iterdir()
                       if p.is_dir() and p.name.startswith("event_")), reverse=True)
    except OSError:
        return []


def recent(folders: list[str], days: int = 45) -> list[str]:
    """只看最近 `days` 天的活动目录 —— 更早的都关掉了，列出来只会干扰判断。"""
    import datetime
    today = datetime.date.today()
    out = []
    for name in folders:
        found = re.search(r"event_(\d{4})(\d{2})(\d{2})", name)
        if not found:
            continue
        try:
            started = datetime.date(int(found.group(1)), int(found.group(2)), int(found.group(3)))
        except ValueError:
            continue
        if (today - started).days <= days:
            out.append(name)
    return sorted(out, reverse=True)


GROUPS = (
    ("campaign/", "关卡数据（新活动/新图）"),
    ("module/campaign/", "关卡流程（三星判定相关）"),
    ("module/map/", "地图识别"),
    ("module/combat/", "战斗"),
    ("module/config/", "配置字段（我们写的 7 个值）"),
    ("module/handler/", "主界面/任务调度"),
    ("module/webui/", "Alas 自己的界面与更新器"),
    ("module/device/", "连模拟器"),
    ("module/island_handler/", "大世界·岛屿（与我们无关）"),
    ("deploy/", "部署脚本"),
    ("tests/", "测试（与我们无关）"),
)


def changes(count: int = 5) -> None:
    """最近 N 次提交，各自改了哪些文件 —— 并标出**哪一类会影响我们**。"""
    data = api(f"/commits?sha=master&per_page={count}")
    if not isinstance(data, list):
        return
    for item in data:
        sha = str(item.get("sha", ""))
        title = str(item.get("commit", {}).get("message", "")).splitlines()[0][:70]
        date = str(item.get("commit", {}).get("author", {}).get("date", ""))[:16]
        detail = api(f"/commits/{sha}")
        files = [str(f.get("filename") or "") for f in (detail.get("files") or [])]
        print(f"\n{sha[:7]}  {date}  {title}")
        if not files:
            print("   （合并提交，没带文件列表）")
            continue
        print(f"   改了 {len(files)} 个文件")
        for prefix, label in GROUPS:
            hit = [f for f in files if f.startswith(prefix)]
            if hit:
                sample = "、".join(hit[:3]) + ("…" if len(hit) > 3 else "")
                print(f"   · {label}：{sample}")
        other = [f for f in files if not any(f.startswith(p) for p, _ in GROUPS)]
        if other:
            print(f"   · 其它：{'、'.join(other[:3])}" + ("…" if len(other) > 3 else ""))


STATE = ROOT / "docs" / "watch.json"
REPORT = ROOT / "docs" / "alas-watch.md"
RELEVANT = ("module/campaign/", "module/map/", "module/config/",
            "module/handler/", "module/combat/", "module/device/",
            "campaign/", "alas.py")


def _today() -> str:
    import datetime
    return datetime.date.today().isoformat()


def _load_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compare(base: str, head: str) -> tuple[int, list[str], list[str]]:
    """`base...head` 之间改了哪些文件、有哪些提交。"""
    try:
        data = api(f"/compare/{base}...{head}")
    except OSError:
        return 0, [], []
    commits = [str(c.get("commit", {}).get("message", "")).splitlines()[0][:70]
               for c in (data.get("commits") or [])]
    files = [str(f.get("filename") or "") for f in (data.get("files") or [])]
    return len(commits), files, commits


def _grouped(files: list[str]) -> list[str]:
    """把文件按"对我们有没有影响"分组，返回给人看的几行。"""
    lines = []
    for prefix, label in GROUPS:
        hit = [f for f in files if f.startswith(prefix)]
        if hit:
            sample = "、".join(hit[:3]) + ("…" if len(hit) > 3 else "")
            lines.append(f"- {label}：{sample}")
    other = [f for f in files if not any(f.startswith(p) for p, _ in GROUPS)]
    if other:
        lines.append(f"- 其它：{'、'.join(other[:3])}" + ("…" if len(other) > 3 else ""))
    return lines


def _event_files(folder: str) -> int:
    """这个活动目录里到底有没有关卡文件（有 = 玩家真能刷了）。"""
    try:
        data = api(f"/contents/campaign/{folder}?ref=master")
    except OSError:
        return 0
    if not isinstance(data, list):
        return 0
    return sum(1 for x in data if str(x.get("name") or "").endswith(".py"))


def _ci(force: bool = False) -> int:
    """GitHub Actions 入口：决定这次要不要报告，要的话写进 `docs/alas-watch.md`。

    两条节奏（用户 2026-10-22 定）：
      - **平时**：每天一次（第一次跑到就写，之后 2 小时一次的都不写）
      - **大节点**：每 2 小时查一次，**新活动图一出现就自动退回每天的节奏**
    小改动（改岛屿商店那种）照常记进文件，但用户侧没有任何动作。
    """
    import datetime
    state = _load_state()
    sha, date, title = latest_commit()
    if not sha:
        print("读不到上游（API 失败），这次跳过")
        return 0

    open_now = recent(event_folders(), 45)
    known = set(state.get("known_events") or [])
    new_events = [e for e in open_now if e not in known]
    hot = bool(state.get("hot"))
    sha_changed = sha != (state.get("last_sha") or "")
    daily_due = _today() != (state.get("last_daily") or "")

    if not state.get("last_sha"):
        # 第一次跑：只记基线。否则会把几个月前的活动当成"新活动"报上来。
        state.update({"last_sha": sha, "known_events": open_now, "last_daily": _today()})
        _save_state(state)
        print("首次运行：已建立基线，下次开始对比")
        return 0

    if hot:
        report = bool(new_events or sha_changed)
    else:
        report = daily_due
    if force:
        report = True                 # 手动触发时的"发一条给我看看"
    if not report:
        return 0

    lines = [f"## {_now_bj()}（北京时间）", ""]
    old = state.get("last_sha") or ""
    if sha_changed:
        lines.append(f"上游：{old[:7] or '（首次）'} → **{sha}**（{date}）{title}")
    else:
        lines.append(f"上游没新提交：{sha}（{date}）")

    related = False
    if sha_changed and old:
        count, files, messages = compare(old, sha)
        if files:
            lines += ["", f"**这次动了什么**（{count or 1} 个提交）", ""]
            if messages:
                lines += [f"- `{m}`" for m in messages[:5]]
            lines += _grouped(files)
            related = any(f.startswith(RELEVANT) for f in files)
        else:
            lines += ["", "（合并提交，没拿到文件清单）"]

    ready = []
    for folder in new_events:
        count = _event_files(folder)
        if count:
            ready.append(folder)
    if new_events:
        lines += ["", "**新活动**"]
        for folder in new_events:
            lines.append(f"- {folder}：" + ("✅ 关卡文件已就绪" if folder in ready
                                            else "目录有了，关卡文件还没齐"))
        if ready:
            lines.append("")
            lines.append("→ **可以写进线上表 `events` 了**："
                         + json.dumps({"events": [{"id": f, "name": _guess_name(f)}
                                                  for f in new_events]}, ensure_ascii=False))
            state["hot"] = False
    elif hot:
        lines += ["", "新活动图**还没出现** —— 继续每 2 小时查"]

    if sha_changed:
        lines += ["", f"**跟我们有关吗**：{'⚠️ 有关，建议看一眼' if related else '无关（改的是别的东西）'}"]

    state["last_sha"] = sha
    state["known_events"] = open_now
    if not hot:
        state["last_daily"] = _today()
    _save_state(state)

    text = "\n".join(lines).rstrip() + "\n"
    print(text)
    _prepend_report(text)
    _notify(text)
    return 0


def _post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"User-Agent": "mumu-azurlane-helper-watch",
                 "Accept": "application/vnd.github+json",
                 "Authorization": f"Bearer {_token()}",
                 "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _notify(text: str) -> None:
    """把报告写进那个固定的 Issue 里，并 @ 仓库 owner —— **邮件就是靠这一下发出去的**。

    为什么不用"Issue 里发新帖"：一天一条新 Issue 会把列表刷满；固定一个 Issue、
    每次加一条评论，历史都在一处，"取消订阅"也只按一次。
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = _token()
    if not (repo and token):
        print("（没有 GITHUB_REPOSITORY / token，跳过通知）")
        return
    owner = repo.split("/")[0]
    body = text.rstrip() + f"\n\n@{owner}\n"
    title = "Alas 观察（自动）"
    base = f"https://api.github.com/repos/{repo}/issues"
    try:
        req = urllib.request.Request(f"{base}?state=open&per_page=50",
                                     headers={"User-Agent": "mumu-azurlane-helper-watch",
                                              "Accept": "application/vnd.github+json",
                                              "Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            issues = json.loads(resp.read().decode("utf-8"))
        number = next((int(i["number"]) for i in issues
                       if i.get("title") == title and "pull_request" not in i), 0)
        if not number:
            created = _post(base, {"title": title,
                                   "body": "这个 Issue 由自动任务维护：每天一条，"
                                           "大节点期间只在新活动出现时发。"})
            number = int(created["number"])
            print(f"建了 Issue #{number}")
        _post(f"{base}/{number}/comments", {"body": body})
        print(f"已写进 Issue #{number}（会发邮件给仓库 owner）")
    except OSError as exc:
        print(f"⚠️ 通知失败：{exc}")


def _prepend_report(text: str, keep: int = 40) -> None:
    """把这次报告放在文件最前面，只留最近 `keep` 段。"""
    old = ""
    try:
        old = REPORT.read_text(encoding="utf-8")
    except OSError:
        old = "# Alas 上游观察（自动）\n\n每天一次；大节点期间每 2 小时一次。\n\n"
    head, _, rest = old.partition("\n## ")
    parts = []
    if rest.strip():
        parts = ["## " + block for block in rest.split("\n## ")]
    parts = [text] + parts
    keeps = "\n".join(p.rstrip() + "\n" for p in parts[:keep])
    REPORT.write_text(head.rstrip() + "\n\n" + keeps, encoding="utf-8")


def main(argv: list[str]) -> int:
    if "--changes" in argv:
        num = 5
        try:
            num = int(argv[argv.index("--changes") + 1])
        except (IndexError, ValueError):
            pass
        changes(num)
        return 0
    if "--hot" in argv:                       # 我手动开/关"大节点"模式
        state = _load_state()
        state["hot"] = "on" in argv
        state["hot_since"] = _today() if state["hot"] else ""
        _save_state(state)
        print(f"大节点模式：{'开（每 2 小时查，直到新活动出现）' if state['hot'] else '关（恢复每天一次）'}")
        return 0
    if "--ci" in argv:                        # GitHub Actions 里跑
        return _ci(force="--force" in argv)
    sha, date, title = latest_commit()
    events = event_folders()
    now = recent(events)
    table = {}
    try:
        table = json.loads(SHELL_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    alas = table.get("alas") or {}
    marked = [str(e.get("id")) for e in (table.get("events") or []) if isinstance(e, dict)]
    known_date = str(alas.get("latest") or "")
    todo = [e for e in now if e not in marked]

    if "--json" in argv:
        print(json.dumps({"sha": sha, "date": date, "title": title,
                          "open_events": now, "listed": marked,
                          "missing_in_table": todo,
                          "upstream_newer": bool(date and date > known_date)},
                         ensure_ascii=False, indent=2))
        return 0

    print(f"上游 master ：{sha}（{date}）{title}")
    print(f"表里记的日期：{known_date or '（没写）'}")
    print(f"表里记的活动：{', '.join(marked) if marked else '（没写）'}")
    print(f"最近在开的图：{', '.join(now) if now else '（近 45 天上游没加新活动）'}")

    if date and date > known_date:
        print("\n⚠️ 上游有更新（表里还是旧的）")
    if todo:
        print(f"\n⚠️ 这些活动表里还没有：{', '.join(todo)}")
        print("   写进 docs/shell.json 的 events 段：")
        print(json.dumps([{"id": e, "name": _guess_name(e)} for e in todo],
                         ensure_ascii=False, indent=2))
    elif now:
        print("\n✔ 正在开的活动都已经在表里")
    return 0


def _guess_name(folder: str) -> str:
    """`event_20261022_cn` → `10 月活动`（猜个名字，人可以在表里改成官方的）。"""
    found = re.search(r"event_(\d{4})(\d{2})(\d{2})", folder or "")
    if not found:
        return folder
    return f"{int(found.group(2))} 月活动"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
