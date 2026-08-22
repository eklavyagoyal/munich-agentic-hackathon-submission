import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, Route, Routes } from "react-router-dom";
import App from "./App";
import Overview from "./pages/Overview";
import Games from "./pages/Games";
import GameDetail from "./pages/GameDetail";
import Items from "./pages/Items";
import Teams from "./pages/Teams";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HashRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Overview />} />
          <Route path="games" element={<Games />} />
          <Route path="games/:id" element={<GameDetail />} />
          <Route path="items" element={<Items />} />
          <Route path="teams" element={<Teams />} />
        </Route>
      </Routes>
    </HashRouter>
  </React.StrictMode>
);
