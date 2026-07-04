import xml.etree.ElementTree as ET
import os
import argparse
import sys
import re
from xml.dom import minidom

def to_persian_num(num_str):
    """Converts English digits in a string to Persian digits."""
    return str(num_str).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

def prettify_xml(elem):
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    # Removing extra blank lines added by minidom
    pretty_string = '\n'.join([line for line in reparsed.toprettyxml(indent="    ").split('\n') if line.strip()])
    return pretty_string

def get_posts_from_xml(xml_path):
    """Parses an XML file and extracts all POST elements."""
    if not os.path.isfile(xml_path):
        print(f"❌ Error: The file '{xml_path}' does not exist.")
        sys.exit(1)
        
    print(f"📄 Parsing {xml_path}...")
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        posts = root.findall('.//POST')
        
        # Try to extract the blog title to reuse it
        blog_title_elem = root.find('.//BLOG_INFO/TITLE')
        blog_title = blog_title_elem.text.strip() if (blog_title_elem is not None and blog_title_elem.text) else None
        
        print(f"  -> Found {len(posts)} posts.")
        return posts, blog_title
    except Exception as e:
        print(f"❌ Error reading {xml_path}: {e}")
        sys.exit(1)

def merge_and_process_xmls(original_xml, recovered_xml, output_xml):
    # 1. Extract posts from both files
    posts1, title1 = get_posts_from_xml(original_xml)
    posts2, title2 = get_posts_from_xml(recovered_xml)
    
    all_posts = posts1 + posts2
    print(f"\n✅ Total posts combined: {len(all_posts)}")
    
    # Choose a blog title
    final_blog_title = title1 or title2 or "آرشیو یکپارچه وبلاگ"

    tag_added_count = 0

    # 2. Process titles, add "سیاه‌مشق" tag, and convert digits to Persian
    for post in all_posts:
        title_elem = post.find('TITLE')
        if title_elem is not None and title_elem.text:
            raw_title = title_elem.text.strip()
            
            # --- CONVERT ENGLISH DIGITS TO PERSIAN IN TITLE ---
            title_elem.text = to_persian_num(raw_title)
            
            # Normalize zero-width non-joiners to standard spaces for the check
            normalized_title = raw_title.replace('\u200c', ' ')
            
            if "سیاه مشق" in normalized_title:
                tags_node = post.find('TAGS')
                
                # Create TAGS node if it doesn't exist
                if tags_node is None:
                    tags_node = ET.SubElement(post, 'TAGS')
                
                # Check if the exact tag already exists to prevent duplicates
                has_target_tag = False
                for tag_name in tags_node.findall('.//NAME'):
                    if tag_name.text and tag_name.text.replace('\u200c', ' ') == "سیاه مشق":
                        has_target_tag = True
                        break
                        
                # Add the tag if it's missing
                if not has_target_tag:
                    new_tag = ET.SubElement(tags_node, 'TAG')
                    new_name = ET.SubElement(new_tag, 'NAME')
                    new_name.text = "سیاه‌مشق"
                    tag_added_count += 1

    print(f"✏️ Added 'سیاه‌مشق' tag to {tag_added_count} matching posts.")
    print(f"🔢 Converted English digits to Persian in all titles.")

    # 3. Sort chronologically (Newest to Oldest)
    all_posts.sort(
        key=lambda p: p.find('CREATED_DATE').text.strip() if (p.find('CREATED_DATE') is not None and p.find('CREATED_DATE').text) else "1970-01-01 00:00:00",
        reverse=True
    )
    print("⏳ Posts successfully sorted by chronological order.")

    # 4. Construct the new XML tree
    print("\n📦 Building the final XML structure...")
    blog_root = ET.Element("BLOG")
    
    blog_info = ET.SubElement(blog_root, "BLOG_INFO")
    title_node = ET.SubElement(blog_info, "TITLE")
    title_node.text = final_blog_title
    
    posts_container = ET.SubElement(blog_root, "POSTS")
    for post in all_posts:
        posts_container.append(post)

    # 5. Write to output file
    try:
        out_dir = os.path.dirname(output_xml)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)
            
        pretty_xml = prettify_xml(blog_root)
        
        with open(output_xml, "w", encoding="utf-8") as f:
            f.write(pretty_xml)
            
        print(f"🎉 Success! Unified XML saved to: {os.path.abspath(output_xml)}")
        
    except Exception as e:
        print(f"❌ Error writing XML file: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge two Blog.ir XML backups, sort them chronologically, and auto-tag specific posts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument("-orig", "--original", required=True, help="Path to original XML")
    parser.add_argument("-rec", "--recovered", required=True, help="Path to recovered XML")
    parser.add_argument("-o", "--output", default="master_delsharm.xml", help="Path to save output")
    
    args = parser.parse_args()
    merge_and_process_xmls(args.original, args.recovered, args.output)