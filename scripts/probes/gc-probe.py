#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe de diarización de Gemini 3.5 Transcribe por `:generateContent`.

Port de `gc-probe.ts` a Python 3.9 sin dependencias externas, para máquinas sin
bun ni node. Verifica la compuerta de entrada del spec de reuniones:
`2026-08-27-reuniones-en-linea-design.md` → "Verificación pendiente".

La key se lee del Llavero de macOS en runtime; nunca se imprime ni se escribe.
Los audios de prueba se generan con `say` y viven fuera del repo (SSD2 es caché
regenerable).

Uso:
    python3 scripts/probes/gc-probe.py              # genera audios y prueba
    python3 scripts/probes/gc-probe.py --solo-audio # solo genera los audios
"""

import json
import os
import subprocess
import sys
import time
import wave

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:  # pragma: no cover - Python 2 no está soportado
    sys.exit("Este probe necesita Python 3.")

CUENTA = "dilo"
SERVICIO = "dilo-gemini-api-key"
MODELO = "gemini-3.5-transcribe"
URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    + MODELO
    + ":generateContent"
)
SCRATCH = "/Volumes/SSD2/scratch/dilo-probes"
MUESTREO = 16000
SILENCIO_MS = 400

# Turnos: (voz de `say`, frase). Cada audio suma ~20 s.
REUNION_2 = [
    ("Mónica", "Buenos días a todos, partamos con el estado del presupuesto del trimestre."),
    ("Eddy (Español (México))", "Ya, mira, el presupuesto está cerrado salvo la parte de marketing."),
    ("Mónica", "¿Y cuándo crees que marketing nos manda sus números definitivos?"),
    ("Eddy (Español (México))", "Les escribo hoy mismo y les pido que los manden mañana a primera hora."),
    ("Mónica", "Perfecto, entonces lo revisamos el viernes en la reunión de cierre."),
]

REUNION_5 = [
    ("Mónica", "Abrimos la reunión de coordinación; primero el avance de ingeniería."),
    ("Eddy (Español (México))", "Ingeniería va bien, cerramos la migración de la base el martes."),
    ("Paulina", "Diseño entregó las pantallas nuevas, faltan los estados de error."),
    ("Rocko (Español (España))", "En soporte bajaron los tickets, pero siguen las quejas de lentitud."),
    ("Grandma (Español (España))", "Administración necesita las facturas antes del día treinta, por favor."),
]


def fallar_sin_key():
    sys.stderr.write(
        "No hay key de Google en el Llavero.\n"
        "Agrégala con:\n"
        "  security add-generic-password -a %s -s %s -U -w\n"
        "(el comando pide la key por teclado; no la pongas en la línea de "
        "comandos ni en un archivo).\n" % (CUENTA, SERVICIO)
    )
    sys.exit(2)


def leer_key():
    """Devuelve la key del Llavero. Sale con código 2 si no está."""
    try:
        salida = subprocess.check_output(
            ["security", "find-generic-password", "-a", CUENTA, "-s", SERVICIO, "-w"],
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, OSError):
        fallar_sin_key()
    key = salida.decode("utf-8").strip()
    if not key:
        fallar_sin_key()
    return key


def decir(voz, frase, destino):
    """Graba una frase con `say` en WAV 16 kHz mono PCM 16-bit."""
    subprocess.check_call(
        ["say", "-v", voz, "--data-format=LEI16@16000", "-o", destino, frase]
    )


def leer_pcm(ruta):
    with wave.open(ruta, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2 or w.getframerate() != MUESTREO:
            raise RuntimeError("Formato inesperado en %s: %s" % (ruta, w.getparams()))
        return w.readframes(w.getnframes())


def armar(turnos, destino, tmp):
    """Concatena los turnos con 400 ms de silencio y escribe un WAV válido."""
    silencio = b"\x00" * int(MUESTREO * SILENCIO_MS / 1000) * 2
    trozos = []
    for i, (voz, frase) in enumerate(turnos):
        parcial = os.path.join(tmp, "turno-%d.wav" % i)
        decir(voz, frase, parcial)
        if trozos:
            trozos.append(silencio)
        trozos.append(leer_pcm(parcial))
        os.remove(parcial)
    pcm = b"".join(trozos)
    with wave.open(destino, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(MUESTREO)
        w.writeframes(pcm)
    return len(pcm) / 2.0 / MUESTREO


def asegurar_audios():
    """Genera los dos audios si faltan. Devuelve [(etiqueta, ruta, segundos)]."""
    if not os.path.isdir("/Volumes/SSD2"):
        sys.exit("No está montado /Volumes/SSD2; ahí viven los audios de prueba.")
    os.makedirs(SCRATCH, exist_ok=True)
    audios = []
    for etiqueta, turnos, nombre in (
        ("2 hablantes", REUNION_2, "reunion-2.wav"),
        ("5 hablantes", REUNION_5, "reunion-5.wav"),
    ):
        ruta = os.path.join(SCRATCH, nombre)
        if os.path.exists(ruta):
            with wave.open(ruta, "rb") as w:
                segs = w.getnframes() / float(w.getframerate())
            print("Audio ya existente: %s (%.1f s)" % (ruta, segs))
        else:
            segs = armar(turnos, ruta, SCRATCH)
            print("Audio generado: %s (%.1f s, %d voces)"
                  % (ruta, segs, len({v for v, _ in turnos})))
        audios.append((etiqueta, ruta, segs))
    return audios


def base64_de(ruta):
    import base64

    with open(ruta, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def cuerpo(ruta):
    return json.dumps(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "audio/wav",
                                "data": base64_de(ruta),
                            }
                        }
                    ],
                }
            ],
            # `mode` no funciona acá (el spec del motor lo documenta): la salida
            # es verbatim. `wordTimestamp` es obligatorio para pedir diarización.
            "generationConfig": {
                "temperature": 0,
                "audioTranscriptionConfig": {
                    "wordTimestamp": True,
                    "diarization": True,
                },
            },
        }
    ).encode("utf-8")


def pedir(key, ruta):
    """POST al endpoint. Devuelve (status, json_o_None, texto_crudo, segundos)."""
    req = Request(
        URL,
        data=cuerpo(ruta),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    t0 = time.time()
    try:
        with urlopen(req, timeout=300) as res:
            crudo = res.read().decode("utf-8", "replace")
            status = res.getcode()
    except HTTPError as e:
        crudo = e.read().decode("utf-8", "replace")
        status = e.code
    except URLError as e:
        return (0, None, "sin red: %s" % e.reason, time.time() - t0)
    try:
        datos = json.loads(crudo)
    except ValueError:
        datos = None
    return (status, datos, crudo, time.time() - t0)


def forma(nodo, prof=0, tope=6):
    """Describe la forma del JSON sin volcar el contenido completo."""
    pad = "  " * prof
    if prof > tope:
        return pad + "…\n"
    if isinstance(nodo, dict):
        out = ""
        for k, v in nodo.items():
            if isinstance(v, (dict, list)):
                out += "%s%s:\n%s" % (pad, k, forma(v, prof + 1, tope))
            else:
                muestra = repr(v)
                if len(muestra) > 70:
                    muestra = muestra[:70] + "…"
                out += "%s%s = %s\n" % (pad, k, muestra)
        return out
    if isinstance(nodo, list):
        if not nodo:
            return pad + "[] (vacío)\n"
        return "%s[%d elementos; se muestra el primero]\n%s" % (
            pad,
            len(nodo),
            forma(nodo[0], prof + 1, tope),
        )
    return pad + repr(nodo) + "\n"


def texto_de(datos):
    partes = []
    for cand in (datos or {}).get("candidates", []):
        for parte in cand.get("content", {}).get("parts", []):
            if isinstance(parte.get("text"), str):
                partes.append(parte["text"])
    return "".join(partes)


def probar(key, etiqueta, ruta, segs):
    print("\n" + "=" * 70)
    print("=== %s — %s (%.1f s) ===" % (etiqueta, os.path.basename(ruta), segs))
    status, datos, crudo, tardo = pedir(key, ruta)
    if status in (429, 503):
        print("HTTP %d en %.2f s — reintento único en 8 s" % (status, tardo))
        time.sleep(8)
        status, datos, crudo, tardo = pedir(key, ruta)
    print("HTTP %s en %.2f s" % (status, tardo))

    if status != 200 or datos is None:
        print("→ ¿aceptó audio/wav?: NO se pudo determinar (la llamada falló)")
        print("→ error crudo: %s" % crudo[:600])
        return

    texto = texto_de(datos)
    print("→ ¿aceptó audio/wav?: SÍ (200 con %d caracteres de texto)" % len(texto))
    print("\n--- Forma exacta de la respuesta ---")
    print(forma(datos), end="")
    etiquetas = any(m in texto for m in ("Speaker", "Hablante", "speaker", "<"))
    print("--- Diarización ---")
    print("¿etiquetas de hablante dentro del texto?: %s"
          % ("SÍ (marcas en el string)" if etiquetas else "no se ven marcas"))
    claves = set()

    def recorrer(n):
        if isinstance(n, dict):
            for k, v in n.items():
                claves.add(k)
                recorrer(v)
        elif isinstance(n, list):
            for v in n:
                recorrer(v)

    recorrer(datos)
    pistas = sorted(
        k for k in claves
        if any(p in k.lower() for p in ("speaker", "time", "diar", "word", "segment"))
    )
    print("¿estructura con tiempos/hablantes?: %s"
          % (", ".join(pistas) if pistas else "ninguna clave de ese tipo"))
    print("\n--- Texto transcrito ---")
    print(texto if texto else "(vacío)")
    print("\n--- JSON crudo (primeros 3000 caracteres) ---")
    print(json.dumps(datos, ensure_ascii=False, indent=1)[:3000])


def main():
    solo_audio = "--solo-audio" in sys.argv
    key = None if solo_audio else leer_key()
    audios = asegurar_audios()
    if solo_audio:
        print("\nSolo audio: no se llamó a la API.")
        return
    for etiqueta, ruta, segs in audios:
        probar(key, etiqueta, ruta, segs)
    print("\nProbe de diarización terminado.")


if __name__ == "__main__":
    main()
