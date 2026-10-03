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
            // The open phone search row floats over the page; it never pushes content down.
            if (header.classList.contains('is-search-open')) { return; }
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
                var scrolled = window.scrollY > 40;
                if (scrolled !== header.classList.contains('is-scrolled')) {
                    header.classList.toggle('is-scrolled', scrolled);
                    // Let the compact header settle, then update the sticky offset.
                    window.setTimeout(measure, 380);
                }
                var top = document.querySelector('.lot-fab--top');
                if (top) { top.classList.toggle('is-visible', window.scrollY > 600); }
                ticking = false;
            });
        }, { passive: true });
    }

    /* ---------- Announcement bar: rotate highlights ---------- */
    function initRotator() {
        document.querySelectorAll('[data-rotator]').forEach(function (rotator) {
            var items = rotator.children;
            if (items.length < 2 || reduceMotion) { return; }
            var current = 0;
            window.setInterval(function () {
                if (document.hidden) { return; }
                var leaving = items[current];
                leaving.classList.remove('is-active');
                leaving.classList.add('is-leaving');
                window.setTimeout(function () { leaving.classList.remove('is-leaving'); }, 460);
                current = (current + 1) % items.length;
                items[current].classList.add('is-active');
            }, 4000);
        });
    }

    /* ---------- Dropdowns (Help, account) ---------- */
    function initDropdowns() {
        var dds = document.querySelectorAll('.lot-dd');
        function closeAll(except) {
            dds.forEach(function (dd) {
                if (dd === except) { return; }
                dd.classList.remove('is-open');
                var t = dd.querySelector('.lot-dd__toggle');
                if (t) { t.setAttribute('aria-expanded', 'false'); }
            });
        }
        dds.forEach(function (dd) {
            var toggle = dd.querySelector('.lot-dd__toggle');
            if (!toggle) { return; }
            toggle.addEventListener('click', function (e) {
                e.stopPropagation();
                var open = !dd.classList.contains('is-open');
                closeAll(dd);
                dd.classList.toggle('is-open', open);
                toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                if (open) {
                    var first = dd.querySelector('.lot-dd__menu a');
                    if (first && e.detail === 0) { first.focus(); } // opened with the keyboard
                }
            });
        });
        document.addEventListener('click', function (e) {
            if (!e.target.closest('.lot-dd')) { closeAll(null); }
        });
        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape') { return; }
            var open = document.querySelector('.lot-dd.is-open');
            if (open) {
                closeAll(null);
                var t = open.querySelector('.lot-dd__toggle');
                if (t) { t.focus(); }
            }
        });
    }

    /* ---------- Search: phone toggle, "/" shortcut, live suggestions ---------- */
    function initSearch() {
        var header = document.querySelector('.lot-header');
        var form = document.getElementById('lot-search');
        var input = document.getElementById('search_item');
        var panel = document.getElementById('search-suggestions');
        var toggle = document.querySelector('.lot-search-toggle');
        if (!form || !input || !panel) { return; }
        var url = form.getAttribute('data-suggest-url');
        var timer = null;
        var lastQuery = '';
        var active = -1;

        function setSearchOpen(open) {
            header.classList.toggle('is-search-open', open);
            if (toggle) { toggle.setAttribute('aria-expanded', open ? 'true' : 'false'); }
            if (open) { window.setTimeout(function () { input.focus(); }, 50); } else { hide(); }
        }
        if (toggle) {
            toggle.addEventListener('click', function () {
                setSearchOpen(!header.classList.contains('is-search-open'));
            });
        }

        // Press "/" anywhere (outside a text field) to jump to search.
        document.addEventListener('keydown', function (e) {
            if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) { return; }
            var tag = (document.activeElement && document.activeElement.tagName) || '';
            if (/INPUT|TEXTAREA|SELECT/.test(tag) || document.activeElement.isContentEditable) { return; }
            e.preventDefault();
            if (toggle && window.getComputedStyle(toggle).display !== 'none') { setSearchOpen(true); } else { input.focus(); }
        });

        function hide() {
            panel.hidden = true;
            active = -1;
        }
        function options() { return panel.querySelectorAll('[data-option]'); }
        function highlight(index) {
            var opts = options();
            opts.forEach(function (o) { o.classList.remove('is-active'); });
            if (!opts.length) { active = -1; return; }
            active = (index + opts.length) % opts.length;
            opts[active].classList.add('is-active');
            opts[active].scrollIntoView({ block: 'nearest' });
        }
        function esc(v) {
            var d = document.createElement('div');
            d.textContent = v == null ? '' : String(v);
            return d.innerHTML;
        }
        function mark(name, q) {
            var safe = esc(name);
            var i = name.toLowerCase().indexOf(q.toLowerCase());
            if (i < 0) { return safe; }
            return esc(name.slice(0, i)) + '<mark>' + esc(name.slice(i, i + q.length)) + '</mark>' + esc(name.slice(i + q.length));
        }
        function render(items, q) {
            var all = form.getAttribute('action') + '?item=' + encodeURIComponent(q);
            var html = '';
            if (!items.length) {
                html = '<div class="lot-suggest__empty">No products named "' + esc(q) + '" yet. Try searching sizes or categories.</div>';
            }
            items.forEach(function (p, i) {
                html += '<a class="lot-suggest__item" data-option role="option" style="animation-delay:' + (i * 40) + 'ms" href="/details/' + encodeURIComponent(p.details_url) + '/">' +
                    (p.image ? '<img src="' + esc(p.image) + '" alt="">' : '') +
                    '<span class="lot-suggest__text"><span class="lot-suggest__name">' + mark(p.name, q) + '</span>' +
                    (p.size ? '<span class="lot-suggest__meta">Sizes: ' + esc(p.size) + '</span>' : '') + '</span>' +
                    '<span class="lot-suggest__price">&#8358;' + Number(p.price).toLocaleString('en-NG') + '</span></a>';
            });
            html += '<a class="lot-suggest__all" data-option href="' + all + '"><span>See all results for "' + esc(q) + '"</span><i class="fa fa-arrow-right"></i></a>';
            panel.innerHTML = html;
            panel.hidden = false;
            active = -1;
        }

        input.addEventListener('input', function () {
            var q = input.value.trim();
            window.clearTimeout(timer);
            if (!q) { hide(); lastQuery = ''; return; }
            timer = window.setTimeout(function () {
                lastQuery = q;
                fetch(url + '?item=' + encodeURIComponent(q), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        // Ignore responses for an older query.
                        if (q === lastQuery && input.value.trim() === q) { render(data.suggestions || [], q); }
                    })
                    .catch(hide);
            }, 200);
        });
        input.addEventListener('keydown', function (e) {
            if (panel.hidden) { return; }
            if (e.key === 'ArrowDown') { e.preventDefault(); highlight(active + 1); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); highlight(active - 1); }
            else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); options()[active].click(); }
            else if (e.key === 'Escape') { hide(); }
        });
        input.addEventListener('focus', function () {
            if (input.value.trim() && panel.innerHTML) { panel.hidden = false; }
        });
        document.addEventListener('click', function (e) {
            if (!form.contains(e.target)) { hide(); }
            if (header.classList.contains('is-search-open') && !header.contains(e.target)) { setSearchOpen(false); }
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && header.classList.contains('is-search-open')) { setSearchOpen(false); if (toggle) { toggle.focus(); } }
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
            counter.setAttribute('data-count', count);
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

    /* ---------- Content pages ---------- */

    // Numbers count up from zero when they scroll into view.
    function initCounters() {
        var els = document.querySelectorAll('[data-count-to]');
        if (!els.length) { return; }
        function run(el) {
            var target = parseInt(el.getAttribute('data-count-to'), 10) || 0;
            if (reduceMotion || target === 0) { el.textContent = target.toLocaleString('en-NG'); return; }
            var start = null;
            function step(ts) {
                if (!start) { start = ts; }
                var t = Math.min((ts - start) / 1200, 1);
                var eased = 1 - Math.pow(1 - t, 3);
                el.textContent = Math.round(target * eased).toLocaleString('en-NG');
                if (t < 1) { window.requestAnimationFrame(step); }
            }
            window.requestAnimationFrame(step);
        }
        if (!('IntersectionObserver' in window)) { els.forEach(run); return; }
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) { run(entry.target); io.unobserve(entry.target); }
            });
        }, { threshold: 0.6 });
        els.forEach(function (el) { el.textContent = '0'; io.observe(el); });
    }

    // Live "12 / 2000" counter under text areas.
    function initCharCounters() {
        document.querySelectorAll('[data-count-chars]').forEach(function (field) {
            var counter = field.parentElement.querySelector('.lot-field__count');
            if (!counter) { return; }
            var max = field.getAttribute('maxlength');
            var update = function () { counter.textContent = field.value.length + (max ? ' / ' + max : ''); };
            field.addEventListener('input', update);
            update();
        });
    }

    // Spinner on the submit button so people don't double-submit.
    function initLoadingForms() {
        document.querySelectorAll('form[data-loading-form]').forEach(function (form) {
            form.addEventListener('submit', function () {
                if (form.noValidate === false && !form.checkValidity()) { return; }
                var btn = form.querySelector('button[type=submit]');
                if (btn) { btn.classList.add('is-loading'); }
            });
        });
    }

    // FAQ: instant search plus topic filter.
    function initFaq() {
        var list = document.getElementById('faq-list');
        if (!list) { return; }
        var input = document.getElementById('faq-search');
        var empty = document.getElementById('faq-empty');
        var tabs = document.querySelectorAll('#faq-topics [data-topic]');
        var items = list.querySelectorAll('.accordion-item');
        var topic = 'all';
        items.forEach(function (item) {
            var header = item.querySelector('.accordion-header');
            var icon = header.querySelector('i');
            header.setAttribute('data-q', header.textContent.trim());
            item._icon = icon;
        });
        function esc(v) { var d = document.createElement('div'); d.textContent = v; return d.innerHTML; }
        function apply() {
            var q = (input && input.value.trim().toLowerCase()) || '';
            var shown = 0;
            items.forEach(function (item) {
                var header = item.querySelector('.accordion-header');
                var question = header.getAttribute('data-q');
                var text = (question + ' ' + item.querySelector('.accordion-content').textContent).toLowerCase();
                var match = (topic === 'all' || item.getAttribute('data-topic') === topic) && (!q || text.indexOf(q) !== -1);
                item.classList.toggle('is-hidden', !match);
                // Highlight the matching words in the question.
                var i = q ? question.toLowerCase().indexOf(q) : -1;
                header.innerHTML = (i < 0 ? esc(question) : esc(question.slice(0, i)) + '<mark>' + esc(question.slice(i, i + q.length)) + '</mark>' + esc(question.slice(i + q.length))) + ' ';
                header.appendChild(item._icon);
                if (match) {
                    shown += 1;
                    item.classList.add('is-visible');
                }
            });
            if (empty) { empty.classList.toggle('is-shown', shown === 0); }
        }
        if (input) { input.addEventListener('input', apply); }
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function (e) {
                e.preventDefault();
                topic = tab.getAttribute('data-topic');
                tabs.forEach(function (t) {
                    t.classList.toggle('is-active', t === tab);
                    t.setAttribute('aria-selected', t === tab ? 'true' : 'false');
                });
                apply();
            });
        });
    }

    // Policies: numbered sections, table of contents, reading progress and time.
    function initLegal() {
        var article = document.querySelector('[data-legal]');
        if (!article) { return; }
        var sections = article.querySelectorAll('.lot-legal__section');
        var toc = document.querySelector('[data-toc]');
        var list = toc && toc.querySelector('ol');
        var links = [];
        sections.forEach(function (section, i) {
            var h2 = section.querySelector('h2');
            if (!h2) { return; }
            var num = document.createElement('span');
            num.className = 'lot-legal__num';
            num.textContent = i + 1;
            h2.insertBefore(num, h2.firstChild);
            if (list) {
                var li = document.createElement('li');
                var a = document.createElement('a');
                a.href = '#' + section.id;
                a.textContent = h2.textContent.replace(/^\d+/, '').trim();
                li.appendChild(a);
                list.appendChild(li);
                links.push({ a: a, section: section });
            }
        });
        // Collapse the contents list on small screens so the policy text comes first.
        if (toc && window.matchMedia('(max-width: 1100px)').matches) { toc.removeAttribute('open'); }

        var words = article.textContent.trim().split(/\s+/).length;
        var readTime = document.querySelector('[data-read-time]');
        if (readTime) { readTime.textContent = Math.max(1, Math.round(words / 200)) + ' min'; }

        var bar = document.getElementById('lot-progress');
        function onScroll() {
            if (bar) {
                var rect = article.getBoundingClientRect();
                var total = rect.height - window.innerHeight * 0.6;
                var done = Math.min(Math.max(-rect.top + window.innerHeight * 0.2, 0) / Math.max(total, 1), 1);
                bar.style.transform = 'scaleX(' + done + ')';
            }
            var current = null;
            links.forEach(function (l) {
                if (l.section.getBoundingClientRect().top < window.innerHeight * 0.35) { current = l; }
            });
            links.forEach(function (l) {
                var on = l === current;
                l.a.classList.toggle('is-active', on);
                l.section.classList.toggle('is-current', on);
            });
        }
        window.addEventListener('scroll', function () { window.requestAnimationFrame(onScroll); }, { passive: true });
        onScroll();
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
        initRotator();
        initDropdowns();
        initSearch();
        initReveal();
        initImages();
        document.querySelectorAll('[data-carousel]').forEach(initCarousel);
        initSteppers();
        initAccordion();
        initSidebar();
        initCounters();
        initCharCounters();
        initLoadingForms();
        initFaq();
        initLegal();
        initBackToTop();
    });
})();
