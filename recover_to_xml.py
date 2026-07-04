import os
import argparse
import sys
import re
import time
import random
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Standard Session Helper ---
def create_robust_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    return session

def extract_content(soup):
    selectors = ['.postDesc', '.post-text', '#post-text', '.posttext', '.post_text', '.post-content', '.Content', '.post-body', 'div[dir="rtl"]', 'body']
    for selector in selectors:
        element = soup.select_one(selector)
        # Verify content exists and isn't just an error page
        if element and len(element.get_text().strip()) > 50 and "خطا در استخراج محتوا" not in element.get_text():
            return str(element).strip()
    return None

def parse_missing_list(filepath):
    posts = []
    with open(filepath, 'r', encoding='utf-8') as f:
        pattern = r"عنوان \(Title\):\s*(.+?)\n\s*لینک \(Link\):\s*(https?://\S+)"
        for title, link in re.findall(pattern, f.read()):
            path_match = re.search(r'delsharm\.blogfa\.com/(.*)', link)
            path = f"/{path_match.group(1)}" if path_match else "/"
            posts.append({'title': title.strip(), 'path': path})
    return posts

def prettify_xml(elem):
    return minidom.parseString(ET.tostring(elem, 'utf-8')).toprettyxml(indent="    ")

def fast_deep_recover(missing_list, snapshot_file, output_xml, failure_log):
    posts_to_scrape = parse_missing_list(missing_list)
    with open(snapshot_file, 'r') as f:
        all_snapshots = [line.strip() for line in f.readlines()]
    
    session = create_robust_session()
    blog_root = ET.Element("BLOG")
    posts_container = ET.SubElement(ET.SubElement(blog_root, "BLOG_INFO"), "POSTS")
    failed_posts = []

    print(f"🚀 Found {len(posts_to_scrape)} posts. Starting fast-track recovery...")
    
    for post in posts_to_scrape:
        print(f"\n🔍 Searching for: {post['title']}")
        
        # Create a randomized sample of snapshots
        sample_size = min(10, len(all_snapshots))
        sampled_snapshots = random.sample(all_snapshots, sample_size)
        
        success = False
        for i, ts in enumerate(sampled_snapshots, 1):
            full_url = f"https://web.archive.org/web/{ts}/http://delsharm.blogfa.com{post['path']}"
            
            # PRINTING THE URL FOR MANUAL INVESTIGATION
            print(f"  -> Attempt {i}/10: {full_url}")
            
            try:
                time.sleep(random.uniform(2.0, 4.0))
                resp = session.get(full_url, timeout=15)
                
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                content = extract_content(soup)
                
                if content:
                    print(f"     ✅ Success found!")
                    post_node = ET.SubElement(posts_container, "POST")
                    ET.SubElement(post_node, "TITLE").text = post['title']
                    ET.SubElement(post_node, "CONTENT").text = content
                    ET.SubElement(post_node, "CREATED_DATE").text = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                    success = True
                    break
            except Exception as e:
                print(f"     -> ⚠️ Request error: {e}")
        
        if not success:
            print(f"     ❌ FAILED after 10 samples.")
            failed_posts.append(post)

    with open(output_xml, "w", encoding="utf-8") as f:
        f.write(prettify_xml(blog_root))
    
    with open(failure_log, "w", encoding="utf-8") as f:
        for p in failed_posts:
            f.write(f"عنوان (Title): {p['title']}\nلینک (Link): ...{p['path']}\n\n")
    
    print(f"\n🎉 Finished! Saved to: {output_xml}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", default="missing_posts_report.txt")
    parser.add_argument("-s", "--snapshots", default="snapshot_ids.txt")
    parser.add_argument("-o", "--output", default="recovered_deep_fast.xml")
    parser.add_argument("-f", "--failures", default="failed_deep_fast.txt")
    args = parser.parse_args()
    fast_deep_recover(args.input, args.snapshots, args.output, args.failures)