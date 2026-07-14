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

# Configure YAML to use nice multi-line strings for messages
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

def parse_persian_date(date_str):
    if not date_str:
        return None
        
    persian_digits = '۰۱۲۳۴۵۶۷۸۹'
    english_digits = '0123456789'
    trans = str.maketrans(persian_digits, english_digits)
    date_str = date_str.translate(trans)

    months = {
        'فروردین': 1, 'اردیبهشت': 2, 'ارديبهشت': 2, 'خرداد': 3,
        'تیر': 4, 'مرداد': 5, 'شهریور': 6,
        'مهر': 7, 'آبان': 8, 'آذر': 9,
        'دی': 10, 'بهمن': 11, 'اسفند': 12
    }

    match = re.search(r'(\d+)\s+([آ-یa-zA-Z]+)\s+(\d+)(?:.*?(\d{1,2}):(\d{2}))?', date_str)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        hour = int(match.group(4)) if match.group(4) else 12
        minute = int(match.group(5)) if match.group(5) else 0

        if year < 100:
            if year > 50:
                year += 1300
            else:
                year += 1400

        month = months.get(month_name, 1)

        try:
            j_date = jdatetime.datetime(year, month, day, hour, minute)
            return j_date.togregorian().isoformat() + "Z"
        except Exception:
            pass
            
    return "2020-01-01T12:00:00.000Z"

def generate_comment_fingerprint(post_slug, author, date_iso, message):
    """Creates a unique hash for a comment to prevent duplicates."""
    raw_string = f"{post_slug}|{author}|{date_iso}|{message[:50]}".encode('utf-8')
    return hashlib.md5(raw_string).hexdigest()

def extract_comments_from_html(html_content, post_slug):
    soup = BeautifulSoup(html_content, 'html.parser')
    comments = []
    
    # STRATEGY 1: Search by blog.ir's default element ID structure
    post_comments = soup.find_all(id=re.compile(r'^comment-\d+$'))
    
    # STRATEGY 2: Fallback to aggressive regex matching for varied themes
    if not post_comments:
        post_comments = soup.find_all(class_=re.compile(r'\b(comment|post-comment|cm-row|cm-message|comment-item|cm-box)\b'))
    
    for pc in post_comments:
        if 'comments' in pc.get('class', []) and len(pc.get('class', [])) == 1:
            continue

        author_elem = pc.find(class_=re.compile(r'(?i)name|author|cm-name|cm_name|cm-author'))
        date_elem = pc.find(class_=re.compile(r'(?i)date|time|cm-date|cm_date|cm-time'))
        body_elem = pc.find(class_=re.compile(r'(?i)body|content|cm-body|cm_body|cm-content|message|text'))

        author = author_elem.get_text(strip=True) if author_elem else "ناشناس"
        
        date_raw = date_elem.get_text(strip=True) if date_elem else ""
        date_iso = parse_persian_date(date_raw)
        
        message = body_elem.get_text(separator='\n', strip=True) if body_elem else ""
        
        if not message:
            continue

        website_elem = pc.find('a', class_=re.compile(r'(?i)web|url|site|link'))
        url = website_elem.get('title', '') if website_elem else ""
        if not url and website_elem:
            raw_href = website_elem.get('href', '')
            if '/http' in raw_href:
                url = 'http' + raw_href.split('/http')[-1]
            elif raw_href.startswith('http'):
                url = raw_href
                
        email_elem = pc.find('a', class_=re.compile(r'(?i)mail|email'))
        email = email_elem.get('title', '') if email_elem else ""
        if not email and email_elem:
            raw_href = email_elem.get('href', '')
            email = raw_href.replace('mailto:', '').split('?')[0]

        reply_data = None
        reply_elem = pc.find(class_=re.compile(r'(?i)reply|answer|admin-response|cm-reply'))
        
        if reply_elem:
            rep_date_elem = reply_elem.find(class_=re.compile(r'(?i)date|time'))
            rep_date_raw = rep_date_elem.get_text(strip=True) if rep_date_elem else ""
            rep_date_iso = parse_persian_date(rep_date_raw)
            
            rep_body_elem = reply_elem.find(class_=re.compile(r'(?i)body|content|text|message'))
            if not rep_body_elem:
                 rep_body_elem = reply_elem
            
            rep_message = rep_body_elem.get_text(separator='\n', strip=True)
            if rep_message.startswith("پاسخ:"):
                rep_message = rep_message.replace("پاسخ:", "", 1).strip()
                
            if rep_message:
                reply_data = {
                    'date': rep_date_iso or date_iso,
                    'message': rep_message
                }

        fingerprint = generate_comment_fingerprint(post_slug, author, date_iso, message)

        comment_obj = {
            '_id': fingerprint,
            'postSlug': post_slug,
            'name': author,
            'email': email,
            'url': url,
            'date': date_iso,
            'message': message
        }
        
        if reply_data:
            comment_obj['adminResponse'] = reply_data
            
        comments.append((fingerprint, comment_obj))
        
    return comments

def get_snapshot_timestamps(original_url, session):
    cdx_url = f"http://web.archive.org/cdx/search/cdx?url={original_url}&output=json&fl=timestamp,statuscode&filter=statuscode:200&collapse=timestamp:6"
    try:
        response = session.get(cdx_url, timeout=15)
        if response.status_code == 200 and response.text.strip():
            data = response.json()
            if len(data) > 1:
                return [row[0] for row in data[1:]]
    except Exception as e:
        print(f"    [!] Failed to fetch CDX timeline: {e}")
    return []

def main():
    parser = argparse.ArgumentParser(description="Smart scrape blog.ir comments (starts from newest snapshot and trusts it).")
    parser.add_argument("xml_file", help="Path to your blog.ir XML backup file.")
    parser.add_argument("output_dir", help="Folder to save the YAML comment files.")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    print("\n--- Phase 1: Parsing XML for all blog posts ---")
    
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))
    
    original_urls = set()
    try:
        tree = ET.parse(args.xml_file)
        root = tree.getroot()
        for post in root.findall('.//POST/LINK'):
            if post.text:
                original_urls.add(post.text.strip())
        print(f"✅ Found {len(original_urls)} original post URLs in the XML file!")
    except Exception as e:
        print(f"❌ Failed to parse XML file: {e}")
        return

    print(f"\n--- Phase 2: Hyper-Fast Scraping from {len(original_urls)} Posts ---")
    
    total_comments_saved = 0
    seen_fingerprints = set() 
    
    for i, orig_url in enumerate(original_urls, 1):
        slug = unquote(urlparse(orig_url).path.strip('/').split('/')[-1])
        print(f"\n[{i}/{len(original_urls)}] Investigating timeline for '{slug}'...")
        
        timestamps = get_snapshot_timestamps(orig_url, session)
        
        if not timestamps:
            print("  -> No valid snapshots found in CDX API. Skipping.")
            time.sleep(1)
            continue
            
        timestamps.sort(reverse=True)
        print(f"  -> Found {len(timestamps)} historical monthly snapshots. Checking newest first...")
        
        new_comments_for_post = 0
        
        for ts in timestamps:
            wayback_url = f"https://web.archive.org/web/{ts}/{orig_url}"
            try:
                response = session.get(wayback_url, headers=headers, timeout=20)
                
                # If the snapshot successfully loads...
                if response.status_code == 200:
                    comments = extract_comments_from_html(response.text, slug)
                    
                    if comments:
                        for fingerprint, comment_obj in comments:
                            if fingerprint not in seen_fingerprints:
                                seen_fingerprints.add(fingerprint)
                                
                                file_name = f"comment_{ts}_{fingerprint[:8]}.yml"
                                file_path = os.path.join(args.output_dir, file_name)
                                
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    yaml.safe_dump(comment_obj, f, allow_unicode=True, sort_keys=False)
                                    
                                new_comments_for_post += 1
                                total_comments_saved += 1
                                
                        print(f"  -> Found {new_comments_for_post} comments in snapshot {ts}. Moving to next post.")
                    else:
                        print(f"  -> Snapshot {ts} loaded successfully but has 0 comments. Moving to next post.")
                    
                    # CRITICAL LOGIC: Break out immediately upon ANY successful page load!
                    break 
                        
            except Exception as e:
                print(f"    [!] Failed to fetch snapshot {ts}: {e}")
            
            # Polite delay between snapshot fetches if we actually have to loop
            time.sleep(1.5)
            
    print(f"\n✅ Finished! Successfully recovered {total_comments_saved} unique comments.")
    print(f"Check your '{args.output_dir}' folder.")

if __name__ == "__main__":
    main()