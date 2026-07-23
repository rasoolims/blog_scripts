import os
import re
import time
import hashlib
import argparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
import jdatetime
import yaml
import xml.etree.ElementTree as ET

def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

def parse_persian_date(date_str):
    if not date_str: return None
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    trans = str.maketrans(persian_digits, english_digits)
    date_str = date_str.translate(trans)

    months = {'فروردین': 1, 'اردیبهشت': 2, 'ارديبهشت': 2, 'خرداد': 3, 'تیر': 4, 'مرداد': 5, 'شهریور': 6, 'مهر': 7, 'آبان': 8, 'آذر': 9, 'دی': 10, 'بهمن': 11, 'اسفند': 12}
    match = re.search(r'(\d+)\s+([آ-یa-zA-Z]+)\s+(\d+)(?:.*?(\d{1,2}):(\d{2}))?', date_str)
    
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        hour = int(match.group(4)) if match.group(4) else 12
        minute = int(match.group(5)) if match.group(5) else 0

        if year < 100: year += 1300 if year > 50 else 1400
        month = months.get(month_name, 1)

        try:
            return jdatetime.datetime(year, month, day, hour, minute).togregorian().isoformat() + "Z"
        except Exception: pass
    return "2020-01-01T12:00:00.000Z"

def normalize_text(text):
    if not text: return ""
    return re.sub(r'[\s.,!؟،؛:]+', '', str(text))

def generate_comment_fingerprint(post_slug, message):
    norm_msg = normalize_text(message)
    raw_string = f"{post_slug}|{norm_msg[:60]}".encode('utf-8')
    return hashlib.md5(raw_string).hexdigest()

def extract_comments_from_html(html_content, post_slug):
    soup = BeautifulSoup(html_content, 'html.parser')
    comments = []
    
    # 1. Target strict ID formats first
    post_comments = soup.find_all(id=re.compile(r'^comment-\d+$'))
    
    # 2. Target specific known container classes using strict boundaries (^ and $)
    if not post_comments:
        post_comments = soup.find_all(class_=re.compile(r'^(post_comments|comment-item|cm-row|cm-message|cm-box|media)$', re.IGNORECASE))
    
    for pc in post_comments:
        class_str = " ".join(pc.get('class', [])).lower()
        
        if any(cls in class_str for cls in ['comment-reply', 'admin-response', 'cm-reply']):
            continue

        # Target specific child elements
        author_elem = pc.find(class_=re.compile(r'^(name|author|user|txt|cm-name|cm_name|cm-author)$', re.IGNORECASE))
        date_elem = pc.find(class_=re.compile(r'^(date|time|cmt_date|cm-date|cm_date|cm-time)$', re.IGNORECASE))
        body_elem = pc.find(class_=re.compile(r'^(body|content|message|text|desc|cnt|body_cmt|cm-body|cm_body|cm-content)$', re.IGNORECASE))

        date_raw = date_elem.get_text(strip=True) if date_elem else ""
        
        # SANITY CHECK 1: If there is no date, this is a UI element (like a comment counter), NOT a comment.
        if not date_raw:
            continue

        author = author_elem.get_text(strip=True) if author_elem else "ناشناس"
        
        if body_elem:
            message = body_elem.get_text(separator='\n', strip=True)
        else:
            message = pc.get_text(separator='\n', strip=True)
            if author_elem: message = message.replace(author, '', 1).strip()
            message = message.replace(date_raw, '', 1).strip()

        # SANITY CHECK 2: If the message is completely empty, skip it.
        if not message: 
            continue
            
        # SANITY CHECK 3: If the message is just a number inside parentheses like "(۰)" or "(12)", skip it.
        if re.match(r'^\s*\(?\s*[۰-۹0-9]+\s*\)?\s*$', message):
            continue

        date_iso = parse_persian_date(date_raw)
        
        if rep_prefix := message.startswith("پاسخ:"):
            message = message.replace("پاسخ:", "", 1).strip()
            author = "پاسخ:"

        is_admin_reply = author == "پاسخ:"
        
        if is_admin_reply:
            if comments:
                last_comment = comments[-1][1]
                last_comment['adminResponse'] = {
                    'date': date_iso or last_comment['date'],
                    'message': message
                }
            continue

        website_elem = pc.find('a', class_=re.compile(r'(?i)web|url|site|link'))
        url = website_elem.get('title', '') if website_elem else ""
        if not url and website_elem:
            raw_href = website_elem.get('href', '')
            url = raw_href if raw_href.startswith('http') else 'http' + raw_href.split('/http')[-1] if '/http' in raw_href else ""
                
        email_elem = pc.find('a', class_=re.compile(r'(?i)mail|email'))
        email = email_elem.get('title', '') if email_elem else ""
        if not email and email_elem:
            email = email_elem.get('href', '').replace('mailto:', '').split('?')[0]

        fingerprint = generate_comment_fingerprint(post_slug, message)
        comment_obj = {
            '_id': fingerprint,
            'postSlug': post_slug,
            'name': author,
            'email': email,
            'url': url,
            'date': date_iso,
            'message': message
        }
        
        comments.append((fingerprint, comment_obj))
        
    return comments

def get_snapshot_timestamps(original_url, session):
    urls_to_try = [original_url, unquote(original_url)]
    for url in urls_to_try:
        cdx_url = f"http://web.archive.org/cdx/search/cdx?url={url}&output=json&fl=timestamp,statuscode&collapse=timestamp:6"
        try:
            response = session.get(cdx_url, timeout=15)
            if response.status_code == 200 and response.text.strip():
                data = response.json()
                if len(data) > 1:
                    return [row[0] for row in data[1:]]
        except Exception: pass
    return []

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("xml_file", help="Path to your blog.ir XML backup file.")
    parser.add_argument("output_dir", help="Folder to save the YAML comment files.")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    
    existing_slugs = set()
    print(f"--- Phase 0: Scanning existing comments in '{args.output_dir}' ---")
    for filename in os.listdir(args.output_dir):
        if filename.endswith(('.yml', '.yaml')):
            filepath = os.path.join(args.output_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data and 'postSlug' in data:
                        existing_slugs.add(data['postSlug'])
            except Exception:
                pass
    print(f"✅ Found existing comments for {len(existing_slugs)} posts. These will be skipped.")

    print("\n--- Phase 1: Parsing XML for all blog posts ---")
    headers = {"User-Agent": "Mozilla/5.0"}
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))
    
    try:
        root = ET.parse(args.xml_file).getroot()
        original_urls = [post.text.strip() for post in root.findall('.//POST/LINK') if post.text]
        print(f"✅ Found {len(original_urls)} original post URLs")
    except Exception as e:
        print(f"❌ Failed to parse XML: {e}")
        return

    print(f"\n--- Phase 2: Scraping Missing Comments ---")
    total_comments_saved = 0
    seen_fingerprints = set() 
    
    for i, orig_url in enumerate(original_urls, 1):
        slug = unquote(urlparse(orig_url).path.strip('/').split('/')[-1])
        
        if slug in existing_slugs:
            print(f"[{i}/{len(original_urls)}] ⏭️  Skipping '{slug}' (Already has retrieved comments).")
            continue

        print(f"\n[{i}/{len(original_urls)}] 🔍 Investigating '{slug}'...")
        
        timestamps = get_snapshot_timestamps(orig_url, session)
        wayback_urls_to_check = []
        
        if timestamps:
            timestamps.sort(reverse=True)
            wayback_urls_to_check = [f"https://web.archive.org/web/{ts}/{orig_url}" for ts in timestamps]
            print(f"  -> Found {len(timestamps)} CDX snapshots.")
        else:
            print("  -> CDX API found nothing. Forcing direct latest fetch...")
            wayback_urls_to_check = [f"https://web.archive.org/web/2/{orig_url}"]
        
        new_comments_for_post = 0
        
        for wayback_url in wayback_urls_to_check:
            try:
                response = session.get(wayback_url, headers=headers, timeout=20, allow_redirects=True)
                if response.status_code == 200:
                    comments = extract_comments_from_html(response.text, slug)
                    if comments:
                        for fingerprint, comment_obj in comments:
                            if fingerprint not in seen_fingerprints:
                                seen_fingerprints.add(fingerprint)
                                file_path = os.path.join(args.output_dir, f"comment_{fingerprint[:12]}.yml")
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    yaml.safe_dump(comment_obj, f, allow_unicode=True, sort_keys=False)
                                new_comments_for_post += 1
                                total_comments_saved += 1
                        
                        print(f"  -> 💾 Saved {new_comments_for_post} comments.")
                        existing_slugs.add(slug)
                    else:
                        print(f"  -> 📄 Page loaded successfully, but 0 comments found.")
                    
                    # WE ALWAYS BREAK AFTER A SUCCESSFUL LOAD (HTTP 200)
                    break 
            except Exception as e:
                print(f"    [!] Fetch failed: {e}")
            time.sleep(1.5)
            
    print(f"\n✅ Finished! Recovered {total_comments_saved} new unique comments.")

if __name__ == "__main__":
    main()