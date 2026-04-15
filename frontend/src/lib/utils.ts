import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNowStrict, format } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return format(new Date(date), "MMM d, yyyy");
}

export function formatDateTime(date: string | Date): string {
  return format(new Date(date), "MMM d, yyyy h:mm a");
}

/**
 * Human-friendly relative time ("3 min ago", "2 days ago"). Used for
 * sync badges, activity timestamps, last-updated columns.
 */
export function formatRelative(date: string | Date): string {
  const d = new Date(date);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  if (diffMs < 30_000) return "just now";
  return `${formatDistanceToNowStrict(d)} ago`;
}

/**
 * Return a contrast-safe text color ("white" | "black") for a given hex
 * background. Used where a tenant accent color is the background of a chip.
 */
export function contrastText(hex: string): "white" | "black" {
  const h = hex.replace("#", "");
  if (h.length !== 6) return "white";
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  // YIQ luminance
  const yiq = (r * 299 + g * 587 + b * 114) / 1000;
  return yiq >= 140 ? "black" : "white";
}
