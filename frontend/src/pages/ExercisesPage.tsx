import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';

import { useAuth } from '@/AuthContext';

export default function ExercisesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const categoryFilter = searchParams.get('category') || '';
  const [exercises, setExercises] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const { token } = useAuth();

  useEffect(() => {
    let url = '/api/exercises';
    if (categoryFilter) {
      url += `?category=${categoryFilter}`;
    }
    
    setLoading(true);
    fetch(url, {
      headers: {
        'x-auth-token': token || '',
      },
    })
      .then(res => res.json())
      .then(data => {
        setExercises(data);
        setLoading(false);
      })
      .catch(console.error);
  }, [categoryFilter, token]);

  const filteredExercises = exercises.filter(ex => 
    ex.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
    ex.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6 fade-in">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold">Exercises</h1>
          <p className="text-muted-foreground mt-1">Browse and practice coding problems.</p>
        </div>
        
        <div className="flex items-center gap-2 w-full md:w-auto">
          <Input 
            placeholder="Search exercises..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-[300px]"
          />
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 pb-2 overflow-x-auto">
        <Button 
          variant={categoryFilter === '' ? 'default' : 'outline'} 
          onClick={() => setSearchParams({})}
        >
          All
        </Button>
        <Button 
          variant={categoryFilter === 'sql' ? 'default' : 'outline'} 
          onClick={() => setSearchParams({ category: 'sql' })}
        >
          SQL
        </Button>
        <Button 
          variant={categoryFilter === 'python' ? 'default' : 'outline'} 
          onClick={() => setSearchParams({ category: 'python' })}
        >
          Python
        </Button>
        <Button 
          variant={categoryFilter === 'pyspark' ? 'default' : 'outline'} 
          onClick={() => setSearchParams({ category: 'pyspark' })}
        >
          PySpark
        </Button>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1,2,3,4,5,6].map(i => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : (
        <>
          {filteredExercises.length === 0 ? (
            <div className="text-center py-20 border rounded-lg bg-card text-muted-foreground">
              <div className="text-5xl mb-4">📭</div>
              <p>No exercises found matching your criteria.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredExercises.map(ex => (
                <Card key={ex.id} className="flex flex-col hover:shadow-md transition-shadow">
                  <CardHeader className="pb-3">
                    <div className="flex justify-between items-start mb-2">
                      <Badge variant="outline" className={
                        ex.category === 'sql' ? 'border-blue-500 text-blue-500' :
                        ex.category === 'python' ? 'border-purple-500 text-purple-500' :
                        'border-amber-500 text-amber-500'
                      }>
                        {ex.category.toUpperCase()}
                      </Badge>
                      <Badge variant="secondary">Lvl {ex.difficulty}</Badge>
                    </div>
                    <CardTitle className="text-xl line-clamp-1" title={ex.title}>
                      {ex.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex-1">
                    <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
                      {ex.description}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {ex.tags?.slice(0, 3).map((tag: string) => (
                        <Badge key={tag} variant="secondary" className="text-[10px] py-0 h-4">
                          {tag.replace(`${ex.category}:`, '')}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                  <CardFooter className="pt-0">
                    <Button asChild className="w-full">
                      <Link to={`/exercise/${ex.id}`}>Solve Problem</Link>
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
