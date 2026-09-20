import SiteHeader from "@/app/components/SiteHeader";

export default function Home() {
  return (
    <main className="flex flex-col gap-8 min-h-screen bg-[var(--sky)]">
      <SiteHeader />
      <main className="flex flex-col w-full max-w-[67vw] mx-auto">
        <section className="flex flex-col gap-4">
          <h1 className="text-7xl font-bold mb-4">Home</h1>
          <p>
            (relevant stats or data here)
          </p>
        </section>
      </main>
    </main>
  );
}
