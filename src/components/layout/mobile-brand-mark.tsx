"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function MobileBrandMark() {
  const pathname = usePathname();

  if (pathname === "/chat") return null;

  return (
    <Link
      href="/"
      className="fixed bottom-4 left-4 z-30 flex items-center gap-2 rounded-xl bg-background/95 px-2.5 py-1.5 shadow-sm ring-1 ring-border backdrop-blur md:hidden"
    >
      <Image
        src="/logo.png"
        alt="PNIXPG"
        width={24}
        height={24}
        className="size-6 rounded-md object-cover"
      />
      <span className="text-xs font-semibold">PNIXPG</span>
    </Link>
  );
}
