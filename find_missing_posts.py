import xml.etree.ElementTree as ET
import os
import argparse
import sys
import re
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def normalize_persian_text(text):
    if not text:
        return ""
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    text = text.replace('\u200c', ' ').replace('_', ' ')
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()

def get_xml_titles(xml_file):
    print(f"📄 Reading local XML file: {xml_file}")
    if not os.path.isfile(xml_file):
        print(f"Error: The file '{xml_file}' does not exist.")
        sys.exit(1)

    xml_titles = set()
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        posts = root.findall('.//POST')
        for post in posts:
            title_elem = post.find('TITLE')
            if title_elem is not None and title_elem.text:
                raw_title = title_elem.text.strip()
                if raw_title.lower() != "unknown" and raw_title != "—" and raw_title != "":
                    norm_title = normalize_persian_text(raw_title)
                    xml_titles.add(norm_title)
                    
        print(f"✅ Found {len(xml_titles)} uniquely titled posts in your XML.")
        return xml_titles
    except Exception as e:
        print(f"Error reading XML: {e}")
        sys.exit(1)

def create_robust_session():
    session = requests.Session()
    retries = Retry(total=5, 
                    backoff_factor=1, 
                    status_forcelist=[ 429, 500, 502, 503, 504 ])
    
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    })
    return session

def find_missing_posts(xml_file, index_url, output_file):
    xml_titles_set = get_xml_titles(xml_file)
    session = create_robust_session()

    print(f"\n🌐 Fetching Main Archive Index from Wayback Machine...")
    print(f"URL: {index_url}")
    
    try:
        response = session.get(index_url, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to fetch the index URL after multiple retries: {e}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, 'html.parser')
    
    monthly_links = set()
    for link in soup.find_all('a'):
        href = link.get('href', '')
        if re.search(r'\b\d{4}\.aspx', href):
            full_url = urljoin(index_url, href)
            monthly_links.add(full_url)
            
    if not monthly_links:
        print("❌ Could not find any monthly archive links on the index page.")
        sys.exit(1)
        
    print(f"✅ Found {len(monthly_links)} monthly archive pages to scan.\n")
    
    wayback_posts = []
    
    for i, month_url in enumerate(sorted(monthly_links), 1):
        print(f"[{i}/{len(monthly_links)}] Scanning month: {month_url} ...")
        
        try:
            sleep_time = random.uniform(3.0, 6.0)
            time.sleep(sleep_time)
            
            resp = session.get(month_url, timeout=30)
            month_soup = BeautifulSoup(resp.text, 'html.parser')
            
            post_count_for_month = 0
            for link in month_soup.find_all('a'):
                href = link.get('href', '')
                raw_title = link.get_text().strip()
                
                if raw_title and re.search(r'post[-/]', href, re.IGNORECASE):
                    norm_title = normalize_persian_text(raw_title)
                    
                    if not any(p['norm_title'] == norm_title for p in wayback_posts):
                        post_url = urljoin(month_url, href)
                        wayback_posts.append({
                            'raw_title': raw_title,
                            'norm_title': norm_title,
                            'url': post_url
                        })
                        post_count_for_month += 1
                        
            print(f"  -> Extracted {post_count_for_month} posts.")
            
        except Exception as e:
            print(f"  -> ⚠️ Failed to load this month after all retries: {e}")

    print(f"\n✅ Finished scanning! Extracted {len(wayback_posts)} total posts from the Web Archive.")
    
    missing_posts = []
    for post in wayback_posts:
        if post['norm_title'] not in xml_titles_set:
            missing_posts.append(post)

    # OUTPUT LOGIC (Terminal)
    print("\n" + "="*60)
    print(" 📊 AUDIT RESULTS (MISSING POSTS)")
    print("="*60)
    
    if not missing_posts:
        print("🎉 Great news! All posts found in the web archive exist in your XML file.")
    else:
        print(f"🚨 FOUND {len(missing_posts)} MISSING POSTS!")
        print(f"Previewing the first 5 missing posts in terminal...\n")
        
        for i, post in enumerate(missing_posts[:5], 1):
            print(f"{i}. عنوان (Title): {post['raw_title']}")
            print(f"   لینک (Link): {post['url']}")
            print("-" * 50)
            
        if len(missing_posts) > 5:
            print(f"... and {len(missing_posts) - 5} more.")
            
    # FILE WRITING LOGIC
    if output_file:
        try:
            # Ensure the directory exists if the user specified a subfolder path
            out_dir = os.path.dirname(output_file)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write("="*60 + "\n")
                f.write(" 📊 AUDIT RESULTS (MISSING POSTS)\n")
                f.write("="*60 + "\n\n")
                
                if not missing_posts:
                    f.write("🎉 Great news! All posts found in the web archive exist in your XML file.\n")
                else:
                    f.write(f"🚨 FOUND {len(missing_posts)} MISSING POSTS!\n\n")
                    for i, post in enumerate(missing_posts, 1):
                        f.write(f"{i}. عنوان (Title): {post['raw_title']}\n")
                        f.write(f"   لینک (Link): {post['url']}\n")
                        f.write("-" * 50 + "\n")
                        
            print(f"\n📂 Full missing posts report successfully saved to: {os.path.abspath(output_file)}")
        except Exception as e:
            print(f"\n❌ Error writing to file '{output_file}': {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Audit a Blogfa Wayback archive by checking all monthly links against your local Blog.ir XML backup.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("xml_file", help="Path to your XML backup file (e.g., delsharm.xml)")
    
    default_url = "https://web.archive.org/web/20151215043004/http://delsharm.blogfa.com/archive.aspx"
    parser.add_argument(
        "-u", "--url", 
        default=default_url, 
        help="The Wayback Machine archive index URL to scrape"
    )
    
    # NEW ARGUMENT FOR FILE EXPORT
    parser.add_argument(
        "-o", "--output", 
        default="missing_posts_report.txt",
        help="Path to save the missing posts report (e.g., missing.txt)"
    )
    
    args = parser.parse_args()
    find_missing_posts(args.xml_file, args.url, args.output)