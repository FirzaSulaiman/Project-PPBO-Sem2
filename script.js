// static/js/script.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Mobile Menu Toggle ---
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');

    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', () => {
            const isHidden = mobileMenu.classList.contains('hidden');
            if (isHidden) {
                mobileMenu.classList.remove('hidden');
                // Tambahkan animasi jika diinginkan, misal:
                // mobileMenu.style.maxHeight = mobileMenu.scrollHeight + "px";
                // mobileMenu.style.opacity = "1";
            } else {
                mobileMenu.classList.add('hidden');
                // mobileMenu.style.maxHeight = "0";
                // mobileMenu.style.opacity = "0";
            }
        });
    }

    // --- Chart.js Logic (jika ada di dashboard.html) ---
    const grafikKonsumsiChartCanvas = document.getElementById('grafikKonsumsiChart');
    if (grafikKonsumsiChartCanvas) {
        let grafikChartInstance; // Variabel untuk menyimpan instance Chart
        const ctx = grafikKonsumsiChartCanvas.getContext('2d');
        const btnMingguan = document.getElementById('btn-mingguan');
        const btnBulanan = document.getElementById('btn-bulanan');
        const statsAvgEl = document.getElementById('stats-avg');
        const statsPeakEl = document.getElementById('stats-peak');
        const statsTypeEl = document.getElementById('stats-type');
        const statsTypePeakEl = document.getElementById('stats-type-peak'); // Untuk label puncak

        async function fetchDataGrafik(tipe) {
            if (statsAvgEl) statsAvgEl.textContent = "Memuat...";
            if (statsPeakEl) statsPeakEl.textContent = "Memuat...";
            if (statsTypeEl) statsTypeEl.textContent = tipe.charAt(0).toUpperCase() + tipe.slice(1);
            if (statsTypePeakEl) statsTypePeakEl.textContent = tipe.charAt(0).toUpperCase() + tipe.slice(1);


            try {
                // Pastikan endpoint ini ada di Flask (sc 2.py)
                const response = await fetch(`/ambil_data_grafik_web?tipe=${tipe}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                return data;
            } catch (error) {
                console.error("Gagal mengambil data grafik:", error);
                if (statsAvgEl) statsAvgEl.textContent = "Error";
                if (statsPeakEl) statsPeakEl.textContent = "Error";
                // Kembalikan data kosong agar renderGrafik bisa menanganinya
                return { label: [], nilai: [], error: "Gagal memuat data grafik." };
            }
        }

        function renderGrafik(data) {
            if (grafikChartInstance) {
                grafikChartInstance.destroy(); 
            }

            if (data.error || !data.label || !data.nilai) {
                console.error("Error rendering chart atau data tidak valid:", data.error || "Data tidak lengkap");
                // Tampilkan pesan error di area chart jika elemen canvas ada
                if (grafikKonsumsiChartCanvas) {
                    const chartParent = grafikKonsumsiChartCanvas.parentElement;
                    if (chartParent) {
                        chartParent.innerHTML = `<p class="text-red-500 text-center p-4">${data.error || "Data grafik tidak tersedia atau tidak valid."}</p>`;
                    }
                }
                if (statsAvgEl) statsAvgEl.textContent = "N/A";
                if (statsPeakEl) statsPeakEl.textContent = "N/A";
                return;
            }
            
            // Jika sebelumnya ada pesan error, kembalikan canvas
            const chartParent = grafikKonsumsiChartCanvas.parentElement;
            if (chartParent.querySelector('p.text-red-500, p.text-gray-500')) {
                 chartParent.innerHTML = ''; // Hapus pesan error/placeholder
                 chartParent.appendChild(grafikKonsumsiChartCanvas); // Tambahkan kembali canvas
            }


            grafikChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.label,
                    datasets: [{
                        label: 'Konsumsi Energi (kWh)',
                        data: data.nilai,
                        borderColor: 'rgb(22, 163, 74)', // Warna hijau (green-600)
                        backgroundColor: 'rgba(22, 163, 74, 0.1)', // Area di bawah garis
                        fill: true,
                        tension: 0.3, // Membuat garis sedikit melengkung
                        pointBackgroundColor: 'rgb(22, 163, 74)',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: 'rgb(22, 163, 74)',
                        borderWidth: 2.5,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Konsumsi (kWh)', font: { size: 12 } },
                            grid: { color: '#e5e7eb' } // Warna grid lebih lembut
                        },
                        x: {
                            title: { display: true, text: 'Tanggal', font: { size: 12 } },
                            grid: { display: false } // Sembunyikan grid x untuk tampilan lebih bersih
                        }
                    },
                    plugins: {
                        legend: {
                            display: false // Sembunyikan legend default jika hanya satu dataset
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false,
                            backgroundColor: '#1f2937', // bg-gray-800
                            titleColor: '#ffffff',
                            bodyColor: '#e5e7eb', // text-gray-200
                            borderColor: '#374151', // border-gray-700
                            borderWidth: 1,
                            padding: 10,
                            cornerRadius: 4,
                            callbacks: {
                                label: function(context) {
                                    return ` Konsumsi: ${context.parsed.y.toFixed(2)} kWh`;
                                }
                            }
                        }
                    },
                    hover: {
                        mode: 'nearest',
                        intersect: true
                    }
                }
            });

            // Update statistik di bawah chart
            const nilaiNumerik = data.nilai.filter(n => typeof n === 'number' && !isNaN(n));
            if (nilaiNumerik.length > 0) {
                const total = nilaiNumerik.reduce((acc, val) => acc + val, 0);
                const avg = total / nilaiNumerik.length;
                const peak = Math.max(...nilaiNumerik);
                if (statsAvgEl) statsAvgEl.textContent = avg.toFixed(2);
                if (statsPeakEl) statsPeakEl.textContent = peak.toFixed(2);
            } else {
                if (statsAvgEl) statsAvgEl.textContent = "0.00";
                if (statsPeakEl) statsPeakEl.textContent = "0.00";
            }
        }

        async function loadGrafikAndUpdateUI(tipe) {
            const dataGrafik = await fetchDataGrafik(tipe);
            renderGrafik(dataGrafik); // Tipe tidak perlu lagi karena sudah dihandle di fetchDataGrafik untuk label stats
            
            // Update tampilan tombol aktif
            if (btnMingguan && btnBulanan) {
                if (tipe === 'mingguan') {
                    btnMingguan.classList.remove('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
                    btnMingguan.classList.add('bg-green-600', 'text-white', 'hover:bg-green-700');
                    btnBulanan.classList.remove('bg-green-600', 'text-white', 'hover:bg-green-700');
                    btnBulanan.classList.add('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
                } else {
                    btnBulanan.classList.remove('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
                    btnBulanan.classList.add('bg-green-600', 'text-white', 'hover:bg-green-700');
                    btnMingguan.classList.remove('bg-green-600', 'text-white', 'hover:bg-green-700');
                    btnMingguan.classList.add('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
                }
            }
        }
        
        if (btnMingguan && btnBulanan) {
            btnMingguan.addEventListener('click', () => loadGrafikAndUpdateUI('mingguan'));
            btnBulanan.addEventListener('click', () => loadGrafikAndUpdateUI('bulanan'));
        }

        // Load grafik mingguan secara default saat halaman dimuat
        loadGrafikAndUpdateUI('mingguan');
    }


    // --- Smart Tips Modal Logic ---
    const smartTipsButton = document.getElementById('btn-smart-tips');
    const smartTipsModal = document.getElementById('smart-tips-modal');
    const closeSmartTipsModalButton = document.getElementById('close-smart-tips-modal');
    const smartTipsContent = document.getElementById('smart-tips-content');
    const smartTipsText = document.getElementById('smart-tips-text');
    const smartTipsLoading = document.getElementById('smart-tips-loading');
    const smartTipsError = document.getElementById('smart-tips-error');
    const smartTipsErrorText = document.getElementById('smart-tips-error-text'); // Elemen untuk pesan error spesifik

    if (smartTipsButton && smartTipsModal && closeSmartTipsModalButton && smartTipsContent && smartTipsText && smartTipsLoading && smartTipsError) {
        smartTipsButton.addEventListener('click', async () => {
            smartTipsModal.classList.remove('hidden');
            smartTipsLoading.classList.remove('hidden');
            smartTipsContent.classList.add('hidden');
            smartTipsError.classList.add('hidden');
            if(smartTipsErrorText) smartTipsErrorText.textContent = "Maaf, terjadi kesalahan saat mengambil tips. Silakan coba lagi."; // Reset pesan error
            smartTipsText.textContent = ''; // Kosongkan tips sebelumnya

            try {
                // Pastikan endpoint ini ada di Flask (sc 2.py)
                const response = await fetch("/generate-smart-tips"); 
                if (!response.ok) {
                     const errorData = await response.json().catch(() => ({error: `HTTP error! Status: ${response.status}`}));
                    throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
                }
                const data = await response.json();

                if (data.error) {
                    if(smartTipsErrorText) smartTipsErrorText.textContent = data.error;
                    smartTipsError.classList.remove('hidden');
                } else if (data.tips) {
                    let formattedTips = data.tips;
                    // Jika tips adalah string dengan poin-poin, kita bisa biarkan atau format lebih lanjut
                    // Jika ingin memastikan setiap poin ada di baris baru dan ada bullet:
                    if (typeof data.tips === 'string') {
                        formattedTips = data.tips.split('\n').map(tip => {
                            tip = tip.trim();
                            if (tip.startsWith('- ') || tip.startsWith('• ')) {
                                return tip;
                            } else if (tip.length > 0) {
                                return `• ${tip}`;
                            }
                            return ''; // Abaikan baris kosong
                        }).filter(tip => tip.length > 0).join('\n');
                    } else if (Array.isArray(data.tips)) { // Jika backend mengembalikan array
                        formattedTips = data.tips.map(tip => `• ${tip.trim()}`).join('\n');
                    }
                    smartTipsText.innerHTML = formattedTips.replace(/\n/g, '<br>'); // Ganti newline dengan <br> untuk HTML
                } else {
                    smartTipsText.textContent = "Tidak ada tips yang dapat ditampilkan saat ini.";
                }
            } catch (e) {
                console.error("Gagal mengambil smart tips:", e);
                if(smartTipsErrorText) smartTipsErrorText.textContent = e.message || "Gagal memuat tips. Periksa koneksi Anda atau coba lagi nanti.";
                smartTipsError.classList.remove('hidden');
            } finally {
                smartTipsLoading.classList.add('hidden');
                smartTipsContent.classList.remove('hidden');
            }
        });

        closeSmartTipsModalButton.addEventListener('click', () => {
            smartTipsModal.classList.add('hidden');
        });

        // Klik di luar modal untuk menutup
        smartTipsModal.addEventListener('click', (event) => {
            if (event.target === smartTipsModal) {
                smartTipsModal.classList.add('hidden');
            }
        });
    }

    // --- Flash Message Auto-hide (Opsional) ---
    const flashMessages = document.querySelectorAll('.flash-messages li');
    flashMessages.forEach(flash => {
        setTimeout(() => {
            flash.style.transition = 'opacity 0.5s ease';
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 500); // Hapus elemen setelah transisi selesai
        }, 5000); // Sembunyikan setelah 5 detik
    });

}); // Akhir dari DOMContentLoaded
