import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

// The starter screen: it proves the web build reaches the server and the server its database.
function App() {
  const [status, setStatus] = useState("checking");
  useEffect(() => {
    fetch("/api/status").then((response) => response.json()).then((body: { database?: string }) => setStatus(body.database ?? "unknown"), () => setStatus("unreachable"));
  }, []);
  return <main><h1>__App__</h1><p>Database: {status}</p></main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
