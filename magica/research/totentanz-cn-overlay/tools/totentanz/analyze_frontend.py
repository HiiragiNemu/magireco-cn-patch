from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher


HERE = Path(__file__).resolve().parent
NEW_ROOT = HERE / "extracted" / "totentanz-frontend" / "totentanz-frontend"
OLD_ROOT = HERE / "old_cn"
TEXT_EXTS = {".html", ".js", ".css", ".json", ".txt", ".py"}
KANA_RE = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# Characters strongly suggestive of Simplified Chinese rather than Japanese text.
SIMPLIFIED_HINT_RE = re.compile(
    r"[这为么们你她里后发对战级体术关门间张显进觉设页图标击败获奖阵营队伍"
    r"继练线换补从与专应开时将无过还边达选当会师万东书乐乡买乱争于亏云亚产亩亲"
    r"亿仅仑仓仪价众优伙伞伟传伤伦伪侧侦侨俩俪俭债倾偿储儿兑党兰兴养兽冈册写军"
    r"农冲决况冻净凉减凑几凤凭凯划刘则刚创删别刹剂剑剧劝办务动励劳势勋匀区医华"
    r"协单卖卢卫却厂厅历厉压厌厕县参双变叙叶号叹吓吕吗听启吴呐员呜咏咤响哑哟唤"
    r"啸喷嘘团园围国圆圣场坏块坚坛坝坞坟坠垄垒垦垫墙壮声壶处备复够头夹夺奋奖妇"
    r"妈孙学宁宝实宠审宪宫宽宾寻导寿尝尧尽层岁岂岖岗岛岭岳峡币帮干并广庄庆库废"
    r"录归彻忆怀态怜总恋恒恳恶恼恽悦悬惊惯愤愿戏户扑执扩扫扬扰抚抛抢护报拟拥拦"
    r"拧拨择挂挚挛挝挞挟挠挡挣挥损捡换据掳掷掸掺摄摆摇摊撑撵敌敛数斋斗断旧昙昼"
    r"晋晓晕暂术朴机杀杂权条来杨杰极构枪柜树样桥梦检楼欢欧歼殁毕气汇汉汤沟没沦"
    r"济浏浑浓涛涂涌润涨涧淀渊渐渔湾湿溃溅滚滞满滤滥滨滩灭灯灵灾炉点炼烁烂烛烟"
    r"烦烧烫热爱爷牵状犹狈狭狮独狱猎猪猫献环现玺电画畅疗疯痪瘫皱盏盐监盘着矿码"
    r"砖砚砺础硕确礼祷祸离种积称稳窃窍竞笔笼筛简粮紧纠红纤约纪纯纲纳纵纷纸纹纺"
    r"纽线练组细织终绍经绑结绕绘给络绝统继绩绪续维绵综绿缀缉编缘缚缝缩缴网罗罚"
    r"职联聪肃肠肤胜胶脑脸腻腾舰舱艳艺节范茧荐荡荣药获莲营萨虑虚虫虽虾蚀蛮蜂蜡"
    r"蝇蝉补装览观规视觅览触订计认让训议记讲讳讶许论设访诀证评识诈诉诊词译试诗"
    r"诚话诞询该详语误说请诸诺读课谁调谈谊谋谎谢谨谱贝负贡财责贤败账货质贩贪贫"
    r"购贯贱贴贵贷贸费贺贼贾资赋赐赏赔赖赚赛赞赶趋跃跻践踊车轨转轮软轰轻载较辅"
    r"辆辉辈边辽迁过迈运近返还进远违连迟迩选逊递逻遗遥邓郑郁邮邻酝释鉴钟钥钩钮"
    r"钱钳钻铁铃铅铜银铺链销锁锅锻镶长闷闪闭问闯闲闹闻阀阁阅阔队阳阴阵阶际陆陈"
    r"险隐隶难雾静顶顷项顺须顾顿颁预领频颠风飘飞饥饭饮饰饱饲饼馆驱驰验骑骗骚鱼"
    r"鸟鸡鸭麦黄齐齿龄龙]"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decode_text(path: Path) -> tuple[str | None, str | None]:
    raw = path.read_bytes()
    if b"\x00" in raw[:4096]:
        return None, None
    for enc in ("utf-8-sig", "utf-8", "gb18030", "shift_jis"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def text_metrics(path: Path) -> dict:
    text, enc = decode_text(path)
    if text is None:
        return {"encoding": None}
    return {
        "encoding": enc,
        "lines": text.count("\n") + (1 if text else 0),
        "chars": len(text),
        "kana": len(KANA_RE.findall(text)),
        "cjk": len(CJK_RE.findall(text)),
        "simplified_hints": len(SIMPLIFIED_HINT_RE.findall(text)),
    }


def scan(root: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        ext = p.suffix.lower()
        row = {
            "path": rel,
            "extension": ext or "[none]",
            "category": rel.split("/", 1)[0],
            "size": p.stat().st_size,
            "sha256": sha256(p),
        }
        if ext in TEXT_EXTS:
            row.update(text_metrics(p))
        out[rel] = row
    return out


def similarity(a: Path, b: Path) -> float | None:
    ta, _ = decode_text(a)
    tb, _ = decode_text(b)
    if ta is None or tb is None:
        return None
    # Line-level structure signal. This is deliberately bounded so the full
    # inventory remains cheap and deterministic even for bundled libraries.
    if len(ta) + len(tb) > 800_000:
        return None
    la, lb = ta.splitlines(), tb.splitlines()
    if len(la) + len(lb) > 30_000:
        return None
    return round(SequenceMatcher(None, la, lb, autojunk=True).ratio(), 6)


def count_by(rows: list[dict], field: str, status: str | None = None) -> dict[str, int]:
    c = Counter()
    for row in rows:
        if status is not None and row["status"] != status:
            continue
        c[row[field]] += 1
    return dict(sorted(c.items()))


def main() -> None:
    if not NEW_ROOT.is_dir() or not OLD_ROOT.is_dir():
        raise SystemExit(f"missing roots: NEW={NEW_ROOT} OLD={OLD_ROOT}")
    new = scan(NEW_ROOT)
    old = scan(OLD_ROOT)
    entries: list[dict] = []
    for rel in sorted(set(new) | set(old)):
        n = new.get(rel)
        o = old.get(rel)
        if n and o:
            status = "shared_identical" if n["sha256"] == o["sha256"] else "shared_modified"
        elif n:
            status = "current_only"
        else:
            status = "old_only"
        row = {
            "path": rel,
            "category": (n or o)["category"],
            "extension": (n or o)["extension"],
            "status": status,
            "current_size": n["size"] if n else None,
            "old_size": o["size"] if o else None,
            "current_sha256": n["sha256"] if n else None,
            "old_sha256": o["sha256"] if o else None,
        }
        for side, data in (("current", n), ("old", o)):
            for key in ("encoding", "lines", "chars", "kana", "cjk", "simplified_hints"):
                row[f"{side}_{key}"] = data.get(key) if data else None
        if status == "shared_modified" and row["extension"] in TEXT_EXTS:
            row["text_similarity"] = similarity(NEW_ROOT / rel, OLD_ROOT / rel)
        else:
            row["text_similarity"] = 1.0 if status == "shared_identical" and row["extension"] in TEXT_EXTS else None
        entries.append(row)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_root": str(NEW_ROOT),
        "old_root": str(OLD_ROOT),
        "current_file_count": len(new),
        "old_file_count": len(old),
        "union_file_count": len(entries),
        "status_counts": dict(Counter(e["status"] for e in entries)),
        "status_by_extension": {
            status: count_by(entries, "extension", status)
            for status in ("shared_identical", "shared_modified", "current_only", "old_only")
        },
        "current_by_category": dict(Counter(e["category"] for e in entries if e["status"] != "old_only")),
        "old_by_category": dict(Counter(e["category"] for e in entries if e["status"] != "current_only")),
    }
    inventory = {"summary": summary, "entries": entries}
    (HERE / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = list(entries[0].keys())
    with (HERE / "inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(entries)
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Focused extracts make manual review and automated merge rule authoring easier.
    focused = [e for e in entries if e["extension"] in {".html", ".js", ".css", ".json"}]
    with (HERE / "text_comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(focused)
    new_ui = [e for e in focused if e["status"] == "current_only"]
    with (HERE / "current_only_ui.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(new_ui)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
