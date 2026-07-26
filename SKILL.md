---
name: x-download
description: |
  X/Twitter 推文批量下载工具：搜索→抓取→下载图片→生成HTML画廊。
  触发条件：用户要求下载X推文、抓取推文图片、生成X内容画廊、批量保存推文。
  支持两种输入：①推文链接/ID列表 ②通过x_search搜索关键词/博主获取链接。
homepage: https://x.com
metadata:
  openclaw:
    emoji: 🐦
    requires:
      tools:
        - x_search
        - terminal
  dependencies:
    - curl（系统自带）
    - jq（系统自带）
    - python3（系统自带）
---

# X Download — 推文批量下载 & 画廊生成

## 工作流程

```
用户需求 → x_search搜索(可选) → 提取推文ID → fxtwitter抓取 → 下载图片 → 生成HTML画廊 → 【必须】自检查验证
```

**自检查是画廊交付的必要条件，FAIL必须修复后才能发送给用户。**

## Step 1: 获取推文ID

两种方式：

### 方式A：用户提供链接或ID
直接从链接中提取数字ID：
```
https://x.com/handle/status/1234567890 → 1234567890
```

### 方式B：用x_search搜索
```
x_search(query="关键词 from:博主handle", limit=20)
```
从返回结果的URL中提取推文ID。

## Step 2: 抓取推文 + 下载图片

使用 `scripts/fetch_tweets.py`：

```bash
python3 /path/to/scripts/fetch_tweets.py --output /root/X_project --ids "id1,id2,id3"
```

脚本会：
1. 通过 fxtwitter API 抓取每条推文（需要代理，fxtwitter被墙）
2. 下载所有图片到 `output/序号_handle_snippet/` 目录
3. 每个推文文件夹保存 `meta.json`（含作者、文本、点赞数、图片路径等）
4. 生成 `all_posts.json` 汇总所有数据

**⚠️ 代理要求**：fxtwitter.com 在国内被墙，必须通过 SOCKS5 代理（`socks5h://127.0.0.1:10808`）访问。

## Step 3: 生成HTML画廊

使用 `scripts/generate_gallery.py`：

```bash
python3 /path/to/scripts/generate_gallery.py --input /root/X_project --output /root/X_project/gallery.html
```

画廊特性：
- 暗色主题，响应式布局
- 每条推文显示：作者、文本、图片、互动数据
- 移动端自适应（图片网格自动调整）
- 图片可点击放大
- 支持两种模式：①纯展示模式 ②选择模式（勾选/排除，用于筛选内容）

### 选择模式（可选）
加 `--select` 参数启用勾选功能，适合从大量推文中筛选优质内容：
```bash
python3 /path/to/scripts/generate_gallery.py --input /root/X_project --output /root/X_project/gallery.html --select
```

## 完整示例

```bash
# 1. 搜索博主近7天推文
x_search(query="from:MANISH1027512 has:images", limit=10)
# → 获得推文ID列表

# 2. 批量抓取+下载
python3 scripts/fetch_tweets.py --output /root/X_galleries/manish --ids "id1,id2,id3"

# 3. 生成画廊
python3 scripts/generate_gallery.py --input /root/X_galleries/manish --output /root/X_galleries/manish/gallery.html

# 4. 【必须】自检查画廊完整性
python3 scripts/verify_gallery.py /root/X_galleries/manish/
```

## Step 4: 自检查（必须执行）

画廊生成后，**必须**运行验证脚本，确认无问题后才能交付用户：

```bash
python3 /root/.hermes/skills/media/x-download/scripts/verify_gallery.py /path/to/gallery/
```

验证脚本检查：
1. **图片存在性** — HTML中引用的每张图片文件是否实际存在
2. **文件大小** — 图片文件是否 >1KB（排除空文件/损坏文件）
3. **路径一致性** — `_folder`字段是否与实际文件夹名一致
4. **HTML/JSON一致性** — HTML中的img路径是否与all_posts.json完全匹配
5. **断链报告** — 列出所有无法显示的图片及原因

输出：
- `✅ PASS` — 验证通过，可以交付
- `❌ FAIL(N)` — 有N个问题，必须修复后重新验证

**规则：FAIL时必须修复后重新运行verify_gallery.py，直到PASS才能交付给用户。**

## 输出目录结构

```
/root/X_project/
├── 01_handle_推文摘要/
│   ├── meta.json        # 推文元数据
│   ├── image_1.jpg      # 下载的图片
│   ├── image_2.jpg
│   └── ...
├── 02_handle_推文摘要/
│   └── ...
├── all_posts.json       # 所有推文汇总
└── gallery.html         # HTML画廊
```

## meta.json 结构

```json
{
  "id": "推文ID",
  "index": 1,
  "author": "显示名",
  "handle": "用户名",
  "text": "推文正文",
  "likes": 100,
  "retweets": 50,
  "views": 10000,
  "time": "发布时间",
  "url": "原文链接",
  "images": [{"file": "image_1.jpg", "url": "原图URL", "size": 123456}],
  "github_links": []
}
```

## 打包与发送

画廊是静态HTML+相对路径图片，**必须打包才能正常浏览**。

```bash
# 打包（用tar.gz，不要用zip——服务器没装zip）
cd /root/X_galleries && tar czf output.tar.gz project_dir/
```

**微信发送限制：** 实测 tar.gz 约34MB可成功发送，176MB失败。估算上限约35-50MB。超过此大小的画廊：
- 告知用户从服务器直接下载（SSH/SCP/Workbench）
- 不要尝试拆分——拆分后gallery.html的相对路径会失效
- 如果必须发微信，可以只发 gallery.html（纯文本浏览），但需告知用户图片不可见

## 提示词筛选模式

当用户要求"只保留有提示词的帖子"时，使用自定义分析脚本替代标准fetch流程：

```bash
python3 scripts/analyze_prompts.py --output /root/X_galleries/filtered --ids "id1,id2,..."
```

该脚本（需临时编写）会：
1. 抓取每条推文内容
2. 检查是否有图片
3. 检查文本中是否包含提示词关键词（prompt/提示词/1girl/solo/photorealistic等）
4. 如果主推文无提示词，检查引用推文中是否有
5. 只保存同时满足"有图片+有提示词"的帖子
6. 跳过的帖子打印原因（no images / no prompt）

**提示词关键词检测列表（用于has_prompt函数）：**
- 英文：prompt, negative, checkpoint, lora, masterpiece, best quality, 8k, cinematic, studio, lighting, bokeh, photorealistic, realistic, flux, sdxl, midjourney, gpt image, grok, 1girl, solo, highres, absurdres, seed, sampler, steps, cfg scale, stable diffusion, comfyui, detailed skin, portrait, close-up, full body, upper body
- 中文：提示词

**⚠️ 关键陷阱：`_folder`字段必须与实际文件夹名一致。** `generate_gallery.py`优先使用`all_posts.json`中的`_folder`字段。如果自定义脚本创建了文件夹但没有在all_posts.json中正确设置`_folder`，会导致图片路径错位、最后几张图打不开。修复方法：自定义脚本保存all_posts.json时，每个条目必须包含`_folder`字段，值等于实际文件夹名。

**注意：** 有些帖子主推文没有提示词，但作者会在回复或引用推文中贴出。脚本需要检查quote字段。

## ⚠️ 关键陷阱：服务器内存限制（1.6GB）

**2026-07-22、07-25、07-26 三次崩溃的根因相同：** 批量下载+压缩+发送超出内存。

**崩溃模式：** 日志中断约4分钟后系统重启（kernel boot），无OOM killer日志，是thrash卡死导致的强制重启。

**绝对禁止的操作组合：**
- 同时下载多个博主的推文（并行curl进程×N）
- 下载完成后立即打包170MB+的目录（tar.gz压缩需要额外内存buffer）
- 打包的同时通过微信发送大文件
- 微信rate limit触发重试时继续其他重操作

**安全操作流程（必须按此顺序）：**
1. **逐个下载**——一个博主完成后再开始下一个
2. **逐个打包**——下载完一个就打包一个，不要等全部下载完再打包
3. **逐个发送**——一个发完再发下一个，避免微信rate limit叠加内存压力
4. **每次操作之间等待几秒**——让系统有时间回收内存

**单个博主的安全上限：** 约30条推文/60张图片/30MB。超过此规模的博主（如Ai_dailypic498有123张/170MB）应告知用户直接从服务器获取，不要尝试打包发送。

**批量处理8+个博主时：** 搜索→fetch→生成画廊 三个步骤都要串行。绝对不要同时搜索多个博主再批量fetch。每个博主完成后检查内存状态再继续下一个。

## x_search 搜索技巧

获取一个博主的40条推文通常需要3-4次搜索，每次约10条结果：

```bash
# 第1轮：最近的推文
x_search(query="from:handle filter:images", limit=20)

# 第2轮：更早的推文（用until:排除已获取的）
x_search(query="from:handle filter:images until:2026-07-23", limit=20)

# 第3轮：继续往前
x_search(query="from:handle filter:images until:2026-07-20", limit=20)
```

**注意事项：**
- `has:images` 操作符无效，必须用 `filter:images`
- `before:` 无效，必须用 `until:YYYY-MM-DD`
- 不加 `filter:images` 会返回大量纯文字回复，浪费fetch时间
- 从返回结果的URL中提取数字ID（`x.com/handle/status/ID` 或 `x.com/i/status/ID`）
- 部分博主发帖频率低，可能搜不到40条，取实际可用数量即可

## 批量处理多个博主（8+个博主的安全流程）

当用户要求处理多个博主时，**必须逐个串行处理**，不要并行：

```
搜索博主A → fetch博主A → 生成画廊A → 搜索博主B → fetch博主B → 生成画廊B → ...
```

**绝对不要** 同时搜索多个博主再批量fetch——这会导致内存耗尽和服务器崩溃。

每个博主完成后，检查内存状态再继续下一个。

## 已知限制

- fxtwitter 只能按推文ID抓取，不能按时间线批量拉取（需先用x_search找ID）
- 视频只记录URL，不自动下载（文件太大）
- 部分被删除或私密推文无法抓取
- 单次 x_search 最多返回约10条结果，获取20+条需要多次不同查询（until:日期过滤）
- x_search 的 `has:images` 操作符无效，用 `filter:images` 替代
- 微信连续发送多个文件会触发rate limit（30秒冷却），需间隔发送

## 追踪博主列表

见 `references/bloggers.md`，包含15个追踪博主的账号、状态和备注。
