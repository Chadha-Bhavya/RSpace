import SiteHeader from "@/app/components/SiteHeader";

export default function Home() {
  return (
    <main className="flex flex-col min-h-screen bg-[var(--sky)]">
      <SiteHeader />
      <section className="justify-self-center flex flex-col max-w-[75vw] bg-white h-100">
        {/* center this.... */}
      </section>
    </main>
  );
}
