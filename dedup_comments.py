import os
import re
import yaml
import argparse

def str_presenter(dumper, data):
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

def normalize_text(text):
    if not text: return ""
    return re.sub(r'[\s.,!؟،؛:]+', '', str(text))

def calculate_score(comment):
    score = 0
    name = str(comment.get('name') or '')
    date_str = str(comment.get('date') or '')

    if name and name not in ['ناشناس', 'Anonymous', 'پاسخ:']:
        score += 10
    if 'adminResponse' in comment:
        score += 20
    if '1970' not in date_str and '2020-01-01' not in date_str:
        score += 5
        
    return score

def main():
    parser = argparse.ArgumentParser(description="Smart deduplicate YAML comments.")
    parser.add_argument("source_dir", help="Folder containing raw scraped comments.")
    parser.add_argument("target_dir", help="Folder to save the clean, unique comments.")
    args = parser.parse_args()

    os.makedirs(args.target_dir, exist_ok=True)

    best_comments = {}
    total_files = 0
    skipped_orphans = 0

    print(f"🔍 Scanning '{args.source_dir}' for duplicates...")

    for filename in os.listdir(args.source_dir):
        if not filename.endswith(('.yml', '.yaml')):
            continue

        total_files += 1
        filepath = os.path.join(args.source_dir, filename)

        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                comment_data = yaml.safe_load(f)
            except Exception as e:
                print(f"  [!] Error reading {filename}: {e}")
                continue

        if not comment_data:
            continue

        name = str(comment_data.get('name') or '').strip()
        message = str(comment_data.get('message') or '')
        post_slug = str(comment_data.get('postSlug') or '')

        # Core Fix: If the old scraper caught a standalone admin reply, toss it out.
        if name == 'پاسخ:':
            skipped_orphans += 1
            continue

        normalized_msg = normalize_text(message)
        if not normalized_msg:
            continue
            
        fingerprint = f"{post_slug}|{normalized_msg[:60]}"
        current_score = calculate_score(comment_data)

        if fingerprint not in best_comments:
            best_comments[fingerprint] = (current_score, comment_data, filename)
        else:
            existing_score = best_comments[fingerprint][0]
            if current_score > existing_score:
                best_comments[fingerprint] = (current_score, comment_data, filename)

    for score, data, original_filename in best_comments.values():
        target_filepath = os.path.join(args.target_dir, original_filename)
        with open(target_filepath, 'w', encoding='utf-8') as out_f:
            yaml.safe_dump(data, out_f, allow_unicode=True, sort_keys=False)

    final_count = len(best_comments)
    duplicates_removed = total_files - final_count - skipped_orphans

    print("\n✅ Clean-up complete!")
    print(f"Total files scanned:    {total_files}")
    print(f"Orphan replies deleted: {skipped_orphans}")
    print(f"Duplicates removed:     {duplicates_removed}")
    print(f"Unique files saved:     {final_count}")
    print(f"📂 Check your '{args.target_dir}' folder.")

if __name__ == "__main__":
    main()