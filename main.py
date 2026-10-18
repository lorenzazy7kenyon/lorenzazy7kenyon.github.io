# -*- coding: utf-8 -*-
"""抓取公共免费节点，生成 Clash / V2ray / Sing-box 订阅与站点内容"""
import base64
import glob
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import yaml

BASE_URL = "https://lorenzazy7kenyon.github.io"
SITE_NAME = "RU节点"
SITE_TITLE = "免费Clash节点订阅 | V2ray/Clash/Sing-box免费机场节点分享"
ROOT = os.path.dirname(os.path.abspath(__file__))
TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

SOURCES = [
    "https://raw.githubusercontent.com/freefq/free/master/v2",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",
]

LINK_RE = re.compile(
    r"(?:vmess|vless|trojan|trojan-go|ss|hysteria2|hys2)://[^\s\"'<>\[\]]+")


def now8():
    return datetime.now(TZ)


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        print("fetch fail:", url, e)
        return ""


def maybe_b64(text):
    text = text.strip()
    if not text or "://" in text[:200]:
        return text
    try:
        pad = text + "=" * (-len(text) % 4)
        decoded = base64.b64decode(pad, validate=False).decode("utf-8", "ignore")
        if "://" in decoded:
            return decoded
    except Exception:
        pass
    return text


def parse_vmess(link):
    body = link[8:].split("#")[0]
    pad = body + "=" * (-len(body) % 4)
    j = json.loads(base64.b64decode(pad).decode("utf-8", "ignore"))
    net = j.get("net", "tcp")
    proxy = {
        "name": j.get("ps") or (str(j.get("add")) + ":" + str(j.get("port"))),
        "type": "vmess",
        "server": str(j.get("add", "")),
        "port": int(j.get("port", 0)),
        "uuid": j.get("id", ""),
        "alterId": int(j.get("aid", 0) or 0),
        "cipher": j.get("scy", "auto"),
        "tls": str(j.get("tls", "")).startswith("t"),
        "network": net if net in ("http", "ws", "grpc", "h2") else "tcp",
        "servername": j.get("sni", j.get("host", "")) or "",
        "udp": True,
    }
    if net in ("ws", "http"):
        proxy["ws-opts"] = {
            "path": j.get("path", "/"),
            "headers": {"Host": [j.get("host", "")]} if j.get("host") else {},
        }
    return proxy


def parse_ss(link):
    u = urllib.parse.urlparse(link)
    origin = link[5:].split("/")[0].split("#")[0]
    if "@" not in origin:
        pad = origin + "=" * (-len(origin) % 4)
        origin = base64.b64decode(pad).decode("utf-8", "ignore")
    userinfo, hostport = origin.rsplit("@", 1)
    if ":" not in userinfo:
        pad = userinfo + "=" * (-len(userinfo) % 4)
        userinfo = base64.b64decode(pad).decode("utf-8", "ignore")
    method, password = userinfo.split(":", 1)
    host, port = hostport.rsplit(":", 1)
    server = urllib.parse.unquote(host)
    return {
        "name": urllib.parse.unquote(u.fragment) if u.fragment else server + ":" + port,
        "type": "ss",
        "server": server,
        "port": int(port or 0),
        "cipher": method,
        "password": password,
        "udp": True,
    }


def parse_trojan(link):
    u = urllib.parse.urlparse(link)
    q = dict(urllib.parse.parse_qsl(u.query or "", keep_blank_values=True))
    host = u.hostname or ""
    return {
        "name": urllib.parse.unquote(u.fragment) if u.fragment else host + ":" + str(u.port),
        "type": "trojan",
        "server": host,
        "port": u.port or 443,
        "password": urllib.parse.unquote(u.username or ""),
        "sni": q.get("sni") or q.get("peer") or host,
        "skip-cert-verify": True,
        "udp": True,
    }


def parse_vless(link):
    u = urllib.parse.urlparse(link)
    q = dict(urllib.parse.parse_qsl(u.query or "", keep_blank_values=True))
    net = q.get("type", "tcp")
    proxy = {
        "name": urllib.parse.unquote(u.fragment) if u.fragment else str(u.hostname) + ":" + str(u.port),
        "type": "vless",
        "server": u.hostname or "",
        "port": u.port or 0,
        "uuid": urllib.parse.unquote(u.username or ""),
        "tls": q.get("security", "none") != "none",
        "servername": q.get("sni") or q.get("host") or "",
        "network": "http" if net in ("http", "xhttp") else net,
        "udp": True,
    }
    if net in ("ws", "http", "xhttp"):
        proxy["ws-opts"] = {"path": q.get("path") or "/"}
        if q.get("host"):
            proxy["ws-opts"]["headers"] = {"Host": [q["host"]]}
    elif net == "grpc":
        proxy["grpc-opts"] = {"grpc-service-name": q.get("serviceName", "")}
    return proxy


def parse_hysteria2(link):
    u = urllib.parse.urlparse(link)
    q = dict(urllib.parse.parse_qsl(u.query or "", keep_blank_values=True))
    host = u.hostname or ""
    return {
        "name": urllib.parse.unquote(u.fragment) if u.fragment else str(u.hostname),
        "type": "hysteria2",
        "server": host,
        "port": u.port or 443,
        "password": urllib.parse.unquote(u.username or ""),
        "sni": q.get("sni") or host,
        "skip-cert-verify": q.get("insecure", "0") in ("1", "true"),
    }


def parse_link(link):
    try:
        if link.startswith("vmess://"):
            return parse_vmess(link)
        if link.startswith("vless://"):
            return parse_vless(link)
        if link.startswith("trojan://") or link.startswith("trojan-go://"):
            if link.startswith("trojan-go://"):
                link = "trojan://" + link[len("trojan-go://"):]
            return parse_trojan(link)
        if link.startswith("ss://"):
            return parse_ss(link)
        if link.startswith("hysteria2://") or link.startswith("hys2://"):
            if link.startswith("hys2://"):
                link = "hysteria2://" + link[len("hys2://"):]
            return parse_hysteria2(link)
    except Exception:
        pass
    return None


def from_clash_proxy(p):
    q = dict(p)
    q["udp"] = True
    supported = {"vmess", "vless", "ss", "ssr", "trojan", "hysteria2", "hysteria"}
    if q.get("type") not in supported:
        return None
    if q["type"] == "ssr":
        q = {**q, "type": "ss"}
    return q


def export_links(proxies):
    links = []
    for p in proxies:
        t = p.get("type")
        try:
            if t == "vmess":
                wo = p.get("ws-opts") or {}
                hh = (wo.get("headers") or {}).get("Host", [])
                j = {"v": "2", "ps": p["name"], "add": p["server"], "port": str(p["port"]),
                     "id": p.get("uuid", ""), "aid": str(p.get("alterId", 0) or 0),
                     "scy": p.get("cipher", "auto"),
                     "net": p.get("network", "tcp") if p.get("network") != "http" else "ws",
                     "type": "none",
                     "host": (hh[0] if hh else "") or p.get("servername", ""),
                     "path": wo.get("path", "/"),
                     "tls": "tls" if p.get("tls") else "",
                     "sni": p.get("servername", "")}
                links.append("vmess://" + base64.b64encode(json.dumps(j, separators=(",", ":")).encode()).decode())
            elif t == "ss":
                raw = "{}:{}@{}:{}".format(p.get("cipher"), urllib.parse.quote(str(p.get("password", ""))),
                                           p["server"], p["port"])
                links.append("ss://" + base64.urlsafe_b64encode(raw.encode()).decode() + "#" + urllib.parse.quote(p["name"]))
            elif t == "trojan":
                links.append("trojan://{}@{}:{}?sni={}#{}".format(
                    urllib.parse.quote(str(p.get("password", ""))), p["server"], p["port"],
                    urllib.parse.quote(str(p.get("sni", "") or p["server"])), urllib.parse.quote(p["name"])))
            elif t == "vless":
                net = p.get("network", "tcp") if p.get("network") != "http" else "ws"
                q = "type={}&security={}".format(net, "tls" if p.get("tls") else "none")
                if p.get("servername"):
                    q += "&sni=" + urllib.parse.quote(str(p["servername"]))
                if p.get("ws-opts"):
                    q += "&path=" + urllib.parse.quote(p["ws-opts"].get("path", "/") or "/")
                    hh = p["ws-opts"].get("headers", {}).get("Host", [])
                    if hh:
                        q += "&host=" + urllib.parse.quote(hh[0])
                links.append("vless://{}@{}:{}?{}#{}".format(p.get("uuid", ""), p["server"], p["port"], q, urllib.parse.quote(p["name"])))
            elif t == "hysteria2":
                links.append("hysteria2://{}@{}:{}?sni={}#{}".format(
                    urllib.parse.quote(str(p.get("password", ""))), p["server"], p["port"],
                    urllib.parse.quote(str(p.get("sni", "") or p["server"])), urllib.parse.quote(p["name"])))
        except Exception:
            continue
    return links


def clash_yaml(proxies):
    names = [p["name"] for p in proxies]
    groups = [
        {"name": "自动选择", "type": "url-test", "proxies": names,
         "url": "http://www.gstatic.com/generate_204", "interval": 300, "tolerance": 50},
        {"name": "手动选择", "type": "select", "proxies": ["自动选择"] + names},
    ]
    cfg = {
        "port": 7890,
        "socks-port": 7891,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "warning",
        "dns": {"enable": True,
                "nameserver": ["https://dns.alidns.com/dns-query", "https://doh.pub/dns-query"],
                "fallback": ["https://1.1.1.1/dns-query"]},
        "proxies": proxies,
        "proxy-groups": groups,
        "rules": ["DOMAIN-SUFFIX,cn,DIRECT", "GEOIP,CN,DIRECT", "MATCH,手动选择"],
    }
    return yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False, width=10**6)


def singbox_outbound(p):
    t = p.get("type")
    ob = {"tag": p["name"], "type": t}
    try:
        if t == "vmess":
            ob.update({"server": p["server"], "server_port": p["port"], "uuid": p.get("uuid", ""),
                       "security": "auto", "alter_id": int(p.get("alterId", 0) or 0)})
            if p.get("tls"):
                ob["tls"] = {"enabled": True, "server_name": p.get("servername", "") or "", "insecure": True}
            if p.get("network") in ("ws", "http"):
                wo = p.get("ws-opts") or {}
                hh = (wo.get("headers") or {}).get("Host", [])
                ob["transport"] = {"type": "ws", "path": wo.get("path", "/"),
                                   "headers": {"Host": hh[0]} if hh else {}}
            elif p.get("network") == "grpc":
                ob["transport"] = {"type": "grpc", "service_name": (p.get("grpc-opts") or {}).get("grpc-service-name", "")}
        elif t == "vless":
            ob.update({"server": p["server"], "server_port": p["port"], "uuid": p.get("uuid", "")})
            if p.get("tls"):
                ob["tls"] = {"enabled": True, "server_name": p.get("servername", "") or "", "insecure": True}
            if p.get("network") in ("ws", "http"):
                wo = p.get("ws-opts") or {}
                hh = (wo.get("headers") or {}).get("Host", [])
                ob["transport"] = {"type": "ws", "path": wo.get("path", "/"),
                                   "headers": {"Host": hh[0]} if hh else {}}
            elif p.get("network") == "grpc":
                ob["transport"] = {"type": "grpc", "service_name": (p.get("grpc-opts") or {}).get("grpc-service-name", "")}
        elif t == "ss":
            ob.update({"server": p["server"], "server_port": p["port"], "method": p.get("cipher", ""),
                       "password": str(p.get("password", ""))})
        elif t == "trojan":
            ob.update({"server": p["server"], "server_port": p["port"], "password": str(p.get("password", "")),
                       "tls": {"enabled": True, "server_name": p.get("sni", "") or "", "insecure": True}})
        elif t == "hysteria2":
            ob.update({"server": p["server"], "server_port": p["port"], "password": str(p.get("password", "")),
                       "tls": {"enabled": True, "server_name": p.get("sni", "") or "", "insecure": True}})
        else:
            return None
    except Exception:
        return None
    return ob


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def clean_old_uploads(keep_months=2):
    updir = os.path.join(ROOT, "uploads")
    today = now8()
    valid = {(today.year + (0 if today.month > keep_months else -1),
              today.month if today.month > keep_months else 12 + today.month - keep_months)}
    yy = today.year
    mm = today.month
    for k in range(keep_months):
        valid.add((yy, mm))
        mm -= 1
        if mm == 0:
            yy -= 1
            mm = 12
    if os.path.isdir(updir):
        for y in os.listdir(updir):
            ydir = os.path.join(updir, y)
            if not os.path.isdir(ydir) or not y.isdigit():
                continue
            for m in os.listdir(ydir):
                mdir = os.path.join(ydir, m)
                if not os.path.isdir(mdir) or not m.isdigit():
                    continue
                if (int(y), int(m)) not in valid:
                    print("cleanup:", ydir, mdir)
                    import shutil
                    shutil.rmtree(mdir, ignore_errors=True)
            if not os.listdir(ydir):
                os.rmdir(ydir)


def main():
    today = now8().strftime("%Y%m%d")
    ysn, msn = now8().strftime("%Y"), now8().strftime("%m")
    stamp = now8().strftime("%Y-%m-%d %H:%M:%S")

    raw_texts = []
    for url in SOURCES:
        text = fetch(url)
        if not text:
            continue
        if url.endswith(".yaml"):
            raw_texts.append(("", url, text))
        else:
            raw_texts.append((maybe_b64(text), url, text))

    links = set()
    clash_dicts = []
    for decoded, url, raw in raw_texts:
        if url.endswith(".yaml"):
            try:
                cfg = yaml.safe_load(raw)
                for p in (cfg or {}).get("proxies") or []:
                    if isinstance(p, dict):
                        clash_dicts.append(p)
            except Exception as e:
                print("yaml parse fail:", url, e)
        for m in LINK_RE.findall(decoded):
            links.add(m.strip())

    proxies = []
    for p in clash_dicts:
        c = from_clash_proxy(p)
        if c:
            proxies.append(c)
    for lk in links:
        p = parse_link(lk)
        if p and p.get("server") and p.get("port"):
            proxies.append(p)

    # 去重
    seen = set()
    uniq = []
    for p in proxies:
        key = "{type}|{server}|{port}|{secret}".format(
            type=p["type"], server=p["server"], port=p["port"],
            secret=p.get("uuid") or p.get("password") or "")
        if key in seen:
            continue
        seen.add(key)
        p["name"] = (p.get("name") or "").strip() or "{}:{}".format(p["server"], p["port"])
        uniq.append(p)
    counter = {}
    for p in uniq:
        counter[p["name"]] = counter.get(p["name"], 0) + 1
        if counter[p["name"]] > 1:
            p["name"] = "{}{:+02d}".format(p["name"], counter[p["name"]] - 1)
    uniq.sort(key=lambda p: (p["type"], p["server"]))
    print("total unique nodes:", len(uniq))
    if not uniq:
        print("no nodes, abort")
        return

    data_dir = os.path.join(ROOT, "data", "")
    os.makedirs(data_dir, exist_ok=True)
    hist_path = data_dir + "history.json"
    history = set()
    if os.path.exists(hist_path):
        try:
            history = set(json.load(open(hist_path, encoding="utf-8")))
        except Exception:
            pass
    def key2(p):
        return "{type}|{server}|{port}".format(type=p["type"], server=p["server"], port=p["port"])
    new_nodes = [p for p in uniq if key2(p) not in history]
    for p in uniq:
        history.add(key2(p))
    json.dump(sorted(history), open(hist_path, "w", encoding="utf-8"))

    for d in ("uploads", "free-nodes", "newly-discovered-nodes"):
        os.makedirs(os.path.join(ROOT, *(d,) if d != "uploads" else (d, ysn, msn)), exist_ok=True)
    upload_dir = os.path.join(ROOT, "uploads", ysn, msn)

    yaml_urls, txt_urls = [], []
    norf = 5
    for i in range(norf):
        chunk = uniq[i::norf]
        if not chunk:
            continue
        ynf = "{}-{}.yaml".format(i, today)
        tnf = "{}-{}.txt".format(i, today)
        with open(os.path.join(upload_dir, ynf), "w", encoding="utf-8") as f:
            f.write(clash_yaml(chunk))
        cl = "\n".join(export_links(chunk))
        with open(os.path.join(upload_dir, tnf), "w", encoding="utf-8") as f:
            f.write(base64.b64encode(cl.encode()).decode() + "\n")
        yaml_urls.append("{}/uploads/{}/{}/{}".format(BASE_URL, ysn, msn, ynf))
        txt_urls.append("{}/uploads/{}/{}/{}".format(BASE_URL, ysn, msn, tnf))

    sb_outbounds, sb_tags = [], set()
    for p in uniq:
        ob = singbox_outbound(p)
        if ob and ob["tag"] not in sb_tags:
            sb_tags.add(ob["tag"])
            sb_outbounds.append(ob)
    sb_cfg = {
        "log": {"level": "warn", "timestamp": True},
        "dns": {"servers": [{"tag": "remote", "address": "https://1.1.1.1/dns-query"},
                             {"tag": "local", "address": "https://dns.alidns.com/dns-query"}]},
        "outbounds": [{"type": "urltest", "tag": "自动选择", "interval": "5m",
                       "outbounds": [o["tag"] for o in sb_outbounds]}]
                      + sb_outbounds + [{"type": "direct", "tag": "direct"}],
    }
    sbf = "{}.json".format(today)
    with open(os.path.join(upload_dir, sbf), "w", encoding="utf-8") as f:
        json.dump(sb_cfg, f, ensure_ascii=False, indent=1)
    sb_url = "{}/uploads/{}/{}/{}".format(BASE_URL, ysn, msn, sbf)

    clean_old_uploads()

    description = "所有免费clash节点都爬取自网络，本次更新共 {n} 个节点，请勿用于非法用途。".format(n=len(uniq))

    def links_ul(urls):
        return "\n".join('<li><a href="{u}" target="_blank" rel="nofollow noopener">{u}</a></li>'.format(u=esc(u)) for u in urls)

    # 今日页面
    daily_links = "\n".join([
        "<h2>免费Clash节点订阅链接</h2>\n<ul class=\"links\">" + links_ul(yaml_urls) + "</ul>",
        "<h2>免费V2ray节点订阅链接</h2>\n<ul class=\"links\">" + links_ul(txt_urls) + "</ul>",
        "<h2>免费Sing-box节点订阅链接</h2>\n<ul class=\"links\">" + links_ul([sb_url]) + "</ul>",
    ])
    page_title = "{m}月{d}日|免费Singbox节点/V2ray节点/Clash节点/SSR节点订阅分享".format(m=today[4:6], d=today[6:])
    with open(os.path.join(ROOT, "free-nodes", today + ".html"), "w", encoding="utf-8") as f:
        f.write(DAILY_TMPL.format(site_name=SITE_NAME, site_title=SITE_TITLE, base_url=BASE_URL,
                                  today=today, stamp=stamp, node_count=len(uniq),
                                  description=description, daily_links=daily_links, page_title=page_title))

    # 新发现节点页
    new_links = export_links(new_nodes)
    new_body = "<p>本次新发现 <strong>{}</strong> 个节点。</p>".format(len(new_nodes))
    if new_links:
        new_body += "\n<ul class=\"links\">" + "".join("<li><code>{}</code></li>".format(esc(l)) for l in new_links[:300]) + "</ul>"
    with open(os.path.join(ROOT, "newly-discovered-nodes", today + ".html"), "w", encoding="utf-8") as f:
        f.write(NEW_TMPL.format(site_name=SITE_NAME, site_title=SITE_TITLE, base_url=BASE_URL,
                                today=today, stamp=stamp, new_body=new_body,
                                page_title="{}月{}日新发现节点更新".format(today[4:6], today[6:]),
                                description="新发现免费clash/v2ray节点 {} 个，每日自动更新。".format(len(new_nodes))))

    # 首页
    pages = sorted(glob.glob(os.path.join(ROOT, "free-nodes", "*.html")))
    recent = [os.path.basename(p)[:-5] for p in pages][-30:]
    recent_links = "\n".join('<li><a href="/free-nodes/{0}.html">{1}-{2}-{3} 节点更新</a></li>'.format(
        r, r[:4], r[4:6], r[6:]) for r in reversed(recent))
    sub_links = "\n".join([
        "<h3>免费Clash节点订阅链接</h3>\n<ul class=\"links\">" + links_ul(yaml_urls) + "</ul>",
        "<h3>免费V2ray节点订阅链接</h3>\n<ul class=\"links\">" + links_ul(txt_urls) + "</ul>",
        "<h3>免费Sing-box节点订阅链接</h3>\n<ul class=\"links\">" + links_ul([sb_url]) + "</ul>",
    ])
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(INDEX_TMPL.format(base_url=BASE_URL, stamp=stamp, today=today, sub_links=sub_links,
                                  description=description, site_title=SITE_TITLE,
                                  node_count=len(uniq), recent_links=recent_links,
                                  y=today[:4], m=today[4:6], d=today[6:]))

    # sitemap
    entries = [("/", "daily", "1.0"), ("/client.htm", "weekly", "0.8"),
               ("/about-us.htm", "weekly", "0.6"), ("/disclaimer.htm", "monthly", "0.5"),
               ("/privacy.htm", "monthly", "0.5")]
    entries += [("/free-nodes/{}.html".format(r), "monthly", "0.7") for r in reversed(recent)]
    d = now8().strftime("%Y-%m-%d")
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "\n".join("<url><loc>{}</loc><lastmod>{}</lastmod><changefreq>{}</changefreq><priority>{}</priority></url>".format(
        BASE_URL + loc, d, cf, pr) for loc, cf, pr in entries)
    sm += "\n</urlset>\n"
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sm)

    # README
    readme = ["# {s} | {m}月{d}日|免费Singbox节点/V2ray节点/Clash节点/SSR节点订阅分享 更新时间 {t}".format(
        s=SITE_NAME, m=today[4:6], d=today[6:], t=stamp)]
    readme.append("\n所有免费clash节点都爬取自网络，请勿用于非法用途 。节点地址：[点击跳转]({})\n".format(BASE_URL))
    readme.append("## clash使用教程：\n\n[科学上网详细教程]({}/client.htm)\n".format(BASE_URL))
    readme.append("## 订阅链接：\n")
    readme.append("### 免费Clash节点订阅链接\n")
    readme += ["- [{}]({})".format(u, u) for u in yaml_urls]
    readme.append("\n### 免费V2ray节点订阅链接\n")
    readme += ["- [{}]({})".format(u, u) for u in txt_urls]
    readme.append("\n### 免费Sing-box节点订阅链接\n")
    readme += ["- [{}]({})".format(u, u) for u in [sb_url]]
    readme.append("\n## 今日更新\n")
    readme.append("[{y}-{m}-{d} 完整节点列表]({b}/free-nodes/{t}.html)".format(
        y=today[:4], m=today[4:6], d=today[6:], b=BASE_URL, t=today))
    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(readme) + "\n")

    meta = {"updated": stamp, "count": len(uniq), "new": len(new_nodes),
            "clash": yaml_urls, "v2ray": txt_urls, "singbox": [sb_url]}
    json.dump(meta, open(data_dir + "meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("done:", stamp, "nodes:", len(uniq), "new:", len(new_nodes))


DAILY_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title} - {site_name}</title>
<meta name="description" content="{description}">
<meta name="keywords" content="免费clash节点,v2ray节点,singbox节点,clash订阅,免费机场">
<link rel="canonical" href="{base_url}/free-nodes/{today}.html">
<meta property="og:type" content="article">
<meta property="og:title" content="{page_title} - {site_name}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{base_url}/free-nodes/{today}.html">
<meta property="og:site_name" content="{site_name}">
<link rel="stylesheet" href="/assets/website/style.css">
</head>
<body>
<header><div class="wrap head"><a class="logo" href="/">{site_name}</a><span class="tagline">{site_title}</span></div></header>
<main class="wrap">
<h1>免费Singbox节点/V2ray节点/Shadowrocket节点/Clash节点/SSR节点订阅分享</h1>
<p>更新时间 {stamp}，当前已入库节点 <strong>{node_count}</strong> 个。{description}<a class="back" href="/">返回首页</a></p>
{daily_links}
<p class="note">Clash / V2ray / Sing-box 客户端导入对应格式的订阅链接即可使用。</p>
</main>
<footer><div class="wrap"><p>&copy; 2026 {site_name} · <a href="/about-us.htm">关于我们</a> · <a href="/disclaimer.htm">免责声明</a> · <a href="/privacy.htm">隐私协议</a></p></div></footer>
</body>
</html>
"""

NEW_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title} - {site_name}</title>
<meta name="description" content="{description}">
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{base_url}/newly-discovered-nodes/{today}.html">
<link rel="stylesheet" href="/assets/website/style.css">
</head>
<body>
<header><div class="wrap head"><a class="logo" href="/">{site_name}</a><span class="tagline">{site_title}</span></div></header>
<main class="wrap">
<h1>{today} 新发现节点</h1>
<p>更新时间 {stamp}</p>
{new_body}
</main>
<footer><div class="wrap"><p>&copy; 2026 {site_name} · <a href="/">首页</a></p></div></footer>
</body>
</html>
"""

INDEX_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site_title} 更新时间 {stamp}</title>
<meta name="description" content="{description}">
<meta name="keywords" content="免费clash节点订阅,clash免费节点,v2ray节点,singbox节点,免费机场节点分享,shadowrocket节点,ssr节点">
<meta name="robots" content="index,follow">
<link rel="canonical" href="{base_url}/">
<meta property="og:type" content="website">
<meta property="og:title" content="{site_title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{base_url}/">
<meta property="og:site_name" content="RU节点">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "RU节点",
  "url": "{base_url}/",
  "description": "{description}",
  "inLanguage": "zh-CN"
}}
</script>
<link rel="stylesheet" href="/assets/website/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9889;</text></svg>">
</head>
<body>
<header>
<div class="wrap head">
<a class="logo" href="/">RU节点</a>
<span class="tagline">免费 Clash / V2ray / Sing-box 节点订阅分享 · 每日更新</span>
</div>
<nav class="wrap">
<a href="/">首页</a><a href="/client.htm">使用教程</a><a href="/about-us.htm">关于我们</a><a href="/disclaimer.htm">免责声明</a><a href="/privacy.htm">隐私协议</a>
</nav>
</header>
<main class="wrap">
<h1>{site_title} 更新时间 {stamp}</h1>
<p>所有免费clash节点都爬取自网络，请勿用于非法用途。今日已入库节点 <strong>{node_count}</strong> 个。</p>
<section class="card">
<h2>今日节点详情</h2>
<p><a href="/free-nodes/{today}.html">点击查看 {y}-{m}-{d} 完整节点列表与订阅 →</a></p>
</section>
<section class="card">
<h2>订阅链接</h2>
{sub_links}
</section>
<section class="card">
<h2>历史更新</h2>
<ul class="links">{recent_links}</ul>
</section>
<section class="card">
<h2>clash使用教程</h2>
<p>详见 <a href="/client.htm">客户端使用教程</a>，Clash / V2ray / Sing-box 客户端导入对应格式的订阅链接即可一键更新节点。</p>
</section>
</main>
<footer><div class="wrap"><p>&copy; 2026 RU节点 · <a href="/about-us.htm">关于我们</a> · <a href="/disclaimer.htm">免责声明</a> · <a href="/privacy.htm">隐私协议</a></p></div></footer>
</body>
</html>
"""


if __name__ == "__main__":
    main()
