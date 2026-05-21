const features = [
  {
    icon: "🧠",
    title: "Smart AI Curation",
    description:
      "Semantic relevance scoring - not keyword matching. Articles are ranked by meaning, so you get stories that actually matter to you.",
  },
  {
    icon: "⏱",
    title: "5-Minute Read",
    description:
      "Every story distilled to 2–3 sentences by a large language model. The insight, without the padding.",
  },
  {
    icon: "📬",
    title: "Daily in Your Inbox",
    description:
      "A beautifully designed newsletter, delivered every morning. Personalized to your chosen topics.",
  },
];

export default function Features() {
  return (
    <section id="features" className="bg-blush/50 border-y border-border py-20">
      <div className="max-w-6xl mx-auto px-6">
        {/* Section label */}
        <p className="text-xs font-sans font-semibold uppercase tracking-widest text-terracotta mb-10 text-center">
          Why TL;DR
        </p>

        <div className="grid md:grid-cols-3 gap-8">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-white rounded-2xl p-8 border border-border shadow-card
                         hover:shadow-editorial transition-shadow duration-200 group"
            >
              <div className="w-12 h-12 rounded-xl bg-blush flex items-center justify-center text-2xl mb-5
                              group-hover:bg-terracotta/10 transition-colors duration-200">
                {f.icon}
              </div>
              <h3 className="font-serif text-xl text-charcoal mb-3">{f.title}</h3>
              <p className="font-sans text-sm text-muted leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
