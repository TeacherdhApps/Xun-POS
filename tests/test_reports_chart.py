from datetime import date, datetime

import reports_gui


def test_sales_by_day_aggregates():
    sales = [
        {
            "fecha_hora": "2026-01-18T10:00:00",
            "total_centavos": 2500,
        },
        {
            "fecha_hora": "2026-01-18T15:30:00",
            "total_centavos": 1500,
        },
        {
            "fecha_hora": "2026-01-19T09:00:00",
            "total_centavos": 4000,
        },
    ]
    totals = reports_gui._sales_by_day(sales)
    assert totals == {
        "2026-01-18": 4000,
        "2026-01-19": 4000,
    }


def test_sales_by_day_empty():
    assert reports_gui._sales_by_day([]) == {}
