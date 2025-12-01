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
    "189.cn": {"server": "smtp.189.cn", "port": 465, "encryption": "SSL"},
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "encryption": "TLS"},
}


# === 配置管理 ===
def load_config():
    config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")
    if not Path(config_path).exists():
        raise FileNotFoundError(f"配置文件 {config_path} 不存在")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    
    print(f"✅ 配置文件加载成功: {config_path}")
    
    config = {
        "VERSION_CHECK_URL": config_data["app"]["version_check_url"],
        "SHOW_VERSION_UPDATE": config_data["app"]["show_version_update"],
        "REQUEST_INTERVAL": config_data["crawler"]["request_interval"],
        "REPORT_MODE": os.environ.get("REPORT_MODE", "").strip() or config_data["report"]["mode"],
        "RANK_THRESHOLD": config_data["report"]["rank_threshold"],
        "USE_PROXY": config_data["crawler"]["use_proxy"],
        "DEFAULT_PROXY": config_data["crawler"]["default_proxy"],
        "ENABLE_CRAWLER": os.environ.get("ENABLE_CRAWLER", "").strip().lower() in ("true", "1") 
            if os.environ.get("ENABLE_CRAWLER", "").strip() 
            else config_data["crawler"]["enable_crawler"],
        "ENABLE_NOTIFICATION": os.environ.get("ENABLE_NOTIFICATION", "").strip().lower() in ("true", "1") 
            if os.environ.get("ENABLE_NOTIFICATION", "").strip() 
            else config_data["notification"]["enable_notification"],
        "MESSAGE_BATCH_SIZE": config_data["notification"]["message_batch_size"],
        "DINGTALK_BATCH_SIZE": config_data["notification"].get("dingtalk_batch_size", 20000),
        "FEISHU_BATCH_SIZE": config_data["notification"].get("feishu_batch_size", 29000),
        "BATCH_SEND_INTERVAL": config_data["notification"]["batch_send_interval"],
        "FEISHU_MESSAGE_SEPARATOR": config_data["notification"]["feishu_message_separator"],
        "PUSH_WINDOW": {
            "ENABLED": os.environ.get("PUSH_WINDOW_ENABLED", "").strip().lower() in ("true", "1") 
                if os.environ.get("PUSH_WINDOW_ENABLED", "").strip() 
                else config_data["notification"].get("push_window", {}).get("enabled", False),
            "TIME_RANGE": {
                "START": os.environ.get("PUSH_WINDOW_START", "").strip() 
                    or config_data["notification"].get("push_window", {}).get("time_range", {}).get("start", "08:00"),
                "END": os.environ.get("PUSH_WINDOW_END", "").strip() 
                    or config_data["notification"].get("push_window", {}).get("time_range", {}).get("end", "22:00"),
            },
            "ONCE_PER_DAY": os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip().lower() in ("true", "1") 
                if os.environ.get("PUSH_WINDOW_ONCE_PER_DAY", "").strip() 
                else config_data["notification"].get("push_window", {}).get("once_per_day", True),
            "RECORD_RETENTION_DAYS": int(os.environ.get("PUSH_WINDOW_RETENTION_DAYS", "").strip() or "0") 
                or config_data["notification"].get("push_window", {}).get("push_record_retention_days", 7),
        },
        "WEIGHT_CONFIG": config_data["weight"],
        "PLATFORMS": config_data["platforms"],
    }

    # 通知渠道配置（优先环境变量）
    notification = config_data.get("notification", {})
    webhooks = notification.get("webhooks", {})
    
    config["FEISHU_WEBHOOK_URL"] = os.environ.get("FEISHU_WEBHOOK_URL", "").strip() or webhooks.get("feishu_url", "")
    config["DINGTALK_WEBHOOK_URL"] = os.environ.get("DINGTALK_WEBHOOK_URL", "").strip() or webhooks.get("dingtalk_url", "")
    config["WEWORK_WEBHOOK_URL"] = os.environ.get("WEWORK_WEBHOOK_URL", "").strip() or webhooks.get("wework_url", "")
    config["TELEGRAM_BOT_TOKEN"] = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or webhooks.get("telegram_bot_token", "")
    config["TELEGRAM_CHAT_ID"] = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or webhooks.get("telegram_chat_id", "")
    
    # ⚠️ 邮件配置（关键修复）
    config["EMAIL_FROM"] = os.environ.get("EMAIL_FROM", "").strip() or webhooks.get("email_from", "")
    config["EMAIL_PASSWORD"] = os.environ.get("EMAIL_PASSWORD", "").strip() or webhooks.get("email_password", "")
    config["EMAIL_TO"] = os.environ.get("EMAIL_TO", "").strip() or webhooks.get("email_to", "")
    config["EMAIL_SMTP_SERVER"] = os.environ.get("EMAIL_SMTP_SERVER", "").strip() or webhooks.get("email_smtp_server", "")
    config["EMAIL_SMTP_PORT"] = os.environ.get("EMAIL_SMTP_PORT", "").strip() or webhooks.get("email_smtp_port", "")
    
    config["NTFY_SERVER_URL"] = os.environ.get("NTFY_SERVER_URL", "").strip() or webhooks.get("ntfy_server_url", "https://ntfy.sh")
    config["NTFY_TOPIC"] = os.environ.get("NTFY_TOPIC", "").strip() or webhooks.get("ntfy_topic", "")
    config["NTFY_TOKEN"] = os.environ.get("NTFY_TOKEN", "").strip() or webhooks.get("ntfy_token", "")

    # 输出邮件配置状态（调试用）
    if config["EMAIL_FROM"] and config["EMAIL_PASSWORD"] and config["EMAIL_TO"]:
        print(f"📧 邮件配置已加载:")
        print(f"   发件人: {config['EMAIL_FROM']}")
        print(f"   收件人: {config['EMAIL_TO']}")
        print(f"   SMTP服务器: {config['EMAIL_SMTP_SERVER'] or '自动识别'}")
        print(f"   SMTP端口: {config['EMAIL_SMTP_PORT'] or '自动识别'}")
    else:
        print("⚠️ 邮件配置未完整，将跳过邮件发送")

    return config


CONFIG = load_config()
print(f"🚀 TrendRadar v{VERSION} 配置加载完成")
print(f"📊 监控平台数量: {len(CONFIG['PLATFORMS'])}")


# === 工具函数 ===
def get_beijing_time():
    return datetime.now(pytz.timezone("Asia/Shanghai"))


def format_date_folder():
    return get_beijing_time().strftime("%Y年%m月%d日")


def format_time_filename():
    return get_beijing_time().strftime("%H时%M分")


def clean_title(title: str) -> str:
    if not isinstance(title, str):
        title = str(title)
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
            try:
                return tuple(map(int, v.strip().split(".")))
            except:
                return (0, 0, 0)
        
        current_tuple = parse_version(current_version)
        remote_tuple = parse_version(remote_version)
        need_update = current_tuple < remote_tuple
        
        return need_update, remote_version if need_update else None
    except Exception as e:
        print(f"版本检查失败: {e}")
        return False, None


def is_first_crawl_today() -> bool:
    date_folder = format_date_folder()
    txt_dir = Path("output") / date_folder / "txt"
    if not txt_dir.exists():
        return True
    return len(list(txt_dir.glob("*.txt"))) <= 1


def html_escape(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


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
                date_str = record_file.stem.replace("push_record_", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")
                file_date = pytz.timezone("Asia/Shanghai").localize(file_date)
                if (current_time - file_date).days > retention_days:
                    record_file.unlink()
            except:
                pass

    def has_pushed_today(self) -> bool:
        record_file = self.get_today_record_file()
        if not record_file.exists():
            return False
        try:
            with open(record_file, "r", encoding="utf-8") as f:
                return json.load(f).get("pushed", False)
        except:
            return False

    def record_push(self, report_type: str):
        try:
            with open(self.get_today_record_file(), "w", encoding="utf-8") as f:
                json.dump({
                    "pushed": True,
                    "push_time": get_beijing_time().strftime("%Y-%m-%d %H:%M:%S"),
                    "report_type": report_type
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存推送记录失败: {e}")

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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Cache-Control": "no-cache",
        }
        
        for i in range(max_retries + 1):
            try:
                resp = requests.get(url, proxies=proxies, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get("status") in ["success", "cache"]:
                    print(f"✅ 获取 {alias} 成功")
                    return resp.text, id_value, alias
            except Exception as e:
                if i < max_retries:
                    wait_time = random.uniform(3, 5) + i
                    print(f"⚠️ 请求 {alias} 失败: {e}. {wait_time:.1f}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ 请求 {alias} 最终失败")
        
        return None, id_value, alias

    def crawl_websites(self, ids_list, request_interval):
        results, id_to_name, failed_ids = {}, {}, []
        
        for i, id_info in enumerate(ids_list):
            id_value = id_info[0] if isinstance(id_info, tuple) else id_info
            name = id_info[1] if isinstance(id_info, tuple) else id_value
            id_to_name[id_value] = name

            # === RSS 抓取逻辑 ===
            if id_value.startswith("http://") or id_value.startswith("https://"):
                print(f"📡 正在抓取 RSS: {name}")
                try:
                    feed = feedparser.parse(id_value)
                    if feed.bozo:  # RSS 解析错误
                        print(f"⚠️ RSS 解析警告 [{name}]: {feed.bozo_exception}")
                    
                    results[id_value] = {}
                    for index, entry in enumerate(feed.entries[:15], 1):  # 取前15条
                        title = entry.get("title", "无标题")
                        url = entry.get("link", "")
                        
                        if title in results[id_value]:
                            results[id_value][title]["ranks"].append(index)
                        else:
                            results[id_value][title] = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": url
                            }
                    
                    print(f"✅ RSS [{name}] 抓取成功，获取 {len(results[id_value])} 条")
                    
                    # RSS 抓取后也需要间隔
                    if i < len(ids_list) - 1:
                        time.sleep(max(50, request_interval + random.randint(-10, 20)) / 1000)
                    
                    continue  # 跳过后续的 API 抓取逻辑
                    
                except Exception as e:
                    print(f"❌ RSS 抓取失败 [{name}]: {e}")
                    failed_ids.append(id_value)
                    continue
            # === RSS 逻辑结束 ===

            # 普通 API 抓取
            response, _, _ = self.fetch_data(id_info)
            if response:
                try:
                    data = json.loads(response)
                    results[id_value] = {}
                    for index, item in enumerate(data.get("items", []), 1):
                        title = item.get("title")
                        if not title or not str(title).strip():
                            continue
                        
                        title = str(title).strip()
                        url = item.get("url", "")
                        mobile_url = item.get("mobileUrl", "")
                        
                        if title in results[id_value]:
                            results[id_value][title]["ranks"].append(index)
                        else:
                            results[id_value][title] = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": mobile_url
                            }
                except Exception as e:
                    print(f"❌ 解析 {name} 数据失败: {e}")
                    failed_ids.append(id_value)
            else:
                failed_ids.append(id_value)
            
            # 请求间隔
            if i < len(ids_list) - 1:
                interval = max(50, request_interval + random.randint(-10, 20))
                time.sleep(interval / 1000)
        
        print(f"\n📊 抓取完成: 成功 {len(results)} 个，失败 {len(failed_ids)} 个")
        return results, id_to_name, failed_ids


# === 数据处理 ===
def save_titles_to_file(results, id_to_name, failed_ids):
    file_path = get_output_path("txt", f"{format_time_filename()}.txt")
    
    with open(file_path, "w", encoding="utf-8") as f:
        for id_val, titles in results.items():
            name = id_to_name.get(id_val, id_val)
            if name != id_val:
                f.write(f"{id_val} | {name}\n")
            else:
                f.write(f"{id_val}\n")
            
            # 按排名排序
            sorted_titles = []
            for title, info in titles.items():
                cleaned_title = clean_title(title)
                ranks = info.get("ranks", [])
                url = info.get("url", "")
                mobile_url = info.get("mobileUrl", "")
                rank = ranks[0] if ranks else 1
                sorted_titles.append((rank, cleaned_title, url, mobile_url))
            
            sorted_titles.sort(key=lambda x: x[0])
            
            for rank, cleaned_title, url, mobile_url in sorted_titles:
                line = f"{rank}. {cleaned_title}"
                if url:
                    line += f" [URL:{url}]"
                if mobile_url:
                    line += f" [MOBILE:{mobile_url}]"
                f.write(line + "\n")
            
            f.write("\n")
        
        if failed_ids:
            f.write("==== 以下ID请求失败 ====\n")
            for id_value in failed_ids:
                f.write(f"{id_value}\n")
    
    return file_path


def load_frequency_words(frequency_file: Optional[str] = None):
    if frequency_file is None:
        frequency_file = os.environ.get("FREQUENCY_WORDS_PATH", "config/frequency_words.txt")
    
    path = Path(frequency_file)
    if not path.exists():
        raise FileNotFoundError(f"频率词文件 {frequency_file} 不存在")
    
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    word_groups = [group.strip() for group in content.split("\n\n") if group.strip()]
    processed_groups = []
    filter_words = []
    
    for group in word_groups:
        words = [word.strip() for word in group.split("\n") if word.strip()]
        group_required_words = []
        group_normal_words = []
        
        for word in words:
            if word.startswith("!"):
                filter_words.append(word[1:])
            elif word.startswith("+"):
                group_required_words.append(word[1:])
            else:
                group_normal_words.append(word)
        
        if group_required_words or group_normal_words:
            group_key = " ".join(group_normal_words) if group_normal_words else " ".join(group_required_words)
            processed_groups.append({
                "required": group_required_words,
                "normal": group_normal_words,
                "group_key": group_key
            })
    
    return processed_groups, filter_words


def matches_word_groups(title: str, word_groups: List[Dict], filter_words: List[str]) -> bool:
    if not isinstance(title, str):
        title = str(title) if title is not None else ""
    if not title.strip():
        return False
    
    if not word_groups:
        return True
    
    title_lower = title.lower()
    
    # 过滤词检查
    if any(filter_word.lower() in title_lower for filter_word in filter_words):
        return False
    
    # 词组匹配
    for group in word_groups:
        required_words = group["required"]
        normal_words = group["normal"]
        
        # 必须词检查
        if required_words:
            all_required_present = all(req_word.lower() in title_lower for req_word in required_words)
            if not all_required_present:
                continue
        
        # 普通词检查
        if normal_words:
            any_normal_present = any(normal_word.lower() in title_lower for normal_word in normal_words)
            if not any_normal_present:
                continue
        
        return True
    
    return False


def count_word_frequency(results: Dict, word_groups: List[Dict], filter_words: List[str], id_to_name: Dict):
    """统计词频"""
    if not word_groups:
        print("⚠️ 频率词配置为空，将显示所有新闻")
        word_groups = [{"required": [], "normal": [], "group_key": "全部新闻"}]
        filter_words = []
    
    word_stats = {group["group_key"]: {"count": 0, "titles": []} for group in word_groups}
    total_titles = sum(len(titles) for titles in results.values())
    
    for source_id, titles_data in results.items():
        for title, title_data in titles_data.items():
            if not matches_word_groups(title, word_groups, filter_words):
                continue
            
            source_ranks = title_data.get("ranks", [])
            source_url = title_data.get("url", "")
            source_mobile_url = title_data.get("mobileUrl", "")
            
            # 找到匹配的词组
            title_lower = str(title).lower() if not isinstance(title, str) else title.lower()
            for group in word_groups:
                required_words = group["required"]
                normal_words = group["normal"]
                
                # 全部新闻模式
                if len(word_groups) == 1 and word_groups[0]["group_key"] == "全部新闻":
                    group_key = group["group_key"]
                else:
                    # 原有匹配逻辑
                    if required_words:
                        all_required_present = all(req_word.lower() in title_lower for req_word in required_words)
                        if not all_required_present:
                            continue
                    
                    if normal_words:
                        any_normal_present = any(normal_word.lower() in title_lower for normal_word in normal_words)
                        if not any_normal_present:
                            continue
                    
                    group_key = group["group_key"]
                
                word_stats[group_key]["count"] += 1
                word_stats[group_key]["titles"].append({
                    "title": title,
                    "source_name": id_to_name.get(source_id, source_id),
                    "ranks": source_ranks,
                    "url": source_url,
                    "mobile_url": source_mobile_url
                })
                break
    
    # 排序
    stats = [
        {
            "word": group_key,
            "count": data["count"],
            "titles": data["titles"],
            "percentage": round(data["count"] / total_titles * 100, 2) if total_titles > 0 else 0
        }
        for group_key, data in word_stats.items()
    ]
    
    stats.sort(key=lambda x: x["count"], reverse=True)
    return stats, total_titles


# === 生成简单的 HTML 报告 ===
def generate_simple_html_report(stats: List[Dict], total_titles: int, failed_ids: List = None) -> str:
    """生成简化的 HTML 报告（用于邮件）"""
    file_path = get_output_path("html", f"{format_time_filename()}.html")
    now = get_beijing_time()
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrendRadar 热点分析报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        .meta {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .word-group {{ margin-bottom: 30px; padding: 15px; background: #f9f9f9; border-radius: 5px; }}
        .word-header {{ font-size: 18px; font-weight: bold; color: #4CAF50; margin-bottom: 10px; }}
        .news-item {{ margin: 10px 0; padding: 10px; background: white; border-left: 3px solid #4CAF50; }}
        .news-title {{ font-size: 15px; color: #333; }}
        .news-source {{ color: #666; font-size: 13px; }}
        .news-rank {{ color: #FF5722; font-weight: bold; }}
        .error {{ color: #f44336; background: #ffebee; padding: 10px; border-radius: 5px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 TrendRadar 热点分析报告</h1>
        <div class="meta">
            <p>📅 生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>📊 新闻总数: {total_titles} 条</p>
            <p>🎯 热点词汇: {len([s for s in stats if s['count'] > 0])} 个</p>
        </div>
"""
    
    # 添加统计数据
    for stat in stats:
        if stat["count"] == 0:
            continue
        
        html_content += f"""
        <div class="word-group">
            <div class="word-header">
                {html_escape(stat['word'])} ({stat['count']} 条新闻)
            </div>
"""
        
        for i, title_data in enumerate(stat["titles"][:10], 1):  # 只显示前10条
            title = html_escape(title_data["title"])
            source = html_escape(title_data["source_name"])
            ranks = title_data.get("ranks", [])
            rank_display = f"[{min(ranks)}]" if ranks else ""
            url = title_data.get("url", "")
            
            if url:
                title_html = f'<a href="{html_escape(url)}" target="_blank" style="color: #1976D2; text-decoration: none;">{title}</a>'
            else:
                title_html = title
            
            html_content += f"""
            <div class="news-item">
                <div class="news-title">
                    {i}. {title_html}
                </div>
                <div class="news-source">
                    来源: {source} <span class="news-rank">{rank_display}</span>
                </div>
            </div>
"""
        
        html_content += """
        </div>
"""
    
    # 添加失败信息
    if failed_ids:
        html_content += """
        <div class="error">
            <strong>⚠️ 以下平台数据获取失败:</strong><br>
"""
        for fid in failed_ids:
            html_content += f"            • {html_escape(fid)}<br>\n"
        html_content += """
        </div>
"""
    
    html_content += f"""
        <div style="text-align: center; margin-top: 30px; color: #999; font-size: 12px;">
            Powered by <a href="https://github.com/sansan0/TrendRadar" style="color: #4CAF50;">TrendRadar</a> v{VERSION}
        </div>
    </div>
</body>
</html>
"""
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return file_path


# === 邮件发送功能（完整恢复）===
def send_to_email(
    from_email: str,
    password: str,
    to_email: str,
    report_type: str,
    html_file_path: str,
    custom_smtp_server: Optional[str] = None,
    custom_smtp_port: Optional[int] = None,
) -> bool:
    """发送邮件通知（完整版）"""
    try:
        # 检查 HTML 文件
        if not html_file_path or not Path(html_file_path).exists():
            print(f"❌ HTML文件不存在: {html_file_path}")
            return False
        
        print(f"📧 准备发送邮件...")
        print(f"   HTML文件: {html_file_path}")
        
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # 确定 SMTP 配置
        domain = from_email.split("@")[-1].lower()
        
        if custom_smtp_server and custom_smtp_port:
            smtp_server = custom_smtp_server
            smtp_port = int(custom_smtp_port)
            use_tls = (smtp_port == 587)  # 587=TLS, 465=SSL
            print(f"   使用自定义SMTP: {smtp_server}:{smtp_port}")
        elif domain in SMTP_CONFIGS:
            config = SMTP_CONFIGS[domain]
            smtp_server = config["server"]
            smtp_port = config["port"]
            use_tls = (config["encryption"] == "TLS")
            print(f"   使用预设SMTP: {smtp_server}:{smtp_port} ({config['encryption']})")
        else:
            smtp_server = f"smtp.{domain}"
            smtp_port = 587
            use_tls = True
            print(f"   使用通用SMTP: {smtp_server}:{smtp_port} (TLS)")
        
        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr(("TrendRadar", from_email))
        
        recipients = [addr.strip() for addr in to_email.split(",")]
        msg["To"] = ", ".join(recipients)
        
        now = get_beijing_time()
        subject = f"TrendRadar 热点分析报告 - {report_type} - {now.strftime('%m月%d日 %H:%M')}"
        msg["Subject"] = Header(subject, "utf-8")
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        
        # 纯文本备选
        text_content = f"""
TrendRadar 热点分析报告
========================
报告类型: {report_type}
生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}

请使用支持HTML的邮件客户端查看完整报告。
"""
        text_part = MIMEText(text_content, "plain", "utf-8")
        msg.attach(text_part)
        
        # HTML 内容
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)
        
        # 发送邮件
        print(f"📤 正在发送邮件到 {to_email}...")
        
        try:
            if use_tls:
                # TLS 模式 (587端口)
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.set_debuglevel(0)
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                # SSL 模式 (465端口)
                server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
                server.set_debuglevel(0)
                server.ehlo()
            
            # 登录
            print(f"🔐 正在登录 {from_email}...")
            server.login(from_email, password)
            
            # 发送
            print(f"✉️ 正在发送邮件...")
            server.send_message(msg)
            server.quit()
            
            print(f"✅ 邮件发送成功! [{report_type}] -> {to_email}")
            return True
        
        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ 邮件认证失败: {e}")
            print(f"💡 请检查:")
            print(f"   1. 邮箱地址是否正确")
            print(f"   2. 密码/授权码是否正确（QQ/163等需要授权码）")
            print(f"   3. 是否开启了SMTP服务")
            return False
        
        except smtplib.SMTPConnectError as e:
            print(f"❌ 无法连接到SMTP服务器: {e}")
            print(f"💡 请检查网络连接和SMTP服务器地址")
            return False
        
        except smtplib.SMTPServerDisconnected:
            print(f"❌ 服务器意外断开连接")
            print(f"💡 请稍后重试或检查网络")
            return False
        
        except Exception as e:
            print(f"❌ 邮件发送失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    except Exception as e:
        print(f"❌ 邮件准备失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# === 通知发送（简化版，包含邮件）===
def send_notifications(stats: List[Dict], failed_ids: List, html_file_path: str = None):
    """发送通知到各个渠道"""
    if not CONFIG["ENABLE_NOTIFICATION"]:
        print("⚠️ 通知功能已禁用")
        return
    
    # 检查是否有内容
    has_content = any(stat["count"] > 0 for stat in stats)
    if not has_content and not failed_ids:
        print("⚠️ 没有匹配的新闻，跳过通知")
        return
    
    now = get_beijing_time()
    report_type = "热点分析"
    
    # 构建简单文本内容（用于飞书/钉钉等）
    content = f"📊 TrendRadar 热点报告 {now.strftime('%H:%M')}\n\n"
    
    for item in stats:
        if item["count"] == 0:
            continue
        content += f"🔥 {item['word']} ({item['count']}条)\n"
        for i, t in enumerate(item["titles"][:5], 1):
            ranks = t.get("ranks", [])
            rank_str = f"[{min(ranks)}]" if ranks else ""
            content += f"  {i}. [{t['source_name']}] {t['title']} {rank_str}\n"
        content += "\n"
    
    if failed_ids:
        content += f"\n⚠️ 失败源: {', '.join(failed_ids)}"
    
    # 飞书
    if CONFIG["FEISHU_WEBHOOK_URL"]:
        try:
            print("📤 发送飞书通知...")
            requests.post(
                CONFIG["FEISHU_WEBHOOK_URL"],
                json={"msg_type": "text", "content": {"text": content}},
                timeout=10
            )
            print("✅ 飞书通知发送成功")
        except Exception as e:
            print(f"❌ 飞书通知失败: {e}")
    
    # 钉钉
    if CONFIG["DINGTALK_WEBHOOK_URL"]:
        try:
            print("📤 发送钉钉通知...")
            requests.post(
                CONFIG["DINGTALK_WEBHOOK_URL"],
                json={
                    "msgtype": "markdown",
                    "markdown": {
                        "title": f"TrendRadar 热点报告",
                        "text": content
                    }
                },
                timeout=10
            )
            print("✅ 钉钉通知发送成功")
        except Exception as e:
            print(f"❌ 钉钉通知失败: {e}")
    
    # 邮件（关键修复）
    if CONFIG["EMAIL_FROM"] and CONFIG["EMAIL_PASSWORD"] and CONFIG["EMAIL_TO"]:
        if not html_file_path:
            print("⚠️ 未提供HTML文件，跳过邮件发送")
        else:
            send_to_email(
                CONFIG["EMAIL_FROM"],
                CONFIG["EMAIL_PASSWORD"],
                CONFIG["EMAIL_TO"],
                report_type,
                html_file_path,
                CONFIG["EMAIL_SMTP_SERVER"],
                CONFIG["EMAIL_SMTP_PORT"]
            )


# === 主分析器 ===
class NewsAnalyzer:
    def __init__(self):
        self.proxy_url = CONFIG["DEFAULT_PROXY"] if CONFIG["USE_PROXY"] else None
        self.is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.is_docker = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER") == "true"
        
        if self.is_github_actions:
            print("🤖 运行环境: GitHub Actions")
        elif self.is_docker:
            print("🐳 运行环境: Docker")
        else:
            print("💻 运行环境: 本地")

    def run(self):
        """执行分析流程"""
        try:
            now = get_beijing_time()
            print(f"\n{'='*60}")
            print(f"🚀 TrendRadar v{VERSION} 启动")
            print(f"⏰ 当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📋 报告模式: {CONFIG['REPORT_MODE']}")
            print(f"{'='*60}\n")
            
            if not CONFIG["ENABLE_CRAWLER"]:
                print("⚠️ 爬虫功能已禁用，程序退出")
                return
            
            # 检查推送窗口
            if CONFIG["PUSH_WINDOW"]["ENABLED"]:
                push_mgr = PushRecordManager()
                start_time = CONFIG["PUSH_WINDOW"]["TIME_RANGE"]["START"]
                end_time = CONFIG["PUSH_WINDOW"]["TIME_RANGE"]["END"]
                
                if not push_mgr.is_in_time_range(start_time, end_time):
                    print(f"⏰ 当前时间不在推送窗口 {start_time}-{end_time} 内，跳过")
                    return
                
                if CONFIG["PUSH_WINDOW"]["ONCE_PER_DAY"] and push_mgr.has_pushed_today():
                    print(f"✅ 今天已推送过，跳过")
                    return
            
            # 数据抓取
            print("📡 开始抓取数据...\n")
            fetcher = DataFetcher(self.proxy_url)
            ids = [(p["id"], p.get("name", p["id"])) for p in CONFIG["PLATFORMS"]]
            
            results, id_to_name, failed = fetcher.crawl_websites(ids, CONFIG["REQUEST_INTERVAL"])
            
            # 保存数据
            print("\n💾 保存数据...")
            txt_file = save_titles_to_file(results, id_to_name, failed)
            print(f"✅ 数据已保存: {txt_file}")
            
            # 加载频率词
            print("\n🔍 加载频率词配置...")
            groups, filters = load_frequency_words()
            print(f"✅ 加载了 {len(groups)} 个词组，{len(filters)} 个过滤词")
            
            # 统计分析
            print("\n📊 开始统计分析...")
            stats, total = count_word_frequency(results, groups, filters, id_to_name)
            
            print(f"\n📈 统计结果:")
            print(f"   总新闻数: {total}")
            print(f"   匹配词组: {len([s for s in stats if s['count'] > 0])}")
            
            for s in stats:
                if s['count'] > 0:
                    print(f"   • {s['word']}: {s['count']} 条")
            
            # 生成 HTML 报告
            print("\n📄 生成HTML报告...")
            html_file = generate_simple_html_report(stats, total, failed)
            print(f"✅ HTML报告已生成: {html_file}")
            
            # 发送通知
            print("\n📬 发送通知...")
            send_notifications(stats, failed, html_file)
            
            # 记录推送
            if CONFIG["PUSH_WINDOW"]["ENABLED"] and CONFIG["PUSH_WINDOW"]["ONCE_PER_DAY"]:
                push_mgr = PushRecordManager()
                push_mgr.record_push("热点分析")
            
            # 打开浏览器（仅本地环境）
            if not self.is_github_actions and not self.is_docker:
                print(f"\n🌐 正在打开浏览器...")
                file_url = "file://" + str(Path(html_file).resolve())
                webbrowser.open(file_url)
            
            print(f"\n{'='*60}")
            print(f"✅ TrendRadar 运行完成!")
            print(f"{'='*60}\n")
        
        except Exception as e:
            print(f"\n❌ 程序运行错误: {e}")
            import traceback
            traceback.print_exc()
            raise


def main():
    try:
        analyzer = NewsAnalyzer()
        analyzer.run()
    except FileNotFoundError as e:
        print(f"\n❌ 配置文件错误: {e}")
        print("\n请确保以下文件存在:")
        print("  • config/config.yaml")
        print("  • config/frequency_words.txt")
    except Exception as e:
        print(f"\n❌ 程序运行错误: {e}")
        raise


if __name__ == "__main__":
    main()
