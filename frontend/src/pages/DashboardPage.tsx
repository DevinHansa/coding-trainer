import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/dashboard')
      .then(res => res.json())
      .then(data => {
        setData(data);
        setLoading(false);
      })
      .catch(console.error);
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-40 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 fade-in">
      {/* Hero Section */}
      <section className="bg-card border rounded-lg p-6 sm:p-10 shadow-sm relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row justify-between gap-6 items-center">
          <div>
            <h1 className="text-3xl sm:text-4xl font-bold mb-3">Welcome to SDE Prep</h1>
            <p className="text-muted-foreground text-lg mb-6 max-w-2xl">
              {data.plan.recommendation_text || "Ready to crush your next interview?"}
            </p>
            <div className="flex flex-wrap gap-3">
              <Button asChild size="lg" className="font-semibold shadow-glow">
                <Link to="/exercises">Train Now ✨</Link>
              </Button>
            </div>
          </div>
          
          {/* Rank Badge */}
          <div className="text-center bg-background/50 backdrop-blur border p-6 rounded-2xl flex-shrink-0 min-w-[200px]">
            <div className="text-5xl mb-2">{data.rank_info.icon}</div>
            <div className="font-bold text-lg">{data.rank_info.rank}</div>
            <div className="text-sm text-muted-foreground mb-3">{data.rank_info.current_xp} XP</div>
            <Progress value={data.rank_info.progress_percent} className="h-2 mb-1" />
            <div className="text-xs text-muted-foreground text-right">{data.rank_info.next_xp}</div>
          </div>
        </div>
      </section>

      {/* Stats Grid */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Attempts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data.stats.total_attempts}</div>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Exercises Passed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-emerald-500">{data.stats.passed_exercises}</div>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Average Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data.stats.average_score}%</div>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Day Streak</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-amber-500">{data.stats.day_streak} 🔥</div>
          </CardContent>
        </Card>
      </section>

      {/* Focus Areas (Weaknesses) */}
      {data.stats.active_weaknesses?.length > 0 && (
        <section>
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
            <span>🎯</span> Focus Areas
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {data.stats.active_weaknesses.map((weak: any) => (
              <Card key={weak.concept_tag} className="border-destructive/30 bg-destructive/5 hover:bg-destructive/10 transition-colors">
                <CardContent className="pt-6">
                  <div className="flex justify-between items-start mb-2">
                    <div className="font-semibold">{weak.concept_tag}</div>
                    <Badge variant="destructive">Needs Review</Badge>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Failed {weak.times_failed} times
                  </div>
                  <Button variant="outline" size="sm" className="mt-4 w-full" asChild>
                    <Link to="/exercises">Practice This</Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Ladder (Optional inline visual) */}
    </div>
  );
}
