import type { Metadata } from "next";
import "./globals.css";
import { FontProvider } from "./context/FontContext";
import BackgroundSquares from "./components/BackgroundSquares";

export const metadata: Metadata = {
  title: "RSpace | Connect with others easily",
  description: "A friendly social space for older adults.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-full flex flex-col">
        <BackgroundSquares />
        <FontProvider>{children}</FontProvider>
      </body>
    </html>
  );
}
