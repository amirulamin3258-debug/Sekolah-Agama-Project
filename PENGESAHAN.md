# Senarai Pengesahan (perlu disemak pihak sekolah)

Perkara di bawah **tidak diteka**. Video tetap dihasilkan; setiap perkara boleh dibetulkan dalam `config/` dan dirender semula
(hanya shot yang berubah dirender semula).

## A. Carta organisasi

| # | Perkara | Status dalam video | Cara betulkan |
|---|---------|-------------------|---------------|
| 1 | **Carta Pentadbiran Sekolah** (Guru Besar: Ustaz Farikh Ikhsan / Ustaz Farid Eh Shahzan; PK Pentadbiran: Ustazah Noor Sadina; Ustazah Ruhayah, Ustazah Nur Syaf…, Ustazah Amni) | **Tidak dipaparkan** — tidak digabung dengan carta jawatankuasa | Sahkan nama & jawatan dalam `config/organization.json` → `administration`, kemudian `enabled: true` |
| 2 | Potret **Pn Suzilawati binti Suhaimi** mengandungi **dua orang** (seorang di rostrum, seorang berpakaian seragam) | Gambar dipaparkan penuh, tidak dipotong ke mana-mana wajah | Hantar potret seorang diri, atau nyatakan orang kiri/kanan (`focus`) |
| 3 | Potret **Pn Ameera binti Yusof** ialah **video 6.7 s** (bukan foto); wajah tidak jelas dalam beberapa bingkai | Klip asal dimainkan dalam bingkai potret | Hantar foto potret, ganti fail `assets/portraits/07_ameera.*` |
| 4 | Potret **En Abd Ghani bin Abu Bakar** resolusi rendah (427×585) | Digunakan | Hantar versi resolusi tinggi jika ada |
| 5 | Fail potret **"Tuan Zulhisham bin Ahmad Shukori.png"** — nama **tiada** dalam senarai jawatankuasa | **Tidak digunakan** | Nyatakan jawatan beliau; tambah ke `committee.members` |
| 6 | Nama **Norsyaruziana** disebut dua kali dalam senarai asal | Dipaparkan sekali sahaja (Pemeriksa Kira-Kira) | — |
| 7 | Ejaan rasmi semua nama (cth. "Abdull", "M Nor") | Mengikut senarai yang diberikan | Betulkan dalam `organization.json` |

## B. Kandungan & tarikh

| # | Perkara | Status dalam video |
|---|---------|-------------------|
| 8 | Folder **"Majlis Anugerah 2025"** — bukan 2026 | Dilabel **"Majlis Anugerah Kecemerlangan 2025"** dalam Bab 4 (tidak didakwa sebagai 2026) |
| 9 | Folder **"Kem Mahir Jawi"** — tali leher murid tertulis *ROCKET CAMP UPKK/SRAI 2026* | Diletakkan di bawah segmen **Rocket Camp** (Bab 2). Jika benar Kem Mahir Jawi, pecahkan segmen dalam `activities.json` |
| 10 | Slogan **"Ilmu Jadi Pemimpin, Iman Jadi Perisai"** (daripada sepanduk rombongan I43/I48) | Digunakan pada tajuk & penutup — sahkan ia slogan rasmi |
| 11 | Bilangan sebenar murid **6A** (I19: 6 murid + 1 guru; I18: seorang murid lain) | Tiada angka dipaparkan; hanya lencana "6A SRAI 2026" |
| 12 | Nama murid | Tiada nama murid dipaparkan |
| 13 | **Ustazah Shahirah** (folder Kenangan Guru Ganti) — tidak pasti wajah yang mana dalam I02/I03 | Nama hanya sebagai teks penghargaan, tidak dilabel pada wajah |
| 14 | Bab 3: CCTV, Smart TV, kipas, tingkap, lantai — **tiada gambar** diterima untuk item ini (bahan sedia ada hanya pemasangan langsir) | Disenaraikan sebagai kad teks "Penambahbaikan 2026" tanpa gambar palsu. Hantar gambar jika ada |
| 15 | **Pendaftaran sekolah 2025** & **mesyuarat guru** — tiada bahan dalam 11 folder | Tidak dimasukkan |
| 16 | Tarikh setiap aktiviti (untuk susunan kronologi) | Disusun mengikut tema (storyboard) |

## C. Bahan teknikal

| # | Perkara | Tindakan |
|---|---------|----------|
| 17 | 56 video asal 360p (WhatsApp) | Di-upscale ke 1080p (Lanczos + sharpen); video menegak diletak atas latar kabur / split-screen |
| 18 | Watermark "HONOR X9e Pro" (I20–I24, I26–I29, I31, I32, I35, I36) | Crop 8% bawah (`asset_fixes`) |
| 19 | I42 ada stiker "OOPS" | **Tidak digunakan** — hantar versi asal tanpa stiker |
| 20 | V03 (0.7 s), V27 (0.5 s), V08 (tangan menghalang) | Digugurkan (ikut storyboard) |
| 21 | V16, V19, V23, V26, V31, V55, V56 (klip 1–2 s / pendua) | Tidak diperlukan dalam suntingan akhir |
| 22 | Suara latar | **Tiada rakaman suara** — narasi dipaparkan sebagai sari kata. Rakam mengikut `output/voiceover_script.txt` dan letak dalam `assets/audio/voiceover/` |
| 23 | Muzik | Gubahan instrumental **asal** yang dijana oleh `scripts/music.py` (tiada hak cipta pihak ketiga). Jika sekolah mahu tanpa alat muzik (nasyid/perkusi sahaja), tetapkan `audio.music_file_override` |
