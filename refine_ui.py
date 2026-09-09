import re

def refine_html():
    with open('index.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # Regex to catch emojis
    emoji_pattern = re.compile(
        r'[\U00010000-\U0010ffff]'
        r'|[\u2600-\u27BF]'
        r'|[\u2300-\u23FF]'
        r'|[\u25A0-\u25FF]'
        r'|[\u2B50]'
    )
    html = emoji_pattern.sub('', html)

    # Remove checked from all checkboxes
    html = re.sub(r'(\s+)checked(\s*/?>)', r'\2', html)

    # Rename and remove AgriPulse
    html = html.replace('AgriPulse ML & Boreholes', 'Borehole Analytics')
    html = html.replace('AgriPulse ML', 'Borehole Analytics')
    html = html.replace('AgriPulse', '')
    html = html.replace('Agripulse', '')

    # Simplify the right panel by dropping bulky/tech-heavy cards
    html = re.sub(r'<div class="info-card">\s*<p class="info-label">Model Validation Metrics</p>.*?</div>', '', html, flags=re.DOTALL)
    html = re.sub(r'<div class="info-card">\s*<p class="info-label">BGI Training Database Status</p>.*?</div>', '', html, flags=re.DOTALL)
    # The user complained about the right panel clutter. 
    # Let's remove the "Top Predictive Features" as well
    html = re.sub(r'<div class="info-card">\s*<p class="info-label">Top Predictive Features</p>.*?</div>', '', html, flags=re.DOTALL)
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html)

def refine_js():
    for fname in ['src/ui/dashboard.js', 'src/map/mapController.js', 'src/main.js']:
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                content = f.read()
            
            emoji_pattern = re.compile(
                r'[\U00010000-\U0010ffff]'
                r'|[\u2600-\u27BF]'
                r'|[\u2300-\u23FF]'
                r'|[\u25A0-\u25FF]'
                r'|[\u2B50]'
            )
            content = emoji_pattern.sub('', content)

            content = content.replace('AgriPulse', 'Platform')
            content = content.replace('Agripulse', 'Platform')

            with open(fname, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            pass

def refine_css():
    try:
        with open('styles.css', 'r', encoding='utf-8') as f:
            css = f.read()
        emoji_pattern = re.compile(
            r'[\U00010000-\U0010ffff]'
            r'|[\u2600-\u27BF]'
            r'|[\u2300-\u23FF]'
            r'|[\u25A0-\u25FF]'
            r'|[\u2B50]'
        )
        css = emoji_pattern.sub('', css)
        with open('styles.css', 'w', encoding='utf-8') as f:
            f.write(css)
    except:
        pass

refine_html()
refine_js()
refine_css()
print("Refinement done")
