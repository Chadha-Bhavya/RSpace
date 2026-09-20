"use client"

import SiteHeader from "@/app/components/SiteHeader";
import { SquigglyBorders } from "@/app/components/SquigglyBorders";

export default function WellnessCheckPage() {
  return (
    <main className="flex flex-col min-h-screen bg-[var(--sky)]">
      <SquigglyBorders />
      <SiteHeader />
      <main className="flex flex-col my-8 w-full max-w-[67vw] mx-auto">
        <section className="flex flex-col gap-12">
          <h1 className="animate-fade-in text-6xl font-bold">Wellness Check</h1>
          <div className="animate-fade-in-delay0.5s flex flex-row gap-16 w-full rounded-2xl">
            <div className="relative">
              <img
                src="/scribble-rotated-1.svg"
                alt="Decorative scribble"
                className="absolute -top-8 -left-12 size-36 opacity-60 pointer-events-none"
              />
              <img
                src="/scribble-rotated-2.svg"
                alt="Decorative scribble"
                className="absolute top-24 -right-8 size-48 opacity-60 pointer-events-none"
              />
              <button 
                className="relative z-10 flex flex-col self-center items-center gap-4 bg-[var(--periwinkle)] px-12 py-8 hover:bg-[var(--periwinkle)]/80 transition-colors shadow-md"
                style={{ clipPath: "url(#squiggly-button)" }}
              >
                <img
                  src="/mic.svg"
                  alt="Microphone icon"
                  className="size-24"
                />
                <span className="text-3xl font-bold text-[var(--ink)]">Talk to Spi</span>
              </button>
              <img
                src="/happyface.svg"
                alt="Happy face"
                className="-rotate-15 absolute bottom-16 -right-8 -translate-x-1/2 size-30 opacity-70 pointer-events-none"
              />
            </div>
            <div 
              className="flex flex-7 flex-col bg-gray-200 px-12 py-8 shadow-lg"
              style={{ clipPath: "url(#squiggly-container)" }}
            >
              <h2 className="text-4xl font-bold mb-6">Brain Health & Mood Metrics</h2>
              <div className="grid grid-cols-2 gap-6">
                <div 
                  className="bg-white px-10 py-6 shadow-md"
                  style={{ clipPath: "url(#squiggly-card)" }}
                >
                  <h3 className="text-xl font-bold mb-3">Social Score</h3>
                  <div className="text-5xl font-bold text-green-600">8.5</div>
                  <p className="text-sm text-black/50 mt-2">Out of 10</p>
                </div>
                <div 
                  className="bg-white px-10 py-6 shadow-md"
                  style={{ clipPath: "url(#squiggly-card)" }}
                >
                  <h3 className="text-xl font-bold mb-3">Mood Score</h3>
                  <div className="text-5xl font-bold text-yellow-500">6.8</div>
                  <p className="text-sm text-black/50 mt-2">Out of 10</p>
                </div>
                <div 
                  className="bg-white px-10 py-6 shadow-md"
                  style={{ clipPath: "url(#squiggly-card)" }}
                >
                  <h3 className="text-xl font-bold mb-3">Stress Level</h3>
                  <div className="text-5xl font-bold text-green-600">Low</div>
                  <p className="text-sm text-black/50 mt-2">Based on recent conversations</p>
                </div>
                <div 
                  className="bg-white px-10 py-6 shadow-md"
                  style={{ clipPath: "url(#squiggly-card)" }}
                >
                  <h3 className="text-xl font-bold mb-3">Overall</h3>
                  <div className="text-5xl font-bold text-yellow-500">7.2</div>
                  <p className="text-sm text-black/50 mt-2">Combined wellness score</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </main>
  );
}
