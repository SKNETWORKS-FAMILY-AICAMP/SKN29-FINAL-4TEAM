import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./app/App";
import "./common/styles/pearl-workspace-v2.css";
import "./common/styles/water-blue-tone.css";
import "./pages/consultant/ConsultantDashboardRefresh.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("root 요소를 찾을 수 없습니다.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
