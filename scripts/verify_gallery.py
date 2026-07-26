#!/usr/bin/env python3
"""Verify HTML gallery integrity — check image paths, file sizes, and consistency."""

import argparse, json, os, re, sys

def verify_gallery(gallery_dir):
    issues = []
    warnings = []
    
    all_posts_path = os.path.join(gallery_dir, "all_posts.json")
    gallery_html_path = os.path.join(gallery_dir, "gallery.html")
    
    # 1. Check required files exist
    if not os.path.exists(all_posts_path):
        issues.append(f"❌ all_posts.json 不存在: {all_posts_path}")
        return issues, warnings
    else:
        print(f"✅ all_posts.json 存在")
    
    if not os.path.exists(gallery_html_path):
        issues.append(f"❌ gallery.html 不存在: {gallery_html_path}")
        return issues, warnings
    else:
        print(f"✅ gallery.html 存在")
    
    # 2. Load and validate all_posts.json
    with open(all_posts_path, "r", encoding="utf-8") as f:
        posts = json.load(f)
    
    print(f"✅ all_posts.json 包含 {len(posts)} 条记录")
    
    # 3. Check each post's folder and images
    total_images = 0
    missing_images = 0
    empty_images = 0
    path_mismatches = 0
    
    for i, p in enumerate(posts):
        if "error" in p:
            continue
        
        folder = p.get("_folder", "")
        handle = p.get("handle", "unknown")
        post_id = p.get("id", "")
        
        # Check _folder field exists
        if not folder:
            issues.append(f"❌ Post {i+1} (@{handle}, ID:{post_id}) 缺少 _folder 字段")
            path_mismatches += 1
            continue
        
        # Check folder actually exists
        actual_folder_path = os.path.join(gallery_dir, folder)
        if not os.path.exists(actual_folder_path):
            # Try to find the actual folder
            found = False
            for entry in os.listdir(gallery_dir):
                if entry.startswith(f"{i+1:02d}_") and os.path.isdir(os.path.join(gallery_dir, entry)):
                    issues.append(f"❌ Post {i+1} (@{handle}) 路径不匹配: JSON中是 '{folder}'，实际文件夹是 '{entry}'")
                    actual_folder_path = os.path.join(gallery_dir, entry)
                    found = True
                    path_mismatches += 1
                    break
            if not found:
                issues.append(f"❌ Post {i+1} (@{handle}) 文件夹不存在: {folder}")
                path_mismatches += 1
                continue
        
        # Check each image
        images = p.get("images", [])
        for img in images:
            total_images += 1
            img_file = img.get("file", "")
            if not img_file:
                issues.append(f"❌ Post {i+1} (@{handle}) 图片缺少 file 字段")
                missing_images += 1
                continue
            
            img_path = os.path.join(actual_folder_path, img_file)
            if not os.path.exists(img_path):
                # Try alternative names
                alt_found = False
                for ext in [".jpg", ".png", ".jpeg"]:
                    alt_path = os.path.join(actual_folder_path, img_file.rsplit(".", 1)[0] + ext)
                    if os.path.exists(alt_path):
                        alt_found = True
                        warnings.append(f"⚠️ Post {i+1} (@{handle}) 图片扩展名不匹配: 期望 {img_file}，实际找到 {os.path.basename(alt_path)}")
                        img_path = alt_path
                        break
                
                if not alt_found:
                    issues.append(f"❌ Post {i+1} (@{handle}) 图片不存在: {folder}/{img_file}")
                    missing_images += 1
                    continue
            
            # Check file size
            try:
                size = os.path.getsize(img_path)
                if size < 1024:  # Less than 1KB
                    issues.append(f"❌ Post {i+1} (@{handle}) 图片太小 ({size}字节): {folder}/{img_file}")
                    empty_images += 1
                elif size < 10240:  # Less than 10KB - warning
                    warnings.append(f"⚠️ Post {i+1} (@{handle}) 图片较小 ({size//1024}KB): {folder}/{img_file}")
            except OSError as e:
                issues.append(f"❌ Post {i+1} (@{handle}) 无法读取图片: {folder}/{img_file} - {e}")
                missing_images += 1
    
    # 4. Check HTML references match all_posts.json
    with open(gallery_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Extract image paths from HTML (exclude lightbox-img which uses JS src)
    html_img_pattern = r'<img[^>]+src="([^"]+)"[^>]*>'
    html_img_paths = set(re.findall(html_img_pattern, html_content))
    # Remove the lightbox placeholder
    html_img_paths.discard("")
    
    # Build expected paths from all_posts.json
    expected_paths = set()
    for p in posts:
        if "error" in p:
            continue
        folder = p.get("_folder", "")
        if not folder:
            continue
        for img in p.get("images", []):
            img_file = img.get("file", "")
            if img_file:
                expected_paths.add(f"{folder}/{img_file}")
    
    # Compare
    html_only = html_img_paths - expected_paths
    json_only = expected_paths - html_img_paths
    
    if html_only:
        issues.append(f"❌ HTML中有 {len(html_only)} 个图片路径不在all_posts.json中")
        for p in sorted(html_only)[:5]:
            issues.append(f"   - {p}")
    
    if json_only:
        issues.append(f"❌ all_posts.json中有 {len(json_only)} 个图片路径不在HTML中")
        for p in sorted(json_only)[:5]:
            issues.append(f"   - {p}")
    
    # 5. Check _folder field consistency
    folder_set = set()
    duplicate_folders = []
    for p in posts:
        if "error" in p:
            continue
        folder = p.get("_folder", "")
        if folder:
            if folder in folder_set:
                duplicate_folders.append(folder)
            folder_set.add(folder)
    
    if duplicate_folders:
        issues.append(f"❌ 发现 {len(duplicate_folders)} 个重复的 _folder 名称")
        for f in duplicate_folders[:5]:
            issues.append(f"   - {f}")
    
    # 6. Summary
    print(f"\n{'='*60}")
    print(f"📊 验证结果摘要:")
    print(f"   - 总帖子数: {len(posts)}")
    print(f"   - 总图片数: {total_images}")
    print(f"   - 缺失图片: {missing_images}")
    print(f"   - 损坏图片(太小): {empty_images}")
    print(f"   - 路径不匹配: {path_mismatches}")
    print(f"   - HTML/JSON不一致: {len(html_only) + len(json_only)}")
    
    if warnings:
        print(f"\n⚠️ 警告 ({len(warnings)}):")
        for w in warnings:
            print(f"   {w}")
    
    if issues:
        print(f"\n❌ 错误 ({len(issues)}):")
        for issue in issues:
            print(f"   {issue}")
        print(f"\n{'='*60}")
        print(f"❌ FAIL({len(issues)})")
        return issues, warnings
    else:
        print(f"\n{'='*60}")
        print(f"✅ PASS — 画廊完整性验证通过!")
        return issues, warnings

def main():
    parser = argparse.ArgumentParser(description="Verify HTML gallery integrity")
    parser.add_argument("gallery_dir", help="Gallery directory to verify")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()
    
    if not os.path.exists(args.gallery_dir):
        print(f"❌ 目录不存在: {args.gallery_dir}")
        return 1
    
    issues, warnings = verify_gallery(args.gallery_dir)
    
    if args.json:
        result = {
            "pass": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "issue_count": len(issues),
            "warning_count": len(warnings)
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    return 0 if len(issues) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
