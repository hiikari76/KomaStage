# Miku Desktop Pet (Shimeji)

Python ve PyQt6 kullanılarak geliştirilmiş; masaüstünde serbestçe dolaşan, ekran kenarlarına ve tavana tırmanan, fareyle etkileşime girebilen çapraz platform (macOS / Windows) masaüstü maskotu uygulaması.

## Özellikler
- **Şeffaf ve Çerçevesiz Pencere:** Masaüstü ve açık pencereler üzerinde kesintisiz hareket.
- **Durum Makinesi (State Machine):** Yürüme, koşma, pırasa taşıma, oturma, kutuya saklanma, duvara ve tavana tırmanma animasyonları.
- **Fizik ve Etkileşim:** Fare ile sürükle-bırak desteği ve yerçekimi mekaniği.
- **Sistem Tepsisi (Menu Bar) Desteği:** Üst menü çubuğundan kontrol ve ekrana birden fazla maskot çağırma (`+1`) özelliği.

## İndirme (Kurulum Gerektirmez)
Sağ taraftaki **[Releases](../../releases)** bölümünden işletim sisteminize uygun dosyayı indirip doğrudan çalıştırabilirsiniz:
- **macOS:** `MikuPet-Mac.zip` (Açtıktan sonra ilk seferde *Sağ Tık > Aç* ile başlatın)
- **Windows:** `MikuPet.exe`

## Kaynak Koddan Çalıştırma
```bash
git clone [https://github.com/hiikari76/desktop-pet.git](https://github.com/hiikari76/desktop-pet.git)
cd desktop-pet
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
cat << 'EOF' >> README.md

## Görsel Kaynağı (Credits)
Bu projede kullanılan Hatsune Miku Shimeji görselleri [Shimeji.org](https://shimeji.org/u/5elo0kxg) kaynağından alınmıştır.
