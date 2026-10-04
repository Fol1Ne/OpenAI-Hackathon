import { createRoot } from "react-dom/client"; import "leaflet/dist/leaflet.css"; import "./style.css"; import App from "./App";
import CameraDemo, { CAMERA_DEMOS } from "./CameraDemo";
const camera = CAMERA_DEMOS.find(item => window.location.pathname === `/demo/${item.slug}`);
createRoot(document.getElementById("root")!).render(camera ? <CameraDemo key={camera.id} camera={camera} /> : <App />);
