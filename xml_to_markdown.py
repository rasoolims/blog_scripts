import xml.etree.ElementTree as ET
import os
import argparse
import sys
import re
import datetime

try:
    import jdatetime
except ImportError:
    print("Error: The 'jdatetime' library is not installed.")
    print("Please install it by running: pip install jdatetime")
    sys.exit(1)

def to_persian_num(num_str):
    return str(num_str).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

def convert_to_jalali(gregorian_date_str):
    try:
        jdatetime.set_locale('fa_IR')
        raw_str = gregorian_date_str.strip()
        if len(raw_str) > 10 and ":" in raw_str:
            dt = datetime.datetime.strptime(raw_str[:19], "%Y-%m-%d %H:%M:%S")
            jalali_dt = jdatetime.datetime.fromgregorian(datetime=dt)
            formatted_date = jalali_dt.strftime("%d %B %Y")
            return to_persian_num(formatted_date)
        else:
            date_part = raw_str[:10]
            year, month, day = map(int, date_part.split('-'))
            jalali_date = jdatetime.date.fromgregorian(day=day, month=month, year=year)
            return to_persian_num(jalali_date.strftime("%d %B %Y"))
    except Exception:
        return gregorian_date_str

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def strip_hardcoded_styles(html_content):
    if not html_content:
        return ""
    cleaned = re.sub(r'\b(?:color|bgcolor|face|size)\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?<!-)\bcolor\s*:\s*[^;"\']+[;]?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bbackground-color\s*:\s*[^;"\']+[;]?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bfont-family\s*:\s*[^;"\']+[;]?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bfont-size\s*:\s*[^;"\']+[;]?', '', cleaned, flags=re.IGNORECASE)
    return cleaned

def convert_xml_to_markdown(xml_file, output_posts_dir):
    if not os.path.exists(output_posts_dir):
        os.makedirs(output_posts_dir)

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Error reading XML: {e}")
        sys.exit(1)

    posts = root.findall('.//POST')
    print(f"Found {len(posts)} posts to convert...")

    for i, post in enumerate(posts):
        title_elem = post.find('TITLE')
        title_raw = title_elem.text.strip() if (title_elem is not None and title_elem.text) else ""
        title = "—" if not title_raw or title_raw.lower() == "unknown" else title_raw
        
        # Format strings to prevent markdown YAML frontmatter breaking
        title = title.replace('"', '\\"')

        content_elem = post.find('CONTENT')
        raw_content = content_elem.text if (content_elem is not None and content_elem.text) else "بدون محتوا"
        content = strip_hardcoded_styles(raw_content)

        date_elem = post.find('CREATED_DATE')
        raw_date = date_elem.text.strip() if (date_elem is not None and date_elem.text) else "1970-01-01"
        
        # Split full timestamp down to standard YYYY-MM-DD for standard frontmatter formatting
        iso_date = raw_date[:10] 
        jalali_date = convert_to_jalali(raw_date)

        url_elem = post.find('URL')
        url_slug = url_elem.text.strip() if (url_elem is not None and url_elem.text) else f"post_{i+1}"
        filename = f"{sanitize_filename(url_slug)}.md"

        # Safely extract and array-format tags for frontmatter
        tags_elem = post.find('TAGS')
        unique_post_tags = set()
        if tags_elem is not None:
            unique_post_tags = set(t.text.strip() for t in tags_elem.findall('.//NAME') if t.text and t.text.strip())
        if title == "—":
            unique_post_tags.add("سیاه‌مشق")
        
        # Turn into a valid YAML list string formatted for modern SSGs
        tags_yaml = ", ".join([f'"{t}"' for t in unique_post_tags])

        # Write out file with clean frontmatter metadata blocks
        md_content = f"""---
title: "{title}"
date: {iso_date}
jalaliDate: "{jalali_date}"
tags: [{tags_yaml}]
---
{content}
"""
        with open(os.path.join(output_posts_dir, filename), "w", encoding="utf-8") as f:
            f.write(md_content)

    print(f"🎉 Successfully converted posts into Markdown in: {output_posts_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert XML backup into standard Markdown files with clean frontmatter attributes.")
    parser.add_argument("xml_file", help="Path to your backup XML file")
    parser.add_argument("-o", "--output", default="posts_markdown", help="Target folder to save markdown files")
    args = parser.parse_args()
    
    convert_xml_to_markdown(args.xml_file, args.output)