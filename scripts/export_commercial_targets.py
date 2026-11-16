import os
import sys
import json
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.main import analyze_point, PointRadiusRequest

# Output path to update public frontend assets
EXPORT_TARGETS_PATH = r"C:\Users\pc\Desktop\Landsat-Water Current\data\exports\ranked_drill_targets.json"
PUBLIC_TARGETS_PATH = r"C:\Users\pc\Desktop\Landsat-Water Current\public\data\exports\ranked_drill_targets.json"

async def export_targets():
    print("Generating commercial drill targets via Two-Stage API...")
    # Target center in Southern Africa hard-rock / Karoo boundary
    req = PointRadiusRequest(latitude=-21.7439, longitude=28.0716, radius_km=50.0)
    res = await analyze_point(req)
    
    data = res.model_dump()
    targets = data.get("top_recommended_drill_targets", [])
    
    # Save to data/exports and public/data/exports
    os.makedirs(os.path.dirname(EXPORT_TARGETS_PATH), exist_ok=True)
    with open(EXPORT_TARGETS_PATH, "w", encoding="utf-8") as f:
        json.dump(targets, f, indent=2)
    print(f"Saved: {EXPORT_TARGETS_PATH}")
    
    if os.path.exists(os.path.dirname(PUBLIC_TARGETS_PATH)):
        with open(PUBLIC_TARGETS_PATH, "w", encoding="utf-8") as f:
            json.dump(targets, f, indent=2)
        print(f"Saved: {PUBLIC_TARGETS_PATH}")

if __name__ == "__main__":
    asyncio.run(export_targets())
