"use client";

import { createContext, useContext, useEffect, useState } from "react";

interface FontContextType {
  useOpenDyslexic: boolean;
  toggleFont: () => void;
}

const FontContext = createContext<FontContextType | undefined>(undefined);

export function FontProvider({ children }: { children: React.ReactNode }) {
  const [useOpenDyslexic, setUseOpenDyslexic] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("useOpenDyslexic");
    if (saved === "true") {
      setUseOpenDyslexic(true);
    }
  }, []);

  useEffect(() => {
    if (mounted) {
      localStorage.setItem("useOpenDyslexic", String(useOpenDyslexic));
      if (useOpenDyslexic) {
        document.body.classList.add("font-opendyslexic");
      } else {
        document.body.classList.remove("font-opendyslexic");
      }
    }
  }, [useOpenDyslexic, mounted]);

  const toggleFont = () => {
    setUseOpenDyslexic(!useOpenDyslexic);
  };

  return (
    <FontContext.Provider value={{ useOpenDyslexic, toggleFont }}>
      {children}
    </FontContext.Provider>
  );
}

export function useFont() {
  const context = useContext(FontContext);
  if (context === undefined) {
    throw new Error("useFont must be used within a FontProvider");
  }
  return context;
}