import { useEffect, useRef } from "react";

type Star = { x: number; y: number; size: number; phase: number; speed: number };
type Flare = { star: Star; born: number };

const FLARE_MS = 3200;
const mix = (colour: string, alpha: number) => `color-mix(in srgb, ${colour} ${Math.round(alpha * 100)}%, transparent)`;

/**
 * The page's backdrop: a sparse field of faint stars, drifting very slowly. Now and then one
 * of them flares in the app's neon colour and throws off a single thin ring.
 * It is drawn behind everything and takes no input. With "reduce motion" on it is a still field.
 */
export function Backdrop() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current!;
    const context = canvas.getContext("2d")!;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let stars: Star[] = [];
    let flares: Flare[] = [];
    let nextFlare = performance.now() + 1500;
    let frame = 0;
    let [width, height] = [0, 0];

    const size = () => {
      const ratio = Math.min(devicePixelRatio || 1, 2);
      [width, height] = [innerWidth, innerHeight];
      canvas.width = width * ratio;
      canvas.height = height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      // One star for about every 9,000 square pixels: sparse on a phone, never crowded on a desk.
      stars = Array.from({ length: Math.round((width * height) / 9000) }, () => ({ x: Math.random() * width, y: Math.random() * height, size: Math.random() < 0.12 ? 1.5 : 0.8, phase: Math.random() * Math.PI * 2, speed: 0.3 + Math.random() * 0.9 }));
      flares = [];
      if (still) draw(0);
    };

    const draw = (now: number) => {
      const style = getComputedStyle(document.documentElement);
      const ink = style.getPropertyValue("--foreground").trim();
      const neon = style.getPropertyValue("--primary").trim();
      // Paper needs darker specks than night does to read at all.
      const strength = document.documentElement.classList.contains("dark") ? 1 : 0.7;
      context.clearRect(0, 0, width, height);
      for (const star of stars) {
        const y = still ? star.y : (star.y + now * 0.0015 * star.speed) % height;
        const twinkle = still ? 0.6 : 0.45 + 0.3 * Math.sin(now * 0.0006 * star.speed + star.phase);
        context.fillStyle = mix(ink, twinkle * 0.85 * strength);
        context.fillRect(star.x, y, star.size, star.size);
      }
      flares = flares.filter((flare) => now - flare.born < FLARE_MS);
      for (const flare of flares) {
        const t = (now - flare.born) / FLARE_MS;
        const { x } = flare.star;
        const y = (flare.star.y + now * 0.0015 * flare.star.speed) % height;
        // The flare: quick up, slow down.
        const glow = t < 0.12 ? t / 0.12 : Math.max(0, 1 - (t - 0.12) / 0.5);
        context.fillStyle = mix(neon, glow * strength);
        context.beginPath();
        context.arc(x, y, 1 + glow * 2.2, 0, Math.PI * 2);
        context.fill();
        // The ring: out to about a seventh of the screen, thinning as it goes.
        context.strokeStyle = mix(neon, (1 - t) ** 2 * 0.55 * strength);
        context.lineWidth = 1;
        context.beginPath();
        context.arc(x, y, 4 + (1 - (1 - t) ** 3) * Math.min(width, height) * 0.14, 0, Math.PI * 2);
        context.stroke();
      }
    };

    const tick = (now: number) => {
      if (now > nextFlare && stars.length) {
        flares.push({ star: stars[Math.floor(Math.random() * stars.length)]!, born: now });
        nextFlare = now + 5000 + Math.random() * 6000;
      }
      draw(now);
      frame = requestAnimationFrame(tick);
    };

    size();
    addEventListener("resize", size);
    // The theme switch changes the colours; a still field is redrawn when it does.
    const themed = new MutationObserver(() => still && draw(0));
    themed.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    if (!still) frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      removeEventListener("resize", size);
      themed.disconnect();
    };
  }, []);
  return <canvas ref={ref} aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 size-full" />;
}
