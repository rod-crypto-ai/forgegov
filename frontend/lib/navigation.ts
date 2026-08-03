import type { LucideIcon } from "lucide-react";
import {
  BadgeDollarSign,
  BarChart3,
  Bell,
  BookOpenCheck,
  Bot,
  BriefcaseBusiness,
  Building2,
  CalendarSearch,
  ChartNoAxesCombined,
  ContactRound,
  FileText,
  FolderKanban,
  Handshake,
  Landmark,
  LayoutDashboard,
  ListChecks,
  Map,
  Network,
  Search,
  Shapes,
  Tags,
  Target,
  Users,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon?: LucideIcon;
  description?: string;
  apiPath?: string;
  recordLabel?: string;
  columns?: Array<{ key: string; label: string }>;
};

export type NavGroup = {
  label: string;
  icon: LucideIcon;
  items: NavItem[];
};

export const standaloneItems: NavItem[] = [
  {
    href: "/assistant",
    label: "ForgeGov AI",
    icon: Bot,
    description: "Research opportunities, summarize documents, and prepare capture actions from grounded platform data.",
  },
];

export const navigationGroups: NavGroup[] = [
  {
    label: "Capture",
    icon: FolderKanban,
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/capture/teaming", label: "Teaming", icon: Handshake, description: "Discover partners and manage teaming leads from vendor and award intelligence." },
      { href: "/project-rooms", label: "Project Rooms", icon: Users, description: "Secure opportunity rooms for internal teams and invited partner companies." },
      { href: "/capture/pipelines", label: "Pipelines", icon: FolderKanban, apiPath: "/pipeline/", recordLabel: "pipeline item" },
      { href: "/capture/pursuits", label: "Pursuits", icon: Target, apiPath: "/pursuits/", recordLabel: "pursuit" },
      { href: "/capture/tasks", label: "Tasks", icon: ListChecks, apiPath: "/tasks/", recordLabel: "task" },
      { href: "/capture/saved-searches", label: "Saved Searches", icon: Search, apiPath: "/saved-searches/", recordLabel: "saved search" },
      { href: "/capture/alerts", label: "Alerts", icon: Bell, description: "Review new matches generated from enabled saved searches." },
    ],
  },
  {
    label: "Network",
    icon: Network,
    items: [
      { href: "/company", label: "Company Hub", icon: Building2, description: "Manage company profile, team members, invitations, roles, and partner relationships." },
      { href: "/network", label: "Company Directory", icon: Building2, description: "Find companies, connect, manage invitations, and invite trusted partners into Project Rooms." },
      { href: "/network?tab=invitations", label: "Invitations", icon: Handshake, description: "Review company connection requests and Project Room invitations." },
      { href: "/network?tab=partners", label: "Active Partners", icon: Users, description: "Manage trusted company relationships and shared Project Rooms." },
    ],
  },
  {
    label: "Beacon",
    icon: ContactRound,
    items: [
      { href: "/beacon/contacts", label: "Contacts", icon: ContactRound, apiPath: "/contacts/", recordLabel: "contact" },
    ],
  },
  {
    label: "Reports",
    icon: BarChart3,
    items: [
      { href: "/reports/funding", label: "Funding", icon: BadgeDollarSign, description: "Analyze obligated dollars, ceiling values, agency concentration, and spending movement." },
      { href: "/reports/new-entrants", label: "New Entrants", icon: ChartNoAxesCombined, description: "Identify vendors entering agencies, categories, and markets for the first time." },
    ],
  },
  {
    label: "Opportunities",
    icon: FileText,
    items: [
      { href: "/opportunities/federal-forecasts", label: "Federal Forecasts", icon: CalendarSearch, description: "Search the official Acquisition.gov directory of recurring agency procurement forecasts." },
      { href: "/opportunities/federal-contracts", label: "Federal Contract Opportunities", icon: FileText },
      { href: "/opportunities/federal-vehicles", label: "Federal Contract Vehicles", icon: Network, description: "Search live USAspending IDV records and contract vehicle holders." },
      { href: "/opportunities/state-local", label: "State and Local Contract Sources", icon: Map, description: "Open verified public state procurement portals." },
      { href: "/opportunities/subcontracting", label: "Subcontracting", icon: Handshake, description: "Search SBA SUBNet opportunities and SAM acquisition subaward data." },
      { href: "/opportunities/federal-grants", label: "Federal Grant Opportunities", icon: Landmark },
    ],
  },
  {
    label: "Awards",
    icon: BriefcaseBusiness,
    items: [
      { href: "/awards/federal-contracts", label: "Federal Contract Awards", icon: BriefcaseBusiness, apiPath: "/live/sam/contract-awards/?record_type=contracts&limit=100", recordLabel: "award" },
      { href: "/awards/federal-idv", label: "Federal Contract IDV Awards", icon: Network, apiPath: "/live/sam/contract-awards/?record_type=idv&limit=100", recordLabel: "IDV award" },
      { href: "/awards/federal-vehicles", label: "Federal Contract Vehicles", icon: Network, apiPath: "/live/sam/contract-awards/?record_type=vehicles&limit=100", recordLabel: "contract vehicle" },
    ],
  },
  {
    label: "Participants",
    icon: Users,
    items: [
      { href: "/participants/federal-agencies", label: "Federal Agencies", icon: Building2, description: "Agency spend, vendors, categories and active opportunities." },
      { href: "/participants/vendors", label: "Vendors", icon: BriefcaseBusiness, description: "Competitor award history, agency relationships and category strengths." },
    ],
  },
  {
    label: "Categories",
    icon: Shapes,
    items: [
      { href: "/categories/naics", label: "NAICS Categories", icon: Tags, description: "Market analytics from stored opportunities and awards." },
      { href: "/categories/psc", label: "PSC Categories", icon: Tags, description: "Market analytics from stored opportunities and awards." },
    ],
  },
];

export const utilityItems: NavItem[] = [
  { href: "/workspace", label: "Workspace", icon: Users, apiPath: "/organizations/", recordLabel: "workspace" },
  { href: "/settings", label: "Settings", icon: BookOpenCheck },
];

export const allNavigationItems = [
  ...standaloneItems,
  ...navigationGroups.flatMap((group) => group.items),
  ...utilityItems,
];

export function getFeatureByPath(pathname: string): NavItem | undefined {
  return allNavigationItems.find((item) => item.href === pathname);
}
