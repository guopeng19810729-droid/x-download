#!/usr/bin/env python3
"""Fetch X/Twitter posts via fxtwitter API, download images, save metadata."""

import argparse, json, os, re, subprocess, sys, time

PROXY = "socks5h://127.0.0.1:10808"

def log(msg):
    print(msg, flush=True)

def fetch_url(url, timeout=30):
    try:
        r = subprocess.run(
            ["curl", "-s", "-L", "--proxy", PROXY, "--max-time", str(timeout), url],
            capture_output=True, timeout=timeout+10
        )
        return r.stdout
    except Exception as e:
        log(f"  curl error: {e}")
        return b""

def sanitize(name, max_len=40):
    name = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:max_len] if name else ""

def fetch_tweet(tid):
    raw = fetch_url(f"https://api.fxtwitter.com/status/{tid}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if data.get("code") == 200 and "tweet" in data:
            return data["tweet"]
    except:
        pass
    return None

def download_image(img_url, save_path):
    raw = fetch_url(img_url)
    if raw and len(raw) > 1000:
        with open(save_path, "wb") as f:
            f.write(raw)
        return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Fetch X tweets and download images")
    parser.add_argument("--output", "-o", required=True, help="Output directory")
    parser.add_argument("--ids", required=True, help="Comma-separated tweet IDs")
    args = parser.parse_args()

    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    ids = [x.strip() for x in args.ids.split(",") if x.strip()]
    if not ids:
        log("ERROR: No valid IDs provided")
        sys.exit(1)

    results = []
    total = len(ids)
    success = 0
    fail = 0

    log(f"Starting fetch of {total} tweets → {output_dir}")

    for i, tid in enumerate(ids):
        log(f"[{i+1}/{total}] {tid}")

        t = fetch_tweet(tid)
        if not t:
            log(f"  SKIP: fetch failed")
            results.append({"id": tid, "error": "fetch failed"})
            fail += 1
            continue

        author = t.get("author", {}).get("name", "Unknown")
        handle = t.get("author", {}).get("screen_name", "unknown")
        text = t.get("text", "")
        likes = t.get("likes", 0)
        retweets = t.get("retweets", 0)
        views = t.get("views", 0)
        time_str = t.get("created_at", "")

        # Folder name
        snippet = sanitize(text[:25]) if text else tid
        folder_name = f"{i+1:02d}_{handle}_{snippet}"
        folder_path = os.path.join(output_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        meta = {
            "id": tid,
            "index": i + 1,
            "author": author,
            "handle": handle,
            "text": text,
            "likes": likes,
            "retweets": retweets,
            "views": views,
            "time": time_str,
            "url": f"https://x.com/{handle}/status/{tid}",
            "images": [],
            "github_links": [],
        }

        # GitHub links
        gh_links = re.findall(r'https?://github\.com/[\w\-./]+', text)
        meta["github_links"] = list(set(gh_links))

        # Download images
        photos = t.get("media", {}).get("photos", [])
        for j, photo in enumerate(photos):
            img_url = photo.get("url", "")
            if not img_url:
                continue
            ext = "png" if ".png" in img_url else "jpg"
            img_name = f"image_{j+1}.{ext}"
            img_path = os.path.join(folder_path, img_name)

            if download_image(img_url, img_path):
                sz = os.path.getsize(img_path)
                meta["images"].append({"file": img_name, "url": img_url, "size": sz})
                log(f"  img: {img_name} ({sz//1024}KB)")
            else:
                log(f"  FAIL img: {img_url}")

        # Videos (save URL only)
        videos = t.get("media", {}).get("videos", [])
        for v in videos:
            vurl = v.get("url", "")
            if vurl:
                meta.setdefault("videos", []).append({"url": vurl})

        with open(os.path.join(folder_path, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        results.append(meta)
        success += 1
        log(f"  OK: @{handle} | {len(meta['images'])} imgs | ❤{likes} 🔄{retweets} 👁{views}")
        time.sleep(0.3)

    # Save all results
    with open(os.path.join(output_dir, "all_posts.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log(f"\n{'='*50}")
    log(f"DONE! Total:{total} Success:{success} Failed:{fail}")
    log(f"Results: {output_dir}/all_posts.json")

if __name__ == "__main__":
    main()
