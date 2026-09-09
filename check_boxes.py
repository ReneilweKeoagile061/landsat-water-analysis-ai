import re
with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()
matches = re.findall(r'<input type=\"checkbox\"[^>]*>', html)
for m in matches:
    print(m)
