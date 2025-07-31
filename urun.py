import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase başlatma fonksiyonu
def initialize_firebase():
    # Streamlit secrets'tan 'firebase' bölümünü çek
    firebase_config = st.secrets["firebase"]

    try:
        # Kimlik bilgilerini kullanarak Firebase'i başlat
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred)
        st.success("Firebase başarıyla başlatıldı!")
        return firestore.client() # Firestore istemcisini döndür
    except ValueError:
        st.warning("Firebase zaten başlatılmış.")
        return firestore.client()
    except Exception as e:
        st.error(f"Firebase başlatılırken hata oluştu: {e}")
        st.info("Lütfen Streamlit Cloud'daki Secrets ayarlarınızı ve `urun.py` dosyanızı kontrol edin.")
        return None

# Uygulama başladı
db = initialize_firebase()

if db:
    st.write("Veritabanı bağlantısı başarılı. Ürünleri listeleyebilirsiniz.")
    # Firebase Firestore ile ilgili işlemlerinize burada devam edin
    # Örnek: products koleksiyonundan veri çekme
    # products_ref = db.collection("products")
    # docs = products_ref.stream()
    # for doc in docs:
    #     st.write(f"{doc.id} => {doc.to_dict()}")
else:
    st.error("Veritabanı bağlantısı kurulamadı. Lütfen hataları düzeltin.")
