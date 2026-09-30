# BudOS · Projekt Yuna

Spot 30 s do ogólnopolskiej kampanii BudOS: „Przetargi opanowane.” Wersja z 30.09.2026 jest ułożona według landingu BudOS v4: te same cztery kroki (Znajdź, Sprawdź, Policz, Złóż), liczby z bazy, lejek z hero i demo bez konta na końcu.

## Co jest w katalogu

| Plik | Opis |
|---|---|
| `index.html` | Odtwarzacz spotu ze scenopisem. Animacja i muzyka liczą się w przeglądarce z jednej osi czasu, więc obraz i dźwięk są zgrane co do beatu. |
| `export/budos-spot-f169.mp4` | 1920×1080, YouTube, TV, OOH digital |
| `export/budos-spot-f916.mp4` | 1080×1920, Reels, TikTok, Shorts, Stories |
| `export/budos-spot-f45.mp4` | 1080×1350, feed Instagram, Facebook i LinkedIn (ten sam format co GIF-y BudOS) |
| `export/budos-soundtrack.wav` | Sama ścieżka dźwiękowa, 48 kHz, 16 bit, stereo |
| `shorts.html` | Odtwarzacz trzech spotów pionowych (TikTok, Reels, YouTube Shorts) z opisem trendów i nakładką stref UI. Budowany z `shorts.src.html` przez `tools/build-shorts.py` |
| `export/budos-short-A.mp4` | Spot A, „Staram się zachowywać normalnie”, 24 s, 1080×1920 |
| `export/budos-short-B.mp4` | Spot B, „Flop-core”, 25,7 s, 1080×1920 |
| `export/budos-short-C.mp4` | Spot C, „Tapnij, żeby odkryć”, 16 s, zapętlony, 1080×1920 |
| `carousel.html` | Podgląd karuzeli premierowej z opisem posta. Budowany z `carousel.src.html` przez `tools/build-carousel.py` |
| `carousel/` | Karuzela premierowa w trzech formatach, po 8 slajdów PNG: `9x16/` 1080×1920 (Stories, TikTok; 01 to oryginalna okładka od BudOS), `4x5/` 1080×1350 (feed Instagrama i Facebooka, Threads, LinkedIn), `1x1/` 1080×1080 (LinkedIn, Facebook, X, YouTube). `BudOS_karuzela_LinkedIn_4x5.pdf` to karuzela dokumentowa na LinkedIn. Render: `tools/render-carousel.cjs` |
| `social.html` | Podgląd teł profili z nakładką stref zasłanianych przez zdjęcie profilowe. Budowany z `social.src.html` przez `tools/build-social.py` |
| `social/` | Tła profili PNG: Facebook 1640×624, X 1500×500, LinkedIn profil 1584×396, LinkedIn firma 1128×191, YouTube 2560×1440, awatar 1080×1080 (ciemny i zielony). Render: `tools/render-social.cjs` |
| `brand/` | Logo BudOS zwektoryzowane z przekazanego pliku PNG (SVG i ścieżki) |
| `tools/render.cjs` | Renderer MP4: Playwright zapisuje klatki, OfflineAudioContext renderuje dźwięk, ffmpeg składa H.264 + AAC |
| `tools/fetch-fonts.sh` | Pobiera fonty z landingu (Space Grotesk, Martian Mono) do lokalnego cache na potrzeby renderu |

## Scenopis (128 BPM, 1 takt = 1,875 s)

| Czas | Scena | Na ekranie | Dźwięk |
|---|---|---|---|
| 00:00 | Licznik | „Ostatnie 7 dni”, licznik do 2 787 nowych ogłoszeń, mapa Polski zapala się ogłoszeniami, „Który jest Twój?” | Sub-boom, tykanie licznika, dzwon |
| 00:03.7 | Chaos | Ściana ogłoszeń z BZP, TED i BIP, „Nie przekopuj całej listy.” | Stopa przez filtr, werbel narasta, pół beatu ciszy |
| 00:07.5 | 01 Znajdź | BZP (co 15 minut), TED (codziennie) i BIP (radar gmin) łączą się w Zwiad. „Jedna lista z BZP, TED i BIP.” „Na górze listy Twoja robota.” Wiersze z nagrania Zwiadu na landingu, dopasowanie 100 | Drop, tomy na każde źródło |
| 00:11.2 | 02 Sprawdź | Strony SWZ przechodzą w raport z demo: 13 wymagań, 13 ryzyk, czerwona flaga ze stroną. Potem karta z Poznania i wybór „Analiza” z powodem. „SWZ przeczytana, z numerem strony.” „Najpierw decyzja. Potem oferta.” | Szelest stron, niski dźwięk flagi, klik |
| 00:15.0 | 03 Policz | Skaner czyta przedmiar z PDF, pozycja 34 trafia do kosztorysu i rozkłada się na skład z kodem KNR, w tle 784 685 cen z bazy. „Przedmiar z PDF w wierszu kosztorysu.” „Kod KNR i skład ceny pozycji.” | Hook C–Es–F, uderzenie na składzie |
| 00:18.7 | 04 Złóż | Dane firmy i kwota 340 235,02 zł brutto wchodzą do formularza, lista braków, podpis. „Formularze z danymi Twojej firmy.” „Decydujesz i podpisujesz Ty.” | Stukot pól, licznik kwoty, pióro |
| 00:22.5 | Lejek | Znajdź. Sprawdź. Policz. Złóż. Każde słowo zapala pierścień lejka z hero landingu. „Od ogłoszenia do oferty.” | Tom na każdy krok |
| 00:26.2 | Packshot | Logo, „Przetargi opanowane.”, przycisk „Zobacz demo bez konta”, budos.io | Dźwiękowe logo C5–Es5–F5, wybrzmienie |

Zasady prawdy z landingu v4: kadry z demo mają podpis „Przykład z demo · przegląd dokumentów” i adres `/demo` w pasku okna, decyzja jest opisana jako „Na tym etapie”, a nie rekomendacja. Spot nie mówi, że BudOS składa ofertę: przygotowuje dokumenty, a decyzję i podpis zostawia firmie.

## Spoty pionowe (TikTok, Reels, YouTube Shorts)

| Spot | Trend | Pomysł | Muzyka |
|---|---|---|---|
| A | „I Try to Act Normal” | Szef pyta o przetarg na remont urzędu w Poznaniu. Na zewnątrz „Jasne, pod kontrolą.”, w środku 39 plików dokumentacji i puls 180. Potem termin, analiza SWZ i kosztorys z demo (z podpisem) i puls spada do 72: „Teraz to nawet prawda.” | 100 BPM, napięcie → luźny trap z Rhodesem |
| B | „Flop-core” | Cztery wtopy (spóźniona oferta, przeoczony warunek, zgubiony przecinek, 2 h przewijania), potem cztery rozwiązania słowami landingu: termin w Zwiadzie, wyciąg i flagi z numerem strony, przedmiar z PDF i ceny z bazy, na górze listy Twoja robota. Hasło: „Mniej flopów. Przetargi opanowane.” | 140 BPM, jersey club, muzyka urywa się na każdej wpadce |
| C | „Tap to reveal” | Sześć rozmytych kafelków: Znajdź, Sprawdź, decyzja, Policz, Złóż, a pod ostatnim logo. Kafelki z liczbami z demo mają podpis „demo”. Ostatnia klatka = pierwsza, więc spot się zapętla | 120 BPM, lo-fi house, ASMR-owe popy |

Wspólne zasady: napis-hak od pierwszej klatki, ważne treści poza strefami interfejsu (górne 150 px, prawe 140 px, dolne 380 px), dźwiękowe logo C–Es–F na końcu każdego spotu. Każdy kończy się hasłem „Przetargi opanowane.” i przyciskiem „Zobacz demo bez konta”, jak na landingu.

Render: `PAGE=shorts.html SPOT=A node render.cjs f916 /tmp/out 30` (plus `FFMPEG`, `FONTCACHE`, `NODE_PATH` jak niżej).

## Marka

- Tło `#070E18`, tekst `#E8DDD4`, akcent `#75B974` (odczytane z GIF-ów BudOS)
- Space Grotesk (nagłówki i UI), Martian Mono (liczby, kody KNR, etykiety), tak jak na landingu v4
- Kolory decyzji z landingu: Tak zielone, Analiza jasnoszare, Nie czerwone (`#E5625C`)
- Motyw przewodni: „czysty blur” z GIF-ów. Nieistotne elementy się rozmywają, ostre zostaje tylko to, co dotyczy użytkownika.

## Ponowny render

```bash
cd tools
./fetch-fonts.sh /tmp/budos-fonts
FFMPEG=$(python3 -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())") \
FONTCACHE=/tmp/budos-fonts NODE_PATH=$(npm root -g) node render.cjs f169 /tmp/out 30
```

Format: `f169`, `f916` albo `f45`. Wynik trafia do `/tmp/out/budos-spot-<format>.mp4`.
