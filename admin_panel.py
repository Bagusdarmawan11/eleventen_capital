import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import json
import re
from PIL import Image

# ==========================================
# 🌟 PENGATURAN HALAMAN
# ==========================================
st.set_page_config(page_title="ElevenTen Admin", page_icon="🤖", layout="wide")

# ==========================================
# ⚙️ GANTI 3 BARIS INI DENGAN KUNCI RAHASIAMU
# ==========================================
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

genai.configure(api_key=GEMINI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_resource
def load_best_model():
    valid_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name.replace('models/', ''))
        chosen = next((p for p in ['gemini-1.5-pro', 'gemini-1.5-flash'] if p in valid_models), valid_models[0] if valid_models else None)
        return genai.GenerativeModel(chosen) if chosen else None, chosen
    except:
        return genai.GenerativeModel('gemini-1.5-flash'), 'gemini-1.5-flash (Fallback)'

model, model_name = load_best_model()

# ==========================================
# 🧠 MASTER PROMPT AI VERSI ULTIMATE (TAK TERPOTONG)
# ==========================================
PROMPT_INSTRUCTION = """
Kamu adalah sistem ekstraksi data finansial tingkat lanjut. Tugasmu adalah membaca BEBERAPA gambar screenshot profil saham (yang mungkin merupakan potongan screenshot dari satu halaman panjang) dan mengekstrak informasinya ke dalam format JSON murni. Rangkum dan gabungkan informasi dari semua gambar tersebut.

Ekstrak key berikut persis seperti penamaan ini:
- "ticker" : (Ambil 4 huruf kapital di nama perusahaan/header)
- "company_name" : (Ambil dari Nama Perusahaan)
- "description" : (Ambil seluruh teks dari Tentang Perusahaan)
- "sector" : (Ambil dari Sektor)
- "sub_sector" : (Ambil dari Sub Sektor)
- "address" : (Ambil dari Alamat)
- "website" : (Ambil dari Website)
- "ipo_date" : (Ambil dari Tanggal Pencatatan Saham)
- "ipo_price" : (Ambil angka dari Harga IPO, hilangkan koma jadikan angka utuh. Contoh: 1400)
- "board" : (Ambil dari Papan Pencatatan)
- "npwp" : (Ambil dari NPWP)
- "telepon" : (Ambil dari Telepon)
- "fax" : (Ambil dari Fax)
- "email" : (Ambil dari Email)
- "saham_ipo" : (Ambil dari Saham IPO, biarkan formatnya seperti di gambar)
- "jumlah_ipo" : (Ambil dari Jumlah IPO, biarkan formatnya seperti di gambar)
- "free_float" : (Ambil dari Free Float)
- "penjamin_emisi" : (Ambil dari Penjamin Emisi)
- "biro_administrasi" : (Ambil dari Biro Administrasi)
- "shareholders_greater_1": [ (Daftar pemegang saham > 1%)
    {"nama": "PT DWIMURIA INVESTAMA ANDALAN", "saham": "67.73 B", "persentase": "54.94%"}
  ],
- "shareholders_100": [ (Daftar pemegang saham masyarakat)
    {"nama": "MASYARAKAT NON WARKAT", "saham": "51.97 B", "persentase": "42.159%"}
  ],
- "board_members": [ (Daftar Direksi & Komisaris)
    {"nama": "JAHJA SETIAATMADJA", "jabatan": "Komisaris", "saham": "35.80 M", "persentase": "0.03%"}
  ],
- "ubo": [ (Daftar nama Ultimate Beneficiary Owner)
    "ROBERT BUDI HARTONO", "BAMBANG HARTONO"
  ],
- "shareholder_history": [ (Histori jumlah pemegang saham)
    {"tanggal": "30 Apr 2026", "jumlah": "761,361", "perubahan": "+46,510"}
  ],
- "insider_data": [ (Histori transaksi insider)
    {
      "date": "28 Jan 26",
      "action": "Buy",
      "name": "ETY YUNIARTI",
      "tag": "[D]",
      "amount": "98,000",
      "amount_pct": "+0.0001%",
      "current": "291,262",
      "current_pct": "0.0002%",
      "previous": "193,262",
      "previous_pct": "0.0001%",
      "price": "3,640",
      "type": "Domestic",
      "source": "IDX"
    }
  ],
- "corp_action": [ (Aksi korporasi seperti Dividen, RUPS, Right Issue)
    {
      "type": "Dividen", 
      "status": "Ongoing", 
      "title_val": "Rp 456.9", 
      "details": {"Cum Date": "4 Jun 2026", "Ex Date": "5 Jun 2026", "Tanggal Pencatatan": "8 Jun 2026", "Tanggal Pembayaran": "25 Jun 2026"}
    }
  ],
- "seasonality": [ (Tabel matrix seasonality MONTHLY)
    {"row_name": "Average", "jan": "10.23", "feb": "-3.56", "mar": "9.46", "apr": "2.97", "may": "-1.50", "jun": "4.20", "jul": "3.15", "aug": "-2.80", "sep": "5.10", "oct": "1.90", "nov": "-3.30", "dec": "7.50"}
  ],
- "fin_income_annual": [ (Laporan Keuangan Laba Rugi TAHUNAN)
    {"period": "2021", "revenue": "55300000000", "net_income": "10500000000", "net_margin": "19.0"}
  ],
- "fin_income_quarter": [ (Laporan Keuangan Laba Rugi KUARTALAN)
    {"period": "Q1 2025", "revenue": "19000000000", "net_income": "32000000000", "net_margin": "17.0"}
  ],
- "fin_balance_annual": [ (Laporan Keuangan Neraca TAHUNAN)
    {"period": "2021", "assets": "82000000000", "liabilities": "31000000000", "der": "0.38"}
  ],
- "fin_balance_quarter": [], (Isi format sama dengan balance_annual)
- "fin_cashflow_annual": [ (Laporan Keuangan Arus Kas TAHUNAN)
    {"period": "2021", "operating": "12000000000", "investing": "-3500000000", "financing": "-6800000000"}
  ],
- "fin_cashflow_quarter": [] (Isi format sama dengan cashflow_annual)

=== TUGAS KEYSTATS (BARU) ===
Format JSON untuk keystats:
"keystats": [
  {
    "section": "Valuation",
    "data": [
      {"label": "Current PE Ratio (Annualised)", "value": "11.96"}
    ]
  },
  {
    "section": "Income Statement - EPS",
    "is_table": true,
    "data": [
      {"Period": "Q1", "2026": "119.12", "2025": "114.75", "2024": "104.48"}
    ]
  }
]

ATURAN WAJIB (BACA DENGAN TELITI, JANGAN LEWATKAN SATUPUN): 
1. KEMBALIKAN HANYA JSON MURNI. Jangan ada tambahan teks markdown seperti ```json atau awalan/akhiran apapun.
2. JANGAN TYPO. Baca angka, koma, titik, dan singkatan (M/B/T) dengan akurasi 100%. Pastikan "ipo_price" selalu berupa angka bulat/integer.
3. PEMEGANG SAHAM & DIREKSI: Pisahkan >1% dan 100%. Untuk Direksi/Komisaris, WAJIB terjemahkan tag [K] = Komisaris, [D] = Direksi.
4. INSIDER: Tangkap jenis action (Buy/Sell/Cross/Transfer/Corp Action), sumber (IDX/KSEI), dan arah panah (Buy=+ / Sell=- pada amount_pct).
5. CORP ACTION: Tangkap tipe, status (jika ada tag ungu Ongoing), dan masukkan SEMUA baris data ke dalam objek "details".
6. SEASONALITY: Ambil nama baris (Average, Tahun, Probabilitas). HILANGKAN tanda % khusus di nilai tabel Seasonality agar terbaca sebagai angka.
7. FINANCIALS: PERHATIKAN tulisan "Annual" atau "Quarter" pada dropdown di gambar. WAJIB konversi angka grafik menjadi angka mentah (raw integer/float), hilangkan T/B/M/K. Net Margin dan DER HARUS angka desimal murni tanpa %.
8. KEYSTATS CERDAS: Jika Header tabel terpotong, lihat nilai angkanya: Jika nominalnya Kecil (puluhan/ratusan) = "Income Statement - EPS". Jika nominalnya Besar (Triliun/Miliar) sejalan Gross Profit = "Income Statement - Revenue". Jika nominalnya Besar tapi di bawah Revenue = "Income Statement - Net Income". Biarkan akhiran huruf (B/T/%) tetap ada khusus di value Keystats.
9. JIKA DATA TIDAK ADA: Isi dengan null (untuk teks tunggal) atau array kosong [] (untuk list).
"""

st.title("🤖 ElevenTen Capital - Smart Admin Panel")
st.write("Unggah screenshot profil emiten (Bisa lebih dari 1 gambar jika panjang).")
st.info(f"✅ Sistem otomatis menggunakan model AI: **{model_name}**")

uploaded_files = st.file_uploader("Pilih Gambar (JPG/PNG)", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files:
    images = []
    cols = st.columns(len(uploaded_files))
    for i, file in enumerate(uploaded_files):
        img = Image.open(file)
        images.append(img)
        with cols[i]:
            st.image(img, use_container_width=True)

    if st.button("✨ Ekstrak Seluruh Data dengan AI", type="primary"):
        with st.spinner('Membaca seluruh gambar secara menyeluruh...'):
            try:
                payload = [PROMPT_INSTRUCTION] + images
                response = model.generate_content(payload)
                raw_text = response.text.strip()
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                
                # Gunakan Regex untuk mengekstrak hanya isi di dalam kurung kurawal {}
                # Ini untuk mencegah jika AI memberikan teks pembuka sebelum JSON.
                match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    extracted_data = json.loads(json_str)
                    st.session_state['extracted_data'] = extracted_data
                    st.success("✅ AI berhasil mengekstrak seluruh data!")
                else:
                    st.error("❌ AI gagal menghasilkan format JSON yang valid.")

            except Exception as e:
                st.error(f"❌ Terjadi kesalahan ekstraksi: {e}")

if 'extracted_data' in st.session_state:
    st.write("---")
    st.markdown("### 📋 Validasi Seluruh Data Profil")
    data = st.session_state['extracted_data']
    
    # Gunakan form agar kita bisa memvalidasi JSON raksasa ini di satu tempat
    with st.form("validation_form"):
        # Kita tampilkan JSON mentahnya di text area agar CEO bisa mengubah array/struktur kompleks jika AI salah baca.
        edited_json_str = st.text_area("JSON Data (Validasi & Edit manual jika ada typo AI)", value=json.dumps(data, indent=4), height=600)
        
        submitted = st.form_submit_button("💾 Simpan Smart Update ke Database")
        
        if submitted:
            try:
                raw_payload = json.loads(edited_json_str)
                ticker = raw_payload.get("ticker", "").upper()
                
                if not ticker:
                    st.error("Ticker kosong!")
                else:
                    # ====================================================
                    # 🛡️ SMART PATCHER: Filter ketat penolak data kosong
                    # ====================================================
                    # Kita bangun payload yang hanya berisi key yang ada isinya.
                    # Ini mencegah Supabase menimpa data lama dengan data kosong dari form Python.
                    payload = {"ticker": ticker}
                    
                    # Daftar semua key data profil yang ingin kita kirim ke Supabase
                    keys_to_check = [
                        "company_name", "description", "sector", "sub_sector", "address", 
                        "website", "ipo_date", "ipo_price", "board", "npwp", "telepon", 
                        "fax", "email", "saham_ipo", "jumlah_ipo", "free_float", 
                        "penjamin_emisi", "biro_administrasi", "shareholders_greater_1", 
                        "shareholders_100", "board_members", "ubo", "shareholder_history", 
                        "insider_data", "corp_action", "seasonality", 
                        "fin_income_annual", "fin_income_quarter", "fin_balance_annual", 
                        "fin_balance_quarter", "fin_cashflow_annual", "fin_cashflow_quarter",
                        "keystats" 
                    ]
                    
                    for key in keys_to_check:
                        value = raw_payload.get(key)
                        
                        # Aturan kelolosan data:
                        # 1. Jika teks (str), tidak boleh kosong atau cuma tanda strip
                        if isinstance(value, str) and value.strip() not in ["", "-", "null"]:
                            payload[key] = value
                        # 2. Jika list/array, tidak boleh kosong (minimal 1 data)
                        elif isinstance(value, list) and len(value) > 0:
                            payload[key] = value
                        # 3. Jika angka (int/float), tidak boleh 0 atau kosong
                        elif isinstance(value, (int, float)) and value > 0:
                            payload[key] = value
                        # 4. Jika boolean (True/False), langsung masukkan
                        elif isinstance(value, bool):
                            payload[key] = value
                    
                    # Kirim paket 'Smart Payload' yang bersih ke Supabase
                    with st.spinner("Mengirim Smart Update ke Supabase..."):
                        supabase.table("company_profiles").upsert(payload).execute()
                        st.success(f"🚀 BERHASIL! Data {ticker} berhasil diperbarui tanpa merusak brankas lama!")
                        del st.session_state['extracted_data']
                        
            except json.JSONDecodeError:
                st.error("❌ Format JSON tidak valid! Pastikan koma dan tanda kutip sudah benar.")
            except Exception as e:
                st.error(f"❌ Gagal menyimpan ke Supabase: {e}")
