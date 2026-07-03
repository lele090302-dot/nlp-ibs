"use client";

import { useState } from "react";
import Image from "next/image";

const topics = [
  { label: "AI", short: "AI" },
  { label: "Fintech",       short: "Fintech" },
  { label: "Tech",          short: "Tech" },
  { label: "Startups",      short: "Startups" },
  { label: "Crypto",        short: "Crypto" },
];

interface Props {
  selectedTopics: string[];
  onTopicsChange: (topics: string[]) => void;
}

type Status = "idle" | "loading" | "success" | "error";

export default function Hero({ selectedTopics, onTopicsChange }: Props) {
  const [name, setName]       = useState("");
  const [email, setEmail]     = useState("");
  const [cadence, setCadence] = useState<"daily" | "weekly">("daily");
  const [status, setStatus]   = useState<Status>("idle");
  const [message, setMessage] = useState("");

  const toggleTopic = (label: string) => {
    onTopicsChange(
      selectedTopics.includes(label)
        ? selectedTopics.filter((t) => t !== label)
        : [...selectedTopics, label]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setMessage("Please enter your name."); return; }
    if (selectedTopics.length === 0) { setMessage("Please select at least one topic."); return; }

    setStatus("loading");
    setMessage("");

    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          topics: selectedTopics,
          frequency: cadence,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setStatus("success");
        const cadenceMsg = cadence === "daily"
          ? "Your newsletter will be delivered every day at 8:00 AM CET/CEST, before your first coffee."
          : "Your newsletter will be delivered every Monday at 8:00 AM CET/CEST, before your first coffee.";
        setMessage(`Preferences updated! ${cadenceMsg}`);
      } else {
        setStatus("error");
        setMessage(data.error ?? "Something went wrong. Please try again.");
      }
    } catch {
      setStatus("error");
      setMessage("Network error. Please try again.");
    }
  };

  return (
    <section id="form" className="max-w-6xl mx-auto px-6 pt-16 pb-20 md:pt-24 md:pb-28">
      <div className="grid md:grid-cols-2 gap-12 items-start">

        {/* Left - copy + form */}
        <div className="flex flex-col gap-6">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 self-start">
            <span className="w-2 h-2 rounded-full bg-terracotta animate-pulse" />
            <span className="text-xs font-sans font-semibold uppercase tracking-widest text-terracotta">
              AI-Curated. Human-Readable.
            </span>
          </div>

          {/* Headline */}
          <h1 className="font-serif text-5xl md:text-6xl lg:text-7xl leading-[1.05] text-charcoal">
            The top&nbsp;10 stories.{" "}
            <em className="text-terracotta not-italic">Zero noise.</em>
          </h1>

          {/* Subheadline */}
          <p className="font-sans text-lg text-muted leading-relaxed max-w-md">
            We pick the most relevant stories from hundreds of articles so you
            don&apos;t have to.
          </p>

          {/* Topic selection - inline */}
          <div>
            <p className="text-xs font-sans font-semibold uppercase tracking-widest text-muted mb-3">
              Choose your topics
            </p>
            <div className="flex flex-wrap gap-2">
              {topics.map(({ label, short }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => toggleTopic(label)}
                  className={`topic-pill text-sm ${
                    selectedTopics.includes(label) ? "topic-pill-active" : "topic-pill-inactive"
                  }`}
                >
                  {short}
                </button>
              ))}
            </div>
            {selectedTopics.length === 0 && (
              <p className="text-xs font-sans text-terracotta mt-2">
                Select at least one topic to get started.
              </p>
            )}
          </div>

          {/* Form */}
          {status === "success" ? (
            <div className="flex items-start gap-3 bg-blush border border-border rounded-2xl px-5 py-4 max-w-md">
              <span className="text-terracotta text-xl mt-0.5">✓</span>
              <p className="font-sans text-sm text-charcoal leading-relaxed">{message}</p>
            </div>
          ) : (
            <form
              onSubmit={handleSubmit}
              className="flex flex-col gap-4 max-w-md"
            >
              {/* Name */}
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                className="bg-white border border-border rounded-full px-5 py-3 text-sm font-sans
                           text-charcoal placeholder:text-muted focus:outline-none focus:ring-2
                           focus:ring-terracotta/40 transition"
              />

              {/* Email */}
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="bg-white border border-border rounded-full px-5 py-3 text-sm font-sans
                           text-charcoal placeholder:text-muted focus:outline-none focus:ring-2
                           focus:ring-terracotta/40 transition"
              />

              {/* Cadence */}
              <div>
                <p className="text-xs font-sans font-semibold uppercase tracking-widest text-muted mb-2">
                  Cadence
                </p>
                <div className="flex gap-2">
                  {(["daily", "weekly"] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setCadence(option)}
                      className={`flex-1 py-2.5 rounded-full text-sm font-sans font-medium border transition-all duration-150
                        ${cadence === option
                          ? "bg-terracotta text-white border-terracotta"
                          : "bg-white text-charcoal border-border hover:border-burnt hover:text-burnt"
                        }`}
                    >
                      {option === "daily" ? "Daily" : "Weekly"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Error message */}
              {status === "error" && (
                <p className="text-xs font-sans text-terracotta px-1">{message}</p>
              )}
              {message && status === "idle" && (
                <p className="text-xs font-sans text-terracotta px-1">{message}</p>
              )}

              <button
                type="submit"
                disabled={status === "loading" || selectedTopics.length === 0}
                className="btn-primary text-sm disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {status === "loading" ? "Subscribing..." : "Get Started"}
              </button>
            </form>
          )}

          {/* Social proof */}
          <p className="text-xs font-sans text-muted">
            Join <span className="text-charcoal font-medium">2,400+</span> readers in tech, finance, and AI.
            Free forever.
          </p>
        </div>

        {/* Right - editorial image card */}
        <div className="relative hidden md:block">
          <div className="absolute -top-8 -right-8 w-72 h-72 rounded-full bg-blush opacity-60 blur-3xl" />

          <div className="relative bg-white rounded-3xl overflow-hidden shadow-editorial border border-border">
            <div className="relative h-64 w-full">
              <Image
                src="/hero-image.png"
                alt="Editorial - morning newspaper with coffee"
                fill
                className="object-cover"
                priority
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[#C83A2A]/30 via-transparent to-[#E7A33C]/10" />
            </div>

            <div className="p-6">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-sans font-semibold uppercase tracking-widest text-terracotta">
                  Today&apos;s Brief
                </span>
                <span className="text-xs text-muted font-sans">· 5 min read</span>
              </div>
              <h3 className="font-serif text-xl text-charcoal leading-snug mb-2">
                OpenAI, Stripe, and the week&apos;s 8 other stories you actually need to know.
              </h3>
              <p className="text-sm font-sans text-muted leading-relaxed">
                Curated from 200+ sources. Summarized by AI. Delivered before your morning coffee.
              </p>
            </div>

            <div className="px-6 pb-6 flex gap-2 flex-wrap">
              {selectedTopics.length > 0
                ? selectedTopics.map((t) => (
                    <span key={t} className="text-xs font-sans font-medium px-3 py-1 rounded-full bg-blush text-terracotta">
                      {t}
                    </span>
                  ))
                : ["AI", "Fintech", "Startups"].map((t) => (
                    <span key={t} className="text-xs font-sans font-medium px-3 py-1 rounded-full bg-blush text-terracotta">
                      {t}
                    </span>
                  ))
              }
            </div>
          </div>

          {/* Reading time card - positioned below the main card */}
          <div className="mt-6 bg-white rounded-2xl shadow-card border border-border px-5 py-4 flex items-center gap-3 w-fit">
            <div className="w-10 h-10 rounded-full bg-blush flex items-center justify-center text-terracotta font-sans font-bold text-xs">TL;DR</div>
            <div>
              <p className="text-xs font-sans text-muted">Avg. reading time</p>
              <p className="text-sm font-sans font-semibold text-charcoal">Under 5 minutes</p>
            </div>
          </div>
        </div>

      </div>
    </section>
  );
}
