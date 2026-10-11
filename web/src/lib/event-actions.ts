// Browser-side event actions shared by the desktop share dropdown
// (ShareMenu.astro) and the narrow layout's event panel (EventPanel.astro):
// read an event off its row, share it, put it in a calendar.
import { shareText } from "@/lib/share"
import { buildIcs } from "@/lib/ics"
import type { ShareEvent, ShareStrings } from "@/lib/types"

/** Per-event data, read off the row's cells (title link text without its
    language/recurrence suffix spans, venue, display price) and data-*. */
export function eventOf(row: HTMLElement): ShareEvent {
  const link = row.querySelector<HTMLAnchorElement>(".gc-title")!
  const title = link.querySelector(".cell-text")!.cloneNode(true) as HTMLElement
  title.querySelectorAll("*").forEach((n) => n.remove())
  const text = (sel: string) => row.querySelector(sel)?.textContent?.trim() ?? ""
  return {
    id: row.dataset.id ?? "",
    title: (title.textContent ?? "").replace(/\s+/g, " ").trim(),
    date: row.dataset.date ?? "",
    time: row.dataset.time || null,
    venue: text(".gc-place > .cell-text"),
    price: text(".gc-price > .cell-text"),
    url: link.href,
  }
}

/** Copy to the clipboard, with the execCommand route for older/insecure
    contexts. */
export async function copyText(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement("textarea")
    ta.value = text
    ta.style.position = "fixed"
    ta.style.opacity = "0"
    document.body.appendChild(ta)
    ta.select()
    document.execCommand("copy")
    ta.remove()
  }
}

/** Share via the OS sheet, else copy text + URL. Must be called synchronously
    from the click so the share sheet keeps its user activation. Resolves to
    "shared", "dismissed" (sheet closed) or "copied" (fallback used). */
export async function shareEvent(
  ev: ShareEvent,
  strings: ShareStrings,
): Promise<"shared" | "dismissed" | "copied"> {
  const text = shareText(ev, strings)
  if (navigator.share) {
    try {
      await navigator.share({ title: ev.title, text, url: ev.url })
      return "shared"
    } catch (err) {
      // Dismissed the sheet: done. Anything else (e.g. not allowed): copy.
      if ((err as DOMException).name === "AbortError") return "dismissed"
    }
  }
  await copyText(`${text} ${ev.url}`)
  return "copied"
}

/** Hand the OS a text/calendar file: iOS Safari offers "Add to Calendar",
    Android opens the calendar app, desktop downloads it. Built here rather
    than served statically (prod nginx has no text/calendar mime type). */
export function addToCalendar(ev: ShareEvent, timezone: string): void {
  const ics = buildIcs(ev, timezone)
  const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar;charset=utf-8" }))
  const a = document.createElement("a")
  a.href = url
  a.download = "event.ics"
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
