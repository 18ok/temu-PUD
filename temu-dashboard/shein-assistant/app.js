const SHEETS = {
  info: "商品信息",
  attrs: "商品属性",
};

const MISSING_RULES = [
  ["spanishName", "西语名"],
  ["descriptionEn", "英文描述"],
  ["sellerSku", "卖家 SKU"],
  ["squareImage", "方块图"],
  ["colorImage", "色块图"],
  ["netWeight", "净重"],
  ["attributes", "属性"],
  ["images", "图片"],
];

const FIELD_LABELS = {
  category: "中文类目",
  mainSpecValue: "规格值",
  subSpecValue1: "规格值",
  itemNo: "货号",
  sellerSku: "卖家 SKU",
  sku: "SKU",
  spu: "SPU",
  skc: "SKC",
  englishName: "英文标题",
  spanishName: "西语标题",
  attributeText: "属性",
  searchText: "全文",
};

const els = {
  fileInput: document.getElementById("fileInput"),
  dropZone: document.getElementById("dropZone"),
  statusLine: document.getElementById("statusLine"),
  importMeta: document.getElementById("importMeta"),
  statsGrid: document.getElementById("statsGrid"),
  searchInput: document.getElementById("searchInput"),
  resetSearchBtn: document.getElementById("resetSearchBtn"),
  resultCount: document.getElementById("resultCount"),
  matchHint: document.getElementById("matchHint"),
  resultsList: document.getElementById("resultsList"),
  detailPane: document.getElementById("detailPane"),
  pendingList: document.getElementById("pendingList"),
  pendingSummary: document.getElementById("pendingSummary"),
  copyPendingBtn: document.getElementById("copyPendingBtn"),
  clearDbBtn: document.getElementById("clearDbBtn"),
};

const db = new Dexie("shein_attribute_library_v1");
db.version(1).stores({
  records: "id, spu, skc, sku, itemNo, sellerSku, category, englishName",
  meta: "key",
});

const ST = {
  records: [],
  groups: [],
  fuse: null,
  selectedId: "",
  meta: null,
  lastResults: [],
};

function clean(value) {
  if (value === null || value === undefined) return "";
  return String(value).replace(/\r\n/g, "\n").trim();
}

function has(value) {
  return clean(value) !== "";
}

function byHeader(row, name) {
  return clean(row[name]);
}

function escapeHtml(value) {
  return clean(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function repairWorksheetRange(sheet) {
  const refs = Object.keys(sheet).filter((key) => key[0] !== "!");
  if (!refs.length) return sheet;
  const range = refs.reduce((acc, ref) => {
    const cell = XLSX.utils.decode_cell(ref);
    acc.s.r = Math.min(acc.s.r, cell.r);
    acc.s.c = Math.min(acc.s.c, cell.c);
    acc.e.r = Math.max(acc.e.r, cell.r);
    acc.e.c = Math.max(acc.e.c, cell.c);
    return acc;
  }, {
    s: { r: Number.MAX_SAFE_INTEGER, c: Number.MAX_SAFE_INTEGER },
    e: { r: 0, c: 0 },
  });
  sheet["!ref"] = XLSX.utils.encode_range(range);
  return sheet;
}

function sheetRows(workbook, sheetName) {
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) throw new Error(`缺少 sheet：${sheetName}`);
  repairWorksheetRange(sheet);
  const table = XLSX.utils.sheet_to_json(sheet, {
    header: 1,
    defval: "",
    blankrows: false,
    raw: false,
  });
  if (table.length < 2) return [];
  const headers = table[0].map(clean);
  return table.slice(1).map((row) => {
    const obj = {};
    headers.forEach((name, index) => {
      if (name) obj[name] = clean(row[index]);
    });
    return obj;
  }).filter((row) => Object.values(row).some(has));
}

function attrKey(spu, skc) {
  return `${clean(spu)}||${clean(skc)}`;
}

function imageList(record) {
  return [
    ["首图", record.mainImage],
    ["方块图", record.squareImage],
    ["色块图", record.colorImage],
    ...record.detailImages.map((url, index) => [`细节图${index + 1}`, url]),
    ["SKU图", record.skuImage],
    ["原图", record.originalImage],
  ].filter(([, url]) => has(url));
}

function checkMissing(record) {
  const missing = [];
  if (!has(record.spanishName)) missing.push("西语名");
  if (!has(record.descriptionEn)) missing.push("英文描述");
  if (!has(record.sellerSku)) missing.push("卖家 SKU");
  if (!has(record.squareImage)) missing.push("方块图");
  if (!has(record.colorImage)) missing.push("色块图");
  if (!has(record.netWeight)) missing.push("净重");
  if (!record.attributes.length) missing.push("属性");
  if (!imageList(record).length) missing.push("图片");
  return missing;
}

function buildCatalog(infoRows, attrRows) {
  const attrMap = new Map();
  attrRows.forEach((row) => {
    const spu = byHeader(row, "SPU");
    const skc = byHeader(row, "SKC");
    const name = byHeader(row, "属性名");
    const value = byHeader(row, "属性值");
    if (!spu && !skc) return;
    const key = attrKey(spu, skc);
    if (!attrMap.has(key)) attrMap.set(key, []);
    if (name || value) attrMap.get(key).push({ name, value });
  });

  const records = infoRows.map((row, index) => {
    const spu = byHeader(row, "SPU");
    const skc = byHeader(row, "SKC");
    const sku = byHeader(row, "SKU");
    const attrs = dedupeAttrs(attrMap.get(attrKey(spu, skc)) || []);
    const detailImages = Array.from({ length: 10 }, (_, i) => byHeader(row, `细节图${i + 1}`)).filter(has);
    const record = {
      id: sku || `${spu}-${skc}-${index}`,
      spu,
      skc,
      sku,
      category: byHeader(row, "末级分类"),
      mainSpecName: byHeader(row, "主规格名"),
      mainSpecValue: byHeader(row, "主规格值"),
      subSpecName1: byHeader(row, "次规格名1"),
      subSpecValue1: byHeader(row, "次规格值1"),
      subSpecName2: byHeader(row, "次规格名2"),
      subSpecValue2: byHeader(row, "次规格值2"),
      brandCode: byHeader(row, "品牌code"),
      brandName: byHeader(row, "品牌名称"),
      brandEnglish: byHeader(row, "品牌名(英文)"),
      englishName: byHeader(row, "默认商品名称(en)"),
      spanishName: byHeader(row, "多语言商品名称(es)"),
      itemNo: byHeader(row, "货号"),
      sellerSku: byHeader(row, "卖家SKU"),
      descriptionEn: byHeader(row, "默认商品描述(en)"),
      descriptionEs: byHeader(row, "多语言商品描述(es)"),
      origin: byHeader(row, "产地"),
      mainImage: byHeader(row, "首图"),
      squareImage: byHeader(row, "方块图"),
      colorImage: byHeader(row, "色块图"),
      detailImages,
      originalImage: byHeader(row, "原图"),
      warehouseId: byHeader(row, "仓库ID"),
      warehouseName: byHeader(row, "仓库名称"),
      stock: byHeader(row, "当前库存"),
      weight: byHeader(row, "重量"),
      weightUnit: byHeader(row, "重量单位"),
      length: byHeader(row, "长"),
      width: byHeader(row, "宽"),
      height: byHeader(row, "高"),
      dimUnit: byHeader(row, "长宽高单位"),
      skuImage: byHeader(row, "SKU图"),
      packaging: byHeader(row, "包装类型"),
      price: byHeader(row, "价格"),
      netWeight: byHeader(row, "净重(手填)"),
      packType: byHeader(row, "件数-类型"),
      packQty: byHeader(row, "件数-数量"),
      packUnit: byHeader(row, "件数-单位"),
      video: byHeader(row, "视频[shein-us]"),
      shopLink: byHeader(row, "商城链接[shein-us]"),
      attributes: attrs,
    };
    record.attributeText = attrs.map((attr) => `${attr.name}:${attr.value}`).join(" ");
    record.imageText = imageList(record).map(([, url]) => url).join(" ");
    record.missing = checkMissing(record);
    record.searchText = [
      record.category,
      record.mainSpecName,
      record.mainSpecValue,
      record.subSpecName1,
      record.subSpecValue1,
      record.subSpecName2,
      record.subSpecValue2,
      record.itemNo,
      record.sellerSku,
      record.sku,
      record.spu,
      record.skc,
      record.englishName,
      record.spanishName,
      record.descriptionEn,
      record.attributeText,
      record.imageText,
    ].filter(has).join(" ");
    return record;
  });

  return {
    records,
    groups: buildGroups(records),
  };
}

function dedupeAttrs(attrs) {
  const seen = new Set();
  return attrs.filter((attr) => {
    const key = `${attr.name}=${attr.value}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return attr.name || attr.value;
  });
}

function buildGroups(records) {
  const spuMap = new Map();
  records.forEach((record) => {
    if (!spuMap.has(record.spu)) {
      spuMap.set(record.spu, {
        spu: record.spu,
        category: record.category,
        title: record.englishName,
        skcs: new Map(),
      });
    }
    const spu = spuMap.get(record.spu);
    if (!spu.skcs.has(record.skc)) {
      spu.skcs.set(record.skc, {
        skc: record.skc,
        mainSpec: record.mainSpecValue,
        attributes: record.attributes,
        skus: [],
      });
    }
    spu.skcs.get(record.skc).skus.push(record);
  });
  return Array.from(spuMap.values()).map((spu) => ({
    ...spu,
    skcs: Array.from(spu.skcs.values()),
  }));
}

function buildFuse() {
  ST.fuse = new Fuse(ST.records, {
    includeMatches: true,
    threshold: 0.36,
    ignoreLocation: true,
    minMatchCharLength: 1,
    keys: [
      { name: "category", weight: 0.9 },
      { name: "mainSpecValue", weight: 0.85 },
      { name: "subSpecValue1", weight: 0.75 },
      { name: "itemNo", weight: 1 },
      { name: "sellerSku", weight: 1 },
      { name: "sku", weight: 1 },
      { name: "spu", weight: 0.8 },
      { name: "skc", weight: 0.8 },
      { name: "englishName", weight: 0.85 },
      { name: "spanishName", weight: 0.55 },
      { name: "attributeText", weight: 0.95 },
      { name: "searchText", weight: 0.35 },
    ],
  });
}

function computeStats(records) {
  const stats = {
    total: records.length,
    spu: new Set(records.map((r) => r.spu)).size,
    skc: new Set(records.map((r) => r.skc)).size,
    sku: new Set(records.map((r) => r.sku)).size,
  };
  MISSING_RULES.forEach(([, label]) => {
    stats[label] = records.filter((record) => record.missing.includes(label)).length;
  });
  return stats;
}

function renderStats() {
  const stats = computeStats(ST.records);
  const cards = [
    ["商品行", stats.total, "SKU 档案"],
    ["SPU", stats.spu, "商品大类"],
    ["SKC", stats.skc, "颜色/图案款式"],
    ["缺西语名", stats["西语名"], "多语言商品名称(es)"],
    ["缺卖家 SKU", stats["卖家 SKU"], "上架跟踪高频项"],
    ["缺方块图", stats["方块图"], "图片完整度"],
    ["缺色块图", stats["色块图"], "图片完整度"],
    ["缺净重", stats["净重"], "净重(手填)"],
  ];
  els.statsGrid.innerHTML = cards.map(([label, value, note]) => `
    <div class="stat-card">
      <strong>${value}</strong>
      <span>${escapeHtml(label)}</span>
      <span>${escapeHtml(note)}</span>
    </div>
  `).join("");
}

function renderResults(results, query) {
  ST.lastResults = results;
  els.resultCount.textContent = `${results.length} 个商品`;
  els.matchHint.textContent = query ? "按匹配度排序" : "显示最近导入";
  els.resultsList.innerHTML = results.slice(0, 120).map((item) => {
    const record = item.item || item;
    const reasons = item.matches ? matchLabels(item.matches) : [];
    const active = record.id === ST.selectedId ? " active" : "";
    return `
      <button class="result-card${active}" type="button" data-id="${escapeHtml(record.id)}">
        <div class="result-title">${escapeHtml(record.englishName || record.itemNo || record.sku)}</div>
        <div class="result-meta">${escapeHtml(record.category || "未分类")} · ${escapeHtml(record.itemNo || "无货号")}</div>
        <div class="result-tags">
          <span class="tag">${escapeHtml(record.mainSpecValue || "无主规格")}</span>
          <span class="tag">${escapeHtml(record.subSpecValue1 || "无尺寸")}</span>
          <span class="${record.missing.length ? "missing-tag" : "ok-tag"}">${record.missing.length ? `缺 ${record.missing.length} 项` : "完整"}</span>
        </div>
        ${reasons.length ? `<div class="match-reasons">匹配：${escapeHtml(reasons.join(" / "))}</div>` : ""}
      </button>
    `;
  }).join("");
}

function matchLabels(matches) {
  return Array.from(new Set(matches.map((match) => FIELD_LABELS[match.key] || match.key))).slice(0, 4);
}

function selectRecord(id) {
  const record = ST.records.find((item) => item.id === id);
  if (!record) return;
  ST.selectedId = id;
  renderDetail(record);
  renderResults(ST.lastResults.length ? ST.lastResults : ST.records, els.searchInput.value.trim());
}

function renderDetail(record) {
  const thumb = record.mainImage || record.squareImage || record.skuImage;
  els.detailPane.innerHTML = `
    <div class="record-head">
      ${thumb ? `<img class="thumb" src="${escapeHtml(thumb)}" alt="">` : `<div class="thumb thumb-fallback">无图片</div>`}
      <div>
        <div class="record-title">
          <h2>${escapeHtml(record.englishName || record.itemNo || record.sku)}</h2>
          <div class="record-actions">
            <button class="primary-btn" type="button" data-copy="core">复制核心信息</button>
            <button class="ghost-btn" type="button" data-copy="missing">复制缺失项</button>
          </div>
        </div>
        <div class="meta-line">${escapeHtml(record.category || "未分类")} · ${escapeHtml(record.itemNo || "无货号")} · ${escapeHtml(record.sellerSku || "无卖家 SKU")}</div>
        <div class="meta-line">SPU ${escapeHtml(record.spu)} / SKC ${escapeHtml(record.skc)} / SKU ${escapeHtml(record.sku)}</div>
        <div class="missing-tags">${missingHtml(record)}</div>
      </div>
    </div>

    <div class="field-grid">
      ${fieldHtml("西语名", record.spanishName || "缺失")}
      ${fieldHtml("规格", specText(record))}
      ${fieldHtml("重量", weightText(record))}
      ${fieldHtml("长宽高", dimText(record))}
      ${fieldHtml("库存", record.stock || "缺失")}
      ${fieldHtml("价格", record.price || "缺失")}
      ${fieldHtml("仓库", [record.warehouseId, record.warehouseName].filter(has).join(" / ") || "缺失")}
      ${fieldHtml("包装", record.packaging || "缺失")}
    </div>

    <div class="content-block">
      <h3>英文描述</h3>
      <div class="description">${escapeHtml(record.descriptionEn || "缺失")}</div>
    </div>

    <div class="content-block">
      <h3>属性列表</h3>
      <div class="attr-list">${attrHtml(record.attributes)}</div>
    </div>

    <div class="content-block">
      <h3>图片链接</h3>
      <div class="image-links">${imageLinkHtml(record)}</div>
    </div>

    <div class="content-block">
      <h3>SPU - SKC - SKU</h3>
      <div class="description">${escapeHtml(hierarchyText(record))}</div>
    </div>
  `;
}

function fieldHtml(label, value) {
  return `<div class="field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function missingHtml(record) {
  if (!record.missing.length) return `<span class="ok-tag">无缺失项</span>`;
  return record.missing.map((item) => `<span class="missing-tag">${escapeHtml(item)}</span>`).join("");
}

function attrHtml(attrs) {
  if (!attrs.length) return `<span class="missing-note">缺失属性</span>`;
  return attrs.map((attr) => `<span class="tag">${escapeHtml(attr.name)}：${escapeHtml(attr.value)}</span>`).join("");
}

function imageLinkHtml(record) {
  const links = imageList(record);
  if (!links.length) return `<span class="missing-note">缺失图片</span>`;
  return links.map(([label, url]) => `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(label)}：${escapeHtml(url)}</a>`).join("");
}

function specText(record) {
  return [
    [record.mainSpecName, record.mainSpecValue].filter(has).join("："),
    [record.subSpecName1, record.subSpecValue1].filter(has).join("："),
    [record.subSpecName2, record.subSpecValue2].filter(has).join("："),
  ].filter(has).join(" / ") || "缺失";
}

function weightText(record) {
  return [record.weight, record.weightUnit].filter(has).join(" ") || "缺失";
}

function dimText(record) {
  const dims = [record.length, record.width, record.height].filter(has).join(" x ");
  return dims ? `${dims} ${record.dimUnit}`.trim() : "缺失";
}

function hierarchyText(record) {
  const group = ST.groups.find((item) => item.spu === record.spu);
  if (!group) return `${record.spu} -> ${record.skc} -> ${record.sku}`;
  return [
    `SPU ${group.spu}（${group.category || "未分类"}）`,
    ...group.skcs.map((skc) => `  SKC ${skc.skc}（${skc.mainSpec || "无主规格"}）：${skc.skus.map((sku) => sku.sku).join("、")}`),
  ].join("\n");
}

function renderPending() {
  const pending = ST.records.filter((record) => record.missing.length);
  els.pendingSummary.textContent = `${pending.length} 个商品有待补项`;
  els.pendingList.innerHTML = pending.slice(0, 80).map((record) => `
    <div class="pending-item">
      <strong>${escapeHtml(record.itemNo || record.sku || record.spu)}</strong>
      <div class="missing-tags">${missingHtml(record)}</div>
      <div class="meta-line">${escapeHtml(record.category || "未分类")} · ${escapeHtml(record.mainSpecValue || "")} ${escapeHtml(record.subSpecValue1 || "")}</div>
      <button class="ghost-btn" type="button" data-copy-missing-id="${escapeHtml(record.id)}">复制这一条</button>
    </div>
  `).join("") || `<div class="empty-state">没有待补项</div>`;
}

function search() {
  const query = els.searchInput.value.trim();
  if (!query) {
    const rows = ST.records.slice(0, 120);
    renderResults(rows, "");
    if (!ST.selectedId && rows[0]) selectRecord(rows[0].id);
    return;
  }
  const results = ST.fuse ? ST.fuse.search(query, { limit: 120 }) : [];
  renderResults(results, query);
  if (results[0]) selectRecord(results[0].item.id);
}

async function handleFile(file) {
  if (!file) return;
  setStatus(`正在读取：${file.name}`);
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, {
    type: "array",
    cellDates: false,
    dense: false,
    nodim: true,
  });
  const infoRows = sheetRows(workbook, SHEETS.info);
  const attrRows = sheetRows(workbook, SHEETS.attrs);
  const catalog = buildCatalog(infoRows, attrRows);
  const meta = {
    key: "lastImport",
    fileName: file.name,
    importedAt: new Date().toISOString(),
    infoRows: infoRows.length,
    attrRows: attrRows.length,
  };
  await saveCatalog(catalog.records, meta);
  applyCatalog(catalog.records, meta);
  toast(`已导入 ${catalog.records.length} 个 SKU 档案`);
}

async function saveCatalog(records, meta) {
  await db.transaction("rw", db.records, db.meta, async () => {
    await db.records.clear();
    await db.records.bulkAdd(records);
    await db.meta.put(meta);
  });
}

async function loadCatalog() {
  const records = await db.records.toArray();
  const meta = await db.meta.get("lastImport");
  applyCatalog(records, meta || null);
}

function applyCatalog(records, meta) {
  ST.records = records;
  ST.groups = buildGroups(records);
  ST.meta = meta;
  ST.selectedId = records[0]?.id || "";
  buildFuse();
  renderStats();
  renderImportMeta();
  renderPending();
  search();
  if (ST.selectedId) renderDetail(ST.records.find((record) => record.id === ST.selectedId));
  else els.detailPane.innerHTML = `<div class="empty-state">导入后选择一个商品查看档案</div>`;
}

function renderImportMeta() {
  if (!ST.meta || !ST.records.length) {
    setStatus("等待导入希音商品列表模板");
    els.importMeta.textContent = "未导入";
    return;
  }
  const date = new Date(ST.meta.importedAt);
  setStatus(`已载入本地属性库：${ST.records.length} 个 SKU，${ST.groups.length} 个 SPU`);
  els.importMeta.innerHTML = `${escapeHtml(ST.meta.fileName)}<br>${date.toLocaleString()}<br>商品 ${ST.meta.infoRows} 行 / 属性 ${ST.meta.attrRows} 行`;
}

function setStatus(text) {
  els.statusLine.textContent = text;
}

function coreText(record) {
  return [
    `英文名：${record.englishName}`,
    `西语名：${record.spanishName || "缺失"}`,
    `描述：${record.descriptionEn || "缺失"}`,
    `类目：${record.category}`,
    `SPU：${record.spu}`,
    `SKC：${record.skc}`,
    `SKU：${record.sku}`,
    `货号：${record.itemNo}`,
    `卖家SKU：${record.sellerSku || "缺失"}`,
    `规格：${specText(record)}`,
    `重量：${weightText(record)}`,
    `长宽高：${dimText(record)}`,
    `库存：${record.stock || "缺失"}`,
    `价格：${record.price || "缺失"}`,
    `图片：${imageList(record).map(([label, url]) => `${label}=${url}`).join("\n") || "缺失"}`,
    `属性：${record.attributes.map((attr) => `${attr.name}=${attr.value}`).join("；") || "缺失"}`,
  ].join("\n");
}

function missingText(record) {
  return [
    `${record.itemNo || record.sku || record.spu}`,
    `SPU：${record.spu}`,
    `SKC：${record.skc}`,
    `SKU：${record.sku}`,
    `待补：${record.missing.join("、") || "无"}`,
  ].join("\n");
}

function allPendingText() {
  return ST.records
    .filter((record) => record.missing.length)
    .map(missingText)
    .join("\n\n");
}

async function copyText(text) {
  if (!text) {
    toast("没有可复制内容");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  toast("已复制");
}

function toast(text) {
  const old = document.querySelector(".toast");
  if (old) old.remove();
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = text;
  document.body.appendChild(node);
  window.setTimeout(() => node.remove(), 1800);
}

async function clearDb() {
  await db.transaction("rw", db.records, db.meta, async () => {
    await db.records.clear();
    await db.meta.clear();
  });
  applyCatalog([], null);
  toast("本地属性库已清空");
}

els.fileInput.addEventListener("change", (event) => handleFile(event.target.files[0]));
els.searchInput.addEventListener("input", search);
els.resetSearchBtn.addEventListener("click", () => {
  els.searchInput.value = "";
  search();
});
els.resultsList.addEventListener("click", (event) => {
  const card = event.target.closest("[data-id]");
  if (card) selectRecord(card.dataset.id);
});
els.detailPane.addEventListener("click", (event) => {
  const btn = event.target.closest("[data-copy]");
  if (!btn) return;
  const record = ST.records.find((item) => item.id === ST.selectedId);
  if (!record) return;
  copyText(btn.dataset.copy === "core" ? coreText(record) : missingText(record));
});
els.pendingList.addEventListener("click", (event) => {
  const btn = event.target.closest("[data-copy-missing-id]");
  if (!btn) return;
  const record = ST.records.find((item) => item.id === btn.dataset.copyMissingId);
  if (record) copyText(missingText(record));
});
els.copyPendingBtn.addEventListener("click", () => copyText(allPendingText()));
els.clearDbBtn.addEventListener("click", clearDb);

["dragenter", "dragover"].forEach((name) => {
  els.dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    els.dropZone.classList.add("dragging");
  });
});
["dragleave", "drop"].forEach((name) => {
  els.dropZone.addEventListener(name, (event) => {
    event.preventDefault();
    els.dropZone.classList.remove("dragging");
  });
});
els.dropZone.addEventListener("drop", (event) => handleFile(event.dataTransfer.files[0]));

loadCatalog().catch((error) => {
  console.error(error);
  setStatus(`本地库读取失败：${error.message}`);
});
