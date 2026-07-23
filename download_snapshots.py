import os
import time
import argparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, unquote
import xml.etree.ElementTree as ET

def get_snapshot_timestamps(original_url, session):
    """Fetches all valid snapshot timestamps from the CDX API."""
    # Try both the encoded and decoded URL to bypass CDX Persian text bugs
    urls_to_try = [original_url, unquote(original_url)]
    
    for url in urls_to_try:
        cdx_url = f"http://web.archive.org/cdx/search/cdx?url={url}&output=json&fl=timestamp,statuscode&filter=statuscode:200&collapse=timestamp:6"
        try:
            response = session.get(cdx_url, timeout=15)
            if response.status_code == 200 and response.text.strip():
                data = response.json()
                if len(data) > 1: # Row 0 is the header
                    return [row[0] for row in data[1:]]
        except Exception as e:
            pass
            
    return []

def main():
    parser = argparse.ArgumentParser(description="Download all Wayback Machine snapshots for blog posts.")
    parser.add_argument("xml_file", help="Path to your blog.ir XML backup file.")
    parser.add_argument("output_dir", help="Main folder to save the HTML snapshots.")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    
    # Setup resilient HTTP session
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))

    print("\n--- Phase 1: Parsing XML ---")
    try:
        root = ET.parse(args.xml_file).getroot()
        urls = [post.text.strip() for post in root.findall('.//POST/LINK') if post.text]
        
        # Priority check for the "Ali" post to ensure we tackle it first
        ali_url = "http://delsharm.blog.ir/1395/09/28/%D8%B9%D9%84%DB%8C"
        if ali_url in urls:
            urls.remove(ali_url)
            urls.insert(0, ali_url)
            print("⭐ Priority post 'علی' moved to the front of the queue.")
            
        print(f"✅ Found {len(urls)} original post URLs to process.")
    except Exception as e:
        print(f"❌ Failed to parse XML: {e}")
        return

    print("\n--- Phase 2: Downloading Snapshots ---")
    
    total_downloaded = 0
    total_skipped = 0

    for i, orig_url in enumerate(urls, 1):
        slug = unquote(urlparse(orig_url).path.strip('/').split('/')[-1])
        if not slug: 
            slug = "home"
            
        post_dir = os.path.join(args.output_dir, slug)
        os.makedirs(post_dir, exist_ok=True)
        
        print(f"\n[{i}/{len(urls)}] 🔍 Checking timeline for '{slug}'...")
        
        timestamps = get_snapshot_timestamps(orig_url, session)
        
        if not timestamps:
            print("  -> No snapshots found in CDX API. Attempting brute-force latest fetch...")
            timestamps = ["2"] # '2' is the Wayback shortcut for "latest available"
        else:
            print(f"  -> Found {len(timestamps)} snapshots in history.")
            
        for ts in timestamps:
            # We save the file using the timestamp as the name
            filename = f"{ts}.html" if ts != "2" else "latest_fallback.html"
            filepath = os.path.join(post_dir, filename)
            
            # RESUME FEATURE: Skip if we already downloaded this exact snapshot
            if os.path.exists(filepath):
                print(f"  -> ⏭️  Skipping {filename} (Already downloaded)")
                total_skipped += 1
                continue
                
            # Note the 'id_' after the timestamp. This requests RAW HTML without Wayback toolbars.
            if ts == "2":
                wayback_url = f"https://web.archive.org/web/2/{orig_url}"
            else:
                wayback_url = f"https://web.archive.org/web/{ts}id_/{orig_url}"
                
            print(f"  -> ⬇️  Downloading snapshot {ts}...")
            
            try:
                # 15 second strict timeout prevents the script from hanging on bad servers
                response = session.get(wayback_url, headers=headers, timeout=15, allow_redirects=True)
                
                if response.status_code == 200:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    total_downloaded += 1
                else:
                    print(f"    [!] Server returned status {response.status_code}")
                    
            except requests.exceptions.Timeout:
                print(f"    [!] Timeout error: Wayback Machine took too long to respond.")
            except Exception as e:
                print(f"    [!] Fetch failed: {e}")
                
            # Be polite to the Wayback Machine to avoid IP bans
            time.sleep(1.5)

    print(f"\n✅ All operations finished!")
    print(f"📊 Downloaded: {total_downloaded} new files")
    print(f"📊 Skipped: {total_skipped} existing files")
    print(f"📂 Snapshots are saved in: {os.path.abspath(args.output_dir)}")

if __name__ == "__main__":
    main()