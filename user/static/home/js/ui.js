/*
 * LOT Store interface behaviour: header, scroll reveal, carousels, toasts,
 * cart feedback, FAQ accordion and small delights. No dependencies.
 * Exposes window.LOT for page scripts (toast, bumpCart, flyToCart, confetti).
 */
(function () {
    'use strict';

    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var LOT = window.LOT = window.LOT || {};

    function ready(fn) {
        if (document.readyState !== 'loading') { fn(); } else { document.addEventListener('DOMContentLoaded', fn); }
    }

    /* ---------- Header: offset content and compact on scroll ---------- */
    function initHeader() {
        var header = document.querySelector('.header');
        var body = document.getElementById('main-body');
        if (!header) { return; }

        function measure() {
            var h = header.offsetHeight;
            document.documentElement.style.setProperty('--header-h', h + 'px');
            if (body && !header.classList.contains('is-scrolled')) { body.style.paddingTop = h + 'px'; }
        }
        measure();
        window.addEventListener('resize', measure);
        window.addEventListener('load', measure);

        var ticking = false;
        window.addEventListener('scroll', function () {
            if (ticking) { return; }
            ticking = true;
            window.requestAnimationFrame(function () {
                header.classList.toggle('is-scrolled', window.scrollY > 40);
                var top = document.querySelector('.lot-fab--top');
                if (top) { top.classList.toggle('is-visible', window.scrollY > 600); }
                ticking = false;
            });
        }, { passive: true });

        // Highlight the nav link for the current page.
        document.querySelectorAll('nav .items > ul > li > a').forEach(function (a) {
            if (a.getAttribute('href') === window.location.pathname) { a.classList.add('is-current'); }
        });
    }

    /* ---------- Scroll reveal ---------- */
    function initReveal(root) {
        var items = (root || document).querySelectorAll('.reveal:not(.is-visible)');
        if (!items.length) { return; }
        if (reduceMotion || !('IntersectionObserver' in window)) {
            items.forEach(function (el) { el.classList.add('is-visible'); });
            return;
        }
        var observer = new IntersectionObserver(function (entries) {
            var batch = 0;
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) { return; }
                // Stagger elements that appear together so grids cascade in.
                entry.target.style.setProperty('--reveal-delay', Math.min(batch * 70, 420) + 'ms');
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
                batch += 1;
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
        items.forEach(function (el) { observer.observe(el); });
    }

    /* ---------- Product images: fade in once loaded ---------- */
    function initImages() {
        document.querySelectorAll('.lot-card__media img').forEach(function (img) {
            var media = img.parentElement;
            function done() { media.classList.add('is-loaded'); }
            if (img.complete && img.naturalWidth) { done(); } else {
                img.addEventListener('load', done);
                img.addEventListener('error', done);
            }
        });
    }

    /* ---------- Carousels ---------- */
    function initCarousel(el) {
        var slides = el.querySelectorAll('.lot-carousel__slide');
        if (slides.length < 2) {
            if (slides[0]) { slides[0].classList.add('is-active'); }
            return;
        }
        var interval = parseInt(el.getAttribute('data-interval'), 10) || 6000;
        el.style.setProperty('--carousel-interval', interval + 'ms');
        var dotsWrap = el.querySelector('.lot-carousel__dots');
        var dots = [];
        var current = 0;
        var timer = null;

        slides.forEach(function (slide, i) {
            var dot = document.createElement('button');
            dot.type = 'button';
            dot.className = 'lot-carousel__dot';
            dot.setAttribute('aria-label', 'Show slide ' + (i + 1));
            dot.addEventListener('click', function () { go(i); });
            dotsWrap.appendChild(dot);
            dots.push(dot);
        });

        function go(index) {
            slides[current].classList.remove('is-active');
            dots[current].classList.remove('is-active');
            current = (index + slides.length) % slides.length;
            slides[current].classList.add('is-active');
            // Restart the progress animation on the active dot.
            var dot = dots[current];
            dot.classList.remove('is-active');
            void dot.offsetWidth;
            dot.classList.add('is-active');
            restart();
        }
        function restart() {
            window.clearTimeout(timer);
            if (!el.classList.contains('is-paused')) {
                timer = window.setTimeout(function () { go(current + 1); }, interval);
            }
        }
        function pause() { el.classList.add('is-paused'); window.clearTimeout(timer); }
        function resume() { el.classList.remove('is-paused'); restart(); }

        var prev = el.querySelector('.lot-carousel__nav--prev');
        var next = el.querySelector('.lot-carousel__nav--next');
        if (prev) { prev.addEventListener('click', function () { go(current - 1); }); }
        if (next) { next.addEventListener('click', function () { go(current + 1); }); }
        el.addEventListener('mouseenter', pause);
        el.addEventListener('mouseleave', resume);
        document.addEventListener('visibilitychange', function () { if (document.hidden) { pause(); } else { resume(); } });

        // Swipe on touch screens.
        var startX = null;
        el.addEventListener('touchstart', function (e) { startX = e.touches[0].clientX; }, { passive: true });
        el.addEventListener('touchend', function (e) {
            if (startX === null) { return; }
            var dx = e.changedTouches[0].clientX - startX;
            if (Math.abs(dx) > 40) { go(dx < 0 ? current + 1 : current - 1); }
            startX = null;
        });

        slides[0].classList.add('is-active');
        dots[0].classList.add('is-active');
        if (reduceMotion) { el.classList.add('is-paused'); } else { restart(); }
    }

    /* ---------- Toasts ---------- */
    LOT.toast = function (message, options) {
        options = options || {};
        var wrap = document.querySelector('.lot-toasts');
        if (!wrap) {
            wrap = document.createElement('div');
            wrap.className = 'lot-toasts';
            wrap.setAttribute('role', 'status');
            wrap.setAttribute('aria-live', 'polite');
            document.body.appendChild(wrap);
        }
        var toast = document.createElement('div');
        var isError = options.type === 'error';
        toast.className = 'lot-toast' + (isError ? ' lot-toast--error' : '');
        var icon = document.createElement('i');
        icon.className = 'fa ' + (isError ? 'fa-exclamation-circle' : 'fa-check-circle');
        var text = document.createElement('span');
        text.textContent = message;
        toast.appendChild(icon);
        toast.appendChild(text);
        if (options.action) {
            var link = document.createElement('a');
            link.href = options.action.href;
            link.textContent = options.action.label;
            toast.appendChild(link);
        }
        wrap.appendChild(toast);
        window.setTimeout(function () {
            toast.classList.add('is-leaving');
            window.setTimeout(function () { toast.remove(); }, 320);
        }, options.duration || 4000);
    };

    /* ---------- Cart feedback ---------- */
    LOT.bumpCart = function (count) {
        var counter = document.getElementById('cart-count');
        if (counter && typeof count !== 'undefined') {
            counter.textContent = count;
            counter.style.color = 'var(--lot-gold)';
        }
        var sideCount = document.querySelector('[data-side-cart-count]');
        if (sideCount && typeof count !== 'undefined') { sideCount.textContent = count; }
        var link = document.querySelector('.lot-cart-link');
        if (!link || reduceMotion) { return; }
        link.classList.remove('is-bumping');
        void link.offsetWidth;
        link.classList.add('is-bumping');
    };

    // Animate a copy of the product image into the header cart icon.
    LOT.flyToCart = function (img, onDone) {
        var target = document.querySelector('.lot-cart-link');
        if (!img || !target || reduceMotion || !img.animate) { if (onDone) { onDone(); } return; }
        var from = img.getBoundingClientRect();
        var to = target.getBoundingClientRect();
        var size = Math.min(from.width, 160);
        var clone = img.cloneNode();
        clone.className = 'lot-fly';
        clone.removeAttribute('style');
        clone.style.width = size + 'px';
        clone.style.height = size + 'px';
        clone.style.left = (from.left + from.width / 2 - size / 2) + 'px';
        clone.style.top = (from.top + from.height / 2 - size / 2) + 'px';
        document.body.appendChild(clone);
        var dx = to.left + to.width / 2 - (from.left + from.width / 2);
        var dy = to.top + to.height / 2 - (from.top + from.height / 2);
        var anim = clone.animate([
            { transform: 'translate(0, 0) scale(1)', opacity: 1 },
            { transform: 'translate(' + dx * 0.6 + 'px,' + (dy * 0.6 - 60) + 'px) scale(0.5)', opacity: 0.9, offset: 0.6 },
            { transform: 'translate(' + dx + 'px,' + dy + 'px) scale(0.08)', opacity: 0.2 }
        ], { duration: 800, easing: 'cubic-bezier(0.55, 0, 0.3, 1)' });
        anim.onfinish = function () { clone.remove(); if (onDone) { onDone(); } };
    };

    /* ---------- Quantity steppers ---------- */
    function initSteppers() {
        document.querySelectorAll('.lot-stepper').forEach(function (stepper) {
            var input = stepper.querySelector('input');
            stepper.querySelectorAll('button[data-step]').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var min = parseInt(input.min, 10) || 1;
                    var max = parseInt(input.max, 10) || Infinity;
                    var value = (parseInt(input.value, 10) || min) + parseInt(btn.getAttribute('data-step'), 10);
                    input.value = Math.max(min, Math.min(max, value));
                    input.dispatchEvent(new Event('change'));
                });
            });
        });
    }

    /* ---------- FAQ accordion ---------- */
    function initAccordion() {
        document.querySelectorAll('.accordion-item').forEach(function (item) {
            var header = item.querySelector('.accordion-header');
            if (!header) { return; }
            header.addEventListener('click', function () {
                var open = item.classList.toggle('is-open');
                header.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
        });
    }

    /* ---------- Sidebar ---------- */
    function initSidebar() {
        var side = document.querySelector('.lot-side');
        if (!side) { return; }

        // Entrance order for the staggered slide-in.
        side.querySelectorAll('.lot-side__item').forEach(function (item, i) {
            item.style.setProperty('--i', i);
        });

        // Collapsible sections remember whether the visitor closed them.
        side.querySelectorAll('[data-collapsible]').forEach(function (card) {
            var key = 'lot-side-' + card.getAttribute('data-collapsible');
            var button = card.querySelector('.lot-side__title');
            function set(collapsed, save) {
                card.classList.toggle('is-collapsed', collapsed);
                button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                if (save) { try { window.localStorage.setItem(key, collapsed ? '1' : '0'); } catch (e) {} }
            }
            try { if (window.localStorage.getItem(key) === '1') { set(true, false); } } catch (e) {}
            button.addEventListener('click', function () { set(!card.classList.contains('is-collapsed'), true); });
        });

        // Live count of active filters on the "Filter products" header.
        var form = document.getElementById('lot-filter-form');
        var badge = side.querySelector('[data-filter-count]');
        if (form && badge) {
            var update = function () {
                var count = form.querySelectorAll('input[name="size"]:checked').length;
                var cat = form.querySelector('select[name="category-filter"]');
                if (cat && cat.value && cat.value !== '0') { count += 1; }
                ['min-price', 'max-price'].forEach(function (name) {
                    var input = form.querySelector('input[name="' + name + '"]');
                    if (input && input.value.trim() !== '') { count += 1; }
                });
                var text = count ? count + ' active' : '';
                if (badge.textContent !== text) {
                    badge.textContent = text;
                    badge.hidden = !count;
                    badge.style.animation = 'none'; void badge.offsetWidth; badge.style.animation = '';
                }
            };
            form.addEventListener('change', update);
            form.addEventListener('input', update);
            update();
        }
    }

    /* ---------- Back to top ---------- */
    function initBackToTop() {
        var btn = document.querySelector('.lot-fab--top');
        if (!btn) { return; }
        btn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
        });
    }

    /* ---------- Confetti for a successful order ---------- */
    LOT.confetti = function () {
        if (reduceMotion) { return; }
        var canvas = document.createElement('canvas');
        canvas.className = 'lot-confetti';
        document.body.appendChild(canvas);
        var ctx = canvas.getContext('2d');
        var w = canvas.width = window.innerWidth;
        var h = canvas.height = window.innerHeight;
        var colors = ['#cdab4b', '#e6c86e', '#008751', '#3ccf8e', '#ffffff'];
        var pieces = [];
        for (var i = 0; i < 160; i++) {
            pieces.push({
                x: w / 2 + (Math.random() - 0.5) * 120,
                y: h * 0.35,
                vx: (Math.random() - 0.5) * 16,
                vy: Math.random() * -14 - 4,
                size: Math.random() * 7 + 4,
                rot: Math.random() * Math.PI,
                vr: (Math.random() - 0.5) * 0.3,
                color: colors[i % colors.length]
            });
        }
        var start = null;
        function frame(ts) {
            if (!start) { start = ts; }
            var elapsed = ts - start;
            ctx.clearRect(0, 0, w, h);
            pieces.forEach(function (p) {
                p.vy += 0.35;
                p.vx *= 0.99;
                p.x += p.vx;
                p.y += p.vy;
                p.rot += p.vr;
                ctx.save();
                ctx.globalAlpha = Math.max(0, 1 - elapsed / 3200);
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
                ctx.restore();
            });
            if (elapsed < 3200) { window.requestAnimationFrame(frame); } else { canvas.remove(); }
        }
        window.requestAnimationFrame(frame);
    };

    LOT.initReveal = initReveal;

    ready(function () {
        initHeader();
        initReveal();
        initImages();
        document.querySelectorAll('[data-carousel]').forEach(initCarousel);
        initSteppers();
        initAccordion();
        initSidebar();
        initBackToTop();
    });
})();
