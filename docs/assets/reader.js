(function () {
    "use strict";

    var STORAGE_HOME = "xj-home-scroll";
    var STORAGE_LAST = "xj-last-reader-id";
    var STORAGE_SCROLL_PREFIX = "xj-reader-scroll-";

    var readerEl = document.getElementById("reader");
    if (!readerEl) return;

    var backdrop = readerEl.querySelector(".reader__backdrop");
    var backBtn = readerEl.querySelector(".reader__back");
    var scrollEl = readerEl.querySelector(".reader__scroll");
    var contentEl = readerEl.querySelector(".reader__content");
    var progressEl = readerEl.querySelector(".reader__progress");
    var hintEl = readerEl.querySelector(".reader__backdrop-hint");

    var manifest = null;
    var contentMap = {};
    var isOpen = false;
    var currentId = null;
    var backdropReadyAt = 0;
    var backdropConfirmUntil = 0;
    var hintTimer = null;

    function loadManifest() {
        if (manifest) return Promise.resolve(manifest);
        return fetch("data/manifest.json")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                manifest = data;
                (data.interviews || []).forEach(function (item) {
                    if (item.content) contentMap[item.id] = item.content;
                });
                (data.briefs || []).forEach(function (item) {
                    if (item.content) contentMap[item.id] = item.content;
                });
                (data.tools || []).forEach(function (item) {
                    if (item.content) contentMap[item.id] = item.content;
                });
                return manifest;
            })
            .catch(function () {
                contentMap = {
                    "interview-01": "content/interview-01.html",
                    "brief-01": "content/brief-01.html",
                    "brief-02": "content/brief-02.html",
                    "calculator": "content/calculator.html"
                };
                return null;
            });
    }

    function saveHomeScroll() {
        sessionStorage.setItem(STORAGE_HOME, String(window.scrollY || 0));
    }

    function restoreHomeScroll() {
        var y = parseInt(sessionStorage.getItem(STORAGE_HOME) || "0", 10);
        requestAnimationFrame(function () {
            window.scrollTo(0, y);
        });
    }

    function saveReaderScroll(id) {
        if (!scrollEl || !id) return;
        sessionStorage.setItem(STORAGE_SCROLL_PREFIX + id, String(scrollEl.scrollTop || 0));
    }

    function restoreReaderScroll(id) {
        var y = parseInt(sessionStorage.getItem(STORAGE_SCROLL_PREFIX + id) || "0", 10);
        scrollEl.scrollTop = y;
        updateProgress();
    }

    function highlightLastRead(id) {
        document.querySelectorAll(".article-list__item.is-last-read, .brief-list__item.is-last-read").forEach(function (el) {
            el.classList.remove("is-last-read");
        });
        if (!id) return;
        var row = document.querySelector('[data-reader-row="' + id + '"]');
        if (row) row.classList.add("is-last-read");
    }

    function updateProgress() {
        if (!progressEl || !scrollEl) return;
        var max = scrollEl.scrollHeight - scrollEl.clientHeight;
        progressEl.style.width = max > 0 ? (scrollEl.scrollTop / max) * 100 + "%" : "0%";
    }

    function initCalculator(root) {
        var cost = root.querySelector("#calc-cost");
        var price = root.querySelector("#calc-price");
        var fees = root.querySelector("#calc-fees");
        var result = root.querySelector("#calc-result");
        if (!cost || !price || !fees || !result) return;

        function fmt(n) {
            return (Math.round(n * 1000) / 10).toFixed(1);
        }

        function recalc() {
            var c = parseFloat(cost.value) || 0;
            var p = parseFloat(price.value) || 0;
            var f = parseFloat(fees.value) || 0;
            if (p <= 0) {
                result.innerHTML = "粗算毛利率：—<small>售价须大于 0</small>";
                return;
            }
            var margin = ((p - c - f) / p) * 100;
            var label = margin < 15 ? "偏低，建议复核运费与活动" : margin < 25 ? "中等，建议对照你的底线" : "粗看尚可，仍需核完整成本";
            result.innerHTML = "粗算毛利率：" + fmt(margin) + "%<small>" + label + " · 公式：(售价 − 采购价 − 费用) ÷ 售价</small>";
        }

        [cost, price, fees].forEach(function (el) {
            el.addEventListener("input", recalc);
        });
        recalc();
    }

    function scrollToHash(hash) {
        if (!hash || !scrollEl) return;
        var safe = hash.replace(/[^a-zA-Z0-9_-]/g, "");
        var target = contentEl.querySelector("#" + safe);
        if (!target) return;
        var panelRect = scrollEl.getBoundingClientRect();
        var targetRect = target.getBoundingClientRect();
        var top = scrollEl.scrollTop + (targetRect.top - panelRect.top) - 12;
        scrollEl.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    }

    function bindInnerActions() {
        contentEl.querySelectorAll("[data-reader-open]").forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                var nextId = btn.getAttribute("data-reader-open");
                var hash = btn.getAttribute("data-reader-hash") || "";
                if (currentId) saveReaderScroll(currentId);
                open(nextId, hash, true);
            });
        });
    }

    function open(id, hash, fromSwitch) {
        if (!id || !contentMap[id]) return;

        loadManifest().then(function () {
            var path = contentMap[id];
            if (!path) return;

            if (!isOpen) {
                saveHomeScroll();
            } else if (currentId && currentId !== id) {
                saveReaderScroll(currentId);
            }

            return fetch(path)
                .then(function (r) { return r.text(); })
                .then(function (html) {
                    contentEl.innerHTML = html;
                    currentId = id;
                    isOpen = true;
                    sessionStorage.setItem(STORAGE_LAST, id);

                    readerEl.hidden = false;
                    readerEl.setAttribute("aria-hidden", "false");
                    document.body.classList.add("reader-open");
                    backdropReadyAt = Date.now() + 400;
                    backdropConfirmUntil = 0;
                    hideBackdropHint();

                    if (fromSwitch) {
                        scrollEl.scrollTop = 0;
                    } else {
                        restoreReaderScroll(id);
                    }
                    updateProgress();

                    bindInnerActions();
                    if (id === "calculator") initCalculator(contentEl);

                    if (hash) {
                        setTimeout(function () { scrollToHash(hash); }, 80);
                    }

                    highlightLastRead(id);
                    history.replaceState(null, "", "#read/" + id);
                });
        });
    }

    function close() {
        if (!isOpen) return;
        if (currentId) saveReaderScroll(currentId);

        readerEl.hidden = true;
        readerEl.setAttribute("aria-hidden", "true");
        document.body.classList.remove("reader-open");
        isOpen = false;
        hideBackdropHint();

        highlightLastRead(currentId);
        restoreHomeScroll();

        if (location.hash.indexOf("#read/") === 0) {
            history.replaceState(null, "", location.pathname + location.search);
        }
    }

    function hideBackdropHint() {
        if (!hintEl) return;
        hintEl.hidden = true;
        if (hintTimer) {
            clearTimeout(hintTimer);
            hintTimer = null;
        }
    }

    function showBackdropHint() {
        if (!hintEl) return;
        hintEl.hidden = false;
        if (hintTimer) clearTimeout(hintTimer);
        hintTimer = setTimeout(hideBackdropHint, 2800);
    }

    function onBackdropClick(e) {
        if (e.target !== backdrop) return;
        if (Date.now() < backdropReadyAt) return;

        if (Date.now() < backdropConfirmUntil) {
            close();
            return;
        }

        backdropConfirmUntil = Date.now() + 3000;
        showBackdropHint();
    }

    function parseHash() {
        var h = location.hash || "";
        var m = h.match(/^#read\/([^/#]+)/);
        if (!m) return null;
        var id = decodeURIComponent(m[1]);
        var hash = "";
        var parts = h.split("#");
        if (parts.length > 2) hash = parts[parts.length - 1];
        return { id: id, anchor: hash };
    }

    function bindTriggers() {
        document.addEventListener("click", function (e) {
            var trigger = e.target.closest("[data-reader-open]");
            if (!trigger) return;
            if (trigger.getAttribute("data-reader-disabled") === "true") return;
            e.preventDefault();
            var id = trigger.getAttribute("data-reader-open");
            var hash = trigger.getAttribute("data-reader-hash") || "";
            open(id, hash, false);
        });
    }

    backBtn.addEventListener("click", close);
    backdrop.addEventListener("click", onBackdropClick);
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && isOpen) close();
    });
    scrollEl.addEventListener("scroll", updateProgress, { passive: true });

    bindTriggers();

    window.Reader = { open: open, close: close };

    loadManifest().then(function () {
        var parsed = parseHash();
        if (parsed) open(parsed.id, parsed.anchor, false);
    });
})();
