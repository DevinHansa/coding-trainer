import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="text-6xl mb-6">🏜️</div>
      <h1 className="text-4xl font-bold mb-4">404 - Page Not Found</h1>
      <p className="text-xl text-muted-foreground mb-8">
        Looks like you've wandered into uncharted territory.
      </p>
      <Button asChild size="lg">
        <Link to="/">Return to Dashboard</Link>
      </Button>
    </div>
  );
}
