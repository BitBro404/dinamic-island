# 2026-11-22 · Presencia distingue al usuario de otras personas

## Solicitud
«¿Hay posibilidad de que la tarea que monitoriza si estoy frente al monitor bloquee la pantalla si no soy yo
quien está ahí?» Evaluada y aprobada por el usuario («si» al plan). Decisiones D1–D6 en `plan.md`.

## Resultado
| Tarea | Cambio | Dónde | Prueba |
|---|---|---|---|
| T1 | Descarga de YuNet/SFace con tamaño + SHA-256, reutilización, `0700/0600`, `ModelError` | `services/identity.py` (`ensure_models`) | `test_identity.py` |
| T2 | Galería (1 ancla + 5 rotativas) persistida sin imágenes; bandas `me ≥ 0.363`, `other < 0.25`, duda entre medias | `identity.Gallery`, `IdentityVerifier` | `test_identity.py` |
| T3 | Decisión pura y estados «Otra persona» / «¿Eras tú?» | `decide()`, `_LABELS`, `_ACCENT` | `test_presence_identity.py`, `test_presence_identity_page.py` |
| T4 | Captura única, `camera_mutex`, identidad integrada, `answer()`, `enroll()`, `clear_identity()` | `services/presence.py` | `test_presence_identity.py`, `test_detector.py` |
| T5 | Registro/borrado, texto de privacidad y tarjeta con foto en memoria | `pages/presence.py` | `test_presence_identity_page.py` |
| T6 | Una muestra al día a hora aleatoria, solo con input reciente; caducidad de 20 s | `next_sample_time()`, `Presence` | `test_presence_identity.py`, `test_identity.py` |
| T7 | README y documentación de niveles; gitignore de `gallery.json`; arnés visual | `README.md`, `docs/DOCUMENTACION.md`, `.gitignore`, fixture | `make check` |

## Seguridad y privacidad
- Cara no reconocida → ausencia (puede bloquear). Sin cara con plantilla → también ausencia.
- Duda, cámara ocupada, en llamada, error, sin OpenCV o sin modelos → fail-open, nunca bloquea.
- La imagen vive solo en RAM (`pending_prompt["frame"]`) y en la miniatura de la tarjeta; ambas se limpian al
  responder o caducar. En disco solo hay un JSON privado con vectores y metadatos; `gallery.json` ignorado por git.
- Sin plantilla, el comportamiento es idéntico al anterior. Regla S2 intacta: si el bloqueo falla, no se apaga
  la pantalla.

## Pruebas y verificación
- `make check` → **456 pruebas OK** (TDD, rojo verificado en cada tarea).
- Arnés visual con foto sintética: `/tmp/opencode/presence-identity/presence.png`; el fixture usa una galería
  temporal para no tocar la real.
- `./install.sh` ejecutado con autorización: versión nueva activa. Modelos descargados y verificados (sha-ok,
  `0600` en carpeta `0700`); SFace y YuNet cargan con el código instalado.
- Correcciones halladas en validación: (1) con plantilla y sin cara se trataba la ausencia como duda y nunca
  bloqueaba; (2) los hashes publicados tenían 63 caracteres y la descarga real siempre fallaba (añadida prueba
  que exige SHA-256 de 64 hex); (3) la miniatura de la tarjeta no se liberaba al responder/caducar; (4) el
  arnés escribió una galería falsa en la config real, ya borrada y corregida en el fixture.

## Efecto visible / limitaciones
- Botones nuevos en **Presencia** → «IDENTIDAD»; la píldora puede mostrar «Otra persona» y «¿Eras tú?».
- La galería sobrevive a reinicios y a `./install.sh`; **Borrar mi rostro** la elimina.
- No hay detección de vida (fotos o pantallas pueden engañar) y una confirmación ajena puede contaminar la
  galería: se mitiga con actividad reciente, caducidad y borrado.
- **Pendiente de validación manual del usuario (C8–C11)**: registrar con cámara real, comprobar que no bloquea
  con él y que bloquea con otra persona, forzar duda/muestra diaria, responder «sí» y «no» y borrar. Hasta
  entonces no se marca la tarea como aceptada.
