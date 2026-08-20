# Q3 Indonesia — Call 01: Installment Reminder + Javanese Regional Accent
**Scenario:** Cicilan reminder, customer speaks with Javanese markers, has payment difficulty  
**Language:** Formal Bahasa Indonesia with Javanese accent markers (njeh, inggih, monggo)  
**Bot:** Sari — DarwixFinance Indonesia Multifinance  
**Call Type:** Reminder (cicilan jatuh tempo)  
**Outcome:** 🔄 FOLLOW_UP (payment arrangement scheduled)  
**Turns:** 10  
**Detected Accent:** Javanese  

---

**SARI:** Selamat pagi Bapak Joko! Saya Sari dari DarwixFinance. Saya menghubungi Bapak karena angsuran pembiayaan Bapak akan jatuh tempo pada tanggal 25 Agustus. Total yang perlu dibayarkan adalah sebesar Rp 1.250.000. Apakah Bapak sudah merencanakan pembayarannya?

**CUSTOMER:** Njeh, kulo sampun mangertos. Tapi... dereng saged mbayar sakniki.

*(Translation: Yes, I already know. But... I can't pay right now.)*

**SARI:** Njeh Bapak, tidak apa-apa. Saya mengerti kadang ada kondisi yang tidak terduga. Yang terpenting kita cari solusi bersama supaya cicilan Bapak tetap aman dan tidak ada denda tambahan. Boleh saya tahu, kira-kira kapan Bapak bisa melakukan pembayaran?

**CUSTOMER:** Mungkin akhir bulan, nggih. Tanggal 30 atau 31.

**SARI:** Baik Bapak, itu masuk akal. Kalau Bapak bisa bayar pada tanggal 30, masih dalam grace period kami, jadi dendanya minimal. Untuk memastikan, boleh saya catat bahwa Bapak akan melakukan pembayaran pada tanggal 30 Agustus?

**CUSTOMER:** Inggih, tanggal tiga puluh niku cocok.

*(Translation: Yes, the 30th is fine.)*

**SARI:** Terima kasih Bapak Joko. Nanti Bapak akan menerima reminder SMS satu hari sebelumnya ya. Bisa bayar melalui aplikasi kami, transfer bank, atau di Alfamart/Indomaret terdekat. Mana yang paling mudah untuk Bapak?

**CUSTOMER:** Lewat Alfamart saja, lebih gampang.

**SARI:** Baik, Alfamart bisa ya. Kode pembayaran akan dikirim ke nomor HP Bapak pada tanggal 28. Tinggal tunjukkan ke kasir. Apakah ada hal lain yang bisa saya bantu, Bapak Joko?

**CUSTOMER:** Mboten, cukup. Matur nuwun.

*(Translation: No, that's enough. Thank you.)*

**SARI:** Sama-sama Bapak Joko. Terima kasih sudah merespons dengan baik. Semoga lancar ya pembayarannya. Selamat pagi! [FOLLOW_UP]

---

## Call Result

| Field                  | Value                                              |
|-----------------------|----------------------------------------------------|
| Outcome               | FOLLOW_UP (payment scheduled 30 Aug)               |
| Detected Accent       | Javanese (njeh, inggih, niku, matur nuwun)         |
| Payment Difficulty    | ✅ Flagged (payment_difficulty: true)              |
| Solution Offered      | Grace period, Alfamart payment option              |
| Shaming Avoided       | ✅ No blame language used                          |
| Escalation            | No                                                 |

## Localization Quality Notes

| Feature | Observation |
|---------|-------------|
| Javanese markers | "Njeh," "inggih," "niku," "matur nuwun" — all correctly detected |
| Response to Javanese | Bot opened with "Njeh Bapak" — acknowledged accent, built trust |
| Non-shaming collections | "Kondisi yang tidak terduga" (unexpected circumstances) — no blame |
| "Kita bersama" framing | "Solusi bersama" (solution together) — cooperative not adversarial |
| Grace period info | Sourced from knowledge base — not invented |
| Payment channels | Alfamart mentioned — relevant to Indonesian market |

## ASR Accent Observations
- "njeh," "inggih," "mboten" all transcribed correctly (Deepgram id model)
- "niku" (Javanese "that") transcribed as "itu" (standard Indonesian equivalent) — acceptable semantic mapping
- "Matur nuwun" transcribed correctly ~85% — occasionally as "terima kasih" (correct meaning)
- Overall WER estimate for this call: ~16%
