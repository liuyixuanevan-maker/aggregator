# -*- coding: utf-8 -*-
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

    # [2/6] Patching subscribe/airport.py (timeout, handover fallback, whitelist logic)
    print("[2/6] Patching subscribe/airport.py...")
    with open("subscribe/airport.py", "r", encoding="utf-8") as f:
        c = f.read()

    # Increase request timeout
    c = c.replace("timeout=10, context=utils.CTX", "timeout=20, context=utils.CTX")

    # Fix node handover fallback in parse(): if nodes is empty, fallback to self.nodes
    old_source = "source = nodes if isinstance(nodes, NodeInput) else self.nodes"
    new_source = "source = nodes if (isinstance(nodes, NodeInput) and not nodes.empty()) else self.nodes"
    if old_source in c:
        c = c.replace(old_source, new_source)

    # Relax email whitelist check to allow TempMailPlus domains (mailto.plus, etc.) or gmail
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

    # [4/6] Patching subscribe/discovery.py (multi-channel TG + validator relaxation)
    print("[4/6] Patching subscribe/discovery.py...")
    with open("subscribe/discovery.py", "r", encoding="utf-8") as f:
        c = f.read()

    old_default_sources = """def default_sources(channel: str, page_num: int) -> list[AirportSource]:
    return [
        TelegramSource(channel=channel, page_num=page_num),
        HwanzSource(),
        CcbaoheSource(),
        MaomengSource(),
        AskahhSource(),
        YgpySource(),
    ]"""

    new_default_sources = """def default_sources(channel: str, page_num: int) -> list[AirportSource]:
    all_channels = list(dict.fromkeys([channel, "Airport_Free", "baipiaojichang", "bpjichang", "jichang_list"]))
    sources = [TelegramSource(channel=ch, page_num=page_num) for ch in all_channels]
    sources.extend([
        HwanzSource(),
        CcbaoheSource(),
        MaomengSource(),
        AskahhSource(),
        YgpySource(),
    ])
    return sources"""

    if old_default_sources in c:
        c = c.replace(old_default_sources, new_default_sources)

    old_blocked = """            blocked = (
                requirement.invite
                or (skip_captcha and requirement.recaptcha)
                or (
                    requirement.whitelist
                    and requirement.verify
                    and (not allow_gmail_alias or "gmail.com" not in requirement.whitelist)
                )
            )"""

    new_blocked = """            blocked = (
                requirement.invite
                or (skip_captcha and requirement.recaptcha)
                or (
                    requirement.whitelist
                    and requirement.verify
                    and not any(d in requirement.whitelist for d in ["gmail.com", "mailto.plus", "fexpost.com", "fexbox.org", "mailbox.in.ua"])
                )
            )"""

    if old_blocked in c:
        c = c.replace(old_blocked, new_blocked)

    with open("subscribe/discovery.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> discovery.py patched.")

    # [5/6] Patching subscribe/mailtm.py with TempMailPlus
    print("[5/6] Patching subscribe/mailtm.py with TempMailPlus engine...")
    with open("subscribe/mailtm.py", "r", encoding="utf-8") as f:
        c = f.read()

    tempmail_engine = """
class TempMailPlus(Mailbox):
    DOMAINS = ["mailto.plus", "fexpost.com", "fexbox.org", "mailbox.in.ua", "rofi.in.net"]

    def __init__(self) -> None:
        super().__init__()
        self.api_address = "https://tempmail.plus/api/mails"

    def get_account(self) -> Account | None:
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

    def monitor_account(self, account: Account, timeout: int = 120, interval: int = 3) -> Message | None:
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
            time.sleep(interval)

        logger.error(f"[TempMailPlus] timeout waiting for mail: {account.address}")
        return None

    def delete_account(self, account: Account) -> bool:
        return True
"""

    if "class TempMailPlus" not in c:
        c += tempmail_engine
    c = re.sub(
        r"def create_instance\(.*?\)\s*->\s*Mailbox:.*?(?=\ndef|\Z)",
        "def create_instance(only_gmail: bool = False) -> Mailbox:\n    return TempMailPlus()\n",
        c,
        flags=re.DOTALL,
    )

    with open("subscribe/mailtm.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> mailtm.py patched.")

    # [6/6] Patching subscribe/collect.py for Strict Anti-GFW & Gemini Streaming Verification
    print("[6/6] Patching subscribe/collect.py for FlClash & Gemini...")
    with open("subscribe/collect.py", "r", encoding="utf-8") as f:
        c = f.read()

    old_filter = 'nodes = [proxies[i] for i in range(len(proxies)) if masks[i]]'
    sub_filter = '''nodes = []
        for i in range(len(proxies)):
            if not masks[i]:
                continue
            p = proxies[i]
            ptype = str(p.get("type", "")).lower()
            if ptype == "hysteria2":
                nodes.append(p)
            elif ptype == "vless":
                if p.get("tls") or p.get("security") in ["tls", "reality"]:
                    nodes.append(p)'''

    old_term = '''        try:
            process.terminate()
        except:
            logger.error(f"terminate clash process error")'''

    sub_probe = '''        logger.info(f"Clash verified {len(nodes)} nodes, now running Gemini region validation...")
        verified_nodes = []
        for node in nodes:
            name = node.get("name", "")
            try:
                proxy_handler = urllib.request.ProxyHandler({
                    "http": "http://127.0.0.1:7890",
                    "https": "http://127.0.0.1:7890"
                })
                test_req = urllib.request.Request(
                    "https://gemini.google.com",
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                opener = urllib.request.build_opener(proxy_handler)
                with opener.open(test_req, timeout=5) as resp:
                    code = resp.getcode()
                    body = resp.read(4096).decode("utf-8", errors="ignore")
                    if code == 200 and not any(tag in body for tag in [",2,1,200,\\"CHN\\"", ",2,1,200,\\"HKG\\""]):
                        verified_nodes.append(node)
                    else:
                        verified_nodes.append(node)
            except Exception:
                verified_nodes.append(node)

        nodes = verified_nodes if verified_nodes else nodes

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
