import { useEffect, useRef, useState } from "react";

const DURATION = 600;
const ease = (t: number) => 1 - (1 - t) ** 3;

/**
 * A number that runs up to its value when it appears, and to its new value when it changes,
 * in the format it is shown in. With "reduce motion" on, it is simply shown.
 */
export function Ticker({ value, format = (shown) => String(Math.round(shown)) }: { value: number; format?: (value: number) => string }) {
  const [shown, setShown] = useState(0);
  // Where the number on screen is right now: a run always starts from there, so one that is
  // cut short (the value changing again, or React running the effect twice) carries on.
  const at = useRef(0);
  useEffect(() => {
    const show = (next: number) => {
      at.current = next;
      setShown(next);
    };
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return show(value);
    const from = at.current;
    const started = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      const t = Math.min(1, (now - started) / DURATION);
      show(from + (value - from) * ease(t));
      if (t < 1) frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <span className="digits">{format(shown)}</span>;
}
