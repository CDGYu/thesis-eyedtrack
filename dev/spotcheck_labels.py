"""Generate a self-contained HTML contact sheet for human label spot-checking.

Usage: py -3.14 dev/spotcheck_labels.py [--dataset-dir P] [--out HTML]
       [--per-class 50]

Open the HTML in a browser, tick every image whose folder label looks WRONG,
click "Export flags" — it downloads spotcheck_flags.csv. Put that file at
dataset/spotcheck_flags.csv; calibrate/evaluate exclude the flagged rows.
"""
import argparse
import base64
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calib_common as cc

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>EyedTrack label spot-check</title>
<style>
 body {{ font-family: sans-serif; margin: 16px; }}
 .grid {{ display: flex; flex-wrap: wrap; gap: 8px; }}
 figure {{ margin: 0; width: 180px; }}
 img {{ width: 180px; display: block; }}
 figcaption {{ font-size: 11px; word-break: break-all; }}
 label.bad {{ color: #b00; font-weight: bold; }}
 #export {{ position: fixed; top: 8px; right: 8px; padding: 8px 14px; }}
</style></head><body>
<h1>Label spot-check — tick images whose label is WRONG</h1>
<button id="export" onclick="exportFlags()">Export flags</button>
{sections}
<script>
function exportFlags() {{
  var rows = ["relpath"];
  document.querySelectorAll("input[type=checkbox]:checked").forEach(function(c) {{
    rows.push(c.dataset.relpath);
  }});
  var blob = new Blob([rows.join("\\n") + "\\n"], {{type: "text/csv"}});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "spotcheck_flags.csv";
  a.click();
}}
</script></body></html>
"""


def _figure(relpath, abspath):
    b64 = base64.b64encode(Path(abspath).read_bytes()).decode("ascii")
    escaped_relpath = html.escape(relpath, quote=True)
    return (f'<figure><img src="data:image/jpeg;base64,{b64}">'
            f'<figcaption>{escaped_relpath}</figcaption>'
            f'<label class="bad"><input type="checkbox" data-relpath="{escaped_relpath}">'
            f' wrong label</label></figure>')


def build_html(dataset_dir, per_class):
    dataset_dir = Path(dataset_dir)
    sections = []
    for class_dir in cc.CLASS_DIRS:
        figures = []
        for split in ("train", "test"):
            d = dataset_dir / split / class_dir
            if not d.is_dir():
                continue
            names = [p.name for p in d.iterdir()
                     if p.suffix.lower() in cc.IMAGE_EXTS]
            for name in cc.every_nth(names, per_class):
                relpath = f"{split}/{class_dir}/{name}"
                figures.append(_figure(relpath, d / name))
        sections.append(f"<h2>{class_dir} ({len(figures)} sampled)</h2>"
                        f'<div class="grid">{"".join(figures)}</div>')
    return _PAGE.format(sections="\n".join(sections))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", default=str(cc.DATASET_DIR))
    ap.add_argument("--out", default=str(cc.DATASET_DIR / "spotcheck.html"))
    ap.add_argument("--per-class", type=int, default=50)
    args = ap.parse_args(argv)
    html = build_html(args.dataset_dir, args.per_class)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} — open in a browser, tick wrong labels, Export flags,"
          f" save as {cc.DATASET_DIR / 'spotcheck_flags.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
