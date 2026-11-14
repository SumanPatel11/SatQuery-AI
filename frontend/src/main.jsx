import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import AppProvider from "./context/AppContext";
import SessionProvider from "./context/SessionContext";

import "./styles/globals.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <SessionProvider>
      <AppProvider>
        <App />
      </AppProvider>
    </SessionProvider>
  </StrictMode>
);