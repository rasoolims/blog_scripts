import xml.etree.ElementTree as ET
import os
import argparse
import re
from xml.dom import minidom

def prettify_xml(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return '\n'.join([line for line in reparsed.toprettyxml(indent="    ").split('\n') if line.strip()])

def is_content_valid(content_text):
    """Checks if the content contains our known error message."""
    error_msg = "خطا در استخراج محتوا"
    if not content_text: return False
    return error_msg not in content_text

def merge_xml_files(input_files, output_xml):
    # Dictionary to keep the best version of each post: { "title": post_element }
    best_posts = {}
    
    print(f"🚀 Merging {len(input_files)} XML files...")

    for file_path in input_files:
        if not os.path.exists(file_path):
            print(f"⚠️ Skipping missing file: {file_path}")
            continue
            
        print(f"📄 Processing: {file_path}")
        tree = ET.parse(file_path)
        for post in tree.findall('.//POST'):
            title = post.find('TITLE').text.strip()
            content = post.find('CONTENT').text or ""
            
            # If we haven't seen this title, add it
            if title not in best_posts:
                best_posts[title] = post
                print(f"  -> Added: {title}")
            else:
                # If we have seen it, check if current is "cleaner" than what we have
                current_best = best_posts[title]
                current_best_content = current_best.find('CONTENT').text or ""
                
                if not is_content_valid(current_best_content) and is_content_valid(content):
                    best_posts[title] = post
                    print(f"  -> ✨ Updated with valid content: {title}")
                else:
                    print(f"  -> ⏭️ Kept existing/better version: {title}")

    # Build the final XML
    blog_root = ET.Element("BLOG")
    posts_container = ET.SubElement(ET.SubElement(blog_root, "BLOG_INFO"), "POSTS")
    
    for post in best_posts.values():
        posts_container.append(post)

    with open(output_xml, "w", encoding="utf-8") as f:
        f.write(prettify_xml(blog_root))
    print(f"\n🎉 Success! Combined valid content saved to: {output_xml}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge multiple XMLs, keeping only the clean versions.")
    parser.add_argument("--inputs", nargs='+', required=True, help="List of XML files to merge")
    parser.add_argument("--output", required=True, help="Path for the final merged XML")
    
    args = parser.parse_args()
    merge_xml_files(args.inputs, args.output)