#!/usr/bin/env python3
"""Generate HTML gallery from fetched tweet data."""

import argparse, json, os, html, re, glob

def make_html_text(text):
    t = html.escape(text)
    t = re.sub(r'(https?://[^\s<]+)', r'<a href="\1" target="_blank">\1</a>', t)
    t = t.replace('\n', '<br>')
    return t

def has_prompt(text):
    keywords = ["prompt", "提示词", "negative", "checkpoint", "lora",
                "masterpiece", "best quality", "8k", "4k", "hyper",
                "cinematic", "studio", "lighting", "bokeh", "depth of field",
                "photorealistic", "realistic", "flux", "sdxl", "midjourney",
                "gpt image", "grok", "imagine", "shot on", "mm lens",
                "create a", "generate a", "ultra-", "detailed"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)

def generate_gallery(posts, output_path, select_mode=False):
    total_images = sum(len(p.get("images", [])) for p in posts)

    # CSS
    css = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0a0a0a; color: #e7e7e7; }
.header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 24px 30px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; }
.header h1 { font-size: 24px; color: #fff; }
.header .stats { color: #888; font-size: 13px; }
.container { max-width: 100%; margin: 0 auto; padding: 16px; }
.post { display: flex; gap: 16px; background: #141414; border: 1px solid #222; border-radius: 12px; margin-bottom: 16px; overflow: visible; transition: all 0.3s; position: relative; }
.post:hover { border-color: #444; }
.post.rejected { opacity: 0.35; border-color: #555; }
.post.rejected::after { content: '✗ 不保留'; position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-size: 32px; color: #ff4444; font-weight: bold; z-index: 10; text-shadow: 0 2px 8px rgba(0,0,0,0.8); }
.post.selected { border-color: #4ade80; box-shadow: 0 0 12px rgba(74,222,128,0.2); }
.post.selected::before { content: '✓'; position: absolute; top: 10px; right: 10px; background: #4ade80; color: #000; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; z-index: 10; }
.post-text { flex: 0 0 220px; min-width: 220px; padding: 20px; overflow-y: auto; max-height: 800px; }
.post-text .author { font-weight: 600; color: #fff; margin-bottom: 4px; font-size: 15px; }
.post-text .handle { color: #666; font-size: 13px; margin-bottom: 12px; }
.post-text .content { font-size: 14px; line-height: 1.7; color: #ccc; word-break: break-word; }
.post-text .content a { color: #7b8cde; text-decoration: none; }
.post-text .content a:hover { text-decoration: underline; }
.post-text .meta { margin-top: 12px; display: flex; gap: 16px; color: #666; font-size: 12px; }
.post-text .meta span { display: flex; align-items: center; gap: 4px; }
.post-images { flex: 1; display: flex; flex-wrap: wrap; gap: 4px; padding: 4px; align-items: flex-start; }
.post-images img { height: auto; object-fit: contain; cursor: pointer; border-radius: 4px; transition: transform 0.2s; }
.post-images img:hover { transform: scale(1.02); }
.post-images img.single { max-width: 500px; width: auto; }
.post-images img.pair { max-width: 48%; width: auto; }
.post-images img.quad { max-width: 48%; width: auto; }
.post-images.no-images { display: none; }
.no-img-placeholder { flex: 1; display: flex; align-items: center; justify-content: center; color: #444; font-size: 14px; padding: 40px; text-align: center; }
@media (max-width: 900px) {
  .post { flex-direction: column; }
  .post-text { flex: none; max-height: none; min-width: auto; }
  .post-images img.single, .post-images img.pair, .post-images img.quad { max-width: 100%; }
}
/* Lightbox */
.lightbox { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.95); z-index: 1000; align-items: center; justify-content: center; cursor: pointer; }
.lightbox.active { display: flex; }
.lightbox img { max-width: 95%; max-height: 95%; object-fit: contain; }
"""

    # Select mode JS
    select_js = ""
    if select_mode:
        select_js = """
let selections = {};
function toggleSelect(idx) {
    const el = document.querySelector(`[data-idx="${idx}"]`);
    if (selections[idx] === 'selected') {
        delete selections[idx];
        el.className = 'post';
    } else {
        selections[idx] = 'selected';
        el.className = 'post selected';
    }
    updateExport();
}
function updateExport() {
    const selected = Object.keys(selections).filter(k => selections[k] === 'selected');
    document.getElementById('export-btn').innerText = `导出选中 (${selected.length})`;
}
function exportSelected() {
    const selected = Object.keys(selections).filter(k => selections[k] === 'selected');
    if (!selected.length) { alert('未选择任何推文'); return; }
    const data = selected.map(i => POSTS[i]);
    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'selected_posts.json';
    a.click();
}
"""

    # Header
    header_extra = ""
    if select_mode:
        header_extra = '<button id="export-btn" onclick="exportSelected()" style="padding:8px 16px;background:#4ade80;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:600;">导出选中 (0)</button>'

    parts = [f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>X 推文画廊</title>
<style>{css}</style>
</head>
<body>
<div class="header">
  <div><h1>X 推文画廊</h1><div class="stats">{len(posts)} 条推文 · {total_images} 张图片</div></div>
  {header_extra}
</div>
<div class="container">
"""]

    posts_json = json.dumps(posts, ensure_ascii=False)
    parts.append(f"<script>const POSTS = {posts_json};</script>")
    parts.append(f"<script>{select_js}</script>")

    for i, p in enumerate(posts):
        text_html = make_html_text(p.get("text", ""))
        likes = p.get("likes", 0)
        rts = p.get("retweets", 0)
        views = p.get("views", 0)
        handle = p.get("handle", "")
        author = p.get("author", "")
        url = p.get("url", "#")
        images = p.get("images", [])
        # Use _folder from all_posts.json if present, otherwise compute it
        folder = p.get("_folder", "")
        if not folder:
            handle_raw = p.get("handle", "unknown")
            snippet = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', p.get("text", "")[:25]).strip()
            snippet = re.sub(r'\s+', '_', snippet)[:40] if snippet else p.get("id", "")
            folder = f"{i+1:02d}_{handle_raw}_{snippet}"
        has_prompt_flag = has_prompt(p.get("text", ""))

        prompt_badge = ' <span style="background:#f59e0b;color:#000;padding:2px 6px;border-radius:3px;font-size:11px;">📝含提示词</span>' if has_prompt_flag else ""
        onclick = f'onclick="toggleSelect({i})"' if select_mode else ""

        num_imgs = len(images)
        if num_imgs == 0:
            cols_class = "no-images"
            img_class = ""
        elif num_imgs == 1:
            cols_class = ""
            img_class = "single"
        elif num_imgs == 2:
            cols_class = ""
            img_class = "pair"
        else:
            cols_class = ""
            img_class = "quad"

        imgs_html = ""
        for img in images:
            img_path = f"{folder}/{img['file']}"
            imgs_html += f'<img class="{img_class}" src="{img_path}" loading="lazy" onclick="openLightbox(this.src)">'

        if not images:
            placeholder = '<div class="no-img-placeholder">📷 无图片</div>'
        else:
            placeholder = ""

        parts.append(f"""
<div class="post" data-idx="{i}" {onclick}>
  <div class="post-text">
    <div class="author">{html.escape(author)}{prompt_badge}</div>
    <div class="handle"><a href="{url}" target="_blank" style="color:#666;text-decoration:none;">@{html.escape(handle)}</a></div>
    <div class="content">{text_html}</div>
    <div class="meta">
      <span>❤ {likes}</span>
      <span>🔄 {rts}</span>
      <span>👁 {views}</span>
    </div>
  </div>
  <div class="{cols_class}">{imgs_html}{placeholder}</div>
</div>
""")

    parts.append("""
</div>
<div class="lightbox" id="lightbox" onclick="this.classList.remove('active')">
  <img id="lightbox-img" src="">
</div>
<script>
function openLightbox(src) {
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').classList.add('active');
}
</script>
</body>
</html>""")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    return len(posts), total_images

def main():
    parser = argparse.ArgumentParser(description="Generate HTML gallery from tweet data")
    parser.add_argument("--input", "-i", required=True, help="Input directory with all_posts.json")
    parser.add_argument("--output", "-o", help="Output HTML path (default: input/gallery.html)")
    parser.add_argument("--select", action="store_true", help="Enable selection mode")
    args = parser.parse_args()

    input_dir = args.input
    output_path = args.output or os.path.join(input_dir, "gallery.html")

    all_posts_path = os.path.join(input_dir, "all_posts.json")
    if not os.path.exists(all_posts_path):
        print(f"ERROR: {all_posts_path} not found")
        return 1

    with open(all_posts_path, "r", encoding="utf-8") as f:
        posts = json.load(f)

    # CRITICAL: preserve _folder from all_posts.json, only compute if missing
    # Previously this script recomputed _folder for ALL posts, which broke image paths
    # when folders were created by a separate script with different numbering.
    for i, p in enumerate(posts):
        if "error" in p:
            continue
        if "_folder" not in p:
            handle = p.get("handle", "unknown")
            snippet = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', p.get("text", "")[:25]).strip()
            snippet = re.sub(r'\s+', '_', snippet)[:40] if snippet else p.get("id", "")
            p["_folder"] = f"{i+1:02d}_{handle}_{snippet}"

    # Filter out error posts
    valid_posts = [p for p in posts if "error" not in p]

    n_posts, n_images = generate_gallery(valid_posts, output_path, select_mode=args.select)
    print(f"✅ Gallery generated: {output_path}")
    print(f"   {n_posts} posts, {n_images} images")
    return 0

if __name__ == "__main__":
    exit(main())
