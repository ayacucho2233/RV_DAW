import { IconAuto, IconClipboard, IconLock } from "../../components/icons";

const OPCIONES = [
  { rama: "consultar", label: "Consultar", Icono: IconAuto },
  { rama: "gestionar", label: "Gestionar reservas", Icono: IconClipboard },
  { rama: "admin", label: "Administrador", Icono: IconLock },
];

export default function MenuPrincipal({ onSelect }) {
  return (
    <div className="menu-shell">
      <h1>Pool de vehículos corporativos</h1>
      <div className="menu-grid">
        {OPCIONES.map((opcion) => (
          <button
            key={opcion.rama}
            type="button"
            className="menu-card"
            onClick={() => onSelect(opcion.rama)}
          >
            <opcion.Icono aria-hidden="true" />
            {opcion.label}
          </button>
        ))}
      </div>
    </div>
  );
}
