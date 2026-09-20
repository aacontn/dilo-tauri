# Dilo — App nativa para Mac (dirección y v1: dictado que parece terminado)

**Fecha:** 2026-09-20 · **Estado:** dirección aprobada por Alfonso en conversación; **compuerta de entrada pendiente** (ver §Verificación) · **Base:** [2026-07-22 Plataforma conversacional abierta](2026-07-22-dilo-plataforma-conversacional-abierta.md), [2026-08-27 Reuniones en línea](2026-08-27-reuniones-en-linea-design.md), [2026-07-31 Conversación por voz](2026-07-31-conversacion-por-voz-design.md) · **Reemplaza:** la premisa "núcleo Rust intacto, nada de reescritura" del [rebrand](2026-07-12-dilo-rebrand-design.md)

## El problema

Dilo tiene 46.004 líneas de Rust; Handy tiene 28.992. De las 17.000 propias,
**13.000 son reuniones, diarización, captura de audio del sistema y TTS** — las
tres cosas que nunca rindieron (evaluación de Alfonso: "el motor de reuniones
es pobre"; "la parte hablada tampoco funcionó nunca bien"). En Tauri esas
piezas se cablearon a mano contra ONNX y `cpal`; en Mac nativo vienen hechas
y mantenidas por otros (SpeechAnalyzer, FluidAudio, taps de Core Audio,
`AVAudioEngine` con cancelación de eco).

Además, Handy (`upstream`) reescribió su historia: el merge-base cayó a
febrero de 2025 y `git cherry` da 295 commits propios contra 662 duplicados.
Ya no existe el "merge barato" que justificaba mantener el núcleo cerca de
upstream. Y macOS 27 impone Liquid Glass a toda app recompilada con Xcode 27;
una UI en WKWebView no lo hereda.

Tracción real a la fecha: 16 ⭐, ~70 descargas acumuladas. El cuello no es
la app: es que no parece un producto terminado.

## Lo que se midió antes de decidir (2026-09-20)

| Dato | Valor |
| --- | --- |
| Rust propio que no rinde | `meeting.rs` 6.485 + diarización 4.400 + `system_audio/macos.rs` 1.510 + TTS 1.850 líneas |
| Handy hoy | v0.9.7, 31.9k ⭐; resolvió solo el Dock (`launch as accessory`), audio de cola, micrófono real-time |
| SpeechAnalyzer (macOS 26+) | español, parciales en streaming, 0 MB, ~2× más rápido que Whisper turbo; sin diarización |
| FluidAudio (Swift, Apache 2.0) | Parakeet v3 batch, Silero, diarización streaming (Sortformer 4 / LS-EEND 10), PocketTTS en español. Streaming ASR sólo inglés |
| Talkify (MIT, 554 ⭐, un autor, release semanal) | Swift 6, SpeechAnalyzer + FoundationModels, notch propio en `CoreHUD/`, pegado por AX/CGEvent/pasteboard, reducer testeable, ~11k líneas, única dependencia Sparkle |
| Yap (MIT) | dictado Mac con SpeechAnalyzer en ~3k líneas, 4 MB, 60 MB en reposo |
| Granola (referencia de notetaker) | transcript **Me/Them** (mic vs sistema), sin diarización en escritorio, **manda el audio a su proveedor**, no guarda audio, no acepta grabaciones |
| Sandbox App Store | bloquea la API de Accesibilidad hacia otras apps "sin importar lo concedido"; pegar (pasteboard + Cmd+V sintético) y atajos (`CGEventTap` + Input Monitoring) sí funcionan. Precedente: TypeMeIt, dos builds |
| Nube de voz | Gemini 3.8 Live ≈ US$0,01–0,02/min; OpenAI realtime 4–5×; Gemini 3.5 Transcribe US$0,005/min, diariza 8 |

## Decisiones tomadas (con Alfonso)

- **Dilo se reescribe nativo en Swift, sólo Mac** (Apple Silicon, macOS 26+).
  No se planea portar: Swift no exporta. Superwhisper y VoiceInk son sólo Mac.
- **Base: fork de Talkify**, en `/Volumes/SSD 1/Dilo/mac/`, con remote
  `upstream`. `CoreHUD/`, `Dictation/` e `Input/` se mantienen cerca del
  original para que los merges sean baratos; lo de Dilo va en módulos aparte.
  Se conserva el copyright MIT de Talkify y se añade el propio, como se hizo
  con Handy.
- **De Handy/Dilo-Tauri se porta el producto, no el código**: modos con
  atajo y proveedor, palabras propias, historial, onboarding, proveedores de
  post-proceso, limpieza de muletillas del español, copy. Se reescribe en
  Swift leyendo los specs, no los `.rs`.
- **El Tauri (`Dilo/app`) se congela en 0.3.2.** No se borra: README apunta
  al nativo, releases quedan. Cero horas más ahí.
- **Meta: la mejor, la más rápida y la más liviana.** En números (§3).
- **El notch es la identidad**, no un adorno: tres estados (dictando, en
  reunión, conversando) en el mismo lugar. Píldora idéntica cuando no hay
  notch (Mac mini, monitores externos).
- **Notetaker: nada menos que Granola** (spec propio, v2). Dos flujos —mic =
  Yo, audio del sistema = Ellos—, en vivo local, WAV a disco desde el primer
  segundo, notas escritas + transcript → notas mejoradas con LLM en nube.
- **Venta directa desde el inicio; App Store es aspiración a hacer realidad.**
  Dos targets desde el día uno (`Dilo`, `Dilo-MAS`); si el sandbox bloquea
  el tap de audio, App Store queda con una versión sólo-dictado.
- **El dinero se decide después.** El código ya es MIT; se parte con
  donaciones + binario gratis y se cobra recién con el notetaker a nivel
  Granola. Si App Store es "mucho webeo", donaciones y punto.
- **Fases, cada una vendible sola:** v1 dictado que parece terminado → v2
  notetaker híbrido → v3 conversación. La voz **se diseña en v1 y no se
  construye en v1**.

## Diseño

### 1 · Qué se toma de Talkify y qué se agrega

| Módulo Talkify | Se usa | Dilo agrega |
| --- | --- | --- |
| `CoreHUD/` (notch, placement, shaders) | tal cual | estados reunión/conversación; nivel de ventana sobre pantalla completa (issue #84 de Talkify; Handy lo resuelve) |
| `Dictation/` (SpeechAnalyzer, sesión, pegado) | tal cual | motor doble (§2), limpieza de muletillas es, historial serio, diccionario personal |
| `Input/` (atajos, hold/latch, fn) | tal cual | **atajo por modo** (spec 2026-08-05) |
| `PromptShaping` (FoundationModels on-device) | tal cual | **modos** con proveedor (on-device, Gemini, Claude vía FoundationModels server, OpenAI) — spec 2026-07-29 |
| `DropTranscription/` | tal cual | base del "arrastrar una grabación" del notetaker |
| `ReadAloud/` (`AVSpeechSynthesizer`) | tal cual | queda como TTS de v1; PocketTTS entra en v3 |
| `Translation/`, `Insights/`, `Updates/` (Sparkle) | tal cual | Sparkle sólo en target directo |

### 2 · Motor doble

- **Apple** (`SpeechTranscriber`): por defecto. 0 MB, español, parciales.
- **Parakeet v3 vía FluidAudio**: segundo motor, para quien prefiera
  consistencia entre máquinas o esté bajo macOS 26 (si se decide bajar el
  mínimo; hoy no). Se descarga a pedido como en Handy.
- Contrato `SpeechEngine` mínimo: `start(locale)`, flujo de parciales,
  `finish() -> texto`. Nada del resto de la app sabe cuál corre.
- **Gemini 3.5 Transcribe** como tercer motor EN LÍNEA (se porta el diseño del
  2026-08-27), con la misma honestidad LOCAL / EN LÍNEA de la tarjeta.

### 3 · Los números no negociables

| Métrica | Meta | Por qué |
| --- | --- | --- |
| RAM en reposo | **< 60 MB** | Yap lo logra con el mismo motor |
| CPU en reposo | **~0 %** | el tap de teclado no puede costar |
| Texto en pantalla tras soltar la tecla | **< 300 ms** | con parciales, el texto ya está cuando sueltas; es la ventaja contra Wispr (nube) |
| Arranque en frío | **< 1 s** | |
| Descarga | **< 20 MB** sin modelos | Talkify hoy ronda eso |
| Micrófono Bluetooth | **aviso visible** mientras abre (issue #130 de Talkify) y *lazy close* como Handy | |

Se miden en CI con un script, no a ojo. Si un cambio rompe un número, no
entra.

### 4 · Capa de capacidades (sandbox desde el día uno)

Todo lo que dependa de la API de Accesibilidad hacia otras apps —foco antes
de pegar, releer lo pegado, título de la ventana, "pegado directo"— va detrás
de un protocolo `HostCapabilities` con dos implementaciones: completa (target
directo) y sandbox (App Store). En sandbox la app **esconde lo que no puede
hacer** (patrón TypeMeIt), nunca falla. Talkify usa AX en 17 puntos; se
inventarían en la primera tarea del plan.

### 5 · Cimientos para v2 y v3 que se ponen en v1

- **Grafo de audio único** con `AVAudioEngine` en modo voice-processing
  (cancelación de eco del sistema): sin eso no hay interrupción a media frase
  en v3. Se enciende desde v1 aunque v1 sólo grabe.
- **Máquina de sesión** con tres modos (dictado, reunión, conversación) y un
  solo escenario (el notch). Dictado es el único modo implementado en v1.
- **Contrato de proveedor S2S** ya definido en el spec de conversación: se
  declara la interfaz, no se implementa.
- **WAV a disco** como primitiva de la sesión, no de reuniones.

### 6 · Español primero

Se conserva todo lo que ya es de Dilo: locale `es` escrito a mano (tuteo,
directo, cero relleno), muletillas del español, voseo y modismos, Spanglish
técnico intacto. Es lo único que ningún fork de Handy ni de Talkify tiene.

## Alcance de v1

Dictado con motor doble, modos con atajo y proveedor, palabras propias,
historial, onboarding en español, notch con estado de dictado y píldora sin
notch, firmado y notarizado, updater (directo), target MAS compilando aunque
no se publique. Nada de reuniones ni de voz más allá de los cimientos de §5.

## Restricciones transversales

- Nada de nombres de backend ni reglas de negocio en el núcleo (spec
  plataforma abierta). Los proveedores entran por contrato.
- Credenciales en Llavero, nunca en `UserDefaults` ni en texto plano.
- Todo copy visible en español autoría propia; inglés como segunda locale.
- Cada feature nueva pasa por spec con medición previa. Es la regla que este
  proyecto ya pagó dos veces por saltarse.

## Riesgos, nombrados

1. **SpeechAnalyzer en español chileno.** Si no rinde en el audio real de
   Alfonso, el motor por defecto pasa a Parakeet v3 y se pierde el "0 MB".
   Se sabe en diez minutos (§Verificación 1).
2. **Talkify tiene un solo autor y seis semanas de vida.** Mitigación: es un
   fork, no una dependencia; si upstream muere, el código queda.
3. **El sandbox y el tap de audio del sistema.** Plausible, no confirmado.
   Si no funciona, App Store = sólo dictado. No mata el plan.
4. **Dos targets es trabajo real** (dos licencias, dos updaters). Se paga una
   vez al inicio; retrofitear después cuesta meses.
5. **Mac mini / monitores externos sin notch** son el 80 % del uso de
   Alfonso: la píldora tiene que sentirse igual de bien que el notch.
6. **Intel queda fuera.** Se acepta; el Tauri 0.3.2 sigue disponible para
   ellos, congelado.

## Verificación pendiente (compuerta de entrada del plan)

Ninguna tarea del plan se ejecuta hasta tener estos cuatro números:

1. **Talkify en español, sin tocar código.** Instalar, poner `es`, dictar diez
   minutos de uso real (prompts, terminal, Slack). Veredicto: ¿mejor, igual o
   peor que Dilo 0.3.2 con Parakeet v3?
2. **Build sandboxed de Talkify.** Activar App Sandbox en el target, firmar,
   y probar: ¿pega en Cursor y en el terminal? ¿el atajo global responde?
   ¿`AudioHardwareCreateProcessTap` entrega audio del sistema con el
   entitlement `audio-input`? Tres sí/no.
3. **Repetir `bun scripts/probes/gc-probe.ts`** (quedó en 503 el 2026-08-27):
   formato de la diarización de Gemini y comportamiento con 2 y 5+ hablantes
   en español. Desbloquea el spec de v2.
4. **Una reunión real de Alfonso por dos flujos** (mic + tap), con WAV a
   disco, transcrita por SpeechAnalyzer flujo por flujo. ¿Se pierde algo?
   ¿Cuánto tarda el parcial en aparecer?

Los resultados se pegan aquí, con fecha, antes de escribir el plan.

## Fuera de alcance

Windows y Linux (se congelan con el Tauri), Intel, reuniones (spec propio
tras la verificación 3 y 4), conversación y wake word (spec propio tras v2),
migración de datos desde el Tauri (se evalúa en el plan; probablemente sólo
historial y palabras propias), cualquier cambio en `Dilo/app` que no sea
el README de congelamiento.
