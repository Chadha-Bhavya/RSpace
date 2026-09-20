"use client";

import { useEffect, useState } from "react";

interface Square {
  id: number;
  x: number;
  y: number;
  size: number;
  rotation: number;
  scale: number;
  hueRotate: number;
  animationClass: string;
}

export default function BackgroundSquares() {
  const [squares, setSquares] = useState<Square[]>([]);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
    const generatedSquares: Square[] = [];
    const numSquares = 15;

    // All 60 animation class names written out literally
    const animationClasses = [
      'animate-square-pulse-delay-0s',
      'animate-square-pulse-delay-1s',
      'animate-square-pulse-delay-2s',
      'animate-square-pulse-delay-3s',
      'animate-square-pulse-delay-4s',
      'animate-square-pulse-delay-5s',
      'animate-square-pulse-delay-6s',
      'animate-square-pulse-delay-7s',
      'animate-square-pulse-delay-8s',
      'animate-square-pulse-delay-9s',
      'animate-square-pulse-delay-10s',
      'animate-square-pulse-delay-11s',
      'animate-square-pulse-delay-12s',
      'animate-square-pulse-delay-13s',
      'animate-square-pulse-delay-14s',
      'animate-square-pulse-delay-15s',
      'animate-square-pulse-delay-16s',
      'animate-square-pulse-delay-17s',
      'animate-square-pulse-delay-18s',
      'animate-square-pulse-delay-19s',
      'animate-square-pulse-delay-20s',
      'animate-square-pulse-delay-21s',
      'animate-square-pulse-delay-22s',
      'animate-square-pulse-delay-23s',
      'animate-square-pulse-delay-24s',
      'animate-square-pulse-delay-25s',
      'animate-square-pulse-delay-26s',
      'animate-square-pulse-delay-27s',
      'animate-square-pulse-delay-28s',
      'animate-square-pulse-delay-29s',
      'animate-square-pulse-delay-30s',
      'animate-square-pulse-delay-31s',
      'animate-square-pulse-delay-32s',
      'animate-square-pulse-delay-33s',
      'animate-square-pulse-delay-34s',
      'animate-square-pulse-delay-35s',
      'animate-square-pulse-delay-36s',
      'animate-square-pulse-delay-37s',
      'animate-square-pulse-delay-38s',
      'animate-square-pulse-delay-39s',
      'animate-square-pulse-delay-40s',
      'animate-square-pulse-delay-41s',
      'animate-square-pulse-delay-42s',
      'animate-square-pulse-delay-43s',
      'animate-square-pulse-delay-44s',
      'animate-square-pulse-delay-45s',
      'animate-square-pulse-delay-46s',
      'animate-square-pulse-delay-47s',
      'animate-square-pulse-delay-48s',
      'animate-square-pulse-delay-49s',
      'animate-square-pulse-delay-50s',
      'animate-square-pulse-delay-51s',
      'animate-square-pulse-delay-52s',
      'animate-square-pulse-delay-53s',
      'animate-square-pulse-delay-54s',
      'animate-square-pulse-delay-55s',
      'animate-square-pulse-delay-56s',
      'animate-square-pulse-delay-57s',
      'animate-square-pulse-delay-58s',
      'animate-square-pulse-delay-59s',
    ];

    for (let i = 0; i < numSquares; i++) {
      generatedSquares.push({
        id: i,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: 20,
        rotation: Math.random() * 360,
        scale: Math.random() * 0.5 + 0.8, // 0.8-1.3
        hueRotate: Math.random() * 30 - 15, // -15 to +15 degrees hue rotation
        animationClass: animationClasses[Math.floor(Math.random() * animationClasses.length)],
      });
    }

    setSquares(generatedSquares);
  }, []);

  if (!isMounted) {
    return null;
  }

  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      {squares.map((square) => (
        <div
          key={square.id}
          className={`-z-100 absolute ${square.animationClass}`}
          style={{
            left: `${square.x}%`,
            top: `${square.y}%`,
            width: `${square.size}vw`,
            height: `${square.size}vw`,
            backgroundColor: 'var(--periwinkle)',
            opacity: 0.15,
            filter: `hue-rotate(${square.hueRotate}deg)`,
            '--rotation': `${square.rotation}deg`,
            '--scale': square.scale,
          } as React.CSSProperties}
        />
      ))}
    </div>
  );
}
