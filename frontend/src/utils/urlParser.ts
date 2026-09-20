export interface ParsedSessionTarget {
  gameId: string;
  roundId?: string;
  isBroadcast: boolean;
}

export function parseLichessTarget(input: string): ParsedSessionTarget | null {
  const clean = input.trim();
  if (!clean) return null;

  // 1. Full Tournament Broadcast URL: https://lichess.org/broadcast/.../ROUND_ID/GAME_ID
  if (clean.includes('lichess.org/broadcast/')) {
    const parts = clean.split('/').filter(p => p && !['http:', 'https:', 'lichess.org', 'broadcast'].includes(p));
    const hex8Tokens = parts.filter(p => /^[a-zA-Z0-9]{8}$/.test(p));
    if (hex8Tokens.length >= 2) {
      // In Lichess URL schemas, roundId precedes gameId
      return { roundId: hex8Tokens[0], gameId: hex8Tokens[1], isBroadcast: true };
    } else if (hex8Tokens.length === 1) {
      return { roundId: hex8Tokens[0], gameId: hex8Tokens[0], isBroadcast: true };
    }
  }

  // 2. Casual Game URL: https://lichess.org/kSc2w4MX/white or https://lichess.org/kSc2w4MX
  const matchUrl = clean.match(/lichess\.org\/([a-zA-Z0-9]{8})/);
  if (matchUrl) {
    return { gameId: matchUrl[1], isBroadcast: false };
  }

  // 3. Two space-separated IDs: <round_id> <game_id>
  const spaceTokens = clean.split(/\s+/);
  if (spaceTokens.length >= 2 && spaceTokens[0].length === 8 && spaceTokens[1].length === 8) {
    return { roundId: spaceTokens[0], gameId: spaceTokens[1], isBroadcast: true };
  }

  // 4. Raw 8-character ID
  const rawIdMatch = clean.match(/^([a-zA-Z0-9]{8})$/);
  if (rawIdMatch) {
    return { gameId: rawIdMatch[1], isBroadcast: false };
  }

  return null;
}