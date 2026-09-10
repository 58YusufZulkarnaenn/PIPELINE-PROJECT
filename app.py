import streamlit as st
import pandas as pd
import gspread
from datetime import date

st.set_page_config(page_title="Automasi Pipeline Corporate", layout="centered")

@st.cache_resource
def get_gsheets_connection():
    creds_dict = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(creds_dict)
    return gc

gc = get_gsheets_connection()

# --- PISAHIN ID MASTER DAN TARGET ---
MASTER_SPREADSHEET_ID = '1s-_CVIJuccM_IEjIMfJU8lUV9s0TTWkS-pli5Aa3ciw' # Tempat load data master
TARGET_SPREADSHEET_ID = '1MlUmZewvwA97thP7TBAMO1LZFaHqg6wzP6CEIWi4xx4' # ID dari link lu barusan (tempat nulis)

# Cache data master 5 menit biar gak nge-query Google tiap reload,
# tapi tetep update kalau ada perubahan data.
@st.cache_data(ttl=300)
def load_master_data(nama_sales):
    sh = gc.open_by_key(MASTER_SPREADSHEET_ID) # <-- Pastiin pakai MASTER_SPREADSHEET_ID
    ws_master = sh.worksheet(f"MASTER_{nama_sales}")
    data_master = ws_master.get_all_records()
    return pd.DataFrame(data_master)


if 'nama_sales' not in st.session_state:
    st.session_state.nama_sales = None

if st.session_state.nama_sales is None:
    st.title("Login Pipeline Corporate")
    pilihan_nama = st.selectbox("Pilih Nama Lu:", ["", "SENA", "ANGGA", "WAWAY", "RAYHAN", "JASMINE", "FAUZAN"])

    if st.button("Masuk"):
        if pilihan_nama != "":
            st.session_state.nama_sales = pilihan_nama
            st.rerun()
        else:
            st.warning("Pilih nama lu dulu bro!")
else:
    st.title(f"Form Kunjungan - {st.session_state.nama_sales}")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Ganti User"):
            st.session_state.nama_sales = None
            st.rerun()
    with col2:
        if st.button("Refresh Data Master"):
            load_master_data.clear()
            st.rerun()

    st.markdown("---")

    try:
        df_master = load_master_data(st.session_state.nama_sales)
        list_customer = df_master['CUSTOMER NAME'].dropna().unique().tolist()
    except Exception as e:
        st.error(f"Gagal narik data master: Pastikan tab 'MASTER_{st.session_state.nama_sales}' ada di Spreadsheet. Error: {e}")
        st.stop()

    if not list_customer:
        st.warning("Belum ada customer di tab master lo. Isi dulu tab MASTER_" + st.session_state.nama_sales)
        st.stop()

    with st.form("form_kunjungan"):
        selected_customer = st.selectbox("Pilih Customer", list_customer)

        # Tanggal otomatis pakai hari ini, tinggal ditampilin (gak perlu input manual)
        tanggal_kunjungan = date.today()
        st.caption(f"Tanggal kunjungan: **{tanggal_kunjungan.strftime('%d-%m-%Y')}** (otomatis, tanggal hari ini)")

        cust_data = df_master[df_master['CUSTOMER NAME'] == selected_customer].iloc[0]

        st.info(f"**PIC:** {cust_data.get('PIC CUSTOMER NAME', '-')} | **No HP:** {cust_data.get('PHONE NUMBER', '-')} | **Segmentasi:** {cust_data.get('SEGMENTASI', '-')}")

        st.subheader("Update Progres")
        sales_stage = st.selectbox("Sales Stage", ["Maintenance", "1st Meeting", "Proposal", "Gain Commitment", "Closing"])
        progress = st.text_area("Progress / Hasil Meeting")
        timeline = st.text_input("Time Line (Opsional)")
        remarks = st.text_area("Remarks / Kendala (Opsional)")

        submit = st.form_submit_button("Submit Data")

        if submit:
            try:
                # V V V Ganti bagian ini nembak ke TARGET_SPREADSHEET_ID V V V
                ws_target = gc.open_by_key(TARGET_SPREADSHEET_ID).worksheet(st.session_state.nama_sales)

                # Ambil header ASLI dari baris pertama tab tujuan
                header_row = ws_target.row_values(2)

                # Data yang mau ditulis, dipetakan pakai NAMA KOLOM (bukan posisi urutan).
                # PENTING: sesuaikan "key" di kiri (nama kolom) ini dengan header
                # yang ADA PERSIS di tab SENA lo (huruf besar/kecil & spasi harus sama).
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

                # Susun baris SESUAI URUTAN HEADER ASLI di sheet.
                # Kalau ada header yang gak ke-mapping di data_map, otomatis dikosongin ("")
                # dan dikasih tau di warning, biar ketauan kalau ada nama kolom yg beda.
                row_to_insert = []
                kolom_tidak_dikenali = []
                for header in header_row:
                    header_bersih = header.strip().upper()
                    if header_bersih in data_map:
                        row_to_insert.append(data_map[header_bersih])
                    elif header_bersih == "NO":
                        row_to_insert.append("")  # biarin kosong / auto-number manual di sheet
                    else:
                        row_to_insert.append("")
                        kolom_tidak_dikenali.append(header)

                    # 1. Kita jadikan satu kolom sebagai "patokan" hitungan.
                    # col_values(3) artinya kita ngecek Kolom C (misal: kolom AE NAME atau CUSTOMER NAME).
                    # Fungsi ini pinter, dia cuma ngitung sel yang ada TULISANNYA aja, dropdown kosong nggak dihitung.
                    kolom_patokan = ws_target.col_values(3) 

                    # 2. Cari tau baris kosong selanjutnya (Jumlah baris yang ada isinya + 1)
                    baris_kosong_selanjutnya = len(kolom_patokan) + 1

                    # 3. Kita "timpa" (update) baris kosong tersebut pakai data baru.
                    # Penting: row_to_insert harus dikurung pakai kurung siku lagi [...] biar jadi list 2 dimensi.
                    ws_target.update(f"A{baris_kosong_selanjutnya}", [row_to_insert])

                st.success(f"Mantap bro! Data kunjungan {selected_customer} berhasil kesimpen di tab {st.session_state.nama_sales}.")
                if kolom_tidak_dikenali:
                    st.warning(f"Ada kolom di sheet yang belum ke-mapping (dikosongin): {kolom_tidak_dikenali}. Cek lagi nama header-nya, mungkin beda sama yang ada di data_map.")
            except Exception as e:
                st.error(f"Gagal submit bro: {e}")
