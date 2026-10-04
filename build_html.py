# -*- coding: utf-8 -*-
"""把本目录全部 Markdown 章节合并为一份带导航的 HTML（Python进阶学习指南.html）。

依赖：pip install markdown pygments
用法：python build_html.py
"""
import html as html_mod
import re
from datetime import date
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

HERE = Path(__file__).resolve().parent
OUT = HERE / "Python进阶学习指南.html"

CHAPTERS = [
    ("README.md", "总览与学习路线"),
    ("01_闭包与装饰器.md", "第1章 闭包与装饰器"),
    ("02_迭代器与生成器.md", "第2章 迭代器与生成器"),
    ("03_上下文管理器与内存管理.md", "第3章 上下文管理器与内存管理"),
    ("04_IO与文件处理.md", "第4章 IO与文件处理"),
    ("05_多线程编程.md", "第5章 多线程编程"),
    ("06_多进程编程.md", "第6章 多进程编程"),
    ("07_异步编程_asyncio.md", "第7章 异步编程 asyncio"),
    ("08_面向对象进阶.md", "第8章 面向对象进阶"),
    ("09_工程化开发规范.md", "第9章 工程化开发规范"),
]

MD = markdown.Markdown(
    extensions=["fenced_code", "tables", "toc", "codehilite"],
    extension_configs={
        "codehilite": {"guess_lang": False, "css_class": "codehilite"},
        "toc": {"permalink": False},
    },
)


def convert_chapter(idx: int, fname: str, fallback_title: str) -> dict:
    text = (HERE / fname).read_text(encoding="utf-8")
    MD.reset()
    body = MD.convert(text)

    prefix = f"sec{idx}"
    body = re.sub(r'id="([^"]+)"', lambda m: f'id="{prefix}-{m.group(1)}"', body)

    # 章节间的相对 .md 链接改为页内锚点
    def link_repl(m: re.Match) -> str:
        href = m.group(1)
        for j, (fn, _) in enumerate(CHAPTERS):
            if href == fn:
                return f'href="#sec{j}"'
        return m.group(0)

    body = re.sub(r'href="([^"#]+?\.md)"', link_repl, body)

    m1 = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    title = re.sub(r"<[^>]+>", "", m1.group(1)).strip() if m1 else fallback_title
    subs = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
    return {"id": prefix, "title": title, "subs": subs, "body": body}


def build_toc(chapters: list[dict]) -> str:
    parts = ['<nav class="toc" id="toc">']
    for ch in chapters:
        parts.append(f'<div class="toc-chapter"><a href="#{ch["id"]}">{html_mod.escape(ch["title"])}</a>')
        if ch["subs"]:
            parts.append('<ul class="toc-subs">')
            for hid, htext in ch["subs"]:
                parts.append(f'<li><a href="#{hid}">{htext}</a></li>')
            parts.append("</ul>")
        parts.append("</div>")
    parts.append("</nav>")
    return "\n".join(parts)


PYGMENTS_CSS = HtmlFormatter(style="default").get_style_defs(".codehilite")

CSS = """
:root {
  --bg: #ffffff; --fg: #24292f; --muted: #656d76;
  --accent: #0969da; --accent-soft: #ddf4ff;
  --border: #d8dee4; --code-bg: #f6f8fa;
  --sidebar-bg: #fbfbfc;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; color: var(--fg); background: var(--bg);
  font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  font-size: 16px; line-height: 1.75;
}
/* ---------- 布局 ---------- */
#sidebar {
  position: fixed; inset: 0 auto 0 0; width: 300px; overflow-y: auto;
  background: var(--sidebar-bg); border-right: 1px solid var(--border);
  padding: 20px 16px 40px; z-index: 10;
}
#sidebar h1 { font-size: 17px; margin: 4px 0 2px; }
#sidebar .sub { color: var(--muted); font-size: 12px; margin-bottom: 14px; }
.toc a { display: block; color: var(--fg); text-decoration: none; font-size: 14px;
         padding: 3px 8px; border-radius: 6px; }
.toc a:hover { background: var(--accent-soft); color: var(--accent); }
.toc a.active { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.toc-chapter > a { font-weight: 600; margin-top: 6px; }
.toc-subs { list-style: none; margin: 2px 0 4px; padding-left: 14px; }
.toc-subs a { color: var(--muted); font-size: 13px; }
main { margin-left: 300px; }
.content { max-width: 860px; margin: 0 auto; padding: 48px 40px 120px; }
/* ---------- 正文 ---------- */
h1 { font-size: 30px; line-height: 1.3; border-bottom: 2px solid var(--border); padding-bottom: 10px; }
h2 { font-size: 22px; margin-top: 2.2em; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
h3 { font-size: 18px; margin-top: 1.6em; }
h2[id], h3[id] { scroll-margin-top: 24px; }
a { color: var(--accent); }
blockquote {
  margin: 1em 0; padding: 10px 16px; border-left: 4px solid var(--accent);
  background: var(--accent-soft); border-radius: 0 8px 8px 0; color: #1f2328;
}
blockquote p { margin: 0.2em 0; }
code {
  font-family: "Cascadia Code", Consolas, "JetBrains Mono", monospace;
  background: var(--code-bg); padding: 2px 6px; border-radius: 5px; font-size: 0.9em;
}
.codehilite { position: relative; margin: 1em 0; }
.codehilite pre {
  margin: 0; padding: 14px 16px; overflow-x: auto; background: var(--code-bg);
  border: 1px solid var(--border); border-radius: 8px;
  font-family: "Cascadia Code", Consolas, "JetBrains Mono", monospace;
  font-size: 13.5px; line-height: 1.6;
}
.codehilite code { background: none; padding: 0; font-size: inherit; }
.copy-btn {
  position: absolute; top: 8px; right: 8px; border: 1px solid var(--border);
  background: #fff; color: var(--muted); border-radius: 6px; padding: 2px 10px;
  font-size: 12px; cursor: pointer; opacity: 0; transition: opacity .15s;
}
.codehilite:hover .copy-btn { opacity: 1; }
.copy-btn:hover { color: var(--accent); border-color: var(--accent); }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 14.5px; }
th, td { border: 1px solid var(--border); padding: 7px 12px; text-align: left; }
th { background: var(--code-bg); }
tbody tr:nth-child(even) { background: #fafbfc; }
hr { border: none; border-top: 1px solid var(--border); margin: 2.5em 0; }
ul, ol { padding-left: 1.6em; }
li { margin: 3px 0; }
.chapter { margin-bottom: 4em; }
/* ---------- 顶栏 / 小屏 ---------- */
#topbar {
  display: none; position: fixed; top: 0; left: 0; right: 0; height: 48px;
  background: var(--bg); border-bottom: 1px solid var(--border);
  align-items: center; gap: 12px; padding: 0 14px; z-index: 20;
}
#menu-btn { border: 1px solid var(--border); background: var(--bg); border-radius: 6px;
            padding: 4px 10px; cursor: pointer; font-size: 14px; }
@media (max-width: 1100px) {
  #sidebar { transform: translateX(-100%); transition: transform .2s; }
  body.sidebar-open #sidebar { transform: translateX(0); box-shadow: 0 0 40px rgba(0,0,0,.2); }
  main { margin-left: 0; }
  #topbar { display: flex; }
  .content { padding-top: 76px; }
}
#backtop {
  position: fixed; right: 24px; bottom: 24px; width: 40px; height: 40px;
  border-radius: 50%; border: 1px solid var(--border); background: var(--bg);
  color: var(--accent); font-size: 18px; cursor: pointer; display: none; z-index: 15;
}
/* ---------- 打印 ---------- */
@media print {
  #sidebar, #topbar, #backtop, .copy-btn { display: none !important; }
  main { margin: 0; }
  .content { max-width: none; padding: 0; }
  .codehilite pre { white-space: pre-wrap; border: 1px solid #ccc; }
}
"""

JS = """
document.addEventListener('DOMContentLoaded', function () {
  // 代码复制按钮
  document.querySelectorAll('.codehilite').forEach(function (block) {
    var btn = document.createElement('button');
    btn.className = 'copy-btn'; btn.textContent = '复制';
    btn.addEventListener('click', function () {
      navigator.clipboard.writeText(block.innerText).then(function () {
        btn.textContent = '已复制';
        setTimeout(function () { btn.textContent = '复制'; }, 1200);
      });
    });
    block.appendChild(btn);
  });

  // 目录滚动高亮
  var links = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  var byId = {};
  links.forEach(function (a) {
    var id = a.getAttribute('href').slice(1);
    byId[id] = a;
  });
  var targets = Object.keys(byId).map(function (id) { return document.getElementById(id); })
                    .filter(Boolean);
  var ticking = false;
  function update() {
    ticking = false;
    var current = targets[0];
    for (var i = 0; i < targets.length; i++) {
      if (targets[i].getBoundingClientRect().top <= 90) current = targets[i];
      else break;
    }
    links.forEach(function (a) { a.classList.remove('active'); });
    if (current && byId[current.id]) {
      byId[current.id].classList.add('active');
      byId[current.id].scrollIntoView({ block: 'nearest' });
    }
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true });
  update();

  // 移动端菜单 & 返回顶部
  var menuBtn = document.getElementById('menu-btn');
  if (menuBtn) menuBtn.addEventListener('click', function () {
    document.body.classList.toggle('sidebar-open');
  });
  document.querySelectorAll('.toc a').forEach(function (a) {
    a.addEventListener('click', function () { document.body.classList.remove('sidebar-open'); });
  });
  var backTop = document.getElementById('backtop');
  window.addEventListener('scroll', function () {
    backTop.style.display = window.scrollY > 600 ? 'block' : 'none';
  }, { passive: true });
  backTop.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
});
"""


def main() -> None:
    chapters = [convert_chapter(i, fn, label) for i, (fn, label) in enumerate(CHAPTERS)]
    sections = "\n".join(
        f'<section class="chapter" id="{c["id"]}">\n{c["body"]}\n</section>'
        for c in chapters
    )
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Python 进阶学习指南</title>
<style>{PYGMENTS_CSS}</style>
<style>{CSS}</style>
</head>
<body>
<header id="topbar">
  <button id="menu-btn">☰ 目录</button>
  <strong>Python 进阶学习指南</strong>
</header>
<aside id="sidebar">
  <h1>Python 进阶学习指南</h1>
  <div class="sub">生成于 {date.today().isoformat()} · 共 {len(chapters)} 章</div>
  {build_toc(chapters)}
</aside>
<main><div class="content">
{sections}
</div></main>
<button id="backtop" title="返回顶部">↑</button>
<script>{JS}</script>
</body>
</html>
"""
    OUT.write_text(doc, encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"OK: {OUT.name} ({size_kb:.0f} KB, {len(chapters)} chapters)")


if __name__ == "__main__":
    main()
