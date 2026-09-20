"use client";

import { useState } from "react";
import { SquigglyBorders } from "@/app/components/SquigglyBorders";

export default function Home() {
  const [register, setRegister] = useState<boolean>(false);

  return (
    <main className="block">
      <SquigglyBorders />
      <div className="relative h-screen overflow-hidden bg-[var(--sky)] sm:grid sm:grid-cols-[1.08fr_.92fr]">
      <svg
        className="pointer-events-none absolute inset-0 z-0 size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          className="hidden fill-[var(--periwinkle)] sm:block"
          d="M54 0 C48 12 61 20 54 33 C48 46 61 54 54 67 C48 80 60 88 54 100 H100 V0 Z"
        />
        <path
          className="fill-[var(--periwinkle)] sm:hidden"
          d="M0 33 C12 29 21 37 34 32 C46 28 55 36 67 32 C79 28 88 36 100 32 V100 H0 Z"
        />
      </svg>
      <svg
        className="animate-wave-breathe-y -translate-y-25 opacity-33 pointer-events-none absolute inset-0 z-0 size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          className="hidden fill-[var(--periwinkle)] sm:block"
          d="M54 0 C48 12 61 20 54 33 C48 46 61 54 54 67 C48 80 60 88 54 100 H100 V0 Z"
        />
        <path
          className="fill-[var(--periwinkle)] sm:hidden"
          d="M0 33 C12 29 21 37 34 32 C46 28 55 36 67 32 C79 28 88 36 100 32 V100 H0 Z"
        />
      </svg>
      <svg
        className="animate-wave-breathe-y-delay5s -translate-y-12.5 opacity-33 pointer-events-none absolute inset-0 z-0 size-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          className="hidden fill-[var(--periwinkle)] sm:block"
          d="M54 0 C48 12 61 20 54 33 C48 46 61 54 54 67 C48 80 60 88 54 100 H100 V0 Z"
        />
        <path
          className="fill-[var(--periwinkle)] sm:hidden"
          d="M0 33 C12 29 21 37 34 32 C46 28 55 36 67 32 C79 28 88 36 100 32 V100 H0 Z"
        />
      </svg>

      <section
        className="relative z-10 grid h-1/2 place-items-center px-8 py-16 sm:h-full sm:p-[clamp(2rem,7vw,7rem)]"
        aria-labelledby="rspace-heading"
      >
        <div className="flex w-full max-w-[39rem] flex-col gap-8 sm:pb-8">
          <h1
            id="rspace-heading"
            className="mb-2 animate-fade-in text-[clamp(4.8rem,11vw,9rem)] font-bold leading-[.9] text-[var(--ink)]"
          >
            <span className="text-(--periwinkle) brightness-50">R</span>
            Space
          </h1>
          <p className="max-w-[22rem] animate-fade-in-delay0.5s text-[clamp(1.55rem,2.6vw,2.25rem)] font-bold leading-[1.15] text-[var(--ink)]">
            Connect with others, care for yourself
          </p>
          <div className="relative -mb-8 self-start size-50"> {/* act as a frame so i can overlap two svgs on top of each other */}
            <img
              src="/stars.svg"
              alt="RSpace logo with stars"
              className="absolute animate-star-pulse z-10 size-50"
            />
            <img
              src="/nostars.svg"
              alt="RSpace logo without stars"
              className="absolute size-50"
            />
          </div>
        </div>
      </section>

      <section
        className="animate-fade-in-delay1s relative z-10 grid h-1/2 place-items-center px-8 py-16 sm:h-full sm:p-[clamp(2rem,7vw,7rem)]"
        aria-labelledby="signin-heading"
      >
        <div className="flex w-full max-w-[27rem] flex-col gap-4 text-[var(--ink)]">
          <h2
            id="signin-heading"
            className="mb-2 text-[clamp(2.3rem,4vw,3.4rem)] font-bold leading-none"
          >
            {!register ? "Sign in" : "Register"}
          </h2>
          <form className="grid gap-2">
            <label
              className="text-[1.1rem] font-bold"
              htmlFor="username"
            >
              Username
            </label>
            <input
              className="mb-3 min-h-14 w-full border-[3px] border-[var(--ink)] bg-white px-4 py-3 text-[var(--ink)] outline-none focus:outline-4 focus:outline-offset-2 focus:outline-[var(--lemon)]"
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              required
            />
            <label
              className="text-[1.1rem] font-bold"
              htmlFor="password"
            >
              Password
            </label>
            <input
              className="mb-3 min-h-14 w-full border-[3px] border-[var(--ink)] bg-white px-4 py-3 text-[var(--ink)] outline-none focus:outline-4 focus:outline-offset-2 focus:outline-[var(--lemon)]"
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
            <button
              className="mt-1 min-h-14 cursor-pointer border-[3px] border-[var(--ink)] bg-[var(--lemon)] px-8 py-3 font-bold text-[var(--ink)] transition-[transform,filter] duration-150 active:translate-y-0 focus-visible:outline-4 focus-visible:outline-offset-3 focus-visible:outline-[var(--lemon)] shadow-md"
              type="submit"
              style={{ clipPath: "url(#squiggly-button)" }}
            >
              {!register ? "Log in" : "Register"}
            </button>
            <button
              className="min-h-14 cursor-pointer border-[3px] border-[var(--ink)] bg-(--lemon) saturate-25 px-8 py-3 font-bold text-[var(--ink)] transition-[transform,filter] duration-150 active:translate-y-0 focus-visible:outline-4 focus-visible:outline-offset-3 focus-visible:outline-[var(--lemon)] shadow-md"
              type="button"
              onClick={() => setRegister(!register)}
              style={{ clipPath: "url(#squiggly-button)" }}
            >
              {!register ? "I don't have an account" : "I already have an account"}
            </button>
          </form>
        </div>
      </section>
      
      <div className="flex flex-row gap-8 pointer-events-none absolute left-0 right-0 bottom-5 z-10 flex items-center justify-center">
        <span className="animate-moving-down text-xl font-extrabold scale-x-150">🡳</span>
        <span className="font-bold tracking-[0.4]">
          Scroll down to find out more about RSpace
        </span>
        <span className="animate-moving-down text-xl font-extrabold scale-x-150">🡳</span>
      </div>

      </div>

      <section
        className="bg-[var(--skywinkle)]"
        aria-label="Additional content"
      >
        <main className="py-[20vh] flex flex-col w-full max-w-[67vw] mx-auto">
          <section className="flex flex-col gap-4">
            <h1 className="animate-fade-in text-7xl font-bold mb-4">What is RSpace?</h1>
            <p className="animate-fade-in-delay0.5s">
              RSpace is a social media/wellness app designed for older audiences.
              Its interface is designed to be accessible and intuitive,
              and its wellness features include
            </p>
            <ul className="animate-fade-in-delay0.5s list-disc pl-6">
              <li>Our comforting AI chatbot, Spi, to advise and comfort users</li>
              <li>A wellness checker that uses its knowledge of the user to suggest nourishing actions.</li>
            </ul>
            <p className="animate-fade-in-delay0.5s">
              Register an account and try RSpace for yourself!
            </p>
          </section>
        </main>
      </section>
    </main>
  );
}
