import requests
import time
import random
import re
import argparse
import os
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom

def prettify_xml(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return '\n'.join([line for line in reparsed.toprettyxml(indent="    ").split('\n') if line.strip()])

def get_all_snapshots(url):
    """Fetches a list of all successful snapshots for a URL."""
    cdx_url = f"http://web.archive.org/cdx/search/cdx?url={url}&output=json&filter=statuscode:200"
    try:
        response = requests.get(cdx_url, timeout=15).json()
        if len(response) > 1:
            # item[1] is the 14-digit timestamp
            return [[item[1], f"https://web.archive.org/web/{item[1]}/{item[2]}"] for item in response[1:]]
    except Exception as e:
        print(f"    -> CDX API Error: {e}")
    return []

def extract_content_smart(url):
    """Fetches snapshot and verifies if content is valid."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        error_indicators = ["خطا در استخراج محتوا", "Error", "404", "Not Found", "مطلب یافت نشد", "Server Error"]
        
        selectors = ['.postDesc', '.post-text', '.post', 'div[dir="rtl"]', '#main', 'article']
        for sel in selectors:
            content = soup.select_one(sel)
            if content:
                text_content = content.get_text()
                if not any(err in text_content for err in error_indicators):
                    return str(content)
        return None
    except:
        return None

def run_recovery(list_file, output_xml):
    if not os.path.exists(list_file):
        print(f"❌ Error: Could not find '{list_file}'.")
        return

    with open(list_file, 'r', encoding='utf-8') as f:
        pattern = r"عنوان \(Title\):\s*(.+?)\n\s*لینک \(Link\):\s*(https?://\S+)"
        matches = re.findall(pattern, f.read())

    blog_root = ET.Element("BLOG")
    posts_container = ET.SubElement(ET.SubElement(blog_root, "BLOG_INFO"), "POSTS")
    
    print(f"🚀 Found {len(matches)} posts. Beginning time-hop recovery...")
    
    for title, url in matches:
        print(f"\nSearching for: {title}")
        snapshots = get_all_snapshots(url)
        
        recovered = False
        # Sort newest first
        for ts, snap_url in sorted(snapshots, reverse=True):
            # PRINTING THE TIMESTAMP WE ARE EFFORTING
            print(f"  -> Efforting timestamp: {ts}") 
            
            content = extract_content_smart(snap_url)
            
            if content:
                print(f"     ✅ Success! Recovered from {ts}")
                post_node = ET.SubElement(posts_container, "POST")
                ET.SubElement(post_node, "TITLE").text = title
                ET.SubElement(post_node, "CONTENT").text = content
                ET.SubElement(post_node, "CREATED_DATE").text = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                recovered = True
                break 
            
            # Anti-refusal sleep
            time.sleep(random.uniform(5, 10)) 
            
        if not recovered:
            print(f"     ❌ Could not find valid content for this title.")

    with open(output_xml, "w", encoding="utf-8") as f:
        f.write(prettify_xml(blog_root))
    print(f"\n🎉 Process finished. Saved to: {output_xml}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run_recovery(args.list, args.output)