import type { AnchorHTMLAttributes } from "react";

type MarkdownLinkProps = Pick<AnchorHTMLAttributes<HTMLAnchorElement>, "href" | "title" | "children">;

export function MarkdownLink({ href, title, children }: MarkdownLinkProps) {
  return (
    <a href={href} title={title} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}
