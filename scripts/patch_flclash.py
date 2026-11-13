# -*- coding: utf-8 -*-
import base64
import json
import os
import re
import urllib.parse
import urllib.request

def run_patch():
    # [1/6] Patching subscribe/utils.py for 32-thread concurrency
    print("[1/6] Patching subscribe/utils.py for 32-thread concurrency...")
    with open("subscribe/utils.py", "r", encoding="utf-8") as f:
        c = f.read()
    t = "def multi_process_run(func: typing.Callable[..., object], tasks: list[object]) -> list[object]:"
    if "num_threads=32" not in c:
        c = c.replace(t, t + "\n    return multi_thread_run(func=func, tasks=tasks, num_threads=32)")
        with open("subscribe/utils.py", "w", encoding="utf-8") as f:
            f.write(c)
    print("  -> utils.py patched.")

    # [2/6] Patching subscribe/airport.py (Direct Multi-Protocol Parser, Timeout, Handover, Alphanumeric Passwords)
    print("[2/6] Patching subscribe/airport.py...")
    with open("subscribe/airport.py", "r", encoding="utf-8") as f:
        c = f.read()

    direct_parser_code = '''
def _decode_node_uri(uri: str) -> dict | None:
    uri = uri.strip()
    if not uri or uri.startswith("#") or uri.startswith("STATUS="):
        return None

    if uri.startswith("hysteria2://") or uri.startswith("hy2://"):
        try:
            parsed = urllib.parse.urlsplit(uri)
            userinfo = parsed.username or (parsed.netloc.split("@")[0] if "@" in parsed.netloc else "")
            host_port = parsed.netloc.split("@")[-1] if "@" in parsed.netloc else parsed.netloc
            if ":" in host_port:
                server, port = host_port.rsplit(":", 1)
                port = int(port)
            else:
                server, port = host_port, 443
            qs = urllib.parse.parse_qs(parsed.query)
            name = urllib.parse.unquote(parsed.fragment) or qs.get("remark", [server])[0]
            if isinstance(name, list): name = name[0]
            name = urllib.parse.unquote(str(name)).strip()
            return {
                "name": name or f"HY2-{server}",
                "type": "hysteria2",
                "server": server,
                "port": port,
                "auth": userinfo,
                "up": qs.get("up", ["100"])[0],
                "down": qs.get("down", ["100"])[0],
                "sni": qs.get("sni", [""])[0] or server,
                "skip-cert-verify": qs.get("insecure", ["0"])[0] == "1",
            }
        except Exception:
            return None

    elif uri.startswith("vless://"):
        try:
            raw = uri[len("vless://"):]
            if "?" in raw:
                authority, query_frag = raw.split("?", 1)
            else:
                authority, query_frag = raw, ""

            if "@" not in authority:
                pad = authority + "=" * ((4 - len(authority) % 4) % 4)
                try:
                    dec_auth = base64.b64decode(pad).decode("utf-8")
                    if "@" in dec_auth:
                        authority = dec_auth
                except Exception:
                    pass
            elif authority.startswith("YXV0"):
                userinfo_part, hp = authority.rsplit("@", 1)
                pad = userinfo_part + "=" * ((4 - len(userinfo_part) % 4) % 4)
                try:
                    dec_user = base64.b64decode(pad).decode("utf-8")
                    if ":" in dec_user:
                        userinfo_part = dec_user.split(":", 1)[1]
                    authority = f"{userinfo_part}@{hp}"
                except Exception:
                    pass

            if "@" in authority:
                userinfo, host_port = authority.split("@", 1)
                uuid = userinfo.split(":", 1)[1] if (":" in userinfo and not userinfo.startswith("auto:")) else userinfo.replace("auto:", "")
            else:
                return None

            if ":" in host_port:
                server, port = host_port.rsplit(":", 1)
                port = int(port)
            else:
                server, port = host_port, 443

            frag = ""
            query_str = query_frag
            if "#" in query_frag:
                query_str, frag = query_frag.split("#", 1)
            qs = urllib.parse.parse_qs(query_str)

            name = urllib.parse.unquote(frag) if frag else qs.get("remark", [f"VLESS-{server}"])[0]
            if isinstance(name, list): name = name[0]
            name = urllib.parse.unquote(str(name)).strip()

            security = qs.get("security", ["none"])[0]
            tls = qs.get("tls", ["0"])[0] in ["1", "true", "tls"] or security in ["tls", "reality"]
            net = qs.get("type", qs.get("net", ["tcp"]))[0]

            node = {
                "name": name or f"VLESS-{server}",
                "type": "vless",
                "server": server,
                "port": port,
                "uuid": uuid,
                "network": net,
                "udp": True,
                "tls": tls,
            }
            if qs.get("flow"):
                node["flow"] = qs.get("flow")[0]
            if qs.get("sni"):
                node["servername"] = qs.get("sni")[0]
            if qs.get("fp"):
                node["client-fingerprint"] = qs.get("fp")[0]
            if qs.get("pbk") or security == "reality" or qs.get("xtls", [""])[0] == "2":
                node["reality-opts"] = {
                    "public-key": qs.get("pbk", [""])[0],
                    "short-id": qs.get("sid", [""])[0]
                }
            if net == "ws":
                node["ws-opts"] = {
                    "path": qs.get("path", ["/"])[0],
                    "headers": {"Host": qs.get("host", [node.get("servername", server)])[0]}
                }
            return node
        except Exception:
            return None

    elif uri.startswith("vmess://"):
        try:
            raw = uri[len("vmess://"):]
            pad = raw.split("?")[0] + "=" * ((4 - len(raw.split("?")[0]) % 4) % 4)
            dec = ""
            try:
                dec = base64.b64decode(pad).decode("utf-8")
            except Exception:
                pass

            if dec.startswith("{") and dec.endswith("}"):
                j = json.loads(dec)
                return {
                    "name": str(j.get("ps", f"VMess-{j.get('add')}")).strip(),
                    "type": "vmess",
                    "server": j.get("add"),
                    "port": int(j.get("port", 443)),
                    "uuid": j.get("id"),
                    "alterId": int(j.get("aid", 0)),
                    "cipher": j.get("scy", "auto"),
                    "udp": True,
                    "tls": j.get("tls") in ["tls", "1", True],
                    "network": j.get("net", "tcp")
                }
            else:
                if "?" in raw:
                    authority, query_frag = raw.split("?", 1)
                else:
                    authority, query_frag = raw, ""
                if "@" not in authority:
                    try:
                        dec_auth = base64.b64decode(authority + "=" * ((4 - len(authority) % 4) % 4)).decode("utf-8")
                        if "@" in dec_auth: authority = dec_auth
                    except Exception: pass
                if "@" in authority:
                    userinfo, host_port = authority.split("@", 1)
                    uuid = userinfo.replace("auto:", "")
                    server, port = host_port.split(":")
                    qs = urllib.parse.parse_qs(query_frag.split("#")[0])
                    name = urllib.parse.unquote(qs.get("remark", [f"VMess-{server}"])[0])
                    if isinstance(name, list): name = name[0]
                    name = urllib.parse.unquote(str(name)).strip()
                    network = "ws" if qs.get("obfs", [""])[0] == "websocket" else qs.get("obfs", ["tcp"])[0]
                    node = {
                        "name": name or f"VMess-{server}",
                        "type": "vmess",
                        "server": server,
                        "port": int(port),
                        "uuid": uuid,
                        "alterId": int(qs.get("alterId", [0])[0]),
                        "cipher": "auto",
                        "udp": True,
                        "network": network,
                        "tls": qs.get("tls", ["0"])[0] in ["1", "true"]
                    }
                    if network == "ws":
                        node["ws-opts"] = {"path": qs.get("path", ["/"])[0]}
                    return node
        except Exception:
            return None

    elif uri.startswith("trojan://"):
        try:
            parsed = urllib.parse.urlsplit(uri)
            password = parsed.username or parsed.netloc.split("@")[0]
            host_port = parsed.netloc.split("@")[-1]
            server, port = host_port.split(":")
            qs = urllib.parse.parse_qs(parsed.query)
            name = urllib.parse.unquote(parsed.fragment) or qs.get("remark", [f"Trojan-{server}"])[0]
            if isinstance(name, list): name = name[0]
            name = urllib.parse.unquote(str(name)).strip()
            return {
                "name": name or f"Trojan-{server}",
                "type": "trojan",
                "server": server,
                "port": int(port),
                "password": password,
                "udp": True,
                "sni": qs.get("sni", [server])[0],
                "skip-cert-verify": qs.get("allowInsecure", ["0"])[0] == "1"
            }
        except Exception:
            return None

    return None

def _parse_direct_subscription(text: str) -> list[dict]:
    if not text:
        return []
    import yaml
    if "proxies:" in text:
        try:
            data = yaml.safe_load(quote_unquoted_ipv6(text))
            if isinstance(data, dict) and isinstance(data.get("proxies"), list):
                return [p for p in data["proxies"] if isinstance(p, dict)]
        except Exception:
            pass

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) == 1 or (len(lines) > 0 and not any("://" in l for l in lines)):
        joined = "".join(lines)
        pad = joined + "=" * ((4 - len(joined) % 4) % 4)
        try:
            dec = base64.b64decode(pad).decode("utf-8", errors="ignore")
            lines = [l.strip() for l in dec.splitlines() if l.strip()]
        except Exception:
            pass

    nodes = []
    for l in lines:
        node = _decode_node_uri(l)
        if node:
            nodes.append(node)
    return nodes
'''

    if "def _parse_direct_subscription" not in c:
        c = direct_parser_code + "\n" + c

    # Hook inside AirPort.decode()
    old_decode = """    def decode(
        text: str,
        program: str,
        artifact: str = "",
        ignore: bool = False,
        special: bool = False,
        throw: bool = False,
        use_subconverter: bool = True,
        do_verify: bool = True,
    ) -> list[dict[str, object]]:"""

    new_decode = """    def decode(
        text: str,
        program: str,
        artifact: str = "",
        ignore: bool = False,
        special: bool = False,
        throw: bool = False,
        use_subconverter: bool = True,
        do_verify: bool = True,
    ) -> list[dict[str, object]]:
        # Fast direct parsing: extracts all modern protocols without SubConverter dropping nodes
        try:
            direct_nodes = _parse_direct_subscription(text)
            if direct_nodes:
                if do_verify:
                    return [x for x in direct_nodes if verify(x, special)]
                return direct_nodes
        except Exception:
            pass"""

    if old_decode in c:
        c = c.replace(old_decode, new_decode)

    # Increase request timeout
    c = c.replace("timeout=10, context=utils.CTX", "timeout=20, context=utils.CTX")

    # Fix node handover fallback in parse(): if nodes is empty, fallback to self.nodes
    old_source = "source = nodes if isinstance(nodes, NodeInput) else self.nodes"
    new_source = "source = nodes if (isinstance(nodes, NodeInput) and not nodes.empty()) else self.nodes"
    if old_source in c:
        c = c.replace(old_source, new_source)

    # Use alphanumeric passwords (punctuation=False) to avoid airport regex rejection
    c = c.replace(
        "password = utils.random_chars(length=random.randint(8, 16), punctuation=True)",
        "password = utils.random_chars(length=random.randint(10, 16), punctuation=False)"
    )

    # Relax email whitelist check to allow TempMailPlus domains
    old_wl = '(rr.whitelist and rr.verify and (not allow_gmail_alias or "gmail.com" not in rr.whitelist))'
    new_wl = '(rr.whitelist and rr.verify and not any(d in rr.whitelist for d in ["gmail.com", "mailto.plus", "fexpost.com", "fexbox.org", "mailbox.in.ua"]))'
    if old_wl in c:
        c = c.replace(old_wl, new_wl)

    with open("subscribe/airport.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> airport.py patched.")

    # [3/6] Patching subscribe/workflow.py (handover bug fix)
    print("[3/6] Patching subscribe/workflow.py...")
    with open("subscribe/workflow.py", "r", encoding="utf-8") as f:
        c = f.read()

    old_get_sub = """    cookie, authorization = "", ""
    if task_conf.nodes.empty() and task_conf.domain:
        cookie, authorization = obj.get_subscribe(
            retry=task_conf.retry,
            allow_gmail_alias=task_conf.allow_gmail_alias,
            skip_captcha=task_conf.skip_captcha,
            invite_code=task_conf.invite_code,
        )"""

    new_get_sub = """    cookie, authorization = "", ""
    if task_conf.nodes.empty() and task_conf.domain:
        cookie, authorization = obj.get_subscribe(
            retry=task_conf.retry,
            allow_gmail_alias=task_conf.allow_gmail_alias,
            skip_captcha=task_conf.skip_captcha,
            invite_code=task_conf.invite_code,
        )
        if not obj.nodes.empty():
            task_conf.nodes = obj.nodes"""

    if old_get_sub in c:
        c = c.replace(old_get_sub, new_get_sub)

    with open("subscribe/workflow.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> workflow.py patched.")

    # [4/6] Seeding verified commercial trial airports into data/domains.txt
    print("[4/6] Seeding verified commercial trial airports into data/domains.txt...")
    os.makedirs("data", exist_ok=True)
    trial_airports = [
        "https://www.fankeyun.space",
        "https://www.fankeyunyaoqing.space",
        "https://plutocore.vip",
        "https://10086900.xyz",
        "https://rcwave.net",
        "https://usyun.cc",
        "https://www.usyun.cc",
        "https://kuais.pw",
        "https://www.kuais.pw",
        "https://vv.louwangzhiyu.org"
    ]
    domains_file = os.path.join("data", "domains.txt")
    existing_domains = []
    if os.path.exists(domains_file):
        with open(domains_file, "r", encoding="utf-8") as f:
            existing_domains = [line.strip() for line in f if line.strip()]
    merged_domains = list(dict.fromkeys(trial_airports + existing_domains))
    with open(domains_file, "w", encoding="utf-8") as f:
        f.write("\n".join(merged_domains) + "\n")
    print(f"  -> {len(merged_domains)} commercial trial airports seeded into data/domains.txt.")

    # [5/6] Patching subscribe/mailtm.py with TempMailPlus
    print("[5/6] Patching subscribe/mailtm.py with TempMailPlus engine...")
    with open("subscribe/mailtm.py", "r", encoding="utf-8") as f:
        c = f.read()

    tempmail_engine = """
class TempMailPlus(TemporaryMail):
    DOMAINS = ["mailto.plus", "fexpost.com", "fexbox.org", "mailbox.in.ua", "rofi.in.net"]

    def __init__(self) -> None:
        super().__init__()
        self.api_address = "https://tempmail.plus/api/mails"

    def get_account(self, retry: int = 3) -> Account | None:
        user = utils.random_chars(length=10, punctuation=False).lower()
        domain = random.choice(self.DOMAINS)
        account = Account(
            account_id=user,
            address=f"{user}@{domain}",
            password=utils.random_chars(length=12, punctuation=False),
        )
        self.account = account
        logger.info(f"[TempMailPlus] created disposable account: {account.address}")
        return account

    def monitor_account(self, account: Account, timeout: int = 120, sleep: int = 3) -> Message | None:
        if not account or not account.address:
            return None
        user, domain = account.address.split("@", 1)
        url = f"{self.api_address}?email={user}%40{domain}&limit=10"
        starttime = time.time()
        logger.info(f"[TempMailPlus] monitoring inbox for {account.address}...")

        while time.time() - starttime < timeout:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                res = urllib.request.urlopen(req, timeout=10, context=utils.CTX)
                if res.getcode() == 200:
                    data = json.loads(res.read().decode("utf-8"))
                    mail_list = data.get("mail_list", [])
                    if mail_list:
                        first_id = mail_list[0].get("mail_id")
                        detail_url = f"{self.api_address}/{first_id}?email={user}%40{domain}"
                        d_req = urllib.request.Request(detail_url, headers={"User-Agent": "Mozilla/5.0"})
                        d_res = urllib.request.urlopen(d_req, timeout=10, context=utils.CTX)
                        if d_res.getcode() == 200:
                            m_data = json.loads(d_res.read().decode("utf-8"))
                            text = m_data.get("text", "") or m_data.get("html", "") or m_data.get("subject", "")
                            logger.info(f"[TempMailPlus] successfully received email for {account.address}")
                            return Message(message_id=str(first_id), text=text)
            except Exception as e:
                logger.debug(f"[TempMailPlus] poll error: {e}")
            time.sleep(sleep)

        logger.error(f"[TempMailPlus] timeout waiting for mail: {account.address}")
        return None

    def delete_account(self, account: Account) -> bool:
        return True
"""

    if "class TempMailPlus" not in c:
        c += tempmail_engine
    c = re.sub(
        r"def create_instance\(.*?\)\s*->\s*TemporaryMail:.*?(?=\ndef|\Z)",
        "def create_instance(only_gmail: bool = False) -> TemporaryMail:\n    return TempMailPlus()\n",
        c,
        flags=re.DOTALL,
    )

    with open("subscribe/mailtm.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> mailtm.py patched.")

    # [6/6] Patching subscribe/collect.py for Commercial Airport Injection & Zero Protocol Restriction & Clash YAML Guarantee
    print("[6/6] Patching subscribe/collect.py for commercial airport injection and multi-protocol guarantee...")
    with open("subscribe/collect.py", "r", encoding="utf-8") as f:
        c = f.read()

    # 1. Clean up dead raw links (Barabama/ermaozi/Raydikalx) and inject verified commercial trial airport subscriptions
    commercial_trial_subs = [
        "https://www.fankeyundingyue.space/fckwec/vip/client/subscribe?token=dc9193504b37d766e1cb57a65a13b98e",
        "https://rcwave.net/api/v1/client/subscribe?token=ff24fb373caad67ace1cb1d7cc7f86e9",
        "https://sf55d7a13a49f.flszjy.com/891aa9/s/e1fd403b76a0cb306fc505b92abef781",
        "https://10086900.xyz/s/a1fe370eaefbaf0269a739df1bf40120",
        "https://usyun.cc/s/c51368ac7be81f19e6e15e139a11fd32",
        "http://xb.xxzf.cc/s/fbae4709c829f4e2fad47f16cc470be5",
        "https://vv.louwangzhiyu.org/api/v1/client/subscribe?token=1b9190917c20076725d401b923154be8",
    ]
    sub_inject_code = f"""
        # Filter out non-commercial / dead raw GitHub and Telegram scraped links
        subscriptions = {{s for s in subscriptions if not any(b in s.lower() for b in ["githubusercontent", "freenodes", "ermaozi", "raydikalx"])}}
        # Inject verified commercial trial airport subscriptions
        for s in {commercial_trial_subs!r}:
            subscriptions.add(s)
        logger.info(f"injected verified commercial trial subscriptions, total: {{len(subscriptions)}}")
        links = list(subscriptions)
"""
    c = c.replace(
        "        links = list(subscriptions)\n        results = utils.multi_thread_run(",
        sub_inject_code + "        results = utils.multi_thread_run("
    )

    # 2. DO NOT restrict protocols! Ensure all proxies passing Clash liveness tests (masks[i] == True) are preserved
    c = re.sub(
        r"nodes = \[\]\s+for i in range\(len\(proxies\)\):.*?nodes\.append\(p\)",
        "nodes = [proxies[i] for i in range(len(proxies)) if masks[i]]",
        c,
        flags=re.DOTALL
    )

    # 3. Post-process data/clash.yaml after SubConverter runs to guarantee all live nodes and reality-opts are preserved
    post_process_code = """
    # Post-process clash.yaml to ensure all live modern proxies (VLESS Reality, HY2, VMess) and complete fields are preserved
    try:
        clash_file_path = os.path.join(DATA_BASE, "clash.yaml")
        if os.path.exists(clash_file_path):
            with open(clash_file_path, "r", encoding="utf-8") as f:
                c_yaml = yaml.safe_load(f)
            if isinstance(c_yaml, dict):
                c_yaml["proxies"] = nodes
                all_proxy_names = [n["name"] for n in nodes]
                for grp in c_yaml.get("proxy-groups", []):
                    if isinstance(grp, dict) and "proxies" in grp:
                        specials = [p for p in grp["proxies"] if p in ["DIRECT", "REJECT"]]
                        grp["proxies"] = specials + [name for name in all_proxy_names if name not in specials]
                with open(clash_file_path, "w", encoding="utf-8") as f:
                    yaml.dump(c_yaml, f, allow_unicode=True)
                logger.info(f"[ClashGuarantee] successfully written {len(nodes)} verified modern proxies to clash.yaml")
    except Exception as ex:
        logger.error(f"[ClashGuarantee] post-processing error: {ex}")
"""

    c = c.replace(
        '    logger.info(f"found {len(nodes)} proxies, save it to {list(records.values())}")',
        post_process_code + '\n    logger.info(f"found {len(nodes)} proxies, save it to {list(records.values())}")'
    )

    with open("subscribe/collect.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> collect.py patched successfully (multi-airport injection, open modern protocols, clash guarantee).")

if __name__ == "__main__":
    run_patch()
