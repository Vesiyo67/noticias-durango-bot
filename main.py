import os, requests, sqlite3, logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GNEWS_KEY = os.getenv("GNEWS_API_KEY")

DB_FILE = "noticias.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS noticias (
            url TEXT PRIMARY KEY, titulo TEXT, categoria TEXT, fuente TEXT,
            fecha TEXT, resumen TEXT, enviado INTEGER DEFAULT 0)''')

CATEGORIAS = {
    "Política": ["presidente", "senado", "diputados", "gobierno", "ley", "electoral", "partido", "congreso", "sheinbaum", "amlo"],
    "Economía": ["peso", "inflación", "banxico", "bolsa", "empresas", "inversión", "turismo", "comercio", "petróleo", "dólar"],
    "Tecnología": ["ia", "inteligencia artificial", "ciberseguridad", "startup", "tech", "software", "digital", "5g"],
    "Deportes": ["fútbol", "selección", "liga mx", "olímpicos", "box", "fórmula", "deportivo", "campeonato", "chivas", "américa"],
    "Sociedad": ["seguridad", "educación", "salud", "migrantes", "clima", "desastre", "protesta", "comunidad", "violencia"]
}

def obtener_categoria(titulo, desc=""):
    texto = f"{titulo} {desc}".lower()
    for cat, palabras in CATEGORIAS.items():
        if any(p in texto for p in palabras):
            return cat
    return "General"

def obtener_noticias():
    try:
        print("📰 Obteniendo noticias de México...")
        url = f"https://gnews.io/api/v4/top-headlines?country=mx&lang=es&max=10&apikey={GNEWS_KEY}"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        print(f"✅ Noticias obtenidas: {len(articles)}")
        return [a for a in articles if a.get("title") and a.get("url")]
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def resumen_inteligente(desc, titulo):
    if not desc:
        return titulo[:90] + "..."
    return desc.split(".")[0].strip() + "."

URGENCIA = ["urgente", "última hora", "alerta", "sismo", "rompe", "exclusiva", "emergencia", "tragedia", "ataque", "tiroteo"]
def es_urgente(titulo, desc=""):
    return any(p in f"{titulo} {desc}".lower() for p in URGENCIA)

def enviar_telegram(texto):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "Markdown", "disable_web_page_preview": False}
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Mensaje enviado a Telegram")
            return True
        print(f"❌ Error Telegram: {r.text}")
        return False
    except Exception as e:
        print(f"❌ Error conexión: {e}")
        return False

def digest_diario():
    print("📅 Generando digest diario...")
    noticias = obtener_noticias()
    
    if not noticias:
        enviar_telegram("️ No se pudieron obtener noticias hoy.")
        return

    hoy = datetime.now().strftime("%A, %d de %B")
    msg = f"🇲🇽 *Noticias México - {hoy}*\n\n"
    
    for i, n in enumerate(noticias[:5], 1):
        cat = obtener_categoria(n["title"], n.get("description", ""))
        resumen = resumen_inteligente(n.get("description", ""), n["title"])
        fuente = n.get("source", {}).get("name", "N/A")
        
        msg += f"🔹 *{i}. [{cat}] {n['title']}*\n"
        msg += f"📝 {resumen}\n"
        msg += f"📰 {fuente} |  [Abrir]({n['url']})\n\n"
        
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT OR IGNORE INTO noticias (url,titulo,categoria,fuente,fecha,resumen) VALUES (?,?,?,?,?,?)",
                         (n["url"], n["title"], cat, fuente, datetime.now().strftime("%Y-%m-%d"), resumen))
    
    msg += "_📁 Historial guardado | Agente 🤖_"
    enviar_telegram(msg)
    print("✅ Digest completado")

def revisar_urgentes():
    print("🔍 Revisando urgentes...")
    noticias = obtener_noticias()
    hoy = datetime.now().strftime("%Y-%m-%d")
    
    for n in noticias:
        url = n.get("url", "")
        if not url:
            continue
        
        with sqlite3.connect(DB_FILE) as conn:
            if conn.execute("SELECT 1 FROM noticias WHERE url=? AND fecha=?", (url, hoy)).fetchone():
                continue
        
        if es_urgente(n["title"], n.get("description", "")):
            cat = obtener_categoria(n["title"], n.get("description", ""))
            fuente = n.get("source", {}).get("name", "N/A")
            msg = f"🚨 *ALERTA URGENTE*\n📰 {n['title']}\n🗂️ {cat} • {fuente}\n🕐 {datetime.now().strftime('%H:%M')}\n🔗 [Ver]({url})"
            enviar_telegram(msg)
            
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("INSERT OR IGNORE INTO noticias (url,titulo,categoria,fuente,fecha,resumen,enviado) VALUES (?,?,?,?,?,?,1)",
                             (url, n["title"], cat, fuente, hoy, n.get("description","")[:100]))
            print("✅ Alerta enviada")

if __name__ == "__main__":
    init_db()
    digest_diario()
