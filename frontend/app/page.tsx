import type { Metadata } from "next";
import { PublicLanding } from "@/components/public-landing";
import { HomeSession } from "@/components/home-session";
export const metadata: Metadata = {
  title: "ForgeGov | Government intelligence. Connected capture.",
  description: "Find government opportunities, research the market, and bring your team into a shared pursuit with ForgeGov Project Rooms. Professional: $2,000 USD annually.",
  alternates: { canonical: "https://forge-gov.com/" },
  openGraph: { title: "ForgeGov — From opportunity to coordinated pursuit", description: "Government intelligence, capture operations, Project Rooms, and ForgeAI in one connected workflow.", url: "https://forge-gov.com/", type: "website", images: [{url:"https://forge-gov.com/product/capture.webp",width:1440,height:900,alt:"ForgeGov capture operations in a demonstration workspace"}] },
  twitter: { card: "summary_large_image", title: "ForgeGov — Government intelligence. Connected capture.", images: ["https://forge-gov.com/product/capture.webp"] },
};
export default function HomePage() { return <HomeSession><PublicLanding/></HomeSession>; }
