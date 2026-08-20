# Q3 Indonesia — Call 02: Loan Qualification + Mixed English Finance Terms + Colloquial
**Scenario:** Loan qualification, customer uses finance English loanwords naturally, colloquial Bahasa  
**Language:** Colloquial Bahasa Indonesia + English loanwords (DP, tenor, cicilan)  
**Bot:** Sari — DarwixFinance Indonesia Multifinance  
**Call Type:** Qualification (pinjaman baru)  
**Outcome:** ✅ QUALIFIED  
**Turns:** 12  
**Detected Accent:** Jakarta (standard)  

---

**SARI:** Selamat siang Bapak/Ibu! Saya Sari dari DarwixFinance. Kami memiliki program pembiayaan yang mungkin sesuai dengan kebutuhan Bapak/Ibu saat ini, dengan proses yang mudah dan cepat. Apakah Bapak/Ibu punya waktu beberapa menit?

**CUSTOMER:** Bisa, gue lagi santai nih. Pengen tau soal kredit motor.

**SARI:** Wah, pas banget! Kami punya program pembiayaan kendaraan yang menarik. Boleh saya tanya dulu — motor apa yang Bapak/Ibu minati, dan kira-kira harganya berapa?

**CUSTOMER:** Honda Vario 125, harganya sekitar 22 juta. Mau DP berapa persen biasanya?

**SARI:** Untuk kendaraan roda dua, biasanya DP-nya mulai dari 20% sampai 30% dari harga OTR. Untuk Honda Vario 125 seharga Rp 22 juta, berarti DP-nya sekitar Rp 4,4 juta sampai Rp 6,6 juta. Tenor yang tersedia biasanya 12, 24, 36, atau 48 bulan. Bapak/Ibu lebih nyaman tenor berapa bulan?

**CUSTOMER:** Kayaknya 24 bulan deh, biar cicilannya ga terlalu gede. Cicilan per bulannya kira-kira berapa?

**SARI:** Dengan asumsi DP 20% dan tenor 24 bulan, cicilan bulanannya kira-kira di sekitar Rp 850.000 sampai Rp 950.000 per bulan, tergantung suku bunga yang berlaku saat pengajuan. Ini perkiraan ya Bapak/Ibu — angka pastinya akan dikonfirmasi oleh tim kami setelah pengajuan diproses.

**CUSTOMER:** Oke, masuk akal. Penghasilan gue sekitar 5 juta per bulan, kira-kira bisa disetujui ga?

**SARI:** Berdasarkan pedoman umum kami, cicilan sebaiknya tidak melebihi 30-40% dari penghasilan bulanan. Dengan penghasilan Rp 5 juta, batas cicilan yang nyaman sekitar Rp 1,5 sampai Rp 2 juta. Cicilan sekitar Rp 900.000 masih dalam batas aman tersebut, jadi peluangnya cukup baik. Tapi keputusan final tetap ada di tim underwriting kami ya.

**CUSTOMER:** Oke. Prosesnya ribet ga? Dokumen apa aja yang dibutuhin?

**SARI:** Prosesnya relatif mudah. Biasanya yang dibutuhkan adalah KTP, slip gaji atau bukti penghasilan, dan formulir aplikasi. Untuk kendaraan, juga perlu STNK referensi. Proses persetujuan biasanya 1-3 hari kerja. Bapak/Ibu bisa mulai pengajuan via aplikasi kami atau kunjungi dealer partner kami.

**CUSTOMER:** Wah, cepet juga ya. Boleh gue daftar sekarang?

**SARI:** Tentu Bapak/Ibu! Saya akan catat data Bapak/Ibu sekarang dan tim kami akan menghubungi dalam 24 jam untuk proses selanjutnya. Boleh saya minta nama lengkap, nomor HP aktif, dan email?

**CUSTOMER:** Nama gue Budi Santoso, HP 081234567890, email budi.santoso@gmail.com.

**SARI:** Terima kasih Budi Santoso! Data sudah saya catat. Tim kami akan menghubungi Bapak paling lambat besok siang untuk konfirmasi dan langkah selanjutnya. Ada pertanyaan lain?

**CUSTOMER:** Ga ada, makasih ya!

**SARI:** Sama-sama Bapak Budi! Semoga pembiayaannya berjalan lancar. Selamat siang! [QUALIFIED]

---

## Call Result

| Field                | Value                                             |
|---------------------|---------------------------------------------------|
| Outcome             | QUALIFIED                                         |
| Product             | Kredit motor (Honda Vario 125)                    |
| DP                  | ~20% (Rp 4.4 juta)                               |
| Tenor               | 24 bulan                                          |
| Est. Cicilan        | Rp 850k–950k/mo                                  |
| Monthly Income      | Rp 5 juta (cicilan <30% income — eligible)       |
| Contact             | 081234567890                                      |
| Escalation          | No                                                |

## Localization Quality Notes

| Feature | Observation |
|---------|-------------|
| Finance loanwords | DP, tenor, cicilan, OTR, KTP, STNK — all used naturally in context |
| Colloquial register | "Gue/nih/deh" (Jakarta casual) — bot maintained formal "Bapak" but responded warmly |
| English mix | "30-40% dari penghasilan" — natural Indonesian financial advisory phrasing |
| 30% DTI rule | Applied from financial knowledge — correctly flags sustainable cicilan |
| Disclaimer | "Angka pastinya dikonfirmasi" — bot did NOT commit to exact rates (correct) |
| Colloquial to formal | Customer used "gue," bot used "Bapak" — appropriate register gap maintained |

## Code-Switching Behavior
- Customer: "Cicilan per bulannya kira-kira berapa?" — Indonesian syntax + English "cicilan"
- Customer: "DP berapa persen" — English abbreviation in Indonesian sentence
- All financial English loanwords transcribed correctly by Deepgram id model
- No unexpected language switching observed

## Known Native-Speaker/Compliance Gaps
- Exact interest rates not available in KB — correctly handled with "perkiraan" (estimate) disclaimer
- "Gue/lu" colloquial register: bot correctly did not mirror informal pronouns in financial context
- No regional TTS: Jakarta accent used for all output, even though customer was Jakarta-standard
