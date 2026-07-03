import StoryCard, { Story } from "./StoryCard";
import SidebarCard from "./SidebarCard";
import StockTicker from "./StockTicker";

const stories: Story[] = [
  {
    rank: 1,
    title: "Meta eyes a side hustle: renting out its AI compute like SpaceX",
    summary:
      "Meta is quietly plotting a cloud business that would sell spare AI compute and model access to outside customers, putting it in direct competition with AWS, Google Cloud, and Azure. The pivot follows a $180B+ infrastructure bet and hints that owning data centers, not just building models, may be where the real AI money is.",
    topic: "Tech",
    readingTime: 3,
    source: "TechCrunch",
    imageUrl: "https://images.unsplash.com/photo-1635002962487-2c1d4d2f63c2?w=400&q=80",
  },
  {
    rank: 2,
    title: "Anthropic drops Claude Sonnet 5 — flagship-level smarts, mid-tier price tag",
    summary:
      "Anthropic's newest model delivers near-Opus performance for agentic tasks like coding and tool use, at roughly 40-60% less cost. It's now the default for Free and Pro users, and the timing lines up with Anthropic's push toward a much-anticipated IPO.",
    topic: "AI",
    readingTime: 3,
    source: "VentureBeat",
    imageUrl: "https://images.unsplash.com/photo-1775441031103-1d559a6f91cd?w=400&q=80",
    imagePosition: "object-[20%_center]",
  },
  {
    rank: 3,
    title: "Europe's crypto grace period ends, and licenses are flying out the door",
    summary:
      "As the EU's MiCA transition period wrapped up, regulators rushed to approve a fresh batch of crypto firms across Italy, France, Malta, and Spain, pushing the bloc's total past 240 licensed providers. Binance, notably, still isn't one of them.",
    topic: "Crypto",
    readingTime: 2,
    source: "CoinTelegraph",
    imageUrl: "https://images.unsplash.com/photo-1518546305927-5a555bb7020d?w=400&q=80",
    imagePosition: "object-right",
  },
  {
    rank: 4,
    title: "J.P. Morgan and India team up so overseas payments show the real exchange rate",
    summary:
      "J.P. Morgan is linking up with India's UPI payment network so people sending money across borders can see the exact amount they'll pay or receive right away, instead of guessing at exchange rates. The feature is already live in nine countries, with more expected to follow.",
    topic: "Fintech",
    readingTime: 2,
    source: "J.P. Morgan Newsroom",
    imageUrl: "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=400&q=80",
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
            Latest Edition
          </p>
          <h2 className="font-serif text-4xl md:text-5xl text-charcoal">
            Top stories.
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
              <p className="font-serif text-lg italic text-charcoal leading-snug mb-1">
                &ldquo;Information is abundant.
              </p>
              <p className="font-serif text-lg italic text-charcoal leading-snug mb-3">
                Clarity is rare.&rdquo;
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
