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
# 🧠 PROMPT AI VERSI JSONB (STRUKTUR KOMPLEKS)
# ==========================================
PROMPT_INSTRUCTION = """
Kamu adalah sistem ekstraksi data finansial tingkat lanjut. Baca SEMUA gambar yang dilampirkan (screenshot profil emiten saham) dan ekstrak HANYA ke dalam format JSON murni.

Struktur JSON yang WAJIB kamu hasilkan:
{
  "ticker": "BBCA",
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
    {"nama": "PT DWIMURIA...", "saham": "67.73 B", "persentase": "54.94%"}
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
  ]

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
  ]
}


ATURAN:
1. Pisahkan pemegang saham >1% dan 100% jika ada datanya.
2. Untuk Direksi/Komisaris, lihat tag [K] untuk Komisaris dan [D] untuk Direksi.
3. Untuk Insider, tangkap jenis action (Buy/Sell/Cross/Transfer/Corp Action), sumber (IDX/KSEI), dan arah panah (jika Buy/naik beri tanda +, jika Sell/turun beri tanda - pada amount_pct).
4. HANYA KEMBALIKAN JSON MURNI. JIKA DATA TIDAK ADA DI GAMBAR, ISI DENGAN NULL ATAU ARRAY KOSONG [].
"""

st.title("🤖 ElevenTen Capital - Smart Admin Panel")
st.info(f"Sistem menggunakan model: **{model_name}**")

uploaded_files = st.file_uploader("Upload SEMUA Screenshot Profil Saham", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files:
    images = [Image.open(f) for f in uploaded_files]
    st.image(images, width=150)

    if st.button("✨ Ekstrak Seluruh Data (Termasuk Pemegang Saham)", type="primary"):
        with st.spinner('AI sedang menganalisis seluruh struktur data...'):
            try:
                response = model.generate_content([PROMPT_INSTRUCTION] + images)
                raw_text = response.text.replace("```json", "").replace("```", "").strip()
                st.session_state['extracted_data'] = json.loads(raw_text)
                st.success("✅ AI berhasil memetakan struktur data yang kompleks!")
            except Exception as e:
                st.error(f"❌ Kesalahan: {e}")

if 'extracted_data' in st.session_state:
    data = st.session_state['extracted_data']
    st.markdown("### 📋 Preview JSON Data Kompleks (Bisa Diedit Manual)")
    
    with st.form("validation_form"):
        # Menampilkan data JSON utuh agar CEO bisa mengubah/memvalidasi array-nya langsung
        edited_json_str = st.text_area("JSON Data (Validasi Struktur Array di Sini)", value=json.dumps(data, indent=4), height=500)
        
        if st.form_submit_button("💾 Simpan Permanen ke Supabase"):
            try:
                final_payload = json.loads(edited_json_str)
                ticker = final_payload.get("ticker", "").upper()
                if not ticker:
                    st.error("Ticker kosong!")
                else:
                    with st.spinner("Menyimpan ke Supabase..."):
                        supabase.table("company_profiles").upsert(final_payload).execute()
                        st.success(f"🚀 BOOM! Data {ticker} beserta struktur pemegang sahamnya berhasil masuk ke Supabase!")
                        del st.session_state['extracted_data']
            except Exception as e:
                st.error(f"❌ Gagal menyimpan: {e}")
