import subprocess, time, os, urllib.request, json, sys
from urllib.parse import unquote
from playwright.sync_api import sync_playwright

SP, AP = 4101, 4102
BASE = f'http://127.0.0.1:{SP}/'; API = f'http://127.0.0.1:{AP}'
srv = subprocess.Popen(['node', 'test/harness.js', str(SP), str(AP)], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), stdout=subprocess.PIPE)
srv.stdout.readline()
tmp = '/tmp/claude-0/ui2'; os.makedirs(tmp, exist_ok=True)
open(f'{tmp}/a.pdf', 'wb').write(b'%PDF-1.4 hello'); open(f'{tmp}/tour.mp4', 'wb').write(b'\x00\x00\x00\x18ftypmp42' + b'0' * 200)
open(f'{tmp}/big.bin', 'wb').write(b'0' * (16 * 1024 * 1024))
import zlib, struct
def png(w, h, rgb):
    raw = b''.join(b'\x00' + bytes(rgb) * w for _ in range(h))
    def ch(t, d): c = struct.pack('>I', len(d)) + t + d; return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')
open(f'{tmp}/cover.png', 'wb').write(png(60, 40, (40, 110, 160)))

MOCK = """(()=>{window.__shared=[];window.__opened=[];window.__mode='ok';
navigator.canShare=(d)=>window.__mode!=='unsupported'&&!!(d&&d.files&&d.files.length);
navigator.share=async(d)=>{window.__shared.push({n:d.files.map(f=>f.name),t:d.files.map(f=>f.type),sz:d.files.map(f=>f.size),text:d.text||null})};
window.open=(u)=>{window.__opened.push(u===undefined?'(none)':u);return null};})()"""
fails = []
def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{extra}]' if extra and not cond else ''))
    if not cond: fails.append(name)

errors = []
try:
  with sync_playwright() as p:
    b = p.chromium.launch()
    def ctx(mobile):
        if mobile: return b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        return b.new_context(viewport={'width': 1280, 'height': 800})
    def watch(pg, tag):
        pg.on('pageerror', lambda e: errors.append((tag, str(e))))
        pg.on('console', lambda m: errors.append((tag, m.text)) if m.type == 'error' and 'fonts.g' not in m.text and 'ERR_' not in m.text and 'drive.google' not in m.text and 'status of 401' not in m.text else None)

    c = ctx(False); pg = c.new_page(); watch(pg, 'admin')
    pg.goto(BASE); pg.wait_for_selector('#lf')
    check('login page shows site name from backend', 'مشاريع الشركة' in pg.inner_text('.login h1'))
    pg.screenshot(path=f'{tmp}/01-login.png')
    pg.fill('input[name=username]', 'admin'); pg.fill('input[name=password]', 'wrong'); pg.click('button[type=submit]')
    pg.wait_for_selector('.err'); check('wrong password message', 'غير صحيحة' in pg.inner_text('.err'))
    pg.fill('input[name=password]', 'Admin#123'); pg.click('button[type=submit]'); pg.wait_for_selector('.page-h')
    check('token stored in localStorage', bool(pg.evaluate("localStorage.getItem('sp_token')")))
    pg.click('[data-act=new-project]'); pg.fill('#pn', 'مجمع الأمل السكني'); pg.click('.dlg .btn.pri'); pg.wait_for_selector('.phead')
    check('project created', 'مجمع الأمل' in pg.inner_text('.phead h1'))
    def upload(sel, f):
        with pg.expect_file_chooser() as fc: pg.click(sel)
        fc.value.set_files(f'{tmp}/{f}')
    upload('[data-act=upload][data-sec=cover]', 'cover.png'); pg.wait_for_selector('.phead .cover[style*=thumbnail]'); check('cover uses Drive thumbnail URL', True)
    upload('.blk[data-sec=info_ar] [data-act=upload]', 'a.pdf'); pg.wait_for_selector('.blk[data-sec=info_ar] .f')
    upload('.blk[data-sec=videos] [data-act=upload]', 'tour.mp4'); pg.wait_for_selector('.blk[data-sec=videos] .f')
    upload('.blk[data-sec=maps] [data-act=upload]', 'cover.png'); pg.wait_for_selector('.blk[data-sec=maps] .f')
    upload('.blk[data-sec=prices] [data-act=upload]', 'big.bin'); time.sleep(1.2)
    check('too-big upload rejected with Drive hint', 'مباشرة في Google Drive' in (pg.inner_text('#toasts')), pg.inner_text('#toasts'))
    check('too-big file not listed', pg.locator('.blk[data-sec=prices] .f').count() == 0)
    pg.click('.blk[data-sec=location] [data-act=add-link]'); pg.fill('#lt', 'الموقع على خرائط Google'); pg.fill('#lu', 'maps.google.com/?q=35.5,45.4'); pg.click('.dlg .btn.pri'); pg.wait_for_selector('.blk[data-sec=location] .f')
    pg.screenshot(path=f'{tmp}/02-project-desktop.png', full_page=True)

    # فتح الملفات
    pg.click('.blk[data-sec=videos] .fn'); pg.wait_for_selector('.viewer iframe.v')
    check('video opens Drive preview iframe', '/preview' in pg.get_attribute('.viewer iframe', 'src')); pg.click('.viewer .x')
    pg.click('.blk[data-sec=info_ar] .fn'); pg.wait_for_selector('.viewer iframe'); check('pdf opens Drive preview', '/preview' in pg.get_attribute('.viewer iframe', 'src')); pg.click('.viewer .x')
    pg.click('.blk[data-sec=maps] .fn'); pg.wait_for_selector('.viewer img'); check('image viewer uses thumbnail', 'thumbnail' in pg.get_attribute('.viewer img', 'src')); pg.click('.viewer .x')

    # واتساب + مشاركة الملف نفسه
    pg.evaluate(MOCK)
    g = lambda: pg.evaluate('[window.__shared.splice(0), window.__opened.splice(0)]')
    pg.click('.blk[data-sec=info_ar] [data-act=send-file]'); time.sleep(1.2); sh, op = g()
    check('single file shared as real File', len(sh) == 1 and sh[0]['n'] == ['a.pdf'] and sh[0]['t'] == ['application/pdf'] and sh[0]['sz'] == [14], sh)
    pg.click('[data-act=send-project]'); time.sleep(1.5); sh, op = g()
    check('project: all files + link text', len(sh) == 1 and set(sh[0]['n']) == {'a.pdf', 'tour.mp4', 'cover.png'} and 'maps.google.com' in (sh[0]['text'] or ''), sh)
    pg.click('.blk[data-sec=location] [data-act=send-section]'); time.sleep(.6); sh, op = g()
    check('links-only section falls back to wa.me', not sh and op and op[0].startswith('https://wa.me/'), op)
    pg.fill('#clientNum', '07701234567'); pg.evaluate("window.__mode='unsupported'")
    pg.click('.blk[data-sec=info_ar] [data-act=send-file]'); time.sleep(.6); sh, op = g(); txt = unquote(op[0].split('text=')[1]) if op else ''
    check('unsupported -> wa.me with Drive link', op and op[0].startswith('https://wa.me/9647701234567') and 'drive.google.com/file/d/' in txt, op)
    pg.click('.blk[data-sec=videos] [data-act=send-section]'); time.sleep(.6); sh, op = g(); txt = unquote(op[0].split('text=')[1]) if op else ''
    pg.click('[data-act=send-project]'); time.sleep(.6); sh, op = g(); txt = unquote(op[0].split('text=')[1])
    share_url = [l for l in txt.split('\n') if 'share.html' in l]
    check('project message has Drive links + maps', 'drive.google.com/file/d/' in txt and 'maps.google.com' in txt, txt[:300])
    pg.evaluate("window.__mode='ok'"); pg.fill('#clientNum', '')
    # خرائط/حجم: ملف أكبر من حد الإرسال المباشر سيرسل كرابط (نضيفه مباشرة في Drive الوهمي)
    # إعدادات + مستخدمون
    pg.goto(BASE + '#/admin/users'); pg.wait_for_selector('#nu')
    pg.fill('#nu [name=name]', 'سارة أحمد'); pg.fill('#nu [name=username]', 'sara'); pg.fill('#nu [name=password]', 'secret1'); pg.click('#nu button[type=submit]')
    pg.wait_for_selector('.urow >> text=سارة'); pg.screenshot(path=f'{tmp}/05-admin-users.png', full_page=True)
    pg.goto(BASE + '#/admin/settings'); pg.wait_for_selector('#save-set'); pg.fill('#s-name', 'شركة النور العقارية'); pg.fill('[data-lab=videos]', 'جولات الفيديو'); pg.click('#save-set')
    pg.wait_for_selector('.brand b >> text=شركة النور'); check('site rename applied', True)
    # عنوان مشاركة (للتحقق من share.html لاحقاً)
    pg.goto(BASE + '#/'); pg.wait_for_selector('.pcard'); pg.click('.pcard h2 a'); pg.wait_for_selector('.phead')
    share_href = pg.evaluate("S.project.shareUrl"); sec_href = pg.evaluate("S.project.sectionShareUrls.videos")
    check('share URL is on the same site (github pages path)', share_href.startswith(BASE + 'share.html?t='), share_href)
    c.close()

    # صفحة العميل بدون تسجيل
    c2 = ctx(True); cl = c2.new_page(); watch(cl, 'client')
    cl.goto(share_href); cl.wait_for_selector('.row'); body = cl.inner_text('main')
    check('client page lists project files (no login)', 'tour.mp4' in body and 'a.pdf' in body and 'جولات الفيديو' in body and 'الموقع على خرائط' in body, body[:200])
    check('client links go to Drive', 'drive.google.com/file/d/' in cl.get_attribute('.row', 'href'))
    cl.screenshot(path=f'{tmp}/09-client-share.png', full_page=True)
    cl.goto(sec_href); cl.wait_for_selector('.row'); check('section page only that section', cl.locator('section').count() == 1 and 'tour.mp4' in cl.inner_text('main'))
    cl.goto(BASE + 'share.html?t=' + share_href.split('t=')[1][:-3] + 'abc'); cl.wait_for_selector('.msg'); check('forged token rejected', 'غير صالح' in cl.inner_text('main'))
    cl.goto(BASE + 'share.html'); cl.wait_for_selector('.msg'); check('no token handled', 'غير صالح' in cl.inner_text('main'))
    c2.close()

    # موظف على الهاتف
    c3 = ctx(True); m = c3.new_page(); watch(m, 'mobile')
    m.goto(BASE); m.fill('input[name=username]', 'sara'); m.fill('input[name=password]', 'secret1'); m.click('button[type=submit]'); m.wait_for_selector('.grid')
    check('sales has no admin controls', m.locator('[data-act=new-project]').count() == 0 and m.locator('a[href="#/admin"]').count() == 0)
    m.screenshot(path=f'{tmp}/07-mobile-list.png')
    m.click('.pcard h2 a'); m.wait_for_selector('.phead'); m.screenshot(path=f'{tmp}/08-mobile-project.png', full_page=True)
    check('sales has no upload/delete', m.locator('[data-act=upload]').count() == 0 and m.locator('[data-act=del-file]').count() == 0)
    check('no horizontal overflow on mobile', m.evaluate('document.documentElement.scrollWidth') <= 390, m.evaluate('document.documentElement.scrollWidth'))
    m.reload(); m.wait_for_selector('.phead'); check('stays logged in after reload', True)
    m.evaluate(MOCK); m.click('.blk[data-sec=info_ar] [data-act=send-file]'); time.sleep(1.2)
    check('sales can share real file', m.evaluate('window.__shared.length') == 1)
    c3.close()

    # إيقاف الحساب
    c4 = ctx(False); a = c4.new_page(); watch(a, 'admin2')
    a.goto(BASE); a.fill('input[name=username]', 'admin'); a.fill('input[name=password]', 'Admin#123'); a.click('button[type=submit]'); a.wait_for_selector('.grid')
    a.goto(BASE + '#/admin/users'); a.wait_for_selector('.urow'); a.locator('.urow', has_text='سارة').locator('[data-uact=toggle]').click(); a.wait_for_selector('.badge.off')
    c4.close()
    c5 = ctx(True); s2 = c5.new_page(); watch(s2, 'sara-after')
    s2.goto(BASE); s2.fill('input[name=username]', 'sara'); s2.fill('input[name=password]', 'secret1'); s2.click('button[type=submit]'); s2.wait_for_selector('.err')
    check('suspended account cannot log in', 'موقوف' in s2.inner_text('.err')); c5.close()
    b.close()
  st = json.load(urllib.request.urlopen(API + '/__stats'))
  check('no CORS preflight (OPTIONS) was ever sent', st['options'] == 0, st)
  print('requests to backend:', st['posts'])
finally:
  srv.terminate()
print('JS errors:', errors)
print('FAILED:' if fails else 'ALL PASSED', fails)
sys.exit(1 if fails else 0)
