import os
import re
import hashlib
import argparse
from bs4 import BeautifulSoup
import jdatetime
import yaml

# --- YAML Formatting Setup ---
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

# --- Helper Functions ---
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

# --- Core Extraction Logic ---
def extract_comments_from_html(html_content, post_slug):
    soup = BeautifulSoup(html_content, 'html.parser')
    comments = []
    
    # 1. Target strict ID formats first
    raw_containers = soup.find_all(id=re.compile(r'^comment-\d+$'))
    
    # 2. Target container classes for BOTH old and new themes
    if not raw_containers:
        raw_containers = soup.find_all(class_=re.compile(r'^(post_comments|post-comments|post-comment|comment-item|cm-row|cm-message|cm-box|media)$', re.IGNORECASE))
    
    # 3. Prevent duplicate parsing by filtering out nested containers
    post_comments = []
    for pc in raw_containers:
        if not any(parent in raw_containers for parent in pc.parents):
            post_comments.append(pc)
            
    for pc in post_comments:
        class_str = " ".join(pc.get('class', [])).lower()
        
        # Support for both old theme (txt/body_cmt) and new theme (comment-name/comment-body)
        author_elem = pc.find(class_=re.compile(r'^(name|author|user|txt|cm-name|cm_name|cm-author|comment-name)$', re.IGNORECASE))
        date_elem = pc.find(class_=re.compile(r'^(date|time|cmt_date|cm-date|cm_date|cm-time|comment-date)$', re.IGNORECASE))
        body_elem = pc.find(class_=re.compile(r'^(body|content|message|text|desc|cnt|body_cmt|cm-body|cm_body|cm-content|comment-body|comment-body-content)$', re.IGNORECASE))

        date_raw = date_elem.get_text(strip=True) if date_elem else ""
        
        # SANITY CHECK 1: Must have a date
        if not date_raw:
            continue

        author = author_elem.get_text(strip=True) if author_elem else "ناشناس"
        
        if body_elem:
            message = body_elem.get_text(separator='\n', strip=True)
        else:
            message = pc.get_text(separator='\n', strip=True)
            if author_elem: message = message.replace(author, '', 1).strip()
            message = message.replace(date_raw, '', 1).strip()

        message = message.strip()
        
        # SANITY CHECK 2 & 3: Not empty, not a UI counter
        if not message or re.match(r'^\s*\(?\s*[۰-۹0-9]+\s*\)?\s*$', message):
            continue

        date_iso = parse_persian_date(date_raw)
        
        # Handle Sibling Admin Replies (Older Themes)
        if rep_prefix := message.startswith("پاسخ:"):
            message = message.replace("پاسخ:", "", 1).strip()
            author = "پاسخ:"

        is_admin_reply = author == "پاسخ:" or author == "پاسخ"
        
        if is_admin_reply:
            if comments:
                last_comment = comments[-1][1]
                last_comment['adminResponse'] = {
                    'date': date_iso or last_comment['date'],
                    'message': message
                }
            continue

        # Handle Nested Admin Replies (Newer Themes like the 2025 snapshot)
        reply_data = None
        reply_elem = pc.find(class_=re.compile(r'^(comment-reply|admin-response|cm-reply)$', re.IGNORECASE))
        
        if reply_elem:
            rep_date_elem = reply_elem.find(class_=re.compile(r'^(date|time|comment-reply-date|cm-date|cm_date|comment-date)$', re.IGNORECASE))
            rep_body_elem = reply_elem.find(class_=re.compile(r'^(body|content|comment-reply-body|cm-body|cm_body|comment-body|text|message)$', re.IGNORECASE))
            
            rep_message = rep_body_elem.get_text(separator='\n', strip=True) if rep_body_elem else reply_elem.get_text(separator='\n', strip=True)
            
            # Clean up explicit "پاسخ:" labels
            if rep_message.startswith("پاسخ:"):
                rep_message = rep_message.replace("پاسخ:", "", 1).strip()
            elif rep_message.startswith("پاسخ"):
                rep_message = rep_message.replace("پاسخ", "", 1).strip()
                
            if rep_message:
                rep_date_raw = rep_date_elem.get_text(strip=True) if rep_date_elem else ""
                reply_data = {
                    'date': parse_persian_date(rep_date_raw) or date_iso,
                    'message': rep_message
                }
                
            # If the parser couldn't isolate the main body and grabbed the whole container, remove the reply text
            if not body_elem:
                reply_raw_text = reply_elem.get_text(separator='\n', strip=True)
                message = message.replace(reply_raw_text, '').strip()

        # Extract URLs and Emails
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
        
        if reply_data:
            comment_obj['adminResponse'] = reply_data
            
        comments.append((fingerprint, comment_obj))
        
    return comments

# --- Main Script Runner ---
def main():
    parser = argparse.ArgumentParser(description="Extract comments from local HTML snapshots.")
    parser.add_argument("raw_folder", help="Folder containing the downloaded HTML snapshots.")
    parser.add_argument("target_folder", help="Folder to save the final YAML comments.")
    args = parser.parse_args()

    os.makedirs(args.target_folder, exist_ok=True)
    
    total_extracted = 0
    seen_fingerprints = set()

    print(f"🔍 Scanning local folder: {args.raw_folder}\n" + "-"*40)

    for slug in os.listdir(args.raw_folder):
        slug_path = os.path.join(args.raw_folder, slug)
        
        if not os.path.isdir(slug_path):
            continue
            
        post_comments_count = 0
        html_files = sorted([f for f in os.listdir(slug_path) if f.endswith('.html')])
        
        for html_file in html_files:
            file_path = os.path.join(slug_path, html_file)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            comments = extract_comments_from_html(html_content, slug)
            
            for fingerprint, comment_obj in comments:
                if fingerprint not in seen_fingerprints:
                    seen_fingerprints.add(fingerprint)
                    
                    yaml_filename = f"comment_{fingerprint[:12]}.yml"
                    yaml_filepath = os.path.join(args.target_folder, yaml_filename)
                    
                    with open(yaml_filepath, 'w', encoding='utf-8') as yml_file:
                        yaml.safe_dump(comment_obj, yml_file, allow_unicode=True, sort_keys=False)
                        
                    post_comments_count += 1
                    total_extracted += 1

        if post_comments_count > 0:
            print(f"📝 Extracted {post_comments_count} unique comments for: {slug}")

    print("-" * 40)
    print(f"🎉 Success! Extracted a total of {total_extracted} unique comments.")
    print(f"📂 Saved in: {os.path.abspath(args.target_folder)}")

if __name__ == "__main__":
    main()