import { describe, expect, test } from "bun:test";
import { buildRecommendationQuery, pickRecommendation } from "../src/recommendations";

const current = { id: "current", title: "Midnight Loops", artist: "Nujabes" };

describe("recommendations", () => {
  test("prefers an unplayed track by the current artist", () => {
    const result = pickRecommendation(current, [
      current,
      { id: "similar-title", title: "Midnight Loops", artist: "Nujabes" },
      { id: "artist-match", title: "Feather", artist: "Nujabes" },
      { id: "query-match", title: "Lofi Hip Hop Mix", artist: "Various Artists" },
    ], "lofi hip hop", new Set(["current"]));

    expect(result?.id).toBe("artist-match");
  });

  test("never recommends a previously played candidate", () => {
    const result = pickRecommendation(current, [
      { id: "played", title: "Feather", artist: "Nujabes" },
      { id: "next", title: "Aruarian Dance", artist: "Nujabes" },
    ], "lofi", new Set(["played"]));

    expect(result?.id).toBe("next");
  });

  test("builds a provider query from artist and listener context", () => {
    expect(buildRecommendationQuery(current, "lofi hip hop")).toBe("Nujabes lofi hip hop music");
  });
});
