# -*- coding: utf-8 -*-
"""抓取公共免费节点，生成 Clash / V2ray / Sing-box 订阅与站点内容（stairnode 博客模板风格）"""
import base64
import glob
import json
import os
import random
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import yaml

BASE_URL = "https://lorenzazy7kenyon.github.io"
SITE_NAME = "Free Clash"
SITE_FULL = "Free Clash 免费节点 机场订阅中文站"
SITE_TITLE = "Free Clash | 2026免费V2ray/Clash/SSR节点推荐"
SITE_DESC = "提供最新 Free Clash 免费节点资源，支持Clash、SSR协议，附详细教程和配置指南。"
ROOT = os.path.dirname(os.path.abspath(__file__))
TZ = timezone(timedelta(hours=8))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# 推荐机场：如需展示付费机场推广，在此填写 ("名称","注册链接","简介")，留空则不展示
AIRPORTS = []

BACKFILL_DAYS = 30  # 首次运行向前回填的每日文章天数

# 每篇文章 slug 轮换的关键词（参考站做法：URL 覆盖不同搜索词）
KW_POOL = ["free-clash-node", "free-v2ray-subscribe", "free-ssr-node", "free-singbox-node",
           "shadowrocket-node", "trojan-node-share", "free-node-subscribe", "clash-v2ray-ss-ssr",
           "free-high-speed-nodes", "node-share-links", "free-v2ray-clash-subscribe", "free-shadowrocket-node"]

PROTO_POOL = ["Clash", "V2ray", "Singbox", "SSR", "Trojan", "Shadowrocket"]

TIPS = [
    "免费节点时效性很短，建议每天更新一次订阅，出现大面积超时就到首页拿最新订阅链接重新导入。",
    "使用「自动选择」分组时，客户端会自动测速切换到最低延迟节点，比手动挑选更省心。",
    "节点名称中的国旗代表落地地区，看视频建议选日本、新加坡、韩国等近距离节点，延迟更低。",
    "如果订阅无法下载，可能是运营商屏蔽了 GitHub Pages，先连接任意可用节点后再更新订阅。",
    "Trojan 与 Hysteria2 协议抗干扰能力更强，优先使用这两类节点通常更稳定。",
    "免费节点属于公共资源，切勿登录网银、社交账号等敏感服务，注意隐私安全。",
    "客户端开启「允许局域网连接」后，同一网络下的电视、盒子等设备也能共享代理。",
    "遇到部分网站无法打开，尝试切换不同地区节点，或检查客户端分流规则是否为全局模式。",
    "Sing-box 订阅与 Clash 订阅内容一致，只是格式不同，选对应客户端支持的格式导入即可。",
    "每天多次更新会让节点池产生少量波动，更新订阅后旧节点消失是正常现象。",
]


def slug_for(dd):
    y, m, d = dd[:4], int(dd[5:7]), int(dd[8:10])
    kw = KW_POOL[int(dd.replace("-", "")) % len(KW_POOL)]
    return "{}-{}-{}-{}".format(kw, y, m, d)


def proto_counts(nodes):
    c = {}
    for p in nodes:
        c[p["type"]] = c.get(p["type"], 0) + 1
    return c


def proto_para(protocols):
    if not protocols:
        return ""
    names = {"vmess": "VMess", "vless": "VLESS", "ss": "Shadowsocks", "trojan": "Trojan", "hysteria2": "Hysteria2"}
    parts = ["{}节点 {} 个".format(names.get(k, k), v) for k, v in sorted(protocols.items(), key=lambda x: -x[1])]
    return "<p>本次节点协议分布：{}。</p>".format("、".join(parts))

SOURCES = [
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt",
    "https://raw.githubusercontent.com/freefq/free/master/v2",
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.txt",
    "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
]

LINK_RE = re.compile(r"(?:vmess|vless|trojan|trojan-go|ss|hysteria2|hys2)://[^\s\"'<>\[\]]+")

REGION_MAP = [
    (r"🇺🇸|美国|US[A-]|America", "美国"), (r"🇭🇰|香港|HK[A-]|Hong", "香港"),
    (r"🇯🇵|日本|JP[A-]|Japan", "日本"), (r"🇸🇬|新加坡|SG[A-]|Singapore", "新加坡"),
    (r"🇹🇼|台湾|TW[A-]|Taiwan", "台湾"), (r"🇰🇷|韩国|KR[A-]|Korea", "韩国"),
    (r"🇬🇧|英国|UK[A-]|United Kingdom", "英国"), (r"🇩🇪|德国|DE[A-]", "德国"),
    (r"🇫🇷|法国|FR[A-]", "法国"), (r"🇷🇺|俄罗斯|俄罗斯|RU[A-]|Russia", "俄罗斯"),
    (r"🇨🇦|加拿大|CA[A-]", "加拿大"), (r"🇦🇺|澳大利亚|AU[A-]", "澳大利亚"),
    (r"🇳🇱|荷兰|NL[A-]", "荷兰"), (r"🇹🇷|土耳其|TR[A-]", "土耳其"),
    (r"🇮🇳|印度|IN[A-]", "印度"), (r"🇲🇾|马来西亚|MY[A-]", "马来西亚"),
    (r"🇹🇭|泰国|TH[A-]", "泰国"), (r"🇻🇳|越南|VN[A-]", "越南"),
    (r"🇵🇭|菲律宾|PH[A-]", "菲律宾"), (r"🇧🇷|巴西|BR[A-]", "巴西"),
]


def now8():
    return datetime.now(TZ)


def stamp_str(dt=None):
    dt = dt or now8()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


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
        proxy["ws-opts"] = {"path": j.get("path", "/"),
                            "headers": {"Host": [j.get("host", "")]} if j.get("host") else {}}
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
        "type": "ss", "server": server, "port": int(port or 0),
        "cipher": method, "password": password, "udp": True,
    }


def parse_trojan(link):
    u = urllib.parse.urlparse(link)
    q = dict(urllib.parse.parse_qsl(u.query or "", keep_blank_values=True))
    host = u.hostname or ""
    return {
        "name": urllib.parse.unquote(u.fragment) if u.fragment else host + ":" + str(u.port),
        "type": "trojan", "server": host, "port": u.port or 443,
        "password": urllib.parse.unquote(u.username or ""),
        "sni": q.get("sni") or q.get("peer") or host,
        "skip-cert-verify": True, "udp": True,
    }


def parse_vless(link):
    u = urllib.parse.urlparse(link)
    q = dict(urllib.parse.parse_qsl(u.query or "", keep_blank_values=True))
    net = q.get("type", "tcp")
    proxy = {
        "name": urllib.parse.unquote(u.fragment) if u.fragment else str(u.hostname) + ":" + str(u.port),
        "type": "vless", "server": u.hostname or "", "port": u.port or 0,
        "uuid": urllib.parse.unquote(u.username or ""),
        "tls": q.get("security", "none") != "none",
        "servername": q.get("sni") or q.get("host") or "",
        "network": "http" if net in ("http", "xhttp") else net, "udp": True,
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
        "type": "hysteria2", "server": host, "port": u.port or 443,
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
    if q.get("type") == "ssr":
        q = {**q, "type": "ss"}
    return q if q.get("type") in ("vmess", "vless", "ss", "trojan", "hysteria2") else None


def export_links(proxies):
    links = []
    for p in proxies:
        t = p.get("type")
        try:
            if t == "vmess":
                wo = p.get("ws-opts") or {}
                hh = (wo.get("headers") or {}).get("Host", [])
                j = {"v": "2", "ps": p["name"], "add": p["server"], "port": str(p["port"]),
                     "id": p.get("uuid", ""), "aid": str(int(p.get("alterId", 0) or 0)),
                     "scy": p.get("cipher", "auto"),
                     "net": "ws" if p.get("network") == "http" else p.get("network", "tcp"),
                     "type": "none",
                     "host": (hh[0] if hh else "") or p.get("servername", ""),
                     "path": p.get("ws-opts", {}).get("path", "/") if p.get("ws-opts") else "",
                     "tls": "tls" if p.get("tls") else "", "sni": p.get("servername", "")}
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
                net = "ws" if p.get("network") == "http" else p.get("network", "tcp")
                qq = "type={}&security={}".format(net, "tls" if p.get("tls") else "none")
                if p.get("servername"):
                    qq += "&sni=" + urllib.parse.quote(str(p["servername"]))
                if p.get("ws-opts"):
                    qq += "&path=" + urllib.parse.quote(p["ws-opts"].get("path", "/") or "/")
                    hh = p["ws-opts"].get("headers", {}).get("Host", [])
                    if hh:
                        qq += "&host=" + urllib.parse.quote(hh[0])
                links.append("vless://{}@{}:{}?{}#{}".format(p.get("uuid", ""), p["server"], p["port"], qq, urllib.parse.quote(p["name"])))
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
        "port": 7890, "socks-port": 7891, "allow-lan": False, "mode": "rule", "log-level": "warning",
        "dns": {"enable": True,
                "nameserver": ["https://dns.alidns.com/dns-query", "https://doh.pub/dns-query"],
                "fallback": ["https://1.1.1.1/dns-query"]},
        "proxies": proxies, "proxy-groups": groups,
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


def regions_of(proxies, limit=7):
    found = []
    joined = " ".join(str(p.get("name", "")) for p in proxies)
    for pat, cn in REGION_MAP:
        if re.search(pat, joined, re.IGNORECASE) and cn not in found:
            found.append(cn)
        if len(found) >= limit:
            break
    return found or ["全球"]


IMG_CYCLE = ["image_1.jpg", "image_2.jpg", "image_3.jpg"]


def thumb_of(i):
    return "/assets/website/img/stairnode/" + IMG_CYCLE[i % len(IMG_CYCLE)]


def render(tpl, **kw):
    out = tpl
    for k, v in kw.items():
        out = out.replace("@@%s@@" % k, str(v))
    out = re.sub(r"@@[a-z_0-9]+@@", "", out)
    return out


def clean_old_uploads(keep_months=2):
    updir = os.path.join(ROOT, "uploads")
    today = now8()
    valid = set()
    yy, mm = today.year, today.month
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
                    import shutil
                    shutil.rmtree(mdir, ignore_errors=True)
            if not os.listdir(ydir):
                os.rmdir(ydir)

# ============================ 模板（stairnode 博客风格） ============================

HEAD_TPL = """<!DOCTYPE html>
<html xml:lang="zh-CN" lang="zh-CN">
<head>
    <meta name="google-site-verification" content="p7ah5V_-k_15Rm-VniFY1K0iOh5KxQIjKCNwqV9geKI" />
    <link rel="canonical" href="@@canonical@@" />
    <title>@@title@@</title>
    <meta name="keywords" content="@@keywords@@" />
    <meta name="description" content="@@description@@" />
    <link rel="icon" href="/assets/website/img/stairnode/favicon.ico" type="image/x-icon"/>
    <meta name="author" content="@@site_full@@">
    <meta property="og:type" content="@@og_type@@" />
    <meta property="og:url" content="@@canonical@@" />
    <meta property="og:site_name" content="@@site_full@@" />
    <meta property="og:title" content="@@title@@" />
    <meta property="og:image" content="/assets/website/img/stairnode/favicon.ico" />
    <meta property="og:description" content="@@description@@" />
    <meta name="applicable-device" content="pc,mobile" />
    <meta name="renderer" content="webkit" />
    <meta name="force-rendering" content="webkit" />
    <meta http-equiv="Cache-Control" content="no-transform" />
    <meta name="robots" content="@@robots@@" />
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black">
    <meta name="apple-mobile-web-app-title" content="@@title@@">
    <meta name="format-detection" content="telephone=no">
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <link href="https://fonts.googleapis.com/css?family=Poppins:100,200,300,400,500,600,700,800,900" rel="stylesheet">
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css">
    <link rel="stylesheet" href="/assets/website/css/stairnode/animate.css">
    <link rel="stylesheet" href="/assets/website/css/stairnode/owl.carousel.min.css">
    <link rel="stylesheet" href="/assets/website/css/stairnode/owl.theme.default.min.css">
    <link rel="stylesheet" href="/assets/website/css/stairnode/magnific-popup.css">
    <link rel="stylesheet" href="/assets/website/css/stairnode/flaticon.css">
    <link rel="stylesheet" href="/assets/website/css/stairnode/style.css">
    <link rel="stylesheet" href="/assets/website/css/G.css" />
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"WebSite","name":"@@site_name@@","url":"@@base_url@@/","description":"@@description@@","inLanguage":"zh-CN"}
</script>
</head>
<body data-page="@@page@@" data-site="@@base_url@@">
@@nav@@
"""

NAV_TPL = """    <nav class="navbar navbar-expand-lg navbar-dark bg-dark ftco-navbar-light site-navbar-target" id="ftco-navbar">
        <div class="container">
            <a class="navbar-brand" href="/">@@brand_tag@@</a>
            <button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#ftco-nav" aria-controls="ftco-nav" aria-expanded="false" aria-label="Toggle navigation">
                <span class="oi oi-menu"></span> Menu
            </button>
            <div class="collapse navbar-collapse" id="ftco-nav">
                <ul class="navbar-nav nav">
                    <li class="nav-item"><a href="/" class="nav-link"><span>首页</span></a></li>
                    <li class="nav-item"><a href="/free-nodes/" class="nav-link"><span>免费节点</span></a></li>
                    <li class="nav-item"><a href="/paid-subscribe/" class="nav-link"><span>推荐机场</span></a></li>
                    <li class="nav-item"><a href="/news/" class="nav-link"><span>新闻资讯</span></a></li>
                    <li class="nav-item"><a href="/client.htm" class="nav-link"><span>客户端</span></a></li>
                </ul>
            </div>
        </div>
    </nav>
"""

HERO_TPL = """    <section id="home-section" class="hero">
        <div class="home-slider owl-carousel">
            <div class="slider-item">
                <div class="overlay"></div>
                <div class="container-fluid px-md-0">
                    <div class="row d-flex no-gutters slider-text align-items-end justify-content-end">
                        <div class="one-third order-md-last img" style="background-image:url(/assets/website/img/stairnode/bg_2.jpg);">
                            <div class="overlay"></div>
                            <div class="overlay-1"></div>
                        </div>
                        <div class="one-forth d-flex align-items-center">
                            <div class="text">
                                <h2 class="mb-4 mt-3">@@hero_title@@</h2>
                                <span class="subheading">@@hero_sub@@</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
"""

HERO2_TPL = """    <section class="hero-wrap hero-wrap-2" style="background-image: url('@bg@');" data-stellar-background-ratio="0.5">
        <div class="overlay"></div>
        <div class="container">
            <div class="row no-gutters slider-text align-items-end justify-content-center">
                <div class="col-md-9 pb-5 text-center">
                    <p class="breadcrumbs">
                        <span class="mr-2"><a href="/">首页 <i class="fa fa-chevron-right"></i></a></span>
                        @@crumbs@@
                        <span>@@tail@@</span>
                    </p>
                    <h1 class="mb-0 bread">@@h1@@</h1>
                </div>
            </div>
        </div>
    </section>
"""

BLOG_ITEM_TPL = """<div class="row no-gutters item mb-3 xcblog-blog-item" data-date="@@date@@" style="padding-left:12px;">
    <div class="col-md-3 d-flex">
        <div class="img-about img d-flex">
            <div class="img">
                <a href="@@url@@" class="xcblog-blog-url"><img src="@@img@@" alt="@@tTitle@@" style="width: 100%;"></a>
            </div>
        </div>
    </div>
    <div class="col-md-9">
        <div class="px-3">
            <div class="row justify-content-start">
                <div class="col-md-12 heading-section">
                    <a href="@@url@@" class="xcblog-blog-url"><h3 class="mb-2 xcblog-blog-title" style="font-size: 1.5rem; text-transform: capitalize;">@@tTitle@@</h3></a>
                    <p style="margin-bottom: 0;">@@tDesc@@</p>
                </div>
            </div>
        </div>
    </div>
</div>"""

SIDEBAR_AD_TPL = """<div class="panel panel-default box right-ad-box">
    <div class="panel-heading"><h3 class="panel-title">特别推荐</h3></div>
    <div class="panel-body">
        <div class="row"><div class="text-center">
            <a href="@@ad_url@@" target="_blank" rel="nofollow noopener">
                <img src="@@ad_img@@" class="avatar" alt="@@ad_name@@">
            </a>
            <dl>
                <dt><a href="@@ad_url@@" target="_blank" rel="nofollow noopener">@@ad_name@@</a></dt>
                <dd>@@ad_desc@@</dd>
            </dl>
        </div></div>
    </div>
</div>"""

SIDEBAR_NOTES_TPL = """<div class="panel panel-default box right-ad-box">
    <div class="panel-heading"><h3 class="panel-title">免费订阅说明</h3></div>
    <div class="panel-body">
        <p style="font-size:14px;">所有免费节点均爬取自网络公开资源，每日自动更新。免费节点有效时间很短，遇到失效属于正常现象。</p>
        <p style="font-size:14px;">复制 <a href="/free-nodes/@@latest@@.htm">最新一天</a> 页面中的订阅链接，在 Clash / V2ray / Sing-box 客户端中添加即可。</p>
    </div>
</div>"""

SIDEBAR_HOT_TPL = """<div class="panel panel-default">
    <div class="panel-heading"><h3 class="panel-title">热门文章</h3></div>
    <div class="panel-body">
        <ul class="p-0 x-0" style="list-style: none;margin: 0;padding: 0;">@@items@@</ul>
    </div>
</div>"""

SIDEBAR_DATE_TPL = """<div class="panel panel-default">
    <div class="panel-heading"><h3 class="panel-title">归纳</h3></div>
    <div class="panel-body">
        <ul class="p-0 x-0" style="list-style: none;margin: 0;padding: 0;">
@@items@@
        </ul>
    </div>
</div>"""

SIDEBAR_TAGS_TPL = """<div class="panel panel-default">
    <div class="panel-heading"><h3 class="panel-title">标签</h3></div>
    <div class="panel-body">
        <a href="/free-nodes/" class="badge badge-info mr-1 mb-1" style="font-size:13px;">免费节点</a>
        <a href="/client.htm" class="badge badge-info mr-1 mb-1" style="font-size:13px;">使用教程</a>
        <a href="/paid-subscribe/" class="badge badge-info mr-1 mb-1" style="font-size:13px;">机场推荐</a>
        <a href="/news/" class="badge badge-info mr-1 mb-1" style="font-size:13px;">资讯</a>
    </div>
</div>"""

FOOTER_TPL = """    <footer class="ftco-footer ftco-section">
        <div class="container">
            <div class="row">
                <div class="col-md-12 text-center">
                    <p>本站内容仅供学习与技术研究用途，无意传播或倡导任何违反法律法规的行为。在此声明：用户须自行了解所在地法律法规，合法合规使用；因使用不当产生的法律责任，与本站及作者无关；请在使用前仔细阅读本声明，继续使用即视为同意以上条款。</p>
                    <p>
                        <a href="/">首页</a> |
                        <a href="/free-nodes/">免费节点</a> |
                        <a href="/paid-subscribe/">推荐机场</a> |
                        <a href="/news/">新闻资讯</a> |
                        <a href="/client.htm">客户端</a> |
                        <a href="/about-us.htm">关于我们</a> |
                        <a href="/disclaimer.htm">免责声明</a> |
                        <a href="/privacy.htm">隐私协议</a> |
                        <a href="/sitemap.xml">网站地图</a>
                    </p>
                    <p>@@site_full@@ 版权所有 Powered by GitHub Pages</p>
                </div>
            </div>
        </div>
    </footer>
    <div id="ftco-loader" class="show fullscreen"><svg class="circular" width="48px" height="48px">
            <circle class="path-bg" cx="24" cy="24" r="22" fill="none" stroke-width="4" stroke="#eeeeee" />
            <circle class="path" cx="24" cy="24" r="22" fill="none" stroke-width="4" stroke-miterlimit="10" stroke="#F96D00" /></svg></div>
    <script src="/assets/website/js/frontend/stairnode/jquery.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/jquery-migrate-3.0.1.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/popper.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/bootstrap.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/jquery.easing.1.3.js"></script>
    <script src="/assets/website/js/frontend/stairnode/jquery.waypoints.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/jquery.stellar.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/owl.carousel.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/jquery.magnific-popup.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/jquery.animateNumber.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/scrollax.min.js"></script>
    <script src="/assets/website/js/frontend/stairnode/main.js"></script>
</body>
</html>
"""

# ============================ 页面组装 ============================

def head(page, title, description, canonical, og_type="webpage", robots="index,follow"):
    keywords = "免费clash节点,免费v2ray节点,免费singbox节点,clash订阅,ssr节点,免费机场"
    return render(HEAD_TPL, page=page, title=title, description=description, keywords=keywords,
                  canonical=canonical, og_type=og_type, robots=robots, site_name=SITE_NAME,
                  site_full=SITE_FULL, base_url=BASE_URL,
                  nav=NAV_TPL.replace("@@brand_tag@@", "<h1>Free Clash 节点中心</h1>" if page == "index" else "<span>Free Clash 节点中心</span>"))


def blog_item(info):
    return render(BLOG_ITEM_TPL, date=info["date"], url=info["url"], img=info["img"],
                  tTitle=esc(info["title"]), tDesc=esc(info["desc"]))


def sidebar(latest_slug, hot_infos, months, ad=None):
    parts = []
    if ad:
        parts.append(render(SIDEBAR_AD_TPL, ad_url=ad["url"], ad_img=ad["img"], ad_name=esc(ad["name"]), ad_desc=esc(ad["desc"])))
    else:
        parts.append(render(SIDEBAR_NOTES_TPL, latest=latest_slug))
    parts.append(render(SIDEBAR_HOT_TPL, items="".join(
        '<li class="py-2"><a href="{}" title="{}">{}</a><hr /></li>'.format(esc(i["url"]), esc(i["title"]), esc(i["title"])) for i in hot_infos)))
    parts.append(render(SIDEBAR_DATE_TPL, items="".join(
        '  <li class="py-2">\n <h4><span class="badge" style="float: right;">{n}</span> <a href="{u}" title="{m} 归档">{m}</a></h4>\n </li>'.format(n=n, u=BASE_URL + "/date/" + m + "/", m=m) for m, n in months)))
    parts.append(SIDEBAR_TAGS_TPL)
    return "".join(parts)


def layout_section(col9, side, extra_class="ftco-about ftco-section ftco-no-pt ftco-no-pb my-5"):
    return "    <section class=\"%s\" id=\"about-section\">\n        <div class=\"container\">\n            <div class=\"row\">\n                <div class=\"col-md-9\">\n%s\n                </div>\n                <div class=\"col-md-3\">\n%s\n                </div>\n            </div>\n        </div>\n    </section>" % (extra_class, col9, side)


def hero_index(title, sub):
    return render(HERO_TPL, hero_title=esc(title), hero_sub=esc(sub))


def hero2(h1, crumbs="", tail="", bg="/assets/website/img/stairnode/bg_4.jpg"):
    return render(HERO2_TPL, h1=h1, crumbs=crumbs, tail=tail, bg=bg)


def days_load():
    path = os.path.join(ROOT, "data", "days.json")
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return {}


def days_save(d):
    path = os.path.join(ROOT, "data", "days.json")
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def subs_cell(urls):
    return "\n".join("<p>{}</p>".format(esc(u)) for u in urls)


def airports_block(count):
    if not AIRPORTS:
        return ""
    out = []
    for name, url, desc in AIRPORTS[:5]:
        out.append('<h3>高端机场推荐 「<a href="{u}" target="_blank" rel="nofollow noopener" style="color:red;">{n}</a>」</h3>'.format(u=esc(url), n=esc(name)))
        out.append("<p>{}</p>".format(esc(desc)))
        out.append('<p style="margin-bottom:3rem;color:#999;font-style:italic;">注：跳转链接可能会 <b style="color:red;">被墙</b> ，如多次打开失败，请先使用下面不稳定免费订阅后，再尝试点击链接</p>')
    return "".join(out)


def article_of(day_info, date, slug, idx, total):
    m, d = date[5:7], date[8:10]
    protos = PROTO_POOL[idx % len(PROTO_POOL):] + PROTO_POOL[:idx % len(PROTO_POOL)]
    title = "{} | {}月{}日{c}|免费{}节点/{}节点/{}节点/{}节点/{}节点/{}节点订阅分享".format(
        SITE_NAME, int(m), int(d), c=str(day_info["count"]) + "个" if day_info.get("count") else "",
        *[p for p in protos])
    desc = "这一次的节点更新覆盖了{r}等地区。只需复制下方的Clash节点/V2ray节点和singbox节点订阅链接,在客户端添加后即可正常使用。".format(
        r="、".join(day_info.get("regions", [])))
    stamp = frame = datetime.strptime(date, "%Y-%m-%d")
    return {
        "date": date, "slug": slug, "url": "{}/free-nodes/{}.htm".format(BASE_URL, slug),
        "img": thumb_of(idx), "title": title, "desc": desc, "count": day_info.get("count", 0),
        "regions": day_info.get("regions", []), "stamp": date,
    }


def url_of(slug):
    return BASE_URL + "/free-nodes/" + slug + ".htm"

# ============================ 主流程 ============================

def main():
    date_full = now8().strftime("%Y-%m-%d")
    today_slug = slug_for(date_full)
    ysn, msn = date_full[:4], date_full[5:7]
    stamp = stamp_str()

    raw_texts, links, clash_dicts = [], set(), []
    for url in SOURCES:
        text = fetch(url)
        if not text:
            continue
        if url.endswith(".yaml"):
            raw_texts.append(("", url, text))
        else:
            raw_texts.append((maybe_b64(text), url, text))

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

    proxies = [c for c in (from_clash_proxy(p) for p in clash_dicts) if c]
    for lk in links:
        p = parse_link(lk)
        if p and p.get("server") and p.get("port"):
            proxies.append(p)

    seen = set()
    uniq = []
    for p in proxies:
        key = "{type}|{server}|{port}|{secret}".format(
            type=p["type"], server=p["server"], port=p["port"], secret=p.get("uuid") or p.get("password") or "")
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

    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    days = days_load()
    days[date_full] = {"count": len(uniq), "regions": regions_of(uniq), "protocols": proto_counts(uniq)}

    # 回填历史每日文章（确定性洗牌，每天独立订阅文件）
    day_nodes_by_date = {}
    for back in range(BACKFILL_DAYS, 0, -1):
        dd = (now8() - timedelta(days=back)).strftime("%Y-%m-%d")
        if dd in days and days[dd].get("backfill") and dd in day_nodes_by_date:
            continue
        if dd in days and not days[dd].get("backfill"):
            continue
        rnd = random.Random(dd)
        idx = list(range(len(uniq)))
        rnd.shuffle(idx)
        day_nodes_by_date[dd] = [uniq[j] for j in idx]
        days[dd] = {"count": len(day_nodes_by_date[dd]), "regions": regions_of(day_nodes_by_date[dd]),
                    "protocols": proto_counts(day_nodes_by_date[dd]), "backfill": True}
        b_ysn, b_msn = dd[:4], dd[5:7]
        b_dir = os.path.join(ROOT, "uploads", b_ysn, b_msn)
        os.makedirs(b_dir, exist_ok=True)
        b_links = export_links(day_nodes_by_date[dd])
        open(os.path.join(b_dir, "0-{}.yaml".format(dd.replace("-", ""))), "w", encoding="utf-8").write(
            clash_yaml(day_nodes_by_date[dd]))
        open(os.path.join(b_dir, "0-{}.txt".format(dd.replace("-", ""))), "w", encoding="utf-8").write(
            base64.b64encode("\n".join(b_links).encode()).decode() + "\n")
        b_obs, b_tags = [], set()
        for p in day_nodes_by_date[dd]:
            ob = singbox_outbound(p)
            if ob and ob["tag"] not in b_tags:
                b_tags.add(ob["tag"])
                b_obs.append(ob)
        b_cfg = {
            "log": {"level": "warn", "timestamp": True},
            "dns": {"servers": [{"tag": "remote", "address": "https://1.1.1.1/dns-query"},
                                {"tag": "local", "address": "https://dns.alidns.com/dns-query"}]},
            "outbounds": [{"type": "urltest", "tag": "自动选择", "interval": "5m",
                           "outbounds": [o["tag"] for o in b_obs]}] + b_obs + [{"type": "direct", "tag": "direct"}],
        }
        open(os.path.join(b_dir, "{}.json".format(dd.replace("-", ""))), "w", encoding="utf-8").write(
            json.dumps(b_cfg, ensure_ascii=False, indent=1))
    days_save(days)

    upload_dir = os.path.join(ROOT, "uploads", ysn, msn)
    os.makedirs(upload_dir, exist_ok=True)

    yaml_urls, txt_urls = [], []
    for i in range(5):
        chunk = uniq[i::5]
        ynf = "{}-{}-free-node.yaml".format(i, date_full.replace("-", ""))
        tnf = "{}-{}-free-node.txt".format(i, date_full.replace("-", ""))
        open(os.path.join(upload_dir, ynf), "w", encoding="utf-8").write(clash_yaml(chunk))
        cl = "\n".join(export_links(chunk))
        open(os.path.join(upload_dir, tnf), "w", encoding="utf-8").write(
            base64.b64encode(cl.encode()).decode() + "\n")
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
    sbf = "{}-free-node.json".format(date_full.replace("-", ""))
    open(os.path.join(upload_dir, sbf), "w", encoding="utf-8").write(json.dumps(sb_cfg, ensure_ascii=False, indent=1))
    sb_url = "{}/uploads/{}/{}/{}".format(BASE_URL, ysn, msn, sbf)
    clean_old_uploads()

    # ---------- 页面构建 ----------
    day_dates = sorted(days.keys())

    arts = {}
    for i, dd in enumerate(day_dates):
        slug = slug_for(dd)
        arts[dd] = article_of(days[dd], dd, slug, i, len(day_dates))
    latest = arts[day_dates[-1]]

    ad = None
    if AIRPORTS:
        name, aurl, desc = AIRPORTS[0]
        ad = {"name": name, "url": aurl, "desc": desc, "img": "/assets/website/img/G/xingchen.webp"}

    def side_html(latest_slug, today_subs):
        sampled = [arts[d] for d in day_dates[-28:]]
        random.Random(7).shuffle(sampled)
        months = []
        month_counts = {}
        for dd in day_dates:
            month_counts.setdefault(dd[:7], 0)
            month_counts[dd[:7]] += 1
        for m in sorted(month_counts, reverse=True):
            months.append((m, month_counts[m]))
        return sidebar(latest_slug, sampled[-10:], months, ad=ad)

    # 旧文件清理
    for pat in (os.path.join(ROOT, "free-nodes", "*.htm"),
                os.path.join(ROOT, "newly-discovered-nodes", "*.htm")):
        for f in glob.glob(pat):
            os.remove(f)

    # ---- index.html ----
    blog_list = "".join(blog_item(dict(arts[dd], url=url_of(slug_for(dd)))) for dd in reversed(day_dates[-20:]))
    col9 = "<h2>最近更新文章</h2>\n<div class=\"xcblog-blog-list\">\n" + blog_list + "\n</div>"
    html = head("index", SITE_TITLE, SITE_DESC, BASE_URL + "/")
    html += hero_index("{}最新免费V2ray/Clash节点分享".format(ysn),
                       "包含美国、日本、台湾、香港、新加坡等节点，提供完整教程，帮助用户快速搭建翻墙环境。")
    html += layout_section(col9, side_html(today_slug, None)) + FOOTER_TPL
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(html)

    def day_subs_url(dd, ext):
        compact = dd.replace("-", "")
        if dd == date_full:
            root_u = "{}/uploads/{}/{}/".format(BASE_URL, ysn, msn)
            if ext == "json":
                return [root_u + "{}-free-node.json".format(compact)]
            return [root_u + "{}-{}-free-node.{}".format(i, compact, ext) for i in range(5)]
        root_u = "{}/uploads/{}/{}/".format(BASE_URL, dd[:4], dd[5:7])
        if ext == "json":
            return [root_u + "{}.json".format(compact)]
        return [root_u + "0-{}.{}".format(compact, ext)]

    # ---- 今日文章页 ----
    for dd in day_dates:
        a = arts[dd]
        sl = a["slug"]
        prev_a = arts.get(day_dates[day_dates.index(dd) - 1]) if day_dates.index(dd) > 0 else None
        next_a = arts.get(day_dates[day_dates.index(dd) + 1]) if day_dates.index(dd) < len(day_dates) - 1 else None
        m, dcount = dd[5:7], a["count"]
        mdt = datetime.strptime(dd, "%Y-%m-%d")
        intro = "<p>今天是{}年{}月{}日，继续给大家带来最新免费节点，已全部合并到下方的订阅链接中，添加到客户端即可使用，节点数量一共{}个，地区包含了{}，节点已全部去重整理。</p>".format(
            dd[:4], int(m), mdt.day, dcount, "、".join(a["regions"]))
        unique = proto_para(days[dd].get("protocols", {})) + "<p>" + TIPS[day_dates.index(dd) % len(TIPS)] + "</p>"
        subs = ("<h2>订阅文件链接</h2>\n"
                "<p><strong>Clash订阅链接</strong></p>\n" + subs_cell(day_subs_url(dd, "yaml")) + "\n"
                "<p><strong>V2ray订阅链接:</strong></p>\n" + subs_cell(day_subs_url(dd, "txt")) + "\n"
                "<p><strong>Sing-Box订阅链接</strong></p>\n" + subs_cell(day_subs_url(dd, "json")) + "\n")
        use = ("<h2>使用必看</h2>\n"
               "<p>全部节点信息均来自互联网收集，且用且珍惜。仅针对用于学习研究的用户分享，请勿随意传播其他信息。免费节点有效时间比较短，遇到失效是正常现象。</p>")
        navp = ""
        if prev_a:
            navp += "<p>上一个：<a href=\"{}.htm\">{}</a></p>".format(prev_a["slug"], esc(prev_a["title"]))
        if next_a:
            navp += "<p>下一个：<a href=\"{}.htm\">{}</a></p>".format(next_a["slug"], esc(next_a["title"]))
        rec = [arts[d2] for d2 in day_dates if d2 != dd][-10:][::-1]
        rec_panel = ('<div class="panel panel-default mt-5"><div class="panel-heading"><h3 class="m-0">推荐文章</h3></div>'
                     '<div class="panel-body"><ul class="p-0 x-0">'
                     + "".join('<li class="py-2"><a href="{}.htm">{}</a></li>'.format(r["slug"], esc(r["title"])) for r in rec)
                     + "</ul></div></div>")
        col9 = intro + unique + airports_block(1) + subs + use + '<div class="col-md-12 mt-5">' + navp + "</div>" + rec_panel
        crumbs = '<span class="mr-2"><a href="/free-nodes/">免费节点 <i class="fa fa-chevron-right"></i></a></span> '
        doc = head("detail", a["title"] + " - " + SITE_NAME, a["desc"], a["url"], og_type="article")
        doc += hero2(a["title"], crumbs=crumbs, tail="正文")
        doc += layout_section(col9, side_html(sl, None)) + FOOTER_TPL
        open(os.path.join(ROOT, "free-nodes", sl + ".htm"), "w", encoding="utf-8").write(doc)

    # ---- free-nodes 列表页 ----
    col9 = "".join(blog_item(dict(a, url=url_of(a["slug"]))) for a in reversed(list(arts.values())[-90:]))
    col9 = '<div class="xcblog-blog-list">' + col9 + "</div>"
    doc = head("list", "免费节点 - " + SITE_NAME, "免费clash节点、免费v2ray节点、免费singbox节点每日更新分享。", BASE_URL + "/free-nodes/")
    doc += hero2("免费节点")
    doc += layout_section(col9, side_html(today_slug, None)) + FOOTER_TPL
    open(os.path.join(ROOT, "free-nodes", "index.html"), "w", encoding="utf-8").write(doc)

    # ---- date 归档页 ----
    month_counts = {}
    month_map = {}
    for dd in day_dates:
        mkey = dd[:7]
        month_counts[mkey] = month_counts.get(mkey, 0) + 1
        month_map.setdefault(mkey, 0)
        month_map[mkey] += 1
    for mkey, n in month_map.items():
        items = [arts[dd] for dd in day_dates if dd.startswith(mkey)]
        col9 = '<div class="xcblog-blog-list">' + "".join(blog_item(dict(a, url=url_of(a["slug"]))) for a in reversed(items)) + "</div>"
        doc = head("list", mkey + " 归档 - " + SITE_NAME, mkey + " 免费节点每日更新归档。", BASE_URL + "/date/" + mkey + "/")
        doc += hero2(mkey + " 归档")
        doc += layout_section(col9, side_html(today_slug, None)) + FOOTER_TPL
        os.makedirs(os.path.join(ROOT, "date", mkey), exist_ok=True)
        open(os.path.join(ROOT, "date", mkey, "index.html"), "w", encoding="utf-8").write(doc)

    # ---- paid-subscribe ----
    if AIRPORTS:
        body = "".join('<div class="panel panel-default"><div class="panel-heading"><h3 class="panel-title">高端机场推荐 {} 「<a href="{u}" target="_blank" rel="nofollow noopener" style="color:red;">{n}</a>」</h3></div><div class="panel-body"><p>{d}</p><p>网站注册地址：【<a href="{u}" target="_blank" rel="nofollow noopener" style="color:#ff0000;">{n}（点击注册）</a>】</p></div></div>'.format(i + 1, u=esc(u), n=esc(nm), d=esc(desc)) for i, (nm, u, desc) in enumerate(AIRPORTS))
        intro = "<p>以下是我们甄别后收录的付费机场（高速、稳定、适合重度用户）。免费节点仅能满足轻度使用，如需更稳定服务可选择付费机场。</p>"
    else:
        body = ('<div class="panel panel-default"><div class="panel-heading"><h3 class="panel-title">暂无推荐</h3></div>'
                '<div class="panel-body"><p>暂未收录推荐机场。本站以免费节点分享为主，免费节点每日更新，请访问 <a href="/">首页</a> 获取。</p>'
                '<p class="note" style="color:#888;font-size:13px;">（站点管理员可编辑仓库中 main.py 的 AIRPORTS 配置项添加推荐机场，页面会自动生成。）</p></div></div>')
        intro = "<p>免费节点已可满足一般使用需求，推荐直接使用每天更新的免费订阅。</p>"
    col9 = intro + body
    doc = head("list", "推荐机场 - " + SITE_NAME, "高速稳定机场推荐，适合对速度和稳定性有更高要求的用户。", BASE_URL + "/paid-subscribe/")
    doc += hero2("推荐机场")
    doc += layout_section(col9, side_html(today_slug, None)) + FOOTER_TPL
    os.makedirs(os.path.join(ROOT, "paid-subscribe"), exist_ok=True)
    open(os.path.join(ROOT, "paid-subscribe", "index.html"), "w", encoding="utf-8").write(doc)

    # ---- news ----
    col9 = '<h2>新闻资讯</h2><p>本栏目汇总每日免费节点更新动态与使用技巧，近期更新如下：</p>' + '<div class="xcblog-blog-list">' + "".join(
        blog_item(dict(arts[dd], url=url_of(arts[dd]["slug"]))) for dd in reversed(day_dates[-20:])) + "</div>"
    doc = head("list", "新闻资讯 - " + SITE_NAME, "免费节点每日更新动态与客户端使用技巧资讯。", BASE_URL + "/news/")
    doc += hero2("新闻资讯")
    doc += layout_section(col9, side_html(today_slug, None)) + FOOTER_TPL
    os.makedirs(os.path.join(ROOT, "news"), exist_ok=True)
    open(os.path.join(ROOT, "news", "index.html"), "w", encoding="utf-8").write(doc)

    # ---- 新发现节点页 ----
    hist_path = os.path.join(ROOT, "data", "history.json")
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
    date_compact = date_full.replace("-", "")
    os.makedirs(os.path.join(ROOT, "newly-discovered-nodes"), exist_ok=True)
    new_links = export_links(new_nodes)
    new_body = "<p>本次运行新发现 <strong>{}</strong> 个节点。</p>".format(len(new_nodes))
    if new_links:
        new_body += '<ul class="xcblog-blog-list" style="list-style:none;padding:0;">' + "".join(
            '<li style="word-break:break-all;"><code>{}</code></li>'.format(esc(l)) for l in new_links[:300]) + "</ul>"
    newdoc = head("detail", "{} 新发现节点 - ".format(date_full) + SITE_NAME,
                  "新发现免费clash/v2ray节点 {} 个，每日自动更新。".format(len(new_nodes)),
                  "{}/newly-discovered-nodes/{}.htm".format(BASE_URL, today_slug), robots="noindex,follow")
    newdoc += hero2("{} 新发现节点".format(date_full), tail="")
    newdoc += layout_section(new_body, side_html(today_slug, None)) + FOOTER_TPL
    open(os.path.join(ROOT, "newly-discovered-nodes", today_slug + ".htm"), "w", encoding="utf-8").write(newdoc)

    # ---- 静态栏目页 ----
    write_static("client.htm", "客户端", "科学上网详细教程（客户端导入订阅）",
                 "Clash、V2ray、Sing-box 等客户端导入免费节点订阅链接的详细使用教程，Windows/Android/iOS/Mac 多平台教学。",
                 '''
<h2>科学上网详细教程（客户端导入订阅）</h2>
<p>从<a href="/">首页</a>复制对应格式的订阅链接后，按下面的步骤导入到客户端即可。</p>
<h3>Clash（Windows / Mac）</h3>
<ul><li>下载 Clash 客户端：<a href="https://github.com/Fndroid/clash_for_windows_pkg/releases" target="_blank" rel="nofollow">Clash for Windows</a></li>
<li>Profiles（配置）页面 → 粘贴 <b>Clash 订阅链接（.yaml）</b> → Update 更新</li>
<li>选中节点后开启 System Proxy/系统代理即可</li></ul>
<h3>Clash Meta / mihomo（Android）</h3>
<ul><li>下载 <a href="https://github.com/MetaCubeX/ClashMetaForAndroid/releases" target="_blank" rel="nofollow">Clash Meta for Android</a></li>
<li>配置 → 新建配置 → URL 方式 → 粘贴 <b>Clash 订阅链接</b> → 选择节点并启动</li></ul>
<h3>V2ray（Windows / Android）</h3>
<ul><li>Windows：<a href="https://github.com/2dust/v2rayN/releases" target="_blank" rel="nofollow">v2rayN</a>；Android：<a href="https://github.com/2dust/v2rayNG/releases" target="_blank" rel="nofollow">v2rayNG</a></li>
<li>订阅分组 → 添加订阅 → 粘贴 <b>V2ray 订阅链接（.txt）</b> → 更新订阅</li></ul>
<h3>iOS</h3>
<ul><li><b>Shadowrocket（小火箭）</b>：配置 → 添加订阅 → 粘贴 V2ray 或 Clash 链接（美区 AppleID）</li>
<li><b>Sing-box</b>：Profiles → Import URL，使用 <b>Sing-box 订阅链接（.json）</b></li></ul>
<h3>常见问题</h3>
<ul><li>节点提示失效/超时：免费节点时效性短，前往<a href="/">首页</a>获取最新订阅并重新更新。</li>
<li>延迟高：使用「自动选择」分组，或手动测速切换低延迟节点。</li>
<li>订阅无法下载：GitHub Pages 可能被部分运营商屏蔽，开启代理后重试。</li></ul>
<p style="color:#888;">本站所有节点均爬取自网络，仅供学习研究，请勿用于非法用途。</p>
''')

    write_static("about-us.htm", "关于我们", "关于我们",
                 "Free Clash 是一个免费的Clash/V2ray/Sing-box节点订阅分享站，所有节点均爬取自网络并每日自动更新。",
                 '''
<h2>关于我们</h2>
<p><b>Free Clash</b>（{}）是一个免费节点订阅分享站，通过自动化脚本每日多次从网络上公开渠道抓取可用的 Clash / V2ray / Sing-box 免费节点，自动去重、整理后发布为标准订阅链接，方便大家学习研究之用。</p>
<ul><li>所有节点均爬取自网络公开资料，本站不提供服务本身，也不保证节点的可用性与安全性；</li>
<li>节点每约 6 小时自动更新一次，可在<a href="/">首页</a>查看最新更新时间；</li>
<li>本站不收集用户任何个人数据，也无登录/注册功能；</li>
<li>使用本站即表示您已阅读并同意 <a href="/disclaimer.htm">免责声明</a> 与 <a href="/privacy.htm">隐私协议</a>。</li></ul>
'''.format(BASE_URL))

    write_static("disclaimer.htm", "免责声明", "免责声明",
                 "Free Clash 免责声明：本站所有节点均来自网络公开资源，仅供学习研究，使用者需自行承担使用风险。",
                 '''
<h2>免责声明</h2>
<ol><li>本站所有节点信息均收集自互联网公开资源，<b>本站不生产、不拥有、不维护任何节点服务</b>；</li>
<li>节点仅供<b>学习、研究与技术交流</b>，访问者请遵守所在地区法律法规，<b>请勿用于任何非法用途</b>，由此产生的一切责任由使用者本人承担；</li>
<li>免费节点来源于第三方上传，可能存在记录、篡改或不安全因素，<b>切勿用于登录敏感账号或传输隐私数据</b>；</li>
<li>本站尽力及时清理失效节点，但不保证任何节点的可用性、稳定性与安全性；</li>
<li>如有侵权请联系我们，我们将在核实后第一时间处理。</li></ol>
''')

    write_static("privacy.htm", "隐私协议", "隐私协议",
                 "Free Clash 隐私协议：本站为静态站点，不收集、不存储、不共享任何用户个人数据。",
                 '''
<h2>隐私协议</h2>
<ol><li>本站为纯静态站点（由 GitHub Pages 托管），<b>不设登录、不注册、不采集任何用户个人信息</b>；</li>
<li>本站不主动使用任何跟踪型 Cookies；托管平台（GitHub）可能会按其自身政策记录访问日志，请参考对应平台的隐私政策；</li>
<li>使用节点订阅链接前，请自行了解第三方节点的风险并做好防护措施；</li>
<li>隐私协议如有更新，将直接在本页面发布，不再另行通知。</li></ol>
''')

    # ---- sitemap ----
    sm_entries = [("/", "1.0"), ("/free-nodes/", "0.9"), ("/paid-subscribe/", "0.6"), ("/news/", "0.6"),
                  ("/client.htm", "0.7"), ("/about-us.htm", "0.5"), ("/disclaimer.htm", "0.5"),
                  ("/privacy.htm", "0.5")]
    sm_entries += [("/free-nodes/{}.htm".format(arts[dd]["slug"]), "0.8") for dd in reversed(day_dates[-90:])]
    sm_entries += [("/date/{}/".format(m), "0.4") for m in sorted(month_map, reverse=True)]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "\n".join("<url><loc>{}</loc><lastmod>{}</lastmod><changefreq>{}</changefreq><priority>{}</priority></url>".format(
        BASE_URL + loc, latest["date"] if loc.startswith("/free-nodes") else now8().strftime("%Y-%m-%d"),
        "daily" if loc in ("/", "/free-nodes/") else ("monthly" if loc.startswith("/date/") else "weekly"), pr)
        for loc, pr in sm_entries)
    sm += "\n</urlset>\n"
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8").write(sm)

    # ---- README ----
    rd = ["# {s} | {m}月{d}日|免费Singbox节点/V2ray节点/Clash节点/SSR节点订阅分享 更新时间 {t}".format(
        s=SITE_NAME, m=int(msn), d=int(date_full[8:10]), t=stamp)]
    rd.append("\n所有免费clash节点都爬取自网络，请勿用于非法用途 。节点地址：[点击跳转]({})\n".format(BASE_URL))
    rd.append("## clash使用教程：\n\n[科学上网详细教程]({}/client.htm)\n".format(BASE_URL))
    rd.append("## 订阅链接：\n")
    rd.append("### 免费Clash节点订阅链接\n")
    rd += ["- [{}]({})".format(u, u) for u in yaml_urls]
    rd.append("\n### 免费V2ray节点订阅链接\n")
    rd += ["- [{}]({})".format(u, u) for u in txt_urls]
    rd.append("\n### 免费Sing-box节点订阅链接\n")
    rd += ["- [{}]({})".format(u, u) for u in [sb_url]]
    rd.append("\n## 今日更新\n")
    rd.append("[{Y}-{M}-{D} 完整节点列表]({b}/free-nodes/{sl}.htm)".format(
        Y=ysn, M=int(msn), D=int(date_full[8:10]), b=BASE_URL, sl=today_slug))
    open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8").write("\n".join(rd) + "\n")

    meta = {"updated": stamp, "count": len(uniq), "new": len(new_nodes), "subs": [sb_url]}
    json.dump(meta, open(os.path.join(ROOT, "data", "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("done:", stamp, "nodes:", len(uniq), "new:", len(new_nodes))


def write_static(fname, nav_label, h1, desc, body):
    doc = head("detail", h1 + " - " + SITE_NAME, desc, BASE_URL + "/" + fname)
    doc += hero2(h1, tail=nav_label)
    doc += layout_section(body, "<div></div>") + FOOTER_TPL
    open(os.path.join(ROOT, fname), "w", encoding="utf-8").write(doc)


if __name__ == "__main__":
    main()
