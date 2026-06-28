# Changelog — Temu 运营数据看板

## V10.4.0 — 2026-06-26

### 组员说明文档对齐 V10.4

- **产品名**：跨境经营诊断系统（界面 V10.4.0）
- **导航改名**：团队工作台 / 团队对齐分；同步入口迁入 **⚙ 管理后台**
- **组员使用说明.html** / **OSS与协作版说明.html** / **先看这里.txt** 更新至 V10.4.0
- 补充 8 业务页 + 管理后台速查；区分 GitHub Pages 与本地 `api_server.py` 协作能力
- bat 说明改为 `api_server.py`（OSS 代理 + 协作 API）
- **GitHub Pages**：`同步Pages.bat` 同步 `docs/`（含组员说明）；workflow 一并部署说明文档
- **协作后台修复**：旧 SQLite 自动补 scope 字段；`/api/status` 不再因旧库断连；`/api/collab/ping` / `groups` 改为轻量探针，避免 OSS bootstrap 卡住后台检测
- **角色权限收口**：普通运营可同步自己的摘要；团队基准 / 主管看板仅主管及以上；同步配置与清除动作仅管理员 / 开发者可见
- **主管 PK 验收**：`/api/collab/team/pk-board` 优先走 SQLite，不再为了生成榜单强依赖 OSS meta/groups，避免主管看板超时
- **网页登录收口**：GitHub Pages / 异位面可检测本机 `api_server.py`（8080）并启用团队登录；未连接时保留 OSS 摘要同步和“检测登录服务”入口
- **侧栏视觉降噪**：主界面 / 异位面侧栏导航从彩色 emoji 改为内联 SVG 线性图标，降低廉价感并统一业务入口视觉

---

## V10.3.1 — 2026-06-03

### 异位面 polish + 组员说明

- **异位面角标**：从页面左上角移至侧栏品牌区 **右上角**，不再遮挡 🛒 图标；**主界面角标保持左上角不变**
- **异位面 UI 对称**：loading / 侧栏遮罩 blur、卡片与按钮 hover 阴影、通知小窗层次，与主界面对齐（浅色配色）
- **组员试用说明**：网页版优先（GitHub Pages + 异位面链接），bat 降为备选；`先看这里.txt` / `组员使用说明.html` 更新至 V10.3.1

---

## V10.3.0-alter — 2026-06-03

### 双界面对 · 主界面 + 异位面

- **主界面**：`temu-dashboard.html` / `docs/index.html` — 深色 Maia（V10.2.6+）
- **异位面**：`temu-dashboard-editorial.html` / `docs/editorial.html` — 浅色 Editorial，配合主界面，对齐 xuanpin-site
- 页脚 **界面对切换**（本地与 GitHub Pages）
- 异位面：Source Serif/Sans、浅底 `#f6f6f4`、6px 圆角、Plotly 浅色主题
- **功能 / OSS / localStorage 与主界面完全一致**，仅视觉层不同
- 异位面增强：侧栏 **异位面角标**、弹窗 **毛玻璃**（OSS 配置 / 日志 / 诊断等）、界面对 **GSAP 切换过渡**
- 主界面对称：侧栏 **主界面角标**、深色 **毛玻璃弹窗**、loading / 移动端遮罩 blur，与异位面一一对应
- **通知小窗**：右上角固定面板，约 3 条可见 + 滚轮滚动；上传/团队导入改为 **批量一条摘要**（减少卡顿）
- **界面对角标**：主界面左上角固定；异位面侧栏品牌区右上角（V10.3.1 调整）

---

## V10.2.5 — 2026-06-06

### 网页版 OSS / 联调

- **🧪 联调** 在 GitHub Pages 可用（不再强制 bat）
- **OSS 诊断**：网页版说明 CORS；增加「签名 GET」测试（与 📥 团队 同路径）；私有桶匿名 GET 403 不再误报
- **未改** `buildCloudSummary` / `uploadToCloud` / `fetchOssJson` 核心逻辑

---

## V10.2.4 — 2026-06-05

### 分发：GitHub Pages 为主入口（降低 bat 门槛）

- **同事主路径**：打开 `https://18ok.github.io/temu-PUD/` → 拖 Excel → PK（无需 Python/bat）
- 修复 **GitHub Actions Pages** 部署（`docs/index.html`）
- 导入页 / 分享链接 / 组员说明改为网页版优先；bat 标注为管理员本地模式
- PK 分享链接默认指向 Pages URL（不再发 localhost）
- **OSS 逻辑未改**；网页版同步需 OSS 控制台 CORS 允许 `https://18ok.github.io`

---

## V10.2.3 — 2026-06-05

### UI（product register · 不动数据流 / OSS）

- **导入 / PK / 诊断**：紧凑 hero、stat 卡片、对比度与 `focus-visible`
- **个人 PK**：对齐分卡片 + GSAP 计分（200ms，尊重 `prefers-reduced-motion`）
- **切页**：导入 / PK / 诊断轻 fade，无整页编排
- 新增 `DESIGN.md`、`.cursor/rules/temu-ui.mdc` 供后续 Agent 对齐规范
- **未改**：`buildCloudSummary`、`temu_v6_*`、OSS 同步逻辑、阶段验证面板逻辑

---

## V10.2.2 — 2026-06-05

### 组员试用包

- 打包脚本输出：`Temu选品助手-V10.2.2-组员试用包.zip`（不含 `.env` / Key）
- 试用路径：bat 启动 → 导入双 Excel → 🏆 个人 PK；云端同步需单独索取 `.env`
- 新增说明文档：`OSS与协作版说明.html`（云端同步 vs 协作版未开放）

### 阶段 1（稳步推进）

- **阶段验证进度面板**（导入页）：本地统计 PK 访问、分享复制、快照、双管线、OSS 状态；可复制摘要给访谈记录
- **PK 深链空状态**：`#pk` 无数据时说明「分享链接不含 Excel，需自行导入」+ 一键去导入
- 双管线齐备时导入页快捷按钮 **🏆 个人 PK**

### 修复

- **一键迁移 .env**：已托管时提示「无需再迁移」；迁移按钮变灰

---

## V10.2.1 — 2026-06-05

### 修复

- **导出诊断周报**：`compareSnapshots` 在诊断 IIFE 内导致导出报错；已移入同一模块
- **一键迁移 .env**：浏览器已存 Key 时刷新自动写入 `.env`；或 ⚙ OSS →「一键迁移 Key 到 .env」

---

## V10.2 — 2026-06-05

### 阶段 1（市场验证 · 不动数据流）

- **PK 预期管理 UI**：页顶「这是你个人的选品×运营对齐分」+ disabled「团队对比（协作版）」（C1-5 门禁）
- **PK 分享**：`#pk` 深链 +「复制分享链接」（对方需自行导入 Excel）
- **沉默统计**：`temu_v6_page_hits` 记录各页访问次数（localStorage，不上云）

### 阶段 0（Key 托管 · OSS 谨慎改动）

- **`POST /api/sync`**：`local_server.py` 从 `.env` 读取 Key；请求体 **不得** 含 `accessKeySecret`（C0-1）
- **兼容**：未配置 `.env` 时仍走 `/__temu_oss__` + 浏览器内 Key（旧行为不变）
- **上传/拉取路径**：`ossUploadObject` / `fetchOssJson` 优先 Key 托管，再回退代理/直传
- **OSS 配置弹窗**：检测到 Key 托管时隐藏 AccessKey 字段；侧边栏显示「Key·服务端」
- 新增 `.env.example`、`.gitignore`（忽略 `.env`）

---

## V10.1 — 2026-06-05

### 修复（P0）

- **初始化顺序**：`bootstrap()` 移至脚本末尾，修复 `DataPipeline` / `PAGE_META` / `renderImportPage` 未定义导致上传、OSS 诊断、联调全线报错
- **上传 loading 卡死**：`handleFileUpload` / `handleTeamUpload` 增加 `finally`，存储满时单独提示「保存失败」
- **OSS 诊断 / 团队联调**：点击即弹出实时结果窗；代理 ping 5s、读写 15s、总超时 35s/45s
- **OSS 配置**：`init` 前定义 `OSS_DEFAULT`，修复 `temu-shujufenxi-data` 读取报错
- **local_server.py**：修复 Chrome DevTools 404 触发的 `log_message` TypeError

### 优化

- 店铺数据 `safeSetItem` 挪至解析成功后，避免误报「解析失败」
- `daily_profit` 双列（毛利润+每天利润）视为 Temu 正常表头，不再 F12 刷红
- `parse_report` 仅写入侧边栏日志，不污染 Console
- 启动自检 `runStartupSelfCheck()`；`docs/index.html` 与主文件同步

---

## V10 — 2026-06-03

团队 OSS 同步上线 + 数据解析全面修复。UI 版本号统一为 **V10**（localStorage 仍用 `temu_v6_*` 前缀，兼容旧数据）。

### 体验优化（UX）— 第二轮

- 各页**空状态**卡片 + 一键「去导入数据」
- **数据洞察条**（导入页/商品画像）：SPU、黄金品占比、团队均毛利
- **工作流条可点击**跳转；③ 团队同步一键触发 OSS
- Toast **堆叠** + 上传成功 **撤销** 最近一次
- 诊断页 **📄 导出周报**（Markdown）· 侧栏快捷入口

### 体验优化（UX）— 首轮

- 顶栏：当前页标题 + 快捷「📋 日志」「⬆ 同步」
- 工作流进度条：导入 → 分析 → 团队同步 → 诊断复盘
- 上传：拖拽高亮、全局加载遮罩、多文件并行解析反馈
- 页面切换淡入动画；侧栏激活金色指示条；背景微渐变
- 移动端：侧栏抽屉 + 遮罩；快捷键 1–8 / M / L；URL `#页面` 深链

### 新增

- **运行日志 v2**：localStorage 环形缓冲（`temu_v6_event_log`，最近 200 条）；级别 + 模块 + 关键词筛选；导入页 + 侧边栏「📋 日志」；复制 / 导出（含解析报告）/ ☁️ OSS 备份（`temu/logs/{归属人}/`）
- **解析报告**：`temu_v6_parse_reports`（最近 30 份）；Excel 原表头 → 内部字段对照表、缺列告警、SPU/毛利率/日销为零占比；导入页「📑 解析报告」面板
- **阿里云 OSS 团队同步**：⬆ 同步 / 📥 团队 / ⚙ OSS 配置
- **本地 OSS 代理**（`local_server.py` + `启动本地看板.bat`）：绕过浏览器 CORS，Bucket 可私有
- **🧪 团队联调**：模拟第二人上传并验证拉取链路
- **RAM 子账号 + 签名读写**：GetObject / PutObject，不依赖公共读
- 双管线文件类型自动识别（利润统计 `.xls` / 数据记录 `.xlsx`）
- 8 页面完整链路：导入 / 商品画像 / 选品规则 / 预测 / 避坑 / 诊断 / 店铺运营 / 个人 PK

### 修复

- Excel 表头自动定位（`商品SPU ID` 行）
- 列名映射：`毛利润率`、`实际卖价`、`每天销量` 等真实表头
- 毛利率小数 `0.93` → `93%` 统一换算
- 店铺 CTR/CVR 格式识别，无数据显示 `—` 而非 `0.00%`
- 团队数据 OSS 拉取后标准化，诊断页「个人 vs 团队」不再假数据
- OSS Bucket 旧名 `temu-pod-data` 自动迁移至 `temu-shujufenxi-data`
- IIFE 页面隔离、快照格式、PK 页、团队上传等多项 P0/P1 Bug

### 文件

| 文件 | 说明 |
|------|------|
| `temu-dashboard.html` | 主看板 V10 |
| `local_server.py` | 本地静态服务 + OSS 代理 |
| `启动本地看板.bat` | 一键启动（必须用此打开才能 OSS 同步） |

### Git

- 仓库：https://github.com/18ok/temu-PUD
- 分支：`master`

---

## V6 及更早（历史）

- 单文件 HTML + localStorage
- Streamlit 迁移至纯前端
- 六页基础分析（无 OSS / 无店铺 PK）
