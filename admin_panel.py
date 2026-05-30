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
# ⚙️ MENGAMBIL KUNCI DARI BRANKAS CLOUD
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
# 🧠 MASTER PROMPT AI VERSI ULTIMATE 
# ==========================================
PROMPT_INSTRUCTION = """
Kamu adalah sistem ekstraksi data finansial tingkat lanjut. Baca SEMUA gambar yang dilampirkan dan ekstrak HANYA ke dalam format JSON murni.

Struktur JSON yang WAJIB kamu hasilkan:
{
  "ticker": "AADI",
  "company_name": "...",
  "description": "...",
  "sector": "...",
  "sub_sector": "...",
  "address": "...",
  "website": "...",
  "ipo_date": "...",
  "ipo_price": 1400,
  "board": "...",
  "npwp": "...",
  "telepon": "...",
  "fax": "...",
  "email": "...",
  "saham_ipo": "...",
  "jumlah_ipo": "...",
  "free_float": "...",
  "penjamin_emisi": "...",
  "biro_administrasi": "...",

  "shareholders_greater_1": [
    {"nama": "PT DWIMURIA INVESTAMA", "saham": "67.73 B", "persentase": "54.94%"}
  ],
  "shareholders_100": [
    {"nama": "MASYARAKAT NON WARKAT", "saham": "51.97 B", "persentase": "42.159%"}
  ],
  "board_members": [
    {"nama": "JAHJA SETIAATMADJA", "jabatan": "Komisaris", "saham": "35.80 M", "persentase": "0.03%"}
  ],
  "ubo": [
    "ROBERT BUDI HARTONO", "BAMBANG HARTONO"
  ],
  "shareholder_history": [
    {"tanggal": "30 Apr 2026", "jumlah": "761,361", "perubahan": "+46,510"}
  ],

  "insider_data": [
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
  
  "corp_action": [
    {
      "type": "Dividen", 
      "status": "Ongoing", 
      "title_val": "Rp 456.9", 
      "details": {"Cum Date": "4 Jun 2026", "Ex Date": "5 Jun 2026", "Tanggal Pencatatan": "8 Jun 2026"}
    }
  ],

  "seasonality": [
    {"row_name": "Rata-rata", "jan": "10.23", "feb": "-3.56", "mar": "9.46", "apr": "2.97"},
    {"row_name": "2026", "jan": "8.96", "feb": "21.71", "mar": "21.89", "apr": "2.88"},
    {"row_name": "Probabilitas", "jan": "100", "feb": "50", "mar": "50", "apr": "100"}
  ],

  "fin_income_annual": [
    {"period": "2021", "revenue": "55.3T", "net_income": "10.5T", "net_margin": "19%"}
  ],
  "fin_income_quarter": [
    {"period": "Q1 2025", "revenue": "19T", "net_income": "3.2T", "net_margin": "17%"}
  ],
  "fin_balance_annual": [],
  "fin_balance_quarter": [],
  "fin_cashflow_annual": [],
  "fin_cashflow_quarter": []
}

ATURAN WAJIB (BACA DENGAN TELITI):
1. AKURASI TINGKAT TINGGI: Baca angka, tanda baca (titik/koma), singkatan (M/B/T), dan teks DENGAN SANGAT TELITI. DILARANG KERAS melakukan typo atau salah penempatan desimal. Pastikan "ipo_price" selalu berupa angka bulat/integer (contoh: 1400).
2. Pemegang Saham: Pisahkan >1% dan 100%. Untuk Direksi/Komisaris, terjemahkan tag [K] = Komisaris, [D] = Direksi.
3. Insider: Tangkap jenis action (Buy/Sell/Cross/Transfer/Corp Action), sumber (IDX/KSEI), dan arah panah (Buy=+ / Sell=- pada amount_pct).
4. Corp Action: Tangkap tipe (Dividen/RUPS/dll), status (jika ada tag ungu Ongoing), dan masukkan semua baris data ke dalam objek "details".
5. Seasonality: Ambil nama baris (Rata-rata, Tahun, Probabilitas) dan masukkan nilai per bulannya. HILANGKAN tanda % khusus di tabel Seasonality. 
6. Financials (Annual vs Quarter): PERHATIKAN tulisan "Annual" atau "Quarter" pada menu dropdown di gambar. Jika gambar "Annual", WAJIB isi array _annual dan kosongkan _quarter (dan sebaliknya).
7. HANYA KEMBALIKAN JSON MURNI. JIKA GAMBAR TIDAK MENGANDUNG DATA TERSEBUT, ISI DENGAN ARRAY KOSONG [].
"""

st.title("🤖 ElevenTen Capital - Smart Admin Panel")
st.info(f"Sistem menggunakan model: **{model_name}**")

uploaded_files = st.file_uploader("Upload SEMUA Screenshot Profil Saham", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files:
    images = [Image.open(f) for f in uploaded_files]
    st.image(images, width=150)

    if st.button("✨ Ekstrak Seluruh Data", type="primary"):
        with st.spinner('AI sedang membedah piksel gambar dengan akurasi tinggi...'):
            try:
                response = model.generate_content([PROMPT_INSTRUCTION] + images)
                raw_text = response.text
                
                # 🛡️ BULLETPROOF JSON EXTRACTOR: Paksa ambil hanya isi dalam { }
                start_idx = raw_text.find('{')
                end_idx = raw_text.rfind('}')
                
                if start_idx != -1 and end_idx != -1:
                    json_str = raw_text[start_idx:end_idx+1]
                    st.session_state['extracted_data'] = json.loads(json_str)
                    st.success("✅ AI berhasil memetakan struktur data tanpa cacat!")
                else:
                    st.error("❌ AI gagal menghasilkan format JSON. Silakan coba lagi.")
                    
            except Exception as e:
                st.error(f"❌ Kesalahan Sistem: {e}")

if 'extracted_data' in st.session_state:
    data = st.session_state['extracted_data']
    st.markdown("### 📋 Preview JSON (Validasi Sebelum Simpan)")
    
    with st.form("validation_form"):
        edited_json_str = st.text_area("Cek & Edit Manual jika diperlukan:", value=json.dumps(data, indent=4), height=500)
        submitted = st.form_submit_button("💾 Simpan Smart Update ke Database")
        
        if submitted:
            try:
                raw_payload = json.loads(edited_json_str)
                ticker = raw_payload.get("ticker", "").upper()
                
                if not ticker:
                    st.error("Ticker kosong! AI gagal membaca Ticker.")
                else:
                    # ====================================================
                    # 🛡️ SMART PATCHER: Filter ketat penolak data kosong
                    # ====================================================
                    payload = {"ticker": ticker}
                    for key, value in raw_payload.items():
                        if key == "ticker": continue
                        
                        # Aturan kelolosan data:
                        if isinstance(value, str) and value.strip() not in ["", "-", "null"]:
                            payload[key] = value
                        elif isinstance(value, list) and len(value) > 0:
                            payload[key] = value
                        elif isinstance(value, (int, float)) and value > 0:
                            payload[key] = value
                    
                    with st.spinner("Mengirim Smart Update ke Supabase..."):
                        supabase.table("company_profiles").upsert(payload).execute()
                        st.success(f"🚀 BERHASIL! Data {ticker} sukses diperbarui tanpa merusak brankas lama!")
                        del st.session_state['extracted_data']
                        
            except json.JSONDecodeError:
                st.error("❌ Format JSON tidak valid! Ada kutip atau koma yang salah saat Anda mengedit manual.")
            except Exception as e:
                st.error(f"❌ Gagal menyimpan ke Database: {e}")
