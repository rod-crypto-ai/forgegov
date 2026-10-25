"use client";
import Link from "next/link";
import { useEffect,useState } from "react";
import { ArrowRight } from "lucide-react";
import { authFetch } from "@/lib/api";
export function EnrollmentAction({className,details=false,label}:{className:string;details?:boolean;label?:string}) {
 const [open,setOpen]=useState<boolean|null>(null);
 useEffect(()=>{let active=true;authFetch<{public_registration:boolean}>("/auth/registration-config/").then(v=>{if(active)setOpen(v.public_registration);}).catch(()=>{});return()=>{active=false;};},[]);
 return <>{details&&<p>{open===true?"Public account registration is open. Verify your email to continue into company onboarding.":open===false?"Company enrollment is currently controlled. Request access for administrator review.":"Account access follows the current registration settings."}</p>}<Link className={className} href={open===false?"/request-access":"/register"}>{label ?? (open===true?"Create your account":open===false?"Request access":"Get started")}<ArrowRight size={17}/></Link></>;
}
