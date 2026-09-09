import re

def fix_index():
    with open('index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # Remove checked attribute from checkboxes to avoid map clutter on load
    html = re.sub(r'(<input type=\"checkbox\"[^>]*?) checked', r'\1', html)

    # Rename AgriPulse
    html = html.replace('AgriPulse ML & Boreholes', 'Borehole Data & Analytics')
    html = html.replace('AgriPulse ML', 'Borehole Analytics')
    html = html.replace('Agripulse', 'Platform')
    html = html.replace('AgriPulse', 'Platform')

    # Remove Emojis
    # Common emojis used in the previous code based on observation:
    emojis = ['??', '??', '??', '??', '??', '?', '??', '??', '??', '??', '??', '?', '??', '??', '??', '???']
    for e in emojis:
        html = html.replace(e, '')

    # Simplify the right panel by hiding technical ML metrics
    # The user said "that right panel has too much clutter... keep what is needed on the dahboard there and whats not needed only in the backened"
    # I'll hide "Model Validation Metrics" and "BGI Training Database Status" cards from the frontend.
    html = re.sub(r'(<div class=\"info-card\">\s*<p class=\"info-label\">Model Validation Metrics</p>.*?</div>)', r'<!-- \1 -->', html, flags=re.DOTALL)
    html = re.sub(r'(<div class=\"info-card\">\s*<p class=\"info-label\">Spatial block CV</p>.*?</div>)', r'<!-- \1 -->', html, flags=re.DOTALL)
    html = re.sub(r'(<div class=\"info-card\">\s*<p class=\"info-label\">Per-class F1</p>.*?</div>)', r'<!-- \1 -->', html, flags=re.DOTALL)
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)

def fix_js():
    for f_name in ['src/ui/dashboard.js', 'src/map/mapController.js', 'src/main.js']:
        try:
            with open(f_name, 'r', encoding='utf-8') as f:
                content = f.read()
                
            emojis = ['??', '??', '??', '??', '??', '?', '??', '??', '??', '??', '??', '?', '??', '??', '??', '???', '??', '??', '?', '??', '???']
            for e in emojis:
                content = content.replace(e, '')
            content = content.replace('AgriPulse', 'Platform')
            content = content.replace('Agripulse', 'Platform')
            
            with open(f_name, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"Skipping {f_name}: {e}")

fix_index()
fix_js()
print("Fixed files")
