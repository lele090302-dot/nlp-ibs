import StoryCard, { Story } from "./StoryCard";
import SidebarCard from "./SidebarCard";
import StockTicker from "./StockTicker";

const stories: Story[] = [
  {
    rank: 1,
    title: "OpenAI launches GPT-5 with breakthrough reasoning capabilities",
    summary:
      "OpenAI has released GPT-5, featuring a new 'thinking mode' that dramatically improves performance on complex reasoning tasks. The model outperforms its predecessor on all major benchmarks and is available via API today.",
    topic: "GenAI",
    readingTime: 3,
    source: "TechCrunch",
    imageUrl: "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=400&q=80",
  },
  {
    rank: 2,
    title: "Stripe raises $1B at $65B valuation to accelerate AI-powered payments",
    summary:
      "Payments giant Stripe has closed a $1 billion funding round, valuing the company at $65 billion. The capital will fund expansion into new markets and accelerate its suite of AI-powered financial tools.",
    topic: "Fintech",
    readingTime: 2,
    source: "Bloomberg",
    imageUrl: "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=400&q=80",
  },
  {
    rank: 3,
    title: "Apple's M4 Ultra chip sets new performance records in independent tests",
    summary:
      "Independent benchmarks confirm Apple's M4 Ultra delivers a 40% performance uplift over M3 Ultra in multi-core workloads. The chip is now shipping in the new Mac Pro, starting at $6,999.",
    topic: "Tech",
    readingTime: 4,
    source: "The Verge",
    imageUrl: "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=400&q=80",
  },
  {
    rank: 4,
    title: "Ethereum ETF inflows hit record $800M in a single week",
    summary:
      "Spot Ethereum ETFs recorded their highest-ever weekly inflows of $800 million, driven by institutional demand following the SEC's approval of staking features. ETH price rose 18% on the news.",
    topic: "Crypto",
    readingTime: 3,
    source: "CoinTelegraph",
    imageUrl: "https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=400&q=80",
  },
];

const sidebarCards = [
  {
    icon: "☀️",
    title: "Your Daily Brief",
    body: "10 stories. 5 minutes. Every morning before 8am.",
    accent: false,
  },
];

export default function Stories() {
  return (
    <section id="stories" className="bg-blush/30 border-t border-border py-20">
      <div className="max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="mb-12">
          <p className="text-xs font-sans font-semibold uppercase tracking-widest text-terracotta mb-3">
            Today&apos;s Edition
          </p>
          <h2 className="font-serif text-4xl md:text-5xl text-charcoal">
            Top stories, ranked.
          </h2>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Story list - takes 2 cols */}
          <div className="lg:col-span-2 flex flex-col gap-5">
            {stories.map((story) => (
              <StoryCard key={story.rank} story={story} />
            ))}
          </div>

          {/* Sidebar */}
          <aside className="flex flex-col gap-5">
            {sidebarCards.map((card) => (
              <SidebarCard key={card.title} {...card} />
            ))}

            {/* Stock ticker */}
            <div id="market-pulse">
              <StockTicker />
            </div>

            {/* Quote card */}
            <div className="rounded-2xl border border-border bg-white p-6 shadow-card">
              <p className="font-serif text-lg italic text-charcoal leading-snug mb-3">
                &ldquo;Information is abundant. Clarity is rare.&rdquo;
              </p>
              <p className="font-sans text-xs text-muted uppercase tracking-widest">
                - The TL;DR Principle
              </p>
            </div>
          </aside>
        </div>
      </div>
    </section>
  );
}
