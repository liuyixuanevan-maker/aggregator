# -*- coding: utf-8 -*-
import json
import os
import re
import urllib.parse
import urllib.request

def run_patch():
    # [1/5] Patching subscribe/utils.py for 32-thread concurrency
    print("[1/5] Patching subscribe/utils.py for 32-thread concurrency...")
    with open("subscribe/utils.py", "r", encoding="utf-8") as f:
        c = f.read()
    t = "def multi_process_run(func: typing.Callable[..., object], tasks: list[object]) -> list[object]:"
    if "num_threads=32" not in c:
        c = c.replace(t, t + "\n    return multi_thread_run(func=func, tasks=tasks, num_threads=32)")
        with open("subscribe/utils.py", "w", encoding="utf-8") as f:
            f.write(c)
    print("  -> utils.py patched.")

    # [2/5] Patching subscribe/airport.py timeout to 20s
    print("[2/5] Patching subscribe/airport.py timeout to 20s...")
    with open("subscribe/airport.py", "r", encoding="utf-8") as f:
        c = f.read()
    c = c.replace("timeout=120", "timeout=20").replace("account, 120,", "account, 20,")
    with open("subscribe/airport.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> airport.py patched.")

    # [3/5] Patching subscribe/discovery.py for multi-channel Telegram crawling
    print("[3/5] Patching subscribe/discovery.py for multi-channel Telegram crawling...")
    with open("subscribe/discovery.py", "r", encoding="utf-8") as f:
        c = f.read()
    old_discovery = """def default_sources(channel: str, page_num: int) -> list[AirportSource]:
    return [
        TelegramSource(channel=channel, page_num=page_num),
        HwanzSource(),
        CcbaoheSource(),
        MaomengSource(),
        AskahhSource(),
        YgpySource(),
    ]"""
    sub_discovery = """def default_sources(channel: str, page_num: int) -> list[AirportSource]:
    tg_channels = [channel, "baipiaojichang", "bpjichang", "Airport_Free"]
    sources = [TelegramSource(channel=ch, page_num=page_num) for ch in set(tg_channels) if ch]
    sources.extend([
        HwanzSource(),
        CcbaoheSource(),
        MaomengSource(),
        AskahhSource(),
        YgpySource(),
    ])
    return sources"""
    if old_discovery in c:
        c = c.replace(old_discovery, sub_discovery)
        with open("subscribe/discovery.py", "w", encoding="utf-8") as f:
            f.write(c)
        print("  -> discovery.py patched for multi-channel crawling.")
    else:
        print("  -> discovery.py target already patched or not found.")

    # [4/5] Patching subscribe/mailtm.py to inject TempMailPlus (bypassing blacklisted domains)
    print("[4/5] Patching subscribe/mailtm.py to inject TempMailPlus...")
    with open("subscribe/mailtm.py", "r", encoding="utf-8") as f:
        c = f.read()
    old_mailtm = """def create_instance(only_gmail: bool = False) -> TemporaryMail:
    if only_gmail:
        return Emailnator(onlygmail=True)

    num = random.randint(0, 1)
    if num == 1:
        return MailTM()
    else:
        return MOAKT()"""
    sub_mailtm = """class TempMailPlus(TemporaryMail):
    def __init__(self) -> None:
        super().__init__()
        self.api_address = "https://tempmail.plus"
        self.domains = ["mailto.plus", "fexpost.com", "fexbox.org", "mailbox.in.ua", "rofi.in.net"]

    def get_domains_list(self) -> list[str]:
        return self.domains

    def get_account(self, retry: int = 3) -> Account:
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(self.domains)
        address = f"{username}@{domain}"
        password = utils.random_chars(random.randint(8, 16), punctuation=True)
        return Account(address=address, password=password, id=username)

    def get_messages(self, account: Account) -> list[Message]:
        try:
            url = f"https://tempmail.plus/api/mails?email={account.address}&limit=5"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))
            mail_list = data.get("mail_list", [])
            messages = []
            for m in mail_list:
                mid = m.get("mail_id")
                d_url = f"https://tempmail.plus/api/mails/{mid}?email={account.address}"
                d_req = urllib.request.Request(d_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(d_req, timeout=6) as rd:
                    md = json.loads(rd.read().decode("utf-8", errors="ignore"))
                text = md.get("text", "") or md.get("html", "")
                messages.append(Message(text=text, id=str(mid), subject=md.get("subject", "")))
            return messages
        except Exception:
            return []

    def delete_account(self, account: Account) -> bool:
        return True

def create_instance(only_gmail: bool = False) -> TemporaryMail:
    return TempMailPlus()"""
    if old_mailtm in c:
        c = c.replace(old_mailtm, sub_mailtm)
        with open("subscribe/mailtm.py", "w", encoding="utf-8") as f:
            f.write(c)
        print("  -> mailtm.py patched with TempMailPlus.")
    else:
        print("  -> mailtm.py target already patched or not found.")

    # [5/5] Patching subscribe/collect.py for Anti-GFW filter and FlClash Probe
    print("[5/5] Patching subscribe/collect.py for Anti-GFW filter and FlClash Probe...")
    with open("subscribe/collect.py", "r", encoding="utf-8") as f:
        c = f.read()

    # Ingest external feeds and strict Anti-GFW filter
    old_filter = "proxies = list(itertools.chain.from_iterable([x[1] for x in results if x]))"
    sub_filter = old_filter + '''
    import re, urllib.request, urllib.parse
    logger.info("Ingesting high-frequency live Hysteria2 & VLESS-Reality feeds from 0xRadikal/Free-v2ray-Configs...")
    jp_sg_tw = re.compile(r"(?i)日本|Japan|Tokyo|Osaka|川崎|埼玉|新加坡|狮城|Singapore|台湾|台灣|Taiwan|Taipei|新北|高雄|\\bJP\\b|\\bSG\\b|\\bTW\\b|🇯🇵|🇸🇬|🇹🇼")

    def parse_hy2(uri):
        p = urllib.parse.urlsplit(uri)
        if p.scheme != "hy2": return None
        qs = urllib.parse.parse_qs(p.query)
        name = urllib.parse.unquote(p.fragment) if p.fragment else f"HY2-{p.hostname}"
        clean_name = re.sub(r'[\\r\\n\\t]', ' ', name).strip()
        node = {
            "name": clean_name,
            "type": "hysteria2",
            "server": p.hostname,
            "port": p.port or 443,
            "password": p.username or "",
        }
        sni = qs.get("sni", [""])[0]
        if sni and sni != "off":
            node["sni"] = sni
        if qs.get("insecure", ["0"])[0] in ["1", "true"]:
            node["skip-cert-verify"] = True
        if "obfs" in qs:
            node["obfs"] = qs["obfs"][0]
            if "obfs-password" in qs:
                node["obfs-password"] = qs["obfs-password"][0]
        return node

    def parse_vless_reality(uri):
        p = urllib.parse.urlsplit(uri)
        if p.scheme != "vless": return None
        qs = urllib.parse.parse_qs(p.query)
        sec = qs.get("security", [""])[0]
        pbk = qs.get("pbk", [""])[0]
        if sec != "reality" and not pbk:
            return None
        name = urllib.parse.unquote(p.fragment) if p.fragment else f"VLESS-{p.hostname}"
        clean_name = re.sub(r'[\\r\\n\\t]', ' ', name).strip()
        node = {
            "name": clean_name,
            "type": "vless",
            "server": p.hostname,
            "port": p.port or 443,
            "uuid": p.username or "",
            "network": qs.get("type", ["tcp"])[0],
            "tls": True,
            "udp": True,
            "servername": qs.get("sni", [""])[0],
            "client-fingerprint": qs.get("fp", ["chrome"])[0],
            "reality-opts": {
                "public-key": pbk,
            }
        }
        if "sid" in qs and qs["sid"][0]:
            node["reality-opts"]["short-id"] = str(qs["sid"][0])
        if "flow" in qs and qs["flow"][0]:
            node["flow"] = qs["flow"][0]
        return node

    ext_nodes = []
    feed_sources = [
        ("hy2", "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/protocols/hysteria2.txt"),
        ("reality", "https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/protocols/vless.txt")
    ]
    for kind, furl in feed_sources:
        try:
            req = urllib.request.Request(furl, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                lines = [l.strip() for l in resp.read().decode("utf-8", errors="ignore").splitlines() if l.strip()]
                for l in lines:
                    if kind == "hy2" and l.startswith("hy2://"):
                        n = parse_hy2(l)
                        if n and jp_sg_tw.search(n["name"]):
                            ext_nodes.append(n)
                    elif kind == "reality" and l.startswith("vless://"):
                        n = parse_vless_reality(l)
                        if n and jp_sg_tw.search(n["name"]):
                            ext_nodes.append(n)
        except Exception as e:
            logger.warning(f"Failed to fetch {kind} feed from {furl}: {e}")

    logger.info(f"Loaded {len(ext_nodes)} high-grade nodes from external live feeds.")
    proxies.extend(ext_nodes)

    def is_anti_gfw(p):
        if not isinstance(p, dict): return False
        ptype = str(p.get("type", "")).lower()
        if ptype in ["hysteria2", "hy2"]: return True
        sec = str(p.get("security", "")).lower()
        if ptype == "vless" and (sec == "reality" or "reality-opts" in p): return True
        return False

    proxies = [p for p in proxies if isinstance(p, dict) and jp_sg_tw.search(p.get("name", "")) and is_anti_gfw(p)]
    logger.info(f"Strict Anti-GFW JP/SG/TW proxies count for Clash check: {len(proxies)}")'''

    # FlClash probe logic before terminating clash
    old_term = """        # 关闭clash
        try:
            process.terminate()
        except:
            logger.error(f"terminate clash process error")

        nodes = [proxies[i] for i in range(len(proxies)) if masks[i]]
        if len(nodes) <= 0:
            logger.error(f"cannot fetch any proxy")
            sys.exit(0)"""

    sub_probe = '''        alive_nodes = [proxies[i] for i in range(len(proxies)) if masks[i]]
        logger.info(f"Clash liveness check passed: {len(alive_nodes)} nodes, now running FlClash Gemini region verification...")
        def verify_gemini_flclash(candidates, controller, port=7890):
            import urllib.request, urllib.parse, json
            marker = b',2,1,200,"'
            blocked = {b"CHN", b"RUS", b"BLR", b"CUB", b"IRN", b"PRK", b"SYR", b"HKG", b"MAC"}
            verified = []
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({
                "http": f"http://127.0.0.1:{port}",
                "https": f"http://127.0.0.1:{port}"
            }))
            for item in candidates[:35]:
                pname = item.get("name", "")
                try:
                    purl = f"http://{controller}/proxies/%F0%9F%8C%90%20Proxy"
                    req = urllib.request.Request(purl, data=json.dumps({"name": pname}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="PUT")
                    with urllib.request.urlopen(req, timeout=3) as _: pass
                    greq = urllib.request.Request("https://gemini.google.com", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                    region = None
                    with opener.open(greq, timeout=5) as gresp:
                        for _ in range(28):
                            chunk = gresp.read(32768)
                            if not chunk: break
                            idx = chunk.find(marker)
                            if idx != -1:
                                code = chunk[idx+len(marker):idx+len(marker)+3]
                                if len(code) == 3 and code.isupper():
                                    region = code
                                    break
                    if region and region not in blocked:
                        reg_str = region.decode("utf-8", errors="ignore")
                        logger.info(f"[FlClash Probe] Node '{pname}' verified for Gemini! Region: {reg_str}")
                        item["name"] = f"[{reg_str}] {pname}"
                        verified.append(item)
                    else:
                        logger.warning(f"[FlClash Probe] Node '{pname}' skipped (Region: {region})")
                except Exception as err:
                    logger.warning(f"[FlClash Probe] Node '{pname}' failed: {err}")
            return verified if verified else candidates

        nodes = verify_gemini_flclash(alive_nodes, clash.EXTERNAL_CONTROLLER, 7890)
        logger.info(f"Final Gemini-verified nodes count: {len(nodes)}")

        # 关闭clash
        try:
            process.terminate()
        except:
            logger.error(f"terminate clash process error")

        if len(nodes) <= 0:
            logger.error(f"cannot fetch any proxy")
            sys.exit(0)'''

    if old_filter in c:
        c = c.replace(old_filter, sub_filter)
    if old_term in c:
        c = c.replace(old_term, sub_probe)

    with open("subscribe/collect.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> collect.py patched successfully.")

if __name__ == "__main__":
    run_patch()
