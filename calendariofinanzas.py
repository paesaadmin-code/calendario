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
import pandas as pd   # ← CORREGIDO: import faltante para export_report

# ================== CONFIGURACIÓN BÁSICA ==================

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")


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
    "LEISURE": "🎮",
    "HEALTH": "🏥",
    "CLOTHES": "👕",
    "TRANSPORT": "🚕",
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
               
        # Cache de rendimiento
        self._cache_month_key = None
        self._cache_month_data = {}
    
        # Debounce del buscador
        self._search_after_id = None

        # Variables que causaban AttributeError
        self._last_month = None
        self.dark_mode = False
    
        # Paths
        if getattr(sys, "frozen", False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        self.ruta_datos = os.path.join(self.base_path, "finanzas_v4.json")
        self.ruta_config = os.path.join(self.base_path, "config.json")
        self.backup_dir = os.path.join(self.base_path, "backups")

        # Catálogos
        self.categorias_pago = ["CREDIT CARD", "PERSONAL LOAN", "SERVICE", "OTHER"]
        self.categorias_compra = [
            "SUPERMARKET", "RESTAURANT", "LEISURE", "STREAMING",
            "HEALTH", "CLOTHES", "TRANSPORT", "SAVINGS"
        ]
        self.metodos = ["CASH", "CREDIT CARD", "DEBIT CARD", "TRANSFER"]

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

        # view_mode: DASH, MONTH, DAY, SEARCH
        self.view_mode = "DASH"

        # Cargar datos antes de UI
        self.cargar_datos()
        self.cargar_config()

        # UI
        self.setup_ui()

        # Render inicial
        self.actualizar_vistas()

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
        self._last_month = None

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

    # ================== UI PRINCIPAL ==================

    def setup_ui(self):
        header = ctk.CTkFrame(self, fg_color=STYLE["white"], corner_radius=0, height=60)
        header.pack(fill="x", side="top")

        self.lbl_mes = ctk.CTkLabel(
            header, text="", font=("Segoe UI", 22, "bold"), text_color=STYLE["primary"]
        )
        self.lbl_mes.pack(side="left", padx=20)

        # Navegación
        nav = ctk.CTkFrame(header, fg_color="transparent")
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

        # Acciones
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right", padx=10)

        btn_style = {"height": 32, "corner_radius": 16, "font": ("Segoe UI", 11, "bold")}

        ctk.CTkButton(actions, text="💾 Backup", fg_color="#0EA5E9",
                      command=self.auto_backup, width=90, **btn_style).pack(side="right", padx=3)

        ctk.CTkButton(actions, text="📊 Stats", fg_color="#F59E0B",
                      command=self.show_statistics, width=80, **btn_style).pack(side="right", padx=3)

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
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        self.left = ctk.CTkFrame(self.body, fg_color="transparent")
        self.left.pack(side="left", fill="both", expand=False, padx=10, pady=10)

        self.right = ctk.CTkFrame(self.body, fg_color="transparent")
        self.right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.cal_frame = ctk.CTkFrame(self.left, fg_color=STYLE["white"], corner_radius=12)
        self.cal_frame.pack(fill="both", expand=True)

        self.detail_frame = ctk.CTkFrame(self.right, fg_color=STYLE["white"], corner_radius=12)
        self.detail_frame.pack(fill="both", expand=True)

        self.init_calendar_grid()

    # ================== NAVEGACIÓN (CORREGIDO) ==================

    def atras(self):
        self.mes_vis -= 1
        if self.mes_vis < 1:
            self.mes_vis = 12
            self.anio_vis -= 1
        self.actualizar_vistas()

    def adelante(self):
        self.mes_vis += 1
        if self.mes_vis > 12:
            self.mes_vis = 1
            self.anio_vis += 1
        self.actualizar_vistas()

    def ir_hoy(self):
        self.mes_vis = self.hoy.month
        self.anio_vis = self.hoy.year
        self.fecha_seleccionada = self.hoy.strftime("%Y-%m-%d")
        self.view_mode = "DASH"
        self.actualizar_vistas()

    # ================== ROUTER DE VISTAS (CORREGIDO) ==================

    def ir_mes(self):
        self.view_mode = "MONTH"
        self.actualizar_vistas()

    def ir_dia(self):
        self.view_mode = "DAY"
        self.actualizar_vistas()

    def actualizar_vistas(self):
        self.lbl_mes.configure(text=f"{calendar.month_name[self.mes_vis]} {self.anio_vis}")

        if getattr(self, "_last_month", None) != (self.anio_vis, self.mes_vis):
            self.update_calendar()
            self._last_month = (self.anio_vis, self.mes_vis)

        self.update_detail()

    # ================== MÉTODOS AUXILIARES ==================

    def calcular_balance_mensual(self):
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

    def marcar_pagado(self, item):
        nombre = item.get("nombre") or item.get("item", "Item")
        if messagebox.askyesno("Marcar Pagado", f"¿Marcar '{nombre}' como PAGADO?"):
            item["status"] = "PAID"
            self.guardar_datos()
            self.actualizar_vistas()

    # ================== VISTAS (CORREGIDO) ==================

    def update_detail(self):
        for w in self.detail_frame.winfo_children():
            w.destroy()

        container = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        if self.view_mode == "DASH":
            self.render_dashboard(container)
        elif self.view_mode == "SEARCH":
            self.render_busqueda_editable(container)
        elif self.view_mode == "MONTH":
            self.render_resumen_mensual(container)
        elif self.view_mode == "DAY":
            self.render_detalle_dia(container)
        else:
            self.render_dashboard(container)

    def render_dashboard(self, parent):
        cache = self.get_month_cache()
        gastos = cache["total"]
        spent_by_cat = cache["spent_by_cat"]

        ingreso, gastos_calc, balance, semanas_mes = self.calcular_balance_mensual()
        spent_by_cat_all, pct_budget = self._compute_budget_usage_month()
        proximos, total_prox = self._compute_upcoming_10d()

        # ===== Barra de KPIs =====
        kpi_row = ctk.CTkFrame(parent, fg_color="transparent")
        kpi_row.pack(fill="x", pady=(0, 12))

        def kpi_card(title, value, subtitle="", color=STYLE["primary"]):
            card = ctk.CTkFrame(parent=kpi_row, fg_color=STYLE["white"], corner_radius=12, border_width=1, border_color=STYLE["line"])
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

        # ===== Fila 2: Próximos pagos + Top categorías =====
        row2 = ctk.CTkFrame(parent, fg_color="transparent")
        row2.pack(fill="both", expand=True)

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

            sc = ctk.CTkScrollableFrame(left, fg_color="transparent")
            sc.pack(fill="both", expand=True, padx=10, pady=(0, 10))

            for p in proximos[:20]:
                fecha_obj = parse_date_ymd(p.get("fecha", ""))
                fecha_txt = fecha_obj.strftime("%d %b").upper() if fecha_obj else str(p.get("fecha", ""))
                icon = get_cat_icon(p.get("categoria"))
                nombre = p.get("nombre") or p.get("item") or ""
                monto = safe_float(p.get("monto", 0))

                r = ctk.CTkFrame(sc, fg_color=STYLE["white"], corner_radius=10, border_width=1, border_color=STYLE["line"])
                r.pack(fill="x", pady=6)

                ctk.CTkLabel(r, text=f"{fecha_txt}", width=90, anchor="w").pack(side="left", padx=(10, 0), pady=8)
                ctk.CTkLabel(r, text=icon, width=40).pack(side="left", pady=8)
                ctk.CTkLabel(r, text=nombre[:30], anchor="w").pack(side="left", fill="x", expand=True, padx=6, pady=8)
                ctk.CTkLabel(r, text=fmt_money(monto), width=120, anchor="e").pack(side="left", padx=6, pady=8)
                ctk.CTkButton(
                    r, text="Pagar", width=80, height=28,
                    fg_color="#D1D5DB", text_color=STYLE["text_main"],
                    hover_color="#9CA3AF",
                    command=lambda p=p: self.marcar_pagado(p)
                ).pack(side="right", padx=10, pady=8)

        # ---- Top categorías del mes ----
        header2 = ctk.CTkFrame(right, fg_color=STYLE["header_soft"], corner_radius=12)
        header2.pack(fill="x")
        ctk.CTkLabel(
            header2, text="📈 Gastos por categoría (mes visible)",
            font=("Segoe UI", 14, "bold"), text_color=STYLE["text_main"]
        ).pack(anchor="w", padx=12, pady=8)

        ctk.CTkFrame(right, fg_color=STYLE["line"], height=1).pack(fill="x")

        if not spent_by_cat:
            ctk.CTkLabel(right, text="Sin gastos para graficar.", text_color=STYLE["text_light"]).pack(anchor="w", padx=12, pady=12)
        else:
            items = sorted(spent_by_cat.items(), key=lambda x: x[1], reverse=True)[:10]
            cats = [k for k, _ in items][::-1]
            vals = [v for _, v in items][::-1]

            fig = plt.Figure(figsize=(5, 3), dpi=100)
            ax = fig.add_subplot(111)
            ax.barh(cats, vals, color="#3B82F6")
            ax.tick_params(axis="y", labelsize=9)
            ax.tick_params(axis="x", labelsize=9)

            canvas = FigureCanvasTkAgg(fig, master=right)
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
            canvas.draw()

        # ===== Atajos inferiores =====
        shortcuts = ctk.CTkFrame(parent, fg_color="transparent")
        shortcuts.pack(fill="x", pady=(12, 0))

        ctk.CTkButton(shortcuts, text="📅 Ver mes detallado", fg_color="#111827", command=self.ir_mes, height=34, corner_radius=14).pack(side="left", padx=5)
        ctk.CTkButton(shortcuts, text="📌 Ir a día seleccionado", fg_color="#111827", command=self.ir_dia, height=34, corner_radius=14).pack(side="left", padx=5)
        
    # ================== CALENDARIO ==================

    def init_calendar_grid(self):
        header_days = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        header_days.pack(fill="x", padx=10, pady=(10, 5))

        for d in ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]:
            ctk.CTkLabel(
                header_days, text=d,
                font=("Segoe UI", 10, "bold"),
                text_color=STYLE["text_light"]
            ).pack(side="left", expand=True)

        self.cal_grid = ctk.CTkFrame(self.cal_frame, fg_color="transparent")
        self.cal_grid.pack(fill="both", expand=True, padx=8, pady=8)

        for i in range(7):
            self.cal_grid.columnconfigure(i, weight=1)
        for i in range(6):
            self.cal_grid.rowconfigure(i, weight=1)

    def update_calendar(self):
        for w in self.cal_grid.winfo_children():
            w.destroy()

        weeks = calendar.Calendar(6).monthdayscalendar(self.anio_vis, self.mes_vis)
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
                lbl_day = ctk.CTkLabel(
                    cell, text=str(day),
                    font=("Segoe UI", 11, "bold"),
                    text_color=num_color
                )
                lbl_day.pack(anchor="nw", padx=5, pady=3)

                cell.bind("<Button-1>", lambda e, f=f_str: self.seleccionar_dia(f))
                lbl_day.bind("<Button-1>", lambda e, f=f_str: self.seleccionar_dia(f))

                for item in mapa_items.get(f_str, [])[:3]:
                    cat = item.get("categoria", "OTHER")
                    icon = get_cat_icon(cat)
                    name = item.get("nombre") or item.get("item") or "ITEM"
                    lbl_item = ctk.CTkLabel(
                        cell,
                        text=f"{icon} {name[:12]} {fmt_money(safe_float(item.get('monto', 0)))}",
                        font=("Segoe UI", 9),
                        text_color=STYLE["text_main"],
                    )
                    lbl_item.pack(anchor="w", padx=5)
                    lbl_item.bind("<Button-1>", lambda e, f=f_str: self.seleccionar_dia(f))

                if len(mapa_items.get(f_str, [])) > 3:
                    lbl_more = ctk.CTkLabel(
                        cell,
                        text=f"+ {len(mapa_items[f_str]) - 3} más...",
                        font=("Segoe UI", 9, "bold"),
                        text_color=STYLE["text_light"]
                    )
                    lbl_more.pack(anchor="w", padx=5, pady=(2, 4))
                    lbl_more.bind("<Button-1>", lambda e, f=f_str: self.seleccionar_dia(f))

    def seleccionar_dia(self, f):
        self.fecha_seleccionada = f
        self.view_mode = "DAY"
        self.update_calendar()
        self.update_detail()

    # ================== BUSCADOR ==================

    def on_search_change(self, *_):
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(400, self._apply_search)

    def _apply_search(self):
        text = self.search_var.get().strip()
        self.view_mode = "SEARCH" if text else "DASH"
        self.update_detail()

    def render_busqueda_editable(self, parent):
        q = self.search_var.get().strip().upper()

        ctk.CTkLabel(
            parent, text=f"🔍 Resultados de búsqueda",
            font=("Segoe UI", 16, "bold"),
            text_color=STYLE["text_main"]
        ).pack(anchor="w", pady=(0, 10))

        items = []
        for x in (self.pagos + self.compras):
            blob = " ".join(str(v) for v in x.values()).upper()
            if q in blob:
                items.append(x)

        if not items:
            ctk.CTkLabel(parent, text="Sin resultados.", text_color=STYLE["text_light"]).pack(pady=20)
            return

        if len(items) > 30:
            ctk.CTkLabel(parent, text=f"Mostrando 30 de {len(items)} resultados.", text_color=STYLE["warn"], font=("Segoe UI", 10, "bold")).pack(pady=5)
            items = items[:30]

        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=STYLE["bg_app"], highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)

        v_scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        v_scroll.pack(side="right", fill="y")

        canvas.configure(yscrollcommand=v_scroll.set)

        inner = ctk.CTkFrame(canvas, fg_color="transparent")
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas.find_withtag("all")[0], width=event.width)

        canvas.bind("<Configure>", _on_configure)
        inner.bind("<Configure>", _on_configure)

        for it in items:
            row = ctk.CTkFrame(inner, fg_color=STYLE["white"], corner_radius=10, border_width=1, border_color=STYLE["line"])
            row.pack(fill="x", pady=4, padx=6)

            name_var = tk.StringVar(value=it.get("nombre") or it.get("item") or "")
            monto_var = tk.StringVar(value=str(it.get("monto", "")))
            fecha_var = tk.StringVar(value=it.get("fecha", ""))

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 0))

            ctk.CTkLabel(top, text=get_cat_icon(it.get("categoria")), width=30).pack(side="left")
            ctk.CTkEntry(top, textvariable=name_var, width=220).pack(side="left", padx=5)
            ctk.CTkEntry(top, textvariable=monto_var, width=100).pack(side="left", padx=5)
            ctk.CTkEntry(top, textvariable=fecha_var, width=100).pack(side="left", padx=5)

            bottom = ctk.CTkFrame(row, fg_color="transparent")
            bottom.pack(fill="x", padx=10, pady=(0, 8))

            def guardar(it=it, name_var=name_var, monto_var=monto_var, fecha_var=fecha_var):
                it["monto"] = safe_float(monto_var.get())
                it["fecha"] = fecha_var.get()
                if "nombre" in it:
                    it["nombre"] = name_var.get().upper()
                else:
                    it["item"] = name_var.get().upper()
                self.guardar_datos()
                self.actualizar_vistas()

            def eliminar(it=it, row=row):
                if messagebox.askyesno("Confirmar", "¿Eliminar este registro?"):
                    if it in self.pagos:
                        self.pagos.remove(it)
                    elif it in self.compras:
                        self.compras.remove(it)
                    self.guardar_datos()
                    row.destroy()
                    self.actualizar_vistas()

            if "nombre" in it and it.get("status") != "PAID":
                ctk.CTkButton(
                    bottom, text="Pagar",
                    fg_color="#D1D5DB", text_color=STYLE["text_main"],
                    hover_color="#9CA3AF", height=24, width=60,
                    command=lambda it=it: self.marcar_pagado(it)
                ).pack(side="left", padx=5)
            elif "nombre" in it:
                ctk.CTkLabel(bottom, text="✓ PAGADO", text_color=STYLE["success"], font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)

            ctk.CTkButton(bottom, text="Guardar", command=guardar, height=24, width=60).pack(side="right", padx=5)
            ctk.CTkButton(bottom, text="Eliminar", fg_color=STYLE["danger"], command=eliminar, height=24, width=60).pack(side="right", padx=5)

    def render_resumen_mensual(self, parent):
        if self.view_mode != "MONTH":
            return
            
        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"
        data = [
            x for x in (self.pagos + self.compras)
            if str(x.get("fecha", "")).startswith(mes_prefix)
            and x.get("status", "PENDING") != "PAID"
        ]

        card = ctk.CTkFrame(parent, fg_color=STYLE["white"], corner_radius=12, border_width=1, border_color=STYLE["line"])
        card.pack(fill="both", expand=True, pady=(0, 15))

        ctk.CTkLabel(
            card, text=f"📘 Resumen Mensual Completo ({calendar.month_name[self.mes_vis]} {self.anio_vis})",
            font=("Segoe UI", 16, "bold"), text_color=STYLE["text_main"]
        ).pack(anchor="w", padx=12, pady=(10, 10))

        if not data:
            ctk.CTkLabel(card, text="No hay transacciones registradas este mes.", text_color=STYLE["text_light"]).pack(pady=20)
            return

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        por_fecha = {}
        for x in data:
            f = x.get("fecha", "")
            por_fecha.setdefault(f, []).append(x)

        for f in sorted(por_fecha.keys()):
            ctk.CTkLabel(scroll, text=f"📅 {f}", font=("Segoe UI", 12, "bold"), text_color=STYLE["primary"]).pack(anchor="w", pady=(10,2))
            for it in por_fecha[f]:
                row = ctk.CTkFrame(scroll, fg_color=STYLE["bg_app"], corner_radius=8)
                row.pack(fill="x", pady=2)
                
                icon = get_cat_icon(it.get("categoria"))
                name = it.get("nombre") or it.get("item") or ""
                
                ctk.CTkLabel(row, text=icon, width=30).pack(side="left", padx=5)
                ctk.CTkLabel(row, text=name[:40], width=250, anchor="w").pack(side="left", fill="x", expand=True)
                ctk.CTkLabel(row, text=it.get("categoria", ""), width=120, anchor="w", text_color=STYLE["text_light"], font=("Segoe UI", 10)).pack(side="left")
                ctk.CTkLabel(row, text=fmt_money(safe_float(it.get("monto", 0))), width=100, anchor="e", font=("Segoe UI", 12, "bold")).pack(side="right", padx=10)

                tipo_obj = 'pago' if 'nombre' in it else 'compra'
                row.bind("<Button-1>", lambda e, x=it, t=tipo_obj: self.editar_item(x, t))
                for child in row.winfo_children():
                    child.bind("<Button-1>", lambda e, x=it, t=tipo_obj: self.editar_item(x, t))

    def render_detalle_dia(self, parent):
        if self.view_mode != "DAY":
            return
            
        card = ctk.CTkFrame(parent, fg_color=STYLE["white"], corner_radius=12, border_width=1, border_color=STYLE["line"])
        card.pack(fill="both", expand=True, pady=(0, 15))

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        
        ctk.CTkLabel(
            header, text=f"📅 Detalle del Día: {self.fecha_seleccionada}",
            font=("Segoe UI", 16, "bold"), text_color=STYLE["text_main"]
        ).pack(side="left")

        ctk.CTkButton(header, text="Cerrar Día", width=80, height=24, fg_color=STYLE["line"], text_color=STYLE["text_main"], hover_color="#9CA3AF", command=self.ir_mes).pack(side="right")

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        items = [
            x for x in (self.pagos + self.compras)
            if x.get("fecha") == self.fecha_seleccionada and x.get("status", "PENDING") != "PAID"
        ]

        if not items:
            ctk.CTkLabel(scroll, text="No hay movimientos en esta fecha.", text_color=STYLE["text_light"]).pack(pady=20)
            return

        for it in items:
            row = ctk.CTkFrame(scroll, fg_color=STYLE["bg_app"], corner_radius=10, border_width=1, border_color=STYLE["line"])
            row.pack(fill="x", pady=6)

            name_var = tk.StringVar(value=it.get("nombre") or it.get("item") or "")
            monto_var = tk.StringVar(value=str(it.get("monto", "")))
            
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 0))

            ctk.CTkLabel(top, text=get_cat_icon(it.get("categoria")), width=30).pack(side="left")
            ctk.CTkEntry(top, textvariable=name_var, width=260).pack(side="left", padx=5, fill="x", expand=True)
            ctk.CTkEntry(top, textvariable=monto_var, width=120).pack(side="right", padx=5)

            bottom = ctk.CTkFrame(row, fg_color="transparent")
            bottom.pack(fill="x", padx=10, pady=(4, 8))

            def guardar(it=it, n_var=name_var, m_var=monto_var):
                it["monto"] = safe_float(m_var.get())
                if "nombre" in it:
                    it["nombre"] = n_var.get().upper()
                else:
                    it["item"] = n_var.get().upper()
                self.guardar_datos()
                self.actualizar_vistas()

            def eliminar(it=it):
                if messagebox.askyesno("Confirmar", "¿Eliminar registro?"):
                    if it in self.pagos:
                        self.pagos.remove(it)
                    elif it in self.compras:
                        self.compras.remove(it)
                    self.guardar_datos()
                    self.actualizar_vistas()

            if "nombre" in it:
                ctk.CTkButton(
                    bottom, text="Marcar Pagado",
                    fg_color=STYLE["success"], text_color=STYLE["white"],
                    height=24, width=100,
                    command=lambda it=it: self.marcar_pagado(it)
                ).pack(side="left", padx=5)

            ctk.CTkButton(bottom, text="Eliminar", fg_color=STYLE["danger"], height=24, width=80, command=eliminar).pack(side="right", padx=5)
            ctk.CTkButton(bottom, text="Guardar", height=24, width=80, command=guardar).pack(side="right", padx=5)

    # ================== BUDGETS ==================

    def manage_budgets(self):
        v = ctk.CTkToplevel(self)
        v.title("Presupuestos y Avances")
        v.geometry("500x600")
        v.attributes("-topmost", True)

        ctk.CTkLabel(v, text="Control de Presupuestos Mensuales", font=("Segoe UI", 16, "bold")).pack(pady=10)
        
        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"
        spent_by_cat = {}
        for x in (self.pagos + self.compras):
            if str(x.get("fecha", "")).startswith(mes_prefix) and x.get("status", "PENDING") != "PAID":
                cat = x.get("categoria", "OTHER")
                spent_by_cat[cat] = spent_by_cat.get(cat, 0.0) + safe_float(x.get("monto", 0.0))

        scroll = ctk.CTkScrollableFrame(v, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        entries = {}
        all_cats = sorted(list(set(self.categorias_pago + self.categorias_compra)))
        
        for c in all_cats:
            row = ctk.CTkFrame(scroll, fg_color=STYLE["white"], corner_radius=8, border_width=1, border_color=STYLE["line"])
            row.pack(fill="x", pady=4, padx=5)

            spent = spent_by_cat.get(c, 0.0)
            budget = self.budgets.get(c, 0.0)

            top_row = ctk.CTkFrame(row, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8,0))

            ctk.CTkLabel(top_row, text=c, width=150, anchor="w", font=("Segoe UI", 12, "bold")).pack(side="left")

            e = ctk.CTkEntry(top_row, width=90, placeholder_text="Límite $")
            if budget > 0:
                e.insert(0, str(budget))
            e.pack(side="right")
            entries[c] = e

            bottom_row = ctk.CTkFrame(row, fg_color="transparent")
            bottom_row.pack(fill="x", padx=10, pady=(4,8))

            if budget > 0:
                pct = spent / budget
                color = STYLE["success"] if pct <= 0.75 else (STYLE["warn"] if pct <= 1.0 else STYLE["danger"])
                txt = f"Gastado: {fmt_money(spent)} / {fmt_money(budget)} ({pct*100:.0f}%)"
                ctk.CTkLabel(bottom_row, text=txt, text_color=color, font=("Segoe UI", 10, "bold")).pack(side="left")

                pb = ctk.CTkProgressBar(bottom_row, height=8, progress_color=color)
                pb.set(min(pct, 1.0))
                pb.pack(side="right", fill="x", expand=True, padx=(10,0))
            else:
                ctk.CTkLabel(bottom_row, text=f"Gastado: {fmt_money(spent)} (Sin límite definido)", text_color=STYLE["text_light"], font=("Segoe UI", 10)).pack(side="left")

        def save():
            self.budgets.clear()
            for c, e in entries.items():
                val = e.get().strip()
                if val and safe_float(val) > 0:
                    self.budgets[c] = safe_float(val)
            self.guardar_config()
            self.actualizar_vistas()
            v.destroy()

        ctk.CTkButton(v, text="Guardar Presupuestos", command=save, fg_color=STYLE["primary"]).pack(pady=10)

    # ================== SALARIO ==================

    def set_salary(self):
        v = ctk.CTkToplevel(self)
        v.title("Salario Semanal")
        v.geometry("300x200")
        v.attributes("-topmost", True)

        ctk.CTkLabel(v, text="Ingresa tu salario semanal:", font=("Segoe UI", 14)).pack(pady=10)
        e = ctk.CTkEntry(v)
        e.insert(0, str(self.weekly_salary))
        e.pack(pady=10)

        def save():
            self.weekly_salary = safe_float(e.get())
            self.salary_history[datetime.now().strftime("%Y-%m-%d")] = self.weekly_salary
            self.guardar_config()
            self.actualizar_vistas()
            v.destroy()

        ctk.CTkButton(v, text="Guardar", command=save).pack(pady=10)

    def confirmar_reset(self):
        if messagebox.askyesno("Reset", "¿Estás seguro de borrar TODOS los datos de compras y pagos?"):
            self.pagos.clear()
            self.compras.clear()
            self.guardar_datos()
            self.actualizar_vistas()

    def export_report(self):
        f = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not f:
            return
        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"
        items = [x for x in (self.pagos + self.compras) if str(x.get("fecha", "")).startswith(mes_prefix)]
        df = pd.DataFrame(items)
        try:
            df.to_csv(f, index=False)
            messagebox.showinfo("Export", "Reporte guardado exitosamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")

    def show_statistics(self):
        v = ctk.CTkToplevel(self)
        v.title("Statistics")
        v.geometry("1000x800")
        v.attributes("-topmost", True)

        tabview = ctk.CTkTabview(v)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        t_over = tabview.add("Overview")
        t_trend = tabview.add("Trends")
        t_comp = tabview.add("Comparison")

        mes_prefix = f"{self.anio_vis}-{self.mes_vis:02d}"
        data = [x for x in (self.pagos + self.compras) if str(x.get("fecha", "")).startswith(mes_prefix) and x.get("status", "PENDING") != "PAID"]

        # Overview (Pie)
        cats = {}
        for x in data:
            cats[x.get("categoria", "OTHER")] = cats.get(x.get("categoria", "OTHER"), 0.0) + float(x.get("monto", 0))

        fig1, ax1 = plt.subplots(figsize=(5, 4))
        if cats:
            ax1.pie(cats.values(), labels=cats.keys(), autopct="%1.1f%%", startangle=90)
        canvas1 = FigureCanvasTkAgg(fig1, master=t_over)
        canvas1.draw()
        canvas1.get_tk_widget().pack(fill="both", expand=True)

        # Trends (Line)
        dates = sorted(list(set([x.get("fecha") for x in data if x.get("fecha")])))
        cum_spend = []
        curr = 0.0
        for d in dates:
            day_sum = sum(float(x.get("monto", 0)) for x in data if x.get("fecha") == d)
            curr += day_sum
            cum_spend.append(curr)

        fig2, ax2 = plt.subplots(figsize=(5, 4))
        ax2.plot(dates, cum_spend, marker="o", color="b")
        ax2.set_title("Cumulative Spending this Month")
        ax2.tick_params(axis="x", rotation=45)
        canvas2 = FigureCanvasTkAgg(fig2, master=t_trend)
        canvas2.draw()
        canvas2.get_tk_widget().pack(fill="both", expand=True)

        # Comparison
        last_m = self.mes_vis - 1 if self.mes_vis > 1 else 12
        last_y = self.anio_vis if self.mes_vis > 1 else self.anio_vis - 1
        last_prefix = f"{last_y}-{last_m:02d}"
        last_data = [x for x in (self.pagos + self.compras) if str(x.get("fecha", "")).startswith(last_prefix) and x.get("status", "PENDING") != "PAID"]

        fig3, ax3 = plt.subplots(figsize=(5, 4))
        ax3.bar(
            ["Mes Anterior", "Este Mes"],
            [sum(float(x.get("monto", 0)) for x in last_data), sum(float(x.get("monto", 0)) for x in data)],
            color=["gray", "blue"],
        )
        canvas3 = FigureCanvasTkAgg(fig3, master=t_comp)
        canvas3.draw()
        canvas3.get_tk_widget().pack(fill="both", expand=True)

    # ================== ALTAS / EDICIÓN ==================

    def abrir_ventana_pago(self):
        v = ctk.CTkToplevel(self)
        v.title("Nuevo Pago")
        v.geometry("360x400")
        v.attributes("-topmost", True)

        ctk.CTkLabel(v, text="Registrar Pago Fijo", font=("Segoe UI", 16, "bold")).pack(pady=15)
        
        en = ctk.CTkEntry(v, placeholder_text="Nombre del Pago")
        em = ctk.CTkEntry(v, placeholder_text="Monto")
        ef = ctk.CTkEntry(v)
        ef.insert(0, self.fecha_seleccionada)

        en.pack(pady=5); em.pack(pady=5); ef.pack(pady=5)

        ec = ctk.CTkComboBox(v, values=self.categorias_pago)
        ec.set("SERVICE")
        ec.pack(pady=5)

        emp = ctk.CTkComboBox(v, values=self.metodos)
        emp.set("CREDIT CARD")
        emp.pack(pady=5)

        def save():
            if not en.get() or not parse_date_ymd(ef.get()):
                messagebox.showerror("Error", "Datos inválidos (Verifica formato de fecha YYYY-MM-DD)")
                return
            self.pagos.append({
                "uid": str(uuid.uuid4()),
                "nombre": en.get().upper(),
                "monto": safe_float(em.get()),
                "fecha": ef.get(),
                "categoria": ec.get(),
                "metodo": emp.get(),
                "status": "PENDING",
            })
            self.guardar_datos()
            self.actualizar_vistas()
            v.destroy()

        ctk.CTkButton(v, text="Guardar Pago", command=save).pack(pady=15)

    def abrir_ventana_compra(self):
        v = ctk.CTkToplevel(self)
        v.title("Nueva Compra")
        v.geometry("360x400")
        v.attributes("-topmost", True)

        ctk.CTkLabel(v, text="Registrar Compra/Gasto", font=("Segoe UI", 16, "bold")).pack(pady=15)
        
        en = ctk.CTkEntry(v, placeholder_text="Nombre del Item")
        em = ctk.CTkEntry(v, placeholder_text="Monto")
        ef = ctk.CTkEntry(v)
        ef.insert(0, self.fecha_seleccionada)

        en.pack(pady=5); em.pack(pady=5); ef.pack(pady=5)

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

        ctk.CTkButton(v, text="Guardar Compra", command=save).pack(pady=15)

    def abrir_ventana_ahorro(self):
        v = ctk.CTkToplevel(self)
        v.title("Nuevo Ahorro")
        v.geometry("360x350")
        v.attributes("-topmost", True)

        ctk.CTkLabel(v, text="Registrar Ahorro", font=("Segoe UI", 16, "bold")).pack(pady=15)
        
        en = ctk.CTkEntry(v, placeholder_text="Concepto del ahorro")
        em = ctk.CTkEntry(v, placeholder_text="Monto ahorrado")
        ef = ctk.CTkEntry(v)
        ef.insert(0, self.fecha_seleccionada)

        en.pack(pady=5); em.pack(pady=5); ef.pack(pady=5)

        def save():
            if not en.get():
                messagebox.showerror("Error", "Ingresa un concepto")
                return
            self.compras.append({
                "uid": str(uuid.uuid4()),
                "item": f"AHORRO - {en.get().upper()}",
                "monto": safe_float(em.get()),
                "fecha": ef.get(),
                "categoria": "SAVINGS",
                "metodo": "TRANSFER",
                "status": "PAID",
            })
            self.guardar_datos()
            self.actualizar_vistas()
            v.destroy()

        ctk.CTkButton(v, text="Guardar Ahorro", command=save).pack(pady=15)

    def editar_item(self, item, tipo):
        v = ctk.CTkToplevel(self)
        v.title("Editar")
        v.geometry("360x450")
        v.attributes("-topmost", True)
        
        ctk.CTkLabel(v, text="Editar Registro", font=("Segoe UI", 16, "bold")).pack(pady=10)

        en = ctk.CTkEntry(v, width=250)
        en.insert(0, item.get("nombre") if tipo == "pago" else item.get("item", ""))
        en.pack(pady=5)

        em = ctk.CTkEntry(v, width=250)
        em.insert(0, str(item.get("monto", "")))
        em.pack(pady=5)

        ef = ctk.CTkEntry(v, width=250)
        ef.insert(0, item.get("fecha", ""))
        ef.pack(pady=5)

        ec = ctk.CTkComboBox(v, values=(self.categorias_pago if tipo == "pago" else self.categorias_compra), width=250)
        ec.set(item.get("categoria", "OTHER"))
        ec.pack(pady=5)

        emp = ctk.CTkComboBox(v, values=self.metodos, width=250)
        emp.set(item.get("metodo", "CASH"))
        emp.pack(pady=5)

        def save_changes():
            if not parse_date_ymd(ef.get()):
                messagebox.showerror("Error", "Fecha inválida")
                return
            item.update({
                "monto": safe_float(em.get()),
                "fecha": ef.get(),
                "categoria": ec.get(),
                "metodo": emp.get(),
            })
            if tipo == "pago":
                item["nombre"] = en.get().upper()
            else:
                item["item"] = en.get().upper()
                
            self.guardar_datos()
            self.actualizar_vistas()
            v.destroy()

        def delete_record():
            if messagebox.askyesno("Confirmar", "¿Eliminar registro permanentemente?"):
                if tipo == "pago" and item in self.pagos:
                    self.pagos.remove(item)
                elif tipo == "compra" and item in self.compras:
                    self.compras.remove(item)
                self.guardar_datos()
                self.actualizar_vistas()
                v.destroy()

        btn_f = ctk.CTkFrame(v, fg_color="transparent")
        btn_f.pack(pady=15)
        ctk.CTkButton(btn_f, text="Guardar Cambios", command=save_changes, width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_f, text="Eliminar", fg_color=STYLE["danger"], command=delete_record, width=100).pack(side="right", padx=5)

if __name__ == "__main__":
    app = PagoApp()
    app.mainloop()
