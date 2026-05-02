import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import UploadValidator from "./UploadValidator";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <UploadValidator />
  </StrictMode>
);
