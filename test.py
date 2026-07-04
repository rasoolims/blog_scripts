import re

def test_full_conversion(content_text):
    print(f"--- Original: {content_text}")
    
    # Normalization
    text = re.sub(r'[\u200c\u200b\s]+', ' ', content_text)
    text = re.sub(r'([آ-ی])(\d{4})', r'\1 \2', text)
    text = re.sub(r'(\d{1,2})([آ-ی])', r'\1 \2', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    print(f"--- Normalized: {text}")
    
    # Conversion Logic
    months = {
        'فروردین': 1, 'اردیبهشت': 2, 'خرداد': 3, 'تیر': 4, 'مرداد': 5, 'شهریور': 6,
        'مهر': 7, 'آبان': 8, 'آذر': 9, 'دی': 10, 'بهمن': 11, 'اسفند': 12
    }
    
    pattern = r'(\d{1,2})\s+([آ-ی]+)\s+(\d{4})'
    match = re.search(pattern, text)
    
    if match:
        print(f"--- Found Match: {match.group(0)}")
        try:
            day = int(match.group(1))
            month = months.get(match.group(2), 1)
            year = int(match.group(3)) + 621
            gregorian = f"{year}-{month:02d}-{day:02d} 00:00:00"
            print(f"--- Result: {gregorian}")
        except Exception as e:
            print(f"--- Error during conversion: {e}")
    else:
        print("--- ❌ Regex failed to match!")

test_string = "سه شنبه 20 مرداد1388ساعت 11:12 بعد از ظهر توسط محمدصادق رسولی"
test_full_conversion(test_string)