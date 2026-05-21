"use client";

import { useState } from "react";
import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Features from "@/components/Features";
import TopicSelector from "@/components/TopicSelector";
import Stories from "@/components/Stories";
import Footer from "@/components/Footer";

export default function Home() {
  // Shared topic state — TopicSelector sets it, Hero reads it for the subscribe call
  const [selectedTopics, setSelectedTopics] = useState<string[]>(["Generative AI"]);

  return (
    <main className="min-h-screen bg-cream">
      <Navbar />
      <Hero selectedTopics={selectedTopics} />
      <Features />
      <TopicSelector selectedTopics={selectedTopics} onTopicsChange={setSelectedTopics} />
      <Stories />
      <Footer />
    </main>
  );
}
