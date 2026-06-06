(function () {
    "use strict";

    var prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var bar = document.querySelector(".read-progress");
    if (bar) {
        function onScroll() {
            var doc = document.documentElement;
            var scrollTop = doc.scrollTop || document.body.scrollTop;
            var height = doc.scrollHeight - doc.clientHeight;
            bar.style.width = height > 0 ? (scrollTop / height) * 100 + "%" : "0%";
        }
        window.addEventListener("scroll", onScroll, { passive: true });
        onScroll();
    }

    if (!prefersReduced) {
        var nodes = document.querySelectorAll(".reveal");
        if (nodes.length && "IntersectionObserver" in window) {
            var io = new IntersectionObserver(
                function (entries) {
                    entries.forEach(function (e) {
                        if (e.isIntersecting) {
                            e.target.classList.add("is-visible");
                            io.unobserve(e.target);
                        }
                    });
                },
                { rootMargin: "0px 0px -8% 0px", threshold: 0.05 }
            );
            nodes.forEach(function (n) { io.observe(n); });
        } else {
            nodes.forEach(function (n) { n.classList.add("is-visible"); });
        }
    } else {
        document.querySelectorAll(".reveal").forEach(function (n) {
            n.classList.add("is-visible");
        });
    }
})();
