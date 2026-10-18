import Link from "next/link";
import type { ReactNode } from "react";
import { MenuLink } from "@/components/atoms/MenuLink";
import { APP_MENU_ITEMS, APP_NAME } from "@/lib/constants";

interface PageTemplateProps {
  children: ReactNode;
}

export function PageTemplate({ children }: PageTemplateProps) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Link href="/" className="text-base font-semibold tracking-tight">
            {APP_NAME}
          </Link>
          <nav aria-label="Main" className="-mx-3 flex max-w-full gap-1 overflow-x-auto px-3">
            {APP_MENU_ITEMS.map((menuItem) => (
              <MenuLink key={menuItem.href} {...menuItem} />
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">{children}</main>
    </div>
  );
}
