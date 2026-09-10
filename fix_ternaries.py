import sys

def fix():
    with open('src/map/mapController.js', 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace('score >= 0.7  "high" : score >= 0.45  "medium" : "low"', 'score >= 0.7 ? "high" : score >= 0.45 ? "medium" : "low"')
    content = content.replace('slopePoints.length  slopePoints : points', 'slopePoints.length ? slopePoints : points')
    content = content.replace('bPoints.length  bPoints : points', 'bPoints.length ? bPoints : points')

    with open('src/map/mapController.js', 'w', encoding='utf-8') as f:
        f.write(content)

fix()
