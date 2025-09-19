import os, re, hashlib
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StandardsWatcher/1.0)"}
TIMEOUT = 30
OUT_DIR = "feeds"
os.makedirs(OUT_DIR, exist_ok=True)

# 监控源（可扩展）
SOURCES = [
    {
        "name": "casc-zzfb",  # 准则发布
        "url": "https://www.casc.org.cn/zzfb/",
        "base": "https://www.casc.org.cn",
        "title": "会计准则委员会｜准则发布",
        # 常见列表容器选择器；不同版式取并集，容错
        "item_selector": "div.list ul li, div.newslist ul li, ul.list li, ul li",
        "title_selector": "a",
        "date_selector": "span, em, i",
    },
    {
        "name": "casc-gztz",  # 工作通知
        "url": "https://www.casc.org.cn/gztz/",
        "base": "https://www.casc.org.cn",
        "title": "会计准则委员会｜工作通知",
        "item_selector": "div.list ul li, div.newslist ul li, ul.list li, ul li",
        "title_selector": "a",
        "date_selector": "span, em, i",
    },
    {
        "name": "mof-kjs-zhengcefabu",  # 政策发布
        "url": "https://kjs.mof.gov.cn/zhengcefabu/",
        "base": "https://kjs.mof.gov.cn",
        "title": "财政部会计司｜政策发布",
        "item_selector": "div.list ul li, div.newslist ul li, ul.list li, ul li",
        "title_selector": "a",
        "date_selector": "span, em, i",
    },
    {
        "name": "mof-kjs-sswd",  # 实施问答（总页）
        "url": "https://kjs.mof.gov.cn/zt/kjzzss/sswd/",
        "base": "https://kjs.mof.gov.cn",
        "title": "财政部会计司｜实施问答（总页）",
        "item_selector": "div.list ul li, div.newslist ul li, ul.list li, ul li",
        "title_selector": "a",
        "date_selector": "span, em, i",
    },
]

def to_abs(base, href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base.rstrip("/") + href
    return base.rstrip("/") + "/" + href

def try_parse_date(text: str):
    if not text:
        return None
    t = re.sub(r"\s+", "", text)
    m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", t)
    if m:
        y, mo, d = map(int, m.groups())
        return datetime(y, mo, d, tzinfo=timezone.utc)
    return None

def scrape(source):
    r = requests.get(source["url"], headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    items = []
    for li in soup.select(source["item_selector"])[:80]:
        a = li.select_one(source["title_selector"])
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get("href") or ""
        url = to_abs(source["base"], href)
        if not title or not url:
            continue

        # 日期策略：优先就近 span/em/i；没有则 None
        dt = None
        for ds in source["date_selector"].split(","):
            el = li.select_one(ds.strip())
            if el:
                dt = try_parse_date(el.get_text(" ", strip=True))
                if dt:
                    break
        # 兜底：若未能解析日期，使用当前时间（确保条目可被订阅器接收）
        if not dt:
            dt = datetime.now(timezone.utc)

        items.append({"title": title, "url": url, "date": dt})

    # 去重（按 URL+标题）
    uniq = {}
    for it in items:
        key = (it["url"], it["title"])
        if key not in uniq:
            uniq[key] = it
    return list(uniq.values())

def build_feed(name, title, url, items):
    fg = FeedGenerator()
    fg.id(url)
    fg.title(title)
    fg.link(href=url, rel="alternate")
    fg.link(href=f"https://ceceliahappyday.github.io/feeds/{name}.xml", rel="self")
    fg.language("zh-cn")

    # 按日期倒序
    items = sorted(items, key=lambda x: x["date"], reverse=True)[:60]

    for it in items:
        fe = fg.add_entry()
        uid = hashlib.md5((it["url"] + it["title"]).encode("utf-8")).hexdigest()
        fe.id(uid)
        fe.title(it["title"])
        fe.link(href=it["url"])
        fe.published(it["date"])

    out_path = os.path.join(OUT_DIR, f"{name}.xml")
    fg.rss_file(out_path, pretty=True)
    print("Wrote", out_path)

def main():
    for s in SOURCES:
        try:
            items = scrape(s)
            if items:
                build_feed(s["name"], s["title"], s["url"], items)
            else:
                print("No items parsed for", s["name"])
        except Exception as e:
            print("ERR:", s["name"], e)

if __name__ == "__main__":
    main()
