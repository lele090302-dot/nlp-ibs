"use client";

import { useState } from "react";
import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Features from "@/components/Features";
import Stories from "@/components/Stories";
import Footer from "@/components/Footer";

export default function Home() {
  const [selectedTopics, setSelectedTopics] = useState<string[]>(["AI"]);

  return (
    <main className="min-h-screen bg-cream">
      <Navbar />
      <Hero selectedTopics={selectedTopics} onTopicsChange={setSelectedTopics} />
      <Features />
      <Stories />
      <Footer />
    </main>
  );
}
