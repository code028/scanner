Inventory Scanner – uputstvo

1) Instalacija:
   python -m venv .venv
   .venv\Scripts\activate    (Windows)   ili   source .venv/bin/activate (Linux/Mac)
   pip install -r requirements.txt

2) Pokretanje:
   python main.py
   Aplikacija startuje; prijavi se kao:
   - korisničko ime: admin
   - lozinka: admin

3) PDF izvoz:
   - U HOME (Inventar) stranici, podesi filtere po potrebi.
   - Klikni "Export PDF".
   - U dijalogu klikni "Sačuvaj PDF" i izaberi lokaciju.
   Napomena: U web okruženju (browser) snimanje putem putanje može biti onemogućeno.
   Preporuka je desktop režim ili flet.app() lokalno.

4) Struktura podataka:
   - SQLite fajl: inventory.db kreira se automatski.
   - Tabele: users, categories, items.
   - Admin nalog se seed-uje ako ne postoji.

5) Funkcionalnosti:
   - Prijava korisnika; admin/moderator uloge
   - Lista inventara sa pretragom i filterima (kategorija, godina, status)
   - Detalji stavke (uređivanje, otpisivanje, brisanje)
   - Dodavanje nove stavke
   - CRUD nad kategorijama
   - CRUD nad korisnicima (samo admin)
   - Statistika (statusi, kategorije, godine)
   - Izveštaj (sažetak) + izvoz u PDF (trenutno filtrirani podaci)

Autor: Inventory Scanner
