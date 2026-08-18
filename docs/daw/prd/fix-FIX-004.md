# Fix FIX-004: Corregir mismatch upper()/lower() en obtener_por_patente_normalizada

- **Bug**: `obtener_por_patente_normalizada` compara con `func.upper(Vehiculo.patente)`, pero el
  índice único creado por la migración `0003_patente_unique_case_insensitive` está construido sobre
  `lower(patente)`. Postgres no puede usar un índice funcional sobre `lower(x)` para resolver una
  condición sobre `upper(x)` — son expresiones distintas para el planner. Confirmado con `EXPLAIN`
  contra la base real: la query actual hace `Seq Scan` (recorre toda la tabla) en vez de
  `Index Scan`. El resultado sigue siendo correcto, pero cada búsqueda por patente — incluida la que
  usan `crear_vehiculo`/`modificar_vehiculo` en cada alta y modificación — no está indexada,
  contradiciendo NFR-01 del PRD de FEAT-004 ("lookups indexados, O(log n)").
- **Change**: `backend/app/features/vehiculos/repository.py:64` — cambiar
  `func.upper(Vehiculo.patente) == patente.strip().upper()` por
  `func.lower(Vehiculo.patente) == patente.strip().lower()`, para que la expresión de la query
  coincida con la expresión indexada por la migración `0003`.
- **Regression test**: `test_obtener_por_patente_normalizada_usa_el_indice_lower` (nuevo, en
  `backend/tests/test_vehiculos_service.py`) — corre `EXPLAIN` sobre la query real después de aplicar
  la migración y confirma `Index Scan using ix_vehiculos_patente_lower_unique`. Falla antes del fix
  (`Seq Scan`), pasa después (`Index Scan`).
- **Risk**: none — el resultado de la comparación no cambia (ambos lados quedan normalizados a
  minúscula en vez de mayúscula; sigue siendo case-insensitive). Los tests existentes de
  case-insensitividad (`test_obtener_por_patente_normalizada_encuentra_por_cualquier_casing`,
  `test_crear_vehiculo_rechaza_patente_duplicada_otro_casing`,
  `test_modificar_vehiculo_rechaza_patente_duplicada_otro_casing`) ya cubren que la búsqueda sigue
  encontrando por cualquier casing — solo cambia si Postgres puede usar el índice para resolverla.
