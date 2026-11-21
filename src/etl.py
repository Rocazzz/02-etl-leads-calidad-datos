"""
Pipeline ETL de leads: Extract -> Transform -> Validate -> Load.

Uso:  python src/etl.py
Salidas:
  data/processed/leads_limpios.csv   (dataset listo para BI)
  data/processed/leads.db            (tabla `leads` en SQLite)
  reports/reporte_calidad.md         (reporte de calidad de datos)
"""
from __future__ import annotations
import logging
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RAW_FILE = BASE / "data" / "raw" / "leads_export.csv"
OUT_DIR = BASE / "data" / "processed"
REPORT = BASE / "reports" / "reporte_calidad.md"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("etl_leads")

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
CIUDADES = {"bogota": "Bogotá", "bogota d.c.": "Bogotá", "bogota dc": "Bogotá",
            "medellin": "Medellín", "cali": "Cali", "santiago de cali": "Cali",
            "barranquilla": "Barranquilla", "b/quilla": "Barranquilla",
            "bucaramanga": "Bucaramanga", "b/manga": "Bucaramanga"}
VERDADERO = {"si", "sí", "true", "1", "yes"}


# ----------------------------- helpers -----------------------------
def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalizar_nombre(s):
    if pd.isna(s):
        return np.nan
    return " ".join(p.capitalize() for p in str(s).split())


def normalizar_email(s):
    if pd.isna(s):
        return np.nan
    s = str(s).strip().lower()
    return s if EMAIL_RE.match(s) else np.nan


def normalizar_telefono(s):
    """Deja celulares colombianos en formato E.164 (+573XXXXXXXXX); inválidos -> NaN."""
    if pd.isna(s):
        return np.nan
    dig = re.sub(r"\D", "", str(s))
    if dig.startswith("57") and len(dig) == 12:
        dig = dig[2:]
    return f"+57{dig}" if len(dig) == 10 and dig.startswith("3") else np.nan


def normalizar_ciudad(s):
    if pd.isna(s):
        return "Sin dato"
    clave = sin_tildes(str(s).strip().lower())
    return CIUDADES.get(clave, "Otra")


def parsear_fecha(s):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d-%b-%Y"):
        try:
            return datetime.strptime(str(s), fmt)
        except ValueError:
            continue
    return pd.NaT


def a_booleano(s) -> bool:
    return False if pd.isna(s) else str(s).strip().lower() in VERDADERO


def a_numero(s):
    if pd.isna(s) or s == "":
        return np.nan
    return float(re.sub(r"[^\d.]", "", str(s)) or "nan")


def canal_desde_utm(s):
    if pd.isna(s):
        return "Desconocido"
    s = str(s).lower()
    if "cpc" in s: return "Google Ads"
    if "paid" in s: return "Redes pagas"
    if "organic" in s: return "Orgánico"
    if "referral" in s: return "Referido"
    return "Otro"


# ----------------------------- pasos -----------------------------
def extract(path: Path = RAW_FILE) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    log.info("Extract: %s filas, %s columnas", *df.shape)
    return df


def transform(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({
        "id_origen": df.id_origen,
        "fuente": df.fuente,
        "fecha_creacion": df.fecha_creacion.map(parsear_fecha),
        "nombre": df.nombre_completo.map(normalizar_nombre),
        "email": df.email.map(normalizar_email),
        "telefono": df.telefono.map(normalizar_telefono),
        "ciudad": df.ciudad.map(normalizar_ciudad),
        "servicio": df.servicio_interes.str.strip(),
        "canal": df.utm_source_medium.map(canal_desde_utm),
        "agendo_cita": df.agendo_cita.map(a_booleano),
        "es_cliente": df.es_cliente.map(a_booleano),
        "valor_venta": df.valor_venta.map(a_numero),
    })
    out["fecha_creacion"] = pd.to_datetime(out.fecha_creacion)
    # Si no tiene email ni teléfono válido no es contactable
    out["contactable"] = out.email.notna() | out.telefono.notna()

    # Deduplicación: mismo email (o teléfono) + servicio -> conserva el registro más antiguo
    out = out.sort_values("fecha_creacion")
    clave = out.email.fillna(out.telefono).fillna(out.id_origen) + "|" + out.servicio
    antes = len(out)
    out = out.loc[~clave.duplicated()].copy()
    log.info("Transform: %s duplicados eliminados", antes - len(out))

    out["mes"] = out.fecha_creacion.dt.to_period("M").astype(str)
    out["lead_id"] = np.arange(1, len(out) + 1)
    return out[["lead_id"] + [c for c in out.columns if c != "lead_id"]].reset_index(drop=True)


def validate(df: pd.DataFrame) -> dict:
    """Reglas de negocio. Lanza error si una regla crítica falla."""
    reglas = {
        "lead_id único": df.lead_id.is_unique,
        "fecha_creacion sin nulos": df.fecha_creacion.notna().all(),
        "fechas dentro de 2025": df.fecha_creacion.dt.year.eq(2025).all(),
        "cliente => agendó cita": (~df.es_cliente | df.agendo_cita).all(),
        "cliente => valor_venta > 0": (df.loc[df.es_cliente, "valor_venta"] > 0).all(),
        "no cliente => sin valor": df.loc[~df.es_cliente, "valor_venta"].isna().all(),
    }
    fallidas = [k for k, ok in reglas.items() if not ok]
    if fallidas:
        raise ValueError(f"Validación fallida: {fallidas}")
    log.info("Validate: %s/%s reglas OK", len(reglas), len(reglas))
    return reglas


def load(df: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / "leads_limpios.csv", index=False, encoding="utf-8")
    with sqlite3.connect(OUT_DIR / "leads.db") as con:
        df.assign(fecha_creacion=df.fecha_creacion.astype(str)).to_sql("leads", con, if_exists="replace", index=False)
    log.info("Load: %s filas -> leads_limpios.csv y leads.db", len(df))


def perfil_calidad(raw: pd.DataFrame, limpio: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for col, fn in [("email", normalizar_email), ("telefono", normalizar_telefono)]:
        filas.append({"métrica": f"{col} válido (crudo)", "valor": f"{raw[col].map(fn).notna().mean():.1%}"})
    filas += [
        {"métrica": "Filas crudas", "valor": len(raw)},
        {"métrica": "Filas limpias", "valor": len(limpio)},
        {"métrica": "Duplicados eliminados", "valor": len(raw) - len(limpio)},
        {"métrica": "Variantes de ciudad (crudo)", "valor": raw.ciudad.nunique()},
        {"métrica": "Ciudades estandarizadas", "valor": limpio.ciudad.nunique()},
        {"métrica": "Formatos de fecha detectados", "valor": 3},
        {"métrica": "Leads contactables", "valor": f"{limpio.contactable.mean():.1%}"},
    ]
    return pd.DataFrame(filas)


def escribir_reporte(raw, limpio, reglas):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    nulos = raw.isna().mean().mul(100).round(1).rename("% nulos (crudo)").to_frame()
    lineas = [
        "# Reporte de calidad de datos · Leads 2025",
        f"_Generado automáticamente por `src/etl.py` el {datetime.now():%Y-%m-%d %H:%M}_\n",
        "## Resumen", perfil_calidad(raw, limpio).to_markdown(index=False), "",
        "## Nulos por columna en el archivo crudo", nulos.to_markdown(), "",
        "## Reglas de validación", "| Regla | Resultado |", "|---|---|",
        *[f"| {k} | {'✅ OK' if v else '❌ Falla'} |" for k, v in reglas.items()],
    ]
    REPORT.write_text("\n".join(lineas), encoding="utf-8")
    log.info("Reporte de calidad -> %s", REPORT.relative_to(BASE))


def main():
    raw = extract()
    limpio = transform(raw)
    reglas = validate(limpio)
    load(limpio)
    escribir_reporte(raw, limpio, reglas)


if __name__ == "__main__":
    main()
