"use client";

const topics = [
  { label: "Generative AI", emoji: "🤖" },
  { label: "Fintech",       emoji: "💳" },
  { label: "Tech",          emoji: "💻" },
  { label: "Startups",      emoji: "🚀" },
  { label: "Crypto",        emoji: "₿"  },
];

interface Props {
  selectedTopics: string[];
  onTopicsChange: (topics: string[]) => void;
}

export default function TopicSelector({ selectedTopics, onTopicsChange }: Props) {
  const toggle = (label: string) => {
    onTopicsChange(
      selectedTopics.includes(label)
        ? selectedTopics.filter((t) => t !== label)
        : [...selectedTopics, label]
    );
  };

  return (
    <section id="topics" className="max-w-6xl mx-auto px-6 py-20">
      <div className="text-center mb-12">
        <p className="text-xs font-sans font-semibold uppercase tracking-widest text-terracotta mb-3">
          Personalize
        </p>
        <h2 className="font-serif text-4xl md:text-5xl text-charcoal mb-4">
          Your interests. Your newsletter.
        </h2>
        <p className="font-sans text-muted max-w-md mx-auto leading-relaxed">
          Pick the topics you care about. The AI does the rest - surfacing only
          the stories most relevant to you.
        </p>
      </div>

      {/* Pills */}
      <div className="flex flex-wrap justify-center gap-3 mb-10">
        {topics.map(({ label, emoji }) => (
          <button
            key={label}
            onClick={() => toggle(label)}
            className={`topic-pill ${
              selectedTopics.includes(label) ? "topic-pill-active" : "topic-pill-inactive"
            }`}
          >
            <span className="mr-1.5">{emoji}</span>
            {label}
          </button>
        ))}
      </div>

      {/* Active summary */}
      <p className="text-center text-sm font-sans text-muted">
        {selectedTopics.length === 0
          ? "Select at least one topic to get started."
          : `You'll receive stories on: ${selectedTopics.join(", ")}.`}
      </p>
    </section>
  );
}
