import streamlit as st
import pandas as pd
import gspread
from datetime import date
import time

st.set_page_config(page_title="Automasi Pipeline Corporate", layout="centered")

# --- KONFIGURASI SPREADSHEET ---
MASTER_SPREADSHEET_ID = '1s-_CVIJuccM_IEjIMfJU8lUV9s0TTWkS-pli5Aa3ciw'
TARGET_SPREADSHEET_ID = '1MlUmZewvwA97thP7TBAMO1LZFaHqg6wzP6CEIWi4xx4'

# =====================================================================
# BUG FIX #5: Wrap koneksi gspread di try-except + retry
# =====================================================================
@st.cache_resource
def get_gsheets_connection():
    """Koneksi gspread dengan retry, biar aman pas app baru bangun dari sleep."""
    last_err = None
    for attempt in range(3):
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(creds_dict)
            return gc
        except Exception as e:
            last_err = e
            time.sleep(1)
    raise RuntimeError(
        f"Gagal konek ke Google Sheets setelah 3x percobaan. "
        f"Error: {type(last_err).__name__} - {last_err}"
    )


# =====================================================================
# BUG FIX #1 & #4: Cache master data, header konsisten
# =====================================================================
@st.cache_data(ttl=300)
def load_master_data(nama_sales):
    gc = get_gsheets_connection()
    sh = gc.open_by_key(MASTER_SPREADSHEET_ID)
    ws_master = sh.worksheet(f"MASTER_{nama_sales}")
    data_master = ws_master.get_all_records()
    return pd.DataFrame(data_master)


# =====================================================================
# BUG FIX #1 & #2 & #3: Logic cari baris kosong & nulis — DIPISAH
# =====================================================================
def cari_baris_kosong(ws_target):
    """
    Cari baris kosong pertama di sheet target.
    - Skip baris 1 (judul) & baris 2 (header) → mulai cek dari index 2 (baris 3)
    - Baris dianggap kosong kalau SEMUA cell-nya kosong (full-row check)
    - Fallback: kalau kolom C kosong, tetep dianggap kandidat baris kosong
    """
    semua_baris = ws_target.get_all_values()
    baris_tujuan = len(semua_baris) + 1  # default: append di paling bawah

    for i, baris in enumerate(semua_baris):
        if i < 2:  # skip baris 1 (judul) & baris 2 (header)
            continue

        # Full-row check: semua cell kosong?
        if all(str(cell).strip() == "" for cell in baris):
            baris_tujuan = i + 1
            break

        # Fallback: kolom C (index 2) kosong → anggap baris kosong
        if len(baris) < 3 or str(baris[2]).strip() == "":
            baris_tujuan = i + 1
            break

    return baris_tujuan


def susun_row(header_row, data_map):
    """
    Susun baris sesuai urutan header asli.
    Return: (row_to_insert, kolom_tidak_dikenali)
    """
    row_to_insert = []
    kolom_tidak_dikenali = []

    for header in header_row:
        h = header.strip().upper()
        if h in data_map:
            row_to_insert.append(data_map[h])
        elif h == "NO":
            row_to_insert.append("")  # auto-number di sheet
        else:
            row_to_insert.append("")
            kolom_tidak_dikenali.append(header)

    return row_to_insert, kolom_tidak_dikenali


# =====================================================================
# BUG FIX #26: Cek duplikat kunjungan hari ini
# =====================================================================
def cek_duplikat_hari_ini(ws_target, customer_name, tanggal):
    """
    Cek apakah customer ini udah dikunjungi hari ini.
    Return: (is_duplikat, baris_ke)
    """
    semua_baris = ws_target.get_all_values()
    tanggal_str = str(tanggal)

    for i, baris in enumerate(semua_baris):
        if i < 2:
            continue
        if len(baris) < 3:
            continue

        # Asumsi: kolom A = DATE, kolom C = CUSTOMER NAME
        tgl_baris = str(baris[0]).strip() if len(baris) > 0 else ""
        cust_baris = str(baris[2]).strip() if len(baris) > 2 else ""

        if tgl_baris == tanggal_str and cust_baris == customer_name:
            return True, i + 1

    return False, None


# =====================================================================
# SESSION STATE
# =====================================================================
if 'nama_sales' not in st.session_state:
    st.session_state.nama_sales = None

# =====================================================================
# HALAMAN LOGIN
# =====================================================================
if st.session_state.nama_sales is None:
    st.title("Login Pipeline Corporate")
    pilihan_nama = st.selectbox(
        "Pilih Nama Lu:",
        ["", "SENA", "ANGGA", "WAWAY", "RAYHAN", "JASMINE", "FAUZAN"]
    )

    if st.button("Masuk"):
        if pilihan_nama != "":
            st.session_state.nama_sales = pilihan_nama
            st.rerun()
        else:
            st.warning("Pilih nama lu dulu bro!")

# =====================================================================
# HALAMAN UTAMA
# =====================================================================
else:
    # UX #24: Layout mobile-friendly — pakai kolom yang lebih fleksibel
    st.title(f"Form Kunjungan - {st.session_state.nama_sales}")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Ganti User", use_container_width=True):
            st.session_state.nama_sales = None
            st.rerun()
    with col2:
        if st.button("Refresh Data Master", use_container_width=True):
            load_master_data.clear()
            st.toast("✅ Data master di-refresh!", icon="🔄")  # UX #10
            st.rerun()

    st.markdown("---")

    # --- Load data master ---
    try:
        df_master = load_master_data(st.session_state.nama_sales)
        list_customer = df_master['CUSTOMER NAME'].dropna().unique().tolist()
    except Exception as e:
        st.error(
            f"Gagal narik data master: Pastikan tab "
            f"'MASTER_{st.session_state.nama_sales}' ada di Spreadsheet. "
            f"Error: {type(e).__name__} - {e}"  # UX #11
        )
        st.stop()

    if not list_customer:
        st.warning(
            f"Belum ada customer di tab master lo. "
            f"Isi dulu tab MASTER_{st.session_state.nama_sales}"
        )
        st.stop()

    # =================================================================
    # FORM KUNJUNGAN
    # =================================================================
    with st.form("form_kunjungan"):
        # UX #13: Selectbox dengan placeholder + search
        selected_customer = st.selectbox(
            "Pilih Customer",
            list_customer,
            index=None,
            placeholder="Ketik nama customer untuk cari...",
        )

        # UX #6: Tanggal bisa diubah, default hari ini
        tanggal_kunjungan = st.date_input(
            "Tanggal Kunjungan",
            value=date.today(),
            help="Default hari ini. Bisa diubah kalau input kunjungan kemarin."
        )

        # Info customer (kalau udah dipilih)
        if selected_customer:
            cust_data = df_master[df_master['CUSTOMER NAME'] == selected_customer].iloc[0]
            st.info(
                f"**PIC:** {cust_data.get('PIC CUSTOMER NAME', '-')} | "
                f"**No HP:** {cust_data.get('PHONE NUMBER', '-')} | "
                f"**Segmentasi:** {cust_data.get('SEGMENTASI', '-')}"
            )
        else:
            cust_data = None

        st.subheader("Update Progres")
        sales_stage = st.selectbox(
            "Sales Stage",
            ["Maintenance", "1st Meeting", "Proposal", "Gain Commitment", "Closing"]
        )
        progress = st.text_area("Progress / Hasil Meeting")
        timeline = st.text_input("Time Line (Opsional)")
        remarks = st.text_area("Remarks / Kendala (Opsional)")

        submit = st.form_submit_button("Submit Data", use_container_width=True)

    # =================================================================
    # PROSES SUBMIT (di luar form)
    # =================================================================
    if submit:
        # UX #7-ish: Validasi wajib isi
        if not selected_customer:
            st.error("Pilih customer dulu bro!")
            st.stop()
        if not progress.strip():
            st.error("Progress / Hasil Meeting wajib diisi!")
            st.stop()

        try:
            gc = get_gsheets_connection()
            ws_target = gc.open_by_key(TARGET_SPREADSHEET_ID).worksheet(
                st.session_state.nama_sales
            )

            header_row = ws_target.row_values(2)

            data_map = {
                "DATE": str(tanggal_kunjungan),
                "AE NAME": st.session_state.nama_sales,
                "CUSTOMER NAME": selected_customer,
                "PIC CUSTOMER NAME": str(cust_data.get('PIC CUSTOMER NAME', '')),
                "ADDRESS": str(cust_data.get('ADDRESS', '')),
                "PHONE NUMBER": str(cust_data.get('PHONE NUMBER', '')),
                "SEGMENTASI": str(cust_data.get('SEGMENTASI', '')),
                "SOURCE": str(cust_data.get('SOURCE', '')),
                "CUSTOMER TYPE": str(cust_data.get('CUSTOMER TYPE', '')),
                "BUSINESS TYPE": str(cust_data.get('BUSINESS TYPE', '')),
                "PRODUK TYPE": str(cust_data.get('PRODUK TYPE', '')),
                "PRODUCT DETAIL": str(cust_data.get('PRODUCT DETAIL', '')),
                "CUSTOMER NEEDS": str(cust_data.get('CUSTOMER NEEDS', '')),
                "FORECAST REVENUE": str(cust_data.get('FORECAST REVENUE', '')),
                "FORECAST SHIPMENT": str(cust_data.get('FORECAST SHIPMENT', '')),
                "SALES STAGE": sales_stage,
                "PROGRESS": progress,
                "TIME LINE": timeline,
                "REMARKS": remarks,
            }

            # BUG FIX #1: Susun row di LUAR loop fetch/update
            row_to_insert, kolom_tidak_dikenali = susun_row(header_row, data_map)

            # BUG FIX #26: Cek duplikat hari ini
            is_dup, baris_dup = cek_duplikat_hari_ini(
                ws_target, selected_customer, tanggal_kunjungan
            )

            if is_dup:
                st.warning(
                    f"⚠️ Customer **{selected_customer}** udah dikunjungi hari ini "
                    f"(di baris {baris_dup}). Data tetep disimpan sebagai kunjungan baru."
                )

            # BUG FIX #2 & #3: Cari baris kosong dengan full-row check
            baris_tujuan = cari_baris_kosong(ws_target)

            # BUG FIX #1: Update SEKALI aja di luar loop
            ws_target.update(
                range_name=f"A{baris_tujuan}",
                values=[row_to_insert]
            )

            # UX #8: Feedback baris berapa
            st.success(
                f"✅ Data kunjungan **{selected_customer}** berhasil disimpen "
                f"di tab **{st.session_state.nama_sales}** baris **{baris_tujuan}**."
            )

            if kolom_tidak_dikenali:
                st.warning(
                    f"⚠️ Ada kolom di sheet yang belum ke-mapping (dikosongin): "
                    f"{kolom_tidak_dikenali}. Cek nama header-nya."
                )

            # UX #9: Preview data yang barusan disubmit
            with st.expander("📋 Lihat data yang barusan disimpan", expanded=False):
                preview_df = pd.DataFrame([{
                    "Tanggal": str(tanggal_kunjungan),
                    "AE Name": st.session_state.nama_sales,
                    "Customer": selected_customer,
                    "Sales Stage": sales_stage,
                    "Progress": progress,
                    "Timeline": timeline or "-",
                    "Remarks": remarks or "-",
                }])
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Gagal submit bro: {type(e).__name__} - {e}")
