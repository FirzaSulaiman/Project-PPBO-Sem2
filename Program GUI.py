import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import webbrowser
import os

DB_NAME = 'energi_desktop_free.db'
DB_TIMEOUT = 15
TARIF_KWH = 1500

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("green")

def log_message(message):
    print(f"LOG ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}): {message}")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.Error as e:
        log_message(f"Peringatan: Tidak dapat mengaktifkan mode WAL: {e}")
    return conn

def init_db():
    log_message("Menginisialisasi database...")
    conn = get_db_connection()
    try:
        with conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS perangkat (
                                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                                nama TEXT UNIQUE NOT NULL, 
                                daya INTEGER NOT NULL CHECK(daya >= 0), 
                                penggunaan REAL NOT NULL CHECK(penggunaan >= 0)
                             )''')
            conn.execute('''CREATE TABLE IF NOT EXISTS konsumsi (
                                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                                tanggal TEXT UNIQUE NOT NULL, 
                                penggunaan REAL NOT NULL CHECK(penggunaan >= 0)
                             )''')
        log_message("Database berhasil diinisialisasi/diverifikasi.")
    except sqlite3.Error as e:
        log_message(f"ERROR: Inisialisasi database gagal: {e}")
    finally:
        if conn: conn.close()

def hitung_konsumsi_harian_tk(tanggal=None):
    if tanggal is None:
        tanggal = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    total_konsumsi_perangkat = 0.0
    try:
        with conn:
            total_row = conn.execute("SELECT SUM(penggunaan) AS total_sum FROM perangkat").fetchone()
            if total_row and total_row['total_sum'] is not None:
                total_konsumsi_perangkat = total_row['total_sum']
            
            conn.execute("INSERT OR REPLACE INTO konsumsi (tanggal, penggunaan) VALUES (?, ?)", 
                         (tanggal, total_konsumsi_perangkat))
        log_message(f"Konsumsi harian dihitung/diupdate untuk {tanggal}: {total_konsumsi_perangkat} kWh")
        return total_konsumsi_perangkat
    except sqlite3.Error as e:
        log_message(f"ERROR: Gagal menghitung/menyimpan konsumsi harian: {e}")
        return 0.0 
    finally:
        if conn: conn.close()

def update_konsumsi_hari_ini_tk():
    return hitung_konsumsi_harian_tk()

def dapatkan_saran_penggunaan_tk():
    conn = get_db_connection()
    saran_list = []
    perangkat_ditemukan = {} 
    try:
        with conn:
            konsumsi_terakhir_rows = conn.execute("SELECT penggunaan FROM konsumsi ORDER BY tanggal DESC LIMIT 7").fetchall()
            konsumsi_terakhir = [row['penggunaan'] for row in konsumsi_terakhir_rows]
            rata_rata_konsumsi_mingguan = sum(konsumsi_terakhir) / len(konsumsi_terakhir) if konsumsi_terakhir else 0
            
            perangkat_data_rows = conn.execute("SELECT nama, daya, penggunaan FROM perangkat ORDER BY penggunaan DESC").fetchall()
        
        if len(konsumsi_terakhir) >= 3:
            if konsumsi_terakhir[0] > konsumsi_terakhir[1] * 1.1 and konsumsi_terakhir[1] > konsumsi_terakhir[2] * 1.1:
                saran_list.append("⚠️ Tren konsumsi energi Anda meningkat signifikan. Periksa penggunaan perangkat Anda.")
            elif konsumsi_terakhir[0] < konsumsi_terakhir[1] * 0.9 and konsumsi_terakhir[1] < konsumsi_terakhir[2] * 0.9:
                saran_list.append("👍 Tren konsumsi energi Anda menurun. Pertahankan!")

        if rata_rata_konsumsi_mingguan > 15:
            saran_list.append(f"Rata-rata konsumsi harian ({rata_rata_konsumsi_mingguan:.2f} kWh) cukup tinggi. Identifikasi perangkat boros.")
        elif rata_rata_konsumsi_mingguan > 0 and rata_rata_konsumsi_mingguan < 5 and len(perangkat_data_rows)>0 :
             saran_list.append(f"Rata-rata konsumsi harian Anda ({rata_rata_konsumsi_mingguan:.2f} kWh) tergolong efisien. Bagus!")


        if perangkat_data_rows:
            perangkat_terboros = perangkat_data_rows[0]
            if perangkat_terboros['penggunaan'] > (0.3 * rata_rata_konsumsi_mingguan if rata_rata_konsumsi_mingguan > 0 else 1) and len(perangkat_data_rows) > 1 : # Hanya jika signifikan & ada >1 perangkat
                 saran_list.append(f"⚡ Perangkat '{perangkat_terboros['nama']}' ({perangkat_terboros['penggunaan']:.2f} kWh) adalah konsumen terbesar Anda. Fokus optimasi di sini.")

            for p_row in perangkat_data_rows:
                nama_lower = p_row['nama'].lower()
                if ("ac" in nama_lower or "pendingin ruangan" in nama_lower) and "ac" not in perangkat_ditemukan:
                    saran_list.append("❄️ AC: Atur suhu ke 24-25°C, matikan jika tak dipakai, bersihkan filter rutin.")
                    perangkat_ditemukan["ac"] = True
                elif ("kulkas" in nama_lower or "lemari es" in nama_lower) and "kulkas" not in perangkat_ditemukan:
                    saran_list.append("🧊 Kulkas: Pastikan pintu rapat, jangan masukkan makanan panas, atur suhu optimal.")
                    perangkat_ditemukan["kulkas"] = True
                elif ("lampu" in nama_lower or "pencahayaan" in nama_lower or "penerangan" in nama_lower) and "lampu" not in perangkat_ditemukan:
                    saran_list.append("💡 Lampu: Gunakan LED hemat energi & matikan lampu jika ruangan tidak digunakan.")
                    perangkat_ditemukan["lampu"] = True
                elif ("tv" in nama_lower or "televisi" in nama_lower) and "tv" not in perangkat_ditemukan:
                    saran_list.append("📺 TV: Matikan TV sepenuhnya (jangan standby) saat tidak ditonton dalam waktu lama.")
                    perangkat_ditemukan["tv"] = True
                elif ("mesin cuci" in nama_lower) and "mesincuci" not in perangkat_ditemukan:
                    saran_list.append("🧺 Mesin Cuci: Gunakan dengan beban penuh & pilih mode hemat energi jika tersedia.")
                    perangkat_ditemukan["mesincuci"] = True
                elif ("pompa air" in nama_lower or "sanyo" in nama_lower) and "pompa" not in perangkat_ditemukan:
                    saran_list.append("💧 Pompa Air: Gunakan tandon air untuk mengurangi frekuensi menyala & periksa kebocoran.")
                    perangkat_ditemukan["pompa"] = True
                elif ("komputer" in nama_lower or "pc" in nama_lower or "laptop" in nama_lower) and "komputer" not in perangkat_ditemukan:
                    saran_list.append("💻 Komputer/Laptop: Aktifkan mode sleep/hibernate & matikan monitor jika tidak digunakan.")
                    perangkat_ditemukan["komputer"] = True
                elif ("rice cooker" in nama_lower or "magic jar" in nama_lower or "penanak nasi" in nama_lower) and "ricecooker" not in perangkat_ditemukan:
                    saran_list.append("🍚 Rice Cooker: Cabut dari listrik jika nasi sudah matang dan tidak perlu dihangatkan lama.")
                    perangkat_ditemukan["ricecooker"] = True
                elif ("dispenser" in nama_lower) and "dispenser" not in perangkat_ditemukan:
                    saran_list.append("🥤 Dispenser: Matikan mode pemanas/pendingin jika tidak dibutuhkan (misal malam hari).")
                    perangkat_ditemukan["dispenser"] = True
        
        saran_umum_penting = [
            "🔌 Cabut charger dan peralatan elektronik dari stopkontak jika sudah tidak digunakan untuk menghindari daya standby.",
            "☀️ Manfaatkan pencahayaan dan ventilasi alami semaksimal mungkin di siang hari.",
            "定期 Periksa dan rawat peralatan elektronik Anda agar tetap efisien."
        ]
        if not perangkat_data_rows or len(saran_list) < 2 :
            for su in saran_umum_penting:
                if su not in saran_list: saran_list.append(su)
        
        if not saran_list:
            saran_list.append("Belum ada saran spesifik. Pastikan Anda telah menambahkan perangkat Anda.")

        return list(dict.fromkeys(saran_list))[:5]
    except sqlite3.Error as e:
        log_message(f"ERROR: Database error di dapatkan_saran_penggunaan_tk: {e}")
        return ["Gagal mengambil saran karena masalah database."]
    finally:
        if conn: conn.close()

def analisis_hasil_penggunaan_tk():
    conn = get_db_connection()
    try:
        with conn:
            data_konsumsi_rows = conn.execute("SELECT tanggal, penggunaan FROM konsumsi ORDER BY tanggal DESC LIMIT 30").fetchall()
        
        data_konsumsi = [(row['tanggal'], row['penggunaan']) for row in data_konsumsi_rows]
        data_konsumsi.reverse()

        if not data_konsumsi or len(data_konsumsi) < 1:
            return {'status': 'Data tidak cukup', 'pesan': 'Belum ada data konsumsi untuk analisis.'}
        
        nilai_konsumsi = [row[1] for row in data_konsumsi]
        rata_rata = np.mean(nilai_konsumsi) if nilai_konsumsi else 0
        tertinggi = np.max(nilai_konsumsi) if nilai_konsumsi else 0
        terendah = np.min(nilai_konsumsi) if nilai_konsumsi else 0
        tren_status = "N/A"
        if len(nilai_konsumsi) >= 7:
            tren_terakhir = nilai_konsumsi[-7:]
            x_val = np.arange(len(tren_terakhir))
            try:
                if not all(val == tren_terakhir[0] for val in tren_terakhir):
                    z_val = np.polyfit(x_val, tren_terakhir, 1)
                    slope = z_val[0]
                    tren_status = "meningkat" if slope > 0.05 else "menurun" if slope < -0.05 else "stabil" # Sesuaikan threshold
                else:
                    tren_status = "stabil (data konstan)"
            except Exception as e:
                log_message(f"Peringatan: Error polyfit saat analisis tren: {e}")
                tren_status = "tidak dapat dihitung"
        elif len(nilai_konsumsi) >= 2:
            tren_status = "meningkat" if nilai_konsumsi[-1] > nilai_konsumsi[0] else "menurun" if nilai_konsumsi[-1] < nilai_konsumsi[0] else "stabil"
        
        return {
            'status': 'OK',
            'rata_rata': round(rata_rata, 2), 
            'tertinggi': round(tertinggi, 2),
            'terendah': round(terendah, 2),
            'tren': tren_status,
        }
    except sqlite3.Error as e:
        log_message(f"ERROR: Database error di analisis_hasil_penggunaan_tk: {e}")
        return {'status': 'Error Database', 'pesan': f'Kesalahan database: {e}'}
    finally:
        if conn: conn.close()

class EnergyMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Pemantauan Energi Rumah (Versi Desktop)")
        self.geometry("1050x720")

        init_db()
        update_konsumsi_hari_ini_tk()

        self.grid_columnconfigure(0, weight=2) 
        self.grid_columnconfigure(1, weight=3) 
        self.grid_rowconfigure(0, weight=1)    

        self.left_frame = ctk.CTkFrame(self, width=350, corner_radius=10)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.grid_propagate(False)

        self.right_frame = ctk.CTkFrame(self, corner_radius=10)
        self.right_frame.grid(row=0, column=1, padx=(0,10), pady=10, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=2) 
        self.right_frame.grid_rowconfigure(1, weight=3) 
        self.right_frame.grid_columnconfigure(0, weight=1)

        self._create_input_widgets()
        self._create_device_list_widgets()
        self._create_chart_widgets()
        self._create_action_buttons()
        self._create_info_display_widgets()

        self.load_devices_to_treeview()
        self.display_chart('mingguan') 

    def _create_input_widgets(self):
        input_frame = ctk.CTkFrame(self.left_frame)
        input_frame.pack(pady=15, padx=15, fill="x")
        ctk.CTkLabel(input_frame, text="Tambah Perangkat Baru", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0,12))
        ctk.CTkLabel(input_frame, text="Nama Perangkat:").pack(fill="x", padx=5, anchor="w")
        self.nama_entry = ctk.CTkEntry(input_frame, placeholder_text="Contoh: Kulkas")
        self.nama_entry.pack(fill="x", padx=5, pady=(0,8))

        ctk.CTkLabel(input_frame, text="Daya (Watt):").pack(fill="x", padx=5, anchor="w")
        self.daya_entry = ctk.CTkEntry(input_frame, placeholder_text="Contoh: 100")
        self.daya_entry.pack(fill="x", padx=5, pady=(0,8))

        ctk.CTkLabel(input_frame, text="Penggunaan Harian (kWh):").pack(fill="x", padx=5, anchor="w")
        self.penggunaan_entry = ctk.CTkEntry(input_frame, placeholder_text="Contoh: 1.5")
        self.penggunaan_entry.pack(fill="x", padx=5, pady=(0,12))

        ctk.CTkButton(input_frame, text="Simpan Perangkat", command=self.add_new_device, height=35).pack(fill="x", padx=5)


    def _create_device_list_widgets(self):
        list_frame = ctk.CTkFrame(self.right_frame)
        list_frame.grid(row=0, column=0, padx=10, pady=(10,5), sticky="nsew")
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(list_frame, text="Daftar Perangkat", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, pady=10, sticky="n")

        style = ttk.Style(self)
        style.theme_use("default") 
        style.configure("Treeview.Heading", font=('Segoe UI', 11, 'bold'), background="#E0E0E0", relief="flat")
        style.map("Treeview.Heading", relief=[('active','groove'),('pressed','sunken')])
        style.configure("Treeview", rowheight=28, font=('Segoe UI', 10), background="white", fieldbackground="white")
        style.map("Treeview", background=[('selected', '#347083')], foreground=[('selected', 'white')])

        self.tree = ttk.Treeview(list_frame, columns=("ID", "Nama", "Daya", "Penggunaan"), show="headings", height=7)
        self.tree.heading("ID", text="ID")
        self.tree.heading("Nama", text="Nama Perangkat")
        self.tree.heading("Daya", text="Daya (W)")
        self.tree.heading("Penggunaan", text="Penggunaan (kWh/hari)")

        self.tree.column("ID", width=50, stretch=tk.NO, anchor="center")
        self.tree.column("Nama", width=200, anchor="w")
        self.tree.column("Daya", width=100, anchor="center")
        self.tree.column("Penggunaan", width=150, anchor="center")
        
        self.tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        scrollbar = ctk.CTkScrollbar(list_frame, command=self.tree.yview, orientation="vertical")
        scrollbar.grid(row=1, column=1, sticky="ns", pady=5, padx=(0,5))
        self.tree.configure(yscrollcommand=scrollbar.set)

    def _create_chart_widgets(self):
        self.chart_frame = ctk.CTkFrame(self.right_frame, corner_radius=0, fg_color="transparent")
        self.chart_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.chart_frame.grid_propagate(False) # Agar chart bisa mengisi frame

    def _create_action_buttons(self):
        action_frame = ctk.CTkFrame(self.left_frame)
        action_frame.pack(pady=10, padx=15, fill="x")
        ctk.CTkLabel(action_frame, text="Tindakan & Kontrol", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0,10))

        delete_buttons_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        delete_buttons_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkButton(delete_buttons_frame, text="Hapus Terpilih", command=self.delete_selected_device, fg_color="#E53935", hover_color="#C62828", height=35).pack(side="left", expand=True, padx=(0,3))
        ctk.CTkButton(delete_buttons_frame, text="Hapus Semua", command=self.delete_all_devices_ui, fg_color="#D32F2F", hover_color="#B71C1C", height=35).pack(side="left", expand=True, padx=(3,0))

        chart_buttons_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        chart_buttons_frame.pack(fill="x", pady=(5, 5))
        ctk.CTkButton(chart_buttons_frame, text="Grafik Mingguan", command=lambda: self.display_chart('mingguan'), height=35).pack(side="left", expand=True, padx=(0,3))
        ctk.CTkButton(chart_buttons_frame, text="Grafik Bulanan", command=lambda: self.display_chart('bulanan'), height=35).pack(side="left", expand=True, padx=(3,0))

        ctk.CTkButton(action_frame, text="Tampilkan Analisis Konsumsi", command=self.display_analysis, height=35).pack(fill="x", pady=5)
        ctk.CTkButton(action_frame, text="💡 Tampilkan Tips Hemat Energi", command=self.display_local_smart_tips, fg_color="#FB8C00", hover_color="#EF6C00", height=35).pack(fill="x", pady=5)
        ctk.CTkButton(action_frame, text="Buat Laporan (HTML)", command=self.generate_and_show_report, height=35).pack(fill="x", pady=5)

    def _create_info_display_widgets(self):
        info_frame_container = ctk.CTkFrame(self.left_frame)
        info_frame_container.pack(pady=10, padx=15, fill="both", expand=True)
        
        ctk.CTkLabel(info_frame_container, text="Informasi & Tips", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0,5))

        self.info_text_widget = ctk.CTkTextbox(info_frame_container, wrap="word", height=220, activate_scrollbars=True, font=("Segoe UI", 11), border_width=1, border_color="#B0B0B0")
        self.info_text_widget.pack(fill="both", expand=True, padx=2, pady=2)
        self.info_text_widget.insert("end", "Selamat datang! Hasil analisis dan tips akan muncul di sini.\n")
        self.info_text_widget.configure(state="disabled")

    def load_devices_to_treeview(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        conn = get_db_connection()
        try:
            with conn:
                devices = conn.execute("SELECT id, nama, daya, penggunaan FROM perangkat ORDER BY nama ASC").fetchall()
            for device in devices:
                self.tree.insert("", "end", values=(device['id'], device['nama'], device['daya'], f"{device['penggunaan']:.2f}"))
        except sqlite3.Error as e:
            log_message(f"ERROR: Gagal memuat perangkat: {e}")
            messagebox.showerror("Database Error", f"Gagal memuat perangkat: {e}")
        finally:
            if conn: conn.close()

    def add_new_device(self):
        nama = self.nama_entry.get().strip()
        daya_str = self.daya_entry.get().strip()
        penggunaan_str = self.penggunaan_entry.get().strip()

        if not nama or not daya_str or not penggunaan_str:
            messagebox.showerror("Input Tidak Lengkap", "Semua field harus diisi.")
            return
        try:
            daya = int(daya_str)
            penggunaan = float(penggunaan_str.replace(',', '.'))
            if daya < 0 or penggunaan < 0:
                messagebox.showerror("Input Tidak Valid", "Daya dan penggunaan tidak boleh negatif.")
                return
        except ValueError:
            messagebox.showerror("Input Tidak Valid", "Daya harus angka bulat dan penggunaan harus angka.")
            return

        conn = get_db_connection()
        try:
            with conn:
                conn.execute("INSERT INTO perangkat (nama, daya, penggunaan) VALUES (?, ?, ?)",
                             (nama, daya, penggunaan))
            update_konsumsi_hari_ini_tk()
            self.load_devices_to_treeview()
            messagebox.showinfo("Sukses", f"Perangkat '{nama}' berhasil ditambahkan.")
            self.nama_entry.delete(0, "end")
            self.daya_entry.delete(0, "end")
            self.penggunaan_entry.delete(0, "end")
            self.display_chart(getattr(self, 'current_chart_type', 'mingguan'))
        except sqlite3.IntegrityError:
            messagebox.showerror("Gagal", f"Nama perangkat '{nama}' sudah ada.")
        except sqlite3.Error as e:
            log_message(f"ERROR: Gagal menambah perangkat: {e}")
            messagebox.showerror("Database Error", f"Gagal menambah perangkat: {e}")
        finally:
            if conn: conn.close()


    def delete_selected_device(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Peringatan", "Pilih perangkat yang ingin dihapus.")
            return
        
        item_values = self.tree.item(selected_item, "values")
        device_id = item_values[0] 
        device_nama = item_values[1]

        if messagebox.askyesno("Konfirmasi Hapus", f"Anda yakin ingin menghapus perangkat '{device_nama}'?"):
            conn = get_db_connection()
            try:
                with conn:
                    conn.execute("DELETE FROM perangkat WHERE id = ?", (device_id,))
                update_konsumsi_hari_ini_tk()
                self.load_devices_to_treeview()
                messagebox.showinfo("Sukses", f"Perangkat '{device_nama}' berhasil dihapus.")
                self.display_chart(getattr(self, 'current_chart_type', 'mingguan'))
            except sqlite3.Error as e:
                log_message(f"ERROR: Gagal menghapus perangkat: {e}")
                messagebox.showerror("Database Error", f"Gagal menghapus perangkat: {e}")
            finally:
                if conn: conn.close()

    def delete_all_devices_ui(self):
        if messagebox.askyesno("Konfirmasi Hapus Semua", "ANDA YAKIN ingin menghapus SEMUA perangkat? Tindakan ini tidak dapat diurungkan."):
            conn = get_db_connection()
            try:
                with conn:
                    conn.execute("DELETE FROM perangkat")
                update_konsumsi_hari_ini_tk()
                self.load_devices_to_treeview()
                messagebox.showinfo("Sukses", "Semua perangkat berhasil dihapus.")
                self.display_chart(getattr(self, 'current_chart_type', 'mingguan'))
            except sqlite3.Error as e:
                log_message(f"ERROR: Gagal menghapus semua perangkat: {e}")
                messagebox.showerror("Database Error", f"Gagal menghapus semua perangkat: {e}")
            finally:
                if conn: conn.close()
    
    def display_chart(self, tipe):
        self.current_chart_type = tipe 
        log_message(f"Membuat grafik {tipe}...")
        update_konsumsi_hari_ini_tk() 

        for widget in self.chart_frame.winfo_children():    
            widget.destroy()

        fig, ax = plt.subplots(figsize=(5.5, 3.8), dpi=100)
        conn = get_db_connection()
        try:
            with conn:
                hari = 7 if tipe == 'mingguan' else 30
                tanggal_query = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(hari-1, -1, -1)]
                label_sumbu_x = [datetime.strptime(t, '%Y-%m-%d').strftime('%d-%m') for t in tanggal_query]
                
                jumlah_perangkat_sekarang_row = conn.execute("SELECT COUNT(*) AS count FROM perangkat").fetchone()
                jumlah_perangkat_sekarang = jumlah_perangkat_sekarang_row['count'] if jumlah_perangkat_sekarang_row else 0
                tanggal_hari_ini_str = datetime.now().strftime('%Y-%m-%d')
                
                nilai = []
                for tgl_db in tanggal_query:
                    konsumsi_row = conn.execute("SELECT penggunaan FROM konsumsi WHERE tanggal = ?", (tgl_db,)).fetchone()
                    penggunaan_hari = konsumsi_row['penggunaan'] if konsumsi_row else 0.0
                    if tgl_db == tanggal_hari_ini_str and jumlah_perangkat_sekarang == 0:
                        penggunaan_hari = 0.0
                    nilai.append(round(penggunaan_hari,2))

            if jumlah_perangkat_sekarang == 0 and not any(n > 0 for n in nilai if n is not None):
                 ax.text(0.5, 0.5, 'Tidak ada data konsumsi', ha='center', va='center', transform=ax.transAxes, fontsize=10, color='gray')
            else:
                ax.plot(label_sumbu_x, nilai, marker='o', linestyle='-', linewidth=1.5, markersize=4, color='#059669') # Warna hijau tema
                ax.fill_between(label_sumbu_x, nilai, alpha=0.2, color='#059669')
                ax.set_ylabel('Konsumsi (kWh)', fontsize=9)
                ax.grid(True, linestyle=':', alpha=0.5)
                ax.tick_params(axis='x', rotation=45, labelsize=8, pad=2)
                ax.tick_params(axis='y', labelsize=8)
                for i, v_val in enumerate(nilai):
                    if v_val > 0.05:
                        ax.annotate(f'{v_val:.1f}', (i, v_val), textcoords="offset points", xytext=(0,6), ha='center', fontsize=7)
            
            ax.set_title(f'Tren Konsumsi Energi ({tipe.capitalize()})', fontsize=11, fontweight='bold')
            fig.patch.set_facecolor('#F0F0F0')
            ax.set_facecolor('#FFFFFF')
            fig.tight_layout(pad=0.8)

            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
            canvas.draw()
        except sqlite3.Error as e:
            log_message(f"ERROR: Database error saat membuat grafik: {e}")
            messagebox.showerror("Database Error", f"Gagal membuat grafik: {e}")
        except Exception as e:
            log_message(f"ERROR: Error umum saat membuat grafik: {e}")
            # Tampilkan pesan error di frame chart jika gagal
            error_label = ctk.CTkLabel(self.chart_frame, text=f"Gagal memuat grafik:\n{e}", text_color="red", wraplength=300)
            error_label.pack(expand=True, fill="both", padx=10, pady=10)
        finally:
            if conn: conn.close()

    def _update_info_text(self, text_to_display, title="Informasi"):
        self.info_text_widget.configure(state="normal")
        self.info_text_widget.delete("1.0", "end")
        self.info_text_widget.insert("end", f"--- {title.upper()} ---\n\n{text_to_display}")
        self.info_text_widget.configure(state="disabled")

    def display_analysis(self):
        log_message("Menampilkan analisis konsumsi...")
        update_konsumsi_hari_ini_tk()
        hasil = analisis_hasil_penggunaan_tk()
        
        if hasil.get('status') == 'OK':
            analisis_text = (
                f"Rata-rata Konsumsi Harian: {hasil.get('rata_rata', 'N/A')} kWh\n"
                f"Konsumsi Tertinggi: {hasil.get('tertinggi', 'N/A')} kWh\n"
                f"Konsumsi Terendah: {hasil.get('terendah', 'N/A')} kWh\n"
                f"Tren Konsumsi: {hasil.get('tren', 'N/A')}\n"
            )
            self._update_info_text(analisis_text, "Analisis Konsumsi")
        else:
            self._update_info_text(hasil.get('pesan', "Gagal melakukan analisis."), "Error Analisis")

    def display_local_smart_tips(self):
        log_message("Menampilkan tips hemat energi lokal...")
        tips = dapatkan_saran_penggunaan_tk()
        if tips:
            tips_text = "\n".join([f"• {tip}" for tip in tips])
            self._update_info_text(tips_text, "💡 Tips Hemat Energi 💡")
        else:
            self._update_info_text("Tidak ada tips yang tersedia saat ini.", "Tips Hemat Energi")

    def generate_and_show_report(self):
        log_message("Membuat laporan HTML...")
        update_konsumsi_hari_ini_tk()
        conn = get_db_connection()
        try:
            with conn:
                perangkat_rows = conn.execute("SELECT id, nama, daya, penggunaan FROM perangkat ORDER BY penggunaan DESC").fetchall()
                perangkat_db = [dict(row) for row in perangkat_rows]
                
                konsumsi_hr_ini_row = conn.execute("SELECT penggunaan FROM konsumsi WHERE tanggal = ?", 
                                                 (datetime.now().strftime('%Y-%m-%d'),)).fetchone()
            total_harian_aktual_db = konsumsi_hr_ini_row['penggunaan'] if konsumsi_hr_ini_row else 0.0

            rekomendasi_list = dapatkan_saran_penggunaan_tk()
            
            html_content = f"""
            <html><head><title>Laporan Energi</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 25px; font-size: 11pt; line-height: 1.5; color: #333; }}
                h1 {{ color: #00796b; text-align: center; font-size: 20pt; border-bottom: 2px solid #00796b; padding-bottom: 10px; margin-bottom: 25px;}}
                h2 {{ color: #004d40; font-size: 15pt; margin-top: 25px; margin-bottom: 10px;}}
                .summary {{ background-color: #e0f2f1; padding: 18px; margin: 20px 0; border-left: 5px solid #00796b; border-radius: 6px;}}
                .summary p {{ margin: 5px 0; }}
                table {{ width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 15px; font-size: 10pt; border: 1px solid #b2dfdb; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);}}
                th, td {{ border-bottom: 1px solid #b2dfdb; padding: 10px 12px; text-align: left; }}
                th {{ background-color: #a7ffeb; color: #004d40; font-weight: 600; border-top-left-radius: 5px; border-top-right-radius: 5px;}}
                tr:last-child td:first-child {{ border-bottom-left-radius: 5px; }}
                tr:last-child td:last-child {{ border-bottom-right-radius: 5px; }}
                tr:nth-child(even) td {{ background-color: #f5f5f5; }}
                ul {{ list-style-type: none; padding-left: 0; }} 
                li {{ background-color: #f5f5f5; margin-bottom: 6px; padding: 8px 12px; border-radius: 4px; border-left: 3px solid #00796b;}}
                .footer {{ text-align:center; font-size:9pt; margin-top:30px; color: #757575; border-top: 1px solid #e0e0e0; padding-top: 15px;}}
            </style></head><body>
            <h1>📊 Laporan Pemantauan Energi</h1>
            <div class="summary">
                <h3>Ringkasan Konsumsi</h3>
                <p>Total Konsumsi Harian: <strong>{total_harian_aktual_db:.2f} kWh</strong></p>
                <p>Estimasi Biaya Harian: <strong>Rp {total_harian_aktual_db * TARIF_KWH:,.0f}</strong></p>
                <p>Estimasi Biaya Bulanan: <strong>Rp {total_harian_aktual_db * TARIF_KWH * 30:,.0f}</strong></p>
                <p><em>*Tarif asumsi: Rp {TARIF_KWH:,.0f}/kWh</em></p>
            </div>
            """
            html_content += "<h2>Detail Perangkat</h2>"
            if perangkat_db:
                html_content += "<table><tr><th>Nama</th><th>Daya (W)</th><th>Penggunaan (kWh)</th><th>% Total</th><th>Biaya Harian (Rp)</th></tr>"
                for p in perangkat_db:
                    persen = (p['penggunaan'] / total_harian_aktual_db * 100) if total_harian_aktual_db > 0 else 0
                    biaya_p = p['penggunaan'] * TARIF_KWH
                    html_content += f"<tr><td>{p['nama']}</td><td>{p['daya']}</td><td>{p['penggunaan']:.2f}</td><td>{persen:.1f}%</td><td>{biaya_p:,.0f}</td></tr>"
                html_content += "</table>"
            else:
                html_content += "<p>Tidak ada perangkat terdaftar.</p>"

            html_content += "<h2>Rekomendasi Penghematan</h2><ul>"
            if rekomendasi_list:
                for saran in rekomendasi_list:
                    html_content += f"<li>{saran}</li>"
            else:
                html_content += "<li>Belum ada rekomendasi spesifik saat ini.</li>"
            html_content += "</ul>"
            html_content += f"<div class='footer'>Laporan dibuat pada: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}</div>"
            html_content += "</body></html>"

            temp_dir = filedialog.gettempdir() if hasattr(filedialog, 'gettempdir') else os.path.expanduser("~") # Fallback
            temp_report_path = os.path.join(temp_dir, f"laporan_energi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            
            try:
                with open(temp_report_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                
                webbrowser.open(f"file://{os.path.realpath(temp_report_path)}")
                messagebox.showinfo("Laporan Dibuat", f"Laporan HTML telah dibuat dan dibuka di browser Anda.\nFile disimpan di: {temp_report_path}")
                self._update_info_text(f"Laporan HTML berhasil dibuat.\nPath: {temp_report_path}", "Laporan")
            except IOError as e:
                log_message(f"ERROR: Gagal menulis file laporan sementara: {e}")
                messagebox.showerror("Error File", f"Gagal menyimpan file laporan: {e}")


        except sqlite3.Error as e:
            log_message(f"ERROR: Database error saat buat laporan: {e}")
            messagebox.showerror("Database Error", f"Gagal membuat laporan: {e}")
        except Exception as e:
            log_message(f"ERROR: Error umum saat buat laporan: {e}")
            messagebox.showerror("Error Laporan", f"Terjadi kesalahan: {e}")
        finally:
            if conn: conn.close()

if __name__ == "__main__":
    app = EnergyMonitorApp()
    app.mainloop()