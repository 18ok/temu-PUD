# 选品心决 — Visual Design

Design Read: Editorial / 采访笔记，Temu 老板+新人，手稿语言；原生 CSS；MOTION 4；DENSITY 3。

## Tokens

| Token | Value |
|-------|-------|
| `--bg` | `#f6f6f4` |
| `--ink` | `#2e2e2e` |
| `--gold` | `#e2b87a` |

## Bans

无 side-stripe · 无 hero metrics · 无 identical card grid · 无 dashboard footer 链接

## Reader（统一浮层）

采访 / 简报 / 计算器共用 `assets/reader.js` + `#read/{id}` 分享链接。

- 遮罩：blur + 半透明；面板：实底 `#ffffff`
- 左侧「← 返回」；面板内独立滚动 + 细金滚动条
- 关闭恢复首页 scrollY；同篇再开恢复浮层内滚动
- 点遮罩：400ms 后生效，需连点两次关闭（防误触）

## CTA 原则

动词+对象；站内闭环：读采访 → 毛利粗算 → 回采访/简报（均在浮层内）
