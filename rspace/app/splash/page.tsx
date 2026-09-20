"use client";

import { useState } from "react";

export default function Home() {
  const [register, setRegister] = useState<boolean>(false);

  return (
    <main
      className="relative block min-h-screen bg-[var(--sky)] sm:grid sm:grid-cols-[1.08fr_.92fr] sm:overflow-hidden"
    >
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
        className="relative z-10 grid min-h-[50vh] place-items-center px-8 py-16 sm:min-h-screen sm:p-[clamp(2rem,7vw,7rem)]"
        aria-labelledby="rspace-heading"
      >
        <div className="flex w-full max-w-[39rem] flex-col gap-8 sm:pb-8">
          <h1
            id="rspace-heading"
            className="mb-2 text-[clamp(4.8rem,11vw,9rem)] font-bold leading-[.9] text-[var(--ink)]"
          >
            <span className="text-(--periwinkle) brightness-50">R</span>
            Space
          </h1>
          <p className="max-w-[22rem] text-[clamp(1.55rem,2.6vw,2.25rem)] font-bold leading-[1.15] text-[var(--ink)]">
            Connect with others easily.
          </p>
        </div>
      </section>

      <section
        className="relative z-10 grid min-h-[50vh] place-items-center px-8 py-16 sm:min-h-screen sm:p-[clamp(2rem,7vw,7rem)]"
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
              className="rounded-2xl mt-1 min-h-14 cursor-pointer border-[3px] border-[var(--ink)] bg-[var(--lemon)] px-4 py-3 font-bold text-[var(--ink)] transition-[transform,filter] duration-150 active:translate-y-0 focus-visible:outline-4 focus-visible:outline-offset-3 focus-visible:outline-[var(--lemon)]"
              type="submit"
            >
              {!register ? "Log in" : "Register"}
            </button>
            <button
              className="rounded-2xl min-h-14 cursor-pointer border-[3px] border-[var(--ink)] bg-(--lemon) saturate-25 px-4 py-3 font-bold text-[var(--ink)] transition-[transform,filter] duration-150 active:translate-y-0 focus-visible:outline-4 focus-visible:outline-offset-3 focus-visible:outline-[var(--lemon)]"
              type="button"
              onClick={() => setRegister(!register)}
            >
              {!register ? "I don't have an account" : "I already have an account"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
