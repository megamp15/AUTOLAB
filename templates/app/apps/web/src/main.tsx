import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import "./tailwind.css";

// The starter screen: it proves the web build reaches the server and the server its database.
function App() {
  const [status, setStatus] = useState("checking");
  useEffect(() => {
    fetch("/api/status").then((response) => response.json()).then((body: { database?: string }) => setStatus(body.database ?? "unknown"), () => setStatus("unreachable"));
  }, []);
  return (
    <main className="grid min-h-svh place-items-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader><CardTitle className="text-xl text-primary">__App__</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">Database: {status}</CardContent>
      </Card>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
