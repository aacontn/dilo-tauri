# Spike 3 — diarización de Gemini por `:generateContent` (2026-09-20)

Compuerta de entrada del plan de reuniones
(`specs/2026-08-27-reuniones-en-linea-design.md` → "Verificación pendiente").
El probe original es TypeScript y esta máquina no tiene bun ni node, así que se
portó a Python 3.9 de sistema.

## Qué se portó

`scripts/probes/gc-probe.py` — port de `gc-probe.ts`, sin dependencias externas
(`urllib`, `json`, `subprocess`, `wave`). Diferencias con el original:

- **Key desde el Llavero**, no desde el settings store de Dilo (que en esta
  máquina no existe): `security find-generic-password -a dilo -s
  dilo-gemini-api-key -w`. Viaja solo en el header `x-goog-api-key`; nunca en la
  URL ni en un log. Sin key: mensaje con el comando para agregarla y **salida 2**.
- **Genera sus audios** con `say` y los arma con `wave` (400 ms de silencio entre
  turnos), en `/Volumes/SSD2/scratch/dilo-probes/` — fuera del repo, porque SSD2
  es caché regenerable. Dos archivos, 16 kHz mono PCM 16-bit:
  - `reunion-2.wav` — 20,4 s, 2 voces (Mónica es_ES / Eddy es_MX), 5 turnos.
  - `reunion-5.wav` — 21,5 s, 5 voces (Mónica, Eddy es_MX, Paulina, Rocko es_ES,
    Grandma es_ES), un turno cada una. Hay 18 voces en español instaladas, así
    que los 5 hablantes del spec se cubren de verdad.
- **Reintento único** ante 429/503 con 8 s de espera (el 503 de congestión fue lo
  que bloqueó el probe del 2026-08-27).
- Imprime por audio: código HTTP y tiempo, si aceptó `audio/wav`, la forma exacta
  de la respuesta (árbol de claves + las claves tipo `speaker`/`time`/`word`/
  `segment` que aparezcan en cualquier nivel), si hay etiquetas de hablante
  dentro del texto, el texto transcrito y 3000 caracteres del JSON crudo.

El body es el mismo del probe TS: `inline_data` con `audio/wav` y
`generationConfig.audioTranscriptionConfig {wordTimestamp: true, diarization:
true}`. Se mantiene sin `mode` a propósito: el spec del motor documenta que
`mode` no funciona en `:generateContent` y la salida sale verbatim.

## Cómo correrlo

```bash
security add-generic-password -a dilo -s dilo-gemini-api-key -U -w   # pide la key por teclado
python3 scripts/probes/gc-probe.py
```

`--solo-audio` regenera los WAV sin llamar a la API ni necesitar la key. Borrar
los WAV y volver a correr los regenera.

## Resultados

**Pendiente: falta la key en el Llavero.** Verificado hasta donde se puede sin
ella: los dos audios se generan bien (`wave` confirma 1 canal / 16 bits /
16 kHz) y el script corre limpio hasta el chequeo de la key, que sale con
código 2 y el mensaje correcto. Las tres preguntas del spec —forma de la
respuesta de diarización, si `audio/wav` basta o exige FLAC, y el
comportamiento con 2 y 5 hablantes— siguen sin responder.

Siguiente paso: agregar la key al Llavero, correr el probe y pegar acá la salida
de los dos audios. El plan de reuniones sigue sin poder ejecutarse hasta eso.
