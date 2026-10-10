import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./app/App";
import "leaflet/dist/leaflet.css";
import "./styles/app.css";
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
