import flet as ft
import sqlite3
import datetime
from collections import Counter

# --- NOVO za PDF ---
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

DB_PATH = "inventory.db"

# -----------------------------
# DB INIT & HELPERS
# -----------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','moderator')),
                password TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT ''
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                uid INTEGER PRIMARY KEY,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('aktivno','otpisano')),
                deleted INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
            );
            """
        )
        # seed admin if not exists
        cur = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
        if cur.fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO users(username, full_name, role, password) VALUES (?,?,?,?)",
                ("admin", "Glavni Administrator", "admin", "admin"),
            )
        # seed demo data if no categories/items
        cur = conn.execute("SELECT COUNT(*) FROM categories")
        if cur.fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO categories(name, description) VALUES(?,?)",
                [("Računari", "Desktop i laptop"), ("Štampači", "Laser i inkjet"), ("Nameštaj", "Stolovi, stolice")],
            )
        cur = conn.execute("SELECT COUNT(*) FROM items")
        if cur.fetchone()[0] == 0:
            cats = {row[1]: row[0] for row in conn.execute("SELECT id, name FROM categories").fetchall()}
            demo = [
                (1001, cats.get("Računari"), "Dell OptiPlex 7090", "i5, 16GB, 512GB SSD", "2024-02-11", "aktivno", 0),
                (1002, cats.get("Računari"), "Lenovo ThinkPad T14", "Ryzen 7, 16GB", "2025-01-21", "aktivno", 0),
                (1003, cats.get("Štampači"), "HP LaserJet Pro M404dn", "Crno-beli laser", "2023-10-05", "aktivno", 0),
                (1004, cats.get("Nameštaj"), "Ergonomska stolica", "Crna, mreža", "2022-05-30", "otpisano", 0),
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO items(uid, category_id, name, description, date, status, deleted) VALUES (?,?,?,?,?,?,?)",
                demo,
            )

# -----------------------------
# APP
# -----------------------------
class Role:
    ADMIN = "admin"
    MOD = "moderator"

class ItemStatus:
    ACTIVE = "aktivno"
    OTPISANO = "otpisano"

def main(page: ft.Page):
    page.title = "Popis inventara"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.window_min_width = 1000
    page.window_min_height = 720

    init_db()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")

    # -------------- state --------------
    current_user = {"id": None, "username": None, "full_name": None, "role": None}

    # -------------- helpers --------------
    def is_admin():
        return current_user.get("role") == Role.ADMIN

    def category_name(cid: int) -> str:
        row = conn.execute("SELECT name FROM categories WHERE id=?", (cid,)).fetchone()
        return row[0] if row else "Nepoznata"

    def next_uid() -> int:
        row = conn.execute("SELECT MAX(uid) FROM items").fetchone()
        return (row[0] + 1) if row and row[0] else 1001

    def years_list():
        rows = conn.execute("SELECT DISTINCT substr(date,1,4) AS y FROM items WHERE deleted=0 ORDER BY y").fetchall()
        return [r[0] for r in rows]

    def categories_list():
        return conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()

    # -------------- top bar --------------
    user_chip = ft.Chip(label=ft.Text("Niste prijavljeni"), leading=ft.Icon(ft.Icons.PERSON))
    logout_btn = ft.IconButton(ft.Icons.LOGOUT, tooltip="Odjava")
    logout_btn.visible = False

    def do_logout(e=None):
        current_user.update({"id": None, "username": None, "full_name": None, "role": None})
        user_chip.label = ft.Text("Niste prijavljeni")
        logout_btn.visible = False
        tabs.visible = False
        set_body(login_view())
        page.update()

    logout_btn.on_click = do_logout
    page.appbar = ft.AppBar(title=ft.Text("Inventory Scanner"), actions=[user_chip, logout_btn])

    # -------------- body container --------------
    body = ft.Container(expand=True)

    def set_body(view):
        body.content = view
        page.update()

    # -------------- LOGIN --------------
    username = ft.TextField(label="Korisničko ime", dense=True, autofocus=True)
    password = ft.TextField(label="Lozinka", password=True, can_reveal_password=True, dense=True)
    login_err = ft.Text("", color=ft.Colors.RED_300)

    def attempt_login(e):
        row = conn.execute(
            "SELECT id, username, full_name, role, password FROM users WHERE username=?",
            (username.value.strip(),),
        ).fetchone()
        if row and row[4] == (password.value or ""):
            current_user.update({"id": row[0], "username": row[1], "full_name": row[2], "role": row[3]})
            user_chip.label = ft.Text(f"{row[2]} ({row[3]})")
            logout_btn.visible = True
            tabs.visible = True
            tabs.selected_index = 0
            refresh_home()
            set_body(home_view())
        else:
            login_err.value = "Neispravni kredencijali."
        page.update()

    def login_view():
        return ft.Container(
            alignment=ft.alignment.center,
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.INVENTORY, size=64),
                    ft.Text("Prijava korisnika", size=22, weight=ft.FontWeight.BOLD),
                    username,
                    password,
                    ft.ElevatedButton("Prijavi se", icon=ft.Icons.LOGIN, on_click=attempt_login),
                    login_err,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            expand=True,
        )

    # -------------- HOME (lista + filteri + izveštaj) --------------
    search_tf = ft.TextField(label="Pretraga (naziv/opis)", dense=True)
    filter_cat = ft.Dropdown(label="Kategorija", dense=True)
    filter_year = ft.Dropdown(label="Godina", dense=True)
    filter_status = ft.Dropdown(
        label="Status",
        dense=True,
        options=[
            ft.dropdown.Option(text="Svi", key=""),
            ft.dropdown.Option(text=ItemStatus.ACTIVE, key=ItemStatus.ACTIVE),
            ft.dropdown.Option(text=ItemStatus.OTPISANO, key=ItemStatus.OTPISANO),
        ],
        value="",
    )

    # --- live filter/search handlers ---
    def on_filter_change(e):
        if filter_cat.value == "Sve":
            filter_cat.value = ""
        if filter_year.value == "Sve":
            filter_year.value = ""
        if filter_status.value == "Svi":
            filter_status.value = ""
        apply_filters_and_fill()
        page.update()

    def on_search_change(e):
        apply_filters_and_fill()
        page.update()

    def clear_search(e):
        search_tf.value = ""
        apply_filters_and_fill()
        page.update()

    search_tf.on_change = on_search_change
    search_tf.suffix = ft.IconButton(ft.Icons.CLEAR, tooltip="Obriši", on_click=clear_search)
    filter_cat.on_change = on_filter_change
    filter_year.on_change = on_filter_change
    filter_status.on_change = on_filter_change

    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("UID")),
            ft.DataColumn(ft.Text("Kategorija")),
            ft.DataColumn(ft.Text("Naziv")),
            ft.DataColumn(ft.Text("Opis")),
            ft.DataColumn(ft.Text("Datum")),
            ft.DataColumn(ft.Text("Status")),
        ],
        rows=[],
    )

    def fill_filters():
        # categories
        cats = categories_list()
        filter_cat.options = [ft.dropdown.Option(text="Sve", key="")] + [
            ft.dropdown.Option(text=name, key=str(cid)) for cid, name in cats
        ]
        if filter_cat.value is None:
            filter_cat.value = ""
        # years
        ys = years_list()
        filter_year.options = [ft.dropdown.Option(text="Sve", key="")] + [
            ft.dropdown.Option(text=y, key=y) for y in ys
        ]
        if filter_year.value is None:
            filter_year.value = ""

    def apply_filters_and_fill():
        q = (search_tf.value or "").lower().strip()
        fc = filter_cat.value or ""
        fy = filter_year.value or ""
        fs = filter_status.value or ""

        sql = "SELECT uid, category_id, name, description, date, status FROM items WHERE deleted=0"
        params = []
        if q:
            sql += " AND (lower(name) LIKE ? OR lower(description) LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if fc and str(fc).isdigit():
            sql += " AND category_id=?"
            params.append(int(fc))
        if fy:
            sql += " AND substr(date,1,4)=?"
            params.append(fy)
        if fs:
            sql += " AND status=?"
            params.append(fs)
        sql += " ORDER BY uid"

        rows = conn.execute(sql, tuple(params)).fetchall()
        table.rows = []

        def open_details(uid):
            set_body(details_view(uid))

        for uid, cid, name, desc, date, status in rows:
            open_cb = (lambda u=uid: (lambda e: open_details(u)))()
            table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(uid)), on_tap=open_cb),
                        ft.DataCell(ft.Text(category_name(cid)), on_tap=open_cb),
                        ft.DataCell(ft.Text(name), on_tap=open_cb),
                        ft.DataCell(ft.Text(desc), on_tap=open_cb),
                        ft.DataCell(ft.Text(date), on_tap=open_cb),
                        ft.DataCell(ft.Text(status), on_tap=open_cb),
                    ]
                )
            )

    def reset_filters(e=None):
        search_tf.value = ""
        filter_cat.value = ""
        filter_year.value = ""
        filter_status.value = ""
        apply_filters_and_fill()
        page.update()

    def build_report_text():
      try:
          rows = conn.execute(
              """
              SELECT c.name,
                    substr(i.date,1,4) AS y,
                    i.status
              FROM items i
              JOIN categories c ON c.id = i.category_id
              WHERE i.deleted = 0
              """
          ).fetchall()

          cat_counter = Counter()
          year_counter = Counter()
          status_counter = Counter()

          for cname, y, s in rows:
              cname = cname or "Nepoznata"
              y = (y or "").strip() or "????"
              s = s or "nepoznato"
              cat_counter[cname] += 1
              year_counter[y] += 1
              status_counter[s] += 1

          lines = ["IZVEŠTAJ INVENTARA", "-" * 30, "Po kategorijama:"]
          if cat_counter:
              for k, v in sorted(cat_counter.items()):
                  lines.append(f"  - {k}: {v}")
          else:
              lines.append("  (nema podataka)")

          lines.append("\nPo godinama popisa:")
          if year_counter:
              for y, v in sorted(year_counter.items()):
                  lines.append(f"  - {y}: {v}")
          else:
              lines.append("  (nema podataka)")

          lines.append("\nStatusi:")
          if status_counter:
              for s, v in status_counter.items():
                  lines.append(f"  - {s}: {v}")
          else:
              lines.append("  (nema podataka)")

          return "\n".join(lines)
      except Exception as ex:
          # vrati tekst greške da bar vidiš u dijalogu šta se desilo
          return f"Greška prilikom generisanja izveštaja:\n{ex}"


    report_dialog = ft.AlertDialog(modal=True)

    def open_report_dialog(e=None):
      try:
          content_text = build_report_text()
          report_dialog.title = ft.Text("Izveštaj")
          # Ako si na starijem Flet-u i sumnjaš na weight, izostavi ga
          report_dialog.content = ft.Column(
              [
                  ft.Text("Sažetak po kategorijama, godinama i statusima:"),
                  ft.Text(content_text, selectable=True),
              ],
              scroll=ft.ScrollMode.ALWAYS,
              width=520,
              height=420,
          )
          report_dialog.actions = [ft.TextButton("Zatvori", on_click=lambda e: close_dialog())]

          # Redosled: dodeli → otvori → update
          page.dialog = report_dialog
          report_dialog.open = True
          page.update()
      except Exception as ex:
          page.snack_bar = ft.SnackBar(ft.Text(f"Izveštaj nije mogao da se prikaže: {ex}"))
          page.snack_bar.open = True
          page.update()


    def close_dialog():
        report_dialog.open = False
        page.update()

    # ---------------- PDF export ----------------
    # file_picker = ft.FilePicker()
    # page.overlay.append(file_picker)

    # pdf_buffer = {"bytes": b""}

    # def build_pdf_bytes(rows_for_pdf):
    #     """
    #     rows_for_pdf: list of tuples (uid, category_id, name, desc, date, status)
    #     return: bytes of generated PDF
    #     """
    #     buf = BytesIO()
    #     # landscape A4 zbog širine tabele
    #     doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)

    #     styles = getSampleStyleSheet()
    #     story = []

    #     title = Paragraph("Izveštaj inventara (trenutni filteri)", styles["Title"])
    #     story.append(title)
    #     story.append(Spacer(1, 12))

    #     # Headings
    #     data = [["UID", "Kategorija", "Naziv", "Opis", "Datum", "Status"]]
    #     for uid, cid, name, desc, date, status in rows_for_pdf:
    #         data.append([
    #             str(uid),
    #             category_name(cid),
    #             name or "",
    #             desc or "",
    #             date or "",
    #             status or "",
    #         ])

    #     table = Table(data, repeatRows=1)
    #     table.setStyle(TableStyle([
    #         ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
    #         ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
    #         ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    #         ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    #         ("FONTSIZE", (0, 0), (-1, 0), 11),
    #         ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
    #         ("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
    #         ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
    #     ]))
    #     story.append(table)

    #     # Footer napomena
    #     story.append(Spacer(1, 12))
    #     note = Paragraph("Generisano iz Inventory Scanner aplikacije.", styles["Normal"])
    #     story.append(note)

    #     doc.build(story)
    #     pdf_bytes = buf.getvalue()
    #     buf.close()
    #     return pdf_bytes

    # def export_pdf(e=None):
    #     # uzmi trenutno filtrirane redove
    #     q = (search_tf.value or "").lower().strip()
    #     fc = filter_cat.value or ""
    #     fy = filter_year.value or ""
    #     fs = filter_status.value or ""

    #     sql = "SELECT uid, category_id, name, description, date, status FROM items WHERE deleted=0"
    #     params = []
    #     if q:
    #         sql += " AND (lower(name) LIKE ? OR lower(description) LIKE ?)"
    #         params += [f"%{q}%", f"%{q}%"]
    #     if fc and str(fc).isdigit():
    #         sql += " AND category_id=?"
    #         params.append(int(fc))
    #     if fy:
    #         sql += " AND substr(date,1,4)=?"
    #         params.append(fy)
    #     if fs:
    #         sql += " AND status=?"
    #         params.append(fs)
    #     sql += " ORDER BY uid"

    #     rows = conn.execute(sql, tuple(params)).fetchall()

    #     # generiši PDF u memoriji
    #     pdf_bytes = build_pdf_bytes(rows)
    #     pdf_buffer["bytes"] = pdf_bytes

    #     # prikaži minimalni preview info u dijalogu
    #     report_dialog.title = ft.Text("Izveštaj (PDF)")
    #     report_dialog.content = ft.Column(
    #         [
    #             ft.Text("PDF je spreman za snimanje."),
    #             ft.Text(f"Broj stavki: {len(rows)}"),
    #             ft.Text("Klikni „Sačuvaj PDF” za izbor lokacije."),
    #         ],
    #         scroll=ft.ScrollMode.AUTO,
    #         width=520,
    #         height=200
    #     )
    #     report_dialog.actions = [
    #         ft.TextButton("Zatvori", on_click=lambda e: close_dialog()),
    #         ft.FilledButton("Sačuvaj PDF", icon=ft.Icons.DOWNLOAD, on_click=lambda e: file_picker.save_file(file_name="izvestaj.pdf", allowed_extensions=["pdf"]))
    #     ]
    #     page.dialog = report_dialog
    #     report_dialog.open = True
    #     page.update()

    # # Snimanje fajla na disk (Desktop: e.path postoji; Web: path najčešće None)
    # def on_file_save_result(e: ft.FilePickerResultEvent):
    #     try:
    #         if e.path:
    #             with open(e.path, "wb") as f:
    #                 f.write(pdf_buffer["bytes"])
    #             page.snack_bar = ft.SnackBar(ft.Text("PDF uspešno sačuvan."))
    #             page.snack_bar.open = True
    #         else:
    #             page.snack_bar = ft.SnackBar(ft.Text("Snimanje nije podržano u ovom okruženju (web). Pokreni kao desktop ili koristi Flet server/app."))
    #             page.snack_bar.open = True
    #     except Exception as ex:
    #         page.snack_bar = ft.SnackBar(ft.Text(f"Greška pri snimanju: {ex}"))
    #         page.snack_bar.open = True
    #     page.update()

    # file_picker.on_result = on_file_save_result
    # ---------------- kraj PDF exporta ----------------

    def simple_bar(label: str, value: int, total: int):
        frac = 0 if total == 0 else value / total
        return ft.Column([
            ft.Row([ft.Text(label), ft.Text(f"{value}")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(
                height=10,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                border_radius=6,
                content=ft.Container(width=400 * frac, height=10, bgcolor=ft.Colors.PRIMARY, border_radius=6),
            ),
        ])

    def stats_view():
        data = conn.execute("SELECT status FROM items WHERE deleted=0").fetchall()
        c = Counter([r[0] for r in data])
        total = sum(c.values())
        by_cat = Counter([row[0] for row in conn.execute("SELECT c.name FROM items i JOIN categories c ON c.id=i.category_id WHERE i.deleted=0").fetchall()])
        by_year = Counter([row[0] for row in conn.execute("SELECT substr(date,1,4) FROM items WHERE deleted=0").fetchall()])
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Statistika inventara", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text("Statusi", weight=ft.FontWeight.BOLD),
                    simple_bar("Aktivno", c.get(ItemStatus.ACTIVE, 0), total),
                    simple_bar("Otpisano", c.get(ItemStatus.OTPISANO, 0), total),
                    ft.Divider(),
                    ft.Text("Po kategorijama", weight=ft.FontWeight.BOLD),
                    *[simple_bar(name, cnt, total) for name, cnt in sorted(by_cat.items())],
                    ft.Divider(),
                    ft.Text("Po godinama", weight=ft.FontWeight.BOLD),
                    *[simple_bar(str(y), cnt, total) for y, cnt in sorted(by_year.items())],
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )

    def home_view():
        fill_filters()
        apply_filters_and_fill()
        header = ft.Row(
            controls=[
                search_tf,
                filter_cat,
                filter_year,
                filter_status,
                ft.IconButton(ft.Icons.REFRESH, tooltip="Poništi filtere", on_click=reset_filters),
                ft.FilledButton("Izveštaj", icon=ft.Icons.SUMMARIZE, on_click=open_report_dialog),
                # --- IZMENJENO dugme ---
                # ft.OutlinedButton("Export PDF", icon=ft.Icons.PICTURE_AS_PDF, on_click=export_pdf),
            ],
            wrap=True,
        )
        return ft.Container(
            content=ft.Column([
                ft.Text("Inventar", size=20, weight=ft.FontWeight.BOLD),
                header,
                ft.Divider(),
                table,
            ], scroll=ft.ScrollMode.AUTO, expand=True),
            expand=True,
        )

    def refresh_home():
        fill_filters()
        apply_filters_and_fill()

    # -------------- DETAILS --------------
    def details_view(uid: int):
        row = conn.execute(
            "SELECT uid, category_id, name, description, date, status, deleted FROM items WHERE uid=?",
            (uid,),
        ).fetchone()
        if not row:
            return ft.Column([ft.Text("Stavka nije pronađena.")])
        uid, cid, name, desc, date, status, deleted = row

        name_tf = ft.TextField(label="Naziv", value=name, dense=True)
        desc_tf = ft.TextField(label="Opis", value=desc, dense=True, multiline=True, min_lines=2, max_lines=4)
        date_tf = ft.TextField(label="Datum (YYYY-MM-DD)", value=date, dense=True)
        cat_dd = ft.Dropdown(label="Kategorija", dense=True, options=[ft.dropdown.Option(text=n, key=str(i)) for i, n in categories_list()], value=str(cid))
        status_dd = ft.Dropdown(label="Status", dense=True, options=[ft.dropdown.Option(text=ItemStatus.ACTIVE, key=ItemStatus.ACTIVE), ft.dropdown.Option(text=ItemStatus.OTPISANO, key=ItemStatus.OTPISANO)], value=status)

        def save_changes(e=None):
            try:
                if not name_tf.value.strip():
                    page.snack_bar = ft.SnackBar(ft.Text("Naziv je obavezan."))
                    page.snack_bar.open = True
                    page.update()
                    return
                conn.execute(
                    "UPDATE items SET category_id=?, name=?, description=?, date=?, status=? WHERE uid=?",
                    (int(cat_dd.value), name_tf.value.strip(), desc_tf.value.strip(), date_tf.value.strip(), status_dd.value, uid),
                )
                conn.commit()
                refresh_home()
                set_body(home_view())
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Greška: {ex}"))
                page.snack_bar.open = True
                page.update()

        def mark_otpisano(e=None):
            conn.execute("UPDATE items SET status=? WHERE uid=?", (ItemStatus.OTPISANO, uid))
            conn.commit()
            refresh_home()
            set_body(details_view(uid))

        def hard_delete(e=None):
            conn.execute("DELETE FROM items WHERE uid=?", (uid,))
            conn.commit()
            refresh_home()
            set_body(home_view())

        return ft.Container(
            content=ft.Column([
                ft.Text(f"Stavka #{uid}", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(f"Kategorija: {category_name(cid)}"),
                name_tf,
                desc_tf,
                date_tf,
                cat_dd,
                status_dd,
                ft.Row([
                    ft.FilledButton("Sačuvaj", icon=ft.Icons.SAVE, on_click=save_changes),
                    ft.OutlinedButton("Označi otpisano", icon=ft.Icons.BACKSPACE, on_click=mark_otpisano),
                    ft.TextButton("Obriši", icon=ft.Icons.DELETE, on_click=hard_delete),
                    ft.TextButton("Nazad", icon=ft.Icons.ARROW_BACK, on_click=lambda e: set_body(home_view())),
                ], wrap=True),
            ], scroll=ft.ScrollMode.AUTO, expand=True),
            expand=True,
        )

    # -------------- DODAVANJE STAVKE --------------
    def add_item_view():
        uid_tf = ft.TextField(label="UID (prazno = auto)", dense=True)
        name_tf = ft.TextField(label="Naziv", dense=True)
        desc_tf = ft.TextField(label="Opis", dense=True, multiline=True, min_lines=2, max_lines=4)
        date_tf = ft.TextField(label="Datum (YYYY-MM-DD)", dense=True, value=datetime.date.today().isoformat())
        cat_dd = ft.Dropdown(label="Kategorija", dense=True, options=[ft.dropdown.Option(text=n, key=str(i)) for i, n in categories_list()])

        def add_now(e=None):
            try:
                if not (name_tf.value.strip() and cat_dd.value):
                    page.snack_bar = ft.SnackBar(ft.Text("Unesi naziv i izaberi kategoriju."))
                    page.snack_bar.open = True
                    page.update()
                    return
                uid_val = int(uid_tf.value) if uid_tf.value else next_uid()
                conn.execute(
                    "INSERT INTO items(uid, category_id, name, description, date, status, deleted) VALUES(?,?,?,?,?,?,0)",
                    (uid_val, int(cat_dd.value), name_tf.value.strip(), desc_tf.value.strip(), date_tf.value.strip(), ItemStatus.ACTIVE),
                )
                conn.commit()
                refresh_home()
                set_body(details_view(uid_val))
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Greška: {ex}"))
                page.snack_bar.open = True
                page.update()

        return ft.Container(
            content=ft.Column([
                ft.Text("Dodavanje nove stavke", size=20, weight=ft.FontWeight.BOLD),
                uid_tf,
                name_tf,
                desc_tf,
                date_tf,
                cat_dd,
                ft.FilledButton("Dodaj", icon=ft.Icons.ADD, on_click=add_now),
            ], scroll=ft.ScrollMode.AUTO, expand=True),
            expand=True,
        )

    # -------------- KATEGORIJE (CRUD) --------------
    def categories_view():
        name_tf = ft.TextField(label="Naziv kategorije", dense=True)
        desc_tf = ft.TextField(label="Opis", dense=True)

        cats_dt = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Naziv")),
                ft.DataColumn(ft.Text("Opis")),
                ft.DataColumn(ft.Text("Akcije")),
            ],
            rows=[]
        )

        add_btn = ft.FilledButton("Dodaj", icon=ft.Icons.ADD, on_click=lambda e: None, disabled=True)

        def validate_category_form(e=None):
            add_btn.disabled = not bool(name_tf.value.strip())
            page.update()

        name_tf.on_change = validate_category_form

        def add_now(e=None):
            try:
                if not name_tf.value.strip():
                    page.snack_bar = ft.SnackBar(ft.Text("Unesi naziv kategorije."))
                    page.snack_bar.open = True
                    page.update()
                    return
                conn.execute(
                    "INSERT INTO categories(name, description) VALUES(?,?)",
                    (name_tf.value.strip(), desc_tf.value.strip())
                )
                conn.commit()
                name_tf.value = ""
                desc_tf.value = ""
                validate_category_form()
                reload()
                refresh_home()
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Greška: {ex}"))
                page.snack_bar.open = True
                page.update()

        def save_edit(cid):
            try:
                if not name_tf.value.strip():
                    page.snack_bar = ft.SnackBar(ft.Text("Naziv kategorije ne može biti prazan."))
                    page.snack_bar.open = True
                    page.update()
                    return
                conn.execute(
                    "UPDATE categories SET name=?, description=? WHERE id=?",
                    (name_tf.value.strip(), desc_tf.value.strip(), cid)
                )
                conn.commit()
                name_tf.value = ""
                desc_tf.value = ""
                add_btn.text = "Dodaj"
                add_btn.on_click = add_now
                validate_category_form()
                reload()
                refresh_home()
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Greška: {ex}"))
                page.snack_bar.open = True
                page.update()

        def reload():
            cats_dt.rows = []
            for cid, name, desc in conn.execute("SELECT id, name, description FROM categories ORDER BY id"):
                def edit_closure(cid=cid, name=name, desc=desc):
                    def do_edit(e):
                        name_tf.value = name
                        desc_tf.value = desc
                        add_btn.text = "Sačuvaj izmene"
                        add_btn.on_click = lambda ev, cid=cid: save_edit(cid)
                        add_btn.disabled = False
                        page.update()
                    return do_edit
                def delete_closure(cid=cid):
                    def do_delete(e):
                        try:
                            conn.execute("DELETE FROM categories WHERE id=?", (cid,))
                            conn.commit()
                            reload()
                            refresh_home()
                        except Exception as ex:
                            page.snack_bar = ft.SnackBar(ft.Text(f"Greška: {ex}"))
                            page.snack_bar.open = True
                            page.update()
                    return do_delete
                cats_dt.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(cid))),
                        ft.DataCell(ft.Text(name)),
                        ft.DataCell(ft.Text(desc)),
                        ft.DataCell(ft.Row([
                            ft.IconButton(ft.Icons.EDIT, tooltip="Izmeni", on_click=edit_closure()),
                            ft.IconButton(ft.Icons.DELETE, tooltip="Obriši", on_click=delete_closure()),
                        ])),
                    ])
                )
            page.update()

        add_btn.on_click = add_now
        reload()

        return ft.Container(
            content=ft.Column([
                ft.Text("Kategorije (CRUD)", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([name_tf, desc_tf, add_btn], wrap=True),
                ft.Divider(),
                cats_dt,
            ], scroll=ft.ScrollMode.AUTO, expand=True),
            expand=True,
        )

    # -------------- MODERATORI (CRUD, samo admin) --------------
    def moderators_view():
        if not is_admin():
            return ft.Container(content=ft.Text("Pristup dozvoljen samo administratoru."), expand=True)

        usern_tf = ft.TextField(label="Korisničko ime", dense=True)
        name_tf = ft.TextField(label="Ime i prezime", dense=True)
        role_dd = ft.Dropdown(
            label="Uloga",
            dense=True,
            options=[ft.dropdown.Option(text="Moderator", key=Role.MOD), ft.dropdown.Option(text="Admin", key=Role.ADMIN)],
            value=Role.MOD
        )
        pass_tf = ft.TextField(label="Lozinka", dense=True, password=True, can_reveal_password=True)

        users_dt = ft.DataTable(columns=[
            ft.DataColumn(ft.Text("ID")),
            ft.DataColumn(ft.Text("Korisničko ime")),
            ft.DataColumn(ft.Text("Ime i prezime")),
            ft.DataColumn(ft.Text("Uloga")),
            ft.DataColumn(ft.Text("Akcije")),
        ], rows=[])

        add_btn = ft.FilledButton("Dodaj", icon=ft.Icons.ADD, on_click=lambda e: None, disabled=True)

        def validate_user_form(e=None):
            add_btn.disabled = not (
                usern_tf.value.strip() and
                name_tf.value.strip() and
                (pass_tf.value or "").strip()
            )
            page.update()

        usern_tf.on_change = validate_user_form
        name_tf.on_change  = validate_user_form
        pass_tf.on_change  = validate_user_form
        role_dd.on_change  = validate_user_form

        def clear_form():
            usern_tf.value = ""
            name_tf.value = ""
            role_dd.value = Role.MOD
            pass_tf.value = ""
            add_btn.text = "Dodaj"
            add_btn.on_click = add_now
            validate_user_form()

        def add_now(e=None):
            try:
                if not (usern_tf.value.strip() and name_tf.value.strip() and (pass_tf.value or "").strip()):
                    page.snack_bar = ft.SnackBar(ft.Text("Popuni korisničko ime, ime i prezime i lozinku."))
                    page.snack_bar.open = True
                    page.update()
                    return
                conn.execute(
                    "INSERT INTO users(username, full_name, role, password) VALUES(?,?,?,?)",
                    (usern_tf.value.strip(), name_tf.value.strip(), role_dd.value, pass_tf.value or "1234")
                )
                conn.commit()
                clear_form()
                reload()
                page.update()
            except sqlite3.IntegrityError:
                page.snack_bar = ft.SnackBar(ft.Text("Korisničko ime već postoji."))
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Greška: {ex}"))
                page.snack_bar.open = True
                page.update()

        def save_edit(uid):
            try:
                if not (usern_tf.value.strip() and name_tf.value.strip()):
                    page.snack_bar = ft.SnackBar(ft.Text("Korisničko ime i ime i prezime su obavezni."))
                    page.snack_bar.open = True
                    page.update()
                    return
                if pass_tf.value:
                    conn.execute(
                        "UPDATE users SET username=?, full_name=?, role=?, password=? WHERE id=?",
                        (usern_tf.value.strip(), name_tf.value.strip(), role_dd.value, pass_tf.value, uid)
                    )
                else:
                    conn.execute(
                        "UPDATE users SET username=?, full_name=?, role=? WHERE id=?",
                        (usern_tf.value.strip(), name_tf.value.strip(), role_dd.value, uid)
                    )
                conn.commit()
                clear_form()
                reload()
                page.update()
            except sqlite3.IntegrityError:
                page.snack_bar = ft.SnackBar(ft.Text("Korisničko ime već postoji."))
                page.snack_bar.open = True
                page.update()
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Greška: {ex}"))
                page.snack_bar.open = True
                page.update()

        def reload():
            users_dt.rows = []
            for uid, username, full_name, role in conn.execute("SELECT id, username, full_name, role FROM users ORDER BY id"):
                def edit(uid=uid, username=username, full_name=full_name, role=role):
                    def _e(e):
                        usern_tf.value = username
                        name_tf.value = full_name
                        role_dd.value = role
                        pass_tf.value = ""
                        add_btn.text = "Sačuvaj izmene"
                        add_btn.on_click = lambda ev, uid=uid: save_edit(uid)
                        add_btn.disabled = False
                        page.update()
                    return _e
                def delete(uid=uid):
                    def _d(e):
                        try:
                            conn.execute("DELETE FROM users WHERE id=?", (uid,))
                            conn.commit()
                            reload()
                            page.update()
                        except Exception as ex:
                            page.snack_bar = ft.SnackBar(ft.Text(f"Greška: {ex}"))
                            page.snack_bar.open = True
                            page.update()
                    return _d
                users_dt.rows.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(str(uid))),
                        ft.DataCell(ft.Text(username)),
                        ft.DataCell(ft.Text(full_name)),
                        ft.DataCell(ft.Text(role)),
                        ft.DataCell(ft.Row([
                            ft.IconButton(ft.Icons.EDIT, tooltip="Izmeni", on_click=edit()),
                            ft.IconButton(ft.Icons.DELETE, tooltip="Obriši", on_click=delete()),
                        ])),
                    ])
                )
            page.update()

        add_btn.on_click = add_now
        reload()

        return ft.Container(
            content=ft.Column([
                ft.Text("Upravljanje moderatorima (CRUD)", size=20, weight=ft.FontWeight.BOLD),
                ft.Row([usern_tf, name_tf, role_dd, pass_tf, add_btn], wrap=True),
                ft.Divider(),
                users_dt,
            ], scroll=ft.ScrollMode.AUTO, expand=True),
            expand=True,
        )

    # -------------- PROFIL --------------
    def profile_view():
        if not current_user.get("id"):
            return ft.Container(content=ft.Text("Nema podataka o profilu."), expand=True)
        return ft.Container(
            content=ft.Column([
                ft.Text("Profil", size=20, weight=ft.FontWeight.BOLD),
                ft.ListTile(leading=ft.Icon(ft.Icons.PERSON), title=ft.Text(current_user.get("full_name")), subtitle=ft.Text(current_user.get("username"))),
                ft.ListTile(leading=ft.Icon(ft.Icons.BADGE), title=ft.Text("Uloga"), subtitle=ft.Text(current_user.get("role"))),
                ft.FilledButton("Odjavi se", icon=ft.Icons.LOGOUT, on_click=do_logout),
            ], alignment=ft.MainAxisAlignment.START, expand=True),
            expand=True,
        )

    # -------------- TABOVI NA DNU (ikonice bez teksta) --------------
    def on_tab_change(e: ft.ControlEvent):
        idx = e.control.selected_index
        if idx == 0:
            refresh_home()
            set_body(home_view())
        elif idx == 1:
            set_body(add_item_view())
        elif idx == 2:
            set_body(categories_view())
        elif idx == 3:
            set_body(moderators_view())
        elif idx == 4:
            set_body(stats_view())
        elif idx == 5:
            set_body(profile_view())

    tabs = ft.Tabs(
        visible=False,
        selected_index=0,
        on_change=on_tab_change,
        tabs=[
            ft.Tab(icon=ft.Icons.HOME_OUTLINED),
            ft.Tab(icon=ft.Icons.ADD_BOX_OUTLINED),
            ft.Tab(icon=ft.Icons.CATEGORY_OUTLINED),
            ft.Tab(icon=ft.Icons.SUPERVISED_USER_CIRCLE_OUTLINED),
            ft.Tab(icon=ft.Icons.INSIGHTS_OUTLINED),
            ft.Tab(icon=ft.Icons.PERSON_OUTLINED),
        ],
        expand=0,
    )

    # initial screen
    set_body(login_view())
    page.add(body, tabs)

if __name__ == "__main__":
    ft.app(target=main)
