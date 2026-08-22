import json
from pathlib import Path

p = Path(__file__).with_name("CET313_Artificial_Intelligence_Prototype (1).ipynb")
out = Path(__file__).with_name("_nb_extract")
out.mkdir(exist_ok=True)
nb = json.loads(p.read_text(encoding="utf-8"))
print("cells", len(nb["cells"]))
needles = ["KMeans", "agreement", "GroupKFold", "water_score", "spatial block", "KFold"]
for i, c in enumerate(nb["cells"]):
    src = "".join(c.get("source", []))
    hit = [k for k in needles if k.lower() in src.lower()]
    if hit:
        fname = f"cell_{i:03d}_{c['cell_type']}.txt"
        (out / fname).write_text(src, encoding="utf-8")
        print(i, c["cell_type"], hit, len(src))
