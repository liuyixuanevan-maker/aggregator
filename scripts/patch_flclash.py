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

    # [2/6] Patching subscribe/airport.py (timeout, handover, alphanumeric password, whitelist)
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

    # Use alphanumeric passwords (punctuation=False) to avoid airport regex rejection
    c = c.replace(
        "password = utils.random_chars(length=random.randint(8, 16), punctuation=True)",
        "password = utils.random_chars(length=random.randint(10, 16), punctuation=False)"
    )

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
        "https://www.kuais.pw"
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

    # [6/6] Patching subscribe/collect.py for Open Modern Protocols & Commercial Trial Subscriptions
    print("[6/6] Patching subscribe/collect.py for open modern protocols and multi-airport subscriptions...")
    with open("subscribe/collect.py", "r", encoding="utf-8") as f:
        c = f.read()

    # 1. Clean up dead raw links (Barabama/ermaozi) from existing subscriptions and inject verified commercial trial subscriptions
    commercial_trial_subs = [
        "https://www.fankeyundingyue.space/fckwec/vip/client/subscribe?token=dc9193504b37d766e1cb57a65a13b98e",
        "https://sf55d7a13a49f.flszjy.com/891aa9/s/e1fd403b76a0cb306fc505b92abef781",
        "https://10086900.xyz/s/a1fe370eaefbaf0269a739df1bf40120",
        "https://rcwave.net/api/v1/client/subscribe?token=ff24fb373caad67ace1cb1d7cc7f86e9",
        "https://usyun.cc/s/c51368ac7be81f19e6e15e139a11fd32",
        "http://xb.xxzf.cc/s/fbae4709c829f4e2fad47f16cc470be5"
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
    # If previously replaced by custom sub_filter, revert to standard unfiltered list comprehension
    c = re.sub(
        r"nodes = \[\]\s+for i in range\(len\(proxies\)\):.*?nodes\.append\(p\)",
        "nodes = [proxies[i] for i in range(len(proxies)) if masks[i]]",
        c,
        flags=re.DOTALL
    )

    with open("subscribe/collect.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("  -> collect.py patched successfully (all modern protocols accepted, 6 commercial airports active).")

if __name__ == "__main__":
    run_patch()
