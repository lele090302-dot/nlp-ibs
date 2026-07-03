import Image from "next/image";

export interface Story {
  rank: number;
  title: string;
  summary: string;
  topic: string;
  readingTime: number;
  imageUrl: string;
  imagePosition?: string;
  source: string;
}

// Only these hosts are allowed by next.config.mjs — anything else falls back to a placeholder
const ALLOWED_IMAGE_HOSTS = ["images.unsplash.com", "picsum.photos"];

function isAllowedImageUrl(url: string): boolean {
  if (!url) return false;
  try {
    return ALLOWED_IMAGE_HOSTS.includes(new URL(url).hostname);
  } catch {
    return false;
  }
}

export default function StoryCard({ story }: { story: Story }) {
  const imageSrc = isAllowedImageUrl(story.imageUrl)
    ? story.imageUrl
    : "https://images.unsplash.com/photo-1495020683877-95802f6f8ceb?w=400&q=80";

  return (
    <article
      className="bg-white rounded-2xl border border-border shadow-card overflow-hidden
                 hover:shadow-editorial transition-shadow duration-200 flex flex-col sm:flex-row"
    >
      {/* Thumbnail */}
      <div className="relative w-full sm:w-40 h-44 sm:h-auto flex-shrink-0">
        <Image
          src={imageSrc}
          alt={story.title}
          fill
          className={`object-cover ${story.imagePosition ?? "object-center"}`}
        />
        {/* Rank badge */}
        <div className="absolute top-3 left-3 w-8 h-8 rounded-full bg-terracotta text-white
                        flex items-center justify-center text-xs font-sans font-bold shadow">
          {story.rank}
        </div>
      </div>

      {/* Content */}
      <div className="p-6 flex flex-col justify-between gap-3 flex-1">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs font-sans font-semibold uppercase tracking-widest text-terracotta">
              {story.topic}
            </span>
            <span className="text-xs text-muted font-sans">· {story.source}</span>
          </div>
          <h3 className="font-serif text-lg text-charcoal leading-snug mb-2">
            {story.title}
          </h3>
          <p className="font-sans text-sm text-muted leading-relaxed">
            {story.summary}
          </p>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs font-sans text-muted">
            ⏱ {story.readingTime} min read
          </span>
          <a
            href="#form"
            className="text-xs font-sans font-semibold text-terracotta hover:underline"
          >
            Subscribe to read →
          </a>
        </div>
      </div>
    </article>
  );
}
