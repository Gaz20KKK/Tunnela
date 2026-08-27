# Tunnela

Jalankan model gambar di komputer sendiri, buka dari browser lewat satu link.

Tunnela terdiri dari dua bagian yang saling melengkapi:

1. **tunnela.py**, skrip resmi yang menyiapkan semuanya secara otomatis.
2. **Web UI** statis untuk menghubungkan link tunnel, generate gambar, dan menyimpan riwayat.

Tidak ada akun, tidak ada konfigurasi rumit, tidak ada data yang dikirim ke siapa pun. Semua komputasi tetap di mesinmu.

## Cara kerjanya

Frontend seperti Automatic1111 atau ComfyUI memang sudah punya antarmuka sendiri. Tunnela berdiri di titik lain: skripnya menangani seluruh persiapan sejak awal, lalu UI cukup menerima satu link tunnel.

1. Paste satu baris perintah ke terminal.
2. Pilih salah satu dari tiga preset bawaan, atau tempel link model sendiri. Skrip mendeteksi GPU atau CPU, membuat virtualenv bila perlu, menginstal PyTorch versi yang tepat, lalu mengunduh model dari HuggingFace atau Civitai dan meminta token hanya kalau modelnya gated.
3. Server hidup, quick tunnel Cloudflare dibuat otomatis, link `trycloudflare.com` dicetak di layar dengan panel ringkasan. Tempel link itu di halaman Connect pada UI dan mulai generate.

Menekan Ctrl+C mematikan model, server, dan tunnel sekaligus tanpa proses yatim.

## Menjalankan

Butuh Python 3.9+. GPU itu opsional, CPU tetap jalan walau lebih lambat.

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/Gaz20KKK/Tunnela/master/tunnela.py -OutFile tunnela.py; python tunnela.py
```

macOS atau Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/Gaz20KKK/Tunnela/master/tunnela.py -o tunnela.py && python3 tunnela.py
```

Google Colab / Kaggle notebook:

```text
!curl -fsSL https://raw.githubusercontent.com/Gaz20KKK/Tunnela/master/tunnela.py -o tunnela.py && python3 tunnela.py
```

Di notebook Colab dan Kaggle, skrip mendeteksi environment bawaan dan memakai torch yang sudah terinstal tanpa membuat virtualenv, jadi tidak ada unduhan raksasa ulang. Terminal biasa mendapat tampilan TUI ringan berupa panel berbingkai, spinner saat proses panjang, bar progres unduhan, dan panel status akhir; notebook otomatis memakai format log polos.

## Preset model bawaan

Belum punya model? Tekan Enter lewat menu, atau langsung `--preset`:

| Preset | Model | Ukuran | Catatan |
|---|---|---|---|
| `fast` | sd-turbo | sekitar 2,5 GB | langkah 1 sampai 4, CPU masih nyaman |
| `balanced` | sdxl-turbo fp16 | sekitar 6,9 GB | langkah 4 di 1024px, enak mulai GPU 8GB |
| `best` | FLUX.1-schnell | sekitar 23,8 GB | Apache 2.0, kualitas tertinggi tapi berat |

Model custom bisa repo HuggingFace, file `.safetensors` tunggal, halaman Civitai, atau file lokal di folder `models/`. Skrip mencetak progres unduhan dengan rapi dan cache lokal supaya kali berikutnya cepat.

## Di dalam UI

- **Connect**: tempel link tunnel, uji koneksi langsung ke endpoint `/health`.
- **Workspace**: prompt plus parameter lanjutan (steps, CFG, sampler, seed, resolusi, batch), skeleton loading, progress tipis.
- **History**: riwayat auto-save lengkap dengan parameter, pencarian, filter waktu, export JSON.
- Mode demo dengan gambar placeholder saat backend belum terhubung.

## Catatan teknis singkat

- CPU offload aktif otomatis ketika free VRAM pas-pasan; FLUX dipakai bfloat16 bila hardware mendukung.
- Token diketik tersembunyi, hidup selama proses saja, tidak ditulis ke disk.
- `python tunnela.py --update` mengambil versi skrip terbaru dari repo ini.

Lisensi MIT.
