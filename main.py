import os
import io
import random
import threading
from datetime import datetime, time
import pytz
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                           CallbackQueryHandler, filters, ContextTypes, ConversationHandler)

from db import (init_db, net_kaydet, haftalik_netler, tum_netler, ders_istatistikleri,
                plan_kaydet, gunun_plani, deneme_kaydet, denemeler_getir,
                son_denemeler, deneme_istatistikleri)

# ── WEB SUNUCUSU ──────────────────────────────────────────────────────────────
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Zeren'in Nexus Botu Aktif!"

def run_web():
    app_flask.run(host='0.0.0.0', port=6000)

# ── AYARLAR ───────────────────────────────────────────────────────────────────
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
YKS_DATE = datetime(2026, 6, 20)
TR_TIMEZONE = pytz.timezone('Europe/Istanbul')
CHAT_ID = int(os.environ.get('TELEGRAM_CHAT_ID', '5314748039'))

MOTIVASYON = [
    "Bugün dünden daha iyi olmak için bir şansın var!",
    "Hedefin büyük, adımların kararlı olsun Zeren.",
    "Başarı, her gün tekrarlanan küçük çabaların toplamıdır.",
    "Zorlandığın anlarda neden başladığını hatırla.",
    "Bugünkü disiplinin, yarınki özgürlüğündür.",
    "Küçük adımlar, büyük yolculuklar başlatır.",
    "Her soru çözdüğünde YKS'ye bir adım daha yaklaşıyorsun.",
    "Yorulduğunda dur, ama asla vazgeçme.",
    "Deneme sınavları puanı değil, eksikleri görmek içindir.",
    "Hatalar seni geri değil, ileriye taşır.",
]

DERS_EMOJILER = {'turkce': '📖', 'matematik': '🔢', 'sosyal': '🌍', 'fen': '🔬'}
DERS_ADLAR = {'turkce': 'Türkçe', 'matematik': 'Matematik', 'sosyal': 'Sosyal', 'fen': 'Fen'}

# ConversationHandler states
DENEME_TUR = 1
DENEME_ALAN = 2
DENEME_NET = 3

ANA_MENU = [
    ['📅 YKS Geri Sayım', '📝 Günlük Planım'],
    ['📈 Net Gir', '📊 Haftalık Grafik'],
    ['🏆 Ders Analizi', '💡 Motivasyon'],
    ['📋 Deneme Gir', '📉 Deneme Takibi'],
]

# ── YARDIMCI ──────────────────────────────────────────────────────────────────

def kalan_gun():
    return (YKS_DATE - datetime.now()).days

# ── ANA KOMUTLAR ─────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Merhaba Zeren! 🚀 *Operation Nexus* aktif!\n\n"
        f"📅 YKS 2026'ya *{kalan_gun()} gün* kaldı.\n\n"
        f"Her sabah 08:00'de hedeflerini soracağım, akşam 23:00'de raporunu bekleyeceğim.",
        reply_markup=ReplyKeyboardMarkup(ANA_MENU, resize_keyboard=True),
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == '📅 YKS Geri Sayım':
        await update.message.reply_text(
            f"⏳ YKS 2026'ya *{kalan_gun()} gün* kaldı.\n\nZaman daralıyor, odaklan Zeren! 💪",
            parse_mode='Markdown'
        )

    elif text == '📝 Günlük Planım':
        plan = gunun_plani(user_id)
        if plan:
            await update.message.reply_text(
                f"📋 *Bugünkü planın:*\n\n{plan['plan']}\n\nGüncellemek için 'Bugün şunları yapacağım:' ile başla.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "Henüz bugün için bir plan yazmamışsın.\n\n"
                "'Bugün şunları yapacağım:' diye başlayarak planını yaz!"
            )

    elif text == '📈 Net Gir':
        await update.message.reply_text(
            "📈 *Günlük Net Girişi*\n\n"
            "Şu formatta yaz:\n`Net: T:28 M:22 S:18 F:20`\n\n"
            "T=Türkçe  M=Matematik  S=Sosyal  F=Fen",
            parse_mode='Markdown'
        )

    elif text == '📊 Haftalık Grafik':
        await gonder_haftalik_grafik(update, user_id)

    elif text == '🏆 Ders Analizi':
        await gonder_ders_analizi(update, user_id)

    elif text == '💡 Motivasyon':
        await update.message.reply_text(
            f"💡 *{random.choice(MOTIVASYON)}*\n\n⏳ YKS'ye {kalan_gun()} gün kaldı.",
            parse_mode='Markdown'
        )

    elif text == '📋 Deneme Gir':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📘 TYT", callback_data='deneme_tur_TYT'),
             InlineKeyboardButton("📗 AYT", callback_data='deneme_tur_AYT')]
        ])
        await update.message.reply_text(
            "📋 *Hangi denemeyi girmek istiyorsun?*",
            reply_markup=kb, parse_mode='Markdown'
        )

    elif text == '📉 Deneme Takibi':
        await gonder_deneme_ozet(update, user_id)

    elif text.lower().startswith('net:'):
        await isle_net_girisi(update, user_id, text)

    elif text.lower().startswith('bugün') or text.lower().startswith('bugün'):
        plan_kaydet(user_id, text)
        await update.message.reply_text(
            f"✅ *Planın kaydedildi!*\n\n_{text}_\n\nAkşam 23:00'de kontrol edeceğiz. Başarılar! 🚀",
            parse_mode='Markdown'
        )

    else:
        await update.message.reply_text(
            "Mesajını aldım! 📬\n\n"
            "• Net girmek için: `Net: T:28 M:22 S:18 F:20`\n"
            "• Plan yazmak için 'Bugün şunları yapacağım:' ile başla\n"
            "• Deneme girmek için: `📋 Deneme Gir` butonunu kullan",
            parse_mode='Markdown'
        )

# ── CALLBACK: DENEME TÜR / ALAN SEÇİMİ ──────────────────────────────────────

async def deneme_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith('deneme_tur_'):
        tur = data.split('_')[-1]
        context.user_data['deneme_tur'] = tur

        if tur == 'TYT':
            context.user_data['deneme_alan'] = ''
            await query.edit_message_text(
                "📘 *TYT Deneme Girişi*\n\n"
                "Netlerini şu formatta yaz:\n"
                "`TYT: T:32 M:28 S:15 F:18`\n\n"
                "T=Türkçe  M=Matematik  S=Sosyal  F=Fen\n\n"
                "_İptal etmek için /iptal yaz_",
                parse_mode='Markdown'
            )
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔢 Sayısal", callback_data='deneme_alan_Sayısal')],
                [InlineKeyboardButton("📖 Sözel", callback_data='deneme_alan_Sözel')],
                [InlineKeyboardButton("⚖️ Eşit Ağırlık (EA)", callback_data='deneme_alan_EA')],
            ])
            await query.edit_message_text(
                "📗 *AYT Alanını seç:*", reply_markup=kb, parse_mode='Markdown'
            )

    elif data.startswith('deneme_alan_'):
        alan = data.replace('deneme_alan_', '')
        context.user_data['deneme_alan'] = alan
        format_str = _ayt_format(alan)
        await query.edit_message_text(
            f"📗 *AYT {alan} Deneme Girişi*\n\n"
            f"Netlerini şu formatta yaz:\n`{format_str}`\n\n"
            f"_İptal etmek için /iptal yaz_",
            parse_mode='Markdown'
        )

def _ayt_format(alan: str) -> str:
    if alan == 'Sayısal':
        return "AYT: M:35 Fiz:10 Kim:10 Bio:10"
    elif alan == 'Sözel':
        return "AYT: Edb:20 Tar1:8 Cog1:5 Tar2:8 Cog2:3 Fel:8 Din:4"
    else:
        return "AYT: M:30 Edb:18 Tar1:8 Cog1:5"

# ── DENEMEYİ İŞLE ────────────────────────────────────────────────────────────

async def isle_deneme_girisi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    tur = context.user_data.get('deneme_tur')
    alan = context.user_data.get('deneme_alan', '')

    if not tur:
        return

    prefix = 'TYT:' if tur == 'TYT' else 'AYT:'
    if not text.upper().startswith(prefix):
        return

    try:
        parcalar = text.upper().replace(prefix, '').strip().split()
        netlər = {}
        kisaltma_map = {
            'T': 'turkce', 'M': 'matematik', 'S': 'sosyal', 'F': 'fen',
            'FIZ': 'fizik', 'KIM': 'kimya', 'BIO': 'biyoloji',
            'EDB': 'edebiyat', 'TAR1': 'tarih1', 'COG1': 'cografya1',
            'TAR2': 'tarih2', 'COG2': 'cografya2', 'FEL': 'felsefe', 'DIN': 'din',
        }
        for p in parcalar:
            if ':' in p:
                k, v = p.split(':', 1)
                col = kisaltma_map.get(k.strip())
                if col:
                    netlər[col] = float(v)

        if tur == 'AYT' and alan == 'Sayısal' and 'matematik' not in netlər and 'mat_ayt' not in netlər:
            for p in parcalar:
                if p.startswith('M:'):
                    netlər['mat_ayt'] = float(p.split(':')[1])

        toplam = deneme_kaydet(user_id, tur, alan, netlər)
        context.user_data.pop('deneme_tur', None)
        context.user_data.pop('deneme_alan', None)

        ozet = _deneme_ozet_satiri(tur, alan, netlər, toplam)
        istat = deneme_istatistikleri(user_id, tur)
        gelisim_satir = ''
        if istat and istat['sayi'] > 1:
            fark = istat['gelisim']
            ok = '📈' if fark > 0 else ('📉' if fark < 0 else '➡️')
            gelisim_satir = f"\n\n{ok} *İlk denemeden bu yana:* `{fark:+.1f}` net"

        await update.message.reply_text(
            f"✅ *{tur} Denemesi Kaydedildi!*\n\n{ozet}"
            f"\n🎯 *Toplam: {toplam:.1f} net*"
            f"{gelisim_satir}\n\n"
            f"📉 Tüm denemelerini görmek için `📉 Deneme Takibi` butonunu kullan.",
            parse_mode='Markdown'
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Format hatalı! Örnek:\n`{_ayt_format(alan) if tur == 'AYT' else 'TYT: T:32 M:28 S:15 F:18'}`",
            parse_mode='Markdown'
        )

def _deneme_ozet_satiri(tur, alan, netlər, toplam):
    if tur == 'TYT':
        return (
            f"📖 Türkçe: `{netlər.get('turkce', 0):.1f}`\n"
            f"🔢 Matematik: `{netlər.get('matematik', 0):.1f}`\n"
            f"🌍 Sosyal: `{netlər.get('sosyal', 0):.1f}`\n"
            f"🔬 Fen: `{netlər.get('fen', 0):.1f}`"
        )
    elif alan == 'Sayısal':
        mat = netlər.get('mat_ayt', netlər.get('matematik', 0))
        return (
            f"🔢 Matematik: `{mat:.1f}`\n"
            f"⚡ Fizik: `{netlər.get('fizik', 0):.1f}`\n"
            f"🧪 Kimya: `{netlər.get('kimya', 0):.1f}`\n"
            f"🌿 Biyoloji: `{netlər.get('biyoloji', 0):.1f}`"
        )
    elif alan == 'Sözel':
        return (
            f"📝 Edebiyat: `{netlər.get('edebiyat', 0):.1f}`\n"
            f"🏛 Tarih-1: `{netlər.get('tarih1', 0):.1f}`  "
            f"🗺 Coğrafya-1: `{netlər.get('cografya1', 0):.1f}`\n"
            f"🏛 Tarih-2: `{netlər.get('tarih2', 0):.1f}`  "
            f"🗺 Coğrafya-2: `{netlər.get('cografya2', 0):.1f}`\n"
            f"💭 Felsefe: `{netlər.get('felsefe', 0):.1f}`  "
            f"☪️ Din: `{netlər.get('din', 0):.1f}`"
        )
    else:  # EA
        mat = netlər.get('mat_ayt', netlər.get('matematik', 0))
        return (
            f"🔢 Matematik: `{mat:.1f}`\n"
            f"📝 Edebiyat: `{netlər.get('edebiyat', 0):.1f}`\n"
            f"🏛 Tarih-1: `{netlər.get('tarih1', 0):.1f}`  "
            f"🗺 Coğrafya-1: `{netlər.get('cografya1', 0):.1f}`"
        )

# ── DENEMELERİ GÖSTER ────────────────────────────────────────────────────────

async def gonder_deneme_ozet(update: Update, user_id: int):
    sonlar = son_denemeler(user_id, limit=8)
    if not sonlar:
        await update.message.reply_text(
            "📉 Henüz deneme kaydı yok!\n\n`📋 Deneme Gir` butonuyla ilk denemeni ekle.",
            parse_mode='Markdown'
        )
        return

    await update.message.reply_text("📊 Grafik hazırlanıyor...")

    tyt_rows = [r for r in denemeler_getir(user_id, tur='TYT')]
    ayt_rows = [r for r in denemeler_getir(user_id, tur='AYT')]

    fig, axes = plt.subplots(2, 1, figsize=(11, 10), facecolor='#1a1a2e')
    fig.suptitle("Zeren'in Deneme Sınavı Takibi 📋", fontsize=15, color='white', fontweight='bold', y=0.98)

    # ── Üst grafik: Toplam net gelişimi ──
    ax1 = axes[0]
    ax1.set_facecolor('#16213e')

    has_data = False
    if tyt_rows:
        has_data = True
        tyt_idx = list(range(1, len(tyt_rows) + 1))
        tyt_top = [r['toplam'] for r in tyt_rows]
        ax1.plot(tyt_idx, tyt_top, 'o-', color='#4ECDC4', linewidth=2.5,
                 markersize=9, label='TYT', zorder=3)
        for i, (x, y) in enumerate(zip(tyt_idx, tyt_top)):
            ax1.annotate(f'{y:.0f}', (x, y), textcoords="offset points",
                         xytext=(0, 10), ha='center', fontsize=9, color='#4ECDC4', fontweight='bold')
        # Trend çizgisi
        if len(tyt_rows) > 1:
            import numpy as np
            z = np.polyfit(tyt_idx, tyt_top, 1)
            p = np.poly1d(z)
            ax1.plot(tyt_idx, p(tyt_idx), '--', color='#4ECDC4', alpha=0.4, linewidth=1.5)

    if ayt_rows:
        has_data = True
        ayt_idx = list(range(1, len(ayt_rows) + 1))
        ayt_top = [r['toplam'] for r in ayt_rows]
        ax1.plot(ayt_idx, ayt_top, 's-', color='#FF6B6B', linewidth=2.5,
                 markersize=9, label='AYT', zorder=3)
        for i, (x, y) in enumerate(zip(ayt_idx, ayt_top)):
            ax1.annotate(f'{y:.0f}', (x, y), textcoords="offset points",
                         xytext=(0, -16), ha='center', fontsize=9, color='#FF6B6B', fontweight='bold')
        if len(ayt_rows) > 1:
            import numpy as np
            z = np.polyfit(ayt_idx, ayt_top, 1)
            p = np.poly1d(z)
            ax1.plot(ayt_idx, p(ayt_idx), '--', color='#FF6B6B', alpha=0.4, linewidth=1.5)

    ax1.set_title('Toplam Net Gelişimi (Deneme No.)', color='white', fontsize=12, pad=10)
    ax1.set_xlabel('Deneme Sayısı', color='#aaaaaa')
    ax1.set_ylabel('Toplam Net', color='#aaaaaa')
    _stil_ax(ax1)
    if has_data:
        ax1.legend(facecolor='#1a1a2e', labelcolor='white', fontsize=10)
        ax1.xaxis.set_major_locator(plt.MaxNLocator(integer=True))

    # ── Alt grafik: TYT ders bazlı ──
    ax2 = axes[1]
    ax2.set_facecolor('#16213e')

    if tyt_rows:
        idx = list(range(1, len(tyt_rows) + 1))
        ax2.plot(idx, [r['turkce'] for r in tyt_rows], 'o-', color='#FF6B6B', linewidth=2, markersize=7, label='Türkçe')
        ax2.plot(idx, [r['matematik'] for r in tyt_rows], 's-', color='#4ECDC4', linewidth=2, markersize=7, label='Matematik')
        ax2.plot(idx, [r['sosyal'] for r in tyt_rows], '^-', color='#FFE66D', linewidth=2, markersize=7, label='Sosyal')
        ax2.plot(idx, [r['fen'] for r in tyt_rows], 'D-', color='#A8E6CF', linewidth=2, markersize=7, label='Fen')
        ax2.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        ax2.legend(facecolor='#1a1a2e', labelcolor='white', fontsize=9, loc='upper left')
        ax2.set_title('TYT — Ders Bazlı Gelişim', color='white', fontsize=12, pad=10)
    else:
        ax2.text(0.5, 0.5, 'TYT verisi yok', ha='center', va='center',
                 color='#aaaaaa', fontsize=13, transform=ax2.transAxes)
        ax2.set_title('TYT — Ders Bazlı Gelişim', color='white', fontsize=12, pad=10)

    ax2.set_xlabel('Deneme Sayısı', color='#aaaaaa')
    ax2.set_ylabel('Net', color='#aaaaaa')
    _stil_ax(ax2)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    buf.seek(0)
    plt.close()

    # Özet metin
    lines = ["📉 *Deneme Sınavı Özeti*\n"]
    for tur, rows in [('TYT 📘', tyt_rows), ('AYT 📗', ayt_rows)]:
        if rows:
            toplamlar = [r['toplam'] for r in rows]
            fark = toplamlar[-1] - toplamlar[0]
            ok = '📈' if fark > 0 else ('📉' if fark < 0 else '➡️')
            lines.append(
                f"*{tur}* — {len(rows)} deneme\n"
                f"  İlk: `{toplamlar[0]:.1f}` → Son: `{toplamlar[-1]:.1f}` {ok} `{fark:+.1f}`\n"
                f"  En yüksek: `{max(toplamlar):.1f}`  Ort: `{sum(toplamlar)/len(toplamlar):.1f}`"
            )

    # Son 5 deneme listesi
    lines.append("\n*Son Denemeler:*")
    for r in son_denemeler(user_id, limit=5):
        alan_str = f" ({r['alan']})" if r['alan'] else ''
        lines.append(f"  • {r['tarih']} {r['tur']}{alan_str}: `{r['toplam']:.1f}` net")

    await update.message.reply_photo(
        photo=buf,
        caption='\n'.join(lines),
        parse_mode='Markdown'
    )

def _stil_ax(ax):
    ax.tick_params(colors='#aaaaaa')
    ax.grid(True, alpha=0.2, color='white')
    for spine in ax.spines.values():
        spine.set_color('#444')
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color('#aaaaaa')

# ── GÜNLÜK NET GİRİŞİ ────────────────────────────────────────────────────────

async def isle_net_girisi(update: Update, user_id: int, text: str):
    try:
        parcalar = text.upper().replace('NET:', '').strip().split()
        d = {'T': 0.0, 'M': 0.0, 'S': 0.0, 'F': 0.0}
        for p in parcalar:
            if ':' in p:
                k, v = p.split(':', 1)
                if k.strip() in d:
                    d[k.strip()] = float(v)
        net_kaydet(user_id, d['T'], d['M'], d['S'], d['F'])
        toplam = sum(d.values())
        await update.message.reply_text(
            f"✅ *Netlerin kaydedildi!*\n\n"
            f"📖 Türkçe: `{d['T']}`  🔢 Matematik: `{d['M']}`\n"
            f"🌍 Sosyal: `{d['S']}`  🔬 Fen: `{d['F']}`\n"
            f"━━━━━━━━━━━━━━\n"
            f"🎯 *Toplam: {toplam:.1f} net* | YKS'ye {kalan_gun()} gün kaldı",
            parse_mode='Markdown'
        )
    except Exception:
        await update.message.reply_text(
            "❌ Format hatalı! Şu şekilde yaz:\n`Net: T:28 M:22 S:18 F:20`",
            parse_mode='Markdown'
        )

# ── HAFTALIK GRAFİK ───────────────────────────────────────────────────────────

async def gonder_haftalik_grafik(update: Update, user_id: int):
    rows = haftalik_netler(user_id)
    if not rows:
        await update.message.reply_text(
            "📊 Henüz net verisi yok!\n\n`Net: T:28 M:22 S:18 F:20` formatıyla gir.",
            parse_mode='Markdown'
        )
        return

    await update.message.reply_text("📊 Grafik hazırlanıyor...")

    from datetime import datetime as dt
    tarihler = [dt.strptime(r['tarih'], '%Y-%m-%d') for r in rows]
    toplam_vals = [r['turkce'] + r['matematik'] + r['sosyal'] + r['fen'] for r in rows]
    ortalama = sum(toplam_vals) / len(toplam_vals)

    fig, axes = plt.subplots(2, 1, figsize=(10, 10), facecolor='#1a1a2e')
    fig.suptitle("Zeren'in Haftalık Net Takibi 🎯", fontsize=16, color='white', fontweight='bold', y=0.98)

    ax1 = axes[0]
    ax1.set_facecolor('#16213e')
    ax1.plot(tarihler, [r['turkce'] for r in rows], 'o-', color='#FF6B6B', linewidth=2.5, markersize=8, label='Türkçe')
    ax1.plot(tarihler, [r['matematik'] for r in rows], 'o-', color='#4ECDC4', linewidth=2.5, markersize=8, label='Matematik')
    ax1.plot(tarihler, [r['sosyal'] for r in rows], 'o-', color='#FFE66D', linewidth=2.5, markersize=8, label='Sosyal')
    ax1.plot(tarihler, [r['fen'] for r in rows], 'o-', color='#A8E6CF', linewidth=2.5, markersize=8, label='Fen')
    ax1.set_title('Derse Göre Netler', color='white', fontsize=12, pad=10)
    ax1.set_ylabel('Net Sayısı', color='#aaaaaa')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax1.legend(loc='upper left', facecolor='#1a1a2e', labelcolor='white', fontsize=9)
    _stil_ax(ax1)

    ax2 = axes[1]
    ax2.set_facecolor('#16213e')
    renkler = ['#e94560' if v == max(toplam_vals) else '#0f3460' for v in toplam_vals]
    bars = ax2.bar([t.strftime('%d %b') for t in tarihler], toplam_vals, color=renkler, edgecolor='#444')
    for bar, val in zip(bars, toplam_vals):
        ax2.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.3,
                 f'{val:.0f}', ha='center', va='bottom', color='white', fontsize=10, fontweight='bold')
    ax2.axhline(y=ortalama, color='#FFE66D', linestyle='--', linewidth=1.5, alpha=0.8, label=f'Ort: {ortalama:.1f}')
    ax2.set_title('Toplam Net (Son 7 Gün)', color='white', fontsize=12, pad=10)
    ax2.set_ylabel('Toplam Net', color='#aaaaaa')
    ax2.legend(facecolor='#1a1a2e', labelcolor='white', fontsize=9)
    _stil_ax(ax2)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    buf.seek(0)
    plt.close()

    await update.message.reply_photo(
        photo=buf,
        caption=(f"📊 *Haftalık Net Raporu*\n\n"
                 f"🎯 En yüksek: `{max(toplam_vals):.0f}` net\n"
                 f"📈 Haftalık ort: `{ortalama:.1f}` net\n"
                 f"📅 YKS'ye {kalan_gun()} gün kaldı"),
        parse_mode='Markdown'
    )

# ── DERS ANALİZİ ─────────────────────────────────────────────────────────────

async def gonder_ders_analizi(update: Update, user_id: int):
    istatistik = ders_istatistikleri(user_id)
    if not istatistik:
        await update.message.reply_text(
            "🏆 Henüz analiz için yeterli veri yok!\n\n`Net: T:28 M:22 S:18 F:20` formatıyla gir.",
            parse_mode='Markdown'
        )
        return

    dersler = ['turkce', 'matematik', 'sosyal', 'fen']
    etiketler = ['Türkçe', 'Matematik', 'Sosyal', 'Fen']
    renkler = ['#FF6B6B', '#4ECDC4', '#FFE66D', '#A8E6CF']
    ortalamalar = [istatistik[d]['ortalama'] for d in dersler]

    fig, axes = plt.subplots(1, 2, figsize=(12, 6), facecolor='#1a1a2e')
    fig.suptitle("Zeren'in Ders Performans Analizi 🏆", fontsize=14, color='white', fontweight='bold')

    ax1 = axes[0]
    ax1.set_facecolor('#16213e')
    wedges, texts, autotexts = ax1.pie(
        ortalamalar, labels=etiketler, colors=renkler, autopct='%1.1f%%', startangle=90,
        textprops={'color': 'white', 'fontsize': 10},
        wedgeprops={'edgecolor': '#1a1a2e', 'linewidth': 2}
    )
    for at in autotexts:
        at.set_color('black')
        at.set_fontweight('bold')
    ax1.set_title('Net Dağılımı (Ortalama)', color='white', fontsize=11, pad=15)

    ax2 = axes[1]
    ax2.set_facecolor('#16213e')
    x = range(len(dersler))
    w = 0.25
    maxlar = [istatistik[d]['max'] for d in dersler]
    minlar = [istatistik[d]['min'] for d in dersler]
    b1 = ax2.bar([i - w for i in x], ortalamalar, w, label='Ortalama', color='#4ECDC4', alpha=0.9)
    ax2.bar([i for i in x], maxlar, w, label='En Yüksek', color='#A8E6CF', alpha=0.9)
    ax2.bar([i + w for i in x], minlar, w, label='En Düşük', color='#FF6B6B', alpha=0.9)
    for bar in b1:
        ax2.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 0.3,
                 f'{bar.get_height():.1f}', ha='center', va='bottom', color='white', fontsize=8)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(etiketler, color='#aaaaaa')
    ax2.set_title('Ortalama / Maks / Min', color='white', fontsize=11, pad=15)
    ax2.legend(facecolor='#1a1a2e', labelcolor='white', fontsize=9)
    _stil_ax(ax2)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    buf.seek(0)
    plt.close()

    lines = ["🏆 *Ders Performans Analizi*\n"]
    for ders in dersler:
        st = istatistik[ders]
        ok = "📈" if st['trend'] > 0 else ("📉" if st['trend'] < 0 else "➡️")
        lines.append(
            f"{DERS_EMOJILER[ders]} *{DERS_ADLAR[ders]}*\n"
            f"  Ort: `{st['ortalama']:.1f}` | Maks: `{st['max']:.1f}` | Son: `{st['son']:.1f}` {ok}"
        )
    await update.message.reply_photo(photo=buf, caption='\n'.join(lines), parse_mode='Markdown')

# ── OTOMATİK GÖREVLER ────────────────────────────────────────────────────────

async def sabah_gorevi(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    msg = (
        f"☀️ *Günaydın Zeren!*\n\n"
        f"📅 YKS'ye son *{kalan_gun()} gün*.\n\n"
        f"💡 _{random.choice(MOTIVASYON)}_\n\n"
        f"🚀 Bugün neler yapacaksın? Planını yaz!\n"
        f"Net format: `Net: T:28 M:22 S:18 F:20`"
    )
    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')

async def oglen_gorevi(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    await context.bot.send_message(
        chat_id=chat_id,
        text=(f"🌞 *Öğle Hatırlatması!*\n\n"
              f"YKS'ye *{kalan_gun()} gün* kaldı.\n\n"
              f"💡 _{random.choice(MOTIVASYON)}_\n\n"
              f"Sabahki planına devam ediyor musun? 💪"),
        parse_mode='Markdown'
    )

async def aksam_gorevi(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    plan = gunun_plani(chat_id)
    plan_metni = plan['plan'] if plan else "Bugün bir plan belirtmemiştin."
    rows = haftalik_netler(chat_id)
    bugun = datetime.now().strftime('%Y-%m-%d')
    bugun_net = next((r for r in rows if r['tarih'] == bugun), None)
    net_satir = (
        f"\n\n📈 *Bugünkü netlerin:* T:{bugun_net['turkce']} M:{bugun_net['matematik']} "
        f"S:{bugun_net['sosyal']} F:{bugun_net['fen']}"
        if bugun_net else "\n\n📈 Bugün net girişi yapmadın. Yarın girmeyi unutma!"
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=(f"🌙 *Saat 23:00 oldu Zeren!*\n\n"
              f"Bugün şunları yapmayı planlamıştın:\n_{plan_metni}_"
              f"{net_satir}\n\nRaporunu ver! Hangilerini tamamladın? 📊"),
        parse_mode='Markdown'
    )

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("HATA: TELEGRAM_BOT_TOKEN ortam değişkeni ayarlanmamış!")
        return

    init_db()
    threading.Thread(target=run_web, daemon=True).start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(deneme_callback, pattern='^deneme_'))

    # Deneme girişi: TYT: veya AYT: ile başlayan mesajlar
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND &
        (filters.Regex(r'(?i)^tyt:') | filters.Regex(r'(?i)^ayt:')),
        isle_deneme_girisi
    ))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    job_queue = application.job_queue
    job_queue.run_daily(sabah_gorevi, time=time(hour=8, minute=0, tzinfo=TR_TIMEZONE), chat_id=CHAT_ID)
    job_queue.run_daily(oglen_gorevi, time=time(hour=13, minute=0, tzinfo=TR_TIMEZONE), chat_id=CHAT_ID)
    job_queue.run_daily(aksam_gorevi, time=time(hour=23, minute=0, tzinfo=TR_TIMEZONE), chat_id=CHAT_ID)

    print("✅ Zeren'in Nexus Botu çalışıyor...")
    application.run_polling()

if __name__ == '__main__':
    main()
