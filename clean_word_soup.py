import os
import re
import sys
from bs4 import BeautifulSoup, Comment

def clean_ms_word_junk(content):
    match = re.match(r'^(---\s*\n.*?\n---\s*\n)(.*)', content, flags=re.MULTILINE | re.DOTALL)
    if match:
        frontmatter = match.group(1)
        body = match.group(2)
    else:
        frontmatter = ""
        body = content

    soup = BeautifulSoup(body, 'html.parser')
    
    for tag in soup(['meta', 'link', 'style', 'script']):
        tag.decompose()
        
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
        
    for tag in soup.find_all(['span', 'font', 'div', 'center']):
        tag.unwrap()
        
    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.get_text(strip=True)
        if text: a.replace_with(f"[{text}]({href})")
        
    for b in soup.find_all(['b', 'strong']):
        text = b.get_text(strip=True)
        if text: b.replace_with(f"**{text}**")
        
    for i in soup.find_all(['i', 'em']):
        text = i.get_text(strip=True)
        if text: i.replace_with(f"*{text}*")

    # --- THE FIX IS HERE ---
    # We modify the P tag natively instead of replacing it with a string
    for p in list(soup.find_all('p')):
        is_centered = False
        if p.get('align', '').lower() == 'center':
            is_centered = True
        if p.get('style') and 'text-align: center' in p.get('style').lower():
            is_centered = True
            
        text = p.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        
        if not text:
            p.decompose()
            continue
            
        if is_centered:
            # 1. Wipe out all the messy MS Word attributes
            p.attrs = {} 
            # 2. Assign only the clean inline style
            p['style'] = 'text-align: center;'
            # 3. Set the clean text
            p.string = text
            # 4. Ensure there are line breaks after it for Markdown spacing
            p.insert_after("\n\n")
        else:
            p.replace_with(text + "\n\n")
            
    for br in soup.find_all('br'):
        br.replace_with('\n')

    clean_body = str(soup)
    
    clean_body = re.sub(r'<!\[endif\]-->', '', clean_body, flags=re.IGNORECASE)
    clean_body = re.sub(r'&lt;!\[endif\].*?&gt;', '', clean_body, flags=re.IGNORECASE)
    
    clean_body = re.sub(r'\n{3,}', '\n\n', clean_body).strip()
    
    return frontmatter + clean_body

def main():
    if len(sys.argv) != 2:
        print("Usage: python clean_word_soup.py <folder_path>")
        sys.exit(1)

    folder_path = sys.argv[1]
    processed_count = 0

    print(f"🔍 Scanning '{folder_path}' for MS Word infected files...\n" + "-"*40)

    for filename in os.listdir(folder_path):
        if not filename.endswith(('.md', '.mdx')):
            continue

        filepath = os.path.join(folder_path, filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        if 'msohtmlclip' not in content and 'Word.Document' not in content and 'gte mso' not in content:
            continue 

        print(f"🩹 Fixing and safely re-centering: {filename}")
        cleaned_content = clean_ms_word_junk(content)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(cleaned_content)
            
        processed_count += 1

    print("-" * 40)
    print(f"🎉 Success! Cleaned and re-centered {processed_count} files.")

if __name__ == "__main__":
    main()