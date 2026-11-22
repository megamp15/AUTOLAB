// What the opening screen is built around. This one is a placeholder: a ring around a
// point. Replace it with a drawing of this app's own.
//
// Brief for drawing it:
//   - Start from the app's name and what it is for, and find the one image in it (Novaflix,
//     a tracker for what you watch: a nova seen through a visor, a star held in a targeting
//     reticle). Stay in the family: space, signals, instruments, a display being looked through.
//   - Minimal: thin lines and one point of light, nothing filled, nothing photographic.
//   - One <svg>, about 280px, drawn only in `currentColor` and `var(--primary)`, so it
//     works in dark and light.
//   - Slow idle motion, with the `intro-spin`, `intro-spin-back` and `intro-pulse` classes.
//   - Coming in is the moment: the part that flies outward carries `intro-burst`, and
//     everything else carries `intro-fade`.
//   - It leans toward the pointer by itself; what should lean furthest sits in a group
//     marked `intro-track-near`.
//   - Pick the three words on the opening screen to match (main.tsx: `action`, `ready`,
//     `leaving`), and swap the backdrop (backdrop.tsx) if stars do not suit the app.

export function Centrepiece() {
  return (
    <svg viewBox="-100 -100 200 200" className="size-[min(70vw,280px)] overflow-visible text-foreground" fill="none" aria-hidden="true">
      <circle className="intro-fade intro-spin" r="92" stroke="currentColor" strokeOpacity="0.22" strokeWidth="0.6" strokeDasharray="1.5 7" />
      <circle className="intro-burst" r="34" stroke="var(--primary)" strokeWidth="0.9" style={{ filter: "drop-shadow(0 0 4px var(--glow))" }} />
      <g className="intro-track-near">
        <circle className="intro-pulse" r="2.4" fill="var(--primary)" style={{ filter: "drop-shadow(0 0 5px var(--primary))" }} />
      </g>
    </svg>
  );
}
