import sqlite3
import io
from datetime import datetime
from weasyprint import HTML
import numpy as np

class LaporanGenerator:
    def __init__(self, db_path='energi.db'):
        """
        Inisialisasi LaporanGenerator
        
        Args:
            db_path (str): Path ke database SQLite
        """
        self.db_path = db_path
    
    def dapatkan_saran_penggunaan(self):
        """
        Dapatkan saran penggunaan energi berdasarkan data historis
        
        Returns:
            list: Daftar saran penghematan energi
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Ambil data konsumsi terakhir
        c.execute("SELECT penggunaan FROM konsumsi ORDER BY tanggal DESC LIMIT 7")
        konsumsi_terakhir = [row[0] for row in c.fetchall()]
        
        # Ambil rata-rata konsumsi
        rata_rata = sum(konsumsi_terakhir) / len(konsumsi_terakhir) if konsumsi_terakhir else 0
        
        # Ambil penggunaan perangkat (urutkan berdasarkan daya * penggunaan)
        c.execute("SELECT nama, daya, penggunaan FROM perangkat ORDER BY daya * penggunaan DESC")
        perangkat = c.fetchall()
        
        conn.close()
        
        saran = []
        
        # Saran berdasarkan tren konsumsi
        if len(konsumsi_terakhir) >= 3 and konsumsi_terakhir[0] > konsumsi_terakhir[1] > konsumsi_terakhir[2]:
            saran.append("Tren konsumsi energi Anda meningkat. Identifikasi perangkat yang mungkin menyebabkan peningkatan ini.")
        
        # Saran berdasarkan konsumsi rata-rata
        if rata_rata > 15:
            saran.append(f"Rata-rata konsumsi harian Anda ({rata_rata:.2f} kWh) cukup tinggi. Pertimbangkan untuk mengurangi penggunaan perangkat dengan daya tinggi.")
        
        # Saran berdasarkan perangkat dengan konsumsi tertinggi
        if perangkat:
            perangkat_tertinggi = perangkat[0]
            saran.append(f"Perangkat '{perangkat_tertinggi[0]}' menggunakan paling banyak energi. Pertimbangkan untuk mengurangi waktu penggunaan atau menggantinya dengan model yang lebih efisien.")
            
            # Jika ada perangkat lain dengan konsumsi tinggi, tambahkan saran tambahan
            if len(perangkat) > 1:
                perangkat_kedua = perangkat[1]
                saran.append(f"Perangkat '{perangkat_kedua[0]}' juga memiliki konsumsi energi yang signifikan. Pertimbangkan untuk mengoptimalkan penggunaannya.")
        
        # Tambahkan saran umum jika belum ada data spesifik atau tidak ada perangkat
        if not saran:
            saran.extend([
                "Matikan perangkat elektronik yang tidak digunakan untuk menghemat energi.",
                "Gunakan lampu LED yang lebih hemat energi dibandingkan lampu pijar tradisional.",
                "Atur suhu AC pada 24-26 derajat Celcius untuk penggunaan yang optimal.",
                "Gunakan fitur timer pada perangkat elektronik untuk mematikannya secara otomatis.",
                "Pertimbangkan untuk berinvestasi pada perangkat hemat energi dengan sertifikasi ENERGY STAR."
            ])
        
        return saran
    
    def ambil_data_perangkat(self):
        """
        Ambil data perangkat dari database
        
        Returns:
            list: Daftar tuple (id, nama, daya, penggunaan)
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT * FROM perangkat")
        perangkat = c.fetchall()
        conn.close()
        return perangkat
    
    def buat_html_laporan(self):
        """
        Buat konten HTML untuk laporan
        
        Returns:
            str: Konten HTML laporan
        """
        # Ambil data perangkat
        perangkat = self.ambil_data_perangkat()
        
        # Ambil saran penghematan energi
        saran = self.dapatkan_saran_penggunaan()
        
        # Buat HTML content
        html_content = f"""
        <html>
        <head>
            <title>Laporan Sistem Pemantauan Energi Cerdas</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 20px; 
                    line-height: 1.6;
                }}
                h1 {{ 
                    color: #333; 
                    text-align: center;
                    margin-bottom: 30px;
                }}
                h2 {{ 
                    color: #555; 
                    border-bottom: 2px solid #ddd;
                    padding-bottom: 5px;
                    margin-top: 30px;
                }}
                table {{ 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin: 20px 0; 
                }}
                th, td {{ 
                    border: 1px solid #333; 
                    padding: 12px; 
                    text-align: left; 
                }}
                th {{ 
                    background-color: #f2f2f2; 
                    font-weight: bold;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                ul {{ 
                    margin: 20px 0; 
                    padding-left: 20px; 
                }}
                li {{
                    margin-bottom: 8px;
                }}
                .footer {{
                    margin-top: 40px;
                    text-align: center;
                    color: #666;
                    font-size: 12px;
                }}
                .no-data {{
                    text-align: center;
                    color: #888;
                    font-style: italic;
                    padding: 20px;
                }}
            </style>
        </head>
        <body>
            <h1>Laporan Sistem Pemantauan Energi Cerdas</h1>
            
            <h2>Konsumsi Perangkat</h2>
            <table>
                <tr>
                    <th>Nama Perangkat</th>
                    <th>Daya (W)</th>
                    <th>Penggunaan (kWh)</th>
                </tr>"""
        
        # Tambahkan data perangkat ke tabel
        if perangkat:
            for p in perangkat:
                html_content += f"""
                <tr>
                    <td>{p[1]}</td>
                    <td>{p[2]}</td>
                    <td>{p[3]}</td>
                </tr>"""
        else:
            html_content += """
                <tr>
                    <td colspan="3" class="no-data">Tidak ada data perangkat</td>
                </tr>"""
        
        html_content += """
            </table>
            
            <h2>Saran Penghematan Energi</h2>
            <ul>"""
        
        # Tambahkan saran penghematan energi
        for s in saran:
            html_content += f"<li>{s}</li>"
        
        html_content += f"""
            </ul>
            
            <div class="footer">
                <p>Dibuat pada {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def generate_pdf_file(self, output_path='laporan_energi.pdf'):
        """
        Generate PDF laporan dan simpan ke file
        
        Args:
            output_path (str): Path output file PDF
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            # Buat HTML content
            html_content = self.buat_html_laporan()
            
            # Konversi HTML ke PDF dan simpan ke file
            HTML(string=html_content).write_pdf(output_path)
            
            return True
        except Exception as e:
            print(f"Error saat membuat PDF laporan: {e}")
            return False
    
    def generate_pdf_buffer(self):
        """
        Generate PDF laporan sebagai buffer (untuk Telegram bot)
        
        Returns:
            io.BytesIO: Buffer PDF atau None jika gagal
        """
        try:
            # Buat HTML content
            html_content = self.buat_html_laporan()
            
            # Konversi HTML ke PDF buffer
            pdf_buffer = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
            
            return pdf_buffer
        except Exception as e:
            print(f"Error saat membuat PDF buffer: {e}")
            return None

# Fungsi untuk penggunaan mandiri
def buat_laporan_energi(db_path='energi.db', output_path='laporan_energi.pdf'):
    """
    Fungsi standalone untuk membuat laporan energi
    
    Args:
        db_path (str): Path ke database SQLite
        output_path (str): Path output file PDF
        
    Returns:
        bool: True jika berhasil, False jika gagal
    """
    generator = LaporanGenerator(db_path)
    return generator.generate_pdf_file(output_path)

# Contoh penggunaan mandiri
if __name__ == "__main__":
    print("Membuat laporan energi...")
    
    # Cara 1: Menggunakan class
    generator = LaporanGenerator()
    if generator.generate_pdf_file():
        print("✓ Laporan berhasil dibuat: laporan_energi.pdf")
    else:
        print("✗ Gagal membuat laporan")
    
    # Cara 2: Menggunakan fungsi standalone
    # if buat_laporan_energi():
    #     print("✓ Laporan berhasil dibuat: laporan_energi.pdf")
    # else:
    #     print("✗ Gagal membuat laporan")