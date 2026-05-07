import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'nexus.db')

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS nets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tarih TEXT NOT NULL,
                turkce REAL DEFAULT 0,
                matematik REAL DEFAULT 0,
                sosyal REAL DEFAULT 0,
                fen REAL DEFAULT 0,
                not_metni TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS planlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tarih TEXT NOT NULL,
                plan TEXT NOT NULL,
                tamamlandi INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS denemeler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tarih TEXT NOT NULL,
                tur TEXT NOT NULL,
                alan TEXT DEFAULT '',
                turkce REAL DEFAULT 0,
                matematik REAL DEFAULT 0,
                sosyal REAL DEFAULT 0,
                fen REAL DEFAULT 0,
                edebiyat REAL DEFAULT 0,
                tarih1 REAL DEFAULT 0,
                cografya1 REAL DEFAULT 0,
                tarih2 REAL DEFAULT 0,
                cografya2 REAL DEFAULT 0,
                felsefe REAL DEFAULT 0,
                din REAL DEFAULT 0,
                fizik REAL DEFAULT 0,
                kimya REAL DEFAULT 0,
                biyoloji REAL DEFAULT 0,
                mat_ayt REAL DEFAULT 0,
                toplam REAL DEFAULT 0,
                not_metni TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()

# ── GÜNLÜK NET ──────────────────────────────────────────────────────────────

def net_kaydet(user_id: int, turkce: float, matematik: float, sosyal: float, fen: float, not_metni: str = ''):
    tarih = datetime.now().strftime('%Y-%m-%d')
    with get_conn() as conn:
        existing = conn.execute(
            'SELECT id FROM nets WHERE user_id=? AND tarih=?', (user_id, tarih)
        ).fetchone()
        if existing:
            conn.execute(
                'UPDATE nets SET turkce=?, matematik=?, sosyal=?, fen=?, not_metni=? WHERE user_id=? AND tarih=?',
                (turkce, matematik, sosyal, fen, not_metni, user_id, tarih)
            )
        else:
            conn.execute(
                'INSERT INTO nets (user_id, tarih, turkce, matematik, sosyal, fen, not_metni, created_at) VALUES (?,?,?,?,?,?,?,?)',
                (user_id, tarih, turkce, matematik, sosyal, fen, not_metni, datetime.now().isoformat())
            )
        conn.commit()

def haftalik_netler(user_id: int):
    bitis = datetime.now()
    baslangic = bitis - timedelta(days=6)
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT * FROM nets WHERE user_id=? AND tarih>=? AND tarih<=? ORDER BY tarih ASC',
            (user_id, baslangic.strftime('%Y-%m-%d'), bitis.strftime('%Y-%m-%d'))
        ).fetchall()
    return [dict(r) for r in rows]

def tum_netler(user_id: int, limit: int = 30):
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT * FROM nets WHERE user_id=? ORDER BY tarih DESC LIMIT ?',
            (user_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]

def ders_istatistikleri(user_id: int):
    rows = tum_netler(user_id, limit=30)
    if not rows:
        return None
    dersler = ['turkce', 'matematik', 'sosyal', 'fen']
    sonuc = {}
    for ders in dersler:
        degerler = [r[ders] for r in rows if r[ders] > 0]
        if degerler:
            sonuc[ders] = {
                'ortalama': sum(degerler) / len(degerler),
                'max': max(degerler),
                'min': min(degerler),
                'son': degerler[0],
                'trend': degerler[0] - degerler[-1] if len(degerler) > 1 else 0
            }
        else:
            sonuc[ders] = {'ortalama': 0, 'max': 0, 'min': 0, 'son': 0, 'trend': 0}
    return sonuc

# ── PLAN ────────────────────────────────────────────────────────────────────

def plan_kaydet(user_id: int, plan: str):
    tarih = datetime.now().strftime('%Y-%m-%d')
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO planlar (user_id, tarih, plan, created_at) VALUES (?,?,?,?)',
            (user_id, tarih, plan, datetime.now().isoformat())
        )
        conn.commit()

def gunun_plani(user_id: int):
    tarih = datetime.now().strftime('%Y-%m-%d')
    with get_conn() as conn:
        row = conn.execute(
            'SELECT * FROM planlar WHERE user_id=? AND tarih=? ORDER BY id DESC LIMIT 1',
            (user_id, tarih)
        ).fetchone()
    return dict(row) if row else None

# ── DENEME ───────────────────────────────────────────────────────────────────

def deneme_kaydet(user_id: int, tur: str, alan: str, netlər: dict, not_metni: str = ''):
    """
    tur: 'TYT' veya 'AYT'
    alan: '' (TYT için), 'Sayısal', 'Sözel', 'EA'
    netlər: dict of field → value  e.g. {'turkce': 32, 'matematik': 28, ...}
    """
    tarih = datetime.now().strftime('%Y-%m-%d')
    fields = ['turkce','matematik','sosyal','fen','edebiyat','tarih1','cografya1',
              'tarih2','cografya2','felsefe','din','fizik','kimya','biyoloji','mat_ayt']
    vals = {f: float(netlər.get(f, 0)) for f in fields}
    toplam = sum(vals.values())
    with get_conn() as conn:
        conn.execute(
            '''INSERT INTO denemeler
               (user_id, tarih, tur, alan,
                turkce, matematik, sosyal, fen,
                edebiyat, tarih1, cografya1, tarih2, cografya2, felsefe, din,
                fizik, kimya, biyoloji, mat_ayt,
                toplam, not_metni, created_at)
               VALUES (?,?,?,?, ?,?,?,?, ?,?,?,?,?,?,?, ?,?,?,?, ?,?,?)''',
            (user_id, tarih, tur, alan,
             vals['turkce'], vals['matematik'], vals['sosyal'], vals['fen'],
             vals['edebiyat'], vals['tarih1'], vals['cografya1'], vals['tarih2'],
             vals['cografya2'], vals['felsefe'], vals['din'],
             vals['fizik'], vals['kimya'], vals['biyoloji'], vals['mat_ayt'],
             toplam, not_metni, datetime.now().isoformat())
        )
        conn.commit()
    return toplam

def denemeler_getir(user_id: int, tur: str = None, limit: int = 20):
    with get_conn() as conn:
        if tur:
            rows = conn.execute(
                'SELECT * FROM denemeler WHERE user_id=? AND tur=? ORDER BY tarih ASC, id ASC LIMIT ?',
                (user_id, tur, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM denemeler WHERE user_id=? ORDER BY tarih ASC, id ASC LIMIT ?',
                (user_id, limit)
            ).fetchall()
    return [dict(r) for r in rows]

def son_denemeler(user_id: int, limit: int = 5):
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT * FROM denemeler WHERE user_id=? ORDER BY tarih DESC, id DESC LIMIT ?',
            (user_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]

def deneme_istatistikleri(user_id: int, tur: str):
    rows = denemeler_getir(user_id, tur=tur, limit=50)
    if not rows:
        return None
    toplamlar = [r['toplam'] for r in rows]
    return {
        'sayi': len(rows),
        'ilk': toplamlar[0],
        'son': toplamlar[-1],
        'max': max(toplamlar),
        'min': min(toplamlar),
        'ortalama': sum(toplamlar) / len(toplamlar),
        'gelisim': toplamlar[-1] - toplamlar[0],
        'rows': rows
    }
