// What the adapter promises, without a browser: the chunk layout of the
// static build, the routes of the workspace API, one request per key, and a
// sentence a reader may see for every failure.

import { describe, expect, it, vi } from "vitest";
import { StaticAdapter } from "./static";
import { ApiAdapter } from "./api";
import { DataError, dataErrorSentence } from "./adapter";

function stub(answers: Record<string, unknown>, seen: string[] = []) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    seen.push(url + (init && (init.headers as Record<string, string>)?.Authorization ? " +token" : ""));
    if (!(url in answers)) return { ok: false, status: 404, json: async () => ({}) } as Response;
    return { ok: true, status: 200, json: async () => answers[url] } as Response;
  });
}

describe("StaticAdapter", () => {
  const base = "https://example.test/previews/9/data/";
  it("reads each view from its own chunk, under the base it was given", async () => {
    const seen: string[] = [];
    const answers = {
      [base + "index.json"]: { schema: "tark.index.v1" },
      [base + "screener.json"]: { schema: "tark.screener.v1" },
      [base + "product/hl_paf/record.json"]: { schema: "tark.record.v1" },
      [base + "product/hl_paf/selection.json"]: { schema: "tark.selection.v1" },
      [base + "product/hl_paf/cohort.json"]: { schema: "tark.cohort.v1" },
      [base + "product/hl_paf/facts.json"]: { schema: "tark.facts.v1" },
      [base + "product/hl_paf/liquidity/plan_tech_media.json"]: { schema: "tark.liquidity.v1" },
      [base + "product/hl_paf/documents/plan_tech_media.json"]: { schema: "tark.documents.v1" },
    };
    vi.stubGlobal("fetch", stub(answers, seen));
    const a = new StaticAdapter(base);
    expect(a.source).toBe("static");
    expect((await a.getIndex()).schema).toBe("tark.index.v1");
    expect((await a.getScreener()).schema).toBe("tark.screener.v1");
    expect((await a.getRecord("hl_paf")).schema).toBe("tark.record.v1");
    expect((await a.getSelection("hl_paf")).schema).toBe("tark.selection.v1");
    expect((await a.getCohort("hl_paf")).schema).toBe("tark.cohort.v1");
    expect((await a.getFacts("hl_paf")).schema).toBe("tark.facts.v1");
    expect((await a.getLiquidity("plan_tech_media", "hl_paf")).schema).toBe("tark.liquidity.v1");
    expect((await a.getDocuments("plan_tech_media", "hl_paf")).schema).toBe("tark.documents.v1");
    expect(seen).toHaveLength(8);
  });

  it("asks once for the same chunk however many views want it", async () => {
    const seen: string[] = [];
    vi.stubGlobal("fetch", stub({ [base + "index.json"]: { schema: "tark.index.v1" } }, seen));
    const a = new StaticAdapter(base);
    await Promise.all([a.getIndex(), a.getIndex(), a.getIndex()]);
    expect(seen).toEqual([base + "index.json"]);
  });

  it("does not keep a failure as an answer", async () => {
    const seen: string[] = [];
    vi.stubGlobal("fetch", stub({}, seen));
    const a = new StaticAdapter(base);
    await expect(a.getIndex()).rejects.toBeInstanceOf(DataError);
    await expect(a.getIndex()).rejects.toBeInstanceOf(DataError);
    expect(seen).toHaveLength(2);
  });
});

describe("ApiAdapter", () => {
  const base = "/api";
  it("reads the reference routes with the reader’s token, and a plan as a query", async () => {
    const seen: string[] = [];
    const answers = {
      "/api/reference/index.json": { schema: "tark.index.v1" },
      "/api/reference/hl_paf/record.json": { schema: "tark.record.v1" },
      "/api/reference/hl_paf/liquidity.json?plan=plan_tech_media": { schema: "tark.liquidity.v1" },
    };
    vi.stubGlobal("fetch", stub(answers, seen));
    const a = new ApiAdapter(base, () => "a-session-token");
    expect(a.source).toBe("api");
    await a.getIndex();
    await a.getRecord("hl_paf");
    await a.getLiquidity("plan_tech_media", "hl_paf");
    expect(seen.every((u) => u.endsWith(" +token"))).toBe(true);
    expect(seen[2]).toContain("plan=plan_tech_media");
  });

  it("reads a workspace record by its id when it was given one", async () => {
    const seen: string[] = [];
    vi.stubGlobal("fetch", stub({ "/api/records/r-1/record.json": { schema: "tark.record.v1" } }, seen));
    const a = new ApiAdapter(base, () => null, "r-1");
    expect((await a.getRecord("anything")).schema).toBe("tark.record.v1");
    expect(seen[0]).toBe("/api/records/r-1/record.json");
    expect(seen[0]).not.toContain("+token");
  });
});

describe("what a reader is told", () => {
  it("gives one plain sentence per failure, never a status code alone", () => {
    expect(dataErrorSentence(new DataError("u", 404, "x"))).toMatch(/not on this build/);
    expect(dataErrorSentence(new DataError("u", 403, "x"))).toMatch(/workspace you belong to/);
    expect(dataErrorSentence(new DataError("u", 500, "x"))).toMatch(/try again in a moment/i);
    expect(dataErrorSentence(new Error("boom"))).toMatch(/try again in a moment/i);
    for (const s of [404, 403, 500].map((n) => dataErrorSentence(new DataError("u", n, "x")))) {
      expect(s).not.toMatch(/[;—]/);
      expect(s.trim().endsWith(".")).toBe(true);
    }
  });
});
