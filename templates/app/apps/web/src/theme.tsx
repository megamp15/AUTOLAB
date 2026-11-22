import { useEffect, useState, type ReactNode } from "react";
import { AnimatedThemeToggler } from "@/components/ui/animated-theme-toggler";

const KEY = "__app__-theme";

/**
 * Switches between dark and light, the new one spreading out from the button, and remembers
 * the choice in this browser. Until one is made, the device decides (index.html).
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));
  const keep = (next: "light" | "dark") => {
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", next === "dark" ? "#09090b" : "#f3f3ef");
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // Private windows may refuse storage; the choice then lasts for this visit.
    }
    setTheme(next);
  };
  return <AnimatedThemeToggler theme={theme} onThemeChange={keep} duration={500} aria-label={theme === "dark" ? "Switch to light" : "Switch to dark"} className={ICON_BUTTON} />;
}

/** A quiet square button holding one icon. */
export const ICON_BUTTON = "grid size-8 cursor-pointer place-items-center rounded-md text-muted-foreground transition-colors hover:text-primary focus-visible:outline-2 [&_svg]:size-4";

const GLYPHS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789/<>_#";

/** Text that resolves out of noise, left to right, after `delay` ms. With "reduce motion" on it is simply shown. */
export function useDecoded(text: string, run: boolean, delay: number): string {
  const [shown, setShown] = useState(run ? "" : text);
  useEffect(() => {
    if (!run || matchMedia("(prefers-reduced-motion: reduce)").matches) return setShown(text);
    const started = performance.now() + delay;
    let frame = requestAnimationFrame(function step(now) {
      const settled = Math.floor((now - started) / 70);
      if (settled >= text.length) return setShown(text);
      setShown(now < started ? "" : text.slice(0, Math.max(0, settled)) + Array.from({ length: text.length - Math.max(0, settled) }, () => GLYPHS[Math.floor(Math.random() * GLYPHS.length)]).join(""));
      frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [text, run, delay]);
  return shown;
}

const NAME = "__App__";
/** From this letter on, the name is in the neon colour. `NAME.length` for none. */
const ACCENT_FROM = NAME.length;

/** The app's name in mono capitals, ending on a neon cursor. With `decode` it resolves out of noise. */
export function Wordmark({ className = "", decode = false }: { className?: string; decode?: boolean }) {
  const shown = useDecoded(NAME, decode, 760);
  return (
    <span className={`inline-block min-h-[1lh] font-mono font-bold tracking-[0.18em] uppercase ${className}`} aria-label={NAME}>
      <span aria-hidden="true">{shown.slice(0, ACCENT_FROM)}<span className="text-primary">{shown.slice(ACCENT_FROM)}_</span></span>
    </span>
  );
}

/** A panel that switches on like a heads-up display (see `.boot` in tailwind.css). */
export const Boot = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`boot ${className}`}>
    <i className="boot-line" />
    <i className="boot-line" />
    {children}
  </div>
);
