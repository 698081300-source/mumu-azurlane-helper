"""查有没有新版本 · 把新版本下下来。

本文件只管**网络和版本号**；真正动手换文件在 `selfupdate.py`。

为什么要有这一层（见 `一键三星_需求记录.md` 的「1 万人怎么同步更新」）：
1 万人手上各有一份壳，你不可能挨个通知 —— 壳自己开窗时读这张表，
发现有新版就后台下好，下次启动前自己换掉。

⚠️ 这张表**也是"热配置"的抓手**（L0）：`notice` / `alas` 两块改完几十秒全网生效，
不用重新打包。形状：

    {
      "shell": {"version": "0.2.1", "url": "https://cdn…/shell-0.2.1.zip",
                "sha256": "…", "size": 412345, "rollout": 100,
                "min_supported": "0.2.0", "notes": "修了刷油被委托打断"},
      "alas":  {"min": "0.4.10", "recommend": "0.4.10", "url": "https://…"},
      "notice": "10-3 最近偶尔走位失败，先手动过一关",
      "rollback": false
    }

`rollout`（灰度）= 只推给百分之几的用户；`min_supported` = 低于它的版本**必须**更。
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import uuid

# 线上那张表放哪（发版脚本 `tools\publish.py` 会自动把这里换成你们仓库的地址）。
# **两个地址都要**：jsDelivr 国内更容易连上（但会缓存几小时），raw.githubusercontent 不缓存
# （但国内有时连不上）—— 一个连不上就试下一个，全失败就当"没有更新"。
INDEX_URLS: tuple[str, ...] = (
    "https://raw.githubusercontent.com/698081300-source/mumu-azurlane-helper/main/docs/shell.json",
    "https://cdn.jsdelivr.net/gh/698081300-source/mumu-azurlane-helper@main/docs/shell.json",
)
TIMEOUT_S = 10           # 读表：raw 在国内首次访问常常 3~8 秒，3 秒会把"有新版"判成"没有"
DOWNLOAD_TIMEOUT_S = 60


class UpdateError(RuntimeError):
    """更新链路上的可预期错误（下载/校验失败），拿给用户看的一句人话。"""


_cache: dict | None = None
LAST_SOURCE = ""        # 这张表是从哪条线路读到的（排错用，见 `source_label()`）


def source_label(url: str) -> str:
    """把地址归成人看得懂的线路名（写进导出日志，别的都不写）。"""
    url = (url or "").lower()
    if "raw.githubusercontent" in url:
        return "raw"
    if "jsdelivr" in url:
        return "jsDelivr"
    if "releases/download" in url:
        return "GitHub Release"
    return url or "（未知）"


def _override() -> dict:
    """**本机临时覆盖**：`%APPDATA%\\MuMu碧蓝助手\\events.json`（没有就是空）。

    为什么留这个口子（2026-10-21）：
      - 线上表还没发布时，我们也要能在实机上测"缺活动 → 提示 → 更新"这条链；
      - 真出事时，先在本机改这一份验证，再改线上表。
    它**只覆盖同名字段**，线上表里的其它内容照常生效。形状和线上表一样：
        {"events": [{"id": "event_20261022_cn", "name": "10 月活动"}],
         "alas": {"latest": "2026-10-21"}}
    """
    try:
        import json as _json
        from onetap import paths
        path = paths.data_dir() / "events.json"
        data = _json.loads(path.read_text(encoding="utf-8"))
    except Exception:      # noqa: BLE001 —— 没这个文件 / 写坏了，都当没有
        return {}
    return data if isinstance(data, dict) else {}


def index(force: bool = False) -> dict | None:
    """读线上那张表（一次运行只读一次，按 `INDEX_URLS` 顺序试）。**任何异常都当"没有"**。"""
    global _cache, LAST_SOURCE
    if _cache is not None and not force:
        return _cache
    for url in INDEX_URLS:
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_S) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:      # noqa: BLE001 —— 没网 / 地址挂了 / json 坏了，换下一个地址
            continue
        if isinstance(data, dict) and data:
            _cache = data
            LAST_SOURCE = source_label(url)
            return _cache
    _cache = {}
    LAST_SOURCE = ""
    return _cache


def _merged() -> dict:
    """线上表 + 本机覆盖（覆盖优先，只覆盖它写了的字段）。"""
    data = dict(index() or {})
    local = _override()
    if local:
        for key, value in local.items():
            if key == "alas" and isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **value}     # 只盖写了的子字段
            else:
                data[key] = value
    return data


def check(current: str, skip: set[str] | None = None) -> dict | None:
    """该不该给这个用户推新版？该 → 返回信息字典，不该 → `None`。

    Args:
        current: 现在跑着的版本（`onetap.__version__`）。
        skip: 明确不要推的版本（换坏了被回滚过的那些，见 `selfupdate.blocked()`）。

    **任何字段缺失 / 版本号认不出来 → 不提示**：宁可不更新，也不能误报或推一个坏包。
    """
    data = index()
    if not data:
        return None
    shell = data.get("shell") or {}
    version = str(shell.get("version") or "").strip()
    url = str(shell.get("url") or "").strip()
    if not (version and url) or not newer(version, current):
        return None
    if version in (skip or set()):
        return None
    # 我太旧（低于线上的 min_supported）→ 必须更，不吃灰度
    forced = newer(str(shell.get("min_supported") or "").strip(), current)
    if not forced and not _in_rollout(shell.get("rollout", 100), version):
        return None
    return {"version": version,
            "url": url,
            "mirrors": [str(x).strip() for x in (shell.get("mirrors") or [])
                        if str(x).strip()],
            "notes": str(shell.get("notes") or "").strip(),
            "sha256": str(shell.get("sha256") or "").strip(),
            "size": _as_int(shell.get("size")),
            "forced": forced}


def alas_broken() -> tuple[str, ...]:
    """线上表里的**黑名单**：已知"这版 Alas 会让壳出事"的版本（短 sha 前缀）。

    写法：`"alas": {"broken": ["2fc8c1c"]}`
    **默认空** → 平时一句话都不说。只在我们真收到用户反馈、定位到某一版时加一条，
    改完几十秒全网生效（不用发版）。

    为什么不是"测过哪几版"（白名单）：那要我们追着 Alas 的每个版本跑一遍测试，
    等于给 Alas 打工，而且名单永远追不上 → 用户天天看到"我没测过"＝纯噪音。
    """
    alas = (_merged().get("alas") or {})
    values = alas.get("broken") or []
    if isinstance(values, str):
        values = [values]
    return tuple(str(v).strip().lower() for v in values if str(v).strip())


def events() -> list[dict]:
    """线上表里的「当前正在开的新活动」清单（`event_folders` 差集用）。

    写法（只列**全新活动**，复刻的不用列 —— 复刻图 Alas 里早就有）：

        "events": [
          {"id": "event_20261009_cn", "name": "10 月活动", "until": "2026-10-22"}
        ]

    只读、只用来判断"本机缺不缺"；`until` 过了就自动不理它。
    **漏写/写错都不会出错**：最坏是少提示一句，或者提示了但用户点一下更新就好了。
    """
    raw = (_merged().get("events") or [])
    if isinstance(raw, dict):
        raw = [raw]
    today = time.strftime("%Y-%m-%d")
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        folder = str(item.get("id") or "").strip()
        if not folder:
            continue
        until = str(item.get("until") or "").strip()
        if until and until < today:          # ISO 日期可以直接比字符串
            continue
        out.append({"id": folder, "name": str(item.get("name") or folder).strip()})
    return out


def alas_latest() -> str:
    """线上表里"Alas 上游最新是哪天"（`"alas": {"latest": "2026-10-20"}`）。

    只用于兜底那句「你的 Alas 有点旧」。**没写就返回空** → 不提示。
    这个日期我们每周手填一次就够，不用每天。
    """
    return str(((_merged().get("alas") or {}).get("latest") or "")).strip()


def notice() -> str:
    """线上表里那条给用户看的公告（没有就是空串）。改它不用发版。"""
    return str((index() or {}).get("notice") or "").strip()


# Alas 的下载页（壳**不打包、不分发** Alas，只负责指路 —— GPL-3.0 红线）。
# 线上表的 `"alas": {"url": …, "note": …}` 可以覆盖这里：改文案/换镜像不用发版。
ALAS_URL = "https://alas.azurlane.cloud/"
ALAS_NOTE = "打开页面点「立即下载」就是完整包，装好就行"


def alas_download() -> tuple[str, str]:
    """Alas 下载 → `(地址, 说明)`。"""
    alas = (_merged().get("alas") or {})
    url = str(alas.get("url") or "").strip() or ALAS_URL
    note = str(alas.get("note") or "").strip() or ALAS_NOTE
    return url, note


def download(url, dest, sha256: str = "", size: int = 0):
    """下到 `dest`，**校验 sha256 / 字节数**，校验不过就删掉并抛 `UpdateError`。

    `url` 可以是字符串，也可以是**地址列表** —— 一个一个试，第一个成功就收工
    （2026-10-22 实机：Release 的下载地址会跳到 objects.githubusercontent.com，
     国内常常连不上；而仓库里的 raw 文件能连。所以每个包都给几个备用地址）。

    为什么要校验（照抄 MAA 的做法）：CDN 可能缓存了旧文件、用户的网可能被中间人插一脚、
    下载可能半途断掉 —— 这三种都会在"换代码"时变成"工具打不开了"，代价太大，几十字节换不起吗。
    """
    urls = [url] if isinstance(url, str) else [u for u in url if u]
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    last: Exception | None = None
    for one in urls:
        digest = hashlib.sha256()
        got = 0
        try:
            with urllib.request.urlopen(one, timeout=DOWNLOAD_TIMEOUT_S) as resp, \
                    tmp.open("wb") as fh:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
                    digest.update(chunk)
                    got += len(chunk)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            last = exc
            continue                      # 换下一个地址
        if sha256 and digest.hexdigest().lower() != sha256.lower():
            tmp.unlink(missing_ok=True)
            last = UpdateError("下载的包校验不过（可能是 CDN 缓存了旧文件），这次先不更新")
            continue
        if size and got != size:
            tmp.unlink(missing_ok=True)
            last = UpdateError(f"下载的包大小不对（{got} ≠ {size} 字节），这次先不更新")
            continue
        tmp.replace(dest)
        return dest
    raise UpdateError(f"下载新版失败：{last}")


def newer(latest: str, current: str) -> bool:
    """版本号比较：按 `.` 切开比数字。有一边认不出来就返回 False（宁可不提示，别误报）。"""
    def parts(text: str) -> tuple[int, ...]:
        return tuple(int(x) for x in text.lstrip("vV").split(".") if x.isdigit())

    a, b = parts(latest), parts(current)
    return bool(a and b and a > b)


def _as_int(value: object) -> int:
    try:
        return int(value)          # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _in_rollout(rollout: object, version: str) -> bool:
    """这台机器在不在这批灰度里。

    按"机器码 + 版本号"哈希取模：同一版本对同一台机器结果固定（不会被反复推来推去），
    不同版本的分桶不同（不会永远是同一批人当小白鼠）。
    `rollout` 缺省 / 写错 → 100%（全量）。
    """
    try:
        percent = int(rollout)          # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    try:
        key = f"{uuid.getnode()}-{version}".encode()
        return int(hashlib.sha1(key).hexdigest()[:8], 16) % 100 < percent
    except Exception:      # noqa: BLE001
        return False
