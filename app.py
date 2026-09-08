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

# --- MASUKIN 1 ID GOOGLE SHEETS LU DI SINI ---
SPREADSHEET_ID = '1s-_CVIJuccM_IEjIMfJU8lUV9s0TTWkS-pli5Aa3ciw' 

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
    
    if st.button("Ganti User"):
        st.session_state.nama_sales = None
        st.rerun()
        
    st.markdown("---")
    
    try:
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # Tarik data dari Tab Master (Misal: MASTER_SENA)
        ws_master = sh.worksheet(f"MASTER_{st.session_state.nama_sales}") 
        data_master = ws_master.get_all_records()
        df_master = pd.DataFrame(data_master)
        
        list_customer = df_master['CUSTOMER NAME'].dropna().unique().tolist()
        
    except Exception as e:
        st.error(f"Gagal narik data master: Pastikan tab 'MASTER_{st.session_state.nama_sales}' ada di Spreadsheet. Error: {e}")
        st.stop()

    with st.form("form_kunjungan"):
        selected_customer = st.selectbox("Pilih Customer", list_customer)
        tanggal_kunjungan = st.date_input("Tanggal Kunjungan", date.today())
        
        # Ambil data baris pertama dari customer yang dipilih untuk auto-fill
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
                # Masukkan data hasil submit ke Tab tujuan (Misal: Tab 'SENA' di spreadsheet yang sama)
                ws_target = sh.worksheet(st.session_state.nama_sales)
                
                data_to_insert = [
                    "", 
                    str(tanggal_kunjungan), 
                    st.session_state.nama_sales, 
                    selected_customer,
                    str(cust_data.get('PIC CUSTOMER NAME', '')), 
                    str(cust_data.get('ADDRESS', '')),
                    str(cust_data.get('PHONE NUMBER', '')), 
                    str(cust_data.get('SEGMENTASI', '')),
                    str(cust_data.get('SOURCE', '')), 
                    str(cust_data.get('CUSTOMER TYPE', '')),
                    str(cust_data.get('BUSINESS TYPE', '')), 
                    str(cust_data.get('PRODUK TYPE', '')),
                    str(cust_data.get('PRODUCT DETAIL', '')), 
                    str(cust_data.get('CUSTOMER NEEDS', '')),
                    str(cust_data.get('FORECAST REVENUE', '')), 
                    str(cust_data.get('FORECAST SHIPMENT', '')),
                    sales_stage, 
                    progress, 
                    timeline, 
                    remarks
                ]
                
                ws_target.append_row(data_to_insert)
                st.success(f"Mantap bro! Data kunjungan {selected_customer} berhasil kesimpen di tab {st.session_state.nama_sales}.")
            except Exception as e:
                st.error(f"Gagal submit bro: {e}")
