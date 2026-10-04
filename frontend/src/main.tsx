import { createRoot } from "react-dom/client"; import "leaflet/dist/leaflet.css"; import "./style.css"; import App from "./App";
import TempleBarDemo from "./TempleBarDemo";
createRoot(document.getElementById("root")!).render(window.location.pathname === "/demo/temple-bar" ? <TempleBarDemo /> : <App />);
