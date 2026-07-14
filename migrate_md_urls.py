import os
import re
import sys

# Ensure correct number of arguments are provided
if len(sys.argv) != 3:
    print("Usage: python migrate.py <source_folder> <destination_folder>")
    print("Example: python migrate.py src/content/blog src/content/blog-new")
    sys.exit(1)

src_dir = sys.argv[1]
dest_dir = sys.argv[2]

# Verify source directory exists
if not os.path.exists(src_dir):
    print(f"Error: Source directory '{src_dir}' does not exist.")
    sys.exit(1)

# Create destination directory if it doesn't exist
os.makedirs(dest_dir, exist_ok=True)

# Regex to capture the slug after the date
blog_ir_regex = re.compile(r'https?://delsharm\.blog\.ir/\d{4}/\d{2}/\d{2}/([^\s"\'()]+)')

processed_count = 0

for filename in os.listdir(src_dir):
    if filename.endswith('.md') or filename.endswith('.mdx'):
        src_path = os.path.join(src_dir, filename)
        dest_path = os.path.join(dest_dir, filename)
        
        with open(src_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Replace the matched URLs with the new GitHub Pages format
        # \g<1> refers to the captured slug from the regex group
        new_content = blog_ir_regex.sub(r'https://rasoolims.github.io/delsharm/blog/\g<1>', content)
        
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        processed_count += 1

print(f"\n✅ Migration complete! Processed {processed_count} files.")
print(f"📂 Check the new files in: {dest_dir}")