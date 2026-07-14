import express from 'express';
import fs from 'fs';
import path from 'path';
import { simpleGit } from 'simple-git';
import { fileURLToPath } from 'url';
import matter from 'gray-matter';
import * as yaml from 'js-yaml';
import multer from 'multer';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const git = simpleGit();
const PORT = 3000;

// Paths
const postsDir = path.join(__dirname, 'src', 'content', 'blog');
const commentsDir = path.join(__dirname, 'src', 'content', 'comments');
const imagesDir = path.join(__dirname, 'public', 'images');

// Ensure the images directory exists
if (!fs.existsSync(imagesDir)) {
    fs.mkdirSync(imagesDir, { recursive: true });
}

// Configure Multer for Image Uploads
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, imagesDir);
    },
    filename: function (req, file, cb) {
        const safeName = Date.now() + '-' + file.originalname.replace(/\s+/g, '-').toLowerCase();
        cb(null, safeName);
    }
});
const upload = multer({ storage: storage });

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Helper: Count comments per post
function getCommentCounts() {
    const counts = {};
    if (fs.existsSync(commentsDir)) {
        const files = fs.readdirSync(commentsDir).filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));
        for (const file of files) {
            try {
                const content = fs.readFileSync(path.join(commentsDir, file), 'utf8');
                const parsed = yaml.load(content);
                if (parsed && parsed.postSlug) {
                    counts[parsed.postSlug] = (counts[parsed.postSlug] || 0) + 1;
                }
            } catch (e) {
                console.error(`Error parsing comment file: ${file}`, e);
            }
        }
    }
    return counts;
}

// 1. Serve the HTML Portal
app.get('/', (req, res) => {
    const commentCounts = getCommentCounts();
    let files = [];
    if (fs.existsSync(postsDir)) {
        files = fs.readdirSync(postsDir).filter(f => f.endsWith('.md') || f.endsWith('.mdx'));
    }
    
    let postsData = [];

    for (const file of files) {
        const content = fs.readFileSync(path.join(postsDir, file), 'utf-8');
        const parsed = matter(content);
        const slug = file.replace(/\.mdx?$/, '');
        
        postsData.push({
            filename: file,
            slug: slug,
            title: parsed.data.title || file,
            date: new Date(parsed.data.date || 0).getTime(),
            comments: commentCounts[slug] || 0
        });
    }

    postsData.sort((a, b) => b.date - a.date);

    const html = `
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="utf-8">
        <title>پنل مدیریت دلشرم</title>
        
        <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;700&display=swap" rel="stylesheet">
        <link href="https://cdn.quilljs.com/1.3.6/quill.snow.css" rel="stylesheet">
        
        <style>
            /* --- CSS VARIABLES FOR DARK/LIGHT MODE --- */
            :root {
                --bg-body: #f4f6f7;
                --bg-container: #ffffff;
                --text-main: #333333;
                --text-muted: #7f8c8d;
                --border-color: #eeeeee;
                --input-bg: #ffffff;
                --hover-bg: #f9f9f9;
                --meta-bg: #ecf0f1;
            }
            
            body.dark-mode {
                --bg-body: #121212;
                --bg-container: #1e1e1e;
                --text-main: #e0e0e0;
                --text-muted: #aaaaaa;
                --border-color: #333333;
                --input-bg: #2d2d2d;
                --hover-bg: #252525;
                --meta-bg: #333333;
            }

            body { font-family: 'Vazirmatn', Tahoma, sans-serif; background: var(--bg-body); padding: 20px; color: var(--text-main); transition: all 0.3s ease; }
            .container { max-width: 1000px; margin: auto; background: var(--bg-container); padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: all 0.3s ease; }
            
            .header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 2px solid var(--border-color); }
            .header-bar h1 { margin: 0; display: flex; align-items: center; gap: 15px; }
            .header-actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
            
            #theme-toggle { background: transparent; color: var(--text-main); font-size: 1.5em; cursor: pointer; padding: 0; margin: 0; box-shadow: none; border: none; }
            #theme-toggle:hover { opacity: 0.7; }

            .post-item { display: flex; justify-content: space-between; align-items: center; padding: 15px 10px; border-bottom: 1px solid var(--border-color); transition: background 0.2s; }
            .post-item:hover { background: var(--hover-bg); }
            .post-info { display: flex; flex-direction: column; gap: 5px; }
            
            .meta-tag { font-size: 0.85em; color: var(--text-muted); background: var(--meta-bg); padding: 3px 8px; border-radius: 10px; display: inline-block; width: fit-content; }
            
            button { background: #3498db; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; font-weight: bold; font-family: inherit; transition: background 0.2s; }
            button:hover:not(:disabled) { opacity: 0.9; }
            button:disabled { opacity: 0.6; cursor: not-allowed; }
            
            .btn-pull { background: #27ae60; }
            .btn-new { background: #9b59b6; }
            .btn-about { background: #8e44ad; }
            .btn-comments { background: #e67e22; margin-left: 5px; }
            .btn-cancel { background: #e74c3c; margin-right: 10px; }
            .btn-delete { background: #c0392b; font-size: 0.8em; padding: 5px 10px; }
            .btn-toggle { background: #34495e; margin-bottom: 15px; }
            
            /* Form Grid */
            .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
            .form-group { margin-bottom: 15px; }
            .form-group.full-width { grid-column: span 2; }
            .form-group label { display: block; margin-bottom: 8px; font-weight: bold; color: var(--text-main); }
            .form-group input { width: 100%; padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; font-family: inherit; font-size: 1em; box-sizing: border-box; background: var(--input-bg); color: var(--text-main); }
            .form-group small { color: var(--text-muted) !important; }

            /* Quill & Code Editor Overrides */
            .ql-toolbar { background: var(--meta-bg); border-radius: 8px 8px 0 0; border-color: var(--border-color) !important; direction: ltr; text-align: left; }
            .ql-container { background: var(--input-bg); height: 450px !important; border-radius: 0 0 8px 8px; border-color: var(--border-color) !important; font-family: 'Vazirmatn', inherit !important; font-size: 16px !important; }
            .ql-editor { direction: rtl; text-align: right; color: var(--text-main); }
            .ql-editor a { color: #3498db; text-decoration: underline; cursor: pointer; }
            
            .ql-toolbar button.ql-rtl_btn, .ql-toolbar button.ql-ltr_btn { width: 45px !important; color: var(--text-main); }
            .ql-toolbar button.ql-rtl_btn::after { content: 'RTL'; font-weight: bold; font-family: Tahoma; font-size: 12px; }
            .ql-toolbar button.ql-ltr_btn::after { content: 'LTR'; font-weight: bold; font-family: Tahoma; font-size: 12px; }
            .ql-toolbar button.ql-image_url { width: 85px !important; color: var(--text-main); }
            .ql-toolbar button.ql-image_url::after { content: '🔗 عکس URL'; font-weight: bold; font-family: Tahoma; font-size: 12px; }
            
            /* SVG icons color for dark mode in Quill */
            body.dark-mode .ql-stroke { stroke: #e0e0e0; }
            body.dark-mode .ql-fill { fill: #e0e0e0; }

            textarea { background: var(--input-bg); color: var(--text-main); border: 1px solid var(--border-color); }
            #raw-markdown { width: 100%; height: 450px; padding: 15px; direction: ltr; font-family: monospace; border-radius: 8px; font-size: 14px; line-height: 1.5; box-sizing: border-box; display: none; }
            
            #about-raw-content { width: 100%; height: 450px; padding: 15px; direction: ltr; font-family: monospace; border-radius: 8px; font-size: 14px; line-height: 1.5; box-sizing: border-box; display: block; background: var(--input-bg); color: var(--text-main); border: 1px solid var(--border-color); }

            /* Pagination */
            .pagination { display: flex; justify-content: center; align-items: center; gap: 8px; margin-top: 20px; flex-wrap: wrap; }
            .page-btn { background: var(--meta-bg); color: var(--text-main); min-width: 35px; padding: 8px 12px; }
            .page-btn.active { background: #3498db; color: white; }
            
            /* Comments */
            .comment-card { background: var(--hover-bg); padding: 15px; border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 15px; }
            .reply-box { margin-top: 15px; padding-top: 15px; border-top: 1px dashed var(--border-color); }
            .reply-textarea { height: 80px; direction: rtl; font-family: inherit; margin-bottom: 10px; width: 100%; padding: 10px; border-radius: 6px; box-sizing: border-box;}
        </style>
    </head>
    <body>
        <div class="container">
            
            <!-- DASHBOARD VIEW -->
            <div id="dashboard-view">
                <div class="header-bar">
                    <h1>
                        مدیریت پست‌ها
                        <button id="theme-toggle" onclick="toggleTheme()" title="تغییر پوسته">🌙</button>
                    </h1>
                    <div class="header-actions">
                        <button class="btn-new" onclick="showPostForm()">➕ پست جدید</button>
                        <button class="btn-about" onclick="editAboutPage()">👤 ویرایش درباره من</button>
                        <button class="btn-pull" onclick="pullChanges()">⬇️ دریافت دیدگاه‌ها</button>
                    </div>
                </div>
                <div id="post-list"></div>
                <div id="pagination-controls" class="pagination"></div>
            </div>
            
            <!-- ABOUT PAGE EDITOR VIEW (Safe Raw Mode) -->
            <div id="about-form-section" style="display:none;">
                <h2>ویرایش صفحه درباره من</h2>
                <div style="background: rgba(241, 196, 15, 0.15); padding:10px; margin-bottom:15px; border-radius:5px; color:#d35400; border-right: 4px solid #f1c40f; font-size:0.9em;">
                    <strong>توجه:</strong> این بخش مستقیماً کدهای فایل ساختاری (Astro) را ویرایش می‌کند. ویرایشگر دیداری برای این صفحه غیرفعال است تا کدهای قالب‌بندی سایت شما از بین نروند.
                </div>
                <div class="form-group full-width">
                    <textarea id="about-raw-content" spellcheck="false"></textarea>
                </div>
                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border-color);">
                    <button id="btn-save-about" onclick="saveAboutForm()">ذخیره و ارسال تغییرات</button>
                    <button class="btn-cancel" onclick="showDashboard()">لغو</button>
                </div>
            </div>

            <!-- SINGLE STAGE POST FORM -->
            <div id="post-form-section" style="display:none;">
                <h2 id="form-section-title">ایجاد پست جدید</h2>
                
                <div class="form-grid">
                    <div class="form-group">
                        <label>عنوان پست:</label>
                        <input type="text" id="post-title" placeholder="مثال: یادداشتی بر یک کتاب">
                    </div>
                    <div class="form-group">
                        <label>نام فایل انگلیسی (Slug):</label>
                        <input type="text" id="post-slug" placeholder="مثال: book-review-2024" dir="ltr">
                    </div>
                    <div class="form-group full-width">
                        <label>تصویر اصلی (Hero Image):</label>
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <input type="text" id="post-hero-image" placeholder="مثال: /images/cover.jpg یا https://example.com/image.jpg" dir="ltr" style="flex-grow: 1;">
                            <input type="file" id="hero-image-upload" accept="image/*" style="display: none;" onchange="uploadHeroImage(event)">
                            <button type="button" onclick="document.getElementById('hero-image-upload').click()" style="background: #2ecc71; white-space: nowrap;">📤 آپلود عکس</button>
                        </div>
                        <small>میتوانید آدرس عکس را تایپ کنید یا یک فایل را از سیستم خود آپلود کنید.</small>
                    </div>
                    <div class="form-group full-width">
                        <label>برچسب‌ها (Tags):</label>
                        <input type="text" id="post-tags" placeholder="مثال: شعر، داستان, کتاب">
                        <small>با کاما انگلیسی (,) یا ویرگول فارسی (،) جدا کنید. فاصله‌های اضافی خودکار حذف می‌شوند.</small>
                    </div>
                </div>

                <div class="form-group full-width">
                    <label>محتوای پست:</label>
                    <button class="btn-toggle" id="toggle-mode-btn" onclick="toggleEditorMode()">💻 نمایش سورس (Markdown/HTML)</button>
                    
                    <div id="quill-container">
                        <div id="quill-editor"></div>
                    </div>
                    <textarea id="raw-markdown" spellcheck="false"></textarea>
                </div>
                
                <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border-color);">
                    <button id="btn-save-post" onclick="savePostForm()">ذخیره و ارسال به گیت‌هاب</button>
                    <button class="btn-cancel" onclick="showDashboard()">لغو</button>
                </div>
            </div>

            <!-- COMMENTS VIEW -->
            <div id="comments-section" style="display:none;">
                <h2 id="comments-title"></h2>
                <button class="btn-cancel" onclick="showDashboard()" style="margin-bottom: 20px;">بازگشت به داشبورد</button>
                <div id="comments-container"></div>
            </div>

        </div>

        <script src="https://cdn.quilljs.com/1.3.6/quill.min.js"></script>

        <script>
            // --- THEME TOGGLE LOGIC ---
            const themeBtn = document.getElementById('theme-toggle');
            const savedTheme = localStorage.getItem('portal-theme') || 'light';
            if (savedTheme === 'dark') {
                document.body.classList.add('dark-mode');
                themeBtn.innerText = '☀️';
            }

            function toggleTheme() {
                const isDark = document.body.classList.toggle('dark-mode');
                themeBtn.innerText = isDark ? '☀️' : '🌙';
                localStorage.setItem('portal-theme', isDark ? 'dark' : 'light');
            }

            const ALL_POSTS = ${JSON.stringify(postsData)};
            let currentPage = 1;
            const postsPerPage = 20;
            
            let quill;
            let isCodeMode = false;
            let currentOriginalFilename = ''; 
            let activeAboutFilepath = ''; 

            function toFa(num) {
                const farsiDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
                return num.toString().replace(/[0-9]/g, x => farsiDigits[x]);
            }

            // --- ABOUT PAGE LOGIC (Safe Mode) ---
            async function editAboutPage() {
                const res = await fetch('/api/about');
                if (!res.ok) {
                    alert('صفحه درباره من (about.astro یا about.md) یافت نشد.');
                    return;
                }
                const data = await res.json();
                activeAboutFilepath = data.filepath;
                
                document.getElementById('dashboard-view').style.display = 'none';
                document.getElementById('post-form-section').style.display = 'none';
                document.getElementById('comments-section').style.display = 'none';
                document.getElementById('about-form-section').style.display = 'block';
                
                document.getElementById('about-raw-content').value = data.content;
            }

            async function saveAboutForm() {
                const content = document.getElementById('about-raw-content').value;
                const btn = document.getElementById('btn-save-about');
                const originalText = btn.innerText;
                
                btn.innerText = 'در حال ذخیره و ارسال...';
                btn.disabled = true;

                try {
                    const res = await fetch('/api/save-about', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filepath: activeAboutFilepath, content: content })
                    });

                    if (res.ok) {
                        alert('تغییرات درباره من با موفقیت به گیت‌هاب ارسال شد!');
                        showDashboard();
                    } else {
                        alert('خطا در ذخیره اطلاعات');
                    }
                } catch (e) {
                    alert('خطا در ارتباط با سرور.');
                }
                
                btn.innerText = originalText;
                btn.disabled = false;
            }

            // --- IMAGE UPLOAD LOGIC ---
            async function uploadHeroImage(event) {
                const file = event.target.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('image', file);

                const btn = event.target.nextElementSibling;
                const originalText = btn.innerText;
                btn.innerText = 'در حال آپلود...';
                btn.disabled = true;

                try {
                    const res = await fetch('/api/upload-image', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (res.ok) {
                        const data = await res.json();
                        document.getElementById('post-hero-image').value = data.url;
                        alert('عکس با موفقیت آپلود شد!');
                    } else {
                        alert('خطا در آپلود عکس.');
                    }
                } catch (e) {
                    alert('خطا در ارتباط با سرور.');
                }
                
                btn.innerText = originalText;
                btn.disabled = false;
                event.target.value = ''; 
            }

            // --- QUILL INITIALIZATION ---
            function initQuill() {
                if(!quill) {
                    const AlignStyle = Quill.import('attributors/style/align');
                    const DirectionStyle = Quill.import('attributors/style/direction');
                    Quill.register(AlignStyle, true);
                    Quill.register(DirectionStyle, true);

                    quill = new Quill('#quill-editor', {
                        modules: {
                            toolbar: {
                                container: [
                                    [{ 'header': [1, 2, 3, false] }],
                                    ['bold', 'italic', 'underline', 'strike'],
                                    [{ 'color': [] }, { 'background': [] }],
                                    ['rtl_btn', 'ltr_btn'], 
                                    [{ 'align': [] }],
                                    [{ 'list': 'ordered'}, { 'list': 'bullet' }],
                                    ['link', 'image', 'image_url'], 
                                    ['clean']
                                ],
                                handlers: {
                                    'rtl_btn': function() {
                                        this.quill.format('direction', 'rtl');
                                        this.quill.format('align', 'right');
                                        updateDirectionButtons();
                                    },
                                    'ltr_btn': function() {
                                        this.quill.format('direction', false);
                                        this.quill.format('align', 'left');
                                        updateDirectionButtons();
                                    },
                                    'image_url': function() {
                                        const range = this.quill.getSelection() || { index: this.quill.getLength() };
                                        const url = prompt('لطفاً آدرس تصویر (URL) را وارد کنید:');
                                        if (url) {
                                            this.quill.insertEmbed(range.index, 'image', url);
                                        }
                                    }
                                }
                            }
                        },
                        theme: 'snow'
                    });

                    quill.on('editor-change', updateDirectionButtons);
                }
            }

            function updateDirectionButtons() {
                if (!quill) return;
                const format = quill.getFormat();
                const rtlBtn = document.querySelector('.ql-rtl_btn');
                const ltrBtn = document.querySelector('.ql-ltr_btn');
                
                if (rtlBtn && ltrBtn) {
                    if (format.direction === 'rtl') {
                        rtlBtn.classList.add('ql-active');
                        ltrBtn.classList.remove('ql-active');
                    } else {
                        rtlBtn.classList.remove('ql-active');
                        ltrBtn.classList.add('ql-active');
                    }
                }
            }

            // --- NAVIGATION ---
            function showDashboard() {
                document.getElementById('dashboard-view').style.display = 'block';
                document.getElementById('post-form-section').style.display = 'none';
                document.getElementById('comments-section').style.display = 'none';
                document.getElementById('about-form-section').style.display = 'none';
                renderPostList();
            }

            // --- RENDER POSTS ---
            function renderPostList() {
                const start = (currentPage - 1) * postsPerPage;
                const end = start + postsPerPage;
                const paginatedPosts = ALL_POSTS.slice(start, end);

                const html = paginatedPosts.map(post => \`
                    <div class="post-item">
                        <div class="post-info">
                            <strong>\${post.title}</strong>
                            <span class="meta-tag">💬 \${toFa(post.comments)} دیدگاه</span>
                        </div>
                        <div>
                            <button class="btn-comments" onclick="openComments('\${post.slug}', '\${post.title}')">نظرات</button>
                            <button onclick="showPostForm('\${post.filename}')">ویرایش</button>
                            <button class="btn-delete" style="margin-right: 5px;" onclick="deletePost('\${post.filename}', event)">🗑️ حذف</button>
                        </div>
                    </div>
                \`).join('');
                
                document.getElementById('post-list').innerHTML = html;
                renderPaginationControls();
            }

            function renderPaginationControls() {
                const totalPages = Math.ceil(ALL_POSTS.length / postsPerPage);
                let html = '';
                for (let i = 1; i <= totalPages; i++) {
                    html += \`<button class="page-btn \${i === currentPage ? 'active' : ''}" onclick="goToPage(\${i})">\${toFa(i)}</button>\`;
                }
                document.getElementById('pagination-controls').innerHTML = html;
            }

            function goToPage(page) { currentPage = page; renderPostList(); }

            // --- POST FORM LOGIC (SINGLE STAGE) ---
            function showPostForm(filename = null) {
                document.getElementById('dashboard-view').style.display = 'none';
                document.getElementById('post-form-section').style.display = 'block';
                
                initQuill();
                if(isCodeMode) toggleEditorMode(); 
                
                if (filename) {
                    document.getElementById('form-section-title').innerText = 'ویرایش پست: ' + filename;
                    currentOriginalFilename = filename;
                    
                    fetch('/api/post/' + filename).then(r => r.json()).then(data => {
                        document.getElementById('post-title').value = data.title;
                        document.getElementById('post-slug').value = filename.replace('.md', '');
                        document.getElementById('post-hero-image').value = data.heroImage || '';
                        document.getElementById('post-tags').value = data.tags.join('، ');
                        
                        quill.root.innerHTML = data.body;
                        document.getElementById('raw-markdown').value = data.body;
                        setTimeout(updateDirectionButtons, 100); 
                    });
                } else {
                    document.getElementById('form-section-title').innerText = 'ایجاد پست جدید';
                    currentOriginalFilename = ''; 
                    
                    document.getElementById('post-title').value = '';
                    document.getElementById('post-slug').value = '';
                    document.getElementById('post-hero-image').value = '';
                    document.getElementById('post-tags').value = '';
                    
                    quill.root.innerHTML = '';
                    document.getElementById('raw-markdown').value = '';
                    setTimeout(updateDirectionButtons, 100);
                }
            }

            function toggleEditorMode() {
                const quillContainer = document.getElementById('quill-container');
                const rawTextarea = document.getElementById('raw-markdown');
                const btn = document.getElementById('toggle-mode-btn');
                
                isCodeMode = !isCodeMode;
                
                if (isCodeMode) {
                    rawTextarea.value = quill.root.innerHTML;
                    quillContainer.style.display = 'none';
                    rawTextarea.style.display = 'block';
                    btn.innerText = '👁️ نمایش ویرایشگر دیداری (WYSIWYG)';
                } else {
                    quill.root.innerHTML = rawTextarea.value;
                    rawTextarea.style.display = 'none';
                    quillContainer.style.display = 'block';
                    btn.innerText = '💻 نمایش سورس (Markdown/HTML)';
                }
            }

            async function savePostForm() {
                const title = document.getElementById('post-title').value;
                let slug = document.getElementById('post-slug').value;
                const tagsInput = document.getElementById('post-tags').value;
                const heroImage = document.getElementById('post-hero-image').value;
                
                if (!title || !slug) {
                    alert('لطفا عنوان پست و نام فایل (Slug) را وارد کنید.');
                    return;
                }

                slug = slug.trim().replace(/\\s+/g, '-').toLowerCase();
                const newFilename = slug.endsWith('.md') ? slug : slug + '.md';
                
                const tagsArray = tagsInput.split(/[,،]/).map(t => t.trim()).filter(t => t.length > 0);
                const content = isCodeMode ? document.getElementById('raw-markdown').value : quill.root.innerHTML;
                
                const btn = document.querySelector('#btn-save-post');
                btn.innerText = 'در حال ذخیره و ارسال...';
                btn.disabled = true;

                const res = await fetch('/api/save-post', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        originalFilename: currentOriginalFilename,
                        newFilename: newFilename,
                        title: title,
                        tags: tagsArray,
                        heroImage: heroImage,
                        content: content
                    })
                });

                if(res.ok) {
                    alert('پست با موفقیت ذخیره و به گیت‌هاب ارسال شد!');
                    location.reload();
                } else {
                    alert('خطا در ذخیره پست');
                    btn.innerText = 'ذخیره و ارسال به گیت‌هاب';
                    btn.disabled = false;
                }
            }

            async function deletePost(filename, event) {
                if (!confirm('آیا از حذف این پست مطمئن هستید؟ غیرقابل بازگشت است!')) return;
                const btn = event.target;
                const originalText = btn.innerText;
                btn.innerText = 'در حال حذف...';
                btn.disabled = true;

                const res = await fetch('/api/delete-post', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: filename })
                });

                if (res.ok) location.reload();
                else { alert('خطا در حذف پست'); btn.innerText = originalText; btn.disabled = false; }
            }

            // --- COMMENTS ---
            async function openComments(slug, title) {
                document.getElementById('dashboard-view').style.display = 'none';
                document.getElementById('comments-section').style.display = 'block';
                document.getElementById('comments-title').innerText = 'دیدگاه‌های: ' + title;
                document.getElementById('comments-container').innerHTML = '<p>در حال بارگذاری...</p>';

                const res = await fetch('/api/comments/' + slug);
                const comments = await res.json();

                if (comments.length === 0) {
                    document.getElementById('comments-container').innerHTML = '<p>هیچ دیدگاهی برای این پست ثبت نشده است.</p>';
                    return;
                }

                let html = '';
                comments.forEach(c => {
                    const existingReply = c.adminResponse ? c.adminResponse.message : '';
                    const jalaliDate = toFa(new Date(c.date).toLocaleDateString('fa-IR'));

                    html += \`
                    <div class="comment-card" id="comment-\${c.filename.replace('.yml', '')}">
                        <h4>\${c.name} (\${jalaliDate})</h4>
                        <textarea id="msg-\${c.filename}" class="reply-textarea">\${c.message}</textarea>
                        <div class="reply-box">
                            <label>پاسخ شما:</label>
                            <textarea id="reply-\${c.filename}" class="reply-textarea" placeholder="پاسخ...">\${existingReply}</textarea><br>
                            <div class="comment-actions">
                                <button onclick="updateCommentData('\${c.filename}', event)">ثبت و ارسال</button>
                                <button class="btn-delete" onclick="deleteComment('\${c.filename}', event)">🗑️ حذف</button>
                            </div>
                        </div>
                    </div>
                    \`;
                });
                document.getElementById('comments-container').innerHTML = html;
            }

            async function updateCommentData(commentFilename, event) {
                const userMsgText = document.getElementById('msg-' + commentFilename).value;
                const replyText = document.getElementById('reply-' + commentFilename).value;
                if (!userMsgText.trim()) return;
                
                const btn = event.target;
                btn.innerText = 'در حال ارسال...';
                btn.disabled = true;

                const res = await fetch('/api/update-comment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: commentFilename, reply: replyText, userMessage: userMsgText })
                });

                if(res.ok) { btn.innerText = 'ثبت شد'; btn.disabled = false; } 
                else { alert('خطا'); btn.disabled = false; }
            }

            async function deleteComment(commentFilename, event) {
                if (!confirm('مطمئن هستید؟')) return;
                const btn = event.target;
                btn.innerText = 'در حال حذف...';
                btn.disabled = true;

                const res = await fetch('/api/delete-comment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: commentFilename })
                });

                if (res.ok) btn.closest('.comment-card').remove();
                else btn.disabled = false;
            }

            async function pullChanges() {
                const btn = document.querySelector('.btn-pull');
                const originalText = btn.innerText;
                btn.innerText = 'در حال دریافت...';
                btn.disabled = true;

                try {
                    const res = await fetch('/api/pull', { method: 'POST' });
                    if(res.ok) location.reload();
                    else alert('خطا: ' + await res.text());
                } catch (e) { alert('خطا در ارتباط با سرور.'); }
                
                btn.innerText = originalText;
                btn.disabled = false;
            }

            renderPostList();
        </script>
    </body>
    </html>
    `;
    res.send(html);
});

// 2. API: Image Upload Handler
app.post('/api/upload-image', upload.single('image'), async (req, res) => {
    try {
        if (!req.file) return res.status(400).send('هیچ عکسی ارسال نشده است.');
        
        const imagePath = `/images/${req.file.filename}`;
        
        await git.add(req.file.path);
        await git.commit(`Uploaded image: ${req.file.filename}`);
        await git.push();
        
        res.json({ url: imagePath });
    } catch (error) {
        console.error(error);
        res.status(500).send(error.message);
    }
});

// 3. API: Get JSON Post Data for Single Stage Form
app.get('/api/post/:filename', (req, res) => {
    const filePath = path.join(postsDir, req.params.filename);
    const content = fs.readFileSync(filePath, 'utf-8');
    const parsed = matter(content);
    
    res.json({
        title: parsed.data.title || '',
        tags: parsed.data.tags || [],
        heroImage: parsed.data.heroImage || '',
        body: parsed.content || '' 
    });
});

// 4. API: Fetch About Page Safely
app.get('/api/about', (req, res) => {
    const possiblePaths = [
        path.join('src', 'pages', 'about.astro'),
        path.join('src', 'pages', 'about.md'),
        path.join('src', 'pages', 'about', 'index.astro')
    ];

    for (let p of possiblePaths) {
        const fullPath = path.join(__dirname, p);
        if (fs.existsSync(fullPath)) {
            const content = fs.readFileSync(fullPath, 'utf8');
            return res.json({ content: content, filepath: p });
        }
    }
    
    res.status(404).send('About page not found');
});

// 5. API: Save About Page Safely
app.post('/api/save-about', async (req, res) => {
    const { filepath, content } = req.body;
    try {
        const fullPath = path.join(__dirname, filepath);
        fs.writeFileSync(fullPath, content, 'utf8');
        await git.add(fullPath);
        await git.commit(`Updated About page via local portal`);
        await git.push();
        res.sendStatus(200);
    } catch (error) {
        console.error(error);
        res.status(500).send(error.message);
    }
});

// 6. API: Save Post (Handles New, Updates, and Renames)
app.post('/api/save-post', async (req, res) => {
    const { originalFilename, newFilename, title, tags, heroImage, content } = req.body;
    
    try {
        let dateISO = new Date().toISOString();
        let pinned = false;
        
        if (originalFilename) {
            const oldPath = path.join(postsDir, originalFilename);
            if (fs.existsSync(oldPath)) {
                const oldContent = fs.readFileSync(oldPath, 'utf-8');
                const parsed = matter(oldContent);
                if (parsed.data.date) dateISO = parsed.data.date;
                if (parsed.data.pinned !== undefined) pinned = parsed.data.pinned;
                
                if (originalFilename !== newFilename) {
                    fs.unlinkSync(oldPath);
                    await git.rm(oldPath);
                }
            }
        }
        
        const newPath = path.join(postsDir, newFilename);
        
        let mdContent = `---
title: "${title}"
date: "${dateISO}"
jalaliDate: ""
`;
        if (heroImage && heroImage.trim() !== '') {
            mdContent += `heroImage: "${heroImage.trim()}"\n`;
        }

        mdContent += `tags: ${JSON.stringify(tags)}
pinned: ${pinned}
---

${content}
`;
        
        fs.writeFileSync(newPath, mdContent, 'utf-8');
        await git.add(newPath);
        await git.commit(`Update post ${newFilename} via local portal`);
        await git.push(); 
        
        res.sendStatus(200);
    } catch (error) {
        console.error(error);
        res.status(500).send(error.message);
    }
});

// 7. API: Delete Post
app.post('/api/delete-post', async (req, res) => {
    const { filename } = req.body;
    const filePath = path.join(postsDir, filename);
    try {
        if (fs.existsSync(filePath)) {
            fs.unlinkSync(filePath);
            await git.add(filePath);
            await git.commit(`Deleted post ${filename} via local portal`);
            await git.push();
            res.sendStatus(200);
        } else res.status(404).send('Not found');
    } catch (error) { res.status(500).send(error.message); }
});

// 8. API: Comments List
app.get('/api/comments/:slug', (req, res) => {
    const slug = req.params.slug;
    const results = [];
    if (fs.existsSync(commentsDir)) {
        const files = fs.readdirSync(commentsDir).filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));
        for(const file of files) {
            try {
                const content = fs.readFileSync(path.join(commentsDir, file), 'utf8');
                const parsed = yaml.load(content);
                if(parsed.postSlug === slug) results.push({ filename: file, ...parsed });
            } catch (e) {}
        }
    }
    results.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    res.json(results);
});

// 9. API: Update Comment
app.post('/api/update-comment', async (req, res) => {
    const { filename, reply, userMessage } = req.body;
    const filepath = path.join(commentsDir, filename);
    try {
        const parsed = yaml.load(fs.readFileSync(filepath, 'utf8'));
        parsed.message = userMessage;
        
        if (reply && reply.trim() !== '') {
            parsed.adminResponse = {
                date: parsed.adminResponse ? parsed.adminResponse.date : new Date().toISOString(),
                message: reply
            };
        } else { delete parsed.adminResponse; }
        
        fs.writeFileSync(filepath, yaml.dump(parsed), 'utf8');
        await git.add(filepath);
        await git.commit(`Moderated comment ${filename}`);
        await git.push();
        res.sendStatus(200);
    } catch (error) { res.status(500).send(error.message); }
});

// 10. API: Delete Comment
app.post('/api/delete-comment', async (req, res) => {
    const { filename } = req.body;
    const filepath = path.join(commentsDir, filename);
    try {
        if (fs.existsSync(filepath)) {
            fs.unlinkSync(filepath);
            await git.add(filepath);
            await git.commit(`Deleted comment ${filename}`);
            await git.push();
            res.sendStatus(200);
        } else res.status(404).send('Not found');
    } catch (error) { res.status(500).send(error.message); }
});

// 11. API: Git Pull
app.post('/api/pull', async (req, res) => {
    try { await git.pull(); res.sendStatus(200); } 
    catch (error) { res.status(500).send(error.message); }
});

app.listen(PORT, () => {
    console.log(`✅ Portal running! Open http://localhost:${PORT} in your browser.`);
});