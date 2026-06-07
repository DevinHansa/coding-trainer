import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function ProgressPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/progress')
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
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  const renderConcepts = (concepts: any[]) => {
    if (!concepts || concepts.length === 0) {
      return (
        <div className="text-center py-12 text-muted-foreground border rounded-lg bg-card">
          <div className="text-4xl mb-4">🌱</div>
          <p>No progress data yet. Start practicing to see your stats here!</p>
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {concepts.map((concept: any) => (
          <Card key={concept.concept_tag} className={`relative overflow-hidden ${
            concept.mastery_level === 'expert' ? 'border-primary' : 
            concept.mastery_level === 'novice' ? 'border-destructive' : ''
          }`}>
            <div className={`absolute top-0 left-0 w-full h-1 ${
              concept.mastery_level === 'expert' ? 'bg-primary' :
              concept.mastery_level === 'proficient' ? 'bg-emerald-500' :
              concept.mastery_level === 'competent' ? 'bg-blue-500' :
              concept.mastery_level === 'learning' ? 'bg-amber-500' :
              'bg-destructive'
            }`} />
            <CardHeader className="pb-2 pt-4">
              <div className="flex justify-between items-start mb-2">
                <CardTitle className="text-lg font-bold truncate pr-2">{concept.concept_tag}</CardTitle>
                <Badge variant={concept.mastery_level === 'novice' ? 'destructive' : 'secondary'} className="capitalize">
                  {concept.mastery_level}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-muted-foreground">Average Score</span>
                    <span className="font-medium">{Math.round(concept.avg_score)}%</span>
                  </div>
                  <Progress value={concept.avg_score} className="h-2" />
                </div>
                
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground block">Attempts</span>
                    <span className="font-semibold">{concept.attempts_count}</span>
                    <span className="text-emerald-500 ml-2">({concept.success_count} ✓)</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Current Streak</span>
                    <span className="font-semibold text-amber-500">{concept.current_streak} 🔥</span>
                    <span className="text-muted-foreground text-xs ml-1">(Best: {concept.best_streak})</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-8 fade-in">
      <div className="flex flex-col md:flex-row justify-between gap-4 items-center">
        <div>
          <h1 className="text-3xl font-bold">Your Progress</h1>
          <p className="text-muted-foreground mt-1">Track your mastery across all concepts.</p>
        </div>
        
        {/* Simplified Rank Badge */}
        <div className="flex items-center gap-4 bg-card border rounded-lg px-6 py-3 shadow-sm">
          <div className="text-4xl">{data.rank_info.icon}</div>
          <div>
            <div className="font-bold text-lg">{data.rank_info.rank}</div>
            <div className="text-sm text-muted-foreground">{data.rank_info.current_xp} XP Total</div>
          </div>
        </div>
      </div>

      <Tabs defaultValue="sql" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-3 mb-6">
          <TabsTrigger value="sql">SQL</TabsTrigger>
          <TabsTrigger value="python">Python</TabsTrigger>
          <TabsTrigger value="pyspark">PySpark</TabsTrigger>
        </TabsList>
        
        <TabsContent value="sql" className="mt-0">
          {renderConcepts(data.sql_progress)}
        </TabsContent>
        <TabsContent value="python" className="mt-0">
          {renderConcepts(data.python_progress)}
        </TabsContent>
        <TabsContent value="pyspark" className="mt-0">
          {renderConcepts(data.pyspark_progress)}
        </TabsContent>
      </Tabs>
    </div>
  );
}
