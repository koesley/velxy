"""GENESIS FORGE: accessible, escaped, read-only HTML preview rendering.

The preview is a visual specification, not a live application. Never embeds
untrusted scripts, URLs, arbitrary markup, or external resources.
"""
import html
from genesis_forge_v1 import validate_manifest

_CSS = """
:root{font-family:system-ui,sans-serif;color-scheme:light}
body{margin:0;background:#f5f7fb;color:#172033}
main{max-width:1080px;margin:0 auto;padding:32px 20px}
header{margin-bottom:24px}h1{margin:0 0 8px;font-size:2rem}
p{line-height:1.5}.muted{color:#526079}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.panel{border:1px solid #dce2eb;border-radius:14px;padding:20px;background:white}
.panel h2{font-size:1.1rem;margin:0 0 8px}
.tag{display:inline-block;border-radius:8px;background:#e7eefc;padding:5px 9px}
.notice{padding:14px;border-left:4px solid #365acb;background:#e7eefc;margin-bottom:20px}
ul{padding-left:20px}li{margin:8px 0}
"""


def render_preview(manifest, workspace_id):
    """Render an inert, escaped preview after validating tenant and manifest."""
    validate_manifest(manifest, workspace_id)
    title = html.escape(manifest["name"], quote=True)
    industry = html.escape(manifest["industry"].title(), quote=True)
    blocks = []
    for block in manifest["components"]:
        label = html.escape(block["label"], quote=True)
        component_type = html.escape(block["type"], quote=True)
        permissions = "".join(
            "<li><code>" + html.escape(permission, quote=True) + "</code></li>"
            for permission in block["permissions"]
        )
        blocks.append(
            '<section class="panel" aria-label="' + label + '">'
            '<h2>' + label + '</h2>'
            '<p class="muted">Component: <code>' + component_type + '</code></p>'
            '<p>Required access:</p><ul>' + permissions + '</ul>'
            '<p class="tag">Preview only — no live data</p></section>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
        '<title>' + title + ' — Genesis Forge Preview</title>'
        '<style>' + _CSS + '</style></head><body><main>'
        '<header><p class="muted">VELXTRIA / GENESIS FORGE</p>'
        '<h1>' + title + '</h1><p class="muted">Industry: ' + industry + '</p></header>'
        '<div class="notice" role="status"><strong>Design preview.</strong> '
        'This is not a deployed application. No records are loaded, changed, '
        'or sent to external services.</div>'
        '<div class="grid">' + "".join(blocks) + '</div>'
        '</main></body></html>'
    )
