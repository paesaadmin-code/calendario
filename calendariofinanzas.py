import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import json
import calendar
import os
import sys
from datetime import datetime, date, timedelta
import uuid

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ================== CONFIGURACIÓN BÁSICA ==================

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


def T():
    return None


STYLE = {
    "bg_app": "#F3F4F6",
    "white": "#FFFFFF",
    "text_main": "#111827",
    "text_light": "#6B7280",
    "primary": "#1D4ED8",
    "primary_soft": "#DBEAFE",
    "success_soft": "#DCFCE7",
    "warn_soft": "#FEF9C3",
    "danger_soft": "#FEE2E2",
    "success": "#16A34A",
    "warn": "#F59E0B",
    "danger": "#DC2626",
    "header_soft": "#E5E7EB",
    "line": "#D1D5DB",
}


CAT_ICONS = {
    "CREDIT CARD": "💳",
    "PERSONAL LOAN": "📄",
    "SERVICE": "🧾",
    "STREAMING": "🎬",
    "SUPERMARKET": "🛒",
    "RESTAURANT": "🍽️",
    "SAVINGS": "💰",
    "OTHER": "📌",
}


def get_cat_icon(cat):
    return CAT_ICONS.get((cat or "OTHER").upper(), "📌")


def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = name.upper()
    rep = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "Ä": "A", "Ë": "E", "Ï": "I", "Ö": "O", "Ü": "U",
        "'": "", ".": "", ",": ""
    }
    for a, b in rep.items():
        name = name.replace(a, b)
    name = "".join(ch for ch in name if ch.isalnum() or ch == " ")
    name = " ".join(name.split())
    return name


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def parse_date_ymd(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def ym_from_date_str(s: str) -> str:
    if not s or len(s) < 7:
        return ""
    return s[:7]


def clamp_day(year: int, month: int, day: int) -> int:
    return min(day, calendar.monthrange(year, month)[1])


# ================== APP PRINCIPAL ==================

class PagoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Finance Pro - Simple Banking")
        self.geometry("1500x900")
        self.minsize(1200, 750)
        self.configure(fg_color=STYLE["bg_app"])

        # Paths - MOVED TO TOP BEFORE CACHE
        if getattr(sys, "frozen", False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        self.ruta_datos = os.path.join(self.base_path, "finanzas_v4.json")
        self.ruta_config = os.path.join(self.base_path, "config.json")
        self.backup_dir = os.path.join(self.base_path, "backups")

        # Cache de rendimiento
        self._cache_month_key = None
        self._cache_month_data = {}

        # Debounce del buscador (rendimiento)
        self._search_after_id = None

        # Catálogos
        self.categorias_pago = ["CREDIT CARD", "PERSONAL LOAN", "SERVICE", "OTHER"]
        self.categorias_compra = [
            "SUPERMARKET", "RESTAURANT", "LEISURE", "STREAMING",
            "HEALTH", "CLOTHES", "TRANSPORT", "SAVINGS"
        ]
        self.metodos = ["CASH", "CREDIT CARD", "DEBIT CARD", "TRANSFER"]
        self.frecuencias = ["WEEKLY", "BIWEEKLY", "MONTHLY"]

        # Datos
        self.pagos = []
        self.compras = []
        self.weekly_salary = 0.0
        self.salary_history = {}
        self.budgets = {}
        self.savings_goals = []

        # Estado UI
        self.hoy = date.today()
        self.mes_vis = self.hoy.month
        self.anio_vis = self.hoy.year
        self.fecha_seleccionada = self.hoy.strftime("%Y-%m-%d")
        self._last_month = None

        # view_mode: DASH, MONTH, DAY, SEARCH
        self.view_mode = "DASH"

        # Cargar datos antes de UI
        self.cargar_datos()
        self.cargar_config()

        # UI
        self.setup_ui()

        # Recurrentes antes de render
        self.ensure_recurrent_instances()

        # Render inicial
        self.actualizar_vistas()

    # ================== CARGA Y GUARDADO ==================

    def cargar_datos(self):
        try:
            with open(self.ruta_datos, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.pagos = d.get("pagos", [])
            self.compras = d.get("compras", [])
        except Exception:
            self.pagos, self.compras = [], []

    def guardar_datos(self):
        data = {"pagos": self.pagos, "compras": self.compras}
        with open(self.ruta_datos, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.auto_backup(silent=True)
        self._cache_month_key = None

    def auto_backup(self, silent=False):
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self.backup_dir, f"finanzas_backup_{ts}.json")
            if os.path.exists(self.ruta_datos):
                with open(self.ruta_datos, "r", encoding="utf-8") as src, open(backup_file, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            if not silent:
                messagebox.showinfo("Backup", f"Backup creado:\n{backup_file}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Backup", f"Error creando backup:\n{e}")

    def cargar_config(self):
        try:
            with open(self.ruta_config, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.weekly_salary = float(d.get("salary", 0.0))
            self.salary_history = d.get("salary_history", {})
            self.budgets = d.get("budgets", {})
            self.savings_goals = d.get("savings_goals", [])
            if not self.salary_history:
                self.salary_history["2020-01-01"] = float(self.weekly_salary or 0.0)
        except Exception:
            self.weekly_salary = 0.0
            self.salary_history = {"2020-01-01": 0.0}
            self.budgets = {}
            self.savings_goals = []

    def guardar_config(self):
        data = {
            "salary": self.weekly_salary,
            "salary_history": self.salary_history,
            "budgets": self.budgets,
            "savings_goals": self.savings_goals,
        }
        with open(self.ruta_config, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ================== CACHE MANAGEMENT ==================

    def get_month_cache(self):
        key = f"{self.anio_vis}-{self.mes_vis:02d}"
        if self._cache_month_key == key:
            return self._cache_month_data

        data = {
            "items": [],
            "by_day": {},
            "spent_by_cat": {},
            "total": 0.0,
        }

        for x in (self.pagos + self.compras):
            if x.get("status", "PENDING") == "PAID":
                continue
            if not str(x.get("fecha", "")).startswith(key):
                continue

            data["items"].append(x)
            data["total"] += safe_float(x.get("monto", 0))

            f = x.get("fecha")
            data["by_day"].setdefault(f, []).append(x)

            cat = x.get("categoria", "OTHER")
            data["spent_by_cat"][cat] = data["spent_by_cat"].get(cat, 0) + safe_float(x.get("monto", 0))

        self._cache_month_key = key
        self._cache_month_data = data
        return data

    # ================== UI PRINCIPAL ==================

    def setup_ui(self):
        header = ctk.CTkFrame(self, fg_color=STYLE["white"], corner_radius=0, height=60)
        header.pack(fill="x", side="top")

        self.lbl_mes = ctk.CTkLabel(
            header, text="", font=("Segoe UI", 22, "bold"), text_color=STYLE["primary"]
        )
        self.lbl_mes.pack(side="left", padx=20)

        # Navegación
        nav = ctk.CTkFrame(header, fg_color=T())
        nav.pack(side="left", padx=10)
        ctk.CTkButton(nav, text="◀", width=40, command=self.atras).pack(side="left", padx=2)
        ctk.CTkButton(nav, text="Hoy", width=60, command=self.ir_hoy).pack(side="left", padx=2)
        ctk.CTkButton(nav, text="▶", width=40, command=self.adelante).pack(side="left", padx=2)

        # Buscador
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        search = ctk.CTkEntry(
            header,
            textvariable=self.search_var,
            placeholder_text="🔍 Buscar (nombre, categoría, método, fecha)...",
            width=350,
            height=32,
            corner_radius=16,
        )
        search.pack(side="left", padx=20)

        # Acciones - NO Stats Button
        actions = ctk.CTkFrame(header, fg_color=T())
        actions.pack(side="right", padx=10)

        btn_style = {"height": 32, "corner_radius": 16, "font": ("Segoe UI", 11, "bold")}

        ctk.CTkButton(actions, text="📊 Dashboard", fg_color="#111827",
                      command=self.ir_dashboard, width=120, **btn_style).pack(side="right", padx=3)

        ctk.CTkButton(actions, text="💾 Backup", fg_color="#0EA5E9",
                      command=self.auto_backup, width=90, **btn_style).pack(side="right", padx=3)

        ctk.CTkButton(actions, text="💰 Salary", fg_color="#6366F1",
                      command=self.set_salary, width=90, **btn_style).pack(side="right", padx=3)

        ctk.CTkButton(actions, text="📋 Budgets", fg_color="#EC4899",
                      command=self.manage_budgets, width=90, **btn_style).pack(side="right", padx=3)

        ctk.CTkButton(actions, text="🧾 Pay", fg_color="#3B82F6",
                      command=self.abrir_ventana_pago, width=80, **btn_style).pack(side="right", padx=3)

        ctk.CTkButton(actions, text="🛒 Buy", fg_color="#10B981",
                      command=self.abrir_ventana_compra, width=80, **btn_style).pack(side="right", padx=3)

        ctk.CTkButton(actions, text="💸 Save", fg_color="#059669",
                      command=self.abrir_ventana_ahorro, width=80, **btn_style).pack(side="right", padx=3)

        ctk.CTkButton(actions, text="🧨 Reset", fg_color="#EF4444",
                      command=self.confirmar_reset, width=80, **btn_style).pack(side="right", padx=3)

        # Cuerpo
        self.body = ctk.CTkFrame(self, fg_color=STYLE["bg_app"])
        self.body.pack(fill="both", expand=True)

        # Layout base
        self.left = ctk.CTkFrame(self.body, fg_color=STYLE["bg_app"])
        self.left.pack(side="left", fill="both", expand=False, padx=10, pady=10)

        self.right = ctk.CTkFrame(self.body, fg_color=STYLE["bg_app"])
        self.right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.cal_frame = ctk.CTkFrame(self.left, fg_color=STYLE["white"], corner_radius=12)
        self.cal_frame.pack(fill="both", expand=True)

        self.detail_frame = ctk.CTkFrame(self.right, fg_color=STYLE["white"], corner_radius=12)
        self.detail_frame.pack(fill="both", expand=True)

        # Calendario grid
        self.init_calendar_grid()

    # ================== ROUTER DE VISTAS ==================

    def ir_dashboard(self):
        self.view_mode = "DASH"
        self.actualizar_vistas()

    def ir_mes(self):
        self.view_mode = "MONTH"
        self.actualizar_vistas()

    def ir_dia(self):
        self.view_mode = "DAY"
        self.actualizar_vistas()

    def actualizar_vistas(self):
        """FIXED: Proper indentation"""
        self.ensure_recurrent_instances()

        self.lbl_mes.configure(text=f"{calendar.month_name[self.mes_vis]} {self.anio_vis}")

        if getattr(self, "_last_month", None) != (self.anio_vis, self.mes_vis):
            self.update_calendar()
            self._last_month = (self.anio_vis, self.mes_vis)

        self.update_detail()

    # ================== BALANCE Y CÁLCULOS ==================

    def calcular_balance_mensual(self):
        """
        Balance mensual usando salario semanal.
        """
        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"

        gastos = 0.0
        for x in (self.pagos + self.compras):
            if str(x.get("fecha", "")).startswith(mes_prefix) and x.get("status", "PENDING") != "PAID":
                gastos += safe_float(x.get("monto", 0.0))

        semanas_mes = len(calendar.monthcalendar(self.anio_vis, self.mes_vis))
        ingreso = safe_float(self.weekly_salary, 0.0) * semanas_mes
        balance = ingreso - gastos
        return ingreso, gastos, balance, semanas_mes

    def _kpi_color_balance(self, balance):
        return STYLE["success"] if balance >= 0 else STYLE["danger"]

    def _kpi_color_gastos(self, gastos, ingreso):
        if ingreso <= 0:
            return STYLE["warn"]
        ratio = gastos / ingreso
        if ratio < 0.6:
            return STYLE["success"]
        if ratio < 0.9:
            return STYLE["warn"]
        return STYLE["danger"]

    def _kpi_color_budget(self, pct):
        if pct < 0:
            return STYLE["text_light"]
        if pct < 0.7:
            return STYLE["success"]
        if pct < 1.0:
            return STYLE["warn"]
        return STYLE["danger"]

    def _compute_budget_usage_month(self):
        """
        Devuelve spent_by_cat y pct_global
        """
        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"
        spent_by_cat = {}

        for x in (self.pagos + self.compras):
            if x.get("status", "PENDING") == "PAID":
                continue
            if not str(x.get("fecha", "")).startswith(mes_prefix):
                continue
            cat = x.get("categoria", "OTHER")
            spent_by_cat[cat] = spent_by_cat.get(cat, 0.0) + safe_float(x.get("monto", 0.0))

        if not self.budgets:
            return spent_by_cat, -1.0

        total_budget = 0.0
        total_spent_in_budgeted = 0.0
        for cat, lim in self.budgets.items():
            limf = safe_float(lim, 0.0)
            if limf <= 0:
                continue
            total_budget += limf
            total_spent_in_budgeted += spent_by_cat.get(cat, 0.0)

        if total_budget <= 0:
            return spent_by_cat, -1.0

        return spent_by_cat, (total_spent_in_budgeted / total_budget)

    def _compute_upcoming_10d(self):
        hoy = date.today()
        limite = hoy + timedelta(days=10)

        proximos = []
        for p in self.pagos:
            if p.get("status", "PENDING") == "PAID":
                continue
            f = parse_date_ymd(p.get("fecha", ""))
            if not f:
                continue
            if hoy <= f <= limite:
                proximos.append(p)

        proximos.sort(key=lambda x: x.get("fecha", ""))
        total = sum(safe_float(x.get("monto", 0.0)) for x in proximos)
        return proximos, total

    def update_detail(self):
        for w in self.detail_frame.winfo_children():
            w.destroy()

        container = ctk.CTkFrame(self.detail_frame, fg_color=T())
        container.pack(fill="both", expand=True, padx=10, pady=10)

        if self.view_mode == "DASH":
            self.render_dashboard(container)
            return

        if self.view_mode == "SEARCH":
            self.render_busqueda_editable(container)
            return

        self.render_proximos_pagos(container)
        self.render_resumen_mensual(container)
        self.render_detalle_dia(container)

    def render_dashboard(self, parent):
        """
        Dashboard: KPIs + Upcoming Payments + Category Resume
        FIXED: Proper alignment for upcoming payments
        """
        cache = self.get_month_cache()
        gastos = cache["total"]
        spent_by_cat = cache["spent_by_cat"]

        ingreso, _, balance, semanas_mes = self.calcular_balance_mensual()
        spent_by_cat_all, pct_budget = self._compute_budget_usage_month()
        proximos, total_prox = self._compute_upcoming_10d()

        # ===== Barra de KPIs =====
        kpi_row = ctk.CTkFrame(parent, fg_color=T())
        kpi_row.pack(fill="x", pady=(0, 12))

        def kpi_card(title, value, subtitle="", color=STYLE["primary"]):
            card = ctk.CTkFrame(kpi_row, fg_color=STYLE["white"], corner_radius=12, border_width=1, border_color=STYLE["line"])
            card.pack(side="left", expand=True, fill="x", padx=6)

            ctk.CTkLabel(card, text=title, font=("Segoe UI", 11, "bold"), text_color=STYLE["text_light"]).pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(card, text=value, font=("Segoe UI", 18, "bold"), text_color=color).pack(anchor="w", padx=12, pady=(0, 0))
            if subtitle:
                ctk.CTkLabel(card, text=subtitle, font=("Segoe UI", 10), text_color=STYLE["text_light"]).pack(anchor="w", padx=12, pady=(0, 10))
            else:
                ctk.CTkLabel(card, text="", font=("Segoe UI", 10), text_color=STYLE["text_light"]).pack(anchor="w", padx=12, pady=(0, 10))

        kpi_card("Ingreso estimado", fmt_money(ingreso), f"Salario semanal × {semanas_mes} semanas", STYLE["success"])
        kpi_card("Gastos del mes", fmt_money(gastos), "Pagos + compras (pendientes)", self._kpi_color_gastos(gastos, ingreso))
        kpi_card("Balance", fmt_money(balance), "Ingreso − gastos", self._kpi_color_balance(balance))

        if pct_budget < 0:
            pct_txt = "Sin budgets"
            pct_color = STYLE["text_light"]
        else:
            pct_txt = f"{pct_budget * 100:.0f}% usado"
            pct_color = self._kpi_color_budget(pct_budget)

        kpi_card("Budgets", pct_txt, "Uso global mensual", pct_color)

        # ===== Fila 2: Próximos pagos + Category Resume =====
        row2 = ctk.CTkFrame(parent, fg_color=T())
        row2.pack(fill="both", expand=True, pady=(12, 0))

        left = ctk.CTkFrame(row2, fg_color=STYLE["white"], corner_radius=12, border_width=1, border_color=STYLE["line"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right = ctk.CTkFrame(row2, fg_color=STYLE["white"], corner_radius=12, border_width=1, border_color=STYLE["line"])
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        # ---- Próximos pagos ----
        header = ctk.CTkFrame(left, fg_color=STYLE["header_soft"], corner_radius=12)
        header.pack(fill="x")
        ctk.CTkLabel(
            header, text="🔔 Próximos pagos (10 días)",
            font=("Segoe UI", 14, "bold"), text_color=STYLE["text_main"]
        ).pack(anchor="w", padx=12, pady=8)

        ctk.CTkFrame(left, fg_color=STYLE["line"], height=1).pack(fill="x")

        if not proximos:
            ctk.CTkLabel(left, text="No hay pagos próximos.", text_color=STYLE["text_light"]).pack(anchor="w", padx=12, pady=12)
        else:
            ctk.CTkLabel(
                left,
                text=f"Total: {fmt_money(total_prox)}",
                font=("Segoe UI", 12, "bold"),
                text_color=STYLE["text_main"]
            ).pack(anchor="w", padx=12, pady=(10, 6))

            sc = ctk.CTkScrollableFrame(left, fg_color=T())
            sc.pack(fill="both", expand=True, padx=10, pady=(0, 10))

            for p in proximos[:20]:
                fecha_obj = parse_date_ymd(p.get("fecha", ""))
                fecha_txt = fecha_obj.strftime("%d %b").upper() if fecha_obj else str(p.get("fecha", ""))
                icon = get_cat_icon(p.get("categoria"))
                nombre = p.get("nombre") or p.get("item") or ""
                monto = safe_float(p.get("monto", 0))

                r = ctk.CTkFrame(sc, fg_color=STYLE["white"], corner_radius=10, border_width=1, border_color=STYLE["line"])
                r.pack(fill="x", pady=6)

                # FIXED: Better alignment with fixed widths
                ctk.CTkLabel(r, text=f"{fecha_txt}", width=70, anchor="w", font=("Segoe UI", 10)).pack(side="left", padx=5, pady=8)
                ctk.CTkLabel(r, text=icon, width=30, anchor="center").pack(side="left", pady=8)
                ctk.CTkLabel(r, text=nombre[:20], anchor="w", font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, padx=5, pady=8)
                ctk.CTkLabel(r, text=fmt_money(monto), width=100, anchor="e", font=("Segoe UI", 10, "bold")).pack(side="left", padx=5, pady=8)
                ctk.CTkButton(
                    r, text="Pagar", width=70, height=28,
                    fg_color="#D1D5DB", text_color=STYLE["text_main"],
                    hover_color="#9CA3AF",
                    command=lambda p=p: self.marcar_pagado(p)
                ).pack(side="right", padx=5, pady=8)

        # ---- Category Resume ----
        header2 = ctk.CTkFrame(right, fg_color=STYLE["header_soft"], corner_radius=12)
        header2.pack(fill="x")
        ctk.CTkLabel(
            header2, text="📊 Resumen por categoría",
            font=("Segoe UI", 14, "bold"), text_color=STYLE["text_main"]
        ).pack(anchor="w", padx=12, pady=8)

        ctk.CTkFrame(right, fg_color=STYLE["line"], height=1).pack(fill="x")

        if not spent_by_cat_all:
            ctk.CTkLabel(right, text="Sin gastos en este mes.", text_color=STYLE["text_light"]).pack(anchor="w", padx=12, pady=12)
        else:
            scroll = ctk.CTkScrollableFrame(right, fg_color=T())
            scroll.pack(fill="both", expand=True, padx=10, pady=10)

            for cat, amount in sorted(spent_by_cat_all.items(), key=lambda x: x[1], reverse=True):
                row = ctk.CTkFrame(scroll, fg_color=T())
                row.pack(fill="x", pady=4)

                ctk.CTkLabel(row, text=f"{get_cat_icon(cat)} {cat}", width=250, anchor="w", font=("Segoe UI", 11)).pack(side="left")
                ctk.CTkLabel(row, text=fmt_money(amount), width=120, anchor="e", font=("Segoe UI", 11, "bold")).pack(side="left")

        # ===== Buttons ===== (ONLY 2 BUTTONS - NO DUPLICATES)
        buttons_row = ctk.CTkFrame(parent, fg_color=T())
        buttons_row.pack(fill="x", pady=(12, 0))

        ctk.CTkButton(buttons_row, text="📋 Ver todos los items del mes", fg_color="#111827", 
                     command=self.abrir_vista_mes_completa, height=34, corner_radius=14).pack(side="left", padx=5)
        ctk.CTkButton(buttons_row, text="📌 Ir a día seleccionado", fg_color="#111827", 
                     command=self.ir_dia, height=34, corner_radius=14).pack(side="left", padx=5)

    # ================== VER TODOS LOS ITEMS DEL MES ==================

    def abrir_vista_mes_completa(self):
        """Open a window showing all items for the selected month"""
        v = ctk.CTkToplevel(self)
        v.title(f"Todos los items - {calendar.month_name[self.mes_vis]} {self.anio_vis}")
        v.geometry("800x600")
        v.attributes("-topmost", True)

        header = ctk.CTkFrame(v, fg_color=STYLE["white"])
        header.pack(fill="x")
        ctk.CTkLabel(
            header, text=f"📅 {calendar.month_name[self.mes_vis]} {self.anio_vis}",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", padx=12, pady=10)

        scroll = ctk.CTkScrollableFrame(v, fg_color=T())
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"
        items = [
            x for x in (self.pagos + self.compras)
            if str(x.get("fecha", "")).startswith(mes_prefix)
            and x.get("status", "PENDING") != "PAID"
        ]

        if not items:
            ctk.CTkLabel(scroll, text="Sin items en este mes.", text_color=STYLE["text_light"]).pack(pady=20)
            return

        # Group by date
        items_by_date = {}
        for item in items:
            fecha = item.get("fecha", "")
            if fecha not in items_by_date:
                items_by_date[fecha] = []
            items_by_date[fecha].append(item)

        for fecha in sorted(items_by_date.keys()):
            date_header = ctk.CTkFrame(scroll, fg_color=STYLE["primary_soft"], corner_radius=8)
            date_header.pack(fill="x", pady=(10, 5))
            
            fecha_obj = parse_date_ymd(fecha)
            fecha_display = fecha_obj.strftime("%A, %d %B").upper() if fecha_obj else fecha
            ctk.CTkLabel(date_header, text=fecha_display, font=("Segoe UI", 12, "bold"), 
                        text_color=STYLE["primary"]).pack(anchor="w", padx=12, pady=8)

            for it in items_by_date[fecha]:
                row = ctk.CTkFrame(scroll, fg_color=STYLE["white"], corner_radius=8, border_width=1, border_color=STYLE["line"])
                row.pack(fill="x", pady=4, padx=5)

                icon = get_cat_icon(it.get("categoria"))
                name = it.get("nombre") or it.get("item") or "SIN NOMBRE"
                monto = safe_float(it.get("monto", 0))
                status = "✓ PAGADO" if it.get("status") == "PAID" else "⏳ PENDIENTE"

                ctk.CTkLabel(row, text=icon, width=30).pack(side="left", padx=5, pady=8)
                ctk.CTkLabel(row, text=name, width=300, anchor="w").pack(side="left", padx=5, pady=8)
                ctk.CTkLabel(row, text=fmt_money(monto), width=120, anchor="e").pack(side="left", padx=5, pady=8)
                ctk.CTkLabel(row, text=status, width=120, anchor="e", text_color=STYLE["success"] if it.get("status") == "PAID" else STYLE["warn"]).pack(side="left", padx=5, pady=8)

    # ================== CALENDARIO AVANZADO ==================

    def init_calendar_grid(self):
        header_days = ctk.CTkFrame(self.cal_frame, fg_color=T())
        header_days.pack(fill="x", padx=10, pady=(10, 5))

        for d in ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]:
            ctk.CTkLabel(
                header_days, text=d,
                font=("Segoe UI", 10, "bold"),
                text_color=STYLE["text_light"]
            ).pack(side="left", expand=True)

        self.cal_grid = ctk.CTkFrame(self.cal_frame, fg_color=T())
        self.cal_grid.pack(fill="both", expand=True, padx=8, pady=8)

        for i in range(7):
            self.cal_grid.columnconfigure(i, weight=1)
        for i in range(6):
            self.cal_grid.rowconfigure(i, weight=1)

    def update_calendar(self):
        for w in self.cal_grid.winfo_children():
            w.destroy()

        weeks = calendar.Calendar(6).monthdayscalendar(self.anio_vis, self.mes_vis)
        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"

        cache = self.get_month_cache()
        mapa_items = cache["by_day"]

        for r, week in enumerate(weeks):
            for c, day in enumerate(week):
                if day == 0:
                    continue

                f_str = f"{self.anio_vis}-{self.mes_vis:02d}-{day:02d}"
                is_today = (f_str == self.hoy.strftime("%Y-%m-%d"))
                is_selected = (f_str == self.fecha_seleccionada)

                total_day = sum(safe_float(x.get("monto", 0)) for x in mapa_items.get(f_str, []))

                if total_day == 0:
                    bg = STYLE["white"]
                elif total_day < 500:
                    bg = STYLE["success_soft"]
                elif total_day < 2000:
                    bg = STYLE["warn_soft"]
                else:
                    bg = STYLE["danger_soft"]

                border_w = 2 if is_selected else 1
                border_c = STYLE["primary"] if is_selected else STYLE["line"]

                cell = ctk.CTkFrame(
                    self.cal_grid, fg_color=bg, corner_radius=10,
                    border_width=border_w, border_color=border_c
                )
                cell.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

                num_color = STYLE["primary"] if is_today else STYLE["text_main"]
                ctk.CTkLabel(
                    cell, text=str(day),
                    font=("Segoe UI", 11, "bold"),
                    text_color=num_color
                ).pack(anchor="nw", padx=5, pady=3)

                for item in mapa_items.get(f_str, [])[:3]:
                    cat = item.get("categoria", "OTHER")
                    icon = get_cat_icon(cat)
                    name = item.get("nombre") or item.get("item") or "ITEM"
                    ctk.CTkLabel(
                        cell,
                        text=f"{icon} {name[:12]} {fmt_money(safe_float(item.get('monto', 0)))}",
                        font=("Segoe UI", 9),
                        text_color=STYLE["text_main"],
                    ).pack(anchor="w", padx=5)

                if len(mapa_items.get(f_str, [])) > 3:
                    ctk.CTkButton(
                        cell,
                        text=f"Ver todo (+{len(mapa_items[f_str]) - 3})",
                        height=22,
                        fg_color="#E5E7EB",
                        text_color=STYLE["text_main"],
                        hover_color="#D1D5DB",
                        command=lambda f=f_str: self.abrir_detalle_dia(f)
                    ).pack(anchor="w", padx=5, pady=(2, 4))

                btn = ctk.CTkButton(
                    cell, text="", fg_color=T(), hover_color="#E5E7EB",
                    command=lambda f=f_str: self.seleccionar_dia(f)
                )
                btn.place(relx=0, rely=0, relwidth=1, relheight=1)
                btn.lower()

    def seleccionar_dia(self, f):
        self.fecha_seleccionada = f
        self.view_mode = "DAY"
        self.update_calendar()
        self.update_detail()

    # ================== VENTANA "VER TODO" DEL DÍA ==================

    def abrir_detalle_dia(self, fecha):
        v = ctk.CTkToplevel(self)
        v.title(f"Movimientos del {fecha}")
        v.geometry("700x520")
        v.attributes("-topmost", True)

        header = ctk.CTkFrame(v, fg_color=STYLE["white"])
        header.pack(fill="x")
        ctk.CTkLabel(
            header, text=f"📅 {fecha}",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", padx=12, pady=10)

        scroll = ctk.CTkScrollableFrame(v, fg_color=T())
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        items = [
            x for x in (self.pagos + self.compras)
            if x.get("fecha") == fecha and x.get("status", "PENDING") != "PAID"
        ]

        if not items:
            ctk.CTkLabel(scroll, text="Sin movimientos.", text_color=STYLE["text_light"]).pack(pady=20)
            return

        for it in items[:]:  # Use slice to avoid modification during iteration
            row = ctk.CTkFrame(scroll, fg_color=STYLE["white"], corner_radius=10, border_width=1, border_color=STYLE["line"])
            row.pack(fill="x", pady=6)

            name_var = tk.StringVar(value=it.get("nombre") or it.get("item") or "")
            monto_var = tk.StringVar(value=str(it.get("monto", "")))
            fecha_var = tk.StringVar(value=it.get("fecha", ""))

            top = ctk.CTkFrame(row, fg_color=T())
            top.pack(fill="x", padx=10, pady=(8, 0))

            ctk.CTkLabel(top, text=get_cat_icon(it.get("categoria")), width=30).pack(side="left")
            ctk.CTkEntry(top, textvariable=name_var, width=260).pack(side="left", padx=5)
            ctk.CTkEntry(top, textvariable=monto_var, width=120).pack(side="left", padx=5)
            ctk.CTkEntry(top, textvariable=fecha_var, width=120).pack(side="left", padx=5)

            bottom = ctk.CTkFrame(row, fg_color=T())
            bottom.pack(fill="x", padx=10, pady=(0, 8))

            def guardar(it=it, row=row):
                it["monto"] = safe_float(monto_var.get())
                it["fecha"] = fecha_var.get()
                if "nombre" in it:
                    it["nombre"] = name_var.get().upper()
                else:
                    it["item"] = name_var.get().upper()
                self.guardar_datos()
                self.actualizar_vistas()
                row.destroy()

            def eliminar(it=it, row=row):
                # FIXED: Properly remove from list and refresh
                if it in self.pagos:
                    self.pagos.remove(it)
                elif it in self.compras:
                    self.compras.remove(it)
                self.guardar_datos()
                self.actualizar_vistas()
                row.destroy()

            if it in self.pagos:
                ctk.CTkButton(
                    bottom, text="Pagar",
                    fg_color="#D1D5DB", text_color=STYLE["text_main"],
                    hover_color="#9CA3AF",
                    command=lambda it=it: self.marcar_pagado(it)
                ).pack(side="left", padx=5)

            ctk.CTkButton(bottom, text="💾 Guardar", command=guardar).pack(side="right", padx=5)
            ctk.CTkButton(bottom, text="🗑️ Eliminar", fg_color=STYLE["danger"], command=eliminar).pack(side="right", padx=5)

    # ================== BUSCADOR EDITABLE ==================

    def on_search_change(self, *_):
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(250, self._apply_search)

    def _apply_search(self):
        text = self.search_var.get().strip()
        self.view_mode = "SEARCH" if text else "MONTH"
        self.update_detail()

    def render_busqueda_editable(self, parent):
        q = self.search_var.get().strip().upper()

        ctk.CTkLabel(
            parent, text=f"🔍 Resultados de búsqueda",
            font=("Segoe UI", 16, "bold"),
            text_color=STYLE["text_main"]
        ).pack(anchor="w", pady=(0, 10))

        outer = ctk.CTkFrame(parent, fg_color=T())
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=STYLE["bg_app"], highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)

        v_scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        v_scroll.pack(side="right", fill="y")

        h_scroll = ttk.Scrollbar(parent, orient="horizontal", command=canvas.xview)
        h_scroll.pack(fill="x")

        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        inner = ctk.CTkFrame(canvas, fg_color=T())
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _on_configure)

        items = []
        for x in (self.pagos + self.compras):
            blob = " ".join(str(v) for v in x.values()).upper()
            if q in blob:
                items.append(x)

        if not items:
            ctk.CTkLabel(inner, text="Sin resultados.", text_color=STYLE["text_light"]).pack(pady=20)
            return

        for it in items[:]:  # Use slice to avoid modification during iteration
            row = ctk.CTkFrame(inner, fg_color=STYLE["white"], corner_radius=10, border_width=1, border_color=STYLE["line"])
            row.pack(fill="x", pady=6, padx=6)

            name_var = tk.StringVar(value=it.get("nombre") or it.get("item") or "")
            monto_var = tk.StringVar(value=str(it.get("monto", "")))
            fecha_var = tk.StringVar(value=it.get("fecha", ""))

            top = ctk.CTkFrame(row, fg_color=T())
            top.pack(fill="x", padx=10, pady=(8, 0))

            ctk.CTkLabel(top, text=get_cat_icon(it.get("categoria")), width=30).pack(side="left")
            ctk.CTkEntry(top, textvariable=name_var, width=260).pack(side="left", padx=5)
            ctk.CTkEntry(top, textvariable=monto_var, width=120).pack(side="left", padx=5)
            ctk.CTkEntry(top, textvariable=fecha_var, width=120).pack(side="left", padx=5)

            bottom = ctk.CTkFrame(row, fg_color=T())
            bottom.pack(fill="x", padx=10, pady=(0, 8))

            def guardar(it=it, row=row):
                it["monto"] = safe_float(monto_var.get())
                it["fecha"] = fecha_var.get()
                if "nombre" in it:
                    it["nombre"] = name_var.get().upper()
                else:
                    it["item"] = name_var.get().upper()
                self.guardar_datos()
                self.actualizar_vistas()
                row.destroy()

            def eliminar(it=it, row=row):
                # FIXED: Properly remove from list and refresh
                if it in self.pagos:
                    self.pagos.remove(it)
                elif it in self.compras:
                    self.compras.remove(it)
                self.guardar_datos()
                self.actualizar_vistas()
                row.destroy()

            if it in self.pagos:
                ctk.CTkButton(
                    bottom, text="Pagar",
                    fg_color="#D1D5DB", text_color=STYLE["text_main"],
                    hover_color="#9CA3AF",
                    command=lambda it=it: self.marcar_pagado(it)
                ).pack(side="left", padx=5)

            ctk.CTkButton(bottom, text="💾 Guardar", command=guardar).pack(side="right", padx=5)
            ctk.CTkButton(bottom, text="🗑️ Eliminar", fg_color=STYLE["danger"], command=eliminar).pack(side="right", padx=5)

    def render_resumen_mensual(self, parent):
        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"

        data = [
            x for x in (self.pagos + self.compras)
            if str(x.get("fecha", "")).startswith(mes_prefix)
            and x.get("status", "PENDING") != "PAID"
        ]

        if not data:
            return

        ingreso, gastos, balance, semanas_mes = self.calcular_balance_mensual()

        card = ctk.CTkFrame(parent, fg_color=STYLE["white"], corner_radius=12, border_width=1, border_color=STYLE["line"])
        card.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(
            card, text="📘 Resumen mensual",
            font=("Segoe UI", 16, "bold"), text_color=STYLE["text_main"]
        ).pack(anchor="w", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            card,
            text=f"Ingreso estimado: {fmt_money(ingreso)}  ·  Gastos: {fmt_money(gastos)}  ·  Balance: {fmt_money(balance)}",
            font=("Segoe UI", 12),
            text_color=STYLE["text_light"]
        ).pack(anchor="w", padx=12, pady=(0, 10))

        grupos = {}
        for x in data:
            raw = x.get("nombre") or x.get("item") or ""
            norm = normalize_name(raw)
            grupos[norm] = grupos.get(norm, 0.0) + safe_float(x.get("monto", 0))

        for name, total in sorted(grupos.items(), key=lambda x: x[1], reverse=True):
            row = ctk.CTkFrame(card, fg_color=T())
            row.pack(fill="x", pady=2, padx=12)

            ctk.CTkLabel(row, text=name, width=360, font=("Segoe UI", 12), anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=fmt_money(total), width=140, font=("Segoe UI", 12), anchor="e").pack(side="left")

    def render_proximos_pagos(self, parent):
        pass

    def render_detalle_dia(self, parent):
        pass

    def marcar_pagado(self, pago):
        pago["status"] = "PAID"
        self.guardar_datos()
        self.actualizar_vistas()

    def ensure_recurrent_instances(self):
        templates = [p for p in self.pagos if p.get("recurrente") is True]

        existing = set()
        for p in self.pagos:
            if p.get("generated"):
                existing.add((p.get("parent_id"), p.get("fecha")))

        for tpl in templates:
            tpl_uid = tpl.get("uid")
            if not tpl_uid:
                tpl_uid = str(uuid.uuid4())
                tpl["uid"] = tpl_uid

            start = parse_date_ymd(tpl.get("fecha"))
            if not start:
                continue

            limit = parse_date_ymd(tpl.get("fecha_limite")) or date(self.anio_vis + 2, 12, 31)
            freq = (tpl.get("frecuencia") or "MONTHLY").upper()

            cur = start
            while cur <= limit:
                key = (tpl_uid, cur.strftime("%Y-%m-%d"))
                if key not in existing:
                    self.pagos.append({
                        "uid": str(uuid.uuid4()),
                        "parent_id": tpl_uid,
                        "generated": True,
                        "nombre": tpl.get("nombre", ""),
                        "monto": safe_float(tpl.get("monto", 0)),
                        "fecha": cur.strftime("%Y-%m-%d"),
                        "categoria": tpl.get("categoria", "OTHER"),
                        "metodo": tpl.get("metodo", "CASH"),
                        "status": "PENDING",
                    })
                    existing.add(key)

                if freq == "WEEKLY":
                    cur += timedelta(days=7)
                elif freq == "BIWEEKLY":
                    cur += timedelta(days=14)
                else:
                    y = cur.year + (1 if cur.month == 12 else 0)
                    m = 1 if cur.month == 12 else cur.month + 1
                    d = clamp_day(y, m, cur.day)
                    cur = date(y, m, d)

    def abrir_ventana_pago(self):
        v = ctk.CTkToplevel(self)
        v.title("Nuevo pago")
        v.geometry("360x520")
        v.attributes("-topmost", True)

        en = ctk.CTkEntry(v, placeholder_text="Nombre")
        em = ctk.CTkEntry(v, placeholder_text="Monto")
        ef = ctk.CTkEntry(v)
        ef.insert(0, self.fecha_seleccionada)

        en.pack(pady=5)
        em.pack(pady=5)
        ef.pack(pady=5)

        ec = ctk.CTkComboBox(v, values=self.categorias_pago)
        ec.set("SERVICE")
        ec.pack(pady=5)

        emp = ctk.CTkComboBox(v, values=self.metodos)
        emp.set("CREDIT CARD")
        emp.pack(pady=5)

        vr = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(v, text="Recurrente", variable=vr).pack(pady=5)

        efr = ctk.CTkComboBox(v, values=self.frecuencias)
        efr.set("MONTHLY")
        efr.pack(pady=5)

        el = ctk.CTkEntry(v, placeholder_text="Hasta (YYYY-MM-DD)")
        el.insert(0, f"{self.anio_vis + 1}-12-31")
        el.pack(pady=5)

        def save():
            if not en.get() or not parse_date_ymd(ef.get()):
                messagebox.showerror("Error", "Datos inválidos")
                return
            self.pagos.append({
                "uid": str(uuid.uuid4()),
                "nombre": en.get().upper(),
                "monto": safe_float(em.get()),
                "fecha": ef.get(),
                "categoria": ec.get(),
                "metodo": emp.get(),
                "recurrente": vr.get(),
                "frecuencia": efr.get(),
                "fecha_limite": el.get(),
                "status": "PENDING",
            })
            self.ensure_recurrent_instances()
            self.guardar_datos()
            self.actualizar_vistas()
            v.destroy()

        ctk.CTkButton(v, text="Guardar", command=save).pack(pady=10)

    def abrir_ventana_compra(self):
        v = ctk.CTkToplevel(self)
        v.title("Nueva compra")
        v.geometry("360x420")
        v.attributes("-topmost", True)

        en = ctk.CTkEntry(v, placeholder_text="Concepto")
        em = ctk.CTkEntry(v, placeholder_text="Monto")
        ef = ctk.CTkEntry(v)
        ef.insert(0, self.fecha_seleccionada)

        en.pack(pady=5)
        em.pack(pady=5)
        ef.pack(pady=5)

        ec = ctk.CTkComboBox(v, values=self.categorias_compra)
        ec.set("SUPERMARKET")
        ec.pack(pady=5)

        emp = ctk.CTkComboBox(v, values=self.metodos)
        emp.set("DEBIT CARD")
        emp.pack(pady=5)

        def save():
            if not en.get() or not parse_date_ymd(ef.get()):
                messagebox.showerror("Error", "Datos inválidos")
                return
            self.compras.append({
                "uid": str(uuid.uuid4()),
                "item": en.get().upper(),
                "monto": safe_float(em.get()),
                "fecha": ef.get(),
                "categoria": ec.get(),
                "metodo": emp.get(),
                "status": "PENDING",
            })
            self.guardar_datos()
            self.actualizar_vistas()
            v.destroy()

        ctk.CTkButton(v, text="Guardar", command=save).pack(pady=10)

    def abrir_ventana_ahorro(self):
        v = ctk.CTkToplevel(self)
        v.title("Registrar ahorro")
        v.geometry("320x300")
        v.attributes("-topmost", True)

        en = ctk.CTkEntry(v, placeholder_text="Concepto")
        em = ctk.CTkEntry(v, placeholder_text="Monto")
        ef = ctk.CTkEntry(v)
        ef.insert(0, self.fecha_seleccionada)

        en.pack(pady=5)
        em.pack(pady=5)
        ef.pack(pady=5)

        def save():
            self.compras.append({
                "uid": str(uuid.uuid4()),
                "item": en.get().upper(),
                "monto": safe_float(em.get()),
                "fecha": ef.get(),
                "categoria": "SAVINGS",
                "metodo": "TRANSFER",
                "status": "PENDING",
            })
            self.guardar_datos()
            self.actualizar_vistas()
            v.destroy()

        ctk.CTkButton(v, text="Guardar", command=save).pack(pady=10)

    def manage_budgets(self):
        v = ctk.CTkToplevel(self)
        v.title("Budgets")
        v.geometry("420x520")
        v.attributes("-topmost", True)

        scroll = ctk.CTkScrollableFrame(v)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        entries = {}
        for c in sorted(set(self.categorias_pago + self.categorias_compra)):
            row = ctk.CTkFrame(scroll)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=c, width=180, anchor="w").pack(side="left")
            e = ctk.CTkEntry(row, width=120)
            if c in self.budgets:
                e.insert(0, str(self.budgets[c]))
            e.pack(side="right")
            entries[c] = e

        def save():
            self.budgets.clear()
            for c, e in entries.items():
                if e.get().strip():
                    self.budgets[c] = safe_float(e.get())
            self.guardar_config()
            v.destroy()

        ctk.CTkButton(v, text="Guardar", command=save).pack(pady=10)

    def set_salary(self):
        v = ctk.CTkToplevel(self)
        v.title("Salario semanal")
        v.geometry("300x200")
        v.attributes("-topmost", True)

        e = ctk.CTkEntry(v)
        e.insert(0, str(self.weekly_salary))
        e.pack(pady=20)

        def save():
            self.weekly_salary = safe_float(e.get())
            self.salary_history[datetime.now().strftime("%Y-%m-%d")] = self.weekly_salary
            self.guardar_config()
            self.actualizar_vistas()
            v.destroy()

        ctk.CTkButton(v, text="Guardar", command=save).pack(pady=10)

    def confirmar_reset(self):
        if not messagebox.askyesno("Reset", "¿Borrar todos los datos?"):
            return
        self.pagos.clear()
        self.compras.clear()
        self.guardar_datos()
        self.actualizar_vistas()

    def atras(self):
        self.mes_vis -= 1
        if self.mes_vis == 0:
            self.mes_vis = 12
            self.anio_vis -= 1
        if self.view_mode != "DASH":
            self._last_month = None
            self.view_mode = "MONTH"
        self.actualizar_vistas()

    def adelante(self):
        self.mes_vis += 1
        if self.mes_vis == 13:
            self.mes_vis = 1
            self.anio_vis += 1
        if self.view_mode != "DASH":
            self._last_month = None
            self.view_mode = "MONTH"
        self.actualizar_vistas()

    def ir_hoy(self):
        self.mes_vis = self.hoy.month
        self.anio_vis = self.hoy.year
        self.fecha_seleccionada = self.hoy.strftime("%Y-%m-%d")
        self._last_month = None
        self.view_mode = "DASH"
        self.actualizar_vistas()


# ================== MAIN ==================

if __name__ == "__main__":
    app = PagoApp()
    app.mainloop()
