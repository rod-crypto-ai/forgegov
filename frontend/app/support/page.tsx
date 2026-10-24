import type { Metadata } from "next";
import { PublicInquiry } from "@/components/public-inquiry";
export const metadata:Metadata={title:"Product support | ForgeGov",description:"Submit a ForgeGov product support inquiry for administrator review."};
export default function Page(){return <PublicInquiry purpose="support"/>;}
