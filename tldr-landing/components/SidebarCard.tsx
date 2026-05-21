export interface SidebarCardProps {
  icon: string;
  title: string;
  body: string;
  accent?: boolean;
}

export default function SidebarCard({ icon, title, body, accent }: SidebarCardProps) {
  return (
    <div
      className={`rounded-2xl border p-5 shadow-card transition-shadow duration-200 hover:shadow-editorial
        ${accent
          ? "bg-terracotta text-white border-terracotta"
          : "bg-white text-charcoal border-border"
        }`}
    >
      <div className={`text-2xl mb-3`}>{icon}</div>
      <h4 className={`font-serif text-base mb-1 ${accent ? "text-white" : "text-charcoal"}`}>
        {title}
      </h4>
      <p className={`font-sans text-sm leading-relaxed ${accent ? "text-white/80" : "text-muted"}`}>
        {body}
      </p>
    </div>
  );
}
