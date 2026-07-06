import os
import argparse
import requests
import re
import time
import random
import html
import jdatetime
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from xml.dom import minidom
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_robust_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    return session

def extract_date_from_text(content_text):
    # 1. Unescape HTML entities like &nbsp;
    text = html.unescape(content_text)
    
    # 2. Normalize spaces and remove zero-width characters
    text = re.sub(r'[\u200c\u200b\s]+', ' ', text)
    
    # 3. Separate Persian letters from numbers intelligently (e.g., "دی1387ساعت" -> "دی 1387 ساعت")
    text = re.sub(r'(?<=[آ-یa-zA-Z])(?=\d)', ' ', text)
    text = re.sub(r'(?<=\d)(?=[آ-یa-zA-Z])', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    months = {'فروردین': 1, 'اردیبهشت': 2, 'خرداد': 3, 'تیر': 4, 'مرداد': 5, 'شهریور': 6,
              'مهر': 7, 'آبان': 8, 'آذر': 9, 'دی': 10, 'بهمن': 11, 'اسفند': 12}
    
    # Match Date: Day + Month Name + Year
    date_match = re.search(r'(\d{1,2})\s+([آ-ی]+)\s+(\d{4})', text)
    
    # Match Time: Hour:Minute
    time_match = re.search(r'(\d{1,2}):(\d{2})', text)
    
    if date_match:
        try:
            day = int(date_match.group(1))
            month_name = date_match.group(2)
            year = int(date_match.group(3))
            month = months.get(month_name, 1)
            
            # Default time variables
            hour, minute = 0, 0
            
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                
                # Adjust for AM/PM based on surrounding context
                if any(pm in text for pm in ['بعد از ظهر', 'بعدازظهر', 'عصر', 'شب', 'ب.ظ']):
                    if hour < 12: 
                        hour += 12
                elif any(am in text for am in ['صبح', 'ق.ظ', 'بامداد']):
                    if hour == 12: 
                        hour = 0
            
            # Convert Jalali datetime to Gregorian using jdatetime
            gregorian_dt = jdatetime.datetime(year, month, day, hour, minute).togregorian()
            
            # Format strictly to standard ISO
            iso_date = gregorian_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Create a clean log string for the terminal
            log_str = f"{date_match.group(0)}" + (f" {time_match.group(0)}" if time_match else "")
            
            return log_str, iso_date
            
        except Exception: 
            pass
            
    return "Not Found", "1970-01-01 00:00:00"

def run_recovery(failed_list_path, index_url, output_xml):
    session = create_robust_session()
    
    failed_posts = {}
    with open(failed_list_path, 'r', encoding='utf-8') as f:
        pattern = r"عنوان \(Title\):\s*(.+?)\n\s*لینک \(Link\):\s*.*?/(post-\d+\.aspx|[\d]+\.aspx)"
        for title, post_id in re.findall(pattern, f.read()):
            failed_posts[post_id] = {'title': title, 'found': False}
    
    total_missing = len(failed_posts)
    successful_count = 0
    print(f"🚀 Starting recovery. Total: {total_missing}")
    
    blog_root = ET.Element("BLOG")
    posts_container = ET.SubElement(ET.SubElement(blog_root, "BLOG_INFO"), "POSTS")
    
    def process_node(post_id, title, post_body_div):
        nonlocal successful_count
        post_desc_div = post_body_div.find_next_sibling('div', class_='postdesc')
        date_raw = post_desc_div.get_text() if post_desc_div else ""
        persian_date_str, iso_date = extract_date_from_text(date_raw)
        
        print(f"     🎯 Success [ID: {post_id}] | Date: {persian_date_str} -> {iso_date}")
        
        post = ET.SubElement(posts_container, "POST")
        ET.SubElement(post, "TITLE").text = title
        ET.SubElement(post, "CONTENT").text = str(post_body_div).strip()
        ET.SubElement(post, "CREATED_DATE").text = iso_date
        
        successful_count += 1
        print(f"     📊 Progress: {successful_count}/{total_missing}")

    # 1. DIRECT ATTEMPT
    print("\n--- Phase 1: Direct ---")
    for post_id, data in failed_posts.items():
        if data['found']: continue
        try:
            time.sleep(2)
            url = f"https://web.archive.org/web/20120701000000*/http://delsharm.blogfa.com/{post_id}"
            resp = session.get(url, timeout=20)
            soup = BeautifulSoup(resp.text, 'html.parser')
            body = soup.find('div', class_='postbody')
            if body:
                process_node(post_id, data['title'], body)
                data['found'] = True
        except: pass

    # 2. SLICER PHASE
    print("\n--- Phase 2: Index Slicing ---")
    resp = session.get(index_url, timeout=30)
    monthly_pages = [f"https://web.archive.org{a['href']}" for a in BeautifulSoup(resp.text, 'html.parser').find_all('a', href=True) if re.search(r'\d{4}\.aspx', a['href'])]
    
    for page in monthly_pages:
        if successful_count == total_missing: break
        try:
            time.sleep(random.uniform(5, 10))
            soup = BeautifulSoup(session.get(page, timeout=30).text, 'html.parser')
            for post_id, data in failed_posts.items():
                if data['found']: continue
                link = soup.find('a', href=re.compile(post_id))
                if link:
                    body = link.find_parent().find_next_sibling('div', class_='postbody')
                    if body:
                        process_node(post_id, data['title'], body)
                        data['found'] = True
        except: pass
            
    with open(output_xml, "w", encoding="utf-8") as f:
        f.write(minidom.parseString(ET.tostring(blog_root, 'utf-8')).toprettyxml(indent="    "))
    
    print(f"\n🎉 Done. Missing: {total_missing - successful_count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="https://web.archive.org/web/20120723095727/http://delsharm.blogfa.com/archive.aspx")
    parser.add_argument("--failed", default="failed_deep_fast.txt")
    parser.add_argument("-o", "--output", default="recovered_final.xml")
    args = parser.parse_args()
    run_recovery(args.failed, args.index, args.output)