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
                          CallbackQueryHandler, filters, ContextTypes)

from db import (init_db, net_kaydet, haftalik_netler, tum_netler, ders_istatistikleri,
                plan_kaydet, gunun_plani, deneme_kaydet, denemeler_getir,
                son_denemeler, deneme_istatistikleri)

# ── WEB SUNUCUSU (RENDER UYUMU) ──────────────────────────────────────────────
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Zeren'in Nexus Botu Aktif ve Görev Başında! 🚀"

def run_web():
    # Render'ın verdiği PORT'u kullan, yoksa 8080 kullan
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

# ── AYARLAR ───────────────────────────────────────────────────────────────────
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
YKS_DATE = datetime(2026, 6, 20)
TR_TIMEZONE = pytz.timezone('Europe/Istanbul')
# Chat ID'yi güvenli bir şekilde al
chat_id_env = os.environ.get('TELEGRAM_CHAT_ID', '5314748039')
CHAT_ID = int(chat_id_env) if chat_id_env.isdigit() else 5314748039

MOTIVASYON = [
    "Bugün dünden daha iyi olmak için bir şansın var!",
    "Hedefin büyük, adımların kararlı olsun Zeren.",
    "Başarı, her gün tekrarlanan küçük çabaların toplamıdır.",
    "Zorlandığın anlarda neden başladığını hatırla.",
    "Bugündeki disiplinin, yarınki özgürlüğündür.",
    "Küçük adımlar, büyük yolculuklar başlatır.",
    "Her soru çözdüğünde YKS'ye bir adım daha yaklaşıyorsun.",
    "Yorulduğunda dur, ama asla vazgeçme.",
    "Deneme sınavları puanı değil, eksikleri görmek içindir.",
    "Hatalar seni geri değil, ileriye taşır.",
]

DERS_EMOJILER = {'turkce': '📖', 'matematik': '🔢', 'sosyal': '🌍', 'fen': '🔬'}
DERS_ADLAR = {'turkce': 'Türkçe', 'matematik': 'Matematik', 'sosyal': 'Sosyal', 'fen': 'Fen'}

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

    elif text.lower().startswith('bugün'):
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

# ── CALLBACK VE DENEME İŞLEME ───────────────────────────────────────────────

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
                "📘 *TYT Deneme Girişi*\nNetlerini şu formatta yaz:\n`TYT: T:32 M:28 S:15 F:18`",
                parse_mode='Markdown'
            )
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔢 Sayısal", callback_data='deneme_alan_Sayısal')],
                [InlineKeyboardButton("📖 Sözel", callback_data='deneme_alan_Sözel')],
                [InlineKeyboardButton("⚖️ Eşit Ağırlık (EA)", callback_data='deneme_alan_EA')],
            ])
            await query.edit_message_text("📗 *AYT Alanını seç:*", reply_markup=kb, parse_mode='Markdown')

    elif data.startswith('deneme_alan_'):
        alan = data.replace('deneme_alan_', '')
        context.user_data['deneme_alan'] = alan
        await query.edit_message_text(
            f"📗 *AYT {alan} Deneme Girişi*\nFormat:\n`AYT: M:30 Edb:18 Tar1:8 Cog1:5`",
            parse_mode='Markdown'
        )

async def isle_deneme_girisi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    tur = context.user_data.get('deneme_tur')
    alan = context.user_data.get('deneme_alan', '')

    if not tur: return

    try:
        prefix = 'TYT:' if tur == 'TYT' else 'AYT:'
        parcalar = text.upper().replace(prefix, '').strip().split()
        netlər = {}
        kisaltma_map = {'T': 'turkce', 'M': 'matematik', 'S': 'sosyal', 'F': 'fen', 'FIZ': 'fizik', 'KIM': 'kimya', 'BIO': 'biyoloji', 'EDB': 'edebiyat', 'TAR1': 'tarih1', 'COG1': 'cografya1'}
        
        for p in parcalar:
            if ':' in p:
                k, v = p.split(':', 1)
                col = kisaltma_map.get(k.strip())
                if col: netlər[col] = float(v)
        
        toplam = deneme_kaydet(user_id, tur, alan, netlər)
        await update.message.reply_text(f"✅ *{tur} Denemesi Kaydedildi!*\n🎯 Toplam: {toplam:.1f} net", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Hata! Formatı kontrol et.")

# ── GRAFİK VE ANALİZ (DETAYLAR) ──────────────────────────────────────────────

async def gonder_haftalik_grafik(update: Update, user_id: int):
    rows = haftalik_netler(user_id)
    if not rows:
        await update.message.reply_text("📊 Veri yok.")
        return
    
    tarihler = [r['tarih'] for r in rows]
    toplam_vals = [r['turkce'] + r['matematik'] + r['sosyal'] + r['fen'] for r in rows]
    
    plt.figure(figsize=(10, 5), facecolor='#1a1a2e')
    plt.plot(tarihler, toplam_vals, 'o-', color='#4ECDC4', linewidth=2)
    plt.title("Haftalık İlerlemen 📈", color='white')
    plt.grid(True, alpha=0.2)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#1a1a2e')
    buf.seek(0)
    plt.close()
    await update.message.reply_photo(photo=buf, caption="Haftalık netlerin hazır! 💪")

async def gonder_ders_analizi(update: Update, user_id: int):
    istatistik = ders_istatistikleri(user_id)
    if not istatistik:
        await update.message.reply_text("🏆 Analiz için veri lazım.")
        return
    
    lines = ["🏆 *Ders Analizi*"]
    for d in ['turkce', 'matematik', 'sosyal', 'fen']:
        s = istatistik[d]
        lines.append(f"• {DERS_ADLAR[d]}: Ort: `{s['ortalama']:.1f}`")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

async def gonder_deneme_ozet(update: Update, user_id: int):
    sonlar = son_denemeler(user_id, limit=5)
    if not sonlar:
        await update.message.reply_text("📉 Deneme yok.")
        return
    
    msg = "*Son 5 Deneme:*\n" + "\n".join([f"• {r['tarih']} {r['tur']}: `{r['toplam']:.1f}`" for r in sonlar])
    await update.message.reply_text(msg, parse_mode='Markdown')

async def isle_net_girisi(update: Update, user_id: int, text: str):
    try:
        parcalar = text.upper().replace('NET:', '').strip().split()
        d = {'T': 0.0, 'M': 0.0, 'S': 0.0, 'F': 0.0}
        for p in parcalar:
            if ':' in p:
                k, v = p.split(':', 1)
                if k.strip() in d: d[k.strip()] = float(v)
        net_kaydet(user_id, d['T'], d['M'], d['S'], d['F'])
        await update.message.reply_text(f"✅ Netler kaydedildi! Toplam: {sum(d.values()):.1f}")
    except:
        await update.message.reply_text("❌ Hata! Örnek: `Net: T:25 M:30 S:15 F:15`")

# ── OTOMATİK GÖREVLER ────────────────────────────────────────────────────────

async def sabah_gorevi(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="☀️ Günaydın Zeren! Bugünün planı nedir? 🚀")

async def aksam_gorevi(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=CHAT_ID, text="🌙 Saat 23:00! Raporları alalım, bugün neler yaptın? 📊")

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    if not TOKEN:
        print("HATA: TOKEN YOK!")
        return

    init_db()
    # Flask sunucusunu ayrı bir kolda başlat (Render için)
    threading.Thread(target=run_web, daemon=True).start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(deneme_callback, pattern='^deneme_'))
    application.add_handler(MessageHandler(filters.Regex(r'(?i)^(TYT:|AYT:)'), isle_deneme_girisi))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

   # Zamanlayıcıyı kontrol ederek başlat
    if application.job_queue:
        application.job_queue.run_daily(sabah_gorevi, time=time(8, 0, tzinfo=TR_TIMEZONE))
        application.job_queue.run_daily(aksam_gorevi, time=time(23, 0, tzinfo=TR_TIMEZONE))
        print("✅ Zamanlayıcı başarıyla kuruldu.")
    else:
        print("⚠️ Uyarı: JobQueue (zamanlayıcı) hazır değil. Bot çalışacak ama sabah mesajları gelmeyebilir.")

    print("✅ Nexus Botu Başlatıldı...")
    application.run_polling()

if __name__ == '__main__':
    main()
