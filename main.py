# coding=utf-8

import json
import os
import random
import re
import time
import webbrowser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

import pytz
import requests
import yaml
import feedparser  # 确保 requirements.txt 里加了 feedparser


VERSION = "3.0.5"


# === SMTP邮件配置 ===
SMTP_CONFIGS = {
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "encryption": "TLS"},
    "qq.com": {"server": "smtp.qq.com", "port": 465, "encryption": "SSL"},
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "encryption": "TLS"},
    "163.com": {"server": "smtp.163.com", "port": 465, "encryption": "SSL"},
    "126.com": {"server": "smtp.126.com", "port": 465, "encryption": "SSL"},
    "sina.com": {"server": "smtp.sina.com", "port": 465, "encryption": "SSL"},
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "encryption": "SSL"},
}


# === 配置管理 ===
def load_config():
    config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")
    if not Path(config_path).exists():
        raise FileNotFoundError(f"配置文件 {config_path} 不存在")
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    
    config = {
        "VERSION_CHECK_URL": config_data["app"]["version_check_url"],
        "SHOW_VERSION_UPDATE": config_data["app"]["show_version_update"],
        "REQUEST_INTERVAL": config_data["crawler"]["request_interval"],
        "REPORT_MODE": os.environ.get("REPORT_MODE", "").strip() or config_data["report"]["mode"],
        "RANK_THRESHOLD": config_data["report"]["rank_threshold"],
        "USE_PROXY": config_data["crawler"]["use_proxy"],
        "DEFAULT_PROXY": config_data["crawler"]["default_proxy"],
        "ENABLE_CRAWLER": os.environ.get("ENABLE_CRAWLER", "").strip().lower() in ("true", "1") if os.environ.get("ENABLE_CRAWLER", "").strip() else config_data["crawler"]["enable_crawler"],
        "ENABLE_NOTIFICATION": os.environ.get("ENABLE_NOTIFICATION", "").strip().lower() in ("true", "1") if os.environ.get("ENABLE_NOTIFICATION", "").strip() else config_data["notification"]["enable_notification"],
        "MESSAGE_BATCH_SIZE": config_data["notification"]["message_batch_size"],
        "DINGTALK_BATCH_SIZE": config_data["notification"].get("dingtalk_batch_size", 20000),
        "FEISHU_BATCH_SIZE": config_data["notification"].get("feishu_batch_size", 29000),
        "BATCH_SEND_INTERVAL": config_data["notification"]["batch_send_interval"],
        "FEISHU_MESSAGE_SEPARATOR": config_data["notification"]["feishu_message_separator"],
        "PUSH_WINDOW": {
            "ENABLED": os.environ.get("PUSH_WINDOW_ENABLED", "").strip().lower() in ("true", "1") if os.environ.get("PUSH_WINDOW_ENABLED", "").strip() else config_data["notification"].get("push_window", {}).get("enabled", False),
            "TIME_RANGE": {
                "START": os.environ.get("PUSH_WINDOW_START", "").strip() or config_data["notification"].get("push_window", {}).get("time_range", {}).get("start", "08:00"),
                "END": os.environ.get("PUSH_WINDOW_END", "").strip() or config_data["notification"].get("push_window", {}).get("time_range", {}).get("end", "22:00"),
            },
            "ONCE_PER_DAY": os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip().lower() in ("true", "1") if os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip() else config_data["notification"].get("push_window", {}).get("once_per_day", True),
            "RECORD_RETENTION_DAYS": int(os.environ.get("PUSH_WINDOW_RETENTION_DAYS", "").strip() or "0") or config_data["notification"].get("push_window", {}).get("push_record_retention_days", 7),
        },
        "WEIGHT_CONFIG": config_data["weight"],
        "PLATFORMS": config_data["platforms"],
    }

    notification = config_data.get("notification", {})
    webhooks = notification.get("webhooks", {})
    config["FEISHU_WEBHOOK_URL"] = os.environ.get("FEISHU_WEBHOOK_URL", "").strip() or webhooks.get("feishu_url", "")
    config["DINGTALK_WEBHOOK_URL"] = os.environ.get("DINGTALK_WEBHOOK_URL", "").strip() or webhooks.get("dingtalk_url", "")
    config["WEWORK_WEBHOOK_URL"] = os.environ.get("WEWORK_WEBHOOK_URL", "").strip() or webhooks.get("wework_url", "")
    config["TELEGRAM_BOT_TOKEN"] = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or webhooks.get("telegram_bot_token", "")
    config["TELEGRAM_CHAT_ID"] = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or webhooks.get("telegram_chat_id", "")
    config["EMAIL_FROM"] = os.environ.get("EMAIL_FROM", "").strip() or webhooks.get("email_from", "")
    config["EMAIL_PASSWORD"] = os.environ.get("EMAIL_PASSWORD", "").strip() or webhooks.get("email_password", "")
    config["EMAIL_TO"] = os.environ.get("EMAIL_TO", "").strip() or webhooks.get("email_to", "")
    config["EMAIL_SMTP_SERVER"] = os.environ.get("EMAIL_SMTP_SERVER", "").strip() or webhooks.get("email_smtp_server", "")
    config["EMAIL_SMTP_PORT"] = os.environ.get("EMAIL_SMTP_PORT", "").strip() or webhooks.get("email_smtp_port", "")
    config["NTFY_SERVER_URL"] = os.environ.get("NTFY_SERVER_URL", "https://ntfy.sh").strip() or webhooks.get("ntfy_server_url", "https://ntfy.sh")
    config["NTFY_TOPIC"] = os.environ.get("NTFY_TOPIC", "").strip() or webhooks.get("ntfy_topic", "")
    config["NTFY_TOKEN"] = os.environ.get("NTFY_TOKEN", "").strip() or webhooks.get("ntfy_token", "")

    return config

CONFIG = load_config()

# === 工具函数 ===
def get_beijing_time():
    return datetime.now(pytz.timezone("Asia/Shanghai"))

def format_date_folder():
    return get_beijing_time().strftime("%Y年%m月%d日")

def format_time_filename():
    return get_beijing_time().strftime("%H时%M分")

def clean_title(title: str) -> str:
    if not isinstance(title, str): title = str(title)
    cleaned_title = title.replace("\n", " ").replace("\r", " ")
    cleaned_title = re.sub(r"\s+", " ", cleaned_title)
    return cleaned_title.strip()

def ensure_directory_exists(directory: str):
    Path(directory).mkdir(parents=True, exist_ok=True)

def get_output_path(subfolder: str, filename: str) -> str:
    date_folder = format_date_folder()
    output_dir = Path("output") / date_folder / subfolder
    ensure_directory_exists(str(output_dir))
    return str(output_dir / filename)

def check_version_update(current_version: str, version_url: str, proxy_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    try:
        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        headers = {"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}
        response = requests.get(version_url, proxies=proxies, headers=headers, timeout=10)
        response.raise_for_status()
        remote_version = response.text.strip()
        
        def parse_version(v):
            try: return tuple(map(int, v.strip().split(".")))
            except: return (0, 0, 0)
            
        return parse_version(current_version) < parse_version(remote_version), remote_version
    except:
        return False, None

def is_first_crawl_today() -> bool:
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"
    if not txt_dir.exists(): return True
    return len(list(txt_dir.glob("*.txt"))) <= 1

def html_escape(text: str) -> str:
    if not isinstance(text, str): text = str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

# === 推送记录管理 ===
class PushRecordManager:
    def __init__(self):
        self.record_dir = Path("output") / ".push_records"
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_old_records()

    def get_today_record_file(self) -> Path:
        return self.record_dir / f"push_record_{get_beijing_time().strftime('%Y%m%d')}.json"

    def cleanup_old_records(self):
        retention_days = CONFIG["PUSH_WINDOW"]["RECORD_RETENTION_DAYS"]
        current_time = get_beijing_time()
        for record_file in self.record_dir.glob("push_record_*.json"):
            try:
                file_date = datetime.strptime(record_file.stem.replace("push_record_", ""), "%Y%m%d")
                file_date = pytz.timezone("Asia/Shanghai").localize(file_date)
                if (current_time - file_date).days > retention_days: record_file.unlink()
            except: pass

    def has_pushed_today(self) -> bool:
        record_file = self.get_today_record_file()
        if not record_file.exists(): return False
        try:
            with open(record_file, "r", encoding="utf-8") as f: return json.load(f).get("pushed", False)
        except: return False

    def record_push(self, report_type: str):
        try:
            with open(self.get_today_record_file(), "w", encoding="utf-8") as f:
                json.dump({"pushed": True, "push_time": get_beijing_time().strftime("%Y-%m-%d %H:%M:%S"), "report_type": report_type}, f)
        except: pass

    def is_in_time_range(self, start_time: str, end_time: str) -> bool:
        now_str = get_beijing_time().strftime("%H:%M")
        return start_time <= now_str <= end_time

# === 数据获取 ===
class DataFetcher:
    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url

    def fetch_data(self, id_info, max_retries=2):
        id_value = id_info[0] if isinstance(id_info, tuple) else id_info
        alias = id_info[1] if isinstance(id_info, tuple) else id_value
        url = f"https://newsnow.busiyi.world/api/s?id={id_value}&latest"
        proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None
        headers = {"User-Agent": "Mozilla/5.0"}
        
        for i in range(max_retries + 1):
            try:
                resp = requests.get(url, proxies=proxies, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") in ["success", "cache"]: return resp.text, id_value, alias
            except:
                if i < max_retries: time.sleep(random.uniform(3, 5))
        return None, id_value, alias

    def crawl_websites(self, ids_list, request_interval):
        results, id_to_name, failed_ids = {}, {}, []
        
        for i, id_info in enumerate(ids_list):
            id_value = id_info[0] if isinstance(id_info, tuple) else id_info
            name = id_info[1] if isinstance(id_info, tuple) else id_value
            id_to_name[id_value] = name

            # === RSS 逻辑 ===
            if id_value.startswith("http"):
                print(f"正在抓取 RSS: {name}")
                try:
                    feed = feedparser.parse(id_value)
                    results[id_value] = {}
                    for index, entry in enumerate(feed.entries[:15], 1):
                        title = entry.title
                        url = entry.link
                        if title in results[id_value]: results[id_value][title]["ranks"].append(index)
                        else: results[id_value][title] = {"ranks": [index], "url": url, "mobileUrl": url}
                    continue
                except Exception as e:
                    print(f"RSS Error [{name}]: {e}")
                    failed_ids.append(id_value)
                    continue
            # === RSS 逻辑结束 ===

            response, _, _ = self.fetch_data(id_info)
            if response:
                try:
                    data = json.loads(response)
                    results[id_value] = {}
                    for index, item in enumerate(data.get("items", []), 1):
                        title = item["title"]
                        if title in results[id_value]: results[id_value][title]["ranks"].append(index)
                        else: results[id_value][title] = {"ranks": [index], "url": item.get("url", ""), "mobileUrl": item.get("mobileUrl", "")}
                except: failed_ids.append(id_value)
            else: failed_ids.append(id_value)
            
            if i < len(ids_list) - 1: time.sleep(max(50, request_interval + random.randint(-10, 20)) / 1000)
            
        return results, id_to_name, failed_ids

# === 数据处理与报告 (简化版，核心逻辑保留) ===
def save_titles_to_file(results, id_to_name, failed_ids):
    file_path = get_output_path("txt", f"{format_time_filename()}.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        for id_val, titles in results.items():
            name = id_to_name.get(id_val, id_val)
            f.write(f"{id_val} | {name}\n")
            sorted_titles = sorted([(info["ranks"][0], t, info["url"]) for t, info in titles.items()], key=lambda x: x[0])
            for rank, title, url in sorted_titles:
                f.write(f"{rank}. {clean_title(title)} [URL:{url}]\n")
            f.write("\n")
    return file_path

def load_frequency_words():
    path = Path(os.environ.get("FREQUENCY_WORDS_PATH", "config/frequency_words.txt"))
    if not path.exists(): return [{"required":[], "normal":[], "group_key":"全部新闻"}], []
    with open(path, "r", encoding="utf-8") as f: content = f.read()
    groups, filters = [], []
    for g in content.split("\n\n"):
        if not g.strip(): continue
        req, norm = [], []
        for w in g.split("\n"):
            w = w.strip()
            if not w: continue
            if w.startswith("!"): filters.append(w[1:])
            elif w.startswith("+"): req.append(w[1:])
            else: norm.append(w)
        if req or norm: groups.append({"required": req, "normal": norm, "group_key": " ".join(norm) or " ".join(req)})
    return groups, filters

def matches_word_groups(title, groups, filters):
    title_lower = title.lower()
    if any(f.lower() in title_lower for f in filters): return False
    if not groups: return True
    for g in groups:
        if g["required"] and not all(w.lower() in title_lower for w in g["required"]): continue
        if g["normal"] and not any(w.lower() in title_lower for w in g["normal"]): continue
        return True
    return False

def count_word_frequency(results, groups, filters, id_to_name):
    stats = {g["group_key"]: {"count": 0, "titles": []} for g in groups}
    for src_id, titles in results.items():
        for title, info in titles.items():
            if not matches_word_groups(title, groups, filters): continue
            for g in groups:
                if (g["required"] and not all(w.lower() in title.lower() for w in g["required"])) or \
                   (g["normal"] and not any(w.lower() in title.lower() for w in g["normal"])): continue
                stats[g["group_key"]]["count"] += 1
                stats[g["group_key"]]["titles"].append({
                    "title": title, "source_name": id_to_name.get(src_id, src_id),
                    "ranks": info["ranks"], "url": info["url"], "mobile_url": info.get("mobileUrl", "")
                })
                break
    return sorted([{"word": k, **v} for k, v in stats.items()], key=lambda x: x["count"], reverse=True)

# === 发送通知 (简化适配) ===
def send_to_feishu(url, content):
    try: requests.post(url, json={"msg_type": "text", "content": {"text": content}}, timeout=10)
    except Exception as e: print(f"Feishu Error: {e}")
        
def send_email(content):
    """
    发送邮件的核心逻辑
    """
    # 1. 检查配置是否完整
    if not CONFIG["EMAIL_FROM"] or not CONFIG["EMAIL_PASSWORD"] or not CONFIG["EMAIL_TO"]:
        print("⚠️ 邮件配置不完整，跳过发送")
        return

    try:
        print("📧 正在发送邮件...")
        msg = MIMEMultipart()
        msg['From'] = formataddr((Header("TrendRadar", 'utf-8').encode(), CONFIG["EMAIL_FROM"]))
        # 处理多个收件人
        to_list = CONFIG["EMAIL_TO"].replace("，", ",").split(",")
        msg['To'] = ",".join([formataddr((Header("Subscriber", 'utf-8').encode(), to.strip())) for to in to_list])
        msg['Subject'] = Header(f"TrendRadar 热点报告 - {get_beijing_time().strftime('%Y-%m-%d %H:%M')}", 'utf-8')
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid()

        # 邮件正文
        msg.attach(MIMEText(content, 'plain', 'utf-8'))

        # 2. 自动识别 SMTP 服务器配置 (如果配置里没填，尝试自动推断)
        smtp_server = CONFIG["EMAIL_SMTP_SERVER"]
        smtp_port = int(CONFIG["EMAIL_SMTP_PORT"]) if CONFIG["EMAIL_SMTP_PORT"] else 465

        # 3. 连接服务器
        if smtp_port == 465:
            # SSL 连接 (QQ邮箱, 163等)
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            # TLS 连接 (Outlook, Gmail等)
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.starttls()

        # 4. 登录并发送
        server.login(CONFIG["EMAIL_FROM"], CONFIG["EMAIL_PASSWORD"])
        server.sendmail(CONFIG["EMAIL_FROM"], to_list, msg.as_string())
        server.quit()
        print("✅ 邮件发送成功！")

    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")

def send_notifications(stats, failed_ids):
    if not stats and not failed_ids: return
    
    # 构造消息内容
    content = f"TrendRadar 热点报告 {get_beijing_time().strftime('%H:%M')}\n\n"
    for item in stats:
        if item["count"] == 0: continue
        content += f"🔥 {item['word']} ({item['count']}条)\n"
        for i, t in enumerate(item["titles"][:5], 1):
            content += f"  {i}. [{t['source_name']}] {t['title']}\n"
            content += f"     链接: {t['url']}\n" # 把链接加上，方便点击
        content += "\n"
    
    if failed_ids: 
        content += f"\n⚠️ 抓取失败的数据源: {', '.join(failed_ids)}\n"
        content += "请检查网络代理设置或 config.yaml 中的 ID 是否正确。\n"

    print("--- 准备发送通知 ---")
    
    # 发送飞书
    if CONFIG["FEISHU_WEBHOOK_URL"]: 
        send_to_feishu(CONFIG["FEISHU_WEBHOOK_URL"], content)
    
    # === 关键：这里调用邮件发送 ===
    if CONFIG["EMAIL_TO"]:
        send_email(content)

class NewsAnalyzer:
    def run(self):
        print("开始运行 TrendRadar...")
        fetcher = DataFetcher(CONFIG["DEFAULT_PROXY"] if CONFIG["USE_PROXY"] else None)
        ids = [(p["id"], p.get("name", p["id"])) for p in CONFIG["PLATFORMS"]]
        results, id_to_name, failed = fetcher.crawl_websites(ids, CONFIG["REQUEST_INTERVAL"])
        save_titles_to_file(results, id_to_name, failed)
        
        groups, filters = load_frequency_words()
        stats = count_word_frequency(results, groups, filters, id_to_name)
        
        # 简单打印结果
        for s in stats:
            if s['count'] > 0: print(f"{s['word']}: {s['count']}")
            
        if CONFIG["ENABLE_NOTIFICATION"]:
            send_notifications(stats, failed)

if __name__ == "__main__":
    NewsAnalyzer().run()
