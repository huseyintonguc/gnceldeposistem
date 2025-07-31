import streamlit as st
import pandas as pd
import datetime

# Firebase kütüphanelerini import et
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# --- Firebase'i Başlat ---
# secrets.toml dosyasından Firebase kimlik bilgilerini yükle
# Streamlit Cloud'da otomatik olarak yüklenir.
# Yerelde test ederken secrets.toml dosyasının .streamlit/ klasöründe olduğundan emin olun.
try:
    # Eğer Firebase zaten başlatılmadıysa başlat
    if not firebase_admin._apps:
        cred = credentials.Certificate(st.secrets["firebase"])
        firebase_admin.initialize_app(cred)
    
    db = firestore.client() # Firestore istemcisini al
except Exception as e:
    st.error(f"Firebase başlatılırken hata oluştu. Lütfen '.streamlit/secrets.toml' dosyanızı kontrol edin ve talimatlara göre yapılandırın: {e}")
    st.stop() # Hata durumunda uygulamayı durdur

# Firestore koleksiyon referansları
PRODUCTS_COLLECTION = db.collection("products")
WAREHOUSE_ENTRIES_COLLECTION = db.collection("warehouse_entries")


# --- Ürün Listesini Yükle ve Kaydet ---
@st.cache_data(ttl=3600) # Ürünler genellikle sık değişmez, 1 saat önbellekte kalabilir
def load_products_from_firestore():
    """Firestore'dan ürün listesini yükler."""
    try:
        docs = PRODUCTS_COLLECTION.stream()
        products_list = []
        for doc in docs:
            product_data = doc.to_dict()
            product_data['SKU'] = doc.id # SKU'yu doküman ID'si olarak kullan
            products_list.append(product_data)
        
        df = pd.DataFrame(products_list)
        
        # Gerekli sütunların varlığını kontrol et
        if 'SKU' not in df.columns or 'Urun Adi' not in df.columns:
            st.sidebar.error("Ürünler koleksiyonunda 'SKU' veya 'Urun Adi' sütunları bulunamadı. Lütfen Firestore'daki 'products' koleksiyonunuzu kontrol edin.")
            return pd.DataFrame(columns=['SKU', 'Urun Adi'])

        # Sadece gerekli sütunları al ve sırala
        df = df[['SKU', 'Urun Adi']].sort_values(by='Urun Adi', ascending=True).reset_index(drop=True)
        
        if df.empty:
            st.warning("Ürünler listesi boş görünüyor. Lütfen yeni ürün ekleyin.")
        else:
            st.sidebar.success("Ürün listesi Firebase Firestore'dan başarıyla yüklendi.")
        return df
    except Exception as e:
        st.error(f"Ürünler Firebase Firestore'dan yüklenirken bir hata oluştu: {e}")
        return pd.DataFrame(columns=['SKU', 'Urun Adi'])

def save_product_to_firestore(sku, product_name):
    """Yeni ürünü Firestore'a kaydeder."""
    try:
        # SKU'yu doküman ID'si olarak kullan
        PRODUCTS_COLLECTION.document(sku).set({"Urun Adi": product_name})
        return True
    except Exception as e:
        st.error(f"Yeni ürün Firebase Firestore'a kaydedilirken bir hata oluştu: {e}")
        return False

# --- Depo Giriş/Çıkışlarını Yükle ve Kaydet ---
@st.cache_data(ttl=1) # Depo girişleri sık değişir, önbelleği kısa tut
def load_warehouse_entries_from_firestore():
    """Firestore'dan depo giriş/çıkışlarını yükler."""
    try:
        docs = WAREHOUSE_ENTRIES_COLLECTION.order_by('Tarih', direction=firestore.Query.DESCENDING).stream()
        entries_list = []
        for doc in docs:
            entry_data = doc.to_dict()
            entries_list.append(entry_data)
        
        df = pd.DataFrame(entries_list)
        
        # Gerekli sütunların varlığını kontrol et
        required_cols = ['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi']
        if not all(col in df.columns for col in required_cols):
            st.sidebar.error("Depo girişleri koleksiyonunda eksik sütunlar var. Lütfen Firestore'daki 'warehouse_entries' koleksiyonunuzu kontrol edin.")
            return pd.DataFrame(columns=required_cols)

        # Tarih sütununu düzgünce datetime.date objesine çevir
        if 'Tarih' in df.columns:
            df['Tarih'] = df['Tarih'].apply(lambda x: datetime.datetime.strptime(x, '%Y-%m-%d').date() if isinstance(x, str) else x)

        if df.empty:
            st.warning("Depo girişleri listesi boş görünüyor. Yeni girişler beklenecek.")
        else:
            st.sidebar.success("Depo girişleri Firebase Firestore'dan başarıyla yüklendi.")
        return df
    except Exception as e:
        st.error(f"Depo girişleri Firebase Firestore'dan yüklenirken bir hata oluştu: {e}")
        return pd.DataFrame(columns=['Tarih', 'SKU', 'Urun Adi', 'Adet', 'Islem Tipi'])

def add_warehouse_entry_to_firestore(entry_data):
    """Yeni depo giriş/çıkışını Firestore'a ekler."""
    try:
        # Otomatik ID ile yeni bir doküman ekle
        WAREHOUSE_ENTRIES_COLLECTION.add(entry_data)
        return True
    except Exception as e:
        st.error(f"Depo girişi/çıkışı Firebase Firestore'a kaydedilirken bir hata oluştu: {e}")
        return False

# --- Uygulama Başlığı ---
st.set_page_config(layout="centered", page_title="Depo Giriş/Çıkış Kayıt Sistemi")
st.title("📦 Depo Giriş/Çıkış Kayıt Sistemi")
st.markdown("Gün içinde depoya alınan ve depodan çıkan ürünleri buraya kaydedin.")

# --- Session State Başlatma ---
if 'products_df' not in st.session_state or st.session_state['products_df'].empty:
    st.session_state['products_df'] = load_products_from_firestore()

if 'warehouse_entries_df' not in st.session_state or st.session_state['warehouse_entries_df'].empty:
     st.session_state['warehouse_entries_df'] = load_warehouse_entries_from_firestore()

products_df = st.session_state['products_df']
warehouse_entries_df = st.session_state['warehouse_entries_df']


# --- Yeni Ürün Ekleme Bölümü ---
st.markdown("---")
st.subheader("➕ Yeni Ürün Ekle")
new_product_sku = st.text_input("Yeni Ürün SKU'su (Benzersiz Olmalı)", key="new_sku_input").strip()
new_product_name = st.text_input("Yeni Ürün Adı", key="new_product_name_input").strip()

if st.button("Yeni Ürünü Kaydet"):
    if new_product_sku and new_product_name:
        # SKU'nun benzersizliğini Firestore'da kontrol et
        if PRODUCTS_COLLECTION.document(new_product_sku).get().exists:
            st.warning(f"SKU '{new_product_sku}' zaten mevcut. Lütfen farklı bir SKU girin.")
        else:
            if save_product_to_firestore(new_product_sku, new_product_name):
                st.success(f"Yeni ürün **{new_product_name}** (SKU: **{new_product_sku}**) başarıyla eklendi!")
                load_products_from_firestore.clear() # Ürün önbelleğini temizle
                st.session_state['products_df'] = load_products_from_firestore() # Güncel veriyi yeniden yükle
                st.rerun() # Sayfayı yeniden yükle
            else:
                st.error("Yeni ürün kaydedilirken bir sorun oluştu.")
    else:
        st.warning("Lütfen hem SKU hem de Ürün Adı girin.")

st.markdown("---") 

# Eğer ürün listesi boşsa uyarı ver
if products_df.empty:
    st.warning("Ürün listesi boş veya yüklenemedi. Lütfen Firebase Firestore'daki ürünler koleksiyonunuzu kontrol edin veya yukarıdan yeni ürün ekleyin.")
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

    transaction_type = st.radio(
        "İşlem Tipi",
        ('Giriş', 'Çıkış'),
        key="transaction_type_val"
    )

    quantity_label = "Alınan Adet" if transaction_type == 'Giriş' else "Verilen Adet"
    
    quantity_default = st.session_state.get("quantity_input_val", 1) 
    quantity = st.number_input(quantity_label, min_value=1, value=quantity_default, step=1, key="quantity_input_val")

    entry_date = st.date_input("Tarih", value=datetime.date.today(), key="date_input_val")

    # --- Kaydet Butonu ---
    if st.button("Kaydet"):
        if selected_sku and quantity > 0:
            entry_data = {
                'Tarih': entry_date.isoformat(), # Firebase için tarihleri string olarak sakla
                'SKU': selected_sku,
                'Urun Adi': selected_product_name,
                'Adet': quantity,
                'Islem Tipi': transaction_type
            }
            
            if add_warehouse_entry_to_firestore(entry_data): 
                st.success(f"**{quantity}** adet **{selected_product_name}** ({selected_sku}) **{entry_date.strftime('%d.%m.%Y')}** tarihinde **{transaction_type}** olarak kaydedildi!")
                
                load_warehouse_entries_from_firestore.clear() # Önbelleği temizle
                st.session_state['warehouse_entries_df'] = load_warehouse_entries_from_firestore() # Güncel veriyi yeniden yükle
                
                st.rerun() 
            
        else:
            st.warning("Lütfen bir ürün seçin ve geçerli bir adet girin.")

    st.markdown("---")
    st.subheader("Son Depo Girişleri")
    if not warehouse_entries_df.empty:
        # Tarih sütunu zaten datetime.date objesi olarak yükleniyor, ISO formatına çevirmeye gerek yok
        st.dataframe(warehouse_entries_df.sort_values(by='Tarih', ascending=False).head(10))
    else:
        st.info("Henüz hiç depo girişi yapılmadı.")

    st.markdown("---")
    st.subheader("Tüm Depo Girişleri")
    if not warehouse_entries_df.empty:
        df_for_download = warehouse_entries_df.copy()
        # Tarihleri indirme için string formatına çevir
        if 'Tarih' in df_for_download.columns:
            df_for_download['Tarih'] = df_for_download['Tarih'].apply(lambda x: x.isoformat() if isinstance(x, datetime.date) else x)

        csv_data = df_for_download.to_csv(index=False, encoding='utf-8-sig', sep=';') 
        st.download_button(
            label="Tüm Depo Girişlerini İndir (CSV)",
            data=csv_data,
            file_name="tum_depo_girisleri.csv",
            mime="text/csv",
        )
        st.dataframe(warehouse_entries_df)
    else:
        st.info("İndirilecek depo girişi verisi bulunmuyor.")

    st.markdown("---")
    st.subheader("Mevcut Ürünler Listesi")
    if not products_df.empty:
        st.dataframe(products_df)
    else:
        st.info("Mevcut ürün bulunmuyor. Lütfen yukarıdan yeni ürün ekleyin.")
