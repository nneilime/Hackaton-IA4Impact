import sys
import json
from collections import Counter
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QAbstractItemView,
    QStackedWidget,
    QProgressBar,
    QScrollArea,
)

try:
    from parser import parse_invoice
except ImportError:
    parse_invoice = None

PARSER_AMOUNT_DIVISOR = 100

NAVY = "#17243A"
BG = "#F5F7FB"
WHITE = "#FFFFFF"
TEXT = "#202B3C"
MUTED = "#8490A3"
GREEN = "#16845B"
YELLOW = "#B7791F"
RED = "#C74646"

FIELD_LABELS = {
    ("Invoice", "tier_number"): "Numéro de tiers",
    ("Invoice", "lot_number"): "Numéro de lot",
    ("Invoice", "invoice_number"): "Numéro de facture",
    ("Invoice", "total_local_service_fee"): "Total prestations locales",
    ("Invoice", "total_outsider_service_fee"): "Total prestations extérieures",
    ("Invoice", "services"): "Prestations (services)",
    ("Invoice", "client_number"): "Numéro de client",
    ("Cerfa", "cerfa_identifier"): "Identifiant CERFA",
    ("Cerfa", "cerfa_code"): "Code CERFA",
    ("Cerfa", "performers"): "Intervenants",
    ("Cerfa", "tier_number"): "Numéro de tiers",
    ("Cerfa", "lot_number"): "Numéro de lot",
    ("Cerfa", "invoice_number"): "Numéro de facture",
    ("Cerfa", "services"): "Prestations (services)",
    ("Cerfa", "total_local_service_fee"): "Total prestations locales",
    ("Cerfa", "total_outsider_service_fee"): "Total prestations extérieures",
    ("Cerfa", "total_service_fee"): "Total des prestations",
    ("Cerfa", "has_signature"): "Signature du directeur",
}

UNKNOWN_CLINIC = "Non renseignée"

DEMO_CLINICS = [
    "Clinique Saint-Joseph",
    "Clinique des Pins",
    "Centre Médical du Lac",
    "Polyclinique Horizon",
]
DEMO_ANOMALIES = [
    ("Invoice", "total_local_service_fee", "Total différent du CERFA"),
    ("Invoice", "total_outsider_service_fee", "Montant extérieur incohérent"),
    ("Invoice", "services", "Prestation non reconnue"),
    ("Cerfa", "has_signature", "Signature manquante"),
    ("Cerfa", "performers", "Intervenant inconnu"),
]

DEMO_INVOICES = []


def make_sample_invoices():
    def anomaly(cls, field, message):
        return {"class": cls, "field": field, "message": message}

    rows = [
        ("Clinique Saint-Joseph", "ANOMALIE", 1250.0, 310.0, [
            anomaly("Invoice", "total_local_service_fee", "Total différent du CERFA"),
            anomaly("Cerfa", "has_signature", "Signature manquante"),
        ]),
        ("Clinique Saint-Joseph", "ANOMALIE", 840.0, 120.0, [
            anomaly("Invoice", "total_local_service_fee", "Total différent du CERFA"),
        ]),
        ("Clinique Saint-Joseph", "VALIDE", 460.0, 0.0, []),
        ("Clinique des Pins", "ANOMALIE", 2100.0, 780.0, [
            anomaly("Invoice", "services", "Prestation non reconnue"),
            anomaly("Invoice", "total_outsider_service_fee", "Montant extérieur incohérent"),
        ]),
        ("Clinique des Pins", "VALIDE", 380.0, 0.0, []),
        ("Clinique des Pins", "VALIDE", 520.0, 0.0, []),
        ("Centre Médical du Lac", "ANOMALIE", 690.0, 90.0, [
            anomaly("Cerfa", "performers", "Intervenant inconnu"),
        ]),
        ("Centre Médical du Lac", "VALIDE", 910.0, 0.0, []),
        ("Centre Médical du Lac", "VALIDE", 300.0, 0.0, []),
        ("Polyclinique Horizon", "VALIDE", 1500.0, 0.0, []),
        ("Polyclinique Horizon", "ANOMALIE", 1780.0, 410.0, [
            anomaly("Invoice", "total_local_service_fee", "Total différent du CERFA"),
            anomaly("Invoice", "services", "Prestation non reconnue"),
        ]),
    ]

    invoices = []
    for i, (clinic, status, amount, divergent, anomalies) in enumerate(rows, 1):
        invoices.append(
            {
                "status": status,
                "contact": "Exemple",
                "invoice": f"FAC-EX-{i:04d}",
                "document": f"exemple_{i:03d}.txt",
                "json": "exemple.json",
                "clinic": clinic,
                "amount": amount,
                "divergent_amount": divergent,
                "anomalies": anomalies,
                "demo": True,
                "sample": True,
            }
        )
    return invoices


def make_label(text, size=12, color=TEXT, bold=False):
    label = QLabel(text)
    label.setStyleSheet(
        f"""
        color: {color};
        font-size: {size}px;
        font-weight: {"bold" if bold else "normal"};
        background-color: transparent;
        """
    )
    return label


def make_button(text, primary=False):
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(40)

    if primary:
        button.setStyleSheet(
            """
            QPushButton {
                background-color: #315EFB;
                color: white;
                border: none;
                border-radius: 9px;
                padding: 10px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #244DE0; }
            QPushButton:pressed { background-color: #1D40C2; }
            QPushButton:disabled {
                background-color: #AAB8E8;
                color: #F5F7FF;
            }
            """
        )
    else:
        button.setStyleSheet(
            """
            QPushButton {
                background-color: white;
                color: #344054;
                border: 1px solid #E2E7EF;
                border-radius: 9px;
                padding: 9px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F4F7FC;
                border-color: #CCD5E3;
            }
            """
        )
    return button


def make_card():
    card = QFrame()
    card.setObjectName("card")
    card.setStyleSheet(
        """
        QFrame#card {
            background-color: white;
            border: 1px solid #E8ECF2;
            border-radius: 14px;
        }
        """
    )
    return card


def format_euro(value):
    text = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
    return f"{text} €"


def format_percent(value):
    return f"{value:.1f} %".replace(".", ",")


def is_txt_invoice(invoice):
    return invoice.get("document", "").lower().endswith(".txt")


def is_checked(invoice):
    return invoice.get("status") in ("VALIDE", "ANOMALIE")


def is_anomalous(invoice):
    return invoice.get("status") == "ANOMALIE"


NAV_ACTIVE = """
    QPushButton {
        text-align: left;
        color: white;
        background: #2C3D59;
        border: none;
        border-radius: 9px;
        padding-left: 10px;
        font-size: 12px;
        font-weight: bold;
    }
"""

NAV_INACTIVE = """
    QPushButton {
        text-align: left;
        color: #B8C6D9;
        background: transparent;
        border: none;
        border-radius: 9px;
        padding-left: 10px;
        font-size: 12px;
        font-weight: bold;
    }
    QPushButton:hover { background: #22324D; color: white; }
"""

TABLE_STYLE = """
    QTableWidget {
        background: white;
        alternate-background-color: #F8FAFD;
        color: #344054;
        border: none;
        border-radius: 10px;
        font-size: 12px;
        selection-background-color: #EAF0FF;
        selection-color: #1E293B;
        outline: none;
    }
    QTableWidget::item {
        padding: 10px 8px;
        border-bottom: 1px solid #EEF1F6;
    }
    QTableWidget::item:hover { background: #F0F5FF; }
    QHeaderView::section {
        background: #F8FAFC;
        color: #8490A3;
        border: none;
        border-bottom: 1px solid #E8ECF2;
        padding: 13px 10px;
        font-size: 9px;
        font-weight: bold;
    }
    QScrollBar:vertical {
        background: #F8FAFC;
        width: 8px;
        margin: 2px;
        border: none;
    }
    QScrollBar::handle:vertical {
        background: #D5DDE8;
        min-height: 25px;
        border-radius: 4px;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical { height: 0px; }
"""


def make_ranking_table(headers, stretch_col=0):
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(44)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    header = table.horizontalHeader()
    header.setFixedHeight(40)
    for col in range(len(headers)):
        header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch_col, QHeaderView.ResizeMode.Stretch)
    last = len(headers) - 1
    header.setSectionResizeMode(last, QHeaderView.ResizeMode.Fixed)
    header.resizeSection(last, 160)
    table.setStyleSheet(TABLE_STYLE)
    return table


def make_bar(ratio):
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(8, 0, 8, 0)
    bar = QProgressBar()
    bar.setRange(0, 1000)
    bar.setValue(int(max(0.0, min(1.0, ratio)) * 1000))
    bar.setTextVisible(False)
    bar.setFixedHeight(8)
    bar.setStyleSheet(
        f"""
        QProgressBar {{ background: #EEF1F6; border: none; border-radius: 4px; }}
        QProgressBar::chunk {{ background: {RED}; border-radius: 4px; }}
        """
    )
    layout.addWidget(bar)
    return container


def fill_ranking_table(table, rows):
    table.setRowCount(len(rows))
    table.setFixedHeight(40 + max(len(rows), 3) * 44 + 4)
    bar_col = table.columnCount() - 1
    for r, (cells, ratio) in enumerate(rows):
        for c, value in enumerate(cells):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if c == 0:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            else:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )
            if c == 0:
                item.setToolTip(str(value))
            table.setItem(r, c, item)
        table.setCellWidget(r, bar_col, make_bar(ratio))


class DonutChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.valid_count = 0
        self.review_count = 0
        self.anomaly_count = 0
        self.setMinimumSize(145, 145)
        self.setMaximumSize(165, 165)

    def set_values(self, valid, review, anomaly):
        self.valid_count = valid
        self.review_count = review
        self.anomaly_count = anomaly
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        total = self.valid_count + self.review_count + self.anomaly_count
        rect = QRectF(17, 17, 111, 111)
        start_angle = 90 * 16
        span_total = 360 * 16

        if total == 0:
            painter.setPen(QPen(QColor("#E9EDF4"), 13))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rect)
        else:
            values = [
                (self.valid_count, GREEN),
                (self.review_count, "#E7A23B"),
                (self.anomaly_count, RED),
            ]
            for value, color in values:
                if value <= 0:
                    continue
                span = int(span_total * value / total)
                painter.setPen(
                    QPen(
                        QColor(color),
                        13,
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.FlatCap,
                    )
                )
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawArc(rect, start_angle, -span)
                start_angle -= span

        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        painter.drawText(
            QRectF(25, 45, 95, 30),
            Qt.AlignmentFlag.AlignCenter,
            str(total),
        )
        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRectF(25, 72, 95, 20),
            Qt.AlignmentFlag.AlignCenter,
            "FACTURES",
        )


class InvoiceDetailDialog(QDialog):
    def __init__(self, invoice, parent=None, on_validate=None):
        super().__init__(parent)
        self.invoice = invoice
        self.on_validate = on_validate
        self.setWindowTitle("Détail de la facture")
        self.resize(560, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)

        layout.addWidget(make_label("Détail du dossier", 21, TEXT, True))
        layout.addWidget(
            make_label("Informations du document sélectionné", 11, MUTED)
        )

        card = make_card()
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setHorizontalSpacing(20)
        card_layout.setVerticalSpacing(15)

        fields = [
            ("Statut", invoice.get("status", "À VÉRIFIER")),
            ("Clinique", invoice.get("clinic") or UNKNOWN_CLINIC),
            ("Contact", invoice.get("contact", "-")),
            ("Numéro de facture", invoice.get("invoice", "-")),
            ("Facture TXT", invoice.get("document", "-")),
            ("Justificatif JSON", invoice.get("json") or "Non fourni"),
        ]
        if is_anomalous(invoice):
            fields.append(
                ("Montant divergent", format_euro(invoice.get("divergent_amount", 0) or 0))
            )

        for row, (field_name, value) in enumerate(fields):
            card_layout.addWidget(make_label(field_name, 10, MUTED), row, 0)
            card_layout.addWidget(make_label(value, 12, TEXT, True), row, 1)

        layout.addWidget(card)
        layout.addWidget(make_label("Rapport de contrôle", 14, TEXT, True))

        anomalies = invoice.get("anomalies") or []
        if invoice.get("status") == "À VÉRIFIER":
            message = (
                "Cette facture est en attente de vérification. "
                "Le bouton « Procéder à la vérification » traite les factures "
                "TXT à vérifier qui possèdent un justificatif JSON associé."
            )
        elif anomalies:
            title = (
                "Anomalies détectées (facture validée manuellement) :"
                if invoice.get("manually_validated")
                else "Anomalies détectées :"
            )
            lines = []
            for a in anomalies:
                label = FIELD_LABELS.get(
                    (a.get("class"), a.get("field")), a.get("field", "?")
                )
                lines.append(
                    f"• {a.get('class', '?')} › {label} : {a.get('message', '')}"
                )
            message = title + "\n" + "\n".join(lines)
        else:
            message = (
                "Statut actuellement enregistré. Les factures de démonstration "
                "servent uniquement à illustrer l'interface."
            )

        explanation = QLabel(message)
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            """
            color: #667085;
            background: #F8FAFD;
            border: 1px solid #E8ECF2;
            border-radius: 10px;
            padding: 14px;
            font-size: 11px;
            """
        )
        layout.addWidget(explanation)
        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        if invoice.get("status") == "ANOMALIE":
            validate_button = make_button("Valider", primary=True)
            validate_button.clicked.connect(self.validate_invoice)
            button_layout.addWidget(validate_button)

        close_button = make_button("Fermer")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def validate_invoice(self):
        self.invoice["status"] = "VALIDE"
        self.invoice["manually_validated"] = True
        if callable(self.on_validate):
            self.on_validate()
        self.accept()


class InvoiceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iMSA | Contrôle des factures")
        self.resize(1450, 880)
        self.setMinimumSize(1100, 700)

        self.invoices = []
        self.filtered_invoices = []

        self.build_ui()
        self.refresh_dashboard()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setFixedWidth(225)
        sidebar.setStyleSheet(f"background-color: {NAVY}; border: none;")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(20, 25, 20, 22)
        side_layout.setSpacing(10)

        side_layout.addWidget(make_label("iMSA", 26, WHITE, True))
        side_layout.addWidget(
            make_label("CONTRÔLE DES FACTURES", 9, "#B8C6D9", True)
        )
        side_layout.addSpacing(30)

        self.nav_dashboard = QPushButton("  ▦    Tableau de bord")
        self.nav_stats = QPushButton("  ▤    Statistiques")
        self.nav_buttons = [self.nav_dashboard, self.nav_stats]
        for index, button in enumerate(self.nav_buttons):
            button.setMinimumHeight(43)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, i=index: self.set_page(i))
            side_layout.addWidget(button)

        side_layout.addStretch()
        side_layout.addWidget(make_label("●  Prototype local", 11, "#B8C6D9"))
        root.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {BG};")
        self.stack.addWidget(self.build_dashboard_page())
        self.stack.addWidget(self.build_stats_page())
        root.addWidget(self.stack, 1)

        self.set_page(0)

    def set_page(self, index):
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setStyleSheet(NAV_ACTIVE if i == index else NAV_INACTIVE)
        if index == 1:
            self.refresh_stats()

    def build_dashboard_page(self):
        main = QWidget()
        main.setStyleSheet(f"background-color: {BG};")
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(30, 25, 30, 25)
        main_layout.setSpacing(20)

        header = QHBoxLayout()
        title_area = QVBoxLayout()
        title_area.setSpacing(5)
        title_area.addWidget(make_label("Tableau de bord", 25, TEXT, True))
        title_area.addWidget(
            make_label(
                "Suivi et vérification des dépenses de santé", 11, MUTED
            )
        )
        header.addLayout(title_area)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher une facture...")
        self.search_input.setFixedWidth(210)
        self.search_input.setMinimumHeight(40)
        self.search_input.setStyleSheet(
            """
            QLineEdit {
                background: white;
                border: 1px solid #E3E8F0;
                border-radius: 9px;
                padding: 0 12px;
                font-size: 11px;
                color: #344054;
            }
            QLineEdit:focus { border: 1px solid #315EFB; }
            """
        )
        self.search_input.textChanged.connect(self.filter_table)
        header.addWidget(self.search_input)

        import_button = make_button("+ Importer des fichiers", False)
        import_button.clicked.connect(self.import_documents)
        header.addWidget(import_button)

        self.verify_button = make_button("Procéder à la vérification", True)
        self.verify_button.clicked.connect(self.proceed_verification)
        header.addWidget(self.verify_button)
        main_layout.addLayout(header)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(18)

        pending_card = make_card()
        pending_card.setMinimumHeight(170)
        pending_layout = QVBoxLayout(pending_card)
        pending_layout.setContentsMargins(22, 20, 22, 20)
        pending_layout.setSpacing(9)
        pending_layout.addWidget(make_label("À TRAITER", 10, MUTED, True))
        self.pending_number = make_label("0", 34, TEXT, True)
        pending_layout.addWidget(self.pending_number)
        pending_layout.addWidget(
            make_label("Factures en attente de vérification", 11, MUTED)
        )
        pending_layout.addStretch()
        pending_layout.addWidget(
            make_label("●  Statut : À VÉRIFIER", 10, YELLOW, True)
        )
        summary_row.addWidget(pending_card, 1)

        chart_card = make_card()
        chart_card.setMinimumHeight(170)
        chart_layout = QHBoxLayout(chart_card)
        chart_layout.setContentsMargins(18, 12, 18, 12)
        chart_layout.setSpacing(15)

        self.donut = DonutChart()
        chart_layout.addWidget(
            self.donut, 0, Qt.AlignmentFlag.AlignVCenter
        )

        legend = QVBoxLayout()
        legend.setSpacing(11)
        legend.addWidget(
            make_label("Répartition des statuts", 12, TEXT, True)
        )
        self.valid_legend = make_label("●  Validées : 0", 10, GREEN)
        self.review_legend = make_label("●  À vérifier : 0", 10, YELLOW)
        self.anomaly_legend = make_label("●  Anomalies : 0", 10, RED)
        legend.addWidget(self.valid_legend)
        legend.addWidget(self.review_legend)
        legend.addWidget(self.anomaly_legend)
        legend.addStretch()
        chart_layout.addLayout(legend, 1)
        summary_row.addWidget(chart_card, 1)
        main_layout.addLayout(summary_row)

        table_card = make_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(20, 18, 20, 18)
        table_layout.setSpacing(14)

        table_header = QHBoxLayout()
        table_titles = QVBoxLayout()
        table_titles.setSpacing(4)
        table_titles.addWidget(make_label("Factures récentes", 16, TEXT, True))
        table_titles.addWidget(
            make_label(
                "Chaque fichier TXT représente une facture ; le JSON représente son justificatif.",
                10,
                MUTED,
            )
        )
        table_header.addLayout(table_titles)
        table_header.addStretch()
        self.count_label = make_label("0 facture(s)", 10, MUTED)
        table_header.addWidget(self.count_label)
        table_layout.addLayout(table_header)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            [
                "STATUT",
                "CONTACT",
                "N° FACTURE",
                "FACTURE TXT",
                "JUSTIFICATIF JSON",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        header_view = self.table.horizontalHeader()
        header_view.setStretchLastSection(True)
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet(TABLE_STYLE)
        self.table.itemDoubleClicked.connect(self.open_invoice_detail)
        table_layout.addWidget(self.table)

        main_layout.addWidget(table_card)
        return main

    def build_stats_page(self):
        main = QWidget()
        main.setStyleSheet(f"background-color: {BG};")
        layout = QVBoxLayout(main)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(16)
        layout.addWidget(make_label("Statistiques", 25, TEXT, True))
        layout.addWidget(make_label(
            "Indicateurs calculés à partir des factures TXT effectivement contrôlées.",
            11, MUTED
        ))

        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(14)

        def make_kpi(title):
            card = make_card()
            card.setMinimumHeight(125)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 16, 18, 16)
            card_layout.setSpacing(6)
            card_layout.addWidget(make_label(title, 10, MUTED, True))
            value = make_label("0", 25, TEXT, True)
            detail = make_label("", 10, MUTED)
            detail.setWordWrap(True)
            card_layout.addWidget(value)
            card_layout.addWidget(detail)
            card_layout.addStretch()
            kpi_row.addWidget(card, 1)
            return value, detail

        self.kpi_rate, self.kpi_rate_detail = make_kpi("TAUX DE FACTURES EN ANOMALIE")
        self.kpi_amount, self.kpi_amount_detail = make_kpi("MONTANT DIVERGENT")
        self.kpi_checked, self.kpi_checked_detail = make_kpi("FACTURES CONTRÔLÉES")
        layout.addLayout(kpi_row)

        self.stats_hint = make_label(
            "Aucune facture contrôlée pour le moment. Importez des fichiers TXT et JSON, "
            "puis lancez la vérification.", 11, YELLOW
        )
        self.stats_hint.setWordWrap(True)
        layout.addWidget(self.stats_hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(14)
        self.stats_table_clinic = make_ranking_table(
            ["Clinique", "Factures contrôlées", "Factures en anomalie",
             "Taux d'anomalie", "Montant divergent", "Indice"], stretch_col=0
        )
        self.stats_table_field = make_ranking_table(
            ["Champ", "Type", "Occurrences", "Part des anomalies", "Indice"], stretch_col=0
        )
        c_layout.addWidget(make_label("Classement des cliniques", 14, TEXT, True))
        c_layout.addWidget(self.stats_table_clinic)
        c_layout.addWidget(make_label("Classement des champs en anomalie", 14, TEXT, True))
        c_layout.addWidget(self.stats_table_field)
        layout.addWidget(scroll, 1)
        return main

    def refresh_dashboard(self):
        displayed = self.invoices
        self.filtered_invoices = displayed

        self.table.setRowCount(len(displayed))
        for row, inv in enumerate(displayed):
            status_item = QTableWidgetItem(inv.get("status", ""))
            contact_item = QTableWidgetItem(inv.get("contact", ""))
            invoice_item = QTableWidgetItem(inv.get("invoice", ""))
            doc_item = QTableWidgetItem(inv.get("document", ""))
            json_item = QTableWidgetItem(inv.get("json", ""))

            for item in (status_item, contact_item, invoice_item, doc_item, json_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row, 0, status_item)
            self.table.setItem(row, 1, contact_item)
            self.table.setItem(row, 2, invoice_item)
            self.table.setItem(row, 3, doc_item)
            self.table.setItem(row, 4, json_item)

        self.count_label.setText(f"{len(displayed)} facture(s)")

        valid = sum(1 for inv in displayed if inv.get("status") == "VALIDE")
        review = sum(1 for inv in displayed if inv.get("status") == "À VÉRIFIER")
        anomaly = sum(1 for inv in displayed if inv.get("status") == "ANOMALIE")

        self.pending_number.setText(str(review))
        self.donut.set_values(valid, review, anomaly)
        self.valid_legend.setText(f"●  Validées : {valid}")
        self.review_legend.setText(f"●  À vérifier : {review}")
        self.anomaly_legend.setText(f"●  Anomalies : {anomaly}")
        self.refresh_stats()

    def filter_table(self):
        text = self.search_input.text().strip().lower()
        if not text:
            self.filtered_invoices = self.invoices
        else:
            self.filtered_invoices = [
                inv for inv in self.invoices
                if text in str(inv.get("invoice", "")).lower()
                or text in str(inv.get("contact", "")).lower()
                or text in str(inv.get("document", "")).lower()
                or text in str(inv.get("json", "")).lower()
            ]

        self.table.setRowCount(len(self.filtered_invoices))
        for row, inv in enumerate(self.filtered_invoices):
            status_item = QTableWidgetItem(inv.get("status", ""))
            contact_item = QTableWidgetItem(inv.get("contact", ""))
            invoice_item = QTableWidgetItem(inv.get("invoice", ""))
            doc_item = QTableWidgetItem(inv.get("document", ""))
            json_item = QTableWidgetItem(inv.get("json", ""))

            for item in (status_item, contact_item, invoice_item, doc_item, json_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row, 0, status_item)
            self.table.setItem(row, 1, contact_item)
            self.table.setItem(row, 2, invoice_item)
            self.table.setItem(row, 3, doc_item)
            self.table.setItem(row, 4, json_item)

        self.count_label.setText(f"{len(self.filtered_invoices)} facture(s)")

    def open_invoice_detail(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.filtered_invoices):
            return
        invoice = self.filtered_invoices[row]
        dlg = InvoiceDetailDialog(invoice, self, on_validate=self.refresh_dashboard)
        dlg.exec()

    def import_documents(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Importer les documents",
            "",
            "Fichiers TXT/JSON (*.txt *.json)"
        )
        if not files:
            return

        # Conserver les fichiers JSON déjà importés, même s'ils ont été
        # sélectionnés lors d'une importation précédente.
        json_paths = {
            str(Path(f).resolve()).casefold(): str(Path(f).resolve())
            for f in files if Path(f).suffix.casefold() == ".json"
        }
        txt_paths = {
            str(Path(f).resolve()).casefold(): str(Path(f).resolve())
            for f in files if Path(f).suffix.casefold() == ".txt"
        }
        for inv in self.invoices:
            old_json = inv.get("json_path")
            old_txt = inv.get("file_path")
            if old_json and Path(old_json).is_file():
                json_paths[str(Path(old_json).resolve()).casefold()] = str(Path(old_json).resolve())
            if old_txt and Path(old_txt).is_file():
                txt_paths[str(Path(old_txt).resolve()).casefold()] = str(Path(old_txt).resolve())

        # Indexer les JSON par nom exact sans extension. Ne jamais regrouper
        # sur la partie avant « _ » : cela associerait des factures différentes.
        json_by_stem = {}
        for js in json_paths.values():
            json_by_stem.setdefault(Path(js).stem.casefold(), []).append(js)

        # Créer une entrée pour chaque TXT importé, même si son JSON est
        # importé plus tard. Une entrée existante pour ce même chemin est réutilisée.
        for txt in txt_paths.values():
            existing = next((item for item in self.invoices
                             if item.get("file_path") and
                             str(Path(item["file_path"]).resolve()).casefold() == str(Path(txt).resolve()).casefold()), None)
            if existing is None:
                existing = {
                    "status": "À VÉRIFIER", "contact": "-", "invoice": "-",
                    "document": Path(txt).name, "json": "", "json_path": None,
                    "file_path": txt, "clinic": UNKNOWN_CLINIC, "amount": 0,
                    "divergent_amount": 0, "anomalies": [], "demo": False, "sample": False,
                }
                self.invoices.append(existing)

            matches = json_by_stem.get(Path(txt).stem.casefold(), [])
            # Si plusieurs JSON portent ce nom, privilégier celui du même dossier.
            same_dir = [js for js in matches if Path(js).parent.resolve() == Path(txt).parent.resolve()]
            if len(same_dir) == 1:
                js = same_dir[0]
            elif len(matches) == 1:
                js = matches[0]
            elif len(matches) == 0:
                existing["json"] = ""
                existing["json_path"] = None
                continue
            else:
                existing["json"] = ""
                existing["json_path"] = None
                existing["anomalies"] = [{"class": "Cerfa", "field": "json", "message":
                    "Plusieurs JSON portent ce nom ; association ambiguë. Importez-les dans le même dossier que le TXT ou renommez-les."}]
                continue

            try:
                with open(js, "r", encoding="utf-8") as f:
                    cerfa = json.load(f)
            except Exception as e:
                existing["json"] = Path(js).name
                existing["json_path"] = js
                existing["anomalies"] = [{"class": "Cerfa", "field": "json", "message": f"Impossible de lire le JSON : {e}"}]
                continue

            existing.update({
                "document": Path(txt).name, "json": Path(js).name,
                "json_path": js, "file_path": txt,
                "contact": cerfa.get("client_number", "-"),
                "invoice": cerfa.get("invoice_number", "-"),
                "clinic": cerfa.get("tier_number", UNKNOWN_CLINIC),
                "amount": cerfa.get("total_service_fee", 0),
            })
            # Une nouvelle association doit pouvoir être vérifiée.
            if existing.get("status") not in ("VALIDE", "ANOMALIE"):
                existing["status"] = "À VÉRIFIER"

        self.refresh_dashboard()

    def compare_invoice_with_json(self, txt_path, cerfa):
        anomalies = []

        if parse_invoice is None:
            anomalies.append({
                "class": "Invoice",
                "field": "file",
                "message": "Parser indisponible"
            })
            return anomalies

        lots = parse_invoice(txt_path)
        if not lots:
            anomalies.append({"class": "Invoice", "field": "file", "message": "Impossible de lire le fichier TXT"})
            return anomalies

        parsed = [inv for lot in lots for inv in lot.invoices]
        if not parsed:
            anomalies.append({"class": "Invoice", "field": "file", "message": "Aucune facture dans le TXT"})
            return anomalies

        inv = parsed[0]

        checks = [
            ("tier_number", inv.tier_number, cerfa.get("tier_number")),
            ("lot_number", inv.lot_number, cerfa.get("lot_number")),
            ("invoice_number", inv.invoice_number, cerfa.get("invoice_number")),
            ("client_number", inv.client_number, cerfa.get("client_number")),
            ("total_local_service_fee", inv.total_local_service_fee, cerfa.get("total_local_service_fee")),
            ("total_outsider_service_fee", inv.total_outsider_service_fee, cerfa.get("total_outsider_service_fee")),
        ]

        for field, txt_val, js_val in checks:
            if str(txt_val) != str(js_val):
                anomalies.append({
                    "class": "Invoice",
                    "field": field,
                    "message": f"TXT={txt_val} / JSON={js_val}"
                })

        if cerfa.get("cerfa_identifier") != "12278*01":
            anomalies.append({
                "class": "Cerfa",
                "field": "cerfa_identifier",
                "message": f"Attendu 12278*01, trouvé {cerfa.get('cerfa_identifier')}"
            })

        if cerfa.get("cerfa_code") != "S3404":
            anomalies.append({
                "class": "Cerfa",
                "field": "cerfa_code",
                "message": f"Attendu S3404, trouvé {cerfa.get('cerfa_code')}"
            })

        performers = cerfa.get("performers", [])
        if not performers:
            anomalies.append({
                "class": "Cerfa",
                "field": "performers",
                "message": "Aucun intervenant dans le JSON"
            })
        else:
            for idx, perf in enumerate(performers):
                if not perf.get("has_signature", False):
                    anomalies.append({
                        "class": "Cerfa",
                        "field": "performers",
                        "message": f"Signature manquante pour l'intervenant {idx + 1} ({perf.get('number', '')})"
                    })

        txt_services = {(s.type.value, s.number) for s in inv.services}
        js_services = {(s.get("type"), s.get("number")) for s in cerfa.get("services", [])}

        if txt_services != js_services:
            anomalies.append({
                "class": "Invoice",
                "field": "services",
                "message": "Prestations différentes entre TXT et JSON"
            })

        total_service_fee = cerfa.get("total_service_fee")
        expected_total = inv.total_local_service_fee + inv.total_outsider_service_fee
        if total_service_fee is not None and expected_total != total_service_fee:
            anomalies.append({
                "class": "Cerfa",
                "field": "total_service_fee",
                "message": f"TXT={expected_total} / JSON={total_service_fee}"
            })

        return anomalies

    def proceed_verification(self):
        processed = 0
        for inv in self.invoices:
            # Ne contrôler que les TXT encore en attente.
            if inv.get("status") != "À VÉRIFIER":
                continue

            txt_path = inv.get("file_path")
            json_path = inv.get("json_path")
            if not txt_path or not json_path:
                continue

            # Sécurité supplémentaire : les deux noms de base doivent être
            # strictement identiques (sans extension), sans découpage sur « _ ».
            if Path(txt_path).stem.casefold() != Path(json_path).stem.casefold():
                inv["anomalies"] = [{"class": "Cerfa", "field": "json",
                    "message": f"Noms incompatibles : {Path(txt_path).name} / {Path(json_path).name}"}]
                continue

            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    cerfa = json.load(f)
            except Exception as e:
                inv["status"] = "ANOMALIE"
                inv["anomalies"] = [{"class": "Cerfa", "field": "json",
                    "message": f"Impossible de lire le JSON : {e}"}]
                processed += 1
                continue

            anomalies = self.compare_invoice_with_json(txt_path, cerfa)
            inv["divergent_amount"] = self.calculate_divergent_amount(txt_path, cerfa)
            inv["anomalies"] = anomalies
            inv["status"] = "ANOMALIE" if anomalies else "VALIDE"
            processed += 1

        self.refresh_dashboard()
        if processed == 0:
            QMessageBox.information(
                self, "Vérification",
                "Aucune facture TXT à vérifier avec un fichier JSON associé portant exactement le même nom."
            )

    def refresh_stats(self):
        invoices = [inv for inv in self.invoices if is_txt_invoice(inv)]
        checked = [inv for inv in invoices if is_checked(inv)]
        anomalous = [inv for inv in checked if is_anomalous(inv)]

        def number(value):
            try:
                return float(value or 0)
            except (TypeError, ValueError):
                return 0.0

        total_checked = len(checked)
        total_anomalies = len(anomalous)
        rate = total_anomalies / total_checked * 100 if total_checked else 0.0
        divergent_total = sum(number(inv.get("divergent_amount")) for inv in anomalous)
        amount_total = sum(number(inv.get("amount")) for inv in checked)
        amount_rate = divergent_total / amount_total * 100 if amount_total else 0.0
        pending = sum(1 for inv in invoices if inv.get("status") == "À VÉRIFIER")

        self.kpi_rate.setText(format_percent(rate))
        self.kpi_rate_detail.setText(
            f"{total_anomalies} anomalie(s) sur {total_checked} facture(s) contrôlée(s)"
            if total_checked else "Aucune facture contrôlée"
        )
        self.kpi_amount.setText(format_euro(divergent_total))
        self.kpi_amount_detail.setText(
            f"Soit {format_percent(amount_rate)} du montant contrôlé ({format_euro(amount_total)})"
            if amount_total else "Montant total des écarts financiers détectés"
        )
        self.kpi_checked.setText(str(total_checked))
        self.kpi_checked_detail.setText(f"{pending} facture(s) en attente de vérification")
        self.stats_hint.setVisible(total_checked == 0)

        clinics = {}
        for inv in checked:
            name = inv.get("clinic") or UNKNOWN_CLINIC
            entry = clinics.setdefault(name, {"total": 0, "anomalies": 0, "divergent": 0.0})
            entry["total"] += 1
            if is_anomalous(inv):
                entry["anomalies"] += 1
                entry["divergent"] += number(inv.get("divergent_amount"))

        sorted_clinics = sorted(
            clinics.items(),
            key=lambda item: (item[1]["anomalies"], item[1]["divergent"]),
            reverse=True
        )
        max_clinic = max((entry["anomalies"] for _, entry in sorted_clinics), default=0)
        clinic_rows = []
        for name, entry in sorted_clinics:
            clinic_rate = entry["anomalies"] / entry["total"] * 100 if entry["total"] else 0.0
            clinic_rows.append((
                [name, entry["total"], entry["anomalies"], format_percent(clinic_rate),
                 format_euro(entry["divergent"]), ""],
                entry["anomalies"] / max_clinic if max_clinic else 0.0
            ))
        fill_ranking_table(self.stats_table_clinic, clinic_rows)

        counter = Counter()
        for inv in anomalous:
            for anomaly in inv.get("anomalies") or []:
                counter[(anomaly.get("class", "?"), anomaly.get("field", "?"))] += 1
        sorted_fields = counter.most_common()
        total_errors = sum(counter.values())
        max_field = sorted_fields[0][1] if sorted_fields else 0
        field_rows = []
        for (cls, field), count in sorted_fields:
            label = FIELD_LABELS.get((cls, field), field)
            share = count / total_errors * 100 if total_errors else 0.0
            field_rows.append((
                [label, cls, count, format_percent(share), ""],
                count / max_field if max_field else 0.0
            ))
        fill_ranking_table(self.stats_table_field, field_rows)

    def calculate_divergent_amount(self, txt_path, cerfa):
        """Calcule l'écart absolu des totaux financiers TXT/JSON comparés."""
        if parse_invoice is None:
            return 0.0
        try:
            lots = parse_invoice(txt_path)
            parsed = [invoice for lot in (lots or []) for invoice in lot.invoices]
            if not parsed:
                return 0.0
            invoice = parsed[0]
            total = 0.0
            for field in ("total_local_service_fee", "total_outsider_service_fee"):
                txt_value = getattr(invoice, field, None)
                json_value = cerfa.get(field)
                if txt_value is None or json_value is None:
                    continue
                try:
                    total += abs(float(txt_value) - float(json_value))
                except (TypeError, ValueError):
                    continue
            return total
        except Exception:
            return 0.0


def main():
    app = QApplication(sys.argv)
    win = InvoiceApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
