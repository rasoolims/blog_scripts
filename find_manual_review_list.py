import xml.etree.ElementTree as ET
import os
import argparse
import re

def parse_missing_list(filepath):
    """Reads the original missing report to map Titles to URLs."""
    mapping = {}
    if not os.path.exists(filepath):
        print(f"❌ Error: Missing report file '{filepath}' not found.")
        return mapping
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract Title and URL pairs
    pattern = r"عنوان \(Title\):\s*(.+?)\n\s*لینک \(Link\):\s*(https?://\S+)"
    matches = re.findall(pattern, content)
    for title, link in matches:
        mapping[title.strip()] = link.strip()
    return mapping

def find_manual_reviews(xml_path, missing_list_path):
    # 1. Load the map of titles to URLs
    url_map = parse_missing_list(missing_list_path)
    
    # 2. Parse the Master XML
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"❌ Error parsing XML: {e}")
        return

    print(f"\n🔍 Scanning for posts requiring manual review...")
    print("="*60)
    
    found_count = 0
    error_msg = "خطا در استخراج محتوا. لطفاً به صورت دستی بررسی کنید."
    
    for post in root.findall('.//POST'):
        content_elem = post.find('CONTENT')
        title_elem = post.find('TITLE')
        
        if content_elem is not None and error_msg in content_elem.text:
            title = title_elem.text.strip() if title_elem is not None else "Unknown Title"
            found_count += 1
            
            # Print the title
            print(f"\n{found_count}. عنوان: {title}")
            
            # Match the URL from our mapping
            url = url_map.get(title, "لینک در فایل گزارش پیدا نشد.")
            print(f"   لینک آرشیو: {url}")
            
    if found_count == 0:
        print("🎉 No posts found requiring manual review!")
    else:
        print(f"\n{'='*60}")
        print(f"✅ Found {found_count} posts. Please review them at the links above.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find posts in your XML that failed extraction.")
    parser.add_argument("--xml", required=True, help="Path to your master XML file")
    parser.add_argument("--list", required=True, help="Path to your missing_posts_report.txt file")
    
    args = parser.parse_args()
    find_manual_reviews(args.xml, args.list)