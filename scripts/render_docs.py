"""Render markdown docs to standalone HTML files for demo viewing.

Each input .md becomes a self-contained .html that the user can open in
the browser without any server. Mermaid diagrams render via mermaid.js
from CDN; code blocks are syntax-highlighted by Pygments at build time
(no JS dependency for highlighting); tables, blockquotes, headers all
get GitHub-style typography.

Usage: python scripts/render_docs.py

Outputs to docs/html/ — one .html per source .md, plus an index.html that
links them all.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    print("Run: backend/venv/Scripts/python.exe -m pip install markdown pygments", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "html"

# (source path relative to REPO_ROOT, output filename, short title)
SOURCES = [
    ("README.md",                "index.html",         "README"),
    ("docs/architecture.md",     "architecture.html",  "Architecture"),
    ("docs/tuning_results.md",   "tuning_results.html","Tuning Results (26 configs)"),
    ("docs/blog_post.md",        "blog_post.html",     "Blog Post"),
    ("docs/demo_script.md",      "demo_script.html",   "Demo Script"),
    ("docs/submission_assets.md","submission_assets.html","Submission Assets"),
    ("docs/RECORDING_SCRIPT.md", "recording_script.html","🎬 Recording Script (read-along)"),
]


CSS = r"""
:root {
  --bg: #0d1117;
  --bg-elev: #161b22;
  --bg-code: #1f242c;
  --text: #e6edf3;
  --text-dim: #8b949e;
  --accent: #f97316;   /* rust */
  --accent-emerald: #34d399;
  --accent-amber: #fbbf24;
  --border: #30363d;
  --border-strong: #484f58;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  line-height: 1.6; font-size: 16px; }
body { display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }
nav.sidebar {
  background: var(--bg-elev); border-right: 1px solid var(--border);
  padding: 24px 16px; position: sticky; top: 0; height: 100vh; overflow-y: auto;
}
nav.sidebar h2 { font-size: 0.78rem; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--text-dim); margin: 0 0 12px;
}
nav.sidebar a { display: block; padding: 7px 10px; color: var(--text);
  text-decoration: none; border-radius: 6px; font-size: 0.9rem; margin: 2px 0;
}
nav.sidebar a:hover { background: var(--bg-code); color: var(--accent); }
nav.sidebar a.active { background: var(--accent); color: #fff; font-weight: 600; }
nav.sidebar .meta { color: var(--text-dim); font-size: 0.72rem;
  border-top: 1px solid var(--border); margin-top: 18px; padding-top: 14px;
}
main { padding: 36px 56px; max-width: 980px; }
h1, h2, h3, h4 { color: var(--text); margin-top: 1.5em; margin-bottom: 0.6em;
  font-weight: 700; line-height: 1.25; }
h1 { font-size: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 0.3em; margin-top: 0; }
h2 { font-size: 1.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25em; }
h3 { font-size: 1.18rem; color: var(--accent); }
h4 { font-size: 1.05rem; color: var(--text-dim); }
p { margin: 0.7em 0; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
strong { color: var(--text); font-weight: 700; }
em { color: var(--text); }
hr { border: none; border-top: 1px solid var(--border); margin: 2em 0; }
ul, ol { padding-left: 1.8em; margin: 0.7em 0; }
li { margin: 0.25em 0; }
blockquote { border-left: 3px solid var(--accent); margin: 1em 0;
  padding: 0.3em 1em; color: var(--text-dim); background: var(--bg-elev);
  border-radius: 0 6px 6px 0;
}
code { background: var(--bg-code); padding: 0.18em 0.4em; border-radius: 4px;
  font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.86em;
  color: #ffa657; border: 1px solid var(--border);
}
pre { background: var(--bg-code); border: 1px solid var(--border);
  border-radius: 8px; padding: 14px 18px; overflow-x: auto; line-height: 1.5;
  font-size: 0.85em;
}
pre code { background: transparent; padding: 0; border: 0; color: var(--text); }
table { border-collapse: collapse; margin: 1em 0; width: 100%;
  background: var(--bg-elev); border-radius: 8px; overflow: hidden;
  border: 1px solid var(--border);
}
th, td { padding: 8px 12px; text-align: left; border: 1px solid var(--border); }
th { background: var(--bg-code); color: var(--text); font-weight: 700;
  font-size: 0.88em; text-transform: uppercase; letter-spacing: 0.03em;
}
tr:nth-child(even) td { background: rgba(255,255,255,0.015); }
/* Mermaid container */
.mermaid { background: var(--bg-elev); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px; margin: 1em 0; text-align: center;
}
/* Pygments code highlight (subset of monokai) */
.codehilite .k, .codehilite .kn, .codehilite .kd { color: #ff7b72; }
.codehilite .s, .codehilite .s1, .codehilite .s2 { color: #a5d6ff; }
.codehilite .c, .codehilite .c1 { color: #8b949e; font-style: italic; }
.codehilite .nb { color: #d2a8ff; }
.codehilite .nf, .codehilite .nc { color: #d2a8ff; }
.codehilite .o { color: #ff7b72; }
.codehilite .mi, .codehilite .mf { color: #79c0ff; }
.codehilite .bp { color: #ff7b72; }
/* Top banner */
.banner { background: linear-gradient(90deg,
    rgba(52,211,153,0.10) 0%,
    rgba(251,191,36,0.10) 100%);
  border: 1px solid var(--border-strong);
  border-radius: 8px; padding: 14px 18px; margin-bottom: 28px;
  font-size: 0.92rem;
}
.banner b { color: var(--accent-amber); }
@media (max-width: 900px) {
  body { grid-template-columns: 1fr; }
  nav.sidebar { position: relative; height: auto; }
  main { padding: 24px; }
}
"""


def _build_nav_html(active_filename: str) -> str:
    """Sidebar HTML — active link highlighted."""
    links = []
    for _src, out, title in SOURCES:
        cls = ' class="active"' if out == active_filename else ''
        links.append(f'<a href="{out}"{cls}>{title}</a>')
    nav = (
        '<nav class="sidebar">'
        '<h2>Demo Docs</h2>'
        + '\n'.join(links) +
        '<div class="meta">'
        '<div>Repo: <a href="https://github.com/Nilanshjain/DevRAG" target="_blank">github.com/Nilanshjain/DevRAG</a></div>'
        '<div style="margin-top:6px;">Token Comparison Across Three RAG Pipelines</div>'
        '</div>'
        '</nav>'
    )
    return nav


_MERMAID_PLACEHOLDER = "@@MERMAID_BLOCK_{i}@@"
_MERMAID_FENCE_RE = re.compile(r"```mermaid\n(.*?)\n```", re.DOTALL)


def _extract_mermaid_blocks(md_text: str) -> tuple[str, list[str]]:
    """Pull ```mermaid``` blocks out of the markdown BEFORE running it through
    markdown.convert() — otherwise the codehilite extension wraps them in
    <div class="codehilite"><pre><span></span><code>...</code></pre></div>
    which mermaid.js can't render. We replace each block with a placeholder
    that survives markdown processing, then swap the placeholders for
    <div class="mermaid"> wrappers afterwards.
    """
    blocks: list[str] = []

    def grab(match):
        idx = len(blocks)
        blocks.append(match.group(1))
        return _MERMAID_PLACEHOLDER.format(i=idx)

    new_md = _MERMAID_FENCE_RE.sub(grab, md_text)
    return new_md, blocks


def _reinsert_mermaid_blocks(html: str, blocks: list[str]) -> str:
    """Replace placeholders with <div class="mermaid"> blocks for mermaid.js."""
    for i, body in enumerate(blocks):
        # Markdown wraps stray text in <p>...</p> sometimes; placeholder may
        # appear inside a paragraph. Match both bare and paragraph-wrapped.
        placeholder = _MERMAID_PLACEHOLDER.format(i=i)
        rendered = f'<div class="mermaid">\n{body}\n</div>'
        html = html.replace(f"<p>{placeholder}</p>", rendered)
        html = html.replace(placeholder, rendered)
    return html


def _convert_md_to_body(md_text: str) -> str:
    """Markdown → HTML body, with ```mermaid``` blocks correctly preserved."""
    md_no_mermaid, mermaid_blocks = _extract_mermaid_blocks(md_text)
    md = markdown.Markdown(
        extensions=[
            'fenced_code',
            'tables',
            'codehilite',
            'toc',
            'attr_list',
            'sane_lists',
        ],
        extension_configs={
            'codehilite': {'guess_lang': False, 'linenums': False, 'noclasses': False},
        },
    )
    html_body = md.convert(md_no_mermaid)
    return _reinsert_mermaid_blocks(html_body, mermaid_blocks)


def _wrap_in_template(body_html: str, title: str, active_filename: str) -> str:
    nav_html = _build_nav_html(active_filename)
    banner = (
        '<div class="banner">'
        '<div style="margin-bottom: 6px;">'
        '<b>Two distinct hackathon wins from the same codebase</b>, selectable via the <code>adaptive_fallback</code> flag:'
        '</div>'
        '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.88rem;">'
        '<div style="border-left: 3px solid var(--accent-emerald); padding-left: 10px;">'
        '🥇 <b>Token Reduction (headline rubric)</b><br>'
        'Default config — <code>805 tok/q</code> vs Basic RAG <code>1,407</code> = <b>−42.8% tokens</b> with <b>+7.1pp</b> judge accuracy.<br>'
        '<span style="color: var(--text-dim); font-size: 0.85em;">Single LLM call, community-summary retrieval. File: <code>accuracy_results_C11_FINAL.json</code></span>'
        '</div>'
        '<div style="border-left: 3px solid var(--accent-amber); padding-left: 10px;">'
        '🏆 <b>Maximum Bonus Tier</b><br>'
        'Adaptive config — <code>judge 92.9%</code> AND <code>F1_raw 0.891</code> in the <b>same eval run</b>. Bonus thresholds: ≥90% / ≥0.88.<br>'
        '<span style="color: var(--text-dim); font-size: 0.85em;">Adds 2-hop graph traversal + answer-trim + judge consensus N=3. File: <code>accuracy_results_C26_FINAL.json</code></span>'
        '</div>'
        '</div>'
        '<div style="margin-top: 8px; font-size: 0.8rem; color: var(--text-dim);">'
        'Two configs, two rubrics. The Adaptive config uses ~3× the tokens of the Default — by design — to buy the accuracy needed for the bonus tier on multi-hop questions.'
        '</div>'
        '</div>'
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Token Comparison Across Three RAG Pipelines</title>
<style>{CSS}</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  document.addEventListener('DOMContentLoaded', function() {{
    if (window.mermaid) {{
      mermaid.initialize({{
        startOnLoad: true,
        theme: 'dark',
        themeVariables: {{
          background: '#161b22',
          primaryColor: '#1f242c',
          primaryTextColor: '#e6edf3',
          primaryBorderColor: '#484f58',
          lineColor: '#8b949e',
          secondaryColor: '#1f242c',
          tertiaryColor: '#0d1117',
        }},
      }});
    }}
  }});
</script>
</head>
<body>
{nav_html}
<main>
{banner}
{body_html}
</main>
</body>
</html>"""


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rendered = []
    for src_rel, out_filename, title in SOURCES:
        src_path = REPO_ROOT / src_rel
        if not src_path.exists():
            print(f"  skip (missing): {src_rel}", file=sys.stderr)
            continue
        md_text = src_path.read_text(encoding="utf-8")
        body_html = _convert_md_to_body(md_text)
        full_html = _wrap_in_template(body_html, title, out_filename)
        out_path = OUTPUT_DIR / out_filename
        out_path.write_text(full_html, encoding="utf-8")
        rendered.append(out_filename)
        size_kb = out_path.stat().st_size / 1024
        print(f"  rendered: {src_rel:42s} -> docs/html/{out_filename}  ({size_kb:.0f} KB)")
    print(f"\nDone. Open: file:///{(OUTPUT_DIR / 'index.html').as_posix()}")


if __name__ == "__main__":
    main()
