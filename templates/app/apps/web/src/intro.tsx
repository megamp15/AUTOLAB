// The opening screen, before sign-in: a heads-up-display frame around the app's centrepiece,
// one button to come in, and a status line. Coming in plays the centrepiece's exit, then
// hands over to whatever is next. This file is the same in every app; the centrepiece
// (centrepiece.tsx) is the part each app draws for itself.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useDecoded } from "./theme.js";

const LEAVE_MS = 650;

export function Intro({ children, action, ready, leaving: leavingText, onEnter }: { children: ReactNode; /** On the button. */ action: string; /** The status line while waiting, and once the button is pressed. */ ready: string; leaving: string; onEnter: () => void }) {
  const [leaving, setLeaving] = useState(false);
  const status = useDecoded(leaving ? leavingText : ready, true, leaving ? 0 : 500);
  const enter = () => {
    if (leaving) return;
    setLeaving(true);
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    setTimeout(onEnter, still ? 0 : LEAVE_MS);
  };
  // The centrepiece leans toward the pointer, as if it were tracking where you look: the
  // pointer's place is kept in --mx and --my (-1 to 1 from the middle), eased toward each frame.
  const frame = useRef<HTMLElement>(null);
  useEffect(() => {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const want = { x: 0, y: 0 };
    const at = { x: 0, y: 0 };
    const moved = (event: PointerEvent) => {
      want.x = (event.clientX / innerWidth) * 2 - 1;
      want.y = (event.clientY / innerHeight) * 2 - 1;
    };
    let id = requestAnimationFrame(function step() {
      at.x += (want.x - at.x) * 0.08;
      at.y += (want.y - at.y) * 0.08;
      frame.current?.style.setProperty("--mx", at.x.toFixed(4));
      frame.current?.style.setProperty("--my", at.y.toFixed(4));
      id = requestAnimationFrame(step);
    });
    addEventListener("pointermove", moved);
    return () => {
      cancelAnimationFrame(id);
      removeEventListener("pointermove", moved);
    };
  }, []);
  useEffect(() => {
    const key = (event: KeyboardEvent) => event.key === "Enter" && enter();
    addEventListener("keydown", key);
    return () => removeEventListener("keydown", key);
  });
  return (
    <main ref={frame} className="intro fixed inset-0 grid place-items-center overflow-hidden" data-leaving={leaving || undefined}>
      {["top-4 left-4 border-t border-l", "top-4 right-4 border-t border-r", "bottom-4 left-4 border-b border-l", "right-4 bottom-4 border-r border-b"].map((corner) => (
        <i key={corner} className={`intro-fade absolute size-5 border-primary/60 ${corner}`} />
      ))}
      <div className="grid justify-items-center gap-10">
        <div className="intro-track">{children}</div>
        <Button type="button" variant="outline" size="lg" className="intro-fade px-8 tracking-[0.3em]" onClick={enter} autoFocus>{action}</Button>
      </div>
      <p className="mono-caps intro-fade absolute bottom-5 left-10 text-[0.65rem] text-muted-foreground" aria-hidden="true">
        &gt; {status}<span className="intro-cursor ml-1 inline-block h-[1em] w-[0.55em] translate-y-[0.15em] bg-primary" />
      </p>
    </main>
  );
}
