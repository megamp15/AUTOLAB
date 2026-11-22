// What a wait looks like. This one is a placeholder: a point inside a turning arc. Replace
// it with one that goes with this app's centrepiece (Novaflix: its nova, small, the star
// throwing off ring after ring inside a turning reticle).
//
// The contract: one <svg> sized by the caller (`size-*`), drawn only in `currentColor` and
// `var(--primary)`, looping calmly on the `intro-spin-fast`, `intro-pulse` and `loader-ping`
// classes, and readable at 20px as well as 48px.
import { useEffect, useState } from "react";

export function Loader({ className = "size-5", label = "Loading" }: { className?: string; label?: string }) {
  return (
    <svg viewBox="-20 -20 40 40" className={`inline-block overflow-visible text-muted-foreground ${className}`} fill="none" role="status" aria-label={label}>
      <circle className="intro-spin-fast" r="17" stroke="var(--primary)" strokeWidth="1" strokeDasharray="26 80.8" strokeLinecap="round" />
      <circle className="intro-pulse" r="2.2" fill="var(--primary)" />
    </svg>
  );
}

/** Fills the space it is given with the loader, but only once the wait has lasted long enough to notice. */
export function Waiting({ className = "min-h-[40svh]" }: { className?: string }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 300);
    return () => clearTimeout(timer);
  }, []);
  return <div className={`grid place-items-center ${className}`}>{slow ? <Loader className="size-12" /> : null}</div>;
}
