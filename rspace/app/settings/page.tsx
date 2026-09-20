"use client";

import SiteHeader from "@/app/components/SiteHeader";
import { useFont } from "@/app/context/FontContext";

export default function SettingsPage() {
  const { useOpenDyslexic, toggleFont } = useFont();

  return (
    <main className="flex flex-col gap-8 min-h-screen bg-[var(--sky)]">
      <SiteHeader />
      <main className="flex flex-col w-full max-w-[67vw] mx-auto">
        <section className="flex flex-col gap-12">
          <h1 className="animate-fade-in text-7xl font-bold">Settings</h1>
          <div className="animate-fade-in-delay0.5s bg-white/50 p-6 rounded-lg shadow-md">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold mb-2">Accessibility</h2>
                <p className="text-lg">Use OpenDyslexic font for easier reading</p>
              </div>
              <button
                onClick={toggleFont}
                className={`relative w-16 h-8 rounded-full transition-colors duration-200 ${
                  useOpenDyslexic ? "bg-[var(--periwinkle)]" : "bg-gray-300"
                }`}
                aria-label={useOpenDyslexic ? "Disable OpenDyslexic font" : "Enable OpenDyslexic font"}
              >
                <span
                  className={`absolute top-1 w-6 h-6 bg-white rounded-full shadow-md transition-transform duration-200 ${
                    useOpenDyslexic ? "translate-x-1" : "-translate-x-7"
                  }`}
                />
              </button>
            </div>
          </div>
        </section>
      </main>
    </main>
  );
}
