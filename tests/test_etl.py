import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from etl import (normalizar_email, normalizar_telefono, normalizar_ciudad,  # noqa: E402
                 parsear_fecha, a_booleano, a_numero, normalizar_nombre)


def test_email():
    assert normalizar_email(" ANA.GOMEZ@GMAIL.COM ") == "ana.gomez@gmail.com"
    assert pd.isna(normalizar_email("anagmail.com"))
    assert pd.isna(normalizar_email(None))


def test_telefono():
    assert normalizar_telefono("+57 3101234567") == "+573101234567"
    assert normalizar_telefono("(310) 1234567") == "+573101234567"
    assert normalizar_telefono("310-123-4567") == "+573101234567"
    assert pd.isna(normalizar_telefono("3101234"))


def test_ciudad():
    assert normalizar_ciudad("BOGOTA D.C.") == "Bogotá"
    assert normalizar_ciudad(" medellin ") == "Medellín"
    assert normalizar_ciudad("Santiago de Cali") == "Cali"
    assert normalizar_ciudad(None) == "Sin dato"


def test_fechas_mixtas():
    assert parsear_fecha("2025-03-05 10:20:00").day == 5
    assert parsear_fecha("05/03/2025 10:20").month == 3
    assert parsear_fecha("05-Mar-2025").year == 2025


def test_booleanos_y_numeros():
    assert a_booleano("Sí") and a_booleano("TRUE") and a_booleano("1")
    assert not a_booleano("no") and not a_booleano(None)
    assert a_numero("$350,000") == 350000.0
    assert normalizar_nombre("  juan   CASTRO ") == "Juan Castro"
