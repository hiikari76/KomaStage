# KomaStage

Python ve PyQt6 kullanılarak geliştirilmiş; masaüstünü interaktif bir sahneye dönüştüren, kendi özel Shimeji karakter paketlerinizi (`.zip` veya klasör) içe aktarabileceğiniz çapraz platform (macOS / Windows) masaüstü maskot motoru.

## Özellikler
- **Özel Karakter İçe Aktarma (`.zip` & Klasör):** İnternetten indirdiğiniz herhangi bir Shimeji paketini tek tıkla kütüphanenize ekleyin.
- **KomaStage Kontrol Paneli:** Yüklü karakterleri önizleyin, ekrana yeni maskotlar çağırın (`+1`), boyut (`64px`–`256px`) ve hız (`%50`–`%250`) ayarlarını canlı olarak değiştirin.
- **Durum Makinesi ve Fizik:** Yürüme, koşma, özel animasyonlar, oturma, kutuya saklanma, duvara/tavana tırmanma ve fare ile sürükle-bırak mekaniği.
- **Eksik Kare Koruması (Fallback):** Standart dışı veya eksik animasyon karelerine sahip özel Shimeji paketlerini çökmeden otomatik uyarlar.

## İndirme (Kurulum Gerektirmez)
Sağ taraftaki **[Releases](../../releases)** bölümünden işletim sisteminize uygun dosyayı indirip doğrudan çalıştırabilirsiniz:
- **macOS:** `KomaStage-Mac.zip` (Açtıktan sonra ilk seferde *Sağ Tık > Aç* ile başlatın)
- **Windows:** `KomaStage.exe`

## Kaynak Koddan Çalıştırma
```bash
git clone [https://github.com/hiikari76/KomaStage.git](https://github.com/hiikari76/KomaStage.git)
cd KomaStage
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
sed -i '' 's/Desktop Pet Studio/KomaStage/g' main.py
sed -i '' 's/DesktopPets/KomaStage/g' main.py
python3 -c '
readme = """# KomaStage

Python ve PyQt6 kullanılarak geliştirilmiş; masaüstünü interaktif bir sahneye dönüştüren, kendi özel Shimeji karakter paketlerinizi (.zip veya klasör) içe aktarabileceğiniz çapraz platform (macOS / Windows) masaüstü maskot motoru.

## Özellikler
- **Özel Karakter İçe Aktarma (.zip & Klasör):** İnternetten indirdiğiniz herhangi bir Shimeji paketini tek tıkla kütüphanenize ekleyin.
- **KomaStage Kontrol Paneli:** Yüklü karakterleri önizleyin, ekrana yeni maskotlar çağırın (+1), boyut (64px-256px) ve hız (%50-%250) ayarlarını canlı olarak değiştirin.
- **Durum Makinesi ve Fizik:** Yürüme, koşma, özel animasyonlar, oturma, kutuya saklanma, duvara/tavana tırmanma ve fare ile sürükle-bırak mekaniği.
- **Eksik Kare Koruması (Fallback):** Standart dışı veya eksik animasyon karelerine sahip özel Shimeji paketlerini çökmeden otomatik uyarlar.

## İndirme (Kurulum Gerektirmez)
Sağ taraftaki **[Releases](../../releases)** bölümünden işletim sisteminize uygun dosyayı indirip doğrudan çalıştırabilirsiniz:
- **macOS:** KomaStage-Mac.zip (Açtıktan sonra ilk seferde Sağ Tık > Aç ile başlatın)
- **Windows:** KomaStage.exe

## Kaynak Koddan Çalıştırma
    git clone https://github.com/hiikari76/KomaStage.git
    cd KomaStage
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python main.py

## Görsel Kaynağı (Credits)
Varsayılan Hatsune Miku Shimeji görselleri [Shimeji.org](https://shimeji.org/u/5elo0kxg) kaynağından alınmıştır.
"""
with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme)
'
cat << 'EOF' > .github/workflows/build.yml
name: Build and Release KomaStage

on:
  push:
    branches: [ main ]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install PyQt6 pyinstaller pillow
      - run: pyinstaller --noconfirm --windowed --onefile --name "KomaStage" --add-data "assets;assets" --icon="assets/shime1.png" main.py
      - uses: actions/upload-artifact@v4
        with:
          name: KomaStage-Windows
          path: dist/KomaStage.exe

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install PyQt6 pyinstaller pillow
      - run: pyinstaller --noconfirm --windowed --name "KomaStage" --add-data "assets:assets" --icon="assets/shime1.png" main.py
      - run: ditto -c -k --sequesterRsrc --keepParent dist/KomaStage.app dist/KomaStage-Mac.zip
      - uses: actions/upload-artifact@v4
        with:
          name: KomaStage-macOS
          path: dist/KomaStage-Mac.zip

  release:
    needs: [build-windows, build-macos]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: artifacts
      - uses: softprops/action-gh-release@v2
        with:
          tag_name: v1.1.0
          name: KomaStage v1.1.0 - Custom Shimeji Engine & Studio GUI
          files: |
            artifacts/KomaStage-Windows/KomaStage.exe
            artifacts/KomaStage-macOS/KomaStage-Mac.zip
