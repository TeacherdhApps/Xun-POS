from tickets import generate_ticket_pdf


def test_generate_ticket_pdf_returns_pdf_bytes():
    items = [
        {
            "nombre": "Producto de ejemplo",
            "cantidad": 2,
            "precio": 10.0,
            "total": 20.0,
        },
        {
            "nombre": "Otro producto de ejemplo",
            "cantidad": 1.5,
            "precio": 25.5,
            "total": 38.25,
        },
    ]

    data = generate_ticket_pdf(
        items,
        business_name="Xun-POS",
        address="Calle Principal 123",
        phone="555-0199",
        cashier="Cajero",
        date_str="2026-11-07",
        total_cents=5825,
    )

    assert data.startswith(b"%PDF")
    assert len(data) > 0
    assert data.decode("latin-1")


def test_generate_ticket_pdf_without_items():
    data = generate_ticket_pdf([], business_name="Xun-POS", total_cents=0)
    assert data.startswith(b"%PDF")
