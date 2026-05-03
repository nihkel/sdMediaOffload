import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Imports from "./pages/Imports";
import ImportDetail from "./pages/ImportDetail";
import Library from "./pages/Library";
import SettingsPage from "./pages/Settings";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/imports", label: "Imports" },
  { to: "/library", label: "Library" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  return (
    <div className="flex min-h-full">
      <aside className="w-56 border-r border-border bg-panel/40 flex flex-col">
        <div className="px-5 py-5 border-b border-border">
          <div className="font-semibold tracking-tight">SD Media Offload</div>
          <div className="text-xs text-muted">v0.1.0</div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((it) => (
            <NavLink
              key={it.to}
              to={it.to}
              end={it.end}
              className={({ isActive }) =>
                `block px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive ? "bg-border text-white" : "text-slate-300 hover:bg-border/40"
                }`
              }
            >
              {it.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/imports" element={<Imports />} />
          <Route path="/imports/:id" element={<ImportDetail />} />
          <Route path="/library" element={<Library />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
