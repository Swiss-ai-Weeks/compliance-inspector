import { useEffect, useState } from "react";
import Home from "./Home";
import JobView from "./JobView";

// Hash routing: #/ is home, #/jobs/<id> is one job. No router dependency, and deep links
// survive being served by FastAPI's catch-all.
function useRoute() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const match = hash.match(/^#\/jobs\/([a-f0-9]+)/);
  return match ? { page: "job" as const, id: match[1] } : { page: "home" as const };
}

export function navigate(path: string) {
  window.location.hash = path;
}

export default function App() {
  const route = useRoute();
  return (
    <div className="app">
      <header className="topbar">
        <a href="#/" className="brand">
          <span className="brand-mark" aria-hidden>◉</span>
          Compliance Inspector
        </a>
        <span className="topbar-note">Did the video follow the manual?</span>
      </header>
      <main className="page">
        {route.page === "job" ? <JobView key={route.id} id={route.id} /> : <Home />}
      </main>
    </div>
  );
}
