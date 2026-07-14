import re
import sys
import requests
from bs4 import BeautifulSoup

def get_goodreads_cover(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_img = soup.find('meta', property='og:image')
            if meta_img and meta_img.get('content'):
                return meta_img['content']
    except Exception as e:
        pass
    return None

def main():
    # 1. Ensure a file path was provided
    if len(sys.argv) != 2:
        print("Usage: python fetch_covers.py <path_to_markdown_file>")
        print("Example: python fetch_covers.py src/content/blog/my-post.md")
        sys.exit(1)

    filepath = sys.argv[1]
    
    # 2. Try to open the file gracefully
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ Error: Could not find the file '{filepath}'.")
        sys.exit(1)

    # 3. Find all placeholder tiles
    pattern = re.compile(r'<a href="(https://www\.goodreads\.com/book/show/\d+)" class="book-tile"[^>]*><img src="[^"]+" alt="[^"]+" /></a>')
    
    def replacer(match):
        gr_url = match.group(1)
        print(f"Fetching cover for {gr_url.split('/')[-1]}...")
        cover_url = get_goodreads_cover(gr_url)
        
        if cover_url:
            return f'<a href="{gr_url}" class="book-tile" target="_blank"><img src="{cover_url}" alt="Book Cover" /></a>'
        else:
            print(f"  -> Failed to fetch cover, keeping placeholder.")
            return match.group(0) # Keep original if it fails

    print(f"🔍 Scanning '{filepath}' for Goodreads placeholders...")
    new_content = pattern.sub(replacer, content)

    # 4. Save the updated content back to the same file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"\n✅ Finished updating all cover images in '{filepath}'!")

if __name__ == "__main__":
    main()