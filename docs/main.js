/* uPtt marketing site — progressive enhancement only; the page reads fine without it. */
(() => {
    'use strict';

    const doc = document.documentElement;
    const zh = (doc.lang || '').toLowerCase().startsWith('zh');
    const T = zh ? {
        copied: '已複製', copy: '複製',
        menuOpen: '開啟選單', menuClose: '關閉選單',
        dlMac: '下載 macOS 版', dlWin: '下載 Windows 版', dl: '免費下載',
        latest: (tag, date) => `最新版本 ${tag} ・ ${date} 發佈`,
        notes: '更新紀錄', pre: '預覽版：',
        termIdle: 'uPtt 已連線 ptt.cc，等待新訊息',
        termParse: (n) => `uPtt 解析中 ... ${n}/4`,
        termDone: '4 則 uPtt 訊息已收下，並從信箱刪除',
        parsed: '✓ 已解析',
        states: ['線上', '離線', '未知'],
    } : {
        copied: 'Copied', copy: 'Copy',
        menuOpen: 'Open menu', menuClose: 'Close menu',
        dlMac: 'Download for macOS', dlWin: 'Download for Windows', dl: 'Download free',
        latest: (tag, date) => `Latest ${tag} · released ${date}`,
        notes: 'Release notes', pre: 'Preview builds: ',
        termIdle: 'uPtt connected to ptt.cc, waiting',
        termParse: (n) => `uPtt parsing ... ${n}/4`,
        termDone: '4 uPtt messages received and removed',
        parsed: '✓ parsed',
        states: ['online', 'offline', 'unknown'],
    };

    const $ = (s, r = document) => r.querySelector(s);
    const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
    const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
    const lerp = (a, b, t) => a + (b - a) * t;
    const ease = (t) => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    const smooth = (a, b, t) => { const x = clamp((t - a) / (b - a)); return x * x * (3 - 2 * x); };
    const mqReduce = matchMedia('(prefers-reduced-motion: reduce)');
    let reduce = mqReduce.matches;
    mqReduce.addEventListener?.('change', (e) => { reduce = e.matches; });
    const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

    /* ------------------------------------------------------------ theme */
    const THEME_COLOR = { graphite: '#0E1114', bone: '#F3F5F5', kraft: '#E9E3D6' };
    const themeListeners = [];
    function syncThemeUI() {
        const t = doc.getAttribute('data-theme');
        $$('[data-theme-set]').forEach((b) => {
            const on = String(b.dataset.themeSet === t);
            b.setAttribute(b.getAttribute('role') === 'radio' ? 'aria-checked' : 'aria-pressed', on);
        });
        $$('meta[name="theme-color"]').forEach((m) => m.setAttribute('content', THEME_COLOR[t]));
        themeListeners.forEach((fn) => fn(t));
    }
    function setTheme(t) {
        doc.setAttribute('data-theme', t);
        try { localStorage.setItem('uptt-theme', t); } catch (e) { /* storage blocked */ }
        syncThemeUI();
    }
    $$('[data-theme-set]').forEach((b) => b.addEventListener('click', () => setTheme(b.dataset.themeSet)));
    // radio-group arrow keys
    const radios = $$('.theme-switch [role="radio"]');
    radios.forEach((b, i) => b.addEventListener('keydown', (e) => {
        const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
        if (!d) return;
        e.preventDefault();
        const n = radios[(i + d + radios.length) % radios.length];
        n.focus(); n.click();
    }));
    syncThemeUI();
    radios.forEach((b) => { b.tabIndex = b.getAttribute('aria-checked') === 'true' ? 0 : -1; });
    themeListeners.push(() => radios.forEach((b) => { b.tabIndex = b.getAttribute('aria-checked') === 'true' ? 0 : -1; }));

    /* ------------------------------------------------------------ load-in */
    // start the intro right away; webfonts swap in underneath without blocking first paint
    requestAnimationFrame(() => document.body.classList.add('is-loaded'));

    /* ------------------------------------------------------------ nav */
    const nav = $('#nav');
    const burger = $('.nav-burger');
    let lastY = scrollY;
    function onNavScroll() {
        const y = scrollY;
        nav.classList.toggle('is-scrolled', y > 8);
        const open = nav.classList.contains('is-open');
        if (!open) nav.classList.toggle('is-hidden', y > lastY && y > 480);
        lastY = y;
        const max = doc.scrollHeight - innerHeight;
        nav.style.setProperty('--progress', max > 0 ? (y / max).toFixed(4) : 0);
    }
    function setMenu(open) {
        nav.classList.toggle('is-open', open);
        burger.setAttribute('aria-expanded', String(open));
        burger.setAttribute('aria-label', open ? T.menuClose : T.menuOpen);
        document.body.style.overflow = open ? 'hidden' : '';
    }
    burger.addEventListener('click', () => setMenu(!nav.classList.contains('is-open')));
    $$('.nav-links a').forEach((a) => a.addEventListener('click', () => setMenu(false)));
    addEventListener('keydown', (e) => { if (e.key === 'Escape' && nav.classList.contains('is-open')) { setMenu(false); burger.focus(); } });

    // highlight the section in view
    const navMap = new Map($$('.nav-links a[href^="#"]').map((a) => [a.getAttribute('href').slice(1), a]));
    if ('IntersectionObserver' in window) {
        const so = new IntersectionObserver((entries) => {
            entries.forEach((en) => {
                const a = navMap.get(en.target.id);
                if (a && en.isIntersecting) {
                    navMap.forEach((x) => x.removeAttribute('aria-current'));
                    a.setAttribute('aria-current', 'true');
                }
            });
        }, { rootMargin: '-45% 0px -50% 0px' });
        navMap.forEach((_, id) => { const el = document.getElementById(id); if (el) so.observe(el); });
    }

    /* ------------------------------------------------------------ reveal */
    const reveals = $$('.reveal');
    if ('IntersectionObserver' in window && !reduce) {
        const ro = new IntersectionObserver((entries) => {
            entries.forEach((en) => {
                if (en.isIntersecting) { en.target.classList.add('is-in'); ro.unobserve(en.target); }
            });
        }, { rootMargin: '0px 0px -8% 0px', threshold: 0.01 });
        reveals.forEach((el) => ro.observe(el));
    } else {
        reveals.forEach((el) => el.classList.add('is-in'));
    }

    /* ------------------------------------------------------------ copy */
    async function copyText(text) {
        try { await navigator.clipboard.writeText(text); return true; } catch (e) {
            const ta = document.createElement('textarea');
            ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
            document.body.appendChild(ta); ta.select();
            let ok = false; try { ok = document.execCommand('copy'); } catch (_) { /* noop */ }
            ta.remove(); return ok;
        }
    }
    const live = document.createElement('div');
    live.className = 'sr-only'; live.setAttribute('aria-live', 'polite');
    document.body.appendChild(live);
    function flashCopied(btn) {
        btn.classList.add('is-copied');
        const use = btn.querySelector('.copy-icon use, .go use');
        if (use) use.setAttribute('href', '#i-check');
        if (btn.matches('.shell-bar button')) btn.textContent = T.copied;
        live.textContent = T.copied;
        clearTimeout(btn._t);
        btn._t = setTimeout(() => {
            btn.classList.remove('is-copied');
            if (use) use.setAttribute('href', '#i-copy');
            if (btn.matches('.shell-bar button')) btn.textContent = T.copy;
        }, 1800);
    }
    $$('[data-copy]').forEach((b) => b.addEventListener('click', async () => { if (await copyText(b.dataset.copy)) flashCopied(b); }));
    $$('[data-copy-from]').forEach((b) => b.addEventListener('click', async () => {
        const src = document.getElementById(b.dataset.copyFrom);
        const cmds = src.textContent.split('\n').filter((l) => l.startsWith('❯ ')).map((l) => l.slice(2)).join('\n');
        if (await copyText(cmds)) flashCopied(b);
    }));

    /* ------------------------------------------------------------ OS + release */
    const ua = navigator.userAgent;
    const os = /Windows/.test(ua) ? 'win' : (/Macintosh|Mac OS X/.test(ua) && !/iPhone|iPad/.test(ua)) ? 'mac' : null;
    if (os) {
        const card = $(`.dl-card[data-os="${os}"]`);
        if (card) {
            card.classList.add('is-yours');
            card.parentElement.prepend(card);
        }
        const label = $('[data-os-label]');
        if (label) label.textContent = os === 'mac' ? T.dlMac : T.dlWin;
    }

    const relLine = $('[data-release]');
    if (relLine && 'fetch' in window) {
        fetch('https://api.github.com/repos/uPtt-messenger/uPtt-app/releases?per_page=8', { headers: { Accept: 'application/vnd.github+json' } })
            .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
            .then((list) => {
                const rel = list.find((r) => !r.draft);
                if (!rel) return;
                const date = new Date(rel.published_at).toLocaleDateString(zh ? 'zh-TW' : 'en-US', { year: 'numeric', month: 'short', day: 'numeric' });
                const pick = (re) => (rel.assets || []).find((a) => re.test(a.name));
                const assets = { mac: pick(/mac|darwin|osx/i), win: pick(/win|setup|\.exe/i) };
                Object.entries(assets).forEach(([k, a]) => {
                    const card = $(`.dl-card[data-os="${k}"]`);
                    if (!card) return;
                    card.href = a ? a.browser_download_url : rel.html_url;
                    if (a) card.removeAttribute('target');
                });
                const cta = $('[data-os-cta]');
                if (cta && os && assets[os]) cta.href = assets[os].browser_download_url;
                relLine.textContent = '';
                const s = document.createElement('span');
                s.textContent = T.latest(rel.tag_name, date) + ' ・ ';
                const a = document.createElement('a');
                a.href = rel.html_url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = T.notes;
                relLine.append(s, a);
            })
            .catch(() => { /* keep the static fallback line */ });
    }

    /* ------------------------------------------------------------ modifier glyphs */
    if (!isMac) $$('[data-mod]').forEach((k) => { k.textContent = 'Ctrl'; });
    if (!isMac) $$('.app-search kbd').forEach((k) => { k.textContent = 'Ctrl K'; });

    /* ------------------------------------------------------------ hero glyph field */
    const canvas = $('.glyph-field');
    if (canvas && canvas.getContext) {
        const ctx = canvas.getContext('2d');
        const GLYPHS = '站內信水球推噓→※◆★□＋uPtt01:/<>[]#=~'.split('');
        const CELL = 22;
        let W = 0, H = 0, cols = 0, rows = 0, grid = [], dpr = 1;
        let mx = -9999, my = -9999, visible = true, raf = 0, last = 0;
        let colFaint = '#5D6570', colAccent = '#8FBFA0';
        const readColors = () => {
            const cs = getComputedStyle(doc);
            colFaint = cs.getPropertyValue('--faint').trim() || colFaint;
            colAccent = cs.getPropertyValue('--accent').trim() || colAccent;
        };
        const size = () => {
            const r = canvas.getBoundingClientRect();
            dpr = Math.min(2, devicePixelRatio || 1);
            W = r.width; H = r.height;
            canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            cols = Math.ceil(W / CELL); rows = Math.ceil(H / CELL);
            grid = Array.from({ length: cols * rows }, () => ({
                g: GLYPHS[(Math.random() * GLYPHS.length) | 0],
                a: Math.random() < 0.72 ? 0 : 0.08 + Math.random() * 0.2,
                h: 0,
            }));
            draw(0, true);
        };
        function draw(now, force) {
            if (!force && now - last < 40) return;
            last = now;
            ctx.clearRect(0, 0, W, H);
            ctx.font = `500 12px "JetBrains Mono", ui-monospace, monospace`;
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            const R = 170;
            for (let y = 0; y < rows; y++) {
                for (let x = 0; x < cols; x++) {
                    const c = grid[y * cols + x];
                    const px = x * CELL + CELL / 2, py = y * CELL + CELL / 2;
                    const d = Math.hypot(px - mx, py - my);
                    const near = d < R ? 1 - d / R : 0;
                    if (!reduce && near > 0.35 && Math.random() < 0.08) c.g = GLYPHS[(Math.random() * GLYPHS.length) | 0];
                    if (!reduce && Math.random() < 0.0015) {
                        c.g = GLYPHS[(Math.random() * GLYPHS.length) | 0];
                        c.h = 1;
                    }
                    c.h *= 0.94;
                    const alpha = Math.max(c.a, near * 0.9, c.h * 0.7);
                    if (alpha < 0.03) continue;
                    ctx.globalAlpha = alpha;
                    ctx.fillStyle = near > 0.2 || c.h > 0.3 ? colAccent : colFaint;
                    ctx.fillText(c.g, px, py);
                }
            }
            ctx.globalAlpha = 1;
        }
        // touch devices get a still field: no pointer to react to, and it saves battery
        const animated = () => !reduce && matchMedia('(pointer: fine)').matches;
        const loop = (now) => { draw(now); raf = visible && animated() ? requestAnimationFrame(loop) : 0; };
        readColors(); size();
        themeListeners.push(() => { readColors(); draw(0, true); });
        if (document.fonts) document.fonts.ready.then(() => draw(0, true));
        let rs; addEventListener('resize', () => { clearTimeout(rs); rs = setTimeout(size, 150); });
        const hero = $('.hero');
        hero.addEventListener('pointermove', (e) => {
            const r = canvas.getBoundingClientRect();
            mx = e.clientX - r.left; my = e.clientY - r.top;
        });
        hero.addEventListener('pointerleave', () => { mx = my = -9999; });
        new IntersectionObserver(([en]) => {
            visible = en.isIntersecting;
            if (visible && !raf && animated()) raf = requestAnimationFrame(loop);
        }).observe(hero);
    }

    /* ------------------------------------------------------------ hero 3D tilt */
    const heroVisual = $('.hero-visual');
    if (heroVisual && matchMedia('(pointer: fine)').matches) {
        const app = $('.app', heroVisual);
        $('.hero').addEventListener('pointermove', (e) => {
            if (reduce || innerWidth < 1080) return;
            const nx = e.clientX / innerWidth - 0.5, ny = e.clientY / innerHeight - 0.5;
            app.style.transform = `rotateY(${-9 + nx * 8}deg) rotateX(${4 - ny * 6}deg)`;
        });
    }

    /* ------------------------------------------------------------ hero: a conversation that actually happens */
    const heroLog = $('.hero .chat-log[data-script]');
    const typed = $('.hero [data-typer]');
    if (heroLog && typed) {
        const script = JSON.parse(heroLog.dataset.script);
        const typing = $('.typing', heroLog);
        const sendBtn = $('.hero .composer .send');
        const initial = Array.from(heroLog.children);
        const wait = (ms) => new Promise((r) => setTimeout(r, ms));
        const now = () => new Date().toTimeString().slice(0, 5);
        const bubble = (text, dir) => {
            const b = document.createElement('div');
            b.className = `bubble ${dir} is-new`;
            b.textContent = text;
            const t = document.createElement('time'); t.textContent = now();
            b.appendChild(t);
            heroLog.insertBefore(b, typing);
            // keep the log short; the oldest lines scroll out of the window anyway
            const all = $$('.bubble', heroLog);
            if (all.length > 5) all[0].remove();
        };
        let heroOn = true;
        new IntersectionObserver(([en]) => { heroOn = en.isIntersecting; }).observe(heroLog);
        const until = async () => { while (!heroOn || document.hidden) await wait(400); };
        async function run() {
            typing.hidden = true;
            for (;;) {
                await wait(1400);
                for (const step of script) {
                    await until();
                    if (step.me) {
                        for (let i = 1; i <= step.me.length; i++) { typed.textContent = step.me.slice(0, i); await wait(70 + Math.random() * 90); }
                        await wait(500);
                        sendBtn.classList.add('is-press'); await wait(140); sendBtn.classList.remove('is-press');
                        typed.textContent = '';
                        bubble(step.me, 'out');
                        await wait(900);
                    } else {
                        typing.hidden = false;
                        await wait(1500);
                        typing.hidden = true;
                        bubble(step.them, 'in');
                        await wait(1600);
                    }
                }
                await wait(3500);
                await until();
                heroLog.replaceChildren(...initial);
                typing.hidden = true;
            }
        }
        if (reduce) typed.textContent = script[0].me; else run();
    }

    /* ------------------------------------------------------------ STORY: mailbox → conversation */
    const story = $('.story');
    if (story) {
        const stage = $('.stage', story);
        const term = $('.term', stage);
        const screen = $('.term-screen', term);
        const app = $('.story-app', stage);
        const layer = $('.morph-layer', stage);
        const steps = $$('.story-step', story);
        const dots = $$('.story-dots li', story);
        const yearEl = $('[data-year]', story);
        const rowsAll = $$('.mail-row', term);
        const statusEl = $('[data-termstatus]', term);
        const countEl = $('[data-mailcount]', term);
        const titleEls = $$('.mail-row .t', term);
        const localBubbles = $$('.bubble.local', app);
        const SCRAMBLE = '░▒▓█▀▄■□◆※#@$%&*+=?';
        const morphs = titleEls.map((t) => {
            const row = t.closest('.mail-row');
            const id = row.dataset.row;
            const target = $(`[data-bubble="${id}"]`, app);
            const el = document.createElement('div');
            el.className = 'morph' + (target && target.classList.contains('out') ? ' out' : '');
            el.innerHTML = '<span class="m-term"></span><span class="m-chat"></span>';
            el.querySelector('.m-term').textContent = t.dataset.target;
            el.querySelector('.m-chat').textContent = t.dataset.target;
            el.style.visibility = 'hidden';
            layer.appendChild(el);
            return { t, row, tag: row.querySelector('.tag'), target, el, original: t.textContent, from: null, to: null };
        });

        let termFs = 12;
        function layout() {
            const w = stage.clientWidth;
            // start from a 52-column screen, then shrink further if the longest mail row would clip
            termFs = w / (52 * 0.6 + 2.8);
            term.style.fontSize = termFs + 'px';
            morphs.forEach((m) => { m.t.textContent = m.t.dataset.target.length > m.original.length ? m.t.dataset.target : m.original; });
            let widest = 0;
            rowsAll.forEach((r) => {
                const range = document.createRange(); range.selectNodeContents(r);
                widest = Math.max(widest, range.getBoundingClientRect().width + termFs * 5);
            });
            const avail = w - termFs * 2.8;
            if (widest > avail) { termFs *= avail / widest; term.style.fontSize = termFs + 'px'; }
            morphs.forEach((m) => { m.t.textContent = m.original; });

            const sr = stage.getBoundingClientRect();
            const prevA = app.style.opacity, prevT = term.style.opacity;
            morphs.forEach((m) => {
                const a = m.t.getBoundingClientRect();
                m.from = { x: a.left - sr.left - 12, y: a.top - sr.top - termFs * 0.25, w: m.t.dataset.target.length * termFs * 1.02 + 24, h: termFs * 1.8 };
                const b = m.target ? m.target.getBoundingClientRect() : null;
                m.to = b && b.width ? { x: b.left - sr.left, y: b.top - sr.top, w: b.width, h: b.height } : null;
                m.el.querySelector('.m-term').style.fontSize = termFs + 'px';
            });
            app.style.opacity = prevA; term.style.opacity = prevT;
            last = -1; update();
        }

        let last = -1;
        function scramble(src, dst, u) {
            const n = Math.max(src.length, dst.length);
            const k = Math.floor(u * dst.length);
            let out = dst.slice(0, k);
            if (u >= 1) return dst;
            for (let i = k; i < Math.min(n, k + Math.max(2, Math.ceil((1 - u) * 6))); i++) out += SCRAMBLE[(Math.random() * SCRAMBLE.length) | 0];
            return out;
        }

        function update() {
            const r = story.getBoundingClientRect();
            const span = story.offsetHeight - innerHeight;
            const p = reduce ? 1 : clamp(-r.top / span);
            if (Math.abs(p - last) < 0.0005) return;
            last = p;

            // copy + chrome
            const step = p < 0.3 ? 0 : p < 0.62 ? 1 : 2;
            steps.forEach((s, i) => s.classList.toggle('is-on', i === step));
            dots.forEach((d, i) => d.style.setProperty('--fill', clamp((p - i / 3) * 3).toFixed(3)));
            yearEl.textContent = Math.round(lerp(1995, 2026, smooth(0.04, 0.9, p)));

            // phase A: cursor walks the mailbox
            const cur = p < 0.3 ? Math.min(4, Math.floor((p / 0.28) * 5)) : -1;
            rowsAll.forEach((row, i) => row.classList.toggle('is-cur', i === cur));

            // phase B: decode the uPtt rows
            let parsed = 0;
            morphs.forEach((m, i) => {
                const u = clamp((p - 0.32 - i * 0.06) / 0.1);
                if (u >= 1) parsed++;
                m.t.textContent = u <= 0 ? m.original : scramble(m.original, m.t.dataset.target, u);
                m.tag.textContent = u >= 1 ? ' ' + T.parsed : '';
            });
            statusEl.textContent = p < 0.3 ? T.termIdle : parsed < 4 ? T.termParse(parsed) : T.termDone;

            // phase C: rows fly into the app
            const appIn = smooth(0.6, 0.68, p);
            app.style.opacity = appIn.toFixed(3);
            app.style.visibility = appIn > 0 ? 'visible' : 'hidden';
            const termOut = smooth(0.62, 0.74, p);
            term.style.opacity = (1 - termOut).toFixed(3);
            term.style.filter = termOut > 0 ? `blur(${(termOut * 3).toFixed(2)}px)` : '';

            morphs.forEach((m, i) => {
                const u = clamp((p - 0.62 - i * 0.015) / (0.13 + i * 0.03));
                const t = ease(u);
                m.row.classList.toggle('is-gone', t > 0);
                if (m.target) m.target.style.opacity = t >= 1 ? '' : '0';
                if (t <= 0 || t >= 1 || !m.from) { m.el.style.visibility = 'hidden'; return; }
                const to = m.to || { x: m.from.x, y: m.from.y - 30, w: m.from.w, h: m.from.h };
                const x = lerp(m.from.x, to.x, t);
                const y = lerp(m.from.y, to.y, t) - Math.sin(t * Math.PI) * 24;
                m.el.style.visibility = 'visible';
                m.el.style.width = lerp(m.from.w, to.w, t) + 'px';
                m.el.style.height = lerp(m.from.h, to.h, t) + 'px';
                m.el.style.transform = `translate3d(${x}px, ${y}px, 0)`;
                m.el.style.opacity = m.to ? 1 : (1 - t).toFixed(3);
                const chat = m.el.querySelector('.m-chat');
                m.el.querySelector('.m-term').style.opacity = (1 - smooth(0, 0.08, u)).toFixed(3);
                chat.style.opacity = smooth(0, 0.08, u).toFixed(3);
                chat.style.fontSize = lerp(termFs, 12.5, smooth(0.1, 0.9, t)).toFixed(2) + 'px';
                chat.style.boxShadow = `0 0 0 1px rgba(143, 191, 160, ${(0.7 * (1 - smooth(0.6, 1, t))).toFixed(3)}), 0 12px 30px -10px rgba(0, 0, 0, ${(0.6 * (1 - t)).toFixed(3)})`;
            });
            countEl.textContent = p > 0.7 ? 4 : 8;

            // replies written locally appear after the incoming ones land
            localBubbles.forEach((b, i) => {
                const v = smooth(0.8 + i * 0.05, 0.86 + i * 0.05, p);
                b.style.opacity = v.toFixed(3);
                b.style.transform = `translateY(${(1 - v) * 10}px)`;
            });
        }

        let ticking = false;
        addEventListener('scroll', () => {
            if (ticking || !armed) return;
            ticking = true;
            requestAnimationFrame(() => { ticking = false; update(); });
        }, { passive: true });
        // measure lazily: the story sits below the fold, so keep its forced reflows off the load path
        let armed = false;
        const arm = () => { if (armed) return; armed = true; layout(); if (document.fonts) document.fonts.ready.then(layout); };
        let rt; addEventListener('resize', () => { if (!armed) return; clearTimeout(rt); rt = setTimeout(layout, 120); });
        new IntersectionObserver(([en]) => { if (en.isIntersecting) arm(); }, { rootMargin: '100% 0px' }).observe(story);
        themeListeners.push(() => { last = -1; update(); });
    }

    /* ------------------------------------------------------------ message type tabs */
    const tabs = $$('.type-tab');
    function selectTab(tab, focus) {
        tabs.forEach((t) => {
            const on = t === tab;
            t.setAttribute('aria-selected', String(on));
            t.tabIndex = on ? 0 : -1;
            const panel = document.getElementById(t.getAttribute('aria-controls'));
            panel.hidden = !on;
            if (on && !reduce) { panel.classList.remove('is-entering'); void panel.offsetWidth; panel.classList.add('is-entering'); }
        });
        if (focus) tab.focus();
    }
    tabs.forEach((t, i) => {
        t.addEventListener('click', () => selectTab(t));
        t.addEventListener('keydown', (e) => {
            const d = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
            if (e.key === 'Home') { e.preventDefault(); selectTab(tabs[0], true); }
            else if (e.key === 'End') { e.preventDefault(); selectTab(tabs[tabs.length - 1], true); }
            else if (d) { e.preventDefault(); selectTab(tabs[(i + d + tabs.length) % tabs.length], true); }
        });
    });

    /* ------------------------------------------------------------ bento: pointer glow */
    $$('.cell').forEach((c) => c.addEventListener('pointermove', (e) => {
        const r = c.getBoundingClientRect();
        c.style.setProperty('--mx', `${e.clientX - r.left}px`);
        c.style.setProperty('--my', `${e.clientY - r.top}px`);
    }));

    /* ------------------------------------------------------------ bento: drag-to-reorder */
    $$('[data-dnd]').forEach((list) => {
        let drag = null;
        const items = () => $$('li', list);
        list.addEventListener('pointerdown', (e) => {
            const li = e.target.closest('li');
            if (!li || e.button !== 0) return;
            e.preventDefault();
            li.setPointerCapture(e.pointerId);
            drag = { li, startY: e.clientY, h: li.offsetHeight + 6 };
            li.classList.add('is-dragging');
        });
        list.addEventListener('pointermove', (e) => {
            if (!drag) return;
            let dy = e.clientY - drag.startY;
            const all = items(), idx = all.indexOf(drag.li);
            if (dy > drag.h * 0.6 && idx < all.length - 1) {
                list.insertBefore(all[idx + 1], drag.li); drag.startY += drag.h; dy -= drag.h;
            } else if (dy < -drag.h * 0.6 && idx > 0) {
                list.insertBefore(drag.li, all[idx - 1]); drag.startY -= drag.h; dy += drag.h;
            }
            drag.li.style.transform = `translateY(${dy}px) scale(1.02)`;
        });
        const end = () => {
            if (!drag) return;
            drag.li.classList.remove('is-dragging');
            drag.li.style.transform = '';
            drag = null;
        };
        list.addEventListener('pointerup', end);
        list.addEventListener('pointercancel', end);
        list.addEventListener('keydown', (e) => {
            const li = e.target.closest('li');
            if (!li || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
            e.preventDefault();
            const all = items(), idx = all.indexOf(li);
            if (e.key === 'ArrowUp' && idx > 0) list.insertBefore(li, all[idx - 1]);
            if (e.key === 'ArrowDown' && idx < all.length - 1) list.insertBefore(all[idx + 1], li);
            li.focus();
        });
    });

    /* ------------------------------------------------------------ bento: presence + notifications */
    const whenVisible = (el, fn) => {
        if (!el) return;
        let id = 0;
        new IntersectionObserver(([en]) => {
            if (en.isIntersecting && !id && !reduce) id = setInterval(fn, 2200);
            if (!en.isIntersecting && id) { clearInterval(id); id = 0; }
        }).observe(el);
    };
    const pres = $('[data-presence]');
    whenVisible(pres, () => {
        const rows = $$('.row', pres);
        const row = rows[(Math.random() * rows.length) | 0];
        const dot = $('.presence', row), st = $('.state', row);
        const next = (Number(row.dataset.s || (dot.classList.contains('on') ? 0 : dot.classList.contains('unknown') ? 2 : 1)) + 1) % 3;
        row.dataset.s = next;
        dot.className = 'presence' + (next === 0 ? ' on' : next === 2 ? ' unknown' : '');
        st.textContent = T.states[next];
    });

    const notify = $('[data-notify]');
    if (notify) {
        const cards = $$('.notify', notify);
        let head = 0;
        const place = () => {
            cards.forEach((c, i) => {
                const k = (i - head + cards.length) % cards.length;
                c.style.zIndex = String(10 - k);
                c.style.transform = `translateY(${k * 14}px) scale(${1 - k * 0.05})`;
                c.style.opacity = k > 2 ? 0 : String(1 - k * 0.25);
            });
        };
        place();
        whenVisible(notify, () => { head = (head - 1 + cards.length) % cards.length; place(); });
    }

    /* ------------------------------------------------------------ architecture packets */
    const arch = $('.arch-diagram svg');
    if (arch && !reduce) {
        const NS = 'http://www.w3.org/2000/svg';
        const spawn = (pathId, cls, dur, begin, reverse) => {
            const c = document.createElementNS(NS, 'circle');
            c.setAttribute('r', '3.5'); c.setAttribute('class', 'pkt ' + cls);
            // hidden until its motion starts, otherwise it waits at the SVG origin
            c.setAttribute('visibility', 'hidden');
            const show = document.createElementNS(NS, 'set');
            show.setAttribute('attributeName', 'visibility'); show.setAttribute('to', 'visible');
            show.setAttribute('begin', begin + 's'); show.setAttribute('fill', 'freeze');
            c.appendChild(show);
            const m = document.createElementNS(NS, 'animateMotion');
            m.setAttribute('dur', dur + 's'); m.setAttribute('begin', begin + 's'); m.setAttribute('repeatCount', 'indefinite');
            if (reverse) { m.setAttribute('keyPoints', '1;0'); m.setAttribute('keyTimes', '0;1'); m.setAttribute('calcMode', 'linear'); }
            const mp = document.createElementNS(NS, 'mpath'); mp.setAttribute('href', '#' + pathId);
            m.appendChild(mp); c.appendChild(m); arch.appendChild(c);
        };
        spawn('w1', '', 2.4, 0); spawn('w3', '', 2.4, 1.2); spawn('w3', '', 2.4, 0.3, true); spawn('w1', '', 2.4, 1.5, true);
        spawn('w2', 'q', 3.6, 0.6); spawn('w4', 'q', 3.6, 2.4); spawn('w4', 'q', 3.6, 1.4, true);
        // SMIL forces a layout every frame, so only run it while the diagram is on screen
        arch.pauseAnimations();
        new IntersectionObserver(([en]) => { if (en.isIntersecting) arch.unpauseAnimations(); else arch.pauseAnimations(); }).observe(arch);
    }

    /* ------------------------------------------------------------ privacy: words light up with scroll */
    const lit = $('[data-lit]');
    const words = lit ? $$('.w', lit) : [];

    /* ------------------------------------------------------------ footer wordmark fill */
    const wordmark = $('[data-wordmark]');

    function onScroll() {
        onNavScroll();
        if (words.length) {
            const r = lit.getBoundingClientRect();
            const p = reduce ? 1 : clamp((innerHeight * 0.85 - r.top) / (r.height + innerHeight * 0.35));
            const n = Math.round(p * words.length);
            words.forEach((w, i) => w.classList.toggle('is-lit', i < n));
        }
        if (wordmark) {
            const r = wordmark.getBoundingClientRect();
            const p = reduce ? 1 : clamp((innerHeight - r.top) / (r.height + innerHeight * 0.25));
            wordmark.style.setProperty('--fill', (p * 100).toFixed(1) + '%');
        }
    }
    addEventListener('scroll', () => requestAnimationFrame(onScroll), { passive: true });
    onScroll();

    /* ------------------------------------------------------------ shortcut keys light up */
    const keyCards = new Map($$('[data-key]').map((c) => [c.dataset.key, c]));
    const keysSection = $('[data-keys]');
    let keysVisible = false;
    if (keysSection) new IntersectionObserver(([en]) => { keysVisible = en.isIntersecting; }).observe(keysSection);
    addEventListener('keydown', (e) => {
        if (!keysVisible || e.repeat) return;
        if (e.target.closest('input, textarea, [contenteditable]')) return;
        const k = e.key === 'Enter' ? 'enter' : e.key.toLowerCase();
        const card = keyCards.get(k);
        if (!card) return;
        if (k === 'enter' && !e.shiftKey) return;
        if (k === 'k' && (e.metaKey || e.ctrlKey)) e.preventDefault();
        card.classList.add('is-pressed');
    });
    addEventListener('keyup', () => keyCards.forEach((c) => c.classList.remove('is-pressed')));
    addEventListener('blur', () => keyCards.forEach((c) => c.classList.remove('is-pressed')));
})();
