import { describe, it, expect } from "vitest";
import { excerpt } from "@/lib/description";

describe("excerpt", () => {
  it("returns null for missing or blank text", () => {
    expect(excerpt(null)).toBeNull();
    expect(excerpt(undefined)).toBeNull();
    expect(excerpt("  \n\t ")).toBeNull();
  });

  it("collapses whitespace and keeps short text whole", () => {
    expect(excerpt("  A night\n\nof   jazz. ")).toBe("A night of jazz.");
  });

  it("cuts long text at a word boundary with an ellipsis", () => {
    const out = excerpt("one two three four five six", 15)!;
    expect(out).toBe("one two three…");
    expect(out.length).toBeLessThanOrEqual(15);
  });

  it("drops trailing punctuation before the ellipsis", () => {
    expect(excerpt("Hello there, my good friend", 14)).toBe("Hello there…");
  });

  it("hard-cuts a single long word", () => {
    expect(excerpt("x".repeat(50), 10)).toBe("x".repeat(9) + "…");
  });
});
