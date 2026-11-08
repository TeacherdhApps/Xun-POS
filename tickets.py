#!/usr/bin/env python3
"""Generacion de tickets PDF para Xun-POS."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = A4


def _money(cents) -> float:
    return float(cents) / 100


def generate_ticket_pdf(
    items,
    *,
    business_name: str = "Xun-POS",
    address: str = "",
    phone: str = "",
    cashier: str = "Cajero",
    date_str: str = "",
    total_cents: int = 0,
) -> bytes:
    """Generate a ticket PDF from sale items.

    ``items`` is a list of dicts with ``nombre``, ``cantidad``,
    ``precio`` (float) and ``total`` (float) keys.
    """
    buffer = BytesIO()
    ticket = canvas.Canvas(buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    margin = PAGE_WIDTH * 0.05
    y = PAGE_HEIGHT - margin

    ticket.setFont("Helvetica-Bold", 14)
    ticket.drawString(margin, y, str(business_name)[:40])
    y -= 16
    if address:
        ticket.setFont("Helvetica", 9)
        ticket.drawString(margin, y, str(address)[:60])
        y -= 12
    if phone:
        ticket.setFont("Helvetica", 9)
        ticket.drawString(margin, y, f"Tel: {phone}")
        y -= 12

    ticket.setFont("Helvetica-Bold", 10)
    ticket.drawString(margin, y, "Ticket de venta")
    y -= 14

    ticket.setFont("Helvetica", 9)
    for item in items:
        precio = item.get("precio") or 0
        cantidad = item.get("cantidad") or 0
        descuento = item.get("descuento", 0)
        line_total = item.get("total") or precio * cantidad * (1 - descuento / 100)
        line = (
            f"{item.get('nombre', '')} x{cantidad}  "
            f"${_money(line_total):.2f}"
        )
        if descuento:
            line = f"{line} (-{descuento}%)"
        ticket.drawString(margin, y, line[:100])
        y -= 12
        if y < margin + 30:
            ticket.showPage()
            y = PAGE_HEIGHT - margin

    ticket.setFont("Helvetica-Bold", 11)
    ticket.drawString(margin, y, f"TOTAL: ${_money(total_cents):.2f}")
    ticket.setFont("Helvetica", 9)
    ticket.drawString(margin, y - 14, f"Cajero: {cashier}")
    if date_str:
        ticket.drawString(margin, y - 26, f"Fecha: {date_str}")

    ticket.showPage()
    ticket.save()
    return buffer.getvalue()
