# Video Dokumentari Rasmi SRAR Iskandariah 2026

Sistem Python + FFmpeg yang menghasilkan video dokumentari sekolah **1920×1080 · 30 fps · H.264 · AAC** daripada
gambar dan video asal sekolah, berdasarkan storyboard rasmi (5 bab + pembukaan & penutup).

Gaya: *Premium Islamic Corporate Documentary* — hijau zamrud `#006B45`, emas `#D4AF37`, putih, hijau gelap `#003B2B`,
corak geometri Islam minimum, tipografi Cinzel / Playfair Display / Montserrat.

## Struktur video

| Bahagian | Kandungan | Anggaran |
|---|---|---|
| Pembukaan | Lambang, nama sekolah, papan tanda, montaj, tajuk + slogan | ~0:30 |
| Bab 1 – Carta Organisasi | Carta dibina peringkat demi peringkat → zoom ke setiap individu → kad potret (nama typewriter + jawatan) → zoom keluar, kotak bertanda emas → kilauan emas | ~1:35 |
| Bab 2 – Aktiviti & Program | Tahun 1–6, kelas tambahan, Rocket Camp, Yasin, Maulidur Rasul, Jamuan Raya, Rombongan KL, gotong-royong | ~4:30 |
| Bab 3 – Pembangunan | Sebelum → proses → wipe sebelum/selepas → selepas → penambahbaikan 2026 | ~1:10 |
| Bab 4 – Pencapaian 2026 | Multaqa KAFA, Naib Johan Tilawah, 6A, Majlis Anugerah (berlabel 2025) | ~1:40 |
| Bab 5 – Di Sebalik Tabir | Guru & AJK di sebalik tabir, guru ganti, penghargaan | ~1:00 |
| Penutup | Montaj, slogan, kredit | ~0:45 |

Tempoh sebenar setiap render direkod dalam `output/render_report.json`.

## Keperluan

- Python 3.10+ dan `pip install -r requirements.txt`
- `ffmpeg` / `ffprobe` (dengan libx264 dan libass)

## Penggunaan

```bash
# 1. Import bahan (folder atau ZIP muat turun Google Drive). Fail asal tidak diubah.
python main.py import ~/Downloads/SRAR_11_folder.zip --portraits ~/Downloads/Gambar_Individu.zip

# 2. Inventori bahan → config/asset_manifest.json
python main.py scan

# 3. Render bab (berbilang proses + cache; hanya shot yang berubah dirender semula)
python main.py build            # semua bab
python main.py build 01         # Bab 1 sahaja (contoh: selepas tukar nama dalam organization.json)

# 4. Pratonton pantas 540p, kemudian versi akhir 1080p
python main.py preview
python main.py render           # → output/SRAR_Iskandariah_Dokumentari_2026.mp4
```

Fail bahan sekolah **tidak** dimuat naik ke GitHub (privasi murid); ia diimport ke `assets/media/` dan
`assets/portraits/` (dalam `.gitignore`). Setiap bahan dikenal pasti dengan kod storyboard `I01–I87` / `V01–V56`
yang dipadankan dengan Google Drive ID dalam `config/storyboard_assets.json`.

## Konfigurasi

| Fail | Fungsi |
|---|---|
| `config/video_config.json` | Resolusi, fps, warna, fon, tempoh, tetapan encode, audio, sari kata |
| `config/organization.json` | Carta jawatankuasa (nama, jawatan, potret, titik fokus potret). Carta pentadbiran disimpan berasingan, `enabled: false` sehingga disahkan |
| `config/activities.json` | Senarai suntingan setiap bab: segmen, shot, lower third, narasi, transisi, pembetulan bahan (crop watermark) |
| `config/storyboard_assets.json` | 143 bahan daripada storyboard + Drive ID + catatan kandungan |
| `config/asset_manifest.json` | Dijana oleh `scan`: fail tempatan, resolusi, orientasi, tempoh, bab yang menggunakannya |

Contoh: tukar nama → edit `organization.json` → `python main.py build 01 && python main.py render`.

## Audio

- **Muzik**: gubahan instrumental asal dijana oleh `scripts/music.py` (piano, pad strings, pulse ringan; mood berbeza
  setiap bab, crossfade antara bab). Tiada muzik berhak cipta. Untuk guna muzik berlesen sendiri:
  `audio.music_file_override` dalam `video_config.json`.
- **Audio asal**: hanya persembahan koir (V09) dikekalkan; muzik di-*duck* secara automatik.
- **Suara latar**: skrip dijana ke `output/voiceover_script.txt`. Rakam setiap baris sebagai
  `assets/audio/voiceover/cue_001.wav`, `cue_002.wav`, … dan render semula — muzik di-*duck* automatik.
- **Sari kata**: `output/subtitles_ms.srt` (dan dibakar ke dalam video, boleh dimatikan: `subtitles.burn_in`).

## Modul

```
main.py                    CLI
scripts/common.py          konfigurasi, fon, cache, paip ffmpeg
scripts/graphics.py        sistem reka bentuk: latar geometri, kad bab, lower third, kad teks, kredit
scripts/shots.py           renderer shot: foto (Ken Burns sub-piksel), video (upscale, latar kabur), split, wipe, kolaj
scripts/orgchart.py        animasi Carta Organisasi (Bab 1)
scripts/build_chapters.py  kembangkan senarai suntingan → render selari → xfade + dip-to-green
scripts/music.py           penjana muzik asal
scripts/render_video.py    gabung bab + audio master + sari kata → MP4 akhir
scripts/import_assets.py   import folder/ZIP & padankan potret
scripts/scan_assets.py     manifest bahan
```

## Pengesahan

Perkara yang belum disahkan (nama, tarikh, label folder, potret) disenaraikan dalam **[PENGESAHAN.md](PENGESAHAN.md)**.
Tiada nama, wajah atau pencapaian yang diteka atau dijana oleh AI — semua imej ialah bahan asal sekolah.
