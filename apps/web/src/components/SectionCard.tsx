import type { ReactNode } from "react";

export function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="section-card">
      <div className="section-card-title">{title}</div>
      <div className="section-card-body">{children}</div>
    </article>
  );
}
