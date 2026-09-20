"use client"

import SiteHeader from "@/app/components/SiteHeader";
import { SquigglyBorders } from "@/app/components/SquigglyBorders";
import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-col min-h-screen bg-[var(--sky)]">
      <SquigglyBorders />
      <SiteHeader />
      <main className="flex flex-col my-8 w-full max-w-[67vw] mx-auto">
        <section className="flex flex-col gap-8">
          <div className="flex flex-row gap-4 items-center">
            <h1 className="animate-fade-in text-7xl font-bold">Welcome back!</h1>
            <img
              src="/happyface.svg"
              alt="Happy face"
              className="animate-fade-in-delay0.5s size-20"
            />
          </div>

          <div className="animate-fade-in-delay0.5s flex flex-row gap-6 w-full">
            <div 
              className="flex-1 bg-[var(--periwinkle)] px-8 py-6 shadow-lg"
              style={{ clipPath: "url(#squiggly-container)" }}
            >
              <h2 className="text-3xl font-bold mb-4">Your Wellness Score</h2>
              <div className="text-6xl font-bold text-[var(--ink)]">7.2</div>
              <p className="text-lg text-[var(--ink)]/80 mt-2">Out of 10</p>
              <Link href="/wellness-check">
                <button 
                  className="mt-4 px-6 py-3 bg-white font-bold text-[var(--ink)] shadow-md"
                  style={{ clipPath: "url(#squiggly-button)" }}
                >
                  View Details
                </button>
              </Link>
            </div>

            <div 
              className="flex-1 bg-[var(--periwinkle-2)] px-8 py-6 shadow-lg"
              style={{ clipPath: "url(#squiggly-container)" }}
            >
              <h2 className="text-3xl font-bold mb-4">Unread Messages</h2>
              <div className="text-6xl font-bold text-[var(--ink)]">3</div>
              <p className="text-lg text-[var(--ink)]/80 mt-2">From friends</p>
              <Link href="/talk-with-others">
                <button 
                  className="mt-4 px-6 py-3 bg-white font-bold text-[var(--ink)] shadow-md"
                  style={{ clipPath: "url(#squiggly-button)" }}
                >
                  Check Messages
                </button>
              </Link>
            </div>

            <div 
              className="flex-1 bg-[var(--periwinkle-3)] px-8 py-6 shadow-lg"
              style={{ clipPath: "url(#squiggly-container)" }}
            >
              <h2 className="text-3xl font-bold mb-4">Spi Conversations</h2>
              <div className="text-6xl font-bold text-[var(--ink)]">5</div>
              <p className="text-lg text-[var(--ink)]/80 mt-2">Active chats</p>
              <Link href="/talk-to-spi">
                <button 
                  className="mt-4 px-6 py-3 bg-white font-bold text-[var(--ink)] shadow-md"
                  style={{ clipPath: "url(#squiggly-button)" }}
                >
                  Talk to Spi
                </button>
              </Link>
            </div>
          </div>

          <div className="animate-fade-in-delay1s flex flex-col gap-4">
            <h2 className="text-4xl font-bold">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-6 place-items-center">
              <Link href="/talk-to-spi">
                <div 
                  className="bg-gray-200 px-8 py-6 shadow-md hover:bg-gray-300 transition-colors cursor-pointer"
                  style={{ clipPath: "url(#squiggly-card)" }}
                >
                  <div className="flex items-center gap-4">
                    <img
                      src="/mic.svg"
                      alt="Microphone icon"
                      className="size-16"
                    />
                    <div>
                      <h3 className="text-2xl font-bold">Start a conversation with Spi</h3>
                      <p className="text-black/60">Get advice and comfort from your AI assistant</p>
                    </div>
                  </div>
                </div>
              </Link>

              <Link href="/talk-with-others">
                <div 
                  className="bg-gray-200 px-8 py-6 shadow-md hover:bg-gray-300 transition-colors cursor-pointer"
                  style={{ clipPath: "url(#squiggly-card)" }}
                >
                  <div className="flex items-center gap-4">
                    <img
                      src="/speechbubble.svg"
                      alt="Speech bubble icon"
                      className="size-16"
                    />
                    <div>
                      <h3 className="text-2xl font-bold">Connect with friends</h3>
                      <p className="text-black/60">Message your friends and find new connections</p>
                    </div>
                  </div>
                </div>
              </Link>

              <Link href="/wellness-check">
                <div 
                  className="bg-gray-200 px-8 py-6 shadow-md hover:bg-gray-300 transition-colors cursor-pointer"
                  style={{ clipPath: "url(#squiggly-card)" }}
                >
                  <div className="flex items-center gap-4">
                    <img
                      src="/happyface.svg"
                      alt="Happy face icon"
                      className="size-16"
                    />
                    <div>
                      <h3 className="text-2xl font-bold">Check your wellness</h3>
                      <p className="text-black/60">View your mood, stress levels, and social score</p>
                    </div>
                  </div>
                </div>
              </Link>

              <Link href="/settings">
                <div 
                  className="bg-gray-200 px-8 py-6 shadow-md hover:bg-gray-300 transition-colors cursor-pointer"
                  style={{ clipPath: "url(#squiggly-card)" }}
                >
                  <div className="flex items-center gap-4">
                    <div className="size-16 rounded-full bg-[var(--lemon)] flex items-center justify-center">
                      <span className="text-3xl">⚙</span>
                    </div>
                    <div>
                      <h3 className="text-2xl font-bold">Adjust your settings</h3>
                      <p className="text-black/60">Customize your RSpace experience</p>
                    </div>
                  </div>
                </div>
              </Link>
            </div>
          </div>
        </section>
      </main>
    </main>
  );
}
