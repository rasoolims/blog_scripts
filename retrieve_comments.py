import os
import re
import time
import uuid
import argparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import jdatetime
import yaml
import xml.etree.ElementTree as ET

# Configure YAML to use nice multi-line strings (the | symbol) for messages
def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

def parse_persian_date(date_str):
    """Converts a Persian date string like '۲۸ ارديبهشت ۰۴ ، ۱۳:۵۹' to ISO 8601"""
    if not date_str:
        return None
        
    # Convert Persian digits to English
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

    # Extract day, month, year, hour, minute
    match = re.search(r'(\d+)\s+([آ-یa-zA-Z]+)\s+(\d+).*?(\d{1,2}):(\d{2})', date_str)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3))
        hour = int(match.group(4))
        minute = int(match.group(5))

        # Handle 2-digit years (04 -> 1404)
        if year < 100:
            year += 1400

        month = months.get(month_name, 1)

        try:
            j_date = jdatetime.datetime(year, month, day, hour, minute)
            # Return standard ISO format required by Astro's z.coerce.date()
            return j_date.togregorian().isoformat() + "Z"
        except Exception as e:
            print(f"    [!] Date conversion error for '{date_str}': {e}")
            
    # Fallback if regex fails but we still need a valid date for Astro
    return "2020-01-01T00:00:00.000Z"

def extract_comments_from_html(html_content, post_slug):
    soup = BeautifulSoup(html_content, 'html.parser')
    comments = []
    
    # Find all main comment blocks
    post_comments = soup.find_all('div', class_='post-comment')
    
    for pc in post_comments:
        author_elem = pc.find(class_='comment-name')
        date_elem = pc.find(class_='comment-date')
        body_elem = pc.find(class_='comment-body-content')

        author = author_elem.get_text(strip=True) if author_elem else "ناشناس"
        date_raw = date_elem.get_text(strip=True) if date_elem else ""
        date_iso = parse_persian_date(date_raw)
        
        # Extract text, converting <br> and <p> to actual newlines
        message = body_elem.get_text(separator='\n', strip=True) if body_elem else ""

        reply_data = None
        # In blog.ir, the admin reply is usually the next sibling div
        next_sibling = pc.find_next_sibling()
        if next_sibling and next_sibling.name == 'div' and 'comment-reply' in next_sibling.get('class', []):
            rep_date_elem = next_sibling.find(class_='comment-reply-date')
            rep_body_elem = next_sibling.find(class_='comment-reply-body')

            rep_date_raw = rep_date_elem.get_text(strip=True) if rep_date_elem else ""
            rep_date_iso = parse_persian_date(rep_date_raw)
            
            # Remove the "پاسخ: " prefix if it gets caught in the body
            rep_message = rep_body_elem.get_text(separator='\n', strip=True) if rep_body_elem else ""
            if rep_message.startswith("پاسخ:"):
                rep_message = rep_message.replace("پاسخ:", "", 1).strip()

            if rep_message:
                reply_data = {
                    'date': rep_date_iso or date_iso, # Fallback to comment date if parsing fails
                    'message': rep_message
                }

        comment_obj = {
            '_id': str(uuid.uuid4()),
            'postSlug': post_slug,
            'name': author,
            'date': date_iso,
            'message': message
        }
        
        if reply_data:
            comment_obj['adminResponse'] = reply_data
            
        comments.append(comment_obj)
        
    return comments

def main():
    parser = argparse.ArgumentParser(description="Scrape blog.ir comments from Wayback Machine using XML backup.")
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
    
    post_urls = set()
    try:
        tree = ET.parse(args.xml_file)
        root = tree.getroot()
        for post in root.findall('.//POST/LINK'):
            if post.text:
                # The '2' in the timestamp tells Wayback to fetch the most recent snapshot available
                wayback_url = f"https://web.archive.org/web/2/{post.text.strip()}"
                post_urls.add(wayback_url)
        print(f"✅ Found {len(post_urls)} post URLs in the XML file!")
    except Exception as e:
        print(f"❌ Failed to parse XML file: {e}")
        return

    print(f"\n--- Phase 2: Scraping Comments from {len(post_urls)} Posts ---")
    
    total_comments_saved = 0
    
    for i, post_url in enumerate(post_urls, 1):
        # The slug is the last part of the original URL
        slug = urlparse(post_url).path.strip('/').split('/')[-1]
        print(f"[{i}/{len(post_urls)}] Fetching '{slug}'...")
        
        try:
            response = session.get(post_url, headers=headers, timeout=20)
            
            # If Wayback returns a 404, it just means they never saved this specific post.
            if response.status_code != 200:
                print(f"  -> Not archived on Wayback Machine. Skipping.")
                continue
                
            comments = extract_comments_from_html(response.text, slug)
            
            if comments:
                print(f"  -> Found {len(comments)} comments. Saving...")
                for comment in comments:
                    file_name = f"comment_{int(time.time() * 1000)}_{str(uuid.uuid4())[:8]}.yml"
                    file_path = os.path.join(args.output_dir, file_name)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        yaml.safe_dump(comment, f, allow_unicode=True, sort_keys=False)
                        
                    total_comments_saved += 1
            else:
                print("  -> No comments found.")
                
        except Exception as e:
            print(f"  [!] Failed to fetch post: {e}")
            
        # Polite delay to prevent getting blocked by the Wayback Machine
        time.sleep(2)
        
    print(f"\n✅ Finished! Successfully recovered {total_comments_saved} comments.")
    print(f"Check your '{args.output_dir}' folder.")

if __name__ == "__main__":
    main()