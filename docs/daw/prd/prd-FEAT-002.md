# PRD FEAT-002: Menú principal y rediseño visual del frontend

| Field | Value |
|-------|-------|
| Ticket | FEAT-002 |
| Tracker | none |
| Date | 2026-08-08 |
| PRD loops | 0 |

## Context and Problem

Hoy la app arranca directamente en la vista pública de consulta/alta de reservas
(`ReservasPublicPage`), sin ningún punto de entrada que oriente al usuario sobre las 3 funciones
disponibles (consultar/reservar, gestionar reservas propias, administrar el pool). El acceso al
listado de reservas y al panel de administración depende de que el usuario sepa navegar
manualmente. Además, la interfaz actual es funcional pero visualmente austera (sin paleta de
colores definida ni iconografía), lo que dificulta identificar de un vistazo qué hace cada
sección.

Este ticket agrega una pantalla de menú principal como punto de entrada, con navegación explícita
hacia las 3 áreas ya existentes de la app, y aplica un rediseño visual (paleta de colores +
iconografía SVG consistente) sobre el menú y esas 3 áreas.

## Goals

- Dar un punto de entrada único y claro que oriente al usuario hacia la función que necesita
  (consultar/reservar, gestionar sus reservas, o administrar el pool).
- Unificar la identidad visual de la app (colores + íconos) en las 4 pantallas (menú + 3 ramas).
- No modificar la lógica de negocio ni el comportamiento funcional ya existente de las 3 ramas —
  este ticket es de navegación y presentación, no de funcionalidad nueva.

## Functional Requirements

- FR-01: El sistema debe mostrar una pantalla de menú principal al iniciar la aplicación, con 3
  opciones de navegación (Administrador, Gestionar reservas, Consultar), cada una identificada con
  un ícono representativo.
- FR-02: El sistema debe navegar a la vista correspondiente al seleccionar cada opción del menú:
  Consultar → vista de disponibilidad y alta de reserva (`ReservasPublicPage`, sin cambios
  funcionales); Gestionar reservas → vista de listado, filtro y cancelación (`ReservasListado`, sin
  cambios funcionales); Administrador → vista de login, o el panel de administración directamente
  si ya hay una sesión activa (`VehiculosAdminPage`, sin cambios funcionales).
- FR-03: El sistema debe mostrar un botón "Volver al menú" en las 3 ramas, que regresa a la
  pantalla de menú principal.
- FR-04: El sistema debe mostrar, dentro de la rama Administrador y solo mientras haya una sesión
  activa, un botón "Cerrar sesión" independiente del botón "Volver al menú".
- FR-05: El sistema debe aplicar una paleta de colores y un sistema de íconos SVG consistente en
  las 4 pantallas (menú principal y las 3 ramas).

## Non-Functional Requirements

- NFR-01: El sistema no debe depender de imágenes externas (fotos, CDNs de terceros) para el
  rediseño visual: los íconos deben ser SVG inline o componentes locales del proyecto, sin
  requests de red adicionales ni nuevas dependencias de npm.

## Acceptance Criteria

- AC-01 (FR-01): WHEN el usuario abre la aplicación, THE sistema SHALL mostrar el menú principal
  con las 3 opciones (Administrador, Gestionar reservas, Consultar), cada una con su ícono.
- AC-02 (FR-02): WHEN el usuario selecciona "Consultar" en el menú, THE sistema SHALL navegar a la
  vista de disponibilidad y alta de reserva, sin alterar su comportamiento actual.
- AC-03 (FR-02): WHEN el usuario selecciona "Gestionar reservas" en el menú, THE sistema SHALL
  navegar a la vista de listado/filtro/cancelación, sin alterar su comportamiento actual.
- AC-04 (FR-02): WHEN el usuario selecciona "Administrador" en el menú, THE sistema SHALL navegar
  al login si no hay sesión activa, o directamente al panel si ya la hay.
- AC-05 (FR-03): WHEN el usuario está en cualquiera de las 3 ramas y hace clic en "Volver al
  menú", THE sistema SHALL regresar a la pantalla de menú principal.
- AC-06 (FR-04): IF hay una sesión de administrador activa dentro de la rama Administrador, THEN
  THE sistema SHALL mostrar un botón "Cerrar sesión" separado de "Volver al menú"; WHEN se hace
  clic en "Cerrar sesión", THE sistema SHALL finalizar la sesión y mostrar el login.
- AC-07 (FR-05): THE sistema SHALL usar la misma paleta de colores y el mismo set de íconos SVG en
  el menú principal y en las 3 ramas.

## Out of Scope

- Fotos reales o cualquier imagen que no sea un ícono/ilustración SVG local.
- Selector de tema claro/oscuro.
- Animaciones o transiciones avanzadas entre pantallas (más allá de las que el propio framework
  provea por defecto).
- Cambios de backend: ningún endpoint ni schema se modifica en este ticket.
- Cambios funcionales dentro de las 3 ramas existentes (validaciones, campos, reglas de negocio) —
  solo cambia su envoltorio visual y el botón "Volver al menú"/"Cerrar sesión".
- Internacionalización (i18n) o soporte multi-idioma.
- Accesibilidad WCAG completa (más allá de las buenas prácticas ya usadas en el proyecto —
  `role="alert"`/`role="status"`, labels asociados a inputs).

## Risks and Mitigations

| ID | Riesgo | Impacto | Probabilidad | Mitigación sugerida |
|-----|--------|---------|--------------|---------------------|
| R-01 | "Más bonito con colores e imágenes" es subjetivo y puede derivar en iteraciones de diseño sin fin. | Medio | Medio | La paleta de colores concreta y el set de íconos se definen y se muestran al usuario para aprobación explícita en la fase PLAN, antes de escribir código — no se decide en CODE. |
| R-02 | Al envolver las 3 vistas existentes en la nueva navegación, se podría romper algún test o comportamiento ya funcionando (regresión). | Alto | Bajo | Los 3 componentes existentes (`ReservasPublicPage`, `ReservasListado`, `VehiculosAdminPage`) se reutilizan sin tocar su lógica interna — solo se agregan el wrapper de navegación y el botón de volver. La suite completa (140 tests) corre en cada bloque del closeout de CODE. |

## Dependencies

| ID | Dependencia | Descripción |
|-----|-------------|-------------|
| D-01 | FEAT-001a/c/d/e | Este ticket reutiliza las 3 vistas ya implementadas (`ReservasPublicPage`, `ReservasListado`, `VehiculosAdminPage`) sin modificar su lógica de negocio. |
| D-02 | Stack tecnológico | Frontend: React + Vite (sin librería de ruteo, mismo criterio ya establecido en FEAT-001c/d — la navegación entre menú y ramas se resuelve con estado local, no con una librería nueva). |
