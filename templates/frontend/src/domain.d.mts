export function summarize(items: { status: string; value: number }[]): {
  total: number;
  completed: number;
  value: number;
};
export function bars<T extends { mean: number | null }>(groups: T[]): (T & { width: number })[];
export function errorMessage(payload: unknown, fallback?: string): string;
