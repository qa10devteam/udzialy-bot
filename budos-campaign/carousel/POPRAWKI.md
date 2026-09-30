# Karuzela BudOS: poprawki pod landing i korektę QA10 (30.09.2026)

Źródło: specyfikacja „Prompt dla Claude — poprawki karuzeli BudOS” oraz landing BudOS v4 (sesja landingowa, gałąź `feat/landing-10`). Strona budos.io była niedostępna z tego środowiska (proxy zwraca 403), więc żywej wersji nie dało się sprawdzić.

Wszystkie slajdy są w `carousel/9x16`, `carousel/4x5`, `carousel/1x1` i w `BudOS_karuzela_LinkedIn_4x5.pdf`. Plik edytowalny: `carousel.src.html` (budowany do `carousel.html`). Oryginalna okładka „Premiera” leży bez zmian w `brand/premiera-okladka-oryginal.png`. We wszystkich formatach slajd 01 jest odtworzony w HTML, żeby dało się dodać gwiazdkę, dopisek i nowy przycisk.

## Lista zmian

| Plik | Poprawka |
|---|---|
| `01-okladka.png` | Przy „6 minut” jest zielona gwiazdka, pod porównaniem dopisek „*Potwierdzone po testach w firmach budowlanych.”. Doszło „Decydujesz i podpisujesz Ty.” z ikoną tarczy. Przycisk „W ZASIĘGU KLIKNIĘCIA” zmieniony na „ZOBACZ DEMO BEZ KONTA”. Logo, „PREMIERA”, „Przetargi opanowane” i porównanie 33 godziny → 6 minut zostały. |
| `02-zwiad.png` | Nowy opis: „Jedna lista z BZP, TED i BIP. Na górze przetargi dopasowane do Twojej firmy.” „Dziś: 171 nowych” zastąpione etykietą „BZP · TED · BIP”. Karta ogłoszenia ma etykietę „Przykładowy alert”. Usunięte „teraz”, „2 min temu”, „za 17 dni” i słowo „nowy”. Mapa i „alert, gdy coś pasuje” zostały. |
| `03-filtry.png` | Nagłówek „Przetargi dopasowane do Twojej firmy.”, opis „Twoje kody CPV, województwa i widełki wartości.” Panel jest ilustracją, więc ma etykietę „Schemat filtrów” i tylko potwierdzone kryteria: kody CPV, województwa, widełki wartości. Usunięte: filtr terminu, „Dziś 171”, „Pokaż wyniki”, „Ustawiasz raz…”, „171 ogłoszeń dziennie”. Pasek: przekreślone „czytanie wszystkich ogłoszeń”, wynik „na górze Twoja robota”. |
| `04-termin.png` | Opis „Data i godzina składania ofert na karcie przetargu.” Duży licznik „17” i „dni do złożenia oferty” zastąpione napisem „Data i godzina”. Z karty usunięte „za 17 dni”. Nad kartą i kalendarzem etykieta „Przykład — nie jest aktualnym odliczaniem.” Data 12.10.2026, 10:00 bez zmian. |
| `05-analiza-swz.png` | Nagłówek „SWZ przeczytana. Z numerem strony.”, opis „Warunki, wadium, kary i terminy na jednej liście. Przy czerwonej fladze sprawdzasz dokument i stronę.” Dawny panel (z „0 ryzyk”) zastąpiony schematem „Warunek → dokument → strona” z etykietą „Schemat · nie jest ekranem aplikacji”, bez numerów stron i treści flag. Dopisek „Analizę AI weryfikujesz w źródłach.” Pasek: przekreślone „szukanie warunków w dokumentach”, wynik „wyciąg i źródła do sprawdzenia”. |
| `06-kosztorys.png` | Nagłówek „Przedmiar z PDF w wiersze kosztorysu.”, opis „Stawki i narzuty ustawiasz sam. Kosztorys zatwierdzasz Ty.” Pozycja KNR 4-01 0422-04 i jej skład bez zmian (kod, cena, ilości, jednostki). Podpis „Przykładowa pozycja KNR — materiały, robocizna i ilości.” Pasek: przekreślone „ręczne przepisywanie przedmiaru”, wynik „wiersze kosztorysu do Twojej weryfikacji”. |
| `07-wynik.png` | Nagłówek „Najpierw decyzja. Potem oferta.”, opis „Tak, Analiza albo Nie — zawsze z powodem. Decyzję „Tak” zapiszesz z zatwierdzonym kosztorysem.” Schemat w pięciu krokach: Zwiad, SWZ, Kosztorys, Decyzja (Tak / Analiza / Nie), Oferta po decyzji „Tak”. Na końcu „Decydujesz i podpisujesz Ty.” Porównanie 33 godziny → 6 minut* zostaje, z tym samym dopiskiem o testach. Usunięte „zanim ktokolwiek otworzy Excela” i „startujesz czy odpuszczasz”. |
| `08-start.png` | Lista na kartce: „Zwiad i dopasowanie ogłoszeń.”, „Terminy na karcie przetargu.”, „Analiza SWZ ze źródłami.”, „Kosztorys do zatwierdzenia.”, „Przygotowanie oferty.” Przycisk „ZOBACZ DEMO BEZ KONTA”, pod nim „budos.io”. Logo, „Przetargi opanowane.” i „Zapisz ten post…” zostały. |
| `BudOS_karuzela_LinkedIn_4x5.pdf` | Złożony od nowa z poprawionych slajdów 4:5. |

Opis posta w `carousel.html` też jest poprawiony: nie ma w nim „z całej Polski”, „skład każdej pozycji” ani „codziennie przegląda”.

## Elementy, które warto zastąpić aktualnym kadrem aplikacji

- 03 Filtry: panel jest schematem. Lepszy byłby prawdziwy kadr ustawień profilu (kody CPV, województwa, widełki).
- 05 Analiza SWZ: schemat „Warunek → dokument → strona” stoi w miejscu prawdziwego ekranu. Potrzebny jest aktualny kadr raportu z czerwoną flagą, dokumentem i stroną.
- 02 Zwiad i 04 Termin: karty (Kościerzyna, Mława, 12.10.2026) pochodzą z dawnych GIF-ów BudOS i mają podpis „przykład”. Aktualny kadr jest opcjonalny.

## Możliwa różnica z landingiem

Opis slajdu 06 („Stawki i narzuty ustawiasz sam.”) wykonałem zgodnie ze specyfikacją. W kopii landingu v4 jest jednak zdanie: „Pozycje KNR wycenione z bazy 784 685 cen … a narzuty ustawisz raz dla całego kosztorysu.” Landing mówi więc, że ceny pozycji przychodzą z bazy. Dobrze potwierdzić, czy „stawki ustawiasz sam” zgadza się z aktualną stroną.

## Teksty alternatywne (do użycia po zatwierdzeniu grafik)

01. Karta „Premiera” BudOS by QA10. Pod logo hasło „Przetargi opanowane.” Na kartce z notesu przekreślone: 33 godziny, żmudny research, stres i zmęczenie. Obok: 6 minut z gwiazdką, szybki wynik, czas i spokój. Pod spodem dopisek: „*Potwierdzone po testach w firmach budowlanych.” Dalej „Decydujesz i podpisujesz Ty.” i zielony przycisk „Zobacz demo bez konta”.

02. Slajd 2 z 8, Zwiad. Nagłówek „Zwiad szuka. Ty wybierasz.” Opis: jedna lista z BZP, TED i BIP, na górze przetargi dopasowane do Twojej firmy. Mapa Polski z punktami ogłoszeń, etykieta „BZP · TED · BIP” i karta z podpisem „Przykładowy alert”: przebudowa ulicy Staffa w Kościerzynie, Pomorskie, termin składania 12.10.2026. Na kartce przekreślone przekopywanie portali i 10 otwartych kart, obok „alert, gdy coś pasuje”.

03. Slajd 3 z 8, Filtry. Nagłówek „Przetargi dopasowane do Twojej firmy.” Opis: Twoje kody CPV, województwa i widełki wartości. Panel podpisany „Schemat filtrów” z przykładowymi kodami CPV, województwami i widełkami. Na kartce przekreślone czytanie wszystkich ogłoszeń, obok „na górze Twoja robota”.

04. Slajd 4 z 8, Termin. Nagłówek „Termin widzisz od razu.” Opis: data i godzina składania ofert na karcie przetargu. Duży napis „Data i godzina”, kalendarz października 2026 i karta z terminem 12 października 2026, 10:00, obie podpisane „Przykład — nie jest aktualnym odliczaniem.” Na kartce przekreślone szukanie w rozdziale XIV i „na kiedy to było?”, obok „data na karcie 12.10, 10:00”.

05. Slajd 5 z 8, Analiza SWZ. Nagłówek „SWZ przeczytana. Z numerem strony.” Opis: warunki, wadium, kary i terminy na jednej liście, przy czerwonej fladze sprawdzasz dokument i stronę. Schemat podpisany „nie jest ekranem aplikacji”: warunek, potem dokument, potem strona. Dopisek: „Analizę AI weryfikujesz w źródłach.” Na kartce przekreślone szukanie warunków w dokumentach, obok „wyciąg i źródła do sprawdzenia”.

06. Slajd 6 z 8, Kosztorys. Nagłówek „Przedmiar z PDF w wiersze kosztorysu.” Opis: stawki i narzuty ustawiasz sam, kosztorys zatwierdzasz Ty. Przykładowa pozycja 34, KNR 4-01 0422-04, podstemplowanie zagrożonych stropów, 253 zł, rozpisana na materiały i robociznę z ilościami, z podpisem „Przykładowa pozycja KNR — materiały, robocizna i ilości.” Na kartce przekreślone ręczne przepisywanie przedmiaru, obok „wiersze kosztorysu do Twojej weryfikacji”.

07. Slajd 7 z 8, Wynik. Nagłówek „Najpierw decyzja. Potem oferta.” Opis: Tak, Analiza albo Nie, zawsze z powodem, a decyzję „Tak” zapiszesz z zatwierdzonym kosztorysem. Pięć kroków: Zwiad, SWZ, Kosztorys, Decyzja, Oferta po decyzji „Tak”, i na końcu „Decydujesz i podpisujesz Ty.” Na kartce przekreślone 33 godziny oraz stres i zmęczenie, obok 6 minut z gwiazdką, czas i spokój, z dopiskiem „*Potwierdzone po testach w firmach budowlanych.”

08. Slajd 8 z 8, Start. Logo BudOS by QA10 i hasło „Przetargi opanowane.” Kartka z listą na następny przetarg: Zwiad i dopasowanie ogłoszeń, terminy na karcie przetargu, analiza SWZ ze źródłami, kosztorys do zatwierdzenia, przygotowanie oferty. Zielony przycisk „Zobacz demo bez konta”, pod nim budos.io. Na dole: „Zapisz ten post. Przyda się przy następnym przetargu.”
