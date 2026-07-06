import xml.etree.ElementTree as ET
import os
import argparse
import sys
import re
import json
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
            formatted_time = jalali_dt.strftime("%H:%M")
            return to_persian_num(formatted_date), to_persian_num(formatted_time)
        else:
            date_part = raw_str[:10]
            year, month, day = map(int, date_part.split('-'))
            jalali_date = jdatetime.date.fromgregorian(day=day, month=month, year=year)
            return to_persian_num(jalali_date.strftime("%d %B %Y")), ""
    except Exception:
        return gregorian_date_str, "" 

def get_baygani_info(gregorian_date_str):
    try:
        jdatetime.set_locale('fa_IR')
        date_part = gregorian_date_str.strip()[:10]
        year, month, day = map(int, date_part.split('-'))
        
        jalali_date = jdatetime.date.fromgregorian(day=day, month=month, year=year)
        sort_key = f"{jalali_date.year}-{jalali_date.month:02d}"
        label = jalali_date.strftime("%B %Y")
        
        return sort_key, to_persian_num(label)
    except Exception:
        return "0000-00", "نامشخص"

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def strip_hardcoded_styles(html_content):
    if not html_content:
        return ""
    # Strip old HTML attributes (color, bgcolor, face, size)
    cleaned = re.sub(r'\b(?:color|bgcolor|face|size)\s*=\s*["\'][^"\']*["\']', '', html_content, flags=re.IGNORECASE)
    # Strip specific inline CSS properties
    cleaned = re.sub(r'(?<!-)\bcolor\s*:\s*[^;"\']+[;]?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bbackground-color\s*:\s*[^;"\']+[;]?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bfont-family\s*:\s*[^;"\']+[;]?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bfont-size\s*:\s*[^;"\']+[;]?', '', cleaned, flags=re.IGNORECASE)
    return cleaned

def extract_preview(html_content):
    img_match = re.search(r'<img[^>]+src=["\'](.*?)["\']', html_content, re.IGNORECASE)
    img_url = img_match.group(1) if img_match else None
    
    no_img_html = re.sub(r'<img[^>]+>', '', html_content, flags=re.IGNORECASE)
    p_blocks = re.findall(r'<p[^>]*>.*?</p>', no_img_html, flags=re.IGNORECASE | re.DOTALL)
    
    target_length = 350 if img_url else 600
    excerpt_html = ""
    
    if p_blocks:
        current_length = 0
        selected_blocks = []
        for p in p_blocks:
            clean_text = re.sub(r'<[^>]+>', '', p).strip()
            if not clean_text and '<br' not in p.lower():
                continue
                
            selected_blocks.append(p)
            current_length += len(clean_text)
            if current_length >= target_length: 
                break
        excerpt_html = "".join(selected_blocks)
        
    if not excerpt_html.strip():
        text_with_markers = re.sub(r'<br\s*/?>|</div>|</p>', '\n', no_img_html, flags=re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', text_with_markers)
        lines = [line.strip() for line in clean_text.split('\n')]
        
        excerpt_lines = []
        current_length = 0
        for line in lines:
            if not line and (not excerpt_lines or not excerpt_lines[-1]):
                continue
                
            excerpt_lines.append(line)
            current_length += len(line)
            if current_length >= target_length:
                break
                
        excerpt_html = "<p>" + "<br>".join(excerpt_lines) + "</p>"
        
    if not excerpt_html.strip() or excerpt_html == "<p></p>":
        excerpt_html = "<p>بدون محتوا</p>"
        
    return img_url, excerpt_html

def render_comments(post_elem):
    comments_elem = post_elem.find('COMMENTS')
    if comments_elem is None: 
        return ""
        
    html = '<div class="comments-section"><h3>نظرات</h3>'
    comments = comments_elem.findall('COMMENT')
    
    if not comments:
        return ""
        
    for c in comments:
        author = c.findtext('AUTHOR', 'ناشناس')
        body = c.findtext('BODY', '')
        date = c.findtext('DATE', '')
        date_html = f'<span class="date">{date}</span>' if date else ''
        
        html += f'''
        <div class="comment-item">
            <strong>{author}</strong> {date_html}
            <p>{body}</p>
        </div>'''
        
    return html + '</div>'

def create_local_blog(xml_file, output_dir):
    if not os.path.isfile(xml_file):
        print(f"Error: The file '{xml_file}' does not exist.")
        sys.exit(1)

    posts_dir = os.path.join(output_dir, "posts")
    tags_dir = os.path.join(output_dir, "tags")
    baygani_dir = os.path.join(output_dir, "baygani")
    
    for directory in [output_dir, posts_dir, tags_dir, baygani_dir]:
        if not os.path.exists(directory):
            os.makedirs(directory)

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except Exception as e:
        print(f"Error reading XML: {e}")
        sys.exit(1)

    blog_title_elem = root.find('.//BLOG_INFO/TITLE')
    blog_title = blog_title_elem.text.strip() if (blog_title_elem is not None and blog_title_elem.text) else "بایگانی وبلاگ"

    css_content = """
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;700&display=swap');

    :root {
        --bg-body: #f0f2f5;
        --bg-container: #ffffff;
        --text-main: #333333;
        --text-heading: #2c3e50;
        --text-muted: #7f8c8d;
        --border-color: #e0e6ed;
        --border-light: #eaeaea;
        --accent-bg: #f9f9f9;
        --fade-start: rgba(255,255,255,0);
        --fade-end: rgba(255,255,255,1);
        --btn-bg: #f4f6f7;
        --btn-hover: #e2e8f0;
        --toggle-bg: #2c3e50;
        --toggle-color: #ffffff;
    }

    html.dark-mode {
        --bg-body: #121212;
        --bg-container: #1e1e1e;
        --text-main: #ffffff; 
        --text-heading: #ffffff;
        --text-muted: #aaaaaa;
        --border-color: #333333;
        --border-light: #333333;
        --accent-bg: #2a2a2a;
        --fade-start: rgba(30,30,30,0);
        --fade-end: rgba(30,30,30,1);
        --btn-bg: #333333;
        --btn-hover: #444444;
        --toggle-bg: #e0e0e0; 
        --toggle-color: #121212;
    }

    body {
        font-family: 'Vazirmatn', sans-serif;
        direction: rtl;
        text-align: justify;
        background-color: var(--bg-body);
        color: var(--text-main);
        line-height: 1.8;
        margin: 0;
        padding: 40px 20px;
        transition: background-color 0.3s ease, color 0.3s ease;
    }
    
    .container { max-width: 1200px; margin: auto; }
    
    .page-header { position: relative; background: var(--bg-container); padding: 30px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 40px; text-align: center; }
    
    h1, h2 { color: var(--text-heading); }
    h1 { margin: 0; font-size: 2.2em; }
    a { color: #2980b9; text-decoration: none; transition: color 0.2s; }
    a:hover { color: #1abc9c; }
    
    .section-title { font-size: 1.4em; color: var(--text-heading); border-bottom: 2px solid var(--border-color); padding-bottom: 10px; margin-bottom: 25px; margin-top: 40px; font-weight: bold;}
    .section-title:first-child { margin-top: 0; }
    
    .main-layout { display: flex; flex-direction: row; gap: 40px; align-items: flex-start; }
    .content-area { flex: 3; min-width: 0; }
    .sidebar-area { flex: 1; min-width: 300px; background: var(--bg-container); padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.04); position: sticky; top: 20px; }
    
    @media (max-width: 850px) {
        .main-layout { flex-direction: column; }
        .sidebar-area { width: 100%; position: static; box-sizing: border-box; margin-top: 20px;}
    }
    
    .tags-grid { display: flex; flex-wrap: wrap; gap: 10px; }
    .tag-tile { background: linear-gradient(135deg, #3498db, #2980b9); color: white; padding: 6px 14px; border-radius: 20px; font-size: 0.9em; display: flex; align-items: center; gap: 8px; transition: transform 0.2s, box-shadow 0.2s; }
    .tag-tile:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(50, 150, 219, 0.3); color: white;}
    
    .baygani-tile { background: linear-gradient(135deg, #34495e, #2c3e50); color: white; padding: 6px 14px; border-radius: 20px; font-size: 0.9em; display: flex; align-items: center; gap: 8px; transition: transform 0.2s, box-shadow 0.2s; }
    .baygani-tile:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(44, 62, 80, 0.3); color: white;}
    
    .tag-count { background: rgba(255,255,255,0.25); padding: 2px 6px; border-radius: 15px; font-size: 0.8em; font-weight: bold;}
    
    .posts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 25px; }
    .post-card { background: var(--bg-container); border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.04); transition: transform 0.2s, box-shadow 0.2s; border: 1px solid var(--border-light); display: flex; flex-direction: column; }
    .post-card:hover { transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0,0,0,0.1); }
    .card-img { width: 100%; height: 200px; object-fit: cover; border-bottom: 1px solid var(--border-color); }
    
    .card-content { padding: 25px; flex-grow: 1; display: flex; flex-direction: column; }
    .card-content h2 { margin-top: 0; font-size: 1.3em; margin-bottom: 8px; text-align: right; }
    .card-content h2 a { color: var(--text-heading); }
    .card-content .date { font-size: 0.85em; color: var(--text-muted); margin-bottom: 15px; }
    
    .card-content .excerpt-container { 
        position: relative;
        flex-grow: 1; 
        margin-bottom: 20px; 
        color: var(--text-main); 
        font-size: 0.95em; 
        line-height: 1.8;
        max-height: 200px; 
        overflow: hidden; 
    }
    .card-content .excerpt-container p {
        margin: 0 0 4px 0; 
    }
    .card-content .excerpt-container::after {
        content: "";
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 60px;
        background: linear-gradient(to bottom, var(--fade-start), var(--fade-end) 90%);
        pointer-events: none; 
    }
    
    .read-more { margin-top: auto; align-self: flex-start; font-weight: bold; font-size: 0.9em; padding: 8px 16px; background: var(--btn-bg); border-radius: 6px; color: #2980b9; transition: background 0.2s; }
    .read-more:hover { background: var(--btn-hover); text-decoration: none;}
    
    .single-post-container { max-width: 800px; margin: auto; background: var(--bg-container); padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
    .single-post-container div img { display: block; margin: 20px auto; max-width: 100%; height: auto; border-radius: 8px;}
    .single-post-container p { margin-bottom: 10px; }
    .post-tags { font-size: 0.85em; color: var(--text-muted); margin-top: 40px; padding-top: 15px; border-top: 1px dashed var(--border-color); }
    .post-tags a { color: #2980b9; font-weight: bold; }
    
    .pagination { display: flex; justify-content: space-between; align-items: center; margin-top: 40px; padding: 20px; background: var(--bg-container); border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); }
    .pagination a { padding: 10px 20px; background: #2c3e50; color: white; border-radius: 8px; font-size: 0.9em; cursor: pointer; transition: background 0.2s;}
    .pagination a:hover { background: #1a252f; text-decoration: none; }
    .page-numbers { display: flex; gap: 5px; direction: rtl; align-items: center; } 
    .page-numbers a, .page-numbers span { padding: 8px 14px; background: var(--btn-bg); color: var(--text-main); border-radius: 6px; font-size: 0.9em; cursor: pointer; transition: background 0.2s;}
    .page-numbers a:hover { background: var(--btn-hover); }
    .page-numbers .current-page { background: #2980b9; color: white; font-weight: bold; cursor: default; }

    /* --- FONT OVERRIDE FIXES --- */
    /* Force clean styles on single post content */
    .post-content-body { font-size: 16px !important; }
    .post-content-body font,
    .post-content-body span,
    .post-content-body p,
    .post-content-body div,
    .post-content-body * {
        color: var(--text-main) !important;
        font-family: 'Vazirmatn', sans-serif !important;
        font-size: 16px !important;
        line-height: 1.8 !important;
        background-color: transparent !important;
    }
    .post-content-body h1, .post-content-body h2, .post-content-body h3 {
        color: var(--text-heading) !important;
        font-family: 'Vazirmatn', sans-serif !important;
        background-color: transparent !important;
    }
    
    /* Force clean styles on previews in the tiles (Index, Tags, Baygani) */
    .excerpt-container { font-size: 15px !important; }
    .excerpt-container font,
    .excerpt-container span,
    .excerpt-container p,
    .excerpt-container div,
    .excerpt-container * {
        color: var(--text-main) !important;
        font-family: 'Vazirmatn', sans-serif !important;
        font-size: 15px !important;
        line-height: 1.8 !important;
        background-color: transparent !important;
    }

    /* Comments Section Styling */
    .comments-section { margin-top: 50px; padding-top: 20px; border-top: 2px solid var(--border-color); }
    .comment-item { background: var(--accent-bg); padding: 20px; border-radius: 8px; margin-bottom: 15px; border-right: 4px solid #3498db; }
    .comment-item strong { color: var(--text-heading); font-size: 1.1em; }
    .comment-item .date { font-size: 0.85em; color: var(--text-muted); margin-right: 10px; }
    .comment-item p { margin: 10px 0 0 0; }

    /* Theme Toggle Button */
    .theme-toggle-btn {
        position: absolute;
        top: 25px;
        left: 25px;
        background: var(--toggle-bg);
        color: var(--toggle-color);
        border: none;
        font-size: 20px;
        width: 45px;
        height: 45px;
        border-radius: 50%;
        cursor: pointer;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.2s ease, background 0.3s ease, opacity 0.2s ease;
        z-index: 10;
    }
    .theme-toggle-btn:hover {
        transform: scale(1.1);
        opacity: 0.9;
    }
    """
    
    with open(os.path.join(output_dir, "style.css"), "w", encoding="utf-8") as f:
        f.write(css_content)

    posts = root.findall('.//POST')
    if not posts:
        print("No posts found.")
        sys.exit(1)

    all_posts_info = []
    tags_dict = {}
    baygani_dict = {} 
    
    theme_head_script = """
    <script>
        if (localStorage.getItem('theme') === 'dark') {
            document.documentElement.classList.add('dark-mode');
        }
    </script>
    """
    
    theme_btn_html = '<button id="theme-toggle" class="theme-toggle-btn" aria-label="تغییر تم">🌙</button>'

    theme_script = """
    <script>
        const themeBtn = document.getElementById('theme-toggle');
        
        function updateIcon() {
            if (document.documentElement.classList.contains('dark-mode')) {
                themeBtn.innerHTML = '☀️';
            } else {
                themeBtn.innerHTML = '🌙';
            }
        }
        
        updateIcon();
        
        themeBtn.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark-mode');
            const isDark = document.documentElement.classList.contains('dark-mode');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            updateIcon();
        });
    </script>
    """

    print("Parsing posts and building metadata...")

    for i, post in enumerate(posts):
        title_elem = post.find('TITLE')
        title_raw = title_elem.text.strip() if (title_elem is not None and title_elem.text) else ""
        title = "—" if not title_raw or title_raw.lower() == "unknown" else title_raw
        
        content_elem = post.find('CONTENT')
        raw_content = content_elem.text if (content_elem is not None and content_elem.text) else "<p>بدون محتوا</p>"
        content = strip_hardcoded_styles(raw_content)

        comments_html = render_comments(post)

        img_url, raw_excerpt = extract_preview(content)
        excerpt = strip_hardcoded_styles(raw_excerpt)
        
        date_elem = post.find('CREATED_DATE')
        raw_date = date_elem.text.strip() if (date_elem is not None and date_elem.text) else "1970-01-01"
        
        date_text, time_text = convert_to_jalali(raw_date)

        baygani_key, baygani_label = get_baygani_info(raw_date)
        url_elem = post.find('URL')
        url_slug = url_elem.text.strip() if (url_elem is not None and url_elem.text) else f"post_{i+1}"
        filename = f"{sanitize_filename(url_slug)}.html"

        tags_elem = post.find('TAGS')
        post_tags = []
        tag_links_html = []
        
        post_metadata = {
            'title': title, 'filename': filename, 'date': date_text, 'raw_date': raw_date,
            'img_url': img_url, 'excerpt': excerpt
        }

        unique_post_tags = set()
        if tags_elem is not None:
            unique_post_tags = set(t.text.strip() for t in tags_elem.findall('.//NAME') if t.text and t.text.strip())
            
        if title == "—":
            unique_post_tags.add("سیاه‌مشق")
            
        for clean_tag in unique_post_tags:
            safe_tag_filename = sanitize_filename(clean_tag)
            post_tags.append(clean_tag)
            tag_links_html.append(f'<a href="../tags/{safe_tag_filename}.html">{clean_tag}</a>')
            
            if clean_tag not in tags_dict:
                tags_dict[clean_tag] = []
            tags_dict[clean_tag].append(post_metadata)

        if baygani_key not in baygani_dict:
            baygani_dict[baygani_key] = {'label': baygani_label, 'posts': []}
        baygani_dict[baygani_key]['posts'].append(post_metadata)

        tags_html = f'<div class="post-tags"><strong>برچسب‌ها:</strong> {"، ".join(tag_links_html)}</div>' if tag_links_html else ""
        date_html = f'<div class="date" style="color: var(--text-muted); font-size: 0.9em; margin-bottom: 20px;">{date_text}</div>' if date_text else ""
        
        time_footer_html = f'<div style="color: var(--text-muted); font-size: 0.85em; margin-top: 40px; padding-top: 15px; border-top: 1px dashed var(--border-color);">تاریخ و زمان انتشار: {date_text} ساعت {time_text}</div>' if time_text else ""
        
        all_posts_info.append(post_metadata)

        post_html = f"""
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title} | {blog_title}</title>
            <link rel="stylesheet" href="../style.css?v=2">
            {theme_head_script}
        </head>
        <body>
            <div class="single-post-container">
                <div class="page-header" style="margin-bottom: 30px;">
                    {theme_btn_html}
                    <h1><a href="../index.html" style="color: inherit; text-decoration: none;">{blog_title}</a></h1>
                    <p style="color: var(--text-muted); margin-top: 10px; font-size: 1.1em;">محمدصادق رسولی</p>
                </div>
                <a href="../index.html" style="display: inline-block; margin-bottom: 20px; font-weight: bold;">← بازگشت به صفحه اصلی</a>
                <h2 style="border-bottom: 2px solid var(--border-color); padding-bottom: 15px; margin-top: 10px;">{title}</h2>
                {date_html}
                <div class="post-content-body">{content}</div>
                {time_footer_html}
                {tags_html}
                {comments_html}
            </div>
            {theme_script}
        </body>
        </html>
        """
        with open(os.path.join(posts_dir, filename), "w", encoding="utf-8") as f:
            f.write(post_html)

    all_posts_info.sort(key=lambda x: x['raw_date'], reverse=True)
    for tag in tags_dict:
        tags_dict[tag].sort(key=lambda x: x['raw_date'], reverse=True)
    for key in baygani_dict:
        baygani_dict[key]['posts'].sort(key=lambda x: x['raw_date'], reverse=True)

    sorted_tags = sorted(tags_dict.items(), key=lambda item: len(item[1]), reverse=True)
    sorted_baygani_keys = sorted(baygani_dict.keys(), reverse=True)

    print("Generating Grouped Pages (Tags & Baygani)...")
    
    for tag, posts_list in tags_dict.items():
        safe_tag_filename = f"{sanitize_filename(tag)}.html"
        tag_page_html = f"""
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>برچسب: {tag} | {blog_title}</title>
            <link rel="stylesheet" href="../style.css?v=2">
            {theme_head_script}
        </head>
        <body>
            <div class="container">
                <div class="page-header">
                    {theme_btn_html}
                    <a href="../index.html" style="float: right; font-weight: bold;">← بازگشت</a>
                    <h1><a href="../index.html" style="color: inherit; text-decoration: none;">{blog_title}</a></h1>
                    <p style="color: var(--text-muted); margin-top: 10px; font-size: 1.1em;">محمدصادق رسولی</p>
                    <hr style="border: 0; border-top: 1px solid var(--border-color); margin: 20px 0;">
                    <h2 style="margin: 0; font-size: 1.5em; text-align: center;">نوشته‌های دارای برچسب: {tag}</h2>
                    <p style="color: var(--text-muted); margin-top: 5px; font-size: 0.9em; text-align: center;">{to_persian_num(len(posts_list))} نوشته یافت شد</p>
                </div>
                <div class="posts-grid">
        """
        for p in posts_list:
            tag_page_html += f'<div class="post-card">'
            if p["img_url"]:
                tag_page_html += f'<a href="../posts/{p["filename"]}"><img src="{p["img_url"]}" class="card-img" alt="تصویر پست"></a>'
            tag_page_html += f'<div class="card-content">'
            tag_page_html += f'<h2><a href="../posts/{p["filename"]}">{p["title"]}</a></h2>'
            if p["date"]:
                tag_page_html += f'<div class="date">{p["date"]}</div>'
            tag_page_html += f'<div class="excerpt-container">{p["excerpt"]}</div>'
            tag_page_html += f'<a href="../posts/{p["filename"]}" class="read-more">ادامه مطلب ←</a>'
            tag_page_html += f'</div></div>'
            
        tag_page_html += f"""
                </div>
            </div>
            {theme_script}
        </body>
        </html>
        """
        with open(os.path.join(tags_dir, safe_tag_filename), "w", encoding="utf-8") as f:
            f.write(tag_page_html)

    for key in sorted_baygani_keys:
        baygani_data = baygani_dict[key]
        baygani_page_html = f"""
        <!DOCTYPE html>
        <html lang="fa" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>بایگانی: {baygani_data['label']} | {blog_title}</title>
            <link rel="stylesheet" href="../style.css?v=2">
            {theme_head_script}
        </head>
        <body>
            <div class="container">
                <div class="page-header">
                    {theme_btn_html}
                    <a href="../index.html" style="float: right; font-weight: bold;">← بازگشت</a>
                    <h1><a href="../index.html" style="color: inherit; text-decoration: none;">{blog_title}</a></h1>
                    <p style="color: var(--text-muted); margin-top: 10px; font-size: 1.1em;">محمدصادق رسولی</p>
                    <hr style="border: 0; border-top: 1px solid var(--border-color); margin: 20px 0;">
                    <h2 style="margin: 0; font-size: 1.5em; text-align: center;">بایگانی نوشته‌ها: {baygani_data['label']}</h2>
                    <p style="color: var(--text-muted); margin-top: 5px; font-size: 0.9em; text-align: center;">{to_persian_num(len(baygani_data['posts']))} نوشته یافت شد</p>
                </div>
                <div class="posts-grid">
        """
        for p in baygani_data['posts']:
            baygani_page_html += f'<div class="post-card">'
            if p["img_url"]:
                baygani_page_html += f'<a href="../posts/{p["filename"]}"><img src="{p["img_url"]}" class="card-img" alt="تصویر پست"></a>'
            baygani_page_html += f'<div class="card-content">'
            baygani_page_html += f'<h2><a href="../posts/{p["filename"]}">{p["title"]}</a></h2>'
            if p["date"]:
                baygani_page_html += f'<div class="date">{p["date"]}</div>'
            baygani_page_html += f'<div class="excerpt-container">{p["excerpt"]}</div>'
            baygani_page_html += f'<a href="../posts/{p["filename"]}" class="read-more">ادامه مطلب ←</a>'
            baygani_page_html += f'</div></div>'
            
        baygani_page_html += f"""
                </div>
            </div>
            {theme_script}
        </body>
        </html>
        """
        with open(os.path.join(baygani_dir, f"{key}.html"), "w", encoding="utf-8") as f:
            f.write(baygani_page_html)

    tag_tiles_html = ""
    for tag, posts_list in sorted_tags:
        count = to_persian_num(len(posts_list))
        safe_tag_filename = sanitize_filename(tag)
        tag_tiles_html += f'<a href="tags/{safe_tag_filename}.html" class="tag-tile"><span class="tag-name">{tag}</span><span class="tag-count">{count}</span></a>\n'

    baygani_tiles_html = ""
    for key in sorted_baygani_keys:
        baygani_data = baygani_dict[key]
        count = to_persian_num(len(baygani_data['posts']))
        baygani_tiles_html += f'<a href="baygani/{key}.html" class="baygani-tile"><span class="tag-name">{baygani_data["label"]}</span><span class="tag-count">{count}</span></a>\n'

    posts_json = json.dumps(all_posts_info, ensure_ascii=False).replace("</", "<\\/")
    
    print("Generating Master Index...")

    index_html = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{blog_title}</title>
        <link rel="stylesheet" href="style.css?v=2">
        {theme_head_script}
    </head>
    <body>
        <div class="container">
            <div class="page-header">
                {theme_btn_html}
                <h1><a href="index.html" style="color: inherit; text-decoration: none;">{blog_title}</a></h1>
                <p style="color: var(--text-muted); margin-top: 10px; font-size: 1.1em;">محمدصادق رسولی</p>
            </div>
            
            <div class="main-layout">
                <div class="content-area">
                    <div class="section-title">آخرین نوشته‌ها</div>
                    <div id="posts-container" class="posts-grid">
                        </div>
                    <div class="pagination" id="pagination-container">
                    </div>
                </div>

                <div class="sidebar-area">
                    <div class="section-title">موضوعات پرطرفدار</div>
                    <div class="tags-grid">
                        {tag_tiles_html}
                    </div>
                    
                    <div class="section-title">بایگانی ماهانه</div>
                    <div class="tags-grid">
                        {baygani_tiles_html}
                    </div>
                </div>
            </div>
            
        </div>
        
        {theme_script}

        <script id="posts-data" type="application/json">
        {posts_json}
        </script>

        <script>
            function toFa(num) {{
                const farsiDigits = ['۰','۱','۲','۳','۴','۵','۶','۷','۸','۹'];
                return num.toString().replace(/\\d/g, x => farsiDigits[x]);
            }}

            const allPosts = JSON.parse(document.getElementById('posts-data').textContent);
            const postsPerPage = 12; 
            let currentPage = 1;

            function renderPosts() {{
                const container = document.getElementById('posts-container');
                container.innerHTML = '';
                
                const start = (currentPage - 1) * postsPerPage;
                const end = start + postsPerPage;
                const pagePosts = allPosts.slice(start, end);

                pagePosts.forEach(p => {{
                    let html = '<div class="post-card">';
                    if (p.img_url) {{
                        html += '<a href="posts/' + p.filename + '"><img src="' + p.img_url + '" class="card-img" alt="تصویر پست"></a>';
                    }}
                    html += '<div class="card-content">';
                    html += '<h2><a href="posts/' + p.filename + '">' + p.title + '</a></h2>';
                    if (p.date) html += '<div class="date">' + p.date + '</div>';
                    
                    html += '<div class="excerpt-container">' + p.excerpt + '</div>'; 
                    
                    html += '<a href="posts/' + p.filename + '" class="read-more">ادامه مطلب ←</a>';
                    html += '</div></div>'; 
                    container.innerHTML += html;
                }});
                
                renderPagination();
            }}

            function renderPagination() {{
                const container = document.getElementById('pagination-container');
                container.innerHTML = '';
                const totalPages = Math.ceil(allPosts.length / postsPerPage);

                if (totalPages <= 1) {{
                    container.style.display = 'none';
                    return;
                }} else {{
                    container.style.display = 'flex';
                }}

                if (currentPage > 1) {{
                    container.innerHTML += '<a onclick="changePage(' + (currentPage - 1) + ')">→ جدیدتر</a>';
                }} else {{
                    container.innerHTML += '<span></span>';
                }}
                
                let pageNumbers = '<div class="page-numbers">';
                let lastAdded = 0;
                
                for(let i=1; i<=totalPages; i++) {{
                    if (i <= 5 || i > totalPages - 3 || Math.abs(i - currentPage) <= 1) {{
                        if (lastAdded > 0 && i - lastAdded > 1) {{
                            pageNumbers += '<span>...</span>';
                        }}
                        if (i === currentPage) {{
                            pageNumbers += '<span class="current-page">' + toFa(i) + '</span>';
                        }} else {{
                            pageNumbers += '<a onclick="changePage(' + i + ')">' + toFa(i) + '</a>';
                        }}
                        lastAdded = i;
                    }}
                }}
                pageNumbers += '</div>';
                
                container.innerHTML += pageNumbers;

                if (currentPage < totalPages) {{
                    container.innerHTML += '<a onclick="changePage(' + (currentPage + 1) + ')">قدیمی‌تر ←</a>';
                }} else {{
                    container.innerHTML += '<span></span>';
                }}
            }}

            function changePage(page) {{
                currentPage = page;
                renderPosts();
                const offset = document.querySelector('.content-area .section-title').offsetTop - 20;
                window.scrollTo({{ top: offset, behavior: 'smooth' }});
            }}

            renderPosts();
        </script>
    </body>
    </html>
    """
    
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"\n✅ Auto-tagging for missing titles implemented.")
    print(f"📂 Output saved to: {os.path.abspath(output_dir)}")
    print(f"🌐 Open '{os.path.join(output_dir, 'index.html')}' in your browser to view.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a Blog.ir XML backup into a local static HTML website.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("xml_file", help="Path to your XML backup file (e.g., delsharm.xml)")
    parser.add_argument("-o", "--output", default="local_blog", help="Directory where the HTML files will be saved")
    
    args = parser.parse_args()
    create_local_blog(args.xml_file, args.output)