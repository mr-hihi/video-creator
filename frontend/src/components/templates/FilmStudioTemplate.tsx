import type { ReactNode } from "react";
import { MenuLink } from "@/components/atoms/MenuLink";
import { FILM_STUDIO_MENU_ITEMS } from "@/lib/constants";
import { PageTemplate } from "./PageTemplate";

interface FilmStudioTemplateProps {
  children: ReactNode;
}

export function FilmStudioTemplate({ children }: FilmStudioTemplateProps) {
  return (
    <PageTemplate>
      <nav aria-label="Film Studio" className="-mt-2 flex flex-wrap items-center gap-1">
        {FILM_STUDIO_MENU_ITEMS.map((menuItem) => (
          <MenuLink key={menuItem.href} {...menuItem} />
        ))}
      </nav>
      {children}
    </PageTemplate>
  );
}
