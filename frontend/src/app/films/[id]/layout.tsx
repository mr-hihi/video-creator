export default function FilmProjectLayout({ children, modal }: LayoutProps<"/films/[id]">) {
  return (
    <>
      {children}
      {modal}
    </>
  );
}
