"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ACTIVE_MENU_LINK_CLASS_NAME = "bg-accent/10 text-accent";
const INACTIVE_MENU_LINK_CLASS_NAME = "text-muted hover:text-foreground";

interface MenuLinkProps {
  href: string;
  label: string;
  activePathPrefixes: readonly string[];
}

export function MenuLink({ href, label, activePathPrefixes }: MenuLinkProps) {
  const pathname = usePathname();
  const isActive = pathname === href || activePathPrefixes.some((prefix) => pathname.startsWith(prefix));

  return (
    <Link
      href={href}
      aria-current={isActive ? "page" : undefined}
      className={`rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
        isActive ? ACTIVE_MENU_LINK_CLASS_NAME : INACTIVE_MENU_LINK_CLASS_NAME
      }`}
    >
      {label}
    </Link>
  );
}
