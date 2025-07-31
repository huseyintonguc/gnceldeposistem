import streamlit as st
import pandas as pd
import datetime
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase başlatma fonksiyonu
def initialize_firebase():
    # Streamlit secrets'tan 'firebase' bölümünü çek
    # st.secrets["firebase"] ifadesi, Streamlit Cloud'daki secrets.toml dosyasındaki
    # [firebase] başlığı altındaki tüm değerleri bir Python dictionary olarak okur.
    try:
        firebase_config = st.secrets["firebase"]
    except KeyError:
        st.error("Firebase secrets bulunamadı! Lütfen Streamlit Cloud'daki Secrets ayarlarınızı kontrol edin.")
        st.info("secrets.toml dosyanızda '[firebase]' başlığı altında Firebase hizmet hesabı bilgileri olmalı.")
        return None

    try:
        # Kimlik bilgilerini kullanarak Firebase'i başlat
        # credentials.Certificate doğrudan bir dosya yolu yerine,
        # dictionary formatındaki kimlik bilgilerini de kabul eder.
        cred = credentials.Certificate(firebase_config)
        
        # Eğer uygulama daha önce başlatılmamışsa başlat
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
            st.success("Firebase başarıyla başlatıldı!")
        else:
            st.warning("Firebase zaten başlatılmıştı, tekrar başlatılmadı.")
        
        return firestore.client() # Firestore istemcisini döndür
    except Exception as e:
        st.error(f"Firebase başlatılırken hata oluştu: {e}")
        st.info("Lütfen Streamlit Cloud'daki Secrets ayarlarınızı ve `urun.py` dosyanızı kontrol edin. Özellikle `private_key` formatını ve secrets.toml'daki `[firebase]` başlığını kontrol edin.")
        return None

# Uygulama başladı, Firebase bağlantısını kurmaya çalış
db = initialize_firebase()

if db:
    st.write("Veritabanı bağlantısı başarılı. Ürünleri listeleyebilir veya Firebase Firestore işlemlerini entegre edebilirsiniz.")
    # BURADA GEREKİRSE Firebase Firestore ile ilgili işlemlerinizi yapabilirsiniz.
    # Örneğin, eğer ürünleri ve depo giriş/çıkışlarını Firestore'da tutmak isterseniz,
    # aşağıdaki load_products ve load_warehouse_entries fonksiyonlarını Firebase'den okuyacak
    # şekilde değiştirebilirsiniz. Şimdilik mevcut CSV tabanlı mantık devam edecektir.
    pass
else:
    st.error("Veritabanı bağlantısı kurulamadı. Lütfen Firebase secret'larını ve kodunuzu kontrol edin.")


# --- Veri Dosyaları Yolları ---
PRODUCTS_FILE = 'products.csv'
WAREHOUSE_ENTRIES_FILE = 'warehouse_entries.csv'

# --- Ürün Listesini Yükle ---
@st.cache_data(ttl=3600) # Ürünler genellikle sık değişmez, 1 saat önbellekte kalabilir
def load_products():
    """
    products.csv dosyasını yükler. 
    Dosya yoksa boş bir DataFrame oluşturur ve başlıkları belirler.
    Kodlama ve ayraç hatalarını ele almak için çeşitli denemeler yapar.
    NOT: Ayraç olarak noktalı virgül (;) kullanıldığını varsayar.
    """
    if os.path.exists(PRODUCTS_FILE):
        df = pd.DataFrame() 
        
        encodings = ['utf-8', 'windows-1254', 'latin-1']
        separator = ';' 

        loaded_successfully = False
        
        for enc in encodings:
            try:
                df = pd.read_csv(PRODUCTS_FILE, encoding=enc, sep=separator)
                # Sütun isimlerini normalize et ve kontrol et
                original_columns = list(df.columns)
                normalized_columns = [col.strip().lower() for col in original_columns]

                sku_col_name = None
                urun_adi_col_name = None

                sku_variations = ['sku', 'urun kodu', 'ürün kodu']
                urun_adi_variations = ['urun adi', 'ürün adı', 'urunismi', 'ürün ismi', 'product name']

                for i, norm_col in enumerate(normalized_columns):
                    if sku_col_name is None and norm_col in sku_variations:
                        sku_col_name = original_columns[i]
                    if urun_adi_col_name is None and norm_col in urun_adi_variations:
                        urun_adi_col_name = original_columns[i]
                    
                    if sku_col_name and urun_adi_col_name:
                        break

                if not sku_col_name or not urun_adi_col_name:
                    st.sidebar.error(f"'{PRODUCTS_FILE}' dosyasında 'SKU' ve 'Urun Adi' (veya benzeri) sütunları bulunamadı. Tespit edilen sütunlar: {original_columns}.")
                    return pd.DataFrame(columns=['SKU', 'Urun Adi']) 

                df = df[[sku_col_name, urun_adi_col_name]] 
                df.columns = ['SKU', 'Urun Adi'] 
                
                st.sidebar.success(f"'{PRODUCTS_FILE}' dosyası '{enc}' kodlaması ve '{separator}' ayraçla yüklendi.")
                loaded_successfully = True
                break 
            except UnicodeDecodeError:
                continue 
            except pd.errors.ParserError as e:
                st.sidebar.warning(f"'{PRODUCTS_FILE}' dosyası '{enc}' kodlaması ve '{separator}' ayraçla ayrıştırılamadı. Hata: {e}")
                continue 
            except Exception as e:
                st.sidebar.error(f"'{PRODUCTS_FILE}' dosyası okunurken beklenmedik bir hata oluştu: {e}.")
                return pd.DataFrame(columns=['SKU', 'Urun Adi'])

        if not loaded_successfully:
            st.error(f"'{PRODUCTS_FILE}' dosyası hiçbir bilinen kodlama veya ayraçla okunamadı. Lütfen dosyanın formatını kontrol edin.")
            return pd.DataFrame(columns=['SKU', 'Urun Adi'])
        
        # Eğer dosya yüklendi ama boşsa (sadece başlıklar varsa), boş bir DataFrame döndür
        if df.empty:
            st.warning(f"'{PRODUCTS_FILE}' dosyası boş görünüyor. Lütfen ürün bilgisi girin.")
            return pd.DataFrame(columns=['SKU', 'Urun Adi'])

        return df
    else:
        # Dosya yoksa, boş bir DataFrame oluştur ve kullanıcıya bilgi ver
        st.info(f"'{PRODUCTS_FILE}' dosyası bulunamadı. Yeni ürünler ekleyerek başlayabilirsiniz.")
        return pd.DataFrame(columns=['SKU', 'Urun Adi'])

def save_products(df):
    """Ürün DataFrame'ini CSV dosyasına kaydeder."""
    try:
        # Boş DataFrame kaydetmemek için kontrol (dosyayı boşaltmayı engeller)
        if df.empty and os.path.exists(PRODUCTS_FILE):
            st.warning("Kaydedilecek ürün bulunamadı. Mevcut ürün dosyası boşaltılmadı.")
            return False # Kaydetme işlemi yapılmadı
        
        df.to_csv(PRODUCTS_FILE, index=False, encoding='utf-8', header=True)
        return True
    except Exception as e:
        st.error(f"Ürünler kaydedilirken bir hata oluştu: {e}")
        return False

# --- Depo Giriş/Çıkışlarını Yükle ve Kaydet ---
@st.cache_data(ttl=1) 
def load_warehouse_entries():
    """
    warehouse_entries.csv dosyasını yükler. 
    Dosya yoksa veya boşsa boş bir DataFrame oluşturur ve başlıkları belirler.
    """
    if os.path.exists(WAREHOUSE_ENTRIES_FILE):
        try:
            df = pd.read_csv(WAREHOUSE_ENTRIES_FILE, encoding='utf-8')
            if 'Tarih' in df.columns:
                df['Tarih'] = pd.to_datetime(df['Tarih']).dt.date
            # Yeni sütun 'Islem Tipi' yoksa ekle ve varsayılan değer ata (eski kayıtlar için 'Giriş')
            if 'Islem Tipi' not in df.columns:
                df['Islem Tipi'] = 'Giriş'
            return df
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(WAREHOUSE_ENTRIES_FILE, encoding='windows-1254')
                st.sidebar.warning(f"'{WAREHOUSE_ENTRIES_FILE}' dosyası UTF-8 olarak okunamadı, 'windows-1254' ile yüklendi.")
                if 'Tarih' in df.columns:
                    df['Tarih'] = pd.to_datetime(df['Tarih']).dt.date
                if 'Islem Tipi' not in df.columns:
                    df['Islem Tipi'] = 'Giriş'
                return df
            except pd.errors.EmptyDataError:
                st.warning(f"'{WAREHOUSE_ENTRIES_FILE}' dosyası boş. Yeni girişler beklenecek.")
                # Boş dosya durumunda bile doğru sütunları içeren bir DataFrame döndür
                return pd.DataFrame(columns=['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi'])
            except Exception as e:
                st.error(f"'{WAREHOUSE_ENTRIES_FILE}' dosyası okunurken beklenmedik bir hata oluştu (windows-1254): {e}.")
                return pd.DataFrame(columns=['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi'])
        except pd.errors.EmptyDataError:
            st.warning(f"'{WAREHOUSE_ENTRIES_FILE}' dosyası boş. Yeni girişler beklenecek.")
            # Boş dosya durumunda bile doğru sütunları içeren bir DataFrame döndür
            return pd.DataFrame(columns=['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi'])
        except Exception as e:
            st.error(f"'{WAREHOUSE_ENTRIES_FILE}' dosyası okunurken beklenmedik bir hata oluştu: {e}.")
            return pd.DataFrame(columns=['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi'])
    else:
        # Dosya yoksa, yeni bir DataFrame oluştururken 'Islem Tipi' sütununu da ekle
        st.info(f"'{WAREHOUSE_ENTRIES_FILE}' dosyası bulunamadı. İlk girişinizi yaparak oluşturabilirsiniz.")
        return pd.DataFrame(columns=['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi'])

def save_warehouse_entry(entry_df):
    """Depo giriş/çıkış DataFrame'ini CSV dosyasına kaydeder."""
    try:
        # Tarih sütununu string olarak kaydetmek için ISO formatına çevir
        if 'Tarih' in entry_df.columns:
            entry_df['Tarih'] = entry_df['Tarih'].apply(lambda x: x.isoformat() if isinstance(x, (datetime.date, datetime.datetime)) else x)

        # Eğer DataFrame boşsa ve dosya zaten varsa, dosyayı silmeyelim
        if entry_df.empty and os.path.exists(WAREHOUSE_ENTRIES_FILE):
            st.warning("Kaydedilecek depo işlemi bulunamadı. Mevcut depo dosyası boşaltılmadı.")
            return False
        
        entry_df.to_csv(WAREHOUSE_ENTRIES_FILE, index=False, encoding='utf-8', header=True)
        return True 
    except Exception as e:
        st.error(f"Depo girişi/çıkışı kaydedilirken bir hata oluştu: {e}")
        return False 

# --- Uygulama Başlığı ---
st.set_page_config(layout="centered", page_title="Depo Giriş/Çıkış Kayıt Sistemi")
st.title("📦 Depo Giriş/Çıkış Kayıt Sistemi")
st.markdown("Gün içinde depoya alınan ve depodan çıkan ürünleri buraya kaydedin.")

# --- Session State Başlatma ---
if 'products_df' not in st.session_state:
    st.session_state['products_df'] = load_products()

# warehouse_entries_df için başlangıçta kontrol ve yükleme
if 'warehouse_entries_df' not in st.session_state or st.session_state['warehouse_entries_df'] is None:
     st.session_state['warehouse_entries_df'] = load_warehouse_entries()

products_df = st.session_state['products_df']
warehouse_entries_df = st.session_state['warehouse_entries_df']


# --- Yeni Ürün Ekleme Bölümü ---
st.markdown("---")
st.subheader("➕ Yeni Ürün Ekle")
new_product_sku = st.text_input("Yeni Ürün SKU'su", key="new_sku_input").strip()
new_product_name = st.text_input("Yeni Ürün Adı", key="new_product_name_input").strip()

if st.button("Yeni Ürünü Kaydet"):
    if new_product_sku and new_product_name:
        # SKU'nun benzersizliğini kontrol et
        if not products_df.empty and new_product_sku in products_df['SKU'].values:
            st.warning(f"SKU '{new_product_sku}' zaten mevcut. Lütfen farklı bir SKU girin.")
        else:
            new_product_data = pd.DataFrame([{
                'SKU': new_product_sku,
                'Urun Adi': new_product_name
            }])
            
            # DataFrame boşsa doğrudan ata, değilse birleştir
            if products_df.empty:
                st.session_state['products_df'] = new_product_data
            else:
                st.session_state['products_df'] = pd.concat([products_df, new_product_data], ignore_index=True)
            
            if save_products(st.session_state['products_df']):
                st.success(f"Yeni ürün **{new_product_name}** (SKU: **{new_product_sku}**) başarıyla eklendi!")
                load_products.clear() # Ürün önbelleğini temizle
                st.session_state['products_df'] = load_products() # Güncel veriyi yeniden yükle
                st.rerun() # Sayfayı yeniden yükle
            else:
                st.error("Yeni ürün kaydedilirken bir sorun oluştu.")
    else:
        st.warning("Lütfen hem SKU hem de Ürün Adı girin.")

st.markdown("---") # Yeni ürün ekleme alanı ile ürün arama arasına ayırıcı

# Eğer ürün listesi boşsa uyarı ver
if products_df.empty:
    st.warning("Ürün listesi boş veya yüklenemedi. Lütfen 'products.csv' dosyasını kontrol edin veya yukarıdan yeni ürün ekleyin.")
else:
    # --- Ürün Arama ve Seçme ---
    st.subheader("Ürün Bilgileri")

    search_query = st.text_input("Ürün Adı veya SKU ile Ara", key="search_input_val").strip() 

    filtered_products = products_df.copy()
    if 'Urun Adi' in filtered_products.columns and 'SKU' in filtered_products.columns:
        if search_query: 
            filtered_products = products_df[
                products_df['Urun Adi'].str.contains(search_query, case=False, na=False) |
                products_df['SKU'].str.contains(search_query, case=False, na=False) 
            ]
            if filtered_products.empty:
                st.info("Aradığınız ürün bulunamadı.")
    else:
        st.warning("Ürün arama ve filtreleme yapılamıyor: 'Urun Adi' veya 'SKU' sütunları bulunamadı.")
        filtered_products = pd.DataFrame(columns=['SKU', 'Urun Adi']) 

    product_options = [f"{row['SKU']} - {row['Urun Adi']}" for index, row in filtered_products.iterrows()]
    
    selected_product_display = st.selectbox(
        "Ürün Seçin",
        options=['Seçiniz...'] + product_options,
        key="product_select_val" 
    )

    selected_sku = None
    selected_product_name = None

    if selected_product_display != 'Seçiniz...':
        parts = selected_product_display.split(' - ', 1) 
        selected_sku = parts[0]
        selected_product_name = parts[1] if len(parts) > 1 else "" 
        st.info(f"Seçilen Ürün: **{selected_product_name}** (SKU: **{selected_sku}**)")

    # --- İşlem Tipi ve Adet Girişi ---
    st.subheader("İşlem Detayları")

    # İşlem tipi seçimi
    transaction_type = st.radio(
        "İşlem Tipi",
        ('Giriş', 'Çıkış'),
        key="transaction_type_val"
    )

    # Adet giriş alanının metnini işlem tipine göre değiştir
    quantity_label = "Alınan Adet" if transaction_type == 'Giriş' else "Verilen Adet"
    
    quantity_default = st.session_state.get("quantity_input_val", 1) 
    quantity = st.number_input(quantity_label, min_value=1, value=quantity_default, step=1, key="quantity_input_val")

    # --- Tarih Seçimi (Varsayılan Bugün) ---
    entry_date = st.date_input("Tarih", value=datetime.date.today(), key="date_input_val")

    # --- Kaydet Butonu ---
    if st.button("Kaydet"):
        if selected_sku and quantity > 0:
            new_entry = pd.DataFrame([{
                'Tarih': entry_date.isoformat(), 
                'SKU': selected_sku,
                'Urun Adi': selected_product_name,
                'Adet': quantity,
                'Islem Tipi': transaction_type # Yeni sütun eklendi
            }])
            
            if warehouse_entries_df.empty:
                updated_df_to_save = new_entry
            else:
                updated_df_to_save = pd.concat([warehouse_entries_df, new_entry], ignore_index=True)
            
            if save_warehouse_entry(updated_df_to_save): 
                st.success(f"**{quantity}** adet **{selected_product_name}** ({selected_sku}) **{entry_date.strftime('%d.%m.%Y')}** tarihinde **{transaction_type}** olarak kaydedildi!")
                
                # Önbelleği temizle
                load_warehouse_entries.clear()
                
                # Session State'teki veriyi, diskten yeniden yükleyerek güncelle
                st.session_state['warehouse_entries_df'] = load_warehouse_entries()
                
                # Sayfayı yeniden yükleyerek tüm inputları resetle ve güncel listeyi göster
                st.rerun() 
            
        else:
            st.warning("Lütfen bir ürün seçin ve geçerli bir adet girin.")

    st.markdown("---")
    st.subheader("Son Depo İşlemleri")
    if not warehouse_entries_df.empty:
        # 'Islem Tipi' sütununu da göster
        st.dataframe(warehouse_entries_df[['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi']].sort_values(by='Tarih', ascending=False).head(10))
    else:
        st.info("Henüz hiç depo işlemi yapılmadı.")

    st.markdown("---")
    st.subheader("Tüm Depo İşlemleri")
    if not warehouse_entries_df.empty:
        
        st.dataframe(warehouse_entries_df[['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi']], use_container_width=True)

        st.markdown("---")
        st.subheader("Kayıt Silme Alanı")
        
        # Her satır için ayrı bir "Sil" butonu oluşturma
        if not warehouse_entries_df.empty:
            for i in range(len(warehouse_entries_df)):
                row = warehouse_entries_df.iloc[i]
                
                # Her buton için benzersiz bir key sağlamak önemli
                # Burada Tarih ve SKU'yu kullanarak daha benzersiz bir anahtar oluşturuyoruz
                unique_key = f"delete_button_{i}_{row['SKU']}_{row['Tarih']}_{row['Adet']}_{row['Islem Tipi']}" 
                
                # Butonun yanına silinecek kaydın özetini gösterelim
                display_text = f"{row['Tarih'].strftime('%d.%m.%Y')} - {row['Urun Adi']} ({row['SKU']}) - {row['Adet']} {row['Islem Tipi']}"
                
                col_text, col_button = st.columns([0.8, 0.2])
                with col_text:
                    st.write(display_text)
                with col_button:
                    if st.button(f"Sil", key=unique_key):
                        # Satırı silme işlemi
                        st.session_state['warehouse_entries_df'] = st.session_state['warehouse_entries_df'].drop(row.name).reset_index(drop=True)
                        if save_warehouse_entry(st.session_state['warehouse_entries_df']):
                            st.success(f"Kayıt başarıyla silindi: {display_text}")
                            load_warehouse_entries.clear() # Önbelleği temizle
                            st.session_state['warehouse_entries_df'] = load_warehouse_entries() # Güncel veriyi yükle
                            st.rerun() # Sayfayı yeniden yükle
        else:
            st.info("Silinecek bir depo işlemi bulunmamaktadır.")


        st.markdown("---") # Silme alanı ile indirme butonu arasına ayırıcı
        df_for_download = warehouse_entries_df.copy()
        if 'Tarih' in df_for_download.columns:
            df_for_download['Tarih'] = df_for_download['Tarih'].apply(lambda x: x.isoformat() if isinstance(x, datetime.date) else x)

        st.download_button(
            label="Tüm Depo İşlemlerini İndir (CSV)",
            data=df_for_download.to_csv(index=False, encoding='utf-8').encode('utf-8'),
            file_name="tum_depo_islemleri.csv",
            mime="text/csv",
        )
    else:
        st.info("Depo işlemleri henüz boş.")

    st.markdown("---")
    st.subheader("Raporlama ve Özet")

    if not warehouse_entries_df.empty:
        # --- Tarih Aralığı Filtreleri ---
        col_start_date, col_end_date = st.columns(2)
        with col_start_date:
            start_date = st.date_input("Başlangıç Tarihi", value=warehouse_entries_df['Tarih'].min() if not warehouse_entries_df.empty else datetime.date.today(), key="report_start_date")
        with col_end_date:
            end_date = st.date_input("Bitiş Tarihi", value=warehouse_entries_df['Tarih'].max() if not warehouse_entries_df.empty else datetime.date.today(), key="report_end_date")

        # Tarih filtrelemesi yap
        filtered_by_date_df = warehouse_entries_df[
            (warehouse_entries_df['Tarih'] >= start_date) & 
            (warehouse_entries_df['Tarih'] <= end_date)
        ].copy()

        if start_date > end_date:
            st.warning("Başlangıç tarihi bitiş tarihinden sonra olamaz. Lütfen tarihleri kontrol edin.")
            filtered_by_date_df = pd.DataFrame(columns=warehouse_entries_df.columns) # Hatalı durumda boş DataFrame göster

        # --- Genel Toplam Giriş/Çıkış Özeti (Tarih Filtresi Uygulanmış) ---
        st.markdown("---")
        st.subheader(f"Seçili Tarih Aralığı ({start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}) Özeti")

        if not filtered_by_date_df.empty:
            total_giris_filtered = filtered_by_date_df[filtered_by_date_df['Islem Tipi'] == 'Giriş']['Adet'].sum()
            total_cikis_filtered = filtered_by_date_df[filtered_by_date_df['Islem Tipi'] == 'Çıkış']['Adet'].sum()

            st.markdown(f"**Toplam Giriş:** {total_giris_filtered} adet")
            st.markdown(f"**Toplam Çıkış:** {total_cikis_filtered} adet")
            st.markdown(f"**Net Stok Değişimi:** {total_giris_filtered - total_cikis_filtered} adet")
        else:
            st.info("Seçilen tarih aralığında bir işlem bulunmamaktadır.")
        
        st.markdown("---")

        # --- Ürüne Göre Filtreleme ve Özet (Tarih Filtresi Uygulanmış) ---
        st.subheader("Ürüne Göre Raporlama (Seçili Tarih Aralığında)")
        
        # Ürün seçenekleri, "Tüm Ürünler" seçeneği ile birlikte
        # Sadece bu tarih aralığındaki işlemlerde geçen ürünleri gösterelim
        products_in_filtered_range = filtered_by_date_df['SKU'].unique()
        product_filter_options_in_range = ['Tüm Ürünler'] + sorted([
            f"{row['SKU']} - {row['Urun Adi']}" 
            for index, row in products_df[products_df['SKU'].isin(products_in_filtered_range)].iterrows()
        ])
        
        selected_product_for_report = st.selectbox(
            "Raporlanacak Ürünü Seçin",
            options=product_filter_options_in_range,
            key="product_report_select_val"
        )

        final_filtered_df = filtered_by_date_df.copy()

        if selected_product_for_report != 'Tüm Ürünler':
            # Seçilen ürünün SKU'sunu bul
            selected_sku_for_report = selected_product_for_report.split(' - ')[0]
            final_filtered_df = filtered_by_date_df[filtered_by_date_df['SKU'] == selected_sku_for_report]
            
            if not final_filtered_df.empty:
                product_total_giris = final_filtered_df[final_filtered_df['Islem Tipi'] == 'Giriş']['Adet'].sum()
                product_total_cikis = final_filtered_df[final_filtered_df['Islem Tipi'] == 'Çıkış']['Adet'].sum()
                
                st.markdown(f"**{selected_product_for_report} için Toplam Giriş:** {product_total_giris} adet")
                st.markdown(f"**{selected_product_for_report} için Toplam Çıkış:** {product_total_cikis} adet")
                st.markdown(f"**{selected_product_for_report} için Net Stok Değişimi:** {product_total_giris - product_total_cikis} adet")
                
                st.dataframe(final_filtered_df[['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi']].sort_values(by='Tarih', ascending=False), use_container_width=True)
            else:
                st.info(f"{selected_product_for_report} için seçilen tarih aralığında hiçbir işlem bulunamadı.")
        else:
            # "Tüm Ürünler" seçiliyse, tarih filtrelenmiş tüm işlemleri göster
            st.info("Seçilen tarih aralığındaki tüm ürünlerin hareketliliği aşağıdaki tabloda gösterilmektedir.")
            st.dataframe(final_filtered_df[['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi']].sort_values(by='Tarih', ascending=False), use_container_width=True)
            
    else:
        st.info("Raporlama için henüz hiç depo işlemi bulunmamaktadır.")
