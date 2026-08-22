import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";

export default function App() {
  const [clock, setClock] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <>
      <nav className="nav">
        <span className="brand">OASIS · C2F v2</span>
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>Overview</NavLink>
        <NavLink to="/games" className={({ isActive }) => (isActive ? "active" : "")}>Games</NavLink>
        <NavLink to="/items" className={({ isActive }) => (isActive ? "active" : "")}>Items</NavLink>
        <NavLink to="/teams" className={({ isActive }) => (isActive ? "active" : "")}>Teams</NavLink>
        <span className="spacer" />
        <span className="clock">
          {clock.toLocaleTimeString("de-DE")} · UTC {clock.toISOString().slice(11, 19)}
        </span>
      </nav>
      <div className="page">
        <Outlet />
      </div>
    </>
  );
}
