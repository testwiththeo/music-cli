export interface RecommendationTrack {
  id: string;
  title: string;
  artist: string;
}

function tokens(value: string): Set<string> {
  return new Set(
    value
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ")
      .split(/\s+/)
      .filter((word) => word.length > 2 && !["official", "video", "audio", "music"].includes(word)),
  );
}

function overlap(left: Set<string>, right: Set<string>): number {
  return [...left].filter((word) => right.has(word)).length;
}

function isSameTrack(left: RecommendationTrack, right: RecommendationTrack): boolean {
  return left.id === right.id || (
    left.title.trim().toLowerCase() === right.title.trim().toLowerCase()
    && left.artist.trim().toLowerCase() === right.artist.trim().toLowerCase()
  );
}

/**
 * Rank unplayed candidates using the active track and the listener's original
 * search as lightweight taste signals. A stable tie-break preserves provider order.
 */
export function pickRecommendation<T extends RecommendationTrack>(
  current: RecommendationTrack,
  candidates: T[],
  sourceQuery: string,
  playedIds: ReadonlySet<string>,
): T | null {
  const currentTitle = tokens(current.title);
  const currentArtist = tokens(current.artist);
  const queryTokens = tokens(sourceQuery);

  let best: T | null = null;
  let bestScore = -1;

  for (const candidate of candidates) {
    if (playedIds.has(candidate.id) || isSameTrack(candidate, current)) continue;

    const candidateTitle = tokens(candidate.title);
    const candidateArtist = tokens(candidate.artist);
    const sameArtist = candidate.artist.trim().toLowerCase() === current.artist.trim().toLowerCase();
    const score =
      (sameArtist ? 40 : 0)
      + overlap(currentArtist, candidateArtist) * 12
      + overlap(currentTitle, candidateTitle) * 5
      + overlap(queryTokens, candidateTitle) * 3
      + overlap(queryTokens, candidateArtist) * 2;

    if (score > bestScore) {
      best = candidate;
      bestScore = score;
    }
  }

  return best;
}

export function buildRecommendationQuery(current: RecommendationTrack, sourceQuery: string): string {
  const artist = current.artist.trim();
  const context = sourceQuery.trim();
  return artist && context ? `${artist} ${context} music` : `${artist || context} music`;
}
