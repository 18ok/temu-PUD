# AGENTS.md — POD智能定制 / Temu运营数据面板

> cc 进入本目录时自动读取。Hermes Agent 通过 skill 体系加载。

---

## 项目结构

```
POD智能定制/
├── temu-dashboard.html          ← 核心：单文件纯前端数据面板（**V10**, ~2450行）
├── local_server.py              ← 本地服务 + OSS 代理（绕过 CORS）
├── 启动本地看板.bat              ← 推荐启动方式 localhost:8080
├── CHANGELOG.md                 ← 版本传递记录
├── POD-AI平台-老板演示.html     ← 给老板看的商业演示页（不是技术文档）
├── POD-AI平台-技术搭建演示文档.html ← 原版技术文档（给技术团队看的）
├── architecture-review.html     ← 架构审查页
├── docs/
│   ├── PRD-双数据管线.md
│   └── agents/
│       ├── issue-tracker.md
│       └── triage-labels.md
└── .git/                        ← GitHub: https://github.com/18ok/temu-PUD
```

---

## temu-dashboard.html 核心约定

### 架构
- 纯前端：HTML + Vanilla JS + CDN（无构建工具）
- **对外版本号：V10**（侧边栏 / title；localStorage 前缀仍为 `temu_v6_`，勿改）
- 本地开发：`启动本地看板.bat` → `http://localhost:8080/temu-dashboard.html`（含 OSS 代理）
- 数据存储：localStorage + 阿里云 OSS（`temu-shujufenxi-data` / `oss-cn-hangzhou`）
- 图表：Plotly CDN · Excel：SheetJS · OSS：ali-oss SDK + Python 代理
- **8 个页面**：数据导入 / 商品画像 / 选品规则 / 智能预测 / 避坑清单 / 个人诊断 / 店铺运营 / 个人 PK
- 侧边栏：⬆ 同步 · 📥 团队 · ⚙ OSS · 🧪 联调 · 💾 本地 · 🗑️ 清除

### 配色（不可随意改）
- 底色 `#0f0f17`（极暗蓝黑）
- 金色 `#e2b87a`（琥珀金，用作强调色）
- 正文 `#e8e6e3`
- 卡片 `#1a1a26`
- 拒绝纯色、黄桔色

### 全局状态对象
```js
ST = {
    files: [],        // 上传文件的解析结果数组
    products: [],     // extractProducts() 的输出
    clusters: [],     // 聚类结果（黄金/白银/观察）
    rules: [],        // 选品规则
    _avoidance: [],   // 避坑清单
    _stats: {},       // 统计摘要
    snapshots: []     // 快照索引
}
```

### 数据流
```
上传 Excel → SheetJS 解析 → normalizeCols() 列名映射 → ST.files
→ DataPipeline.analyze() → ST.products / clusters / rules / _avoidance / _stats
→ 各页面 renderXxx() 读取 ST 渲染
```

---

## ⚠️ 关键踩坑（cc 修改前必读）

### 1. localStorage 配额（今天修过，不要再犯）

**问题**：localStorage 上限 ~5MB。之前快照存全量 `JSON.stringify(ST.files)`，几次上传就爆。
**修复**：
- 快照只存摘要 `{time, fileCount, rowCount}`，不存全量数据
- 新增 `safeSetItem(key, value)` 函数——**所有 localStorage 写入必须走这个函数，不能直接 `localStorage.setItem`**
- 配额溢出时自动清理旧快照（保留最近 3 个）后重试
- 快照上限 10 个，`handleFileUpload` 中自动删除超出部分
- `clearAllData()` 可清空所有 `temu_v6_*` 键

```js
// ✅ 正确写法
safeSetItem('temu_v6_data', JSON.stringify(ST.files));

// ❌ 错误写法（会导致 QuotaExceededError）
localStorage.setItem('temu_v6_data', JSON.stringify(ST.files));
```

### 2. 数据损坏恢复

`init()` 中如果 `ST.files` 解析失败或 `reprocessAll()` 抛异常，会自动调用 `clearAllData()` 清空重建。**不要移除这个保护逻辑。**

### 3. 列名映射（cc 做容易出错）

`normalizeCols()` 在文件约第 600 行，做 Excel 列名 → 内部字段的映射。Excel 列名不规范时容易映射失败。**修改映射前先看实际 Excel 文件的列名。**

关键映射：
```
spuid/spu id → spu_id
名称/品名/商品名称 → name
成本 → cost
克重/重量/weight → weight_g
售价/卖价 → price
日均销量/销量/daily_sales/sales → daily_sales
毛利率 → gross_margin
日利润 → daily_profit
品类 → category
```

### 4. DataPipeline.analyze() 可能返回 undefined

当输入数据为空或格式错误时，`DataPipeline.analyze()` 可能返回不带 `products` 属性的结果。`reprocessAll()` 和所有调用方已做了空值检查。**新增调用点时也要加检查。**

---

## 开发流程

```bash
# 推荐：本地看板（OSS 同步必须走此方式）
双击 启动本地看板.bat
# → http://localhost:8080/temu-dashboard.html

# Git
git remote -v   # origin  git@github.com:18ok/temu-PUD.git
# 版本记录见 CHANGELOG.md
```

---

## cc 常见任务

| 任务 | 涉及函数/区域 | 注意事项 |
|------|-------------|---------|
| 新增导入格式支持 | `normalizeCols()` / `handleFileUpload()` | 先看实际 Excel 列名 |
| 新增分析指标 | `DataPipeline.analyze()` / `extractProducts()` | 同步更新 `_stats` 对象 |
| 新增页面/面板 | 参照现有 6 页的 `<details class="expander">` 结构 | 配色用 CSS 变量 `var(--gold)` 等 |
| 修 localStorage bug | 全局搜索 `localStorage.setItem` | 全部替换为 `safeSetItem` |
| 改 UI/配色 | 全局搜索颜色值 | 只用 `#0f0f17`/`#e2b87a`/`#e8e6e3`/`#1a1a26` |
