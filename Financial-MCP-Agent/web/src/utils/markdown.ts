export interface MarkdownHeading {
  depth: number;
  text: string;
  id: string;
}


export function headingId(text: string): string {
  const cleaned = text
    .trim()
    .toLowerCase()
    .replace(/[`*_~]/g, "")
    .replace(/[^a-z0-9\u3400-\u9fff\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return cleaned || "section";
}


export function extractHeadings(markdown: string): MarkdownHeading[] {
  const seen = new Map<string, number>();
  return markdown
    .split(/\r?\n/)
    .map((line) => line.match(/^(#{1,3})\s+(.+?)\s*$/))
    .filter((match): match is RegExpMatchArray => Boolean(match))
    .map((match) => {
      const text = match[2].replace(/[`*_~]/g, "").trim();
      const base = headingId(text);
      const count = seen.get(base) ?? 0;
      seen.set(base, count + 1);
      return {
        depth: match[1].length,
        text,
        id: count === 0 ? base : `${base}-${count + 1}`,
      };
    });
}


export function sanitizeMarkdown(markdown: string): string {
  return markdown
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<[^>]+>/g, "");
}
