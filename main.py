import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkcalendar import DateEntry
from PIL import Image, ImageTk
import os
import shutil
import sys

from database import Database

# --- Configuration & Constants ---
COLORS = {
    "bg_main": "#F4F7F6",        # Light Grey-Blue
    "bg_card": "#FFFFFF",        # White
    "primary": "#4A90E2",        # Soft Blue
    "primary_hover": "#357ABD",
    "secondary": "#2ECC71",      # Green
    "secondary_hover": "#27AE60",
    "text_dark": "#2C3E50",      # Dark Grey
    "text_light": "#7F8C8D",     # Light Grey
    "accent": "#E67E22",         # Orange
    "danger": "#E74C3C",         # Red
    "danger_hover": "#C0392B"
}

FONTS = {
    "header": ("Segoe UI", 14, "bold"),
    "subheader": ("Segoe UI", 12, "bold"),
    "body": ("Segoe UI", 10),
    "body_bold": ("Segoe UI", 10, "bold"),
    "small": ("Segoe UI", 9)
}

TYPE_MAP = {
    "Illness": "Болезнь",
    "Anthropometry": "Антропометрия",
    "Checkup": "Осмотр",
    "Болезнь": "Illness",
    "Антропометрия": "Anthropometry",
    "Осмотр": "Checkup"
}

STATUS_MAP = {
    "Done": "Сделана",
    "Refused": "Отказ",
    "Medical Exemption": "Медотвод",
    "Сделана": "Done",
    "Отказ": "Refused",
    "Медотвод": "Medical Exemption"
}

class KindergartenApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Health Monitor: Детский Сад")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS["bg_main"])
        
        try:
            self.db = Database()
        except Exception as e:
            messagebox.showerror("Fatal Error", f"Database connection failed:\n{e}")
            sys.exit(1)

        self.setup_styles()
        self.create_main_layout()
        self.load_data()
        
        # Ensure database closes on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        if self.db:
            self.db.close()
        self.root.destroy()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # General
        style.configure(".", background=COLORS["bg_main"], foreground=COLORS["text_dark"], font=FONTS["body"])
        
        # Frames & Containers
        style.configure("Card.TFrame", background=COLORS["bg_card"], relief="flat")
        style.configure("Main.TFrame", background=COLORS["bg_main"])
        style.configure("Header.TFrame", background=COLORS["primary"])

        # Typography
        style.configure("Header.TLabel", background=COLORS["primary"], foreground="white", font=("Segoe UI", 18, "bold"))
        style.configure("CardTitle.TLabel", background=COLORS["bg_card"], foreground=COLORS["primary"], font=FONTS["header"])
        style.configure("Body.TLabel", background=COLORS["bg_card"], foreground=COLORS["text_dark"], font=FONTS["body"])
        style.configure("Label.TLabel", background=COLORS["bg_main"], foreground=COLORS["text_dark"], font=FONTS["body"])
        style.configure("Warning.TLabel", background=COLORS["bg_card"], foreground=COLORS["danger"], font=("Segoe UI", 12, "bold"))

        # Buttons
        style.configure("Primary.TButton", background=COLORS["primary"], foreground="white", borderwidth=0, font=FONTS["body_bold"], padding=10)
        style.map("Primary.TButton", background=[('active', COLORS["primary_hover"])])

        style.configure("Success.TButton", background=COLORS["secondary"], foreground="white", borderwidth=0, font=FONTS["body_bold"], padding=10)
        style.map("Success.TButton", background=[('active', COLORS["secondary_hover"])])

        style.configure("Danger.TButton", background=COLORS["danger"], foreground="white", borderwidth=0, font=FONTS["body_bold"], padding=5)
        style.map("Danger.TButton", background=[('active', COLORS["danger_hover"])])
        
        style.configure("SmallDanger.TButton", background=COLORS["danger"], foreground="white", borderwidth=0, font=("Segoe UI", 8), padding=2)

        # Treeview
        style.configure("Treeview", background="white", fieldbackground="white", foreground=COLORS["text_dark"], rowheight=30, font=FONTS["body"], borderwidth=0)
        style.configure("Treeview.Heading", background=COLORS["bg_main"], foreground=COLORS["text_dark"], font=FONTS["body_bold"], relief="flat")
        style.map("Treeview", background=[('selected', COLORS["primary"])], foreground=[('selected', 'white')])

        # Notebook
        style.configure("TNotebook", background=COLORS["bg_main"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=[15, 5], font=FONTS["body_bold"], background=COLORS["bg_main"], foreground=COLORS["text_dark"])
        style.map("TNotebook.Tab", background=[("selected", COLORS["bg_card"])], foreground=[("selected", COLORS["primary"])])
        
        # Inputs
        style.configure("TEntry", padding=5, relief="flat", borderwidth=1)

    def create_main_layout(self):
        # --- Header ---
        header = ttk.Frame(self.root, style="Header.TFrame", padding=15)
        header.pack(fill=tk.X)
        
        ttk.Label(header, text="🏥 Система контроля здоровья воспитанников", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="💾 Бэкап", command=self.backup_database).pack(side=tk.RIGHT)

        # --- Main Content ---
        container = ttk.Frame(self.root, style="Main.TFrame", padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        # Sidebar (List & Search)
        sidebar = ttk.Frame(container, style="Main.TFrame", width=400)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        
        self._create_sidebar(sidebar)

        # Main Detail Area
        self.right_panel = ttk.Frame(container, style="Card.TFrame", padding=20)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.show_welcome_view()

    def _create_sidebar(self, parent):
        # Toolbar
        toolbar = ttk.Frame(parent, style="Card.TFrame", padding=15)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # Search
        ttk.Label(toolbar, text="Поиск:", style="Body.TLabel").pack(anchor=tk.W)
        self.search_var = tk.StringVar()
        search_ent = ttk.Entry(toolbar, textvariable=self.search_var)
        search_ent.pack(fill=tk.X, pady=5)
        search_ent.bind('<Return>', lambda e: self.load_data())

        # Filter
        ttk.Label(toolbar, text="Группа:", style="Body.TLabel").pack(anchor=tk.W, pady=(10, 0))
        self.group_filter_var = tk.StringVar(value="Все")
        self.group_combo = ttk.Combobox(toolbar, textvariable=self.group_filter_var, state="readonly")
        self.group_combo.pack(fill=tk.X, pady=5)
        self.group_combo.bind("<<ComboboxSelected>>", lambda e: self.load_data())

        # Action Buttons
        actions = ttk.Frame(toolbar, style="Card.TFrame")
        actions.pack(fill=tk.X, pady=10)
        ttk.Button(actions, text="Найти", style="Primary.TButton", command=self.load_data).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(actions, text="Сброс", command=self.reset_filters).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        ttk.Separator(toolbar, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Navigation
        nav_btns = [
            ("+ Ребёнок", "Success.TButton", self.show_add_child_view),
            ("📅 Посещаемость", None, self.show_attendance_view),
            ("Управление группами", None, self.show_manage_groups_view),
            ("📊 Статистика", None, self.show_statistics_view),
            ("📥 Excel", None, self.export_to_excel)
        ]
        
        for text, style, cmd in nav_btns:
            kwargs = {"style": style} if style else {}
            ttk.Button(toolbar, text=text, command=cmd, **kwargs).pack(fill=tk.X, pady=5)

        # Treeview List
        list_frame = ttk.Frame(parent, style="Card.TFrame", padding=2)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(list_frame, columns=("id", "full_name", "group"), show="headings")
        self.tree.heading("id", text="#"); self.tree.heading("full_name", text="ФИО"); self.tree.heading("group", text="Группа")
        self.tree.column("id", width=30, anchor="center"); self.tree.column("full_name", width=180); self.tree.column("group", width=80, anchor="center")

        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self.on_child_select)

    # --- Views ---
    def clear_right_panel(self):
        for widget in self.right_panel.winfo_children():
            widget.destroy()

    def show_welcome_view(self):
        self.clear_right_panel()
        ttk.Label(self.right_panel, text="Выберите ребёнка из списка слева\nили добавьте нового", 
                  style="Body.TLabel", font=("Segoe UI", 16), foreground=COLORS["text_light"], justify=tk.CENTER).pack(expand=True)

    def show_manage_groups_view(self):
        self.clear_right_panel()
        ttk.Label(self.right_panel, text="Управление группами", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 20))
        
        # Add Group
        add_frame = ttk.Frame(self.right_panel, style="Card.TFrame")
        add_frame.pack(fill=tk.X, pady=(0, 20))
        
        new_group_entry = ttk.Entry(add_frame, width=30)
        new_group_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        def add_group():
            name = new_group_entry.get()
            if name and self.db.add_group(name):
                messagebox.showinfo("Успех", "Группа добавлена")
                self.load_data()
                self.show_manage_groups_view()
            else:
                messagebox.showerror("Ошибка", "Группа уже существует или имя пустое")
        
        ttk.Button(add_frame, text="Добавить", style="Success.TButton", command=add_group).pack(side=tk.LEFT)

        # List Groups
        list_frame = ttk.Frame(self.right_panel, style="Card.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True)

        for g in self.db.get_groups():
            row = ttk.Frame(list_frame, style="Card.TFrame")
            row.pack(fill=tk.X, pady=5)
            
            name_var = tk.StringVar(value=g['name'])
            ttk.Entry(row, textvariable=name_var, width=30).pack(side=tk.LEFT)
            
            # Save btn
            ttk.Button(row, text="💾", width=3, command=lambda gid=g['id'], nv=name_var: self._update_group(gid, nv.get())).pack(side=tk.LEFT, padx=(10, 5))
            # Delete btn
            ttk.Button(row, text="🗑", width=3, style="SmallDanger.TButton", command=lambda gid=g['id']: self._delete_group(gid)).pack(side=tk.LEFT)

    def _update_group(self, gid, name):
        if self.db.update_group(gid, name):
            messagebox.showinfo("Успех", "Обновлено")
            self.load_data()
        else:
            messagebox.showerror("Ошибка", "Не удалось обновить")

    def _delete_group(self, gid):
        if messagebox.askyesno("Подтверждение", "Удалить группу?"):
            if self.db.delete_group(gid):
                self.show_manage_groups_view()
                self.load_data()
            else:
                messagebox.showerror("Ошибка", "Нельзя удалить группу, в которой есть дети")

    def show_attendance_view(self):
        self.clear_right_panel()
        ttk.Label(self.right_panel, text="Табель посещаемости", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 20))
        
        # Controls
        ctrl = ttk.Frame(self.right_panel, style="Card.TFrame")
        ctrl.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(ctrl, text="Дата:", style="Body.TLabel").pack(side=tk.LEFT)
        date_ent = DateEntry(ctrl, width=12, background=COLORS['primary'], foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        date_ent.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(ctrl, text="Группа:", style="Body.TLabel").pack(side=tk.LEFT, padx=(20, 0))
        groups = self.db.get_groups()
        group_dict = {g['name']: g['id'] for g in groups}
        group_cb = ttk.Combobox(ctrl, values=list(group_dict.keys()), state="readonly")
        group_cb.pack(side=tk.LEFT, padx=10)
        if groups: group_cb.current(0)
        
        list_box = ttk.Frame(self.right_panel, style="Card.TFrame")
        list_box.pack(fill=tk.BOTH, expand=True)
        
        def load_list():
            for w in list_box.winfo_children(): w.destroy()
            if not group_cb.get(): return
            
            gid = group_dict[group_cb.get()]
            date = date_ent.get_date()
            
            # Header
            h = ttk.Frame(list_box, style="Card.TFrame")
            h.pack(fill=tk.X, pady=5)
            ttk.Label(h, text="ФИО", width=30, font=FONTS["body_bold"]).pack(side=tk.LEFT)
            ttk.Label(h, text="Статус", font=FONTS["body_bold"]).pack(side=tk.LEFT, padx=20)
            
            for child in self.db.get_group_attendance(gid, date):
                row = ttk.Frame(list_box, style="Card.TFrame")
                row.pack(fill=tk.X, pady=2)
                ttk.Label(row, text=child['full_name'], width=30).pack(side=tk.LEFT)
                
                status_var = tk.StringVar(value=child['status'] if child['status'] else "Present")
                save_cmd = lambda cid=child['id'], var=status_var: self.db.mark_attendance(cid, date, var.get())
                
                for val, txt in [("Present", "Присутствует"), ("Sick", "Болеет"), ("Absent", "Отсутствует")]:
                    ttk.Radiobutton(row, text=txt, variable=status_var, value=val, command=save_cmd).pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl, text="Загрузить", style="Primary.TButton", command=load_list).pack(side=tk.LEFT, padx=20)

    def show_add_child_view(self):
        self.clear_right_panel()
        ttk.Label(self.right_panel, text="Новый воспитанник", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 20))
        self._build_child_form()

    def show_edit_child_view(self, child_id):
        self.clear_right_panel()
        child, _, _, _ = self.db.get_child_full_info(child_id)
        ttk.Label(self.right_panel, text="Редактирование данных", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 20))
        self._build_child_form(child)

    def _build_child_form(self, child=None):
        form = ttk.Frame(self.right_panel, style="Card.TFrame")
        form.pack(fill=tk.X)

        # Fields
        fields = {}
        
        def add_row(label, row_idx):
            ttk.Label(form, text=label, style="Body.TLabel").grid(row=row_idx, column=0, sticky=tk.W, pady=10)
        
        add_row("ФИО:", 0)
        fields['name'] = ttk.Entry(form, width=40)
        fields['name'].grid(row=0, column=1, pady=10, padx=10)
        if child: fields['name'].insert(0, child['full_name'])

        add_row("Дата рождения:", 1)
        fields['dob'] = DateEntry(form, width=37, background=COLORS['primary'], foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        fields['dob'].grid(row=1, column=1, pady=10, padx=10)
        if child: fields['dob'].set_date(child['birth_date'])

        add_row("Группа:", 2)
        groups = self.db.get_groups()
        g_dict = {g['name']: g['id'] for g in groups}
        fields['group'] = ttk.Combobox(form, values=list(g_dict.keys()), state="readonly", width=37)
        fields['group'].grid(row=2, column=1, pady=10, padx=10)
        if child and child['group_name']: fields['group'].set(child['group_name'])

        add_row("Аллергии:", 3)
        fields['allergies'] = ttk.Entry(form, width=40)
        fields['allergies'].grid(row=3, column=1, pady=10, padx=10)
        if child and child['allergies']: fields['allergies'].insert(0, child['allergies'])

        add_row("Фото:", 4)
        photo_path_var = tk.StringVar(value=child['photo_path'] if child and child['photo_path'] else "")
        
        def choose_photo():
            path = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
            if path: photo_path_var.set(path)
            
        ttk.Button(form, text="Выбрать файл", command=choose_photo).grid(row=4, column=1, sticky=tk.W, padx=10)
        ttk.Label(form, textvariable=photo_path_var, style="Body.TLabel").grid(row=4, column=1, padx=100)

        def save():
            data = {k: v.get() for k, v in fields.items()}
            data['photo'] = photo_path_var.get()
            
            if not (data['name'] and data['dob'] and data['group']):
                messagebox.showwarning("Внимание", "Заполните обязательные поля (ФИО, ДР, Группа)")
                return

            # Handle photo file
            final_photo = data['photo']
            if final_photo and os.path.exists(final_photo) and "photos" not in final_photo:
                if not os.path.exists("photos"): os.makedirs("photos")
                filename = f"{data['name']}_{datetime.now().timestamp()}.jpg"
                dest = os.path.join("photos", filename)
                try:
                    shutil.copy(final_photo, dest)
                    final_photo = dest
                except Exception: pass

            if child:
                self.db.update_child(child['id'], data['name'], data['dob'], g_dict[data['group']], final_photo, data['allergies'])
                messagebox.showinfo("Успех", "Данные обновлены")
                self.load_data()
                self.show_child_details(child['id'])
            else:
                new_id = self.db.add_child(data['name'], data['dob'], g_dict[data['group']], final_photo, data['allergies'])
                messagebox.showinfo("Успех", "Ребёнок добавлен")
                self.load_data()
                self.show_child_details(new_id)

        ttk.Button(self.right_panel, text="Сохранить", style="Success.TButton", command=save).pack(anchor=tk.W, pady=20)
        
        if child:
            def delete():
                if messagebox.askyesno("Внимание", "Удалить ребёнка и все связанные данные?"):
                    self.db.delete_child(child['id'])
                    self.load_data()
                    self.show_welcome_view()
            ttk.Button(self.right_panel, text="Удалить карточку", style="Danger.TButton", command=delete).pack(anchor=tk.W)

    def show_statistics_view(self):
        self.clear_right_panel()
        ttk.Label(self.right_panel, text="Статистика и Напоминания", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 20))
        
        # Reminders
        reminders = self.db.get_vaccine_reminders()
        if reminders:
            r_frame = ttk.Frame(self.right_panel, style="Card.TFrame", borderwidth=1, relief="solid")
            r_frame.pack(fill=tk.X, pady=(0, 20))
            ttk.Label(r_frame, text="🔔 Вакцинация (Срочно)", style="Warning.TLabel").pack(anchor=tk.W, padx=10, pady=5)
            for r in reminders:
                ttk.Label(r_frame, text=f"• {r}", style="Body.TLabel").pack(anchor=tk.W, padx=20)
        
        stats = self.db.get_dashboard_stats()
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4), facecolor="white")
        
        # Bar Chart
        if stats['children_per_group']:
            groups = [x[0] for x in stats['children_per_group']]
            counts = [x[1] for x in stats['children_per_group']]
            ax1.bar(groups, counts, color=COLORS["primary"])
            ax1.set_title("Дети по группам")
            plt.setp(ax1.get_xticklabels(), rotation=30, ha="right")
        
        # Pie Chart
        if stats['top_diagnoses']:
            diags = [x[0] for x in stats['top_diagnoses']]
            d_counts = [x[1] for x in stats['top_diagnoses']]
            ax2.pie(d_counts, labels=diags, autopct='%1.1f%%', colors=[COLORS["primary"], COLORS["secondary"], COLORS["accent"], "#9B59B6", "#34495E"])
            ax2.set_title("Частые диагнозы")
        
        canvas = FigureCanvasTkAgg(fig, master=self.right_panel)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def on_child_select(self, event):
        sel = self.tree.selection()
        if sel:
            item = self.tree.item(sel[0], "values")
            self.show_child_details(item[0])

    def show_child_details(self, child_id):
        self.clear_right_panel()
        child, parents, health, vaccinations = self.db.get_child_full_info(child_id)
        
        # Header Info
        header = ttk.Frame(self.right_panel, style="Card.TFrame")
        header.pack(fill=tk.X, pady=(0, 20))
        
        # Photo
        if child['photo_path'] and os.path.exists(child['photo_path']):
            try:
                img = Image.open(child['photo_path']).resize((100, 100), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                lbl = ttk.Label(header, image=photo)
                lbl.image = photo
                lbl.pack(side=tk.LEFT, padx=(0, 20))
            except Exception: pass

        info = ttk.Frame(header, style="Card.TFrame")
        info.pack(side=tk.LEFT)
        ttk.Label(info, text=child['full_name'], style="CardTitle.TLabel", font=("Segoe UI", 20, "bold")).pack(anchor=tk.W)
        ttk.Label(info, text=f"Группа: {child['group_name']}", style="Body.TLabel").pack(anchor=tk.W)
        if child['allergies']:
            ttk.Label(info, text=f"⚠️ АЛЛЕРГИЯ: {child['allergies']}", style="Warning.TLabel").pack(anchor=tk.W, pady=(5, 0))
        
        actions = ttk.Frame(header, style="Card.TFrame")
        actions.pack(side=tk.RIGHT, anchor=tk.N)
        
        def generate_pdf():
            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
            if path:
                try:
                    from reports import generate_child_report
                    generate_child_report(path, child, parents, health, vaccinations)
                    messagebox.showinfo("Успех", "PDF создан")
                except Exception as e:
                    messagebox.showerror("Ошибка", str(e))

        ttk.Button(actions, text="🖨 PDF", width=8, command=generate_pdf).pack(side=tk.RIGHT, padx=5)
        ttk.Button(actions, text="✎ Ред.", width=8, command=lambda: self.show_edit_child_view(child_id)).pack(side=tk.RIGHT)

        # Tabs
        nb = ttk.Notebook(self.right_panel)
        nb.pack(fill=tk.BOTH, expand=True)
        
        self._build_info_tab(nb, child, parents)
        self._build_health_tab(nb, health, child['id'])
        self._build_vaccine_tab(nb, vaccinations, child['id'])
        self._build_bmi_tab(nb, health)

    def _build_info_tab(self, nb, child, parents):
        frame = ttk.Frame(nb, style="Card.TFrame", padding=20)
        nb.add(frame, text="📋 Общее")
        
        ttk.Label(frame, text="Родители", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 15))
        
        p_list = ttk.Frame(frame, style="Card.TFrame")
        p_list.pack(fill=tk.BOTH, expand=True)
        
        for p in parents:
            row = ttk.Frame(p_list, style="Card.TFrame", padding=5)
            row.pack(fill=tk.X, pady=5)
            
            def del_p(pid=p['id']):
                if messagebox.askyesno("Подтверждение", "Удалить запись?"):
                    self.db.delete_parent(pid)
                    self.show_child_details(child['id'])

            ttk.Button(row, text="X", style="SmallDanger.TButton", width=3, command=del_p).pack(side=tk.RIGHT)
            ttk.Label(row, text=f"📞 {p['phone']}", style="Body.TLabel").pack(side=tk.RIGHT, padx=10)
            ttk.Label(row, text=f"👤 {p['full_name']}", style="Body.TLabel", font=FONTS["body_bold"]).pack(side=tk.LEFT)
            ttk.Separator(p_list, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # Add Parent
        add = ttk.Frame(frame, style="Card.TFrame")
        add.pack(fill=tk.X, pady=20)
        p_name = ttk.Entry(add, width=25); p_name.pack(side=tk.LEFT, padx=(0, 5))
        p_phone = ttk.Entry(add, width=15); p_phone.pack(side=tk.LEFT, padx=5)
        
        def save_p():
            if p_name.get():
                self.db.add_parent(child['id'], p_name.get(), p_phone.get())
                self.show_child_details(child['id'])
                
        ttk.Button(add, text="+ Родитель", style="Success.TButton", command=save_p).pack(side=tk.LEFT, padx=10)

    def _build_health_tab(self, nb, records, child_id):
        frame = ttk.Frame(nb, style="Card.TFrame", padding=20)
        nb.add(frame, text="🩺 Здоровье")
        
        tree = ttk.Treeview(frame, columns=("id", "date", "type", "desc", "diagnosis"), show="headings", height=8)
        tree.heading("date", text="Дата"); tree.heading("type", text="Тип"); tree.heading("desc", text="Описание"); tree.heading("diagnosis", text="Диагноз")
        tree.column("id", width=0, stretch=tk.NO)
        tree.pack(fill=tk.BOTH, expand=True)
        
        for r in records:
            d_type = TYPE_MAP.get(r['record_type'], r['record_type'])
            tree.insert("", tk.END, values=(r['id'], r['record_date'], d_type, r['description'], r['diagnosis']))
            
        def del_rec():
            sel = tree.selection()
            if sel and messagebox.askyesno("Удалить", "Удалить запись?"):
                self.db.delete_health_record(tree.item(sel[0], "values")[0])
                self.show_child_details(child_id)

        ttk.Button(frame, text="Удалить запись", style="SmallDanger.TButton", command=del_rec).pack(anchor=tk.E, pady=5)

        # Add Record
        form = ttk.Frame(frame, style="Card.TFrame")
        form.pack(fill=tk.X, pady=10)
        
        r1 = ttk.Frame(form, style="Card.TFrame"); r1.pack(fill=tk.X)
        d_ent = DateEntry(r1, width=12, background=COLORS['primary'], foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        d_ent.pack(side=tk.LEFT)
        t_cb = ttk.Combobox(r1, values=["Болезнь", "Антропометрия", "Осмотр"], width=15, state="readonly")
        t_cb.pack(side=tk.LEFT, padx=5)
        
        r2 = ttk.Frame(form, style="Card.TFrame"); r2.pack(fill=tk.X, pady=5)
        desc_ent = ttk.Entry(r2, width=40); desc_ent.pack(side=tk.LEFT)
        
        r3 = ttk.Frame(form, style="Card.TFrame"); r3.pack(fill=tk.X)
        h_ent = ttk.Entry(r3, width=8); h_ent.pack(side=tk.LEFT)
        w_ent = ttk.Entry(r3, width=8); w_ent.pack(side=tk.LEFT, padx=5)
        diag_ent = ttk.Entry(r3, width=20); diag_ent.pack(side=tk.LEFT, padx=5)
        
        def add():
            try:
                h = float(h_ent.get()) if h_ent.get() else None
                w = float(w_ent.get()) if w_ent.get() else None
                self.db.add_health_record(child_id, d_ent.get(), TYPE_MAP.get(t_cb.get(), "Checkup"), desc_ent.get(), h, w, diag_ent.get())
                self.show_child_details(child_id)
            except ValueError:
                messagebox.showerror("Ошибка", "Рост/Вес должны быть числами")

        ttk.Button(form, text="Добавить", style="Success.TButton", command=add).pack(anchor=tk.E, pady=5)

    def _build_vaccine_tab(self, nb, records, child_id):
        frame = ttk.Frame(nb, style="Card.TFrame", padding=20)
        nb.add(frame, text="💉 Вакцинация")
        
        tree = ttk.Treeview(frame, columns=("id", "vac", "date", "status"), show="headings", height=8)
        tree.heading("vac", text="Вакцина"); tree.heading("date", text="Дата"); tree.heading("status", text="Статус")
        tree.column("id", width=0, stretch=tk.NO)
        tree.pack(fill=tk.BOTH, expand=True)
        
        for r in records:
            tree.insert("", tk.END, values=(r['id'], r['vaccine_name'], r['date_administered'], STATUS_MAP.get(r['status'], r['status'])))
            
        def del_vac():
            sel = tree.selection()
            if sel and messagebox.askyesno("Удалить", "Удалить запись?"):
                self.db.delete_vaccination(tree.item(sel[0], "values")[0])
                self.show_child_details(child_id)
        
        ttk.Button(frame, text="Удалить", style="SmallDanger.TButton", command=del_vac).pack(anchor=tk.E, pady=5)
        
        # Add Vaccine
        form = ttk.Frame(frame, style="Card.TFrame")
        form.pack(fill=tk.X, pady=10)
        
        v_name = ttk.Entry(form, width=20); v_name.pack(side=tk.LEFT)
        v_date = DateEntry(form, width=12, background=COLORS['primary'], foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        v_date.pack(side=tk.LEFT, padx=5)
        v_stat = ttk.Combobox(form, values=["Сделана", "Отказ", "Медотвод"], width=15, state="readonly")
        v_stat.pack(side=tk.LEFT, padx=5)
        
        def add():
            if v_name.get():
                self.db.add_vaccination(child_id, v_name.get(), v_date.get(), STATUS_MAP.get(v_stat.get(), "Done"))
                self.show_child_details(child_id)
                
        ttk.Button(form, text="Добавить", style="Success.TButton", command=add).pack(side=tk.LEFT, padx=20)

    def _build_bmi_tab(self, nb, records):
        frame = ttk.Frame(nb, style="Card.TFrame", padding=30)
        nb.add(frame, text="⚖️ ИМТ")
        
        h, w = 0, 0
        for r in records:
            if r['height'] and r['weight']:
                h, w = r['height'], r['weight']
                break
        
        left = ttk.Frame(frame, style="Card.TFrame")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(left, text="Рост (см):", style="Body.TLabel").pack(anchor=tk.W)
        h_var = tk.DoubleVar(value=h)
        ttk.Entry(left, textvariable=h_var).pack(fill=tk.X, pady=5)
        
        ttk.Label(left, text="Вес (кг):", style="Body.TLabel").pack(anchor=tk.W)
        w_var = tk.DoubleVar(value=w)
        ttk.Entry(left, textvariable=w_var).pack(fill=tk.X, pady=5)
        
        res_var = tk.StringVar(value="--")
        
        def calc():
            try:
                hv, wv = h_var.get(), w_var.get()
                if hv > 0 and wv > 0:
                    bmi = wv / ((hv/100)**2)
                    res_var.set(f"ИМТ: {bmi:.2f}")
            except: pass

        ttk.Button(left, text="Рассчитать", style="Primary.TButton", command=calc).pack(fill=tk.X, pady=10)
        ttk.Label(frame, textvariable=res_var, font=("Segoe UI", 24, "bold"), background="white").pack(side=tk.RIGHT, padx=50)

    def backup_database(self):
        path = filedialog.asksaveasfilename(defaultextension=".db", filetypes=[("Database", "*.db")])
        if path:
            if self.db.backup_db(path): messagebox.showinfo("Успех", "Резервная копия создана")
            else: messagebox.showerror("Ошибка", "Не удалось создать копию")

    def load_data(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        data = self.db.get_children_summary(self.search_var.get(), self.group_filter_var.get())
        for row in data:
            self.tree.insert("", tk.END, values=(row['id'], row['full_name'], row['group_name']))

    def reset_filters(self):
        self.search_var.set("")
        self.group_filter_var.set("Все")
        self.load_data()

    def export_to_excel(self):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            data = [self.tree.item(i, "values") for i in self.tree.get_children()]
            try:
                pd.DataFrame(data, columns=["ID", "ФИО", "Группа"]).to_excel(path, index=False)
                messagebox.showinfo("Успех", "Файл сохранен")
            except Exception as e: messagebox.showerror("Ошибка", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = KindergartenApp(root)
    root.mainloop()
