import { createServerFn } from "@tanstack/react-start";
import { supabaseAdmin } from "@/integrations/supabase/client.server";
import problemsData from "@/data/problems.json";

type RawProblem = {
  slug: string; lang: "sql" | "python"; topic: string; diff: number;
  title: string; prompt: string; starter?: string; solution?: string;
  schema?: string | null; expected?: unknown; fn?: string; tests?: unknown[]; hints: string[];
};

export const seedProblems = createServerFn({ method: "POST" }).handler(async () => {
  const rows = (problemsData as RawProblem[]).map((p) => ({
    slug: p.slug,
    language: p.lang,
    topic: p.topic,
    difficulty: p.diff,
    title: p.title,
    prompt_md: p.prompt,
    starter_code: p.starter ?? "",
    solution_code: p.solution ?? "",
    schema_sql: p.lang === "sql" ? p.schema ?? null : null,
    test_cases: p.lang === "sql"
      ? { kind: "sql", expected: p.expected }
      : { kind: "python", fn: p.fn, cases: p.tests },
    hints: p.hints,
  }));
  const { error } = await supabaseAdmin.from("problems").upsert(rows, { onConflict: "slug" });
  if (error) throw new Error(error.message);
  const { count } = await supabaseAdmin.from("problems").select("*", { count: "exact", head: true });
  return { inserted: rows.length, total: count };
});
