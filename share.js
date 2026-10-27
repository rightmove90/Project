'use strict';
// صفحة العميل: تعرض ملفات مشروع أو قسم عبر رابط موقّع، دون تسجيل دخول
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ICON = { image: '🖼️', video: '🎬', pdf: '📄', sheet: '📊', doc: '📝', audio: '🎧', link: '📍', other: '📎' };
const fmtSize = (n) => (!n ? '' : n < 1048576 ? Math.max(1, Math.round(n / 1024)) + ' KB' : (n / 1048576).toFixed(1) + ' MB');
const safeHref = (u) => (/^https?:\/\//i.test(u) ? u : '#');
(async function () {
  const main = document.getElementById('main');
  const t = new URLSearchParams(location.search).get('t');
  try {
    if (!t) throw new Error('الرابط غير صالح');
    const cfg = window.PORTAL || {};
    const res = await fetch(cfg.API_URL, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify({ action: 'shareView', t }) });
    const j = await res.json();
    if (!j.ok) throw new Error(j.status === 404 ? 'الرابط غير صالح أو انتهت صلاحيته' : j.error);
    const d = j.data;
    document.title = d.title + ' — ' + d.siteName;
    document.getElementById('site').textContent = d.siteName;
    document.getElementById('title').textContent = d.title;
    const groups = d.groups.filter((g) => g.items.length);
    main.innerHTML = groups.length ? groups.map((g) => `<section><h2>${esc(g.label)}</h2>${g.items.map((it) =>
      `<a class="row" href="${esc(safeHref(it.href))}" target="_blank" rel="noopener"><span class="ic">${ICON[it.category] || ICON.other}</span><span class="nm">${esc(it.name)}</span><span class="sz">${esc(fmtSize(it.size))}</span></a>`).join('')}</section>`).join('')
      : '<p class="msg">لا توجد ملفات هنا بعد.</p>';
  } catch (e) {
    document.getElementById('title').textContent = 'تعذّر فتح الرابط';
    main.innerHTML = `<p class="msg">${esc(e.message || 'حدث خطأ')}</p>`;
  }
})();
