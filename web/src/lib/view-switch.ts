// Client-side view switcher shared by pages that ship several views of the same
// content in one static page (film: by film / by time; My list: events / films
// / venues). Markup contract:
//   <div data-view-root=NAME data-active-view=…>
//     <GridRadioButtons name=NAME …/>        (fires `gridradiochange`)
//     <div data-view="a">…</div> <div data-view="b" hidden>…</div>
// The active view is shown (others get `hidden`), reflected into the radio
// control, persisted under `storageKey`, and the grid + agenda scripts re-run
// for the tree that just became visible.

export interface ViewSwitch {
  /** Show a view without persisting it (e.g. a forced empty-state view). */
  show(view: string): void;
  /** The persisted choice, or the fallback when none/invalid is stored. */
  stored(): string;
}

export function initViewSwitch(
  name: string,
  storageKey: string,
  fallback: string,
  onChange?: (view: string) => void,
): ViewSwitch | null {
  const root = document.querySelector<HTMLElement>(`[data-view-root="${name}"]`);
  const group = root?.querySelector<HTMLElement>(`[data-grid-radio="${name}"]`);
  if (!root || !group) return null;
  const views = [...root.querySelectorAll<HTMLElement>("[data-view]")];
  const valid = new Set(views.map((v) => v.dataset.view));

  function stored(): string {
    let value: string | null = null;
    try {
      value = localStorage.getItem(storageKey);
    } catch {
      // Blocked storage: use the fallback.
    }
    if (value && valid.has(value)) return value;
    // A page may omit views it has no content for (a city without film).
    return valid.has(fallback) ? fallback : (views[0]?.dataset.view ?? fallback);
  }

  function show(view: string) {
    root!.dataset.activeView = view;
    views.forEach((v) => (v.hidden = v.dataset.view !== view));
    // Reflect the choice into the radio control: check the matching input and
    // move data-active so the indicator fill follows (CSS keys off
    // [data-grid-radio-option][data-active]).
    const input = group!.querySelector<HTMLInputElement>(`input[value="${view}"]`);
    if (input) input.checked = true;
    group!
      .querySelectorAll<HTMLElement>("[data-grid-radio-option]")
      .forEach((opt) =>
        opt.dataset.value === view
          ? opt.setAttribute("data-active", "")
          : opt.removeAttribute("data-active"),
      );
    // Announce gridsync for the just-revealed tree (its grid geometry comes
    // from CSS, but dependents re-place against it), then re-place the
    // now-markers.
    window.syncGrid?.();
    window.syncAgenda?.();
    onChange?.(view);
  }

  group.addEventListener("gridradiochange", (e) => {
    const view = (e as CustomEvent<string>).detail;
    try {
      localStorage.setItem(storageKey, view);
    } catch {
      // Not persisted; still switch for this visit.
    }
    show(view);
  });

  return { show, stored };
}
