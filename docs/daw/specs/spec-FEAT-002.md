# Spec FEAT-002: Menú principal y rediseño visual del frontend

| Field | Value |
|-------|-------|
| Ticket | FEAT-002 |
| PRD | docs/daw/prd/prd-FEAT-002.md |
| Tier | FEATURE |
| Date | 2026-08-08 |
| Spec loops | 0 |

## Summary

Se agrega una pantalla de menú principal (`MenuPrincipal`) como nuevo estado inicial de
navegación en `App.jsx`, y una hoja de estilos global (`index.css` + `components/icons.jsx`) que
estiliza elementos nativos (botones, inputs, encabezados) para que las 3 pantallas ya existentes
(`ReservasPublicPage`, `ReservasListado`, `VehiculosAdminPage`/`LoginAdmin`) hereden el nuevo
aspecto visual **sin que su código interno se modifique una sola línea**. La navegación sigue sin
librería de router (reafirma la decisión ya tomada en spec Block 4 de FEAT-001c y Block 3 de
FEAT-001d: proyecto chico, tres/cuatro pantallas, estado local alcanza).

**Decisión de PLAN confirmada con el usuario:** se preserva el invariante ya existente en
`App.jsx` — con sesión de administrador activa, la app SIEMPRE muestra el panel admin,
independientemente del valor de `vista`. Esto significa que el botón "Volver al menú", cuando se
usa desde dentro de la rama Administrador con sesión activa, también cierra la sesión (es la única
forma de que el botón tenga efecto visible dado que el guard de sesión tiene prioridad). El botón
"Cerrar sesión" es una acción distinta: cierra la sesión pero permanece en la rama Administrador
(vuelve a mostrar el login), en vez de saltar al menú. Ambos botones cumplen así con AC-06
("independientes", con destinos distintos) sin reabrir el guard de sesión existente.

## Coverage: PRD → blocks

| Requirement | Covered by |
|---|---|
| FR-01 | Block 2 |
| FR-02 | Block 3 |
| FR-03 | Block 3 |
| FR-04 | Block 3 |
| FR-05 | Block 1 |
| NFR-01 | Strategy: `components/icons.jsx` son SVG inline escritos a mano (sin paquetes de íconos, sin `<img src="https://...">`, sin fuentes de íconos tipo Font Awesome vía CDN) |

## Dependencies between blocks

Block 1 (fundación visual) → Block 2 (MenuPrincipal, usa los íconos de Block 1) → Block 3
(integración en App.jsx, usa MenuPrincipal de Block 2 y las clases CSS de Block 1). Orden
secuencial estricto.

## Paleta de colores y set de íconos (para aprobación explícita, R-01 del PRD)

**Paleta** (variables CSS en `:root`, tema claro único — sin selector de tema oscuro, ver Out of
Scope del PRD):

| Variable | Valor | Uso |
|---|---|---|
| `--color-primary` | `#1D4ED8` | Botones primarios, header, bordes activos |
| `--color-primary-hover` | `#1E40AF` | Estado `:hover`/`:focus` de botones primarios |
| `--color-accent` | `#F59E0B` | Íconos del menú principal |
| `--color-success` | `#16A34A` | Mensajes `role="status"` (éxito) |
| `--color-error` | `#DC2626` | Mensajes `role="alert"` (error) |
| `--color-bg` | `#F1F5F9` | Fondo general de la página |
| `--color-surface` | `#FFFFFF` | Fondo de tarjetas/formularios |
| `--color-text` | `#0F172A` | Texto principal |
| `--color-text-muted` | `#475569` | Texto secundario/labels |
| `--color-border` | `#CBD5E1` | Bordes de inputs/tarjetas/tablas |

**Íconos** (`components/icons.jsx`, SVG 24×24, `stroke="currentColor"`, sin relleno, trazo
simple):

| Ícono | Uso |
|---|---|
| `IconAuto` | Opción "Consultar" del menú |
| `IconClipboard` | Opción "Gestionar reservas" del menú |
| `IconLock` | Opción "Administrador" del menú |
| `IconArrowLeft` | Botón "Volver al menú" |
| `IconLogout` | Botón "Cerrar sesión" |

## Block 1 — Fundación visual (paleta + CSS global + íconos SVG)

**Files**
- `frontend/src/index.css` (new) — variables CSS de la paleta de arriba + estilos base de
  elementos nativos
- `frontend/src/main.jsx` (modified) — agrega `import "./index.css"` antes del render
- `frontend/src/components/icons.jsx` (new) — los 5 componentes SVG de la tabla de arriba
- `frontend/src/components/icons.test.jsx` (new)

**Logic**

`index.css` tiene DOS secciones estrictamente separadas, para cerrar el WARN de
`daw-arch-auditor` sobre fuga de estilos entre el menú y las pantallas funcionales:

1. **Reset/paleta sobre elementos nativos** (`body`, `button`, `input`, `select`, `h1`, `h2`,
   `ul`, `li`, `form`, `[role="alert"]`, `[role="status"]`): tipografía, colores de la paleta,
   `padding`/`border-radius` conservadores (botones/inputs con aspecto consistente en toda la
   app), sin asumir la estructura de tarjetas del menú. Estos selectors son los que
   `ReservasPublicPage`/`ReservasListado`/`VehiculosAdminPage`/`LoginAdmin` heredan sin cambiar su
   código.
2. **Clases scoped al menú** (`.menu-shell`, `.menu-grid`, `.menu-card`, `.app-header`): layout de
   grid/tarjetas con sombra, usadas EXCLUSIVAMENTE por `MenuPrincipal` (Block 2) y por el
   `<header>` de navegación de `App.jsx` (Block 3). Ningún selector de esta sección apunta a un
   elemento nativo sin clase — así un cambio en el layout del menú nunca se filtra a un botón
   funcional de `ReservasListado`/`VehiculosAdminPage`.

`components/icons.jsx` exporta 5 funciones de componente, cada una un `<svg>` con `viewBox="0 0
24 24"`, `fill="none"`, `stroke="currentColor"`, sin estado ni props más allá de las que React
pasa por defecto (`...props` para permitir `aria-hidden`/`className` desde el caller).

**Error handling**

N/A — este bloque no maneja errores (sin fetch, sin input de usuario).

**Required tests**

- [ ] `renderiza cada ícono como un elemento svg` — smoke test iterando los 5 exports de
      `icons.jsx`, confirma que cada uno renderiza un `<svg>` sin lanzar.
- [ ] `index.css define las 10 variables de la paleta` — lee el archivo con `fs.readFileSync` (test
      de Node, no de DOM) y confirma por regex que las 10 variables de la tabla de paleta están
      declaradas en `:root`. No reemplaza la verificación visual de AC-07, pero cierra la parte
      mecánicamente verificable (F-SPEC-02): que la fuente única de la paleta existe y no se
      dispersa en valores hardcodeados sueltos.

**Completion criterion**

El test pasa; `main.jsx` importa `index.css` sin errores de build (`npm run build` no falla).
Verificación visual (no automatizada, ver nota de AC-07 más abajo) vía `/run`: las 4 pantallas
muestran la misma paleta de colores en sus botones/inputs.

## Block 2 — Componente MenuPrincipal

**Files**
- `frontend/src/features/menu/MenuPrincipal.jsx` (new)
- `frontend/src/features/menu/MenuPrincipal.test.jsx` (new)

**Logic**

Componente puramente presentacional. Recibe `onSelect(rama)` por prop (`rama` ∈
`"consultar" | "gestionar" | "admin"`). Renderiza un array de configuración local (NO un array
importado de otro módulo — son 3 entradas fijas, no datos de negocio):

```js
const OPCIONES = [
  { rama: "consultar", label: "Consultar", Icono: IconAuto },
  { rama: "gestionar", label: "Gestionar reservas", Icono: IconClipboard },
  { rama: "admin", label: "Administrador", Icono: IconLock },
];
```

Mapeado con `.map()` sobre `OPCIONES`, cada tarjeta con `key={opcion.rama}` (cierra el WARN de
`daw-arch-auditor` sobre keys únicas — `rama` es un string fijo y único por definición, nunca un
índice de array). Cada tarjeta es un `<button type="button" className="menu-card"
onClick={() => onSelect(opcion.rama)}>` con el ícono y el label adentro.

**Error handling**

N/A — sin fetch, sin input, sin estados de error posibles.

**Required tests**

- [ ] `renderiza las 3 opciones con su texto` — confirma "Administrador", "Gestionar reservas" y
      "Consultar" visibles.
- [ ] `click en "Consultar" llama a onSelect con "consultar"`
- [ ] `click en "Gestionar reservas" llama a onSelect con "gestionar"`
- [ ] `click en "Administrador" llama a onSelect con "admin"`

**Completion criterion**

Los 4 tests pasan. `MenuPrincipal` no importa nada de `api/client.js` ni de `context/`.

## Block 3 — Integración de navegación en App.jsx

**Files**
- `frontend/src/App.jsx` (modified)
- `frontend/src/App.test.jsx` (new — hoy no existe ningún test de `App.jsx`)

**Logic**

`vista` pasa de 3 a 4 valores posibles: `"menu"` (nuevo, estado inicial por defecto en vez de
`"reservas"`), `"consultar"` (antes `"reservas"`), `"gestionar"` (antes `"listado"`), `"admin"`
(antes `"login"`).

**El guard de sesión existente NO se elimina** (decisión confirmada con el usuario en PLAN, ver
Summary): la condición `if (session) return <VehiculosAdminPage />` sigue evaluándose primero,
antes de mirar `vista`, exactamente como hoy. Se envuelve con el nuevo header de navegación:

```jsx
if (session) {
  return (
    <SessionContext.Provider value={{ session, setSession }}>
      <header className="app-header">
        <button type="button" onClick={() => setSession(null)}>
          <IconLogout aria-hidden="true" /> Cerrar sesión
        </button>
        <button type="button" onClick={() => { setSession(null); setVista("menu"); }}>
          <IconArrowLeft aria-hidden="true" /> Volver al menú
        </button>
      </header>
      <VehiculosAdminPage />
    </SessionContext.Provider>
  );
}

if (vista === "menu") {
  return <MenuPrincipal onSelect={setVista} />;
}

return (
  <SessionContext.Provider value={{ session, setSession }}>
    <header className="app-header">
      <button type="button" onClick={() => setVista("menu")}>
        <IconArrowLeft aria-hidden="true" /> Volver al menú
      </button>
    </header>
    {vista === "consultar" && <ReservasPublicPage />}
    {vista === "gestionar" && <ReservasListado />}
    {vista === "admin" && <LoginAdmin />}
  </SessionContext.Provider>
);
```

Nota explícita para quien lea el código después (reemplaza el docstring actual, que describía el
diseño de 3 vistas): el guard de sesión sigue teniendo prioridad absoluta sobre `vista` — es
intencional, no un bug. Un admin logueado NUNCA ve `ReservasPublicPage`/`ReservasListado`
directamente; para navegar ahí primero tiene que cerrar sesión (vía "Volver al menú" o "Cerrar
sesión", ambos lo hacen).

`ReservasPublicPage.jsx`, `ReservasListado.jsx`, `VehiculosAdminPage.jsx` y `LoginAdmin.jsx` **no
se tocan** — heredan el estilo únicamente por los selectors de elemento nativo de `index.css`
(Block 1).

**Error handling**

Sin cambios: `setUnauthorizedHandler(() => setSession(null))` sigue registrado igual que hoy —
ante un 401 de cualquier request autenticado, la sesión se limpia y (por el guard) el usuario cae
en la rama `vista==="admin"` mostrando `LoginAdmin`, sin pasar por el menú. Comportamiento
preexistente, sin cambios.

**Required tests**

- [ ] `al montar sin sesión, muestra el menú principal` — no `ReservasPublicPage` ni ningún otro
      contenido.
- [ ] `click en "Consultar" muestra la vista de reservas con botón "Volver al menú"`
- [ ] `click en "Gestionar reservas" muestra el listado con botón "Volver al menú"`
- [ ] `click en "Volver al menú" desde Consultar/Gestionar regresa al menú principal`
- [ ] `click en "Administrador" sin sesión muestra el login, con "Volver al menú" y SIN botón
      "Cerrar sesión"`
- [ ] `tras un login exitoso, se muestra el panel admin con "Cerrar sesión" y "Volver al menú"
      visibles simultáneamente` (AC-06)
- [ ] `click en "Cerrar sesión" limpia la sesión y vuelve a mostrar el login (permanece en la
      rama Administrador, NO salta al menú)`
- [ ] `click en "Volver al menú" con sesión activa limpia la sesión Y muestra el menú principal`
      (decisión de PLAN documentada arriba)
- [ ] `un 401 de la API limpia la sesión automáticamente sin romper la navegación` (no-regresión
      del comportamiento ya existente vía `setUnauthorizedHandler`)

Los mocks de `ReservasPublicPage`/`ReservasListado`/`VehiculosAdminPage`/`LoginAdmin` en este
archivo son `vi.mock(...)` con un marcador simple (ej. `data-testid`), para mantener
`App.test.jsx` aislado de la lógica interna de esos 4 componentes (ya cubierta por sus propios
tests).

**Completion criterion**

Los 9 tests pasan. Ningún test existente de `ReservasPublicPage.test.jsx`,
`ReservasListado.test.jsx`, `VehiculosAdminPage.test.jsx` o `LoginAdmin.test.jsx` se modifica ni
se rompe (renderizan standalone, confirmado por `daw-impact-scanner` en PLAN).

## Final verification

- Suite completa (backend + frontend) en verde, incluyendo los 15 tests nuevos de este ticket
  (2 + 4 + 9).
- Las 4 pantallas (menú + 3 ramas) comparten la misma paleta de colores y tipografía.
- Ningún archivo de los 4 componentes reutilizados (`ReservasPublicPage.jsx`,
  `ReservasListado.jsx`, `VehiculosAdminPage.jsx`, `LoginAdmin.jsx`) aparece en el diff de este
  ticket.
- `npm run build` compila sin errores.
- **AC-07 es en parte una verificación visual manual** (no hay tooling de snapshot/regresión
  visual instalado en el proyecto — mismo tipo de limitación ya aceptada como WARN en
  FEAT-001c/d/e para coverage de frontend): se verifica en VERIFY levantando la app vía `/run` y
  confirmando visualmente que las 4 pantallas comparten paleta e íconos, no solo por inspección de
  código.
