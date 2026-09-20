const navigationItems = [
  {
    label: "Home",
    href: "/home",
    color: "bg-[var(--periwinkle)]",
    position: "left-0",
    width: "w-1/3",
    zIndex: "z-[1]",
  },
  {
    label: "Talk with Others",
    href: "/talk-with-others",
    color: "bg-[var(--periwinkle-2)]",
    position: "left-[23%]",
    width: "w-[20%]",
    zIndex: "z-[10]",
    clipPaths: ["header-item-wave-1", "header-item-wave-2"],
  },
  {
    label: "Talk to Spi",
    href: "/talk-to-spi",
    color: "bg-[var(--periwinkle-3)]",
    position: "left-1/3",
    width: "w-1/3",
    zIndex: "z-[2]",
  },
  {
    label: "Wellness Check",
    href: "/wellness-check",
    color: "bg-[var(--periwinkle-4)]",
    position: "left-[57%]",
    width: "w-[20%]",
    zIndex: "z-[10]",
    clipPaths: ["header-item-wave-3", "header-item-wave-4"],
  },
  {
    label: "Settings",
    href: "/settings",
    color: "bg-[var(--periwinkle-5)]",
    position: "left-2/3",
    width: "w-1/3",
    zIndex: "z-[3]",
  },
];

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 w-screen bg-[var(--sky)]">
      <svg
        className="absolute size-0"
        aria-hidden="true"
      >
        <defs>
          <clipPath
            id="header-bottom-wave"
            clipPathUnits="objectBoundingBox"
          >
            <path d="M0 0 H1 V.78 C.92 .94 .84 .62 .75 .78 C.67 .94 .58 .62 .5 .78 C.42 .94 .33 .62 .25 .78 C.16 .94 .08 .62 0 .78 Z" />
          </clipPath>
          <clipPath id="header-item-wave-1" clipPathUnits="objectBoundingBox">
            <path d="M.1 0 H1 V1 H.1 C.02 .84 .18 .66 .08 .5 C-.01 .34 .17 .14 .1 0 Z" />
          </clipPath>
          <clipPath id="header-item-wave-2" clipPathUnits="objectBoundingBox">
            <path d="M0 0 H.9 C.98 .16 .82 .34 .92 .5 C1 .66 .83 .86 .9 1 H0 Z" />
          </clipPath>
          <clipPath id="header-item-wave-3" clipPathUnits="objectBoundingBox">
            <path d="M.08 0 H1 V1 H.08 C0 .82 .16 .64 .06 .48 C-.02 .32 .16 .13 .08 0 Z" />
          </clipPath>
          <clipPath id="header-item-wave-4" clipPathUnits="objectBoundingBox">
            <path d="M0 0 H.92 C1 .18 .84 .36 .94 .52 C1 .68 .84 .87 .92 1 H0 Z" />
          </clipPath>
        </defs>
      </svg>

      <nav
        className="z-50 relative h-32 overflow-hidden"
        aria-label="Main navigation"
        style={{ clipPath: "url(#header-bottom-wave)" }}
      >
        {navigationItems.map((item) => (
          <a
            key={item.label}
            className={`absolute inset-y-0 ${item.position} ${item.width} ${item.zIndex} flex items-center justify-center text-center text-xs font-bold text-[var(--ink)] outline-none transition-[filter,scale] focus-visible:scale-105 focus-visible:brightness-100 sm:text-lg ${item.clipPaths ? "" : item.color}`}
            href={item.href}
          >
            {item.clipPaths?.map((clipPath, index) => (
              <span
                key={clipPath}
                className={`pointer-events-none absolute inset-y-0 w-[58%] ${item.color} ${index === 0 ? "left-0" : "right-0"}`}
                style={{ clipPath: `url(#${clipPath})` }}
              />
            ))}
            <span className="relative z-10 whitespace-nowrap -translate-y-2 px-3">
              {item.label}
            </span>
          </a>
        ))}
      </nav>
      <div
        className="animate-wave-breathe-x fixed w-screen top-1 left-0 right-0 h-32 bg-(--periwinkle) opacity-33 overflow-hidden"
        aria-label="Main navigation"
        style={{ clipPath: "url(#header-bottom-wave)" }}
      />
      <div
        className="animate-wave-breathe-x-delay5s fixed w-screen top-2 left-0 right-0 h-32 bg-(--periwinkle) opacity-33 overflow-hidden"
        aria-label="Main navigation"
        style={{ clipPath: "url(#header-bottom-wave)" }}
      />
    </header>
  );
}
