from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
import sqlite3
from weasyprint import HTML
from datetime import datetime
import json
import io
import numpy as np
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters
import matplotlib.pyplot as plt
import matplotlib
import grafik
matplotlib.use('Agg')
import threading
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

TELEGRAM_TOKEN = "API Token Here"

DB_NAME = 'energi.db'
DB_TIMEOUT = 10

NAMA_PERANGKAT, DAYA_PERANGKAT, PENGGUNAAN_PERANGKAT = range(3)

def enable_wal_mode():
    logger.info("Mencoba mengaktifkan WAL mode...")
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()
        if mode and mode[0].lower() == 'wal':
            logger.info(f"WAL mode berhasil diaktifkan. Mode saat ini: {mode[0]}")
        else:
            logger.warning(f"Gagal mengaktifkan WAL mode atau mode tidak terkonfirmasi. Mode saat ini: {mode[0] if mode else 'Tidak diketahui'}")
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error saat mengaktifkan WAL mode: {e}")
    finally:
        if conn:
            conn.close()

def init_db():
    logger.info("Menginisialisasi database...")
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS perangkat 
                 (id INTEGER PRIMARY KEY, nama TEXT, daya INTEGER, penggunaan REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS konsumsi 
                 (id INTEGER PRIMARY KEY, tanggal TEXT, penggunaan REAL)''')
    default_devices = ['Unit AC', 'Kulkas', 'Pencahayaan']
    for device_name in default_devices: 
        c.execute("DELETE FROM perangkat WHERE nama = ?", (device_name,))
    
    conn.commit()
    conn.close()
    logger.info("Database berhasil diinisialisasi tanpa data konsumsi contoh acak.")

def analisis_hasil_penggunaan():
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    try:
        c.execute("SELECT tanggal, penggunaan FROM konsumsi ORDER BY tanggal DESC LIMIT 30")
        data_konsumsi = c.fetchall()
        data_konsumsi = list(reversed(data_konsumsi))

        if not data_konsumsi or len(data_konsumsi) < 2:
            return {
                'status': 'Data tidak cukup',
                'pesan': 'Belum ada cukup data konsumsi yang tersedia untuk analisis mendalam.'
            }
        
        nilai_konsumsi = [row[1] for row in data_konsumsi]
        rata_rata = sum(nilai_konsumsi) / len(nilai_konsumsi)
        tertinggi = max(nilai_konsumsi)
        terendah = min(nilai_konsumsi)
        std_dev = np.std(nilai_konsumsi)

        if len(nilai_konsumsi) >= 7:
            tren_terakhir = nilai_konsumsi[-7:]
            x = list(range(len(tren_terakhir)))
            z = np.polyfit(x, tren_terakhir, 1)
            slope = z[0]
            tren_status = "meningkat" if slope > 0.1 else "menurun" if slope < -0.1 else "stabil"
        elif len(nilai_konsumsi) >=2:
            tren_status = "meningkat" if nilai_konsumsi[-1] > nilai_konsumsi[0] else "menurun" if nilai_konsumsi[-1] < nilai_konsumsi[0] else "stabil"
        else:
            tren_status = "belum dapat ditentukan (data tidak cukup)"

        hari_tertinggi = "N/A"
        if nilai_konsumsi:
            index_tertinggi = nilai_konsumsi.index(tertinggi)
            if index_tertinggi < len(data_konsumsi):
                 hari_tertinggi = data_konsumsi[index_tertinggi][0]

        rata_rata_nasional = 12.5
        perbandingan = (rata_rata / rata_rata_nasional - 1) * 100
        potensi_hemat = 0
        if rata_rata > rata_rata_nasional:
            potensi_hemat = (rata_rata - rata_rata_nasional) * 30 * 1500
        perkiraan_tagihan = rata_rata * 30 * 1500
        
        return {
            'periode': f"{data_konsumsi[0][0]} hingga {data_konsumsi[-1][0]}" if data_konsumsi else "N/A",
            'rata_rata': round(rata_rata, 2),
            'tertinggi': tertinggi,
            'terendah': terendah,
            'standar_deviasi': round(std_dev, 2),
            'tren': tren_status,
            'hari_tertinggi': hari_tertinggi,
            'perbandingan_nasional': round(perbandingan, 1),
            'potensi_hemat': int(potensi_hemat),
            'perkiraan_tagihan': int(perkiraan_tagihan)
        }
    except sqlite3.Error as e:
        logger.error(f"Database error di analisis_hasil_penggunaan: {e}")
        return {'status': 'Error Database', 'pesan': f'Terjadi kesalahan database: {e}'}
    finally:
        if conn:
            conn.close()

@app.route('/')
def index():
    logger.info("Mengakses halaman utama...")
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM perangkat")
        perangkat_data = c.fetchall() 
        c.execute("SELECT tanggal, penggunaan FROM konsumsi ORDER BY tanggal DESC LIMIT 7")
        konsumsi_terakhir = c.fetchall()
        return render_template('index.html', perangkat=perangkat_data, konsumsi=konsumsi_terakhir)
    except sqlite3.Error as e:
        logger.error(f"Database error di index route: {e}")
        return "Terjadi kesalahan database, silakan coba lagi nanti.", 500
    finally:
        if conn:
            conn.close()

@app.route('/tambah_perangkat', methods=['GET', 'POST'])
def tambah_perangkat():
    logger.info("Mengakses halaman tambah perangkat...")
    if request.method == 'POST':
        nama = request.form['nama']
        daya = int(request.form['daya'])
        penggunaan = float(request.form['penggunaan'])
        conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO perangkat (nama, daya, penggunaan) VALUES (?, ?, ?)", 
                      (nama, daya, penggunaan))
            conn.commit()
            grafik.update_konsumsi_hari_ini() 
            logger.info(f"Berhasil menambahkan perangkat baru: {nama} dan mengupdate konsumsi harian.")
            return redirect(url_for('index'))
        except sqlite3.Error as e:
            logger.error(f"Database error saat tambah perangkat (web): {e}")
            return "Gagal menambahkan perangkat karena kesalahan database.", 500
        finally:
            if conn:
                conn.close()
    return render_template('tambah_perangkat.html')

@app.route('/hapus_perangkat/<nama>', methods=['GET'])
def hapus_perangkat(nama):
    logger.info(f"Mengakses rute untuk menghapus perangkat: {nama}...")
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM perangkat WHERE nama = ?", (nama,))
        conn.commit()
        grafik.update_konsumsi_hari_ini() 
        logger.info(f"Berhasil menghapus perangkat: {nama} dan mengupdate konsumsi harian.")
        return redirect(url_for('index'))
    except sqlite3.Error as e:
        logger.error(f"Database error saat hapus perangkat (web): {e}")
        return "Gagal menghapus perangkat karena kesalahan database.", 500
    finally:
        if conn:
            conn.close()

@app.route('/hapus_semua_perangkat', methods=['GET'])
def hapus_semua_perangkat():
    logger.info("Mengakses rute untuk menghapus semua perangkat...")
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM perangkat")
        conn.commit()
        grafik.update_konsumsi_hari_ini() 
        logger.info("Berhasil menghapus semua perangkat dan mengupdate konsumsi harian.")
        return redirect(url_for('index'))
    except sqlite3.Error as e:
        logger.error(f"Database error saat hapus semua perangkat (web): {e}")
        return "Gagal menghapus semua perangkat karena kesalahan database.", 500
    finally:
        if conn:
            conn.close()

@app.route('/hasil_penggunaan')
def hasil_penggunaan():
    logger.info("Mengakses halaman hasil penggunaan...")
    hasil = analisis_hasil_penggunaan()
    if hasil.get('status') == 'Error Database':
         return render_template('hasil_penggunaan.html', hasil=hasil, tanggal="[]", nilai="[]", error_db=True)

    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    try:
        c.execute("SELECT tanggal, penggunaan FROM konsumsi ORDER BY tanggal DESC LIMIT 30")
        data_konsumsi = list(reversed(c.fetchall()))
        tanggal = [row[0] for row in data_konsumsi]
        nilai = [row[1] for row in data_konsumsi]
        return render_template('hasil_penggunaan.html', hasil=hasil, tanggal=json.dumps(tanggal), nilai=json.dumps(nilai))
    except sqlite3.Error as e:
        logger.error(f"Database error di hasil_penggunaan (web): {e}")
        return render_template('hasil_penggunaan.html', hasil=hasil, tanggal="[]", nilai="[]", error_db_grafik=True)
    finally:
        if conn:
            conn.close()

def dapatkan_saran_penggunaan():
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    saran_list = []
    perangkat_ditemukan = {}

    try:
        c.execute("SELECT penggunaan FROM konsumsi ORDER BY tanggal DESC LIMIT 7")
        konsumsi_terakhir = [row[0] for row in c.fetchall()]
        rata_rata_konsumsi_mingguan = sum(konsumsi_terakhir) / len(konsumsi_terakhir) if konsumsi_terakhir else 0
        
        c.execute("SELECT nama, daya, penggunaan FROM perangkat ORDER BY penggunaan DESC")
        perangkat_data = c.fetchall()
        
        if len(konsumsi_terakhir) >= 3:
            if konsumsi_terakhir[0] > konsumsi_terakhir[1] * 1.1 and konsumsi_terakhir[1] > konsumsi_terakhir[2] * 1.1: # Peningkatan signifikan
                saran_list.append("⚠️ Tren konsumsi energi Anda meningkat signifikan beberapa hari terakhir. Periksa penggunaan perangkat Anda.")
            elif konsumsi_terakhir[0] < konsumsi_terakhir[1] * 0.9 and konsumsi_terakhir[1] < konsumsi_terakhir[2] * 0.9: # Penurunan signifikan
                saran_list.append("👍 Tren konsumsi energi Anda menurun. Pertahankan!")

        if rata_rata_konsumsi_mingguan > 15:
            saran_list.append(f"Rata-rata konsumsi harian Anda ({rata_rata_konsumsi_mingguan:.2f} kWh) cukup tinggi. Identifikasi perangkat boros energi.")
        elif rata_rata_konsumsi_mingguan > 0 and rata_rata_konsumsi_mingguan < 5:
             saran_list.append(f"Rata-rata konsumsi harian Anda ({rata_rata_konsumsi_mingguan:.2f} kWh) tergolong efisien. Bagus!")

        if perangkat_data:
            perangkat_terboros = perangkat_data[0]
            if perangkat_terboros[2] > (0.3 * rata_rata_konsumsi_mingguan if rata_rata_konsumsi_mingguan > 0 else 1): # Jika konsumsi perangkat > 30% total rata2
                 saran_list.append(f"⚡ Perangkat '{perangkat_terboros[0]}' ({perangkat_terboros[2]:.2f} kWh) adalah konsumen energi terbesar Anda. Fokus optimasi pada perangkat ini.")

            for nama_perangkat, daya, penggunaan_harian in perangkat_data:
                nama_lower = nama_perangkat.lower()
                if ("ac" in nama_lower or "pendingin ruangan" in nama_lower) and "ac" not in perangkat_ditemukan:
                    saran_list.append("❄️ AC: Atur suhu AC ke 24-25°C. Matikan jika ruangan tidak digunakan & bersihkan filter secara berkala.")
                    perangkat_ditemukan["ac"] = True
                elif ("kulkas" in nama_lower or "lemari es" in nama_lower) and "kulkas" not in perangkat_ditemukan:
                    saran_list.append("🧊 Kulkas: Pastikan pintu kulkas tertutup rapat & jangan masukkan makanan panas langsung.")
                    perangkat_ditemukan["kulkas"] = True
                elif ("lampu" in nama_lower or "pencahayaan" in nama_lower or "penerangan" in nama_lower) and "lampu" not in perangkat_ditemukan:
                    saran_list.append("💡 Lampu: Gunakan lampu LED hemat energi & matikan lampu jika tidak diperlukan.")
                    perangkat_ditemukan["lampu"] = True
                elif ("tv" in nama_lower or "televisi" in nama_lower) and "tv" not in perangkat_ditemukan:
                    saran_list.append("📺 TV: Matikan TV sepenuhnya (jangan standby) saat tidak ditonton.")
                    perangkat_ditemukan["tv"] = True
                elif ("mesin cuci" in nama_lower) and "mesincuci" not in perangkat_ditemukan:
                    saran_list.append("🧺 Mesin Cuci: Gunakan mesin cuci dengan beban penuh & gunakan mode hemat energi jika ada.")
                    perangkat_ditemukan["mesincuci"] = True
                elif ("pompa air" in nama_lower or "sanyo" in nama_lower) and "pompa" not in perangkat_ditemukan:
                    saran_list.append("💧 Pompa Air: Gunakan tandon air untuk mengurangi frekuensi menyala pompa & periksa kebocoran pipa.")
                    perangkat_ditemukan["pompa"] = True
                elif ("komputer" in nama_lower or "pc" in nama_lower or "laptop" in nama_lower) and "komputer" not in perangkat_ditemukan:
                    saran_list.append("💻 Komputer/Laptop: Aktifkan mode sleep saat tidak digunakan & matikan monitor jika meninggalkan meja.")
                    perangkat_ditemukan["komputer"] = True
                elif ("rice cooker" in nama_lower or "magic jar" in nama_lower or "penanak nasi" in nama_lower) and "ricecooker" not in perangkat_ditemukan:
                    saran_list.append("🍚 Rice Cooker: Cabut dari listrik jika nasi sudah matang dan tidak perlu dihangatkan terlalu lama.")
                    perangkat_ditemukan["ricecooker"] = True
                elif ("dispenser" in nama_lower) and "dispenser" not in perangkat_ditemukan:
                    saran_list.append("🥤 Dispenser: Matikan mode pemanas/pendingin jika tidak dibutuhkan, terutama di malam hari.")
                    perangkat_ditemukan["dispenser"] = True

        if not perangkat_data or len(saran_list) < 2:
            saran_list.extend([
                "🔌 Cabut charger dan peralatan elektronik dari stopkontak jika sudah tidak digunakan (hindari daya standby).",
                "☀️ Manfaatkan pencahayaan alami semaksimal mungkin di siang hari.",
                "💨 Perhatikan ventilasi ruangan untuk mengurangi ketergantungan pada AC atau kipas angin."
            ])
        
        saran_unik = list(dict.fromkeys(saran_list))
        return saran_unik[:7]

    except sqlite3.Error as e:
        logger.error(f"Database error di dapatkan_saran_penggunaan: {e}")
        return ["Maaf, terjadi kesalahan saat mengambil data untuk saran."]
    finally:
        if conn:
            conn.close()


async def saran_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Perintah /saran diterima.")
    try:
        saran_list_data = dapatkan_saran_penggunaan()
        if not saran_list_data or (len(saran_list_data) == 1 and "Maaf, terjadi kesalahan" in saran_list_data[0]):
            await update.message.reply_text(saran_list_data[0] if saran_list_data else "Belum ada saran yang dapat diberikan saat ini. Pastikan data konsumsi sudah tercatat.")
            return

        pesan = "💡 Rekomendasi Penghematan Energi Untuk Anda:\n\n"
        for i, s_item in enumerate(saran_list_data, 1):
            pesan += f"▪️ {s_item}\n"
        await update.message.reply_text(pesan)
    except Exception as e: 
        logger.error(f"Error saat mengambil saran (Telegram): {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat memproses permintaan saran. Silakan coba lagi nanti.")

async def laporan_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Perintah /laporan diterima.")
    try:
        grafik.update_konsumsi_hari_ini() 
        await grafik.laporan(update, context) 
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            logger.error(f"Database terkunci saat membuat laporan (Telegram): {e}")
            await update.message.reply_text("Database sedang sibuk, coba beberapa saat lagi untuk membuat laporan.")
        else:
            logger.error(f"Error database operasional saat membuat laporan (Telegram): {e}")
            await update.message.reply_text("Terjadi masalah dengan database saat membuat laporan. Silakan coba lagi nanti.")
    except Exception as e:
        logger.error(f"Error saat memanggil laporan dari modul grafik (Telegram): {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat membuat laporan. Silakan coba lagi nanti.")


@app.route('/ekspor_pdf', methods=['POST'])
def ekspor_pdf():
    logger.info("Mengekspor laporan PDF...")
    conn = None 
    try:
        conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
        c = conn.cursor()
        c.execute("SELECT * FROM perangkat")
        perangkat_db = c.fetchall() 
        
        grafik.update_konsumsi_hari_ini()
        
        c.execute("SELECT penggunaan FROM konsumsi WHERE tanggal = ?", (datetime.now().strftime('%Y-%m-%d'),))
        konsumsi_hr_ini = c.fetchone()
        total_harian_aktual_db = konsumsi_hr_ini[0] if konsumsi_hr_ini else 0

        rekomendasi_list = dapatkan_saran_penggunaan() 

        html_content = f"""
        <html>
        <head>
            <title>Laporan Energi</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; color: #333; }}
                h1 {{ color: #2E8B57; text-align: center; }}
                h2 {{ color: #4682B4; border-bottom: 2px solid #4682B4; padding-bottom: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f8f9fa; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                ul {{ margin: 20px 0; padding-left: 20px; list-style-type: '▪️ '; /* Menggunakan emoji sebagai bullet point */}}
                li {{ margin-bottom: 8px; padding-left: 5px; }}
                .summary {{ background-color: #e8f5e8; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #2E8B57; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <h1>📊 Laporan Sistem Pemantauan Energi Cerdas</h1>

            <div class="summary">
                <h3>🔋 Ringkasan Konsumsi Energi</h3>
                <p><strong>Total Konsumsi Harian (dari tabel konsumsi):</strong> {total_harian_aktual_db:.2f} kWh</p>
                <p><strong>Estimasi Biaya Harian:</strong> Rp {total_harian_aktual_db * 1500:.0f}</p>
                <p><strong>Estimasi Biaya Bulanan:</strong> Rp {total_harian_aktual_db * 1500 * 30:.0f}</p>
                <p><em>*Asumsi tarif listrik Rp 1.500 per kWh</em></p>
            </div>
            
            <h2>⚡ Detail Konsumsi Per Perangkat</h2>
        """
        if perangkat_db:
            html_content += """
                <table>
                    <tr>
                        <th>Nama Perangkat</th>
                        <th>Daya Terpasang (W)</th>
                        <th>Konsumsi Harian (kWh)</th>
                        <th>Persentase (%)</th>
                        <th>Biaya Harian (Rp)</th>
                    </tr>
            """
            for d_item in perangkat_db:
                persentase = (d_item[3] / total_harian_aktual_db * 100) if total_harian_aktual_db > 0 else 0
                html_content += f'''<tr>
                        <td>{d_item[1]}</td>
                        <td>{d_item[2]}</td>
                        <td>{d_item[3]:.2f}</td>
                        <td>{persentase:.1f}%</td>
                        <td>Rp {d_item[3] * 1500:.0f}</td>
                    </tr>'''
            html_content += "</table>"
        else:
            html_content += "<p>Tidak ada perangkat terdaftar.</p>"

        html_content += f"""
            <h2>💡 Rekomendasi Penghematan Energi</h2>
            <ul>
                {''.join([f'<li>{r}</li>' for r in rekomendasi_list])}
            </ul>
            
            <div class="footer">
                <p>Laporan dibuat pada {datetime.now().strftime('%d %B %Y, %H:%M:%S')}</p>
                <p>Sistem Pemantauan Energi Cerdas v1.0</p>
            </div>
        </body>
        </html>
        """
        
        pdf_buffer = io.BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        logger.info("Laporan PDF berhasil dibuat.")
        return send_file(pdf_buffer, as_attachment=True, download_name=f'laporan_energi_{datetime.now().strftime("%Y%m%d")}.pdf', mimetype='application/pdf')
    except sqlite3.Error as e:
        logger.error(f"Database error saat ekspor PDF: {e}")
        return jsonify({"error": f"Gagal membuat laporan PDF karena kesalahan database: {e}"}), 500
    except Exception as e:
        logger.error(f"Error saat mengekspor PDF: {e}")
        return jsonify({"error": f"Gagal membuat laporan PDF: {e}"}), 500
    finally:
        if conn:
            conn.close() 
        
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Perintah /start diterima.")
    await update.message.reply_text(
        "Selamat datang di Sistem Pemantauan Energi Cerdas!\n"
        "Perintah yang tersedia:\n"
        "/perangkat - Lihat konsumsi perangkat\n"
        "/tambah_perangkat - Tambahkan perangkat baru\n"
        "/hapus_perangkat <nama> - Hapus perangkat tertentu\n"
        "/hapus_semua_perangkat - Hapus semua perangkat\n"
        "/grafik [mingguan/bulanan] - Lihat tren konsumsi energi\n"
        "/hasil - Lihat hasil analisis penggunaan energi\n"
        "/laporan - Unduh laporan PDF\n"
        "/saran - Dapatkan saran penghematan energi\n" 
    )

async def perangkat_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    logger.info("Perintah /perangkat diterima.")
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    try:
        c.execute("SELECT * FROM perangkat")
        perangkat_list = c.fetchall() 
        if not perangkat_list:
            await update.message.reply_text("Belum ada perangkat yang terdaftar.")
            return
        pesan = "Konsumsi Perangkat:\n"
        for p_item in perangkat_list: 
            pesan += f"{p_item[1]}: {p_item[2]} W, {p_item[3]} kWh\n"
        await update.message.reply_text(pesan)
    except sqlite3.Error as e:
        logger.error(f"Database error di perangkat_telegram: {e}")
        await update.message.reply_text("Terjadi kesalahan saat mengambil data perangkat. Coba lagi nanti.")
    finally:
        if conn:
            conn.close()

async def grafik_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    logger.info("Perintah /grafik diterima.")
    # tipe = 'mingguan' # Default sudah ada di grafik.grafik
    # if context.args and context.args[0].lower() in ['mingguan', 'bulanan']: 
    #     tipe = context.args[0].lower()
    
    try:
        await grafik.grafik(update, context) 
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            logger.error(f"Database terkunci saat membuat grafik (Telegram): {e}")
            await update.message.reply_text("Database sedang sibuk, coba beberapa saat lagi untuk membuat grafik.")
        else:
            logger.error(f"Error database operasional saat membuat grafik (Telegram): {e}")
            await update.message.reply_text("Terjadi masalah dengan database saat membuat grafik. Silakan coba lagi nanti.")
    except Exception as e:
        logger.error(f"Error saat memanggil grafik.grafik (Telegram): {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat membuat grafik. Silakan coba lagi nanti.")


async def hasil_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    logger.info("Perintah /hasil diterima.")
    try:
        grafik.update_konsumsi_hari_ini() 
        
        hasil_analisis = analisis_hasil_penggunaan()
        if 'status' in hasil_analisis and (hasil_analisis['status'] == 'Data tidak cukup' or hasil_analisis['status'] == 'Error Database'):
            await update.message.reply_text(hasil_analisis['pesan'])
            return
        
        pesan = "📊 Hasil Analisis Penggunaan Energi:\n\n"
        pesan += f"🔹 **Periode Analisis:** {hasil_analisis.get('periode', 'N/A')}\n" 
        pesan += f"🔹 **Konsumsi Rata-rata:** {hasil_analisis.get('rata_rata', 0):.2f} kWh/hari\n"
        pesan += f"🔹 **Konsumsi Tertinggi:** {hasil_analisis.get('tertinggi', 0):.2f} kWh (pada {hasil_analisis.get('hari_tertinggi', 'N/A')})\n"
        pesan += f"🔹 **Konsumsi Terendah:** {hasil_analisis.get('terendah', 0):.2f} kWh\n"
        pesan += f"🔹 **Tren Konsumsi (7 hari terakhir):** {hasil_analisis.get('tren', 'N/A')}\n"
        
        perbandingan_nasional = hasil_analisis.get('perbandingan_nasional', 0)
        if perbandingan_nasional > 0:
            pesan += f"🔹 **Perbandingan:** {perbandingan_nasional:.1f}% di atas rata-rata nasional (asumsi).\n"
        elif perbandingan_nasional < 0:
            pesan += f"🔹 **Perbandingan:** {abs(perbandingan_nasional):.1f}% di bawah rata-rata nasional (asumsi).\n"
        else:
            pesan += f"🔹 **Perbandingan:** Sesuai dengan rata-rata nasional (asumsi).\n"

        pesan += f"🔹 **Perkiraan Tagihan Bulanan:** Rp {hasil_analisis.get('perkiraan_tagihan', 0):,.0f}\n"
        if hasil_analisis.get('potensi_hemat', 0) > 0:
            pesan += f"🔹 **Potensi Penghematan:** Rp {hasil_analisis['potensi_hemat']:,}/bulan (jika mencapai rata-rata nasional).\n"
        
        await update.message.reply_text(pesan) 

        if hasil_analisis.get('rata_rata',0) > 0 :
             buffer_grafik = grafik.buat_grafik('bulanan') 
             await update.message.reply_photo(photo=buffer_grafik, caption="📈 Grafik Penggunaan Energi Bulanan Terakhir")

    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            logger.error(f"Database terkunci saat menampilkan hasil (Telegram): {e}")
            await update.message.reply_text("Database sedang sibuk, coba beberapa saat lagi untuk melihat hasil.")
        else:
            logger.error(f"Error database operasional saat menampilkan hasil (Telegram): {e}")
            await update.message.reply_text("Terjadi masalah dengan database saat menampilkan hasil. Silakan coba lagi nanti.")
    except Exception as e:
        logger.error(f"Error umum saat menampilkan hasil (Telegram): {e}")
        await update.message.reply_text("Maaf, terjadi kesalahan saat menampilkan hasil. Silakan coba lagi nanti.")

async def hapus_perangkat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Perintah /hapus_perangkat diterima.")
    if not context.args:
        await update.message.reply_text("Gunakan: /hapus_perangkat <nama_perangkat>")
        return
    nama = " ".join(context.args)
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    try:
        c.execute("SELECT nama FROM perangkat WHERE nama = ?", (nama,))
        if c.fetchone():
            c.execute("DELETE FROM perangkat WHERE nama = ?", (nama,))
            conn.commit()
            grafik.update_konsumsi_hari_ini() 
            await update.message.reply_text(f"Perangkat '{nama}' berhasil dihapus dan konsumsi harian telah diupdate.")
            logger.info(f"Berhasil menghapus perangkat: {nama} dan mengupdate konsumsi harian.")
        else:
            await update.message.reply_text(f"Perangkat '{nama}' tidak ditemukan.")
    except sqlite3.Error as e:
        logger.error(f"Database error di hapus_perangkat_handler (Telegram): {e}")
        await update.message.reply_text("Terjadi kesalahan database saat menghapus perangkat.")
    finally:
        if conn:
            conn.close()

async def hapus_semua_perangkat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Perintah /hapus_semua_perangkat diterima.")
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM perangkat")
        jumlah = c.fetchone()[0]
        if jumlah > 0:
            c.execute("DELETE FROM perangkat")
            conn.commit()
            grafik.update_konsumsi_hari_ini()
            await update.message.reply_text("Semua perangkat berhasil dihapus dan konsumsi harian telah diupdate menjadi nol.")
            logger.info("Berhasil menghapus semua perangkat dan mengupdate konsumsi harian.")
        else:
            await update.message.reply_text("Tidak ada perangkat untuk dihapus.")
    except sqlite3.Error as e:
        logger.error(f"Database error di hapus_semua_perangkat_handler (Telegram): {e}")
        await update.message.reply_text("Terjadi kesalahan database saat menghapus semua perangkat.")
    finally:
        if conn:
            conn.close()

async def tambah_perangkat_start_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    logger.info("Perintah /tambah_perangkat diterima.")
    await update.message.reply_text(
        "Mari tambahkan perangkat baru!\n"
        "Masukkan nama perangkat:"
    )
    return NAMA_PERANGKAT

async def tambah_nama_perangkat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nama = update.message.text
    context.user_data['nama_perangkat'] = nama
    await update.message.reply_text(
        f"Nama perangkat: {nama}\n"
        "Masukkan daya perangkat (dalam Watt, contoh: 100):"
    )
    return DAYA_PERANGKAT

async def tambah_daya_perangkat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        daya_text = update.message.text
        if not daya_text.isdigit():
            raise ValueError("Input daya harus berupa angka bulat positif.")
        daya = int(daya_text)
        if daya <=0:
             raise ValueError("Input daya harus berupa angka bulat positif.")
        context.user_data['daya_perangkat'] = daya
        await update.message.reply_text(
            f"Daya perangkat: {daya} W\n"
            "Masukkan perkiraan penggunaan perangkat harian (dalam kWh, contoh: 1.5):"
        )
        return PENGGUNAAN_PERANGKAT
    except ValueError as e:
        await update.message.reply_text(f"Input tidak valid: {e}. Masukkan nilai daya yang valid. Coba lagi:")
        return DAYA_PERANGKAT

async def tambah_penggunaan_perangkat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = None 
    try:
        penggunaan_text = update.message.text
        penggunaan = float(penggunaan_text.replace(',', '.')) 
        if penggunaan < 0:
            raise ValueError("Penggunaan tidak boleh negatif.")
            
        nama = context.user_data['nama_perangkat']
        daya = context.user_data['daya_perangkat']
        
        conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
        c = conn.cursor()
        c.execute("INSERT INTO perangkat (nama, daya, penggunaan) VALUES (?, ?, ?)", 
                  (nama, daya, penggunaan))
        conn.commit()
        
        grafik.update_konsumsi_hari_ini() 
        
        logger.info(f"Berhasil menambahkan perangkat baru via Telegram: {nama} dan mengupdate konsumsi harian.")
        await update.message.reply_text(
            f"✅ Berhasil menambahkan perangkat baru!\n\n"
            f"**Nama:** {nama}\n"
            f"**Daya:** {daya} W\n"
            f"**Penggunaan Harian:** {penggunaan} kWh\n\n"
            "Konsumsi harian telah diupdate.",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError as e:
        await update.message.reply_text(f"Input tidak valid: {e}. Masukkan nilai penggunaan yang valid (angka, contoh: 1.5). Coba lagi:")
        return PENGGUNAAN_PERANGKAT 
    except sqlite3.Error as e:
        logger.error(f"Database error saat tambah penggunaan perangkat (Telegram): {e}")
        await update.message.reply_text("Terjadi kesalahan database. Gagal menambahkan perangkat.")
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error saat menambah penggunaan perangkat (Telegram): {e}")
        await update.message.reply_text("Terjadi kesalahan internal. Silakan coba lagi nanti.")
        context.user_data.clear()
        return ConversationHandler.END
    finally:
        if conn:
            conn.close()


async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Membatalkan operasi input data.")
    if context.user_data:
        context.user_data.clear()
    await update.message.reply_text("Operasi dibatalkan.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def run_flask():
    logger.info("Menjalankan server Flask...")
    app.run(debug=False, host='0.0.0.0', port=5001, use_reloader=False) 

def run_telegram():
    logger.info("Menjalankan bot Telegram...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("saran", saran_telegram)) 
    application.add_handler(CommandHandler("perangkat", perangkat_telegram)) 
    application.add_handler(CommandHandler("grafik", grafik_telegram))
    application.add_handler(CommandHandler("laporan", laporan_telegram)) 
    application.add_handler(CommandHandler("hasil", hasil_telegram)) 
    application.add_handler(CommandHandler("hapus_perangkat", hapus_perangkat_handler))
    application.add_handler(CommandHandler("hapus_semua_perangkat", hapus_semua_perangkat_handler))
    
    tambah_perangkat_conv_handler = ConversationHandler( 
        entry_points=[CommandHandler("tambah_perangkat", tambah_perangkat_start_telegram)], 
        states={
            NAMA_PERANGKAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tambah_nama_perangkat)],
            DAYA_PERANGKAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tambah_daya_perangkat)],
            PENGGUNAAN_PERANGKAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tambah_penggunaan_perangkat)],
        },
        fallbacks=[CommandHandler("batal", batal)],
    )
    application.add_handler(tambah_perangkat_conv_handler)
    application.run_polling()

def main():
    init_db()
    enable_wal_mode() 
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True 
    flask_thread.start()
    run_telegram()

if __name__ == '__main__':
    main()
