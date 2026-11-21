"""
Simula la exportación "sucia" de leads que llegan desde formularios web
(WordPress), agendamientos (Calendly) y una hoja de Google Sheets compartida.
Incluye a propósito los problemas típicos: duplicados, formatos de fecha mixtos,
teléfonos inconsistentes, emails inválidos, ciudades mal escritas y nulos.

Uso:  python src/generar_datos_crudos.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

rng = np.random.default_rng(7)
BASE = Path(__file__).resolve().parents[1]
RAW = BASE / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

nombres = ["Ana", "Luis", "Carlos", "María", "Juliana", "Andrés", "Sofía", "Felipe", "Valentina", "Diego",
           "Camila", "Santiago", "Laura", "Mateo", "Daniela", "Sebastián", "Paula", "Nicolás", "Isabella", "Tomás"]
apellidos = ["Gómez", "Rodríguez", "López", "Martínez", "García", "Hernández", "Ramírez", "Torres", "Díaz", "Moreno",
             "Castro", "Vargas", "Rojas", "Ortiz", "Jiménez"]
ciudades_variantes = {
    "Bogotá": ["Bogotá", "bogota", "BOGOTA D.C.", "Bogota DC", " Bogotá "],
    "Medellín": ["Medellín", "medellin", "MEDELLIN", "Medellin "],
    "Cali": ["Cali", "cali", "CALI", "Santiago de Cali"],
    "Barranquilla": ["Barranquilla", "barranquilla", "B/quilla"],
    "Bucaramanga": ["Bucaramanga", "bucaramanga", "B/manga"],
}
servicios = ["Trámite de visa", "Pasaporte", "Apostilla", "Traducción oficial", "Asesoría migratoria"]
fuentes = {"wordpress_form": 0.45, "calendly": 0.30, "google_sheets": 0.25}
utm = ["google / cpc", "facebook / paid", "organic", "instagram / paid", "referral", None]

n = 1800
rows = []
fecha0 = pd.Timestamp("2025-01-01")
for i in range(n):
    nom, ape = rng.choice(nombres), rng.choice(apellidos)
    ciudad_real = rng.choice(list(ciudades_variantes), p=[.35, .25, .2, .1, .1])
    fuente = rng.choice(list(fuentes), p=list(fuentes.values()))
    f = fecha0 + pd.Timedelta(minutes=int(rng.integers(0, 365 * 24 * 60)))
    # Formato de fecha distinto según la fuente
    fecha_txt = {"wordpress_form": f.strftime("%Y-%m-%d %H:%M:%S"),
                 "calendly": f.strftime("%d/%m/%Y %H:%M"),
                 "google_sheets": f.strftime("%d-%b-%Y")}[fuente]
    email = f"{nom}.{ape}{rng.integers(1, 999)}@{rng.choice(['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com'])}"
    email = email.lower().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    r = rng.random()
    if r < 0.04:   email = email.replace("@", "")            # inválido
    elif r < 0.08: email = email.upper()                      # mayúsculas
    elif r < 0.11: email = None                               # nulo
    tel = f"3{rng.integers(0, 3)}{rng.integers(0, 10)}{rng.integers(1000000, 9999999)}"
    tel = rng.choice([tel, f"+57 {tel}", f"{tel[:3]}-{tel[3:6]}-{tel[6:]}", f"({tel[:3]}) {tel[3:]}", tel[:7]],
                     p=[.4, .25, .15, .15, .05])
    servicio = rng.choice(servicios, p=[.3, .25, .2, .15, .1])
    # Embudo: lead -> agendó -> cliente
    p_agenda = {"calendly": 1.0, "wordpress_form": 0.38, "google_sheets": 0.3}[fuente]
    agendo = rng.random() < p_agenda
    p_cierre = 0.42 if fuente == "calendly" else 0.3
    if servicio == "Asesoría migratoria": p_cierre += 0.1
    cliente = agendo and rng.random() < p_cierre
    valor = round(float(rng.choice([180_000, 250_000, 350_000, 600_000, 950_000])), 0) if cliente else None
    rows.append({
        "id_origen": f"{fuente[:2].upper()}-{i:05d}",
        "fuente": fuente,
        "fecha_creacion": fecha_txt,
        "nombre_completo": rng.choice([f"{nom} {ape}", f"{nom.upper()} {ape.upper()}", f"  {nom.lower()} {ape.lower()} "], p=[.7, .15, .15]),
        "email": email,
        "telefono": tel,
        "ciudad": rng.choice(ciudades_variantes[ciudad_real]) if rng.random() > 0.06 else None,
        "servicio_interes": servicio,
        "utm_source_medium": rng.choice(utm, p=[.25, .2, .22, .13, .1, .1]),
        "agendo_cita": rng.choice(["Sí", "si", "TRUE", "1"]) if agendo else rng.choice(["No", "no", "FALSE", "0", None]),
        "es_cliente": "Sí" if cliente else "No",
        "valor_venta": f"${valor:,.0f}" if valor and rng.random() < 0.5 else valor,
    })

df = pd.DataFrame(rows)
# Duplicados exactos (re-envíos del formulario) y duplicados entre fuentes
dups = df.sample(90, random_state=1)
dups_cross = df.sample(60, random_state=2).assign(fuente="google_sheets")
dups_cross["id_origen"] = ["GO-D" + s[3:] for s in dups_cross.id_origen]
df = pd.concat([df, dups, dups_cross]).sample(frac=1, random_state=3).reset_index(drop=True)
df.to_csv(RAW / "leads_export.csv", index=False, encoding="utf-8")
print(f"Archivo crudo generado: {len(df)} filas -> data/raw/leads_export.csv")
