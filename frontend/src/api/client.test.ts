import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getToken,
  handleAuthExpired,
  onAuthExpired,
  setToken,
} from "./client";

class MemoryStorage implements Storage {
  private values = new Map<string, string>();

  get length() {
    return this.values.size;
  }

  clear() {
    this.values.clear();
  }

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  key(index: number) {
    return [...this.values.keys()][index] ?? null;
  }

  removeItem(key: string) {
    this.values.delete(key);
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}

describe("session expiration", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", new MemoryStorage());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each(["AUTH_REQUIRED", "SESSION_EXPIRED"])(
    "clears the token and refreshes auth state for %s",
    (code) => {
      const listener = vi.fn();
      const unsubscribe = onAuthExpired(listener);
      setToken("active-session");

      expect(handleAuthExpired(code)).toBe(true);
      expect(getToken()).toBeNull();
      expect(listener).toHaveBeenCalledOnce();
      unsubscribe();
    },
  );

  it("ignores unrelated errors", () => {
    const listener = vi.fn();
    const unsubscribe = onAuthExpired(listener);

    expect(handleAuthExpired("UPSTREAM_ERROR")).toBe(false);
    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });

  it("refreshes auth state even if another request already cleared the token", () => {
    const listener = vi.fn();
    const unsubscribe = onAuthExpired(listener);

    expect(handleAuthExpired("SESSION_EXPIRED")).toBe(true);
    expect(listener).toHaveBeenCalledOnce();
    unsubscribe();
  });
});
