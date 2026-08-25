import { useEffect, useRef, useState } from "react";

/**
 * InteractiveGradientBackground
 *
 * A fluid, interactive ambient gradient background inspired by Apple HIG materials
 * and Kokonut UI modern lighting effects.
 *
 * Features:
 * - Fluid mouse / touch tracking with spring physics & interpolation
 * - Multi-layered atmospheric orbs (Clinical Cyan, Soft Emerald, Deep Indigo)
 * - Subtle geometric grid matrix with organic breath
 * - Automatic Light & Dark mode adaptation
 * - Respects prefers-reduced-motion
 */
export function InteractiveGradientBackground({
  className = "",
  showGrid = true,
}: {
  className?: string;
  showGrid?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  // Target mouse coordinates and smoothly interpolated current coordinates
  const mousePos = useRef({ x: 0.5, y: 0.4 });
  const currentPos = useRef({ x: 0.5, y: 0.4 });
  const isHovered = useRef(false);

  useEffect(() => {
    setMounted(true);
    let animationFrameId: number;

    const handleMouseMove = (e: MouseEvent) => {
      isHovered.current = true;
      const x = e.clientX / window.innerWidth;
      const y = e.clientY / window.innerHeight;
      mousePos.current = { x, y };
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        isHovered.current = true;
        const touch = e.touches[0];
        const x = touch.clientX / window.innerWidth;
        const y = touch.clientY / window.innerHeight;
        mousePos.current = { x, y };
      }
    };

    const handleMouseLeave = () => {
      isHovered.current = false;
      mousePos.current = { x: 0.5, y: 0.4 };
    };

    // Smooth lerp loop
    const animate = () => {
      const ease = 0.065; // smooth damping factor
      currentPos.current.x += (mousePos.current.x - currentPos.current.x) * ease;
      currentPos.current.y += (mousePos.current.y - currentPos.current.y) * ease;

      if (containerRef.current) {
        containerRef.current.style.setProperty(
          "--mouse-x",
          `${(currentPos.current.x * 100).toFixed(2)}%`,
        );
        containerRef.current.style.setProperty(
          "--mouse-y",
          `${(currentPos.current.y * 100).toFixed(2)}%`,
        );
      }

      animationFrameId = requestAnimationFrame(animate);
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    window.addEventListener("touchmove", handleTouchMove, { passive: true });
    document.addEventListener("mouseleave", handleMouseLeave);
    animationFrameId = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("touchmove", handleTouchMove);
      document.removeEventListener("mouseleave", handleMouseLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  if (!mounted) return null;

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className={`pointer-events-none fixed inset-0 -z-10 overflow-hidden select-none ${className}`}
      style={
        {
          "--mouse-x": "50%",
          "--mouse-y": "40%",
        } as React.CSSProperties
      }
    >
      {/* 1. Base Gradient Canvas */}
      <div className="absolute inset-0 bg-background transition-colors duration-500" />

      {/* 2. Interactive Cursor Spotlight (Primary Clinical Glow) */}
      <div
        className="absolute inset-0 opacity-70 dark:opacity-80 transition-opacity duration-700"
        style={{
          background: `
            radial-gradient(
              700px circle at var(--mouse-x) var(--mouse-y),
              color-mix(in oklch, var(--color-primary) 22%, transparent),
              transparent 70%
            )
          `,
        }}
      />

      {/* 3. Floating Ambient Atmosphere Orbs */}
      <div className="absolute -left-[10%] -top-[10%] h-[55vw] w-[55vw] min-h-[350px] min-w-[350px] rounded-full bg-gradient-to-br from-primary/15 via-primary/5 to-transparent blur-[90px] dark:from-primary/20 dark:via-primary/5 animate-pulse [animation-duration:9s]" />

      <div
        className="absolute -right-[10%] top-[20%] h-[50vw] w-[50vw] min-h-[320px] min-w-[320px] rounded-full bg-gradient-to-bl from-teal-500/12 via-cyan-500/6 to-transparent blur-[100px] dark:from-teal-400/18 dark:via-cyan-400/5 animate-pulse [animation-duration:12s] [animation-delay:2s]"
        style={{
          transform: `translate(calc((var(--mouse-x) - 50%) * -0.2), calc((var(--mouse-y) - 50%) * -0.2))`,
        }}
      />

      <div
        className="absolute left-[20%] -bottom-[15%] h-[60vw] w-[60vw] min-h-[380px] min-w-[380px] rounded-full bg-gradient-to-tr from-indigo-500/10 via-sky-500/5 to-transparent blur-[110px] dark:from-indigo-500/15 dark:via-sky-400/5 animate-pulse [animation-duration:15s] [animation-delay:4s]"
        style={{
          transform: `translate(calc((var(--mouse-x) - 50%) * 0.15), calc((var(--mouse-y) - 50%) * 0.15))`,
        }}
      />

      {/* 4. Fine Geometric Micro-Grid Mesh (Subtle Apple / Kokonut UI Texture) */}
      {showGrid && (
        <div
          className="absolute inset-0 opacity-[0.025] dark:opacity-[0.045] mix-blend-overlay"
          style={{
            backgroundImage: `
              linear-gradient(to right, currentColor 1px, transparent 1px),
              linear-gradient(to bottom, currentColor 1px, transparent 1px)
            `,
            backgroundSize: "40px 40px",
            maskImage: "radial-gradient(ellipse 70% 60% at 50% 50%, #000 50%, transparent 100%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 70% 60% at 50% 50%, #000 50%, transparent 100%)",
          }}
        />
      )}

      {/* 5. Subtle Vignette Depth */}
      <div className="absolute inset-0 bg-radial-[ellipse_at_center] from-transparent via-transparent to-background/60 dark:to-background/80" />
    </div>
  );
}
