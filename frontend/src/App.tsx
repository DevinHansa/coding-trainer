import { Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'sonner';
import { AppShell } from '@/components/AppShell';
import DashboardPage from '@/pages/DashboardPage';
import ExercisesPage from '@/pages/ExercisesPage';
import ProgressPage from '@/pages/ProgressPage';
import ExercisePage from '@/pages/ExercisePage';
import NotFoundPage from '@/pages/NotFoundPage';
import AuthPage from '@/pages/AuthPage';
import { AuthProvider, useAuth } from '@/AuthContext';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<AuthPage />} />
        
        {/* Protected application routes wrapped inside AppShell */}
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <AppShell>
                <Routes>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/exercises" element={<ExercisesPage />} />
                  <Route path="/exercise/:id" element={<ExercisePage />} />
                  <Route path="/progress" element={<ProgressPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </AppShell>
            </ProtectedRoute>
          }
        />
      </Routes>
      <Toaster position="bottom-right" richColors />
    </AuthProvider>
  );
}

export default App;
